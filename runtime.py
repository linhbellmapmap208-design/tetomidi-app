import os
import sys


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel)


def setup_ffmpeg():
    # ffmpeg đi kèm trong app, đặt lên đầu PATH
    os.environ["PATH"] = resource_path("bin") + os.pathsep + os.environ["PATH"]


def gpu_info():
    """Trả về (có_gpu, tên_gpu, vram_GB)."""
    try:
        import torch
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            return True, p.name, round(p.total_memory / 1024 ** 3, 1)
    except Exception:
        pass
    return False, None, 0
