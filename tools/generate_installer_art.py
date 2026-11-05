"""Generate installer branding from the app icon. No generated artwork or slogans."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCALE = 3


def font(size, bold=False):
    paths = [Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf"),
             Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")]
    return ImageFont.truetype(str(next(path for path in paths if path.exists())), size * SCALE)


def main():
    icon = Image.open(ROOT / "assets/icon.png").convert("RGBA")
    sidebar = Image.new("RGB", (164 * SCALE, 314 * SCALE), "#20242b")
    mark = icon.resize((66 * SCALE, 66 * SCALE), Image.Resampling.LANCZOS)
    sidebar.paste(mark, (18 * SCALE, 28 * SCALE), mark)
    pen = ImageDraw.Draw(sidebar)
    pen.text((23 * SCALE, 106 * SCALE), "InputLock", font=font(20, True), fill="#ffffff")
    pen.text((23 * SCALE, 274 * SCALE), "made by", font=font(9), fill="#b6bec9")
    pen.text((23 * SCALE, 289 * SCALE), "rafaelolv", font=font(10), fill="#ffffff")
    sidebar.save(ROOT / "assets/installer-sidebar.png")
    header = Image.new("RGBA", (64 * SCALE, 64 * SCALE))
    mark = icon.resize((48 * SCALE, 48 * SCALE), Image.Resampling.LANCZOS)
    header.alpha_composite(mark, (8 * SCALE, 8 * SCALE))
    header.save(ROOT / "assets/installer-header.png")


if __name__ == "__main__":
    main()
