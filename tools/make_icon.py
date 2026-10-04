"""Generate the project icons: app.ico (Windows) and opendrop.png (Linux .desktop).

The source is the project logo, kept in docs/screenshots/OpenDrop_Logo.webp.
Run it from the repo root: python tools/make_icon.py
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop" / "OpenDrop"
LINUX = ROOT / "packaging" / "linux"
SOURCE = ROOT / "docs" / "screenshots" / "OpenDrop_Logo.webp"

SIZE = 512          # final image
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def save_png(img: Image.Image, path: Path) -> None:
    img.save(path, format="PNG", optimize=True, compress_level=9)


def make_image() -> Image.Image:
    logo = Image.open(SOURCE).convert("RGB")
    return logo.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    img = make_image()

    DESKTOP.mkdir(parents=True, exist_ok=True)
    LINUX.mkdir(parents=True, exist_ok=True)

    # 256px .png for the Linux .desktop
    save_png(img.resize((256, 256), Image.LANCZOS), LINUX / "opendrop.png")

    # .ico for the Windows installer and for the window/tray icon
    img.save(DESKTOP / "app.ico", sizes=ICO_SIZES)

    print(f"OK: {DESKTOP / 'app.ico'}")
    print(f"OK: {LINUX / 'opendrop.png'}")


if __name__ == "__main__":
    main()
