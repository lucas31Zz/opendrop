"""Audit des routes : qui exige vraiment un token, et comment on repond.

Ce fichier fait office de table de verite du contrat d'acces :
- les routes API sensibles exigent un token (403 sinon)
- les routes volontairement publiques ne laissent fuzzer aucun secret
- les reponses d'erreur ont le bon format (JSON pour l'API) et les
  en-tetes de securite, sans exposer la version de Python
"""
import http.client
import json
import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from opendrop.server.rate_limit import limiter_general, limiter_session
from tests.conftest import (SSL_CONTEXT, TestResult, _start_server, _url,
                            cert_dir, dd, ip, sd)

r = TestResult()

TOKEN_ROUTES_GET = [
    "/api/progress",
    "/api/files",
    "/api/quota",
    "/api/download/test.txt",
    "/qr",
]

ASSETS_PUBLICS = ["/", "/style.css", "/app.js"]


def _request(port, method, path, body=b"", content_type=None):
    conn = http.client.HTTPSConnection(ip, port, context=SSL_CONTEXT, timeout=15)
    try:
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def _get(port, path):
    return _request(port, "GET", path)


def _security_headers_ok(headers):
    return (headers.get("X-Content-Type-Options") == "nosniff"
            and headers.get("X-Frame-Options") == "DENY"
            and "no-store" in headers.get("Cache-Control", ""))


def _token_tests():
    print("--- Routes exigeant un token ---\n")
    server, port, token = _start_server()
    try:
        for path in TOKEN_ROUTES_GET:
            status, _, _ = _get(port, path)
            r.check(f"GET {path} sans token = 403", status == 403, status)

        status, _, _ = _request(port, "POST", "/api/upload", b"{}",
                                "multipart/form-data; boundary=X")
        r.check("POST /api/upload sans token = 403", status == 403, status)

        status, _, _ = _get(port, "/api/files?token=token_invalide")
        r.check("GET /api/files mauvais token = 403", status == 403, status)

        status, _, _ = _get(port, "/api/quota?token=")
        r.check("GET /api/quota token vide = 403", status == 403, status)
    finally:
        server.shutdown()
        server.server_close()


def _info_tests():
    print("--- GET /api/info (route de decouverte) ---\n")
    server, port, token = _start_server()
    try:
        status, headers, body = _get(port, "/api/info")
        data = json.loads(body)
        r.check("GET /api/info sans token = 200 (decouverte desktop)",
                status == 200, status)
        r.check("Sans token: ip et port presents",
                "ip" in data and "port" in data, data)
        r.check("Sans token: aucune information de session",
                "session" not in data, data)
        r.check("Sans token: ni token ni code de session dans la reponse",
                token.encode() not in body
                and server.sessions.code.encode() not in body,
                data)
        r.check("GET /api/info sans token: en-tetes de securite",
                _security_headers_ok(headers), headers.get("Server"))

        status, _, body = _get(port, f"/api/info?token={token}")
        data = json.loads(body)
        r.check("GET /api/info avec token = 200", status == 200, status)
        r.check("Avec token: bloc session present",
                "session" in data and data["session"]["active_sessions"] >= 1,
                data)

        status, _, _ = _get(port, "/api/info?token=token_invalide")
        r.check("GET /api/info mauvais token = 403", status == 403, status)
    finally:
        server.shutdown()
        server.server_close()


def _asset_tests():
    print("--- Assets publics (shell de l'interface web) ---\n")
    server, port, token = _start_server()
    try:
        for asset in ASSETS_PUBLICS:
            status, headers, body = _get(port, asset)
            r.check(f"{asset} servi sans token", status == 200, status)
            r.check(f"{asset}: aucun secret dedans",
                    token.encode() not in body
                    and server.sessions.code.encode() not in body,
                    asset)
            r.check(f"{asset}: en-tetes de securite",
                    _security_headers_ok(headers), headers.get("Server"))
            r.check(f"{asset}: Server sans version Python",
                    "Python" not in headers.get("Server", ""),
                    headers.get("Server"))
    finally:
        server.shutdown()
        server.server_close()


def _error_format_tests():
    print("--- Reponses d'erreur (format + en-tetes) ---\n")
    server, port, token = _start_server()
    try:
        status, headers, body = _get(port, f"/api/route-inconnue?token={token}")
        ct = headers.get("Content-Type", "")
        r.check("Route API inconnue = 404 JSON", status == 404 and "application/json" in ct,
                f"{status} {ct}")
        payload = {}
        if "application/json" in ct and body:
            try:
                payload = json.loads(body)
            except ValueError:
                payload = {}
        r.check("404 JSON: corps au format {error, code}",
                payload.get("code") == 404 and "error" in payload, payload)
        r.check("404 API: en-tetes de securite",
                _security_headers_ok(headers), headers.get("Server"))

        status, headers, body = _get(port, "/page-inconnue")
        ct = headers.get("Content-Type", "")
        r.check("Page inconnue = 404 HTML", status == 404 and "text/html" in ct,
                f"{status} {ct}")
        r.check("404 HTML: en-tetes de securite",
                _security_headers_ok(headers), headers.get("Server"))

        status, headers, _ = _request(port, "POST", "/api/post-inconnu", b"{}",
                                      "application/json")
        ct = headers.get("Content-Type", "")
        r.check("POST route inconnue = 404 JSON",
                status == 404 and "application/json" in ct, f"{status} {ct}")

        status, headers, _ = _request(port, "PUT", "/api/upload", b"{}")
        r.check("Methode inconnue = 501", status == 501, status)
        r.check("501: Server sans version Python",
                "Python" not in headers.get("Server", ""), headers.get("Server"))
        r.check("501: en-tetes de securite",
                _security_headers_ok(headers), headers.get("Server"))
    finally:
        server.shutdown()
        server.server_close()


def _download_tests():
    print("--- Telechargement (en-tete Content-Disposition) ---\n")
    server, port, token = _start_server()
    try:
        ascii_name = "route_ascii.txt"
        with open(os.path.join(sd, ascii_name), "wb") as fh:
            fh.write(b"ascii")
        status, headers, body = _get(
            port, "/api/download/" + quote(ascii_name) + f"?token={token}")
        r.check("Telechargement d'un nom ASCII", status == 200 and body == b"ascii",
                f"{status} {body[:40]}")

        # Nom hors latin-1 : l'ancien encodage d'en-tete plantait ici.
        unicode_name = "fichier_测试.txt"
        with open(os.path.join(sd, unicode_name), "wb") as fh:
            fh.write(b"unicode")
        try:
            status, headers, body = _get(
                port, "/api/download/" + quote(unicode_name) + f"?token={token}")
            disposition = headers.get("Content-Disposition", "")
            r.check("Telechargement d'un nom non-ASCII", status == 200 and body == b"unicode",
                    f"{status} {body[:60]}")
            r.check("Content-Disposition encode en UTF-8 (filename*)",
                    "filename*=UTF-8''" in disposition, disposition)
        finally:
            os.remove(os.path.join(sd, unicode_name))
        os.remove(os.path.join(sd, ascii_name))

        status, _, _ = _get(port, "/api/download/inexistant.txt?token=" + token)
        r.check("Telechargement fichier absent = 404 JSON",
                status == 404, status)
    finally:
        server.shutdown()
        server.server_close()


def _rate_limit_tests():
    print("--- Routes publiques rate-limitees ---\n")
    server, port, token = _start_server()
    try:
        # /qr rend un PNG et porte le token : il doit passer par le rate
        # limiting general comme le reste de l'API.
        limiter_general.reset()
        limited = False
        for i in range(125):
            status, _, _ = _get(port, f"/qr?token={token}")
            if status == 429:
                limited = True
                r.check("GET /qr rate-limite (429)", True, f"requete #{i+1}")
                break
        if not limited:
            r.check("GET /qr rate-limite (429)", False, "aucun 429 en 125 requetes")
        limiter_general.reset()

        # POST /api/session/unlock est public par nature (auth par code) :
        # le force brute doit etre borne (5/min/IP).
        limiter_session.reset()
        codes_403 = 0
        got_429 = False
        for _ in range(6):
            status, _, _ = _request(port, "POST", "/api/session/unlock?code=AAAAAA")
            if status == 429:
                got_429 = True
            elif status == 403:
                codes_403 += 1
        r.check("POST /api/session/unlock: 403 sur code faux", codes_403 >= 5, codes_403)
        r.check("POST /api/session/unlock: force brute bornee (429)", got_429, got_429)
        limiter_session.reset()
        limiter_general.reset()
    finally:
        server.shutdown()
        server.server_close()


def test_routes():
    print("--- Routes / audit d'acces ---\n")
    _token_tests()
    _info_tests()
    _asset_tests()
    _error_format_tests()
    _download_tests()
    _rate_limit_tests()
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_routes() else 1)
