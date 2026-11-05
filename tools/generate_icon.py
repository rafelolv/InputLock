"""Rebuild the original InputLock vector mark as Windows icon sizes."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((16, 16, 1008, 1008), radius=230, fill="#c4f56b")
draw.arc((320, 190, 704, 630), 180, 360, fill="#19220e", width=68)
draw.rounded_rectangle((258, 406, 766, 814), radius=76, fill="#19220e")
draw.ellipse((474, 530, 550, 606), fill="#c4f56b")
draw.rounded_rectangle((492, 560, 532, 675), radius=18, fill="#c4f56b")
image.resize((256, 256), Image.Resampling.LANCZOS).save(ROOT / "assets/icon.png")
image.save(ROOT / "assets/icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
