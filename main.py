import os
import sys
import queue
import traceback
import multiprocessing as mp
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from runtime import setup_ffmpeg, resource_path, gpu_info

setup_ffmpeg()

BG = "#000000"
PANEL = "#0d0d0d"
HOVER = "#1a1a1a"
BORDER = "#2a2a2a"
TEXT = "#ffffff"
MUTED = "#8a8a8a"


def output_dir():
    """Thư mục 'midi' cạnh exe; nếu không ghi được thì dùng Documents."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(".")
    d = os.path.join(base, "midi")
    try:
        os.makedirs(d, exist_ok=True)
        if not os.access(d, os.W_OK):
            raise OSError
    except OSError:
        d = os.path.join(os.path.expanduser("~"), "Documents", "tetomidi", "midi")
        os.makedirs(d, exist_ok=True)
    return d


def _worker(src, dst, q):
    """Chạy trong tiến trình riêng (GPU) để hủy được bằng terminate()."""
    try:
        sys.argv = ["transkun", src, dst, "--device", "cuda"]
        from transkun import transcribe
        try:
            transcribe.main()
        except SystemExit as e:
            if e.code not in (None, 0):
                raise RuntimeError(f"Transkun thoát với mã {e.code}")
        q.put(("done", dst))
    except Exception:
        q.put(("error", traceback.format_exc()))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("tetomidi")
        self.geometry("460x700")
        self.minsize(400, 620)
        self.configure(fg_color=BG)

        self.src = None
        self.proc = None
        self.q = None
        self.folder = None
        self.has_gpu, self.gpu_name, self.vram = gpu_info()

        self._build()

    def _build(self):
        wrap = ctk.CTkFrame(self, fg_color=BG)
        wrap.pack(fill="both", expand=True, padx=28, pady=24)

        logo_path = resource_path("assets/logo.png")
        if os.path.exists(logo_path):
            logo = ctk.CTkImage(Image.open(logo_path), size=(96, 96))
            ctk.CTkLabel(wrap, image=logo, text="").pack(pady=(8, 4))

        ctk.CTkLabel(wrap, text="tetomidi", text_color=TEXT,
                     font=ctk.CTkFont(size=26, weight="bold")).pack()
        ctk.CTkLabel(wrap, text="MP3 → MIDI", text_color=MUTED,
                     font=ctk.CTkFont(size=13)).pack(pady=(0, 22))

        # chọn file
        ctk.CTkButton(
            wrap, text="Chọn file MP3", height=44, corner_radius=12,
            fg_color=PANEL, hover_color=HOVER, border_width=1,
            border_color=BORDER, text_color=TEXT,
            command=self.pick_file).pack(fill="x")
        self.file_lbl = ctk.CTkLabel(
            wrap, text="Chưa chọn file", text_color=MUTED,
            font=ctk.CTkFont(size=12), wraplength=380)
        self.file_lbl.pack(pady=(8, 18))

        # model
        ctk.CTkLabel(wrap, text="Model", text_color=MUTED, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x")
        self.model = ctk.CTkOptionMenu(
            wrap, values=["Transkun V2"], height=40, corner_radius=12,
            fg_color=PANEL, button_color=PANEL, button_hover_color=HOVER,
            dropdown_fg_color=PANEL, dropdown_hover_color=HOVER,
            text_color=TEXT)
        self.model.pack(fill="x", pady=(4, 14))

        # thiết bị (GPU)
        ctk.CTkLabel(wrap, text="Thiết bị", text_color=MUTED, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x")
        dev = ctk.CTkFrame(wrap, fg_color=PANEL, corner_radius=12,
                           border_width=1, border_color=BORDER, height=40)
        dev.pack(fill="x", pady=(4, 6))
        dev.pack_propagate(False)
        if self.has_gpu:
            dev_text = f"GPU: {self.gpu_name} · {self.vram} GB"
        else:
            dev_text = "Không tìm thấy GPU NVIDIA"
        ctk.CTkLabel(dev, text=dev_text, text_color=TEXT,
                     font=ctk.CTkFont(size=13)).pack(expand=True)
        hint = "" if self.has_gpu else \
            "Cần card NVIDIA và driver mới nhất để dùng app này."
        ctk.CTkLabel(wrap, text=hint, text_color=MUTED,
                     font=ctk.CTkFont(size=12), wraplength=380
                     ).pack(pady=(0, 22))

        # nút chạy + hủy
        row = ctk.CTkFrame(wrap, fg_color=BG)
        row.pack(fill="x")
        self.go_btn = ctk.CTkButton(
            row, text="Transcribe", height=48, corner_radius=14,
            fg_color=TEXT, hover_color="#d0d0d0", text_color="#000000",
            font=ctk.CTkFont(size=15, weight="bold"), command=self.start,
            state="normal" if self.has_gpu else "disabled")
        self.go_btn.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ctk.CTkButton(
            row, text="✕", width=48, height=48, corner_radius=14,
            fg_color=PANEL, hover_color=HOVER, border_width=1,
            border_color=BORDER, text_color=TEXT, command=self.cancel)

        self.status = ctk.CTkLabel(
            wrap, text="", text_color=MUTED, font=ctk.CTkFont(size=12),
            wraplength=380, justify="center")
        self.status.pack(pady=(18, 0))

        self.bar = ctk.CTkProgressBar(
            wrap, mode="indeterminate", height=4,
            fg_color=PANEL, progress_color=TEXT)

        self.open_btn = ctk.CTkButton(
            wrap, text="Mở thư mục midi", height=40, corner_radius=12,
            fg_color=PANEL, hover_color=HOVER, border_width=1,
            border_color=BORDER, text_color=TEXT,
            command=lambda: os.startfile(self.folder))

    # ---------- hành động ----------
    def pick_file(self):
        p = filedialog.askopenfilename(
            filetypes=[("Audio", "*.mp3 *.wav *.flac *.m4a *.ogg")])
        if p:
            self.src = p
            self.file_lbl.configure(text=os.path.basename(p), text_color=TEXT)
            self.status.configure(text="")

    def start(self):
        if not self.src:
            self.status.configure(text="Hãy chọn file trước.")
            return
        name = os.path.splitext(os.path.basename(self.src))[0] + ".mid"
        dst = os.path.join(output_dir(), name)
        self.open_btn.pack_forget()

        self.q = mp.Queue()
        self.proc = mp.Process(target=_worker,
                               args=(self.src, dst, self.q), daemon=True)
        self.proc.start()

        self.go_btn.configure(state="disabled", text="Đang xử lý…")
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.bar.pack(fill="x", pady=(18, 0), before=self.status)
        self.bar.start()
        self.status.configure(text="Đang chuyển sang MIDI bằng GPU…")
        self.after(300, self.poll)

    def poll(self):
        if self.proc is None:
            return
        try:
            kind, msg = self.q.get_nowait()
        except queue.Empty:
            if self.proc.is_alive():
                self.after(300, self.poll)
            else:
                self.finish("Tiến trình dừng đột ngột.")
            return
        if kind == "done":
            self.finish(f"Xong: {os.path.basename(msg)}",
                        os.path.dirname(msg))
        else:
            self.finish("Lỗi:\n" + msg[-400:])

    def cancel(self):
        if self.proc and self.proc.is_alive():
            self.proc.terminate()
        self.finish("Đã hủy.")

    def finish(self, text, folder=None):
        self.proc = None
        self.bar.stop()
        self.bar.pack_forget()
        self.cancel_btn.pack_forget()
        self.go_btn.configure(state="normal", text="Transcribe")
        self.status.configure(text=text)
        if folder:
            self.folder = folder
            self.open_btn.pack(fill="x", pady=(12, 0))


if __name__ == "__main__":
    mp.freeze_support()
    App().mainloop()
