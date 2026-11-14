"""Tests for the HTTPS layer: TLS socket, certificate, regeneration."""
import datetime
import ipaddress
import os
import socket
import ssl
import sys
import tempfile
import shutil
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from tests.conftest import _start_server, cert_dir, ip, TestResult
from opendrop.security import tls_cert

r = TestResult()


def _load_cert_key(directory=None):
    base = directory or cert_dir
    cert = x509.load_pem_x509_certificate(
        open(os.path.join(base, tls_cert.CERT_FILE), "rb").read())
    key = serialization.load_pem_private_key(
        open(os.path.join(base, tls_cert.KEY_FILE), "rb").read(), password=None)
    return cert, key


def _pub_bytes(key):
    """SPKI DER: accepts a private or already-public key."""
    pub = key.public_key() if hasattr(key, "public_key") else key
    return pub.public_bytes(serialization.Encoding.DER,
                            serialization.PublicFormat.SubjectPublicKeyInfo)


def _dates(cert):
    """(start, end): the UTC attributes avoid cryptography warnings."""
    if hasattr(cert, "not_valid_after_utc"):
        return cert.not_valid_before_utc, cert.not_valid_after_utc
    return cert.not_valid_before, cert.not_valid_after


def _write_short_cert(cert_path, key_path, target_ip, days):
    """Valid certificate that expires soon (renewal test)."""
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.datetime.now(datetime.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OpenDrop")])
    cert = (x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=days))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address(target_ip)),
            ]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None),
                           critical=True)
            .add_extension(x509.ExtendedKeyUsage(
                [x509.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))


def _get(port, path, timeout=5):
    ctx = ssl._create_unverified_context()
    with ctx.wrap_socket(socket.create_connection((ip, port), timeout=timeout),
                         server_hostname=ip) as sock:
        sock.sendall(
            f"GET {path} HTTP/1.1\r\nHost: {ip}\r\nConnection: close\r\n\r\n".encode()
        )
        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks)


def test_tls():
    server, port, token = _start_server()

    print("--- TLS tests ---\n")

    # Plain TLS handshake answers an HTTP response
    try:
        raw = _get(port, "/api/info")
        status = raw.split(b" ")[1] if b" " in raw else b"?"
        r.check("TLS handshake serves /api/info", status == b"200", raw[:40])
    except Exception as e:
        r.check("TLS handshake serves /api/info", False, str(e))

    # Certificate exists and carries the server IP in its SAN
    try:
        cert_path = os.path.join(cert_dir, tls_cert.CERT_FILE)
        cert = x509.load_pem_x509_certificate(open(cert_path, "rb").read())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        ips = san.get_values_for_type(x509.IPAddress)
        r.check("Certificate SAN has 127.0.0.1",
                any(str(v) == ip for v in ips), [str(v) for v in ips])
    except Exception as e:
        r.check("Certificate SAN has 127.0.0.1", False, str(e))

    # Authenticity: the serving certificate is issued by the LOCAL CA
    # (self-signed anchor, BasicConstraints ca), the leaf is not a CA
    # itself, the key matches, server EKU and expected lifetimes.
    try:
        cert, key = _load_cert_key()
        ca = x509.load_pem_x509_certificate(
            open(os.path.join(cert_dir, tls_cert.CA_CERT_FILE), "rb").read())
        r.check("Certificate issued by the local CA (issuer == CA subject)",
                cert.issuer == ca.subject, f"{cert.issuer} / {ca.subject}")
        cert.verify_directly_issued_by(ca)
        r.check("Certificate signature verifies against the CA", True)
        r.check("CA certificate is self-signed (issuer == subject)",
                ca.issuer == ca.subject, f"{ca.issuer} / {ca.subject}")
        ca.verify_directly_issued_by(ca)
        r.check("CA signature verifies against itself", True)
        bc_ca = ca.extensions.get_extension_for_class(x509.BasicConstraints).value
        r.check("CA carries BasicConstraints ca=True", bc_ca.ca is True, bc_ca.ca)
        bc_leaf = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        r.check("Serving certificate is not a CA (ca=False)",
                bc_leaf.ca is False, bc_leaf.ca)
        r.check("Private key matches certificate",
                _pub_bytes(key) == _pub_bytes(cert.public_key()))
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        r.check("Certificate has serverAuth EKU",
                x509.ExtendedKeyUsageOID.SERVER_AUTH in eku, list(eku))
        # not_valid_before = now - 1 day (clock margin) and
        # not_valid_after = now + 397 days.
        jours = (_dates(cert)[1] - _dates(cert)[0]).days
        r.check("Certificate lifetime is ~397 days", 397 <= jours <= 398, jours)
        # The anchor must outlive every leaf it signs (~20 years).
        ca_jours = (_dates(ca)[1] - _dates(ca)[0]).days
        r.check("CA lifetime is ~7300 days", ca_jours >= 7000, ca_jours)
    except Exception as e:
        r.check("Certificate authenticity checks", False, str(e))

    # The local CA is NOT in the system trust store: until the device
    # installs it once (Settings > Security, GET /ca.crt), the browser
    # must show its warning (TOFU). After the install: green padlock.
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.create_connection((ip, port), timeout=5),
                             server_hostname=ip) as sock:
            sock.sendall(b"GET /api/info HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
            sock.recv(64)
        r.check("Certificate not trusted until the CA is installed",
                False, "the trusted handshake succeeded")
    except ssl.SSLCertVerificationError as e:
        r.check("Certificate not trusted until the CA is installed", True,
                str(e)[:120])
    except Exception as e:
        r.check("Certificate not trusted until the CA is installed", False, str(e))

    # GET /ca.crt serves the anchor itself: 200, exactly the ca.crt
    # bytes, no private key inside, as a downloadable attachment.
    try:
        raw = _get(port, "/ca.crt")
        head, sep, body = raw.partition(b"\r\n\r\n")
        status = head.split(b" ")[1] if b" " in head else b"?"
        r.check("GET /ca.crt = 200", status == b"200", head[:60])
        ca_on_disk = open(os.path.join(cert_dir, tls_cert.CA_CERT_FILE), "rb").read()
        r.check("GET /ca.crt body is exactly the CA certificate",
                bool(sep) and body == ca_on_disk,
                f"{len(body)} vs {len(ca_on_disk)} bytes")
        r.check("GET /ca.crt leaks no private key",
                b"PRIVATE KEY" not in body, body[:40])
        r.check("GET /ca.crt is a downloadable attachment",
                b'Content-Disposition: attachment; filename="OpenDrop-ca.crt"' in head,
                head[:200])
    except Exception as e:
        r.check("GET /ca.crt route", False, str(e))

    # Plaintext HTTP must not get an HTTP answer on a TLS port
    try:
        sock = socket.create_connection((ip, port), timeout=5)
        sock.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        try:
            data = sock.recv(4096)
        except (ssl.SSLError, OSError):
            data = b""
        finally:
            sock.close()
        r.check("Plaintext HTTP rejected", not data.startswith(b"HTTP/1.1"), data[:40])
    except Exception as e:
        r.check("Plaintext HTTP rejected", False, str(e))

    server.shutdown()

    # Certificate lifecycle: the LEAF regenerates (IP change, corruption,
    # renewal) while the CA - the trust anchor - must stay byte-identical,
    # otherwise every device would have to trust a new anchor again.
    work = tempfile.mkdtemp(prefix="opendrop_cert_")
    try:
        c1, k1 = tls_cert.ensure_certificate("10.0.0.7", directory=work)
        stamp = c1.stat().st_mtime_ns
        ca_path = os.path.join(work, tls_cert.CA_CERT_FILE)
        ca_bytes = open(ca_path, "rb").read()
        ca_stamp = os.stat(ca_path).st_mtime_ns
        time.sleep(0.05)
        tls_cert.ensure_certificate("10.0.0.7", directory=work)
        r.check("Certificate reused for same IP", c1.stat().st_mtime_ns == stamp)

        # New IP -> leaf regeneration (DHCP change), same CA.
        tls_cert.ensure_certificate("10.0.0.8", directory=work)
        r.check("Certificate regenerated on IP change", c1.stat().st_mtime_ns != stamp)
        r.check("CA untouched by the IP change",
                open(ca_path, "rb").read() == ca_bytes
                and os.stat(ca_path).st_mtime_ns == ca_stamp)

        # Corrupted certificate -> regeneration, still the same CA.
        c1.write_bytes(b"not a certificate")
        tls_cert.ensure_certificate("10.0.0.8", directory=work)
        cert = x509.load_pem_x509_certificate(c1.read_bytes())
        r.check("Corrupted certificate regenerated", cert is not None)
        ca_now = x509.load_pem_x509_certificate(open(ca_path, "rb").read())
        r.check("Regenerated leaf issued by the unchanged CA",
                cert.issuer == ca_now.subject,
                f"{cert.issuer} / {ca_now.subject}")

        # Corrupted private key -> regeneration (the server must not
        # start with an unreadable key)
        k1.write_bytes(b"not a key")
        tls_cert.ensure_certificate("10.0.0.8", directory=work)
        cert2, key2 = _load_cert_key(work)
        r.check("Corrupted key regenerated",
                k1.read_bytes() != b"not a key"
                and k1.read_bytes().startswith(b"-----BEGIN"), k1.read_bytes()[:20])
        r.check("Regenerated key readable and matches certificate",
                _pub_bytes(key2) == _pub_bytes(cert2.public_key()))

        # Certificate close to expiry -> renewal before the 30 day window
        _write_short_cert(c1, k1, "10.0.0.9", days=10)
        court = x509.load_pem_x509_certificate(c1.read_bytes())
        tls_cert.ensure_certificate("10.0.0.9", directory=work)
        renouvele = x509.load_pem_x509_certificate(c1.read_bytes())
        gain = ((_dates(renouvele)[1] - _dates(court)[1]).days)
        r.check("Certificate renewed before expiry", gain > 300, f"+{gain} days")
        r.check("CA survives the renewal (bytes + mtime)",
                open(ca_path, "rb").read() == ca_bytes
                and os.stat(ca_path).st_mtime_ns == ca_stamp)
        ca_final = x509.load_pem_x509_certificate(open(ca_path, "rb").read())
        renouvele.verify_directly_issued_by(ca_final)
        r.check("Renewed leaf verifies against the same CA", True)

        # Corrupted CA -> regenerated: the ONLY case where the trust
        # anchor changes (devices must then trust the new ca.crt).
        open(ca_path, "wb").write(b"not a ca")
        tls_cert.ensure_certificate("10.0.0.9", directory=work)
        ca_new = x509.load_pem_x509_certificate(open(ca_path, "rb").read())
        leaf_new = x509.load_pem_x509_certificate(c1.read_bytes())
        r.check("Corrupted CA regenerated and leaf re-signed by it",
                ca_new.subject == leaf_new.issuer,
                f"{ca_new.subject} / {leaf_new.issuer}")
    except Exception as e:
        r.check("Certificate lifecycle", False, str(e))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_tls() else 1)
