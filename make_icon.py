import os
from PIL import Image

if os.path.exists("assets/logo.png"):
    Image.open("assets/logo.png").convert("RGBA").save(
        "assets/tetomidi.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
