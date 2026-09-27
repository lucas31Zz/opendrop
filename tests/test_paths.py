"""Audit 3/3 : aucun chemin absolu du serveur ne doit sortir en reponse HTTP.

Le serveur connait le dossier de reception, le dossier de partage et la
racine du depot. Rien de tout cela ne doit figurer dans une reponse metier,
une erreur ou un asset de l'interface web : ni nom de fichier absolu, ni
chemin Windows/Unix, ni dossier utilisateur.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.conftest import (TestResult, urlopen, _start_server, _upload,
                            _raw_upload, ip)

LEAK_PATTERNS = [
    (re.compile(r"[A-Za-z]:[\\/]"), "chemin Windows avec lettre de lecteur"),
    (re.compile(r"\\\\\S+\\\\"), "chemin UNC"),
    (re.compile(r"/(?:Users|home|tmp|var|etc|opt|proc|mnt)/"), "chemin racine Unix"),
    (re.compile(r"(?:AppData|OneDrive|site-packages|opendrop_tests)", re.I),
     "dossier local"),
]


def _find_leak(text):
    for pattern, label in LEAK_PATTERNS:
        m = pattern.search(text)
        if m:
            return f"{label} -> {m.group(0)!r}"
    return None


def _collect(status, headers, body):
    """Assemble tout ce qui part vers le client : corps + valeurs d'en-tetes."""
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", "replace")
    blob = body or ""
    for key, value in headers.items():
        if key.lower() in ("date", "content-length"):
            continue
        blob += f"\n{key}: {value}"
    return blob


def _request(port, path, token=None, method="GET", data=None, headers=None):
    url = f"https://{ip}:{port}{path}"
    if token is not None:
        url += f"?token={token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        resp = urlopen(req)
        body = resp.read().decode("utf-8", "replace")
        return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, dict(e.headers), body


def _check_clean(r, label, status, headers, body, expect_status=None):
    blob = _collect(status, headers, body)
    leak = _find_leak(blob)
    r.check(f"{label}: aucun chemin absolu", leak is None, leak)
    if expect_status is not None:
        r.check(f"{label}: status {expect_status}", status == expect_status,
                f"status={status} body={body[:120]!r}")


def _upload_response_tests(r, port, token):
    print("\n  Reponse d'upload...")
    resp = _upload(port, token, filename="chemins.txt", content=b"path leak test")
    body = resp.read().decode("utf-8", "replace")
    headers = dict(resp.headers)
    data = {}
    try:
        data = json.loads(body)
    except ValueError:
        pass
    r.check("Upload: reponse JSON", data.get("success") is True, body[:200])
    r.check("Upload: pas de cle 'path' (chemin serveur)",
            "path" not in data, f"cles={sorted(data)}")
    _check_clean(r, "Upload", resp.status, headers, body)


def _json_route_tests(r, port, token):
    print("\n  Routes metier...")
    for label, path, tok, expect in [
        ("Info (sans token)", "/api/info", None, 200),
        ("Info (avec token)", "/api/info", token, 200),
        ("Files", "/api/files", token, 200),
        ("Progress", "/api/progress", token, 200),
        ("Quota", "/api/quota", token, 200),
    ]:
        status, headers, body = _request(port, path, tok)
        _check_clean(r, label, status, headers, body, expect)

    # Le QR est une image : on ne scanne que le status (binaire bruité).
    status, headers, body = _request(port, "/qr", token)
    r.check("QR: 200", status == 200, f"status={status}")

    status, headers, body = _request(port, "/api/files", token)
    try:
        files = json.loads(body).get("files", [])
    except ValueError:
        files = []
    if files:
        cles = sorted(files[0].keys())
        r.check("Files: uniquement nom + taille",
                cles == ["name", "size"], cles)
    else:
        r.check("Files: fichier de test present", False, body)


def _asset_tests(r, port):
    print("\n  Assets de l'interface web...")
    for path in ("/", "/style.css", "/app.js"):
        status, headers, body = _request(port, path)
        _check_clean(r, f"Asset {path}", status, headers, body, 200)


def _error_tests(r, port, token):
    print("\n  Reponses d'erreur...")

    status, headers, body = _request(port, "/api/files", "mauvais_token")
    _check_clean(r, "403 token invalide", status, headers, body, 403)

    status, headers, body = _request(port, "/api/inconnue", token)
    _check_clean(r, "404 route API", status, headers, body, 404)

    status, headers, body = _request(port, "/page-inconnue")
    _check_clean(r, "404 page HTML", status, headers, body, 404)

    status, headers, body = _request(
        port, "/api/download/INEXISTANT.txt", token)
    _check_clean(r, "404 download", status, headers, body, 404)

    # Corps multipart corrompu -> erreur 400 de parsing
    junk = b"pas-un-multipart"
    status, headers, body = _request(
        port, "/api/upload", token, method="POST", data=junk,
        headers={"Content-Type": "multipart/form-data; boundary=zz",
                 "Content-Length": str(len(junk))})
    _check_clean(r, "400 multipart invalide", status, headers, body, 400)

    # Nom de fichier traversant : assaini (pas de 400) et surtout aucun
    # chemin serveur ne doit partir dans la reponse
    evil = (b"--zz\r\nContent-Disposition: form-data; name=\"file\"; "
            b"filename=\"../etc/passwd\"\r\n\r\nx\r\n--zz--\r\n")
    status, headers, body = _request(
        port, "/api/upload", token, method="POST", data=evil,
        headers={"Content-Type": "multipart/form-data; boundary=zz",
                 "Content-Length": str(len(evil))})
    _check_clean(r, "Upload traversant", status, headers, body, 200)
    try:
        nom = json.loads(body).get("filename")
    except ValueError:
        nom = None
    r.check("Upload traversant: nom reduit au fichier seul",
            nom == "passwd", f"filename={nom!r}")

    # Upload sans token -> 403
    status, headers, body = _request(
        port, "/api/upload", None, method="POST", data=b"x",
        headers={"Content-Length": "1"})
    _check_clean(r, "403 upload sans token", status, headers, body, 403)

    # Fichier au-dela de la limite -> 400, corps borne a l'en-tete
    status, body = _raw_upload(port, token, 11 * 1024 ** 3)
    _check_clean(r, "400 fichier trop volumineux", status, {}, body, 400)


def _download_header_tests(r, port, token):
    print("\n  En-tete de telechargement...")
    status, headers, body = _request(port, "/api/download/test.txt", token)
    if status != 200:
        r.check("Download: 200", False, f"status={status} {body[:120]!r}")
        return
    disposition = headers.get("Content-Disposition", "")
    r.check("Download: Content-Disposition sans chemin",
            _find_leak(disposition) is None, disposition)
    r.check("Download: disposition = attachment",
            disposition.startswith("attachment"), disposition)


def _progress_after_error_tests(r, port, token):
    print("\n  Progress apres erreur...")
    # Un upload qui echoue ne doit pas laisser de chemin reel dans l'etat
    payload = (b"--zz\r\nContent-Disposition: form-data; name=\"file\"; "
               b"filename=\"x.txt\"\r\n\r\nx\r\n--zz--\r\n")
    _request(port, "/api/upload", token, method="POST", data=payload,
             headers={"Content-Type": "multipart/form-data; boundary=zz",
                      "Content-Length": str(len(payload))})
    status, headers, body = _request(port, "/api/progress", token)
    _check_clean(r, "Progress (apres erreur)", status, headers, body, 200)
    try:
        state = json.loads(body)
    except ValueError:
        state = {}
    r.check("Progress: pas de cle 'path'/'dir'",
            "path" not in state and "dir" not in state, sorted(state))


def test_paths():
    r = TestResult()
    print("\n=== Audit 3/3 : chemins absolus ===")
    print("\n  Demarrage du serveur...")
    server, port, token = _start_server()
    try:
        _upload_response_tests(r, port, token)
        _json_route_tests(r, port, token)
        _asset_tests(r, port)
        _error_tests(r, port, token)
        _download_header_tests(r, port, token)
        _progress_after_error_tests(r, port, token)
    finally:
        server.shutdown()
        server.server_close()
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_paths() else 1)
