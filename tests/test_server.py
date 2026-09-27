"""Tests for upload, download, file listing, and QR code."""
import json
import os
import socket
import sys
import urllib.request
import urllib.error

from opendrop.server.server import PortInUseError, create_server
from tests.conftest import (_start_server, _url, _upload, TestResult, cert_dir,
                            dd, ip, sd, urlopen)

r = TestResult()


def test_server():
    server, port, token = _start_server()

    print("--- Server tests ---\n")

    # Static pages
    for path in ["/", "/style.css", "/app.js"]:
        try:
            resp = urlopen(f"https://127.0.0.1:{port}{path}")
            r.check(f"GET {path}", resp.status == 200)
        except Exception as e:
            r.check(f"GET {path}", False, str(e))

    # Upload
    try:
        resp = _upload(port, token, "server_test.txt", b"hello world")
        data = json.loads(resp.read())
        r.check("Upload", data.get("success") and data.get("size") == 11, data)
    except Exception as e:
        r.check("Upload", False, str(e))

    # List files
    try:
        resp = urlopen(_url(port, "/api/files", token))
        data = json.loads(resp.read())
        r.check("List files", "files" in data, data)
    except Exception as e:
        r.check("List files", False, str(e))

    # Download
    try:
        resp = urlopen(_url(port, "/api/download/test.txt", token))
        r.check("Download", resp.read() == b"test content share")
    except Exception as e:
        r.check("Download", False, str(e))

    # Info
    try:
        resp = urlopen(_url(port, "/api/info", token))
        data = json.loads(resp.read())
        r.check("Info", "ip" in data and "session" in data, data)
    except Exception as e:
        r.check("Info", False, str(e))

    # QR code
    try:
        resp = urlopen(_url(port, "/qr", token))
        r.check("QR code", resp.status == 200 and resp.headers.get("Content-Type") == "image/png")
    except Exception as e:
        r.check("QR code", False, str(e))

    # SHA-256 in upload response
    try:
        resp = _upload(port, token, "sha_test.txt", b"hash me")
        data = json.loads(resp.read())
        r.check("SHA-256 hash returned", "sha256" in data and len(data["sha256"]) == 64, data)
    except Exception as e:
        r.check("SHA-256 hash returned", False, str(e))

    # Double bind : un second serveur sur le meme port est refuse, et le
    # serveur deja en place est bien identifie comme OpenDrop.
    try:
        create_server(ip, port, "token_doublon", dd, sd, tls_cert_dir=cert_dir)
        r.check("Second serveur sur meme port refuse", False, "aucune exception")
    except PortInUseError as e:
        r.check("Second serveur sur meme port refuse", "OpenDrop" in str(e), str(e))
    except Exception as e:
        r.check("Second serveur sur meme port refuse", False, str(e))

    # Un port tenu par un autre programme est aussi refuse (handshake TLS
    # qui echoue : ce n'est pas un serveur OpenDrop).
    busy = socket.socket()
    busy.bind(("0.0.0.0", 0))
    busy_port = busy.getsockname()[1]
    busy.listen(5)
    try:
        create_server(ip, busy_port, "token_etranger", dd, sd, tls_cert_dir=cert_dir)
        r.check("Port occupe par autre programme refuse", False, "aucune exception")
    except PortInUseError as e:
        r.check("Port occupe par autre programme refuse", "autre programme" in str(e), str(e))
    except Exception as e:
        r.check("Port occupe par autre programme refuse", False, str(e))
    finally:
        busy.close()

    server.shutdown()

    # Cleanup : noms exacts ecrits par ce test (ne jamais vider le dossier,
    # il peut contenir les fichiers de l'utilisateur)
    for f in ("server_test.txt", "sha_test.txt"):
        try:
            os.remove(os.path.join(dd, f))
        except OSError:
            pass

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_server() else 1)
