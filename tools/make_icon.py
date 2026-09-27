"""Genere les icones du projet : app.ico (Windows) et app.png (Linux .desktop).

Le logo est un QR code pointant vers le depot (avec bordure blanche arrondie).
A lancer depuis la racine : python tools/make_icon.py
"""
import io
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop" / "OpenDrop"
LINUX = ROOT / "packaging" / "linux"

URL = "https://github.com/lucas31Zz/opendrop"
SIZE = 512          # image finale
PADDING = 64        # marge blanche


def make_image() -> Image.Image:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=16, border=1)
    qr.add_data(URL)
    qr.make(fit=True)
    modules = qr.modules_count

    img = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(img)

    # Fond : carre blanc avec coins legerement colores (teinte du projet).
    draw.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=72, fill="white")

    # QR centre, noir, sans blanchir les bords.
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

    # .png 256 pour le .desktop Linux
    img.resize((256, 256), Image.LANCZOS).save(LINUX / "opendrop.png")

    # .ico pour l'installeur Windows
    img.save(DESKTOP / "app.ico",
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    print(f"OK: {DESKTOP / 'app.png'}")
    print(f"OK: {DESKTOP / 'app.ico'}")
    print(f"OK: {LINUX / 'opendrop.png'}")


if __name__ == "__main__":
    main()
