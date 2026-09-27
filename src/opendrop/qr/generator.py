import io
from pathlib import Path

try:
    import qrcode
    HAS_QR = True
except ImportError:
    HAS_QR = False


def generate_qr_png(url: str) -> bytes | None:
    if not HAS_QR:
        return None
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
