"""Route audit: who really requires a token, and how we answer.

This file is the source of truth for the access contract:
- sensitive API routes require a token (403 otherwise)
- intentionally public routes let a fuzzer find no secret
- error responses have the right format (JSON for the API) and the
  security headers, without exposing the Python version
"""
import http.client
import json
import os
import sys
import time
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _unlink(path):
    # The server thread may still hold the handle for a moment on Windows.
    for _ in range(20):
        try:
            os.remove(path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.remove(path)

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
    print("--- Routes requiring a token ---\n")
    server, port, token = _start_server()
    try:
        for path in TOKEN_ROUTES_GET:
            status, _, _ = _get(port, path)
            r.check(f"GET {path} without token = 403", status == 403, status)

        status, _, _ = _request(port, "POST", "/api/upload", b"{}",
                                "multipart/form-data; boundary=X")
        r.check("POST /api/upload without token = 403", status == 403, status)

        status, _, _ = _get(port, "/api/files?token=token_invalide")
        r.check("GET /api/files bad token = 403", status == 403, status)

        status, _, _ = _get(port, "/api/quota?token=")
        r.check("GET /api/quota empty token = 403", status == 403, status)
    finally:
        server.shutdown()
        server.server_close()


def _info_tests():
    print("--- GET /api/info (discovery route) ---\n")
    server, port, token = _start_server()
    try:
        status, headers, body = _get(port, "/api/info")
        data = json.loads(body)
        r.check("GET /api/info without token = 200 (desktop discovery)",
                status == 200, status)
        r.check("Without token: ip and port present",
                "ip" in data and "port" in data, data)
        r.check("Without token: no session information",
                "session" not in data, data)
        r.check("Without token: neither token nor session code in the response",
                token.encode() not in body
                and server.sessions.code.encode() not in body,
                data)
        r.check("GET /api/info without token: security headers",
                _security_headers_ok(headers), headers.get("Server"))

        status, _, body = _get(port, f"/api/info?token={token}")
        data = json.loads(body)
        r.check("GET /api/info with token = 200", status == 200, status)
        r.check("With token: session block present",
                "session" in data and data["session"]["active_sessions"] >= 1,
                data)

        status, _, _ = _get(port, "/api/info?token=token_invalide")
        r.check("GET /api/info bad token = 403", status == 403, status)
    finally:
        server.shutdown()
        server.server_close()


def _asset_tests():
    print("--- Public assets (web UI shell) ---\n")
    server, port, token = _start_server()
    try:
        for asset in ASSETS_PUBLICS:
            status, headers, body = _get(port, asset)
            r.check(f"{asset} served without token", status == 200, status)
            r.check(f"{asset}: no secret inside",
                    token.encode() not in body
                    and server.sessions.code.encode() not in body,
                    asset)
            r.check(f"{asset}: security headers",
                    _security_headers_ok(headers), headers.get("Server"))
            r.check(f"{asset}: Server without Python version",
                    "Python" not in headers.get("Server", ""),
                    headers.get("Server"))
    finally:
        server.shutdown()
        server.server_close()


def _error_format_tests():
    print("--- Error responses (format + headers) ---\n")
    server, port, token = _start_server()
    try:
        status, headers, body = _get(port, f"/api/route-inconnue?token={token}")
        ct = headers.get("Content-Type", "")
        r.check("Unknown API route = 404 JSON", status == 404 and "application/json" in ct,
                f"{status} {ct}")
        payload = {}
        if "application/json" in ct and body:
            try:
                payload = json.loads(body)
            except ValueError:
                payload = {}
        r.check("404 JSON: body in {error, code} format",
                payload.get("code") == 404 and "error" in payload, payload)
        r.check("404 API: security headers",
                _security_headers_ok(headers), headers.get("Server"))

        status, headers, body = _get(port, "/page-inconnue")
        ct = headers.get("Content-Type", "")
        r.check("Unknown page = 404 HTML", status == 404 and "text/html" in ct,
                f"{status} {ct}")
        r.check("404 HTML: security headers",
                _security_headers_ok(headers), headers.get("Server"))

        status, headers, _ = _request(port, "POST", "/api/post-inconnu", b"{}",
                                      "application/json")
        ct = headers.get("Content-Type", "")
        r.check("POST unknown route = 404 JSON",
                status == 404 and "application/json" in ct, f"{status} {ct}")

        status, headers, _ = _request(port, "PUT", "/api/upload", b"{}")
        r.check("Unknown method = 501", status == 501, status)
        r.check("501: Server without Python version",
                "Python" not in headers.get("Server", ""), headers.get("Server"))
        r.check("501: security headers",
                _security_headers_ok(headers), headers.get("Server"))
    finally:
        server.shutdown()
        server.server_close()


def _download_tests():
    print("--- Download (Content-Disposition header) ---\n")
    server, port, token = _start_server()
    try:
        ascii_name = "route_ascii.txt"
        with open(os.path.join(sd, ascii_name), "wb") as fh:
            fh.write(b"ascii")
        status, headers, body = _get(
            port, "/api/download/" + quote(ascii_name) + f"?token={token}")
        r.check("Download of an ASCII name", status == 200 and body == b"ascii",
                f"{status} {body[:40]}")

        # Name outside latin-1: the old header encoding crashed here.
        unicode_name = "fichier_测试.txt"
        with open(os.path.join(sd, unicode_name), "wb") as fh:
            fh.write(b"unicode")
        try:
            status, headers, body = _get(
                port, "/api/download/" + quote(unicode_name) + f"?token={token}")
            disposition = headers.get("Content-Disposition", "")
            r.check("Download of a non-ASCII name", status == 200 and body == b"unicode",
                    f"{status} {body[:60]}")
            r.check("Content-Disposition encoded in UTF-8 (filename*)",
                    "filename*=UTF-8''" in disposition, disposition)
        finally:
            _unlink(os.path.join(sd, unicode_name))
        _unlink(os.path.join(sd, ascii_name))

        status, _, _ = _get(port, "/api/download/inexistant.txt?token=" + token)
        r.check("Download of missing file = 404 JSON",
                status == 404, status)
    finally:
        server.shutdown()
        server.server_close()


def _rate_limit_tests():
    print("--- Rate-limited public routes ---\n")
    server, port, token = _start_server()
    try:
        # /qr returns a PNG and carries the token: it must go through the
        # general rate limiting like the rest of the API.
        limiter_general.reset()
        limited = False
        for i in range(125):
            status, _, _ = _get(port, f"/qr?token={token}")
            if status == 429:
                limited = True
                r.check("GET /qr rate-limited (429)", True, f"request #{i+1}")
                break
        if not limited:
            r.check("GET /qr rate-limited (429)", False, "no 429 in 125 requests")
        limiter_general.reset()

        # POST /api/session/unlock is public by nature (code auth):
        # brute force must be capped (5/min/IP).
        limiter_session.reset()
        codes_403 = 0
        got_429 = False
        for _ in range(6):
            status, _, _ = _request(port, "POST", "/api/session/unlock?code=AAAAAA")
            if status == 429:
                got_429 = True
            elif status == 403:
                codes_403 += 1
        r.check("POST /api/session/unlock: 403 on wrong code", codes_403 >= 5, codes_403)
        r.check("POST /api/session/unlock: brute force capped (429)", got_429, got_429)
        limiter_session.reset()
        limiter_general.reset()
    finally:
        server.shutdown()
        server.server_close()


def test_routes():
    print("--- Routes / access audit ---\n")
    _token_tests()
    _info_tests()
    _asset_tests()
    _error_format_tests()
    _download_tests()
    _rate_limit_tests()
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_routes() else 1)
