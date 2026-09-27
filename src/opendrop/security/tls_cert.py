"""Self-signed TLS certificate for the OpenDrop server.

The server speaks HTTPS only: QR-code scanning (getUserMedia) and keeping
traffic confidential on the LAN require a secure context, which
"http://<private ip>" can never provide.

The certificate is generated locally (EC P-256 key, self-signed, SHA-256)
with the current IP in the SAN. It is regenerated automatically when:
  - the file is missing or unreadable,
  - it expires in less than 30 days,
  - the current IP is no longer in the SAN (DHCP change).

To force a regeneration: delete the certs\\ folder.

The self-signed certificate triggers a trust warning on the first visit from
a phone ("Continue" / "Show this website"): this is expected, and it does not
block the camera.
"""
import datetime
import ipaddress
import os
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from opendrop.config.config import get_config_dir

CERT_FILE = "server.crt"
KEY_FILE = "server.key"
VALIDITY_DAYS = 397
RENEW_BEFORE_DAYS = 30


def get_cert_dir(directory: str | Path | None = None) -> Path:
    return Path(directory) if directory else get_config_dir() / "certs"


def ensure_certificate(ip: str, directory: str | Path | None = None) -> tuple[Path, Path]:
    """Return a valid (cert, key) pair for this IP, generating it if needed."""
    base = get_cert_dir(directory)
    cert_path = base / CERT_FILE
    key_path = base / KEY_FILE

    if _is_valid(cert_path, key_path, ip):
        return cert_path, key_path

    base.mkdir(parents=True, exist_ok=True)
    _generate(cert_path, key_path, ip)
    return cert_path, key_path


def _ip_list(value: str | None) -> list:
    if not value:
        return []
    try:
        return [ipaddress.ip_address(value)]
    except ValueError:
        return []


def _is_valid(cert_path: Path, key_path: Path, ip: str) -> bool:
    if not (cert_path.is_file() and key_path.is_file()):
        return False
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    except (ValueError, OSError, TypeError):
        return False

    if cert.not_valid_after_utc <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=RENEW_BEFORE_DAYS):
        return False

    if not isinstance(key, ec.EllipticCurvePrivateKey):
        return False
    try:
        if key.public_key().public_numbers() != cert.public_key().public_numbers():
            return False
    except (ValueError, AttributeError):
        return False

    # iOS/Safari rejects a certificate without the serverAuth EKU: regenerate.
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if x509.ExtendedKeyUsageOID.SERVER_AUTH not in eku:
            return False
    except x509.ExtensionNotFound:
        return False

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return False
    wanted = _ip_list(ip)
    if not wanted or wanted[0] not in san.get_values_for_type(x509.IPAddress):
        return False
    return True


def _san_entries(ip: str) -> list:
    entries: list = [x509.DNSName("localhost")]
    hostname = socket.gethostname()
    if hostname:
        try:
            entries.append(x509.DNSName(hostname))
        except (UnicodeError, ValueError):
            pass
    for value in ("127.0.0.1", ip):
        for addr in _ip_list(value):
            entries.append(x509.IPAddress(addr))
    return entries


def _generate(cert_path: Path, key_path: Path, ip: str) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.datetime.now(datetime.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OpenDrop")])

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=VALIDITY_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(_san_entries(ip)),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=True, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    _atomic_write(cert_path, cert.public_bytes(serialization.Encoding.PEM))
    _atomic_write(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
