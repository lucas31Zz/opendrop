"""Generate the project icons: app.ico (Windows) and app.png (Linux .desktop).

The logo is a QR code pointing to the repository (with a rounded white border).
Run it from the repo root: python tools/make_icon.py
"""
import io
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop" / "OpenDrop"
LINUX = ROOT / "packaging" / "linux"

URL = "https://github.com/lucas31Zz/opendrop"
SIZE = 512          # final image
PADDING = 64        # white margin


def make_image() -> Image.Image:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=16, border=1)
    qr.add_data(URL)
    qr.make(fit=True)
    modules = qr.modules_count

    img = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(img)

    # Background: white square with slightly tinted corners (the project hue).
    draw.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=72, fill="white")

    # Centered black QR, without whitening the edges.
    inner = SIZE - 2 * PADDING
    cell = inner / modules
    for r in range(modules):
        for c in range(modules):
            if qr.modules[r][c]:
                x0 = PADDING + c * cell
                y0 = PADDING + r * cell
                draw.rectangle([x0, y0, x0 + cell, y0 + cell], fill="black")
    return img


def main() -> None:
    img = make_image()

    DESKTOP.mkdir(parents=True, exist_ok=True)
    LINUX.mkdir(parents=True, exist_ok=True)

    img.save(DESKTOP / "app.png")

    # 256px .png for the Linux .desktop
    img.resize((256, 256), Image.LANCZOS).save(LINUX / "opendrop.png")

    # .ico for the Windows installer
    img.save(DESKTOP / "app.ico",
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    print(f"OK: {DESKTOP / 'app.png'}")
    print(f"OK: {DESKTOP / 'app.ico'}")
    print(f"OK: {LINUX / 'opendrop.png'}")


if __name__ == "__main__":
    main()
