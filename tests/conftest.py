import atexit
import http.client
import os
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from opendrop.network.interfaces import get_local_ip, find_available_port
from opendrop.server.server import create_server

# --- Isolation des tests -------------------------------------------------
# Les tests travaillent TOUJOURS dans un dossier temporaire cree ici.
# Le fichier de config de l'utilisateur n'est meme pas ouvert : ni le
# dossier de reception, ni le dossier de partage reels ne sont lus,
# ecrits ou supprimes par les tests.
_WORKSPACE = tempfile.mkdtemp(prefix="opendrop_tests_")

ip = "127.0.0.1"
dd = os.path.join(_WORKSPACE, "recus")
sd = os.path.join(_WORKSPACE, "partage")
cert_dir = os.path.join(_WORKSPACE, "certs")
os.makedirs(dd, exist_ok=True)
os.makedirs(sd, exist_ok=True)

# Le serveur parle HTTPS avec un certificat auto-signe : les tests ne
# verifient pas la chaine de confiance (elle est generee a la volee dans
# le workspace temporaire).
SSL_CONTEXT = ssl._create_unverified_context()


def urlopen(url, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, **kwargs):
    kwargs.setdefault("context", SSL_CONTEXT)
    return urllib.request.urlopen(url, data, timeout, **kwargs)

_share_file = os.path.join(sd, "test.txt")
_FIXTURE_CONTENT = b"test content share"
with open(_share_file, "wb") as _f:
    _f.write(_FIXTURE_CONTENT)


def _cleanup_workspace():
    """Supprime tout le dossier temporaire des tests a la fin du processus."""
    shutil.rmtree(_WORKSPACE, ignore_errors=True)


atexit.register(_cleanup_workspace)


def _start_server(session_expires_in=3600, session_code=None, **kwargs):
    port = find_available_port(10000 + int(time.time() * 1000) % 10000)
    token = "testtoken_" + str(port)
    server = create_server(ip, port, token, dd, sd,
                           session_expires_in=session_expires_in,
                           session_code=session_code,
                           tls_cert_dir=cert_dir,
                           **kwargs)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)
    return server, port, token


def _url(port, path, token="testtoken"):
    return f"https://{ip}:{port}{path}?token={token}"


def _upload(port, token, filename="upload.txt", content=b"upload data"):
    boundary = "----TEST"
    body = (
        b"--" + boundary.encode() + b"\r\n"
        b'Content-Disposition: form-data; name="file"; filename="' + filename.encode() + b'"\r\n'
        b"Content-Type: text/plain\r\n\r\n"
        + content
        + b"\r\n--" + boundary.encode() + b"--\r\n"
    )
    req = urllib.request.Request(
        _url(port, "/api/upload", token),
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    return urlopen(req)


def _raw_upload(port, token, content_length):
    """POST /api/upload avec un Content-Length annonce, sans envoyer de corps.

    Le serveur doit trancher sur l'en-tete seul (taille, quota) avant de
    lire quoi que ce soit : aucun octet n'est alors ecrit, et le client ne
    peut pas se faire couper en pleine ecriture.
    """
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=SSL_CONTEXT, timeout=20)
    try:
        conn.putrequest("POST", f"/api/upload?token={token}")
        conn.putheader("Content-Type", "multipart/form-data; boundary=----TEST")
        conn.putheader("Content-Length", str(content_length))
        conn.endheaders()
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def check(self, name, cond, detail=""):
        if cond:
            self.passed += 1
            print(f"  OK  {name}")
        else:
            self.failed += 1
            self.errors.append(f"{name}: {detail}")
            print(f"  FAIL {name}: {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{self.passed}/{total} passed, {self.failed} failed")
        return self.failed == 0
