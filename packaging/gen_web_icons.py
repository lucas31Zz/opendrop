"""Generate the committed web/PWA icon assets.

Run from the repo root:  python packaging/gen_web_icons.py

One design, one script - a rounded square #0f0f0f background drawn on a
64-unit grid, with a white envelope glyph (a rectangle body plus a
polygon flap cut out of the top edge). Outputs exactly four files:

    web/icons/icon-192.png           192x192 rounded square
    web/icons/icon-512.png           512x512 rounded square
    web/icons/icon-maskable-512.png  512x512 FULL-BLEED square (no
                                     rounded corners), glyph shrunk
                                     inside the 80% safe circle
    web/favicon.ico                  multi-size ICO (16 + 32 + 48)

Pillow is already a product dependency via qrcode[pil]: this generator
adds NOTHING to the dependency set. The generated files are the
committed assets - re-run this script only when the design changes.
"""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ICONS_DIR = os.path.join(ROOT, "web", "icons")

GRID = 64           # design grid: every coordinate below is in units
BG = (15, 15, 15)   # #0f0f0f - the app's theme colour
FG = (255, 255, 255)
RADIUS = 14         # rounded-corner radius of the square, in units
SS = 4              # supersampling factor: draw big, downsample (AA)

# Envelope glyph on the grid: a white body rectangle...
BODY = (14, 20, 50, 44)                    # x1, y1, x2, y2
# ...and the polygon flap: a V notch cut out of the body's top edge,
# filled with the background colour - the classic open-envelope glyph.
FLAP = [(14, 20), (32, 33), (50, 20)]

# Maskable icons live inside a circular safe zone of 80% of the width:
# the glyph must stay within a radius of 0.4 * GRID around the centre.
MASKABLE_SCALE = 0.85


def _scaled(x, y, scale):
    """A grid point scaled about the grid centre (32, 32)."""
    return 32 + (x - 32) * scale, 32 + (y - 32) * scale


def _safe_for_maskable(scale):
    """Worst-case glyph corner distance vs. the 80% safe circle radius."""
    worst = max(
        math.hypot(x - 32, y - 32)
        for x in (BODY[0], BODY[2])
        for y in (BODY[1], BODY[3])
    )
    return worst * scale <= 0.4 * GRID


def render(size, rounded=True, scale=1.0):
    """One icon at `size` px: drawn at SSx, then downsampled."""
    assert rounded or _safe_for_maskable(scale), \
        "maskable glyph would escape the 80% safe circle"
    big = size * SS
    u = big / GRID
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background: rounded square, or full-bleed square for maskable.
    if rounded:
        draw.rounded_rectangle([0, 0, big - 1, big - 1],
                               radius=int(RADIUS * u), fill=BG + (255,))
    else:
        draw.rectangle([0, 0, big - 1, big - 1], fill=BG + (255,))

    # Envelope body (white) ...
    bx1, by1 = _scaled(BODY[0], BODY[1], scale)
    bx2, by2 = _scaled(BODY[2], BODY[3], scale)
    draw.rectangle([bx1 * u, by1 * u, bx2 * u, by2 * u], fill=FG + (255,))
    # ... and the flap notch on top of it (background colour).
    draw.polygon([tuple(c * u for c in _scaled(x, y, scale))
                  for x, y in FLAP], fill=BG + (255,))

    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(ICONS_DIR, exist_ok=True)
    outputs = [
        (os.path.join(ICONS_DIR, "icon-192.png"),
         render(192, rounded=True, scale=1.0)),
        (os.path.join(ICONS_DIR, "icon-512.png"),
         render(512, rounded=True, scale=1.0)),
        (os.path.join(ICONS_DIR, "icon-maskable-512.png"),
         render(512, rounded=False, scale=MASKABLE_SCALE)),
    ]
    # favicon.ico: one base image, three embedded sizes.
    favicon = render(48, rounded=True, scale=1.0)
    favicon_path = os.path.join(ROOT, "web", "favicon.ico")

    for path, img in outputs:
        img.save(path)
    favicon.save(favicon_path, format="ICO",
                 sizes=[(16, 16), (32, 32), (48, 48)])

    for path, _ in outputs:
        print(f"{os.path.relpath(path, ROOT)} {Image.open(path).size}")
    ico = Image.open(favicon_path)
    print(f"web/favicon.ico {ico.size} sizes={sorted(ico.info.get('sizes', []))}")


if __name__ == "__main__":
    main()
