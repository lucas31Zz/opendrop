"""Generate the project's ROUND icon master: `desktop/src-tauri/icons/icon.png`.

The source is the project logo, kept in docs/screenshots/OpenDrop_Logo.webp.
Run it from the repo root: python tools/make_icon.py

Every image this script writes is masked to a circle FIRST (centre 256,256
in the 512x512 master, radius ~255, drawn on a canvas 4x larger and
downsampled with LANCZOS, then MULTIPLIED into the alpha channel), so a
square output is impossible: the shape the author validated is baked into
the master itself, and nothing downstream can smooth it away.

It deliberately writes no .ico/.icns of its own - only the masked master
and the Linux .desktop icon. After running, regenerate the full set with:
    npx tauri icon desktop/src-tauri/icons/icon.png
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop" / "src-tauri" / "icons"
LINUX = ROOT / "packaging" / "linux"
SOURCE = ROOT / "docs" / "screenshots" / "OpenDrop_Logo.webp"

SIZE = 512          # master square
CENTER = SIZE // 2   # 256
RADIUS = 255         # ~255/512: the geometry that made the icon round
SS = 4               # supersampling factor for the mask's edge


def save_png(img: Image.Image, path: Path) -> None:
    img.save(path, format="PNG", optimize=True, compress_level=9)


def circle_alpha(size: int = SIZE, radius: int = RADIUS, ss: int = SS) -> Image.Image:
    """Antialiased circular alpha mask, `size` pixels square.

    Drawn on a canvas `ss` times larger and downsampled with LANCZOS: a
    direct ellipse at final size leaves a staircase, the supersampled one
    leaves the smooth rim the round icon needs.
    """
    big = size * ss
    mask = Image.new("L", (big, big), 0)
    half = radius * ss
    c = size * ss // 2
    ImageDraw.Draw(mask).ellipse((c - half, c - half, c + half, c + half), fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def make_image() -> Image.Image:
    """The logo resized to the master, then cut to the circle.

    The mask is MULTIPLIED into the alpha the source already carries, so
    it can only ever remove pixels - whatever alpha arrives, the corners
    end up at 0.
    """
    logo = Image.open(SOURCE).convert("RGBA")
    master = logo.resize((SIZE, SIZE), Image.LANCZOS)
    master.putalpha(ImageChops.multiply(master.getchannel("A"), circle_alpha()))
    return master


def main() -> None:
    img = make_image()

    DESKTOP.mkdir(parents=True, exist_ok=True)
    LINUX.mkdir(parents=True, exist_ok=True)

    # The masked 512 master: `npx tauri icon` derives the whole set from
    # it, so the .ico, .icns and every PNG come out round too.
    save_png(img, DESKTOP / "icon.png")

    # Masked 256px .png for the Linux .desktop entry (Icon=opendrop).
    save_png(img.resize((256, 256), Image.LANCZOS), LINUX / "opendrop.png")

    print(f"OK: {DESKTOP / 'icon.png'}")
    print(f"OK: {LINUX / 'opendrop.png'}")
    print("Now regenerate the full set: npx tauri icon desktop/src-tauri/icons/icon.png")


if __name__ == "__main__":
    main()
