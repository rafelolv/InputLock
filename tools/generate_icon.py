"""Rebuild the original InputLock vector mark as Windows icon sizes."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((16, 16, 1008, 1008), radius=230, fill="#1764ff")
draw.arc((320, 190, 704, 630), 180, 360, fill="#ffffff", width=68)
draw.rounded_rectangle((258, 406, 766, 814), radius=76, fill="#ffffff")
draw.ellipse((474, 530, 550, 606), fill="#1764ff")
draw.rounded_rectangle((492, 560, 532, 675), radius=18, fill="#1764ff")
image.resize((256, 256), Image.Resampling.LANCZOS).save(ROOT / "assets/icon.png")
image.save(ROOT / "assets/icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

# Device icons are rendered at 4x and downsampled for smooth edges.
for kind in ("keyboard", "mouse"):
    icon = Image.new("RGBA", (192, 192))
    pen = ImageDraw.Draw(icon)
    color = "#1764ff"
    if kind == "keyboard":
        pen.rounded_rectangle((16, 44, 176, 148), radius=16, outline=color, width=9)
        for row in (68, 92):
            for col in (42, 68, 94, 120, 146):
                pen.rounded_rectangle((col, row, col + 9, row + 9), radius=2, fill=color)
        pen.rounded_rectangle((62, 119, 130, 128), radius=4, fill=color)
    else:
        pen.rounded_rectangle((48, 16, 144, 176), radius=46, outline=color, width=9)
        pen.line((96, 20, 96, 81), fill=color, width=8)
        pen.line((52, 84, 140, 84), fill=color, width=8)
    icon.resize((48, 48), Image.Resampling.LANCZOS).save(ROOT / f"assets/{kind}.png")
    active = icon.copy()
    active.putdata([(255, 255, 255, pixel[3]) for pixel in active.getdata()])
    active.resize((48, 48), Image.Resampling.LANCZOS).save(ROOT / f"assets/{kind}_active.png")
