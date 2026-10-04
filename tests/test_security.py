"""Tests for security: tokens, path traversal, rate limiting, CORS."""
import contextlib
import http.client
import io
import json
import os
import shutil
import sys
import time
import urllib.request
import urllib.error
import threading

from opendrop.network.interfaces import find_available_port
from opendrop.server import multipart as multipart_mod
from opendrop.server import server as server_module
from opendrop.server.rate_limit import limiter_upload
from opendrop.server.server import create_server
from tests.conftest import (SSL_CONTEXT, _raw_upload, _start_server, _url, _upload,
                            TestResult, cert_dir, dd, ip, sd, urlopen)

r = TestResult()


def test_security():
    server, port, token = _start_server()

    print("--- Security tests ---\n")

    # Invalid token
    try:
        urlopen(_url(port, "/api/files", "badtoken"))
        r.check("Invalid token rejected", False, "should be 403")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        r.check("Invalid token rejected", e.code == 403 and body.get("error") == "Invalid session token", f"{e.code} {body}")

    # Missing token
    try:
        urlopen(f"https://127.0.0.1:{port}/api/files")
        r.check("Missing token rejected", False, "should be 403")
    except urllib.error.HTTPError as e:
        r.check("Missing token rejected", e.code == 403)

    # Path traversal download
    try:
        urlopen(_url(port, "/api/download/..%2F..%2Fetc%2Fpasswd", token))
        r.check("Path traversal blocked", False, "should be 400")
    except urllib.error.HTTPError as e:
        r.check("Path traversal blocked", e.code == 400)

    # Path traversal with encoded slash
    try:
        urlopen(_url(port, "/api/download/..%2Fetc%2Fshadow", token))
        r.check("Encoded path traversal blocked", False, "should be 400")
    except urllib.error.HTTPError as e:
        r.check("Encoded path traversal blocked", e.code == 400)

    # File not found
    try:
        urlopen(_url(port, "/api/download/nonexistent.txt", token))
        r.check("File not found", False, "should be 404")
    except urllib.error.HTTPError as e:
        r.check("File not found", e.code == 404)

    # Bad upload content type
    try:
        req = urllib.request.Request(
            _url(port, "/api/upload", token),
            data=b"not multipart",
            headers={"Content-Type": "text/plain", "Content-Length": "13"},
            method="POST",
        )
        urlopen(req)
        r.check("Bad upload content type", False, "should be 400")
    except urllib.error.HTTPError as e:
        r.check("Bad upload content type", e.code == 400)

    # Valid upload
    try:
        resp = _upload(port, token, "sec.txt", b"secure")
        data = json.loads(resp.read())
        r.check("Valid upload", data.get("success"), data)
    except Exception as e:
        r.check("Valid upload", False, str(e))

    # Valid download
    try:
        resp = urlopen(_url(port, "/api/download/test.txt", token))
        r.check("Valid download", resp.read() == b"test content share")
    except Exception as e:
        r.check("Valid download", False, str(e))

    # Info endpoint
    try:
        resp = urlopen(f"https://127.0.0.1:{port}/api/info")
        r.check("Info endpoint", resp.status == 200)
    except Exception as e:
        r.check("Info endpoint", False, str(e))

    # Security headers
    try:
        resp = urlopen(f"https://127.0.0.1:{port}/api/info")
        r.check("X-Content-Type-Options", resp.headers.get("X-Content-Type-Options") == "nosniff")
        r.check("X-Frame-Options", resp.headers.get("X-Frame-Options") == "DENY")
        r.check("Cache-Control", "no-store" in resp.headers.get("Cache-Control", ""))
    except Exception as e:
        r.check("Security headers", False, str(e))

    # Static assets served without token (bootstrap of the web UI)
    for asset in ("/", "/style.css", "/app.js"):
        try:
            resp = urlopen(f"https://127.0.0.1:{port}{asset}")
            r.check(f"Asset {asset} without token", resp.status == 200)
        except Exception as e:
            r.check(f"Asset {asset} without token", False, str(e))

    # Contract consumed by web/app.js: 403 must be a JSON body, not an empty list
    try:
        urlopen(f"https://127.0.0.1:{port}/api/files")
        r.check("Missing token JSON body", False, "should be 403")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        r.check("Missing token JSON body",
                e.code == 403 and body == {"error": "Missing session token", "code": 403},
                f"{e.code} {body}")

    # Cross-origin POST rejected with 403 JSON (previously: TypeError, no response)
    try:
        req = urllib.request.Request(
            _url(port, "/api/upload", token),
            data=b"not multipart",
            headers={
                "Content-Type": "text/plain",
                "Content-Length": "13",
                "Origin": "http://evil.example",
            },
            method="POST",
        )
        urlopen(req)
        r.check("Foreign origin rejected", False, "should be 403")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        r.check("Foreign origin rejected",
                e.code == 403 and body.get("error") == "Origin not allowed",
                f"{e.code} {body}")
    except Exception as e:
        r.check("Foreign origin rejected", False, str(e))

    # Same-origin POST must still pass the origin check (400 = content rejected later)
    try:
        req = urllib.request.Request(
            _url(port, "/api/upload", token),
            data=b"not multipart",
            headers={
                "Content-Type": "text/plain",
                "Content-Length": "13",
                "Origin": f"https://127.0.0.1:{port}",
            },
            method="POST",
        )
        urlopen(req)
        r.check("Same origin accepted", False, "should be 400")
    except urllib.error.HTTPError as e:
        r.check("Same origin accepted", e.code == 400, f"{e.code}")
    except Exception as e:
        r.check("Same origin accepted", False, str(e))

    # Right host, wrong scheme: the server only speaks HTTPS
    try:
        req = urllib.request.Request(
            _url(port, "/api/upload", token),
            data=b"not multipart",
            headers={
                "Content-Type": "text/plain",
                "Content-Length": "13",
                "Origin": f"http://127.0.0.1:{port}",
            },
            method="POST",
        )
        urlopen(req)
        r.check("HTTP origin rejected", False, "should be 403")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        r.check("HTTP origin rejected",
                e.code == 403 and body.get("error") == "Origin not allowed",
                f"{e.code} {body}")
    except Exception as e:
        r.check("HTTP origin rejected", False, str(e))

    # --- Upload size: per-file limit, no global quota -----
    limiter_upload.reset()

    limit = server_module.MAX_UPLOAD_SIZE
    try:
        status, body = _raw_upload(port, token, limit + 1)
        data = json.loads(body)
        r.check("Upload > 10 GB rejected on header",
                status == 400 and "too large" in data.get("error", ""),
                f"{status} {data}")
    except Exception as e:
        r.check("Upload > 10 GB rejected on header", False, str(e))

    # The real limit is indeed the server's (checked with a reduced
    # value: 5000 > 4096 must be rejected).
    old_limit = server_module.MAX_UPLOAD_SIZE
    server_module.MAX_UPLOAD_SIZE = 4096
    try:
        status, body = _raw_upload(port, token, 5000)
        data = json.loads(body)
        r.check("Configured size limit enforced",
                status == 400 and "too large" in data.get("error", ""),
                f"{status} {data}")

        # Two 3000-byte files pass while 6000 > 4096: the limit is
        # indeed per file and no global quota is applied.
        try:
            a = json.loads(_upload(port, token, "quota_a.bin", b"A" * 3000).read())
            b = json.loads(_upload(port, token, "quota_b.bin", b"B" * 3000).read())
            r.check("Limit is per file, no global quota",
                    bool(a.get("success")) and bool(b.get("success")), f"{a} {b}")
        except Exception as e:
            r.check("Limit is per file, no global quota", False, str(e))
    finally:
        server_module.MAX_UPLOAD_SIZE = old_limit

    # --- Incomplete body: rejected, no file, no hash ----------------------
    # HTTP case: the body stops before the final boundary.
    # Unit case: the reader hits EOF midway (connection cut during the
    # transfer). In both cases the server must return no SHA-256: a hash
    # over an incomplete file would lie.
    limiter_upload.reset()
    boundary = "----TRUNC"
    head = (f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="tronque.bin"\r\n'
            "Content-Type: text/plain\r\n\r\n").encode()
    truncated_body = head + b"X" * 4096
    try:
        conn = http.client.HTTPSConnection(ip, port, context=SSL_CONTEXT, timeout=20)
        conn.request("POST", f"/api/upload?token={token}", body=truncated_body,
                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                              "Content-Length": str(len(truncated_body))})
        resp = conn.getresponse()
        text = resp.read().decode("utf-8", "replace")
        conn.close()
        r.check("Body without final boundary rejected (400)", resp.status == 400,
                f"{resp.status} {text}")
        r.check("Incomplete body: no SHA-256 returned", "sha256" not in text,
                text[:200])
        leftovers = [f for f in os.listdir(dd) if f.startswith("tronque")]
        r.check("Incomplete body: no partial file", not leftovers, leftovers)
    except Exception as e:
        r.check("Body without final boundary rejected (400)", False, str(e))

    # Unit case: cut in the middle of the body (reader EOF)
    cut_dir = os.path.join(dd, "coupure")
    shutil.rmtree(cut_dir, ignore_errors=True)
    os.makedirs(cut_dir, exist_ok=True)
    full_body = (head + b"Y" * 2048 + b"\r\n--" + boundary.encode() + b"--\r\n")
    try:
        reader = io.BytesIO(full_body[:len(head) + 512])
        name, error, digest = multipart_mod.parse_multipart_upload(
            reader, f"multipart/form-data; boundary={boundary}",
            len(full_body), cut_dir)
        r.check("Reader cut mid-stream: error returned",
                name is None and bool(error), (name, error))
        r.check("Reader cut mid-stream: no hash returned",
                digest is None, digest)
        r.check("Reader cut mid-stream: no file",
                os.listdir(cut_dir) == [], os.listdir(cut_dir))
    except Exception as e:
        r.check("Reader cut mid-stream", False, repr(e))

    # --- Final flush failure: 507, file cleaned up, no hash ---------------
    # Simulates a full disk on the very last block: closing fails even
    # though the whole body was read. Without handling, the server would
    # answer 200 with a hash covering a file truncated on disk.
    real_open = open

    class _FlakyFile:
        def __init__(self, fh):
            self._fh = fh

        def write(self, data):
            return self._fh.write(data)

        def flush(self):
            return self._fh.flush()

        def close(self):
            try:
                self._fh.close()
            finally:
                raise OSError(28, "No space left on device")

    def _patched_open(path, mode="r", *args, **kwargs):
        if mode == "xb":
            return _FlakyFile(real_open(path, mode, *args, **kwargs))
        return real_open(path, mode, *args, **kwargs)

    multipart_mod.open = _patched_open
    limiter_upload.reset()
    try:
        try:
            _upload(port, token, "flush_fail.bin", b"Z" * 2048)
            r.check("Final flush failure -> 507", False, "upload accepted")
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            r.check("Final flush failure -> 507", e.code == 507, f"{e.code} {text}")
            r.check("Final flush failure: no server path in the response",
                    "flush_fail" not in text and ".bin" not in text, text)
            leftovers = [f for f in os.listdir(dd) if f.startswith("flush_fail")]
            r.check("Final flush failure: partial file deleted",
                    not leftovers, leftovers)
        except Exception as e:
            r.check("Final flush failure -> 507", False, str(e))
    finally:
        del multipart_mod.open

    # --- Server logs contain neither token nor code ----------
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            urlopen(_url(port, "/qr", token))
        except Exception:
            pass
        try:
            req = urllib.request.Request(
                f"https://127.0.0.1:{port}/api/session/unlock?code=ZZZZZZ",
                data=b"", method="POST", headers={"Content-Length": "0"})
            urlopen(req)
        except Exception:
            pass
        time.sleep(0.3)
    journaux = buf.getvalue()
    r.check("Logs without token", token not in journaux, journaux[:300])
    r.check("Logs without session code", "ZZZZZZ" not in journaux,
            journaux[:300])
    r.check("Logs: token and code masked",
            "token=***" in journaux and "code=***" in journaux, journaux[:300])

    # Write impossible (invalid receive folder): 507 response and no
    # partial file left behind. This is what happens when the disk is full.
    blocker = os.path.join(os.path.dirname(dd), "dossier_bloque.txt")
    with open(blocker, "w", encoding="utf-8") as fh:
        fh.write("ce fichier occupe la place d'un dossier")
    token_disk = "testtoken_disk_" + str(int(time.time() * 1000) % 100000)
    port_disk = find_available_port(10000 + int(time.time() * 1000) % 10000)
    server_disk = create_server(ip, port_disk, token_disk, blocker, sd,
                                tls_cert_dir=cert_dir)
    threading.Thread(target=server_disk.serve_forever, daemon=True).start()
    time.sleep(0.5)
    try:
        _upload(port_disk, token_disk, "disk.txt", b"data")
        r.check("Disk write error -> 507", False, "should be 507")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        r.check("Disk write error -> 507", e.code == 507, f"{e.code} {body}")
    except Exception as e:
        r.check("Disk write error -> 507", False, str(e))
    finally:
        server_disk.shutdown()
        try:
            os.remove(blocker)
        except OSError:
            pass

    # Rate limiting (general: 120/min) - runs LAST because it pollutes the global rate limiter
    server_rl, port_rl, token_rl = _start_server()
    print("\n  Testing rate limit (120 requests)...")
    rate_limited = False
    for i in range(125):
        try:
            urlopen(_url(port_rl, "/api/files", token_rl))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                rate_limited = True
                break
    r.check("Rate limit triggered", rate_limited, "should get 429")
    server_rl.shutdown()

    server.shutdown()

    # Cleanup: exact names written by this test (never empty the folder,
    # it may contain the user's files)
    try:
        os.remove(os.path.join(dd, "sec.txt"))
    except OSError:
        pass
    for leftover in ("quota_a.bin", "quota_b.bin"):
        try:
            os.remove(os.path.join(dd, leftover))
        except OSError:
            pass

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_security() else 1)
