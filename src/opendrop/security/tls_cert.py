"""TLS certificates for the OpenDrop server: a local CA plus a leaf.

The server speaks HTTPS only: QR-code scanning (getUserMedia) and keeping
traffic confidential on the LAN require a secure context, which
"http://<private ip>" can never provide.

Two files live side by side in the certs\\ folder:
  - ca.crt / ca.key: the local certificate authority ("OpenDrop Local
    CA", EC P-256, ~20 years). It is created ONCE and persisted: no IP
    change, no leaf renewal and no app update ever regenerates it. It is
    only replaced when it is missing, unreadable or expired - which is
    exactly when devices would have to trust a new anchor anyway.
  - server.crt / server.key: the serving certificate, a leaf SIGNED by
    that CA with the current IP in the SAN. It is regenerated (and
    silently re-signed by the same CA) when:
      - the file is missing or unreadable,
      - it expires in less than 30 days,
      - the current IP is no longer in the SAN (DHCP change),
      - it is not issued by our CA (a leftover self-signed certificate
        from an older install).

Because the CA never changes, a device that trusts it once keeps a green
"secure connection" across updates, IP changes and renewals: no browser
warning, no "Not secure" badge. The anchor is served without a token on
GET /ca.crt (it is a trust anchor, not a secret) and the in-app
Settings > Security section walks through the one-time install per OS.

To force a full regeneration (every device must trust the new CA):
delete the certs\\ folder.
"""
import datetime
import ipaddress
import os
import socket
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from opendrop.config.config import get_config_dir

CERT_FILE = "server.crt"
KEY_FILE = "server.key"
CA_CERT_FILE = "ca.crt"
CA_KEY_FILE = "ca.key"
VALIDITY_DAYS = 397
# The anchor must outlive every leaf it signs by far: ~20 years.
CA_VALIDITY_DAYS = 7300
RENEW_BEFORE_DAYS = 30


def get_cert_dir(directory: str | Path | None = None) -> Path:
    return Path(directory) if directory else get_config_dir() / "certs"


def ensure_certificate(ip: str, directory: str | Path | None = None) -> tuple[Path, Path]:
    """Return a valid (cert, key) pair for this IP.

    The local CA is ensured first: the leaf is issued by it, and an old
    self-signed leaf (pre-CA install) fails verification and is re-signed.
    """
    base = get_cert_dir(directory)
    ca_cert_path, ca_key_path = ensure_ca(directory=base)
    cert_path = base / CERT_FILE
    key_path = base / KEY_FILE

    if _is_valid(cert_path, key_path, ip, ca_cert_path):
        return cert_path, key_path

    base.mkdir(parents=True, exist_ok=True)
    _generate(cert_path, key_path, ip, ca_cert_path, ca_key_path)
    return cert_path, key_path


def ensure_ca(directory: str | Path | None = None) -> tuple[Path, Path]:
    """Return the persistent local CA (cert, key), generating it once.

    This is the trust anchor devices install once (GET /ca.crt): it must
    stay byte-identical across leaf renewals, IP changes and app
    updates, so it is regenerated ONLY when unusable (missing,
    unreadable, expired soon, or not actually a CA).
    """
    base = get_cert_dir(directory)
    cert_path = base / CA_CERT_FILE
    key_path = base / CA_KEY_FILE

    if _ca_is_valid(cert_path, key_path):
        return cert_path, key_path

    base.mkdir(parents=True, exist_ok=True)
    _generate_ca(cert_path, key_path)
    return cert_path, key_path


def _ip_list(value: str | None) -> list:
    if not value:
        return []
    try:
        return [ipaddress.ip_address(value)]
    except ValueError:
        return []


def _load_pair(cert_path: Path, key_path: Path):
    """(cert, key) or None when either file is missing/unreadable."""
    if not (cert_path.is_file() and key_path.is_file()):
        return None
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    except (ValueError, OSError, TypeError):
        return None
    return cert, key


def _ca_is_valid(cert_path: Path, key_path: Path) -> bool:
    pair = _load_pair(cert_path, key_path)
    if pair is None:
        return False
    cert, key = pair

    # Never let the anchor expire under the leaves it signed: renew it
    # with the same 30 day margin as the serving certificate.
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

    # A real anchor: self-signed, BasicConstraints CA, keyCertSign set.
    # Anything else (a leaf, a foreign CA, a corrupted file) is replaced.
    try:
        if cert.issuer != cert.subject:
            return False
        cert.verify_directly_issued_by(cert)
    except (ValueError, TypeError, InvalidSignature):
        return False
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        if not bc.ca:
            return False
    except x509.ExtensionNotFound:
        return False
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not ku.key_cert_sign:
            return False
    except x509.ExtensionNotFound:
        return False
    return True


def _is_valid(cert_path: Path, key_path: Path, ip: str, ca_cert_path: Path) -> bool:
    pair = _load_pair(cert_path, key_path)
    if pair is None:
        return False
    cert, key = pair

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

    # Must be issued by OUR CA and verify against it: a leftover
    # self-signed certificate (older install) or a foreign issuer is
    # re-signed here - the CA itself never changes for that.
    try:
        ca = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
        cert.verify_directly_issued_by(ca)
    except (ValueError, OSError, TypeError, InvalidSignature):
        return False

    # The serving certificate must never act as a CA itself.
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        if bc.ca:
            return False
    except x509.ExtensionNotFound:
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


def _write_key(path: Path, key) -> None:
    _atomic_write(
        path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _generate_ca(cert_path: Path, key_path: Path) -> None:
    """Create the local CA: self-signed anchor, ~20 years, path_length 0."""
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.datetime.now(datetime.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OpenDrop Local CA")])

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=CA_VALIDITY_DAYS))
        # path_length 0: this CA may sign leaves only - never another CA.
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
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
    _write_key(key_path, key)


def _generate(cert_path: Path, key_path: Path, ip: str,
              ca_cert_path: Path, ca_key_path: Path) -> None:
    """Issue the serving certificate, signed by the local CA."""
    ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
    ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.datetime.now(datetime.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OpenDrop")])

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=VALIDITY_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(_san_entries(ip)),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
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
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    _atomic_write(cert_path, cert.public_bytes(serialization.Encoding.PEM))
    _write_key(key_path, key)


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
