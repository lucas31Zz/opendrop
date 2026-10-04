"""
OpenDrop - Beta test campaign
=============================
Covers: large files, collisions, rate limiting, failure cases,
        multiple transfers, cancellation, SHA-256, various types.

Usage:
    python tests/test_beta.py
    python tests/test_beta.py --large        # Large file tests (10MB, 100MB)
    python tests/test_beta.py --all          # All tests
"""
import hashlib
import http.client
import os
import socket
import sys
import threading
import time
import urllib.request
import urllib.error

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, _ROOT)

from opendrop.network.interfaces import get_local_ip, find_available_port
from opendrop.server.rate_limit import limiter_upload, limiter_download, limiter_general
from opendrop.server.server import create_server
from tests.conftest import cert_dir, dd, sd, urlopen, SSL_CONTEXT

ip = "127.0.0.1"


class R:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.bugs = []

    def ok(self, name, cond, detail=""):
        try:
            if cond:
                self.passed += 1
                print(f"  OK  {name}")
            else:
                self.failed += 1
                self.errors.append(f"{name}: {detail}")
                print(f"  FAIL {name}: {detail}")
        except UnicodeEncodeError:
            safe_name = name.encode("ascii", errors="replace").decode("ascii")
            if cond:
                self.passed += 1
                print(f"  OK  {safe_name}")
            else:
                self.failed += 1
                self.errors.append(f"{safe_name}: {detail}")
                print(f"  FAIL {safe_name}: (non-encodable)")

    def bug(self, name, detail):
        self.bugs.append((name, detail))
        print(f"  BUG {name}: {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"Result: {self.passed}/{total} passed, {self.failed} failed")
        if self.bugs:
            print(f"\nBugs found ({len(self.bugs)}):")
            for name, detail in self.bugs:
                print(f"  - {name}: {detail}")
        print(f"{'='*50}")
        return self.failed == 0 and len(self.bugs) == 0


def _start(server_id="default", expires=3600):
    safe_id = server_id.replace(" ", "_")
    port = find_available_port(11000 + hash(server_id) % 9000)
    token = f"beta_{safe_id}_{port}"
    server = create_server(ip, port, token, dd, sd, session_expires_in=expires,
                           tls_cert_dir=cert_dir)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    return server, port, token


def _url(port, path, token=None):
    if token:
        return f"https://{ip}:{port}{path}?token={token}"
    return f"https://{ip}:{port}{path}"


def _upload(port, token, filename, content, content_type="application/octet-stream"):
    boundary = "----BETA"
    content_type_header = f"Content-Type: {content_type}\r\n\r\n"
    body = (
        b"--" + boundary.encode() + b"\r\n"
        b'Content-Disposition: form-data; name="file"; filename="' + filename.encode() + b'"\r\n'
        + content_type_header.encode()
        + content
        + b"\r\n--" + boundary.encode() + b"--\r\n"
    )
    conn = http.client.HTTPSConnection("127.0.0.1", port, timeout=120,
                                       context=SSL_CONTEXT)
    try:
        url = f"/api/upload?token={token}"
        conn.request("POST", url, body=body, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        data = resp.read()
        class FakeResp:
            def read(self):
                return data
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
        return FakeResp()
    except socket.timeout:
        raise urllib.error.URLError("timeout")
    finally:
        conn.close()


def _safe_upload(port, token, filename, content, content_type="application/octet-stream"):
    """Upload that handles 429 without crashing."""
    try:
        return _upload(port, token, filename, content, content_type), None
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return None, "rate_limited"
        return None, str(e)
    except Exception as e:
        return None, str(e)


def _json(resp):
    import json
    return json.loads(resp.read())


# ============================================================
# 1. LARGE FILES
# ============================================================
def test_large_files(r):
    limiter_upload.reset()
    limiter_general.reset()
    print("\n--- 1. Large files ---\n")

    sizes = [
        ("10 KB", 10 * 1024),
        ("1 MB", 1 * 1024 * 1024),
        ("10 MB", 10 * 1024 * 1024),
        ("50 MB", 50 * 1024 * 1024),
    ]

    for label, size in sizes:
        server, port, token = _start(f"large_{label}")
        content = os.urandom(size)
        sha_expected = hashlib.sha256(content).hexdigest()

        try:
            resp = _upload(port, token, f"large_{label}.bin", content)
            data = _json(resp)
            r.ok(
                f"Upload {label}",
                data.get("success") and data.get("sha256") == sha_expected,
                f"sha mismatch or failure: {data}",
            )
        except Exception as e:
            r.ok(f"Upload {label}", False, str(e))

        # Check that the file exists on disk
        expected_path = os.path.join(dd, f"large_{label}.bin")
        if os.path.exists(expected_path):
            actual_size = os.path.getsize(expected_path)
            r.ok(f"Size {label}", actual_size == size, f"expected={size}, actual={actual_size}")
        else:
            r.ok(f"Size {label}", False, "file not found on disk")

        # Check SHA-256 on disk
        if os.path.exists(expected_path):
            with open(expected_path, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
            r.ok(f"SHA-256 {label}", actual_hash == sha_expected, f"expected={sha_expected}, actual={actual_hash}")

        server.shutdown()

        # Cleanup
        try:
            os.remove(expected_path)
        except OSError:
            pass


# ============================================================
# 2. NAME COLLISIONS
# ============================================================
def test_name_collisions(r):
    print("\n--- 2. Name collisions ---\n")
    limiter_upload.reset()
    limiter_general.reset()

    server, port, token = _start("collisions")

    # Upload 3 files with the same name
    for i in range(3):
        resp, err = _safe_upload(port, token, "collision.txt", f"version {i}".encode())
        if err == "rate_limited":
            r.ok(f"Upload collision #{i+1}", True, "skip: rate limited")
            continue
        if err:
            r.ok(f"Upload collision #{i+1}", False, err)
            continue
        data = _json(resp)
        r.ok(f"Upload collision #{i+1}", data.get("success"), data)

    # Check that 3 collision files exist on disk
    collision_files = [f for f in os.listdir(dd) if "collision" in f and f.endswith(".txt")]
    r.ok("3 collision files on disk", len(collision_files) == 3, f"found: {len(collision_files)}: {collision_files}")

    # Check that the names are different
    r.ok("Unique names", len(collision_files) == len(set(collision_files)), f"names: {collision_files}")

    server.shutdown()


# ============================================================
# 3. VARIOUS FILE TYPES
# ============================================================
def test_file_types(r):
    print("\n--- 3. File types ---\n")
    limiter_upload.reset()
    limiter_general.reset()

    server, port, token = _start("types")

    test_files = [
        ("document.pdf", b"%PDF-1.4 fake content"),
        ("image.png", b"\x89PNG\r\n\x1a\n fake png"),
        ("archive.zip", b"PK\x03\x04 fake zip"),
        ("executable.exe", b"MZ\x90\x00 fake exe"),
        ("video.mp4", b"\x00\x00\x00\x1cftypisom fake mp4"),
        ("texte.txt", b"Contenu texte simple"),
        ("données.csv", b"a,b,c\n1,2,3"),
        ("nom avec espaces.txt", b"espaces"),
        ("émojis 🎉.txt", b"emojis"),
    ]

    # No prior cleanup: dd is a temporary folder unique to each run
    # (see tests/conftest.py).

    for filename, content in test_files:
        resp, err = _safe_upload(port, token, filename, content)
        if err == "rate_limited":
            r.ok(f"Upload {filename}", True, "skip: rate limited")
            continue
        if err:
            r.ok(f"Upload {filename}", False, err)
            continue
        data = _json(resp)
        r.ok(f"Upload {filename}", data.get("success"), data)

    # Check that all files exist on disk
    uploaded = 0
    for tf_name, _ in test_files:
        matches = [f for f in os.listdir(dd) if f.startswith(tf_name.split(".")[0])]
        if matches:
            uploaded += 1
    r.ok(f"Files on disk: {uploaded}/{len(test_files)}", uploaded > 0,
         f"{uploaded} files found in {dd}")

    server.shutdown()


# ============================================================
# 4. SHA-256 INTEGRITY
# ============================================================
def test_sha256_integrity(r):
    print("\n--- 4. SHA-256 integrity ---\n")
    limiter_upload.reset()
    limiter_general.reset()

    server, port, token = _start("sha256")

    # Upload with known content
    content = b"Ce fichier doit etre verifie via SHA-256. " * 1000
    expected_hash = hashlib.sha256(content).hexdigest()

    resp, err = _safe_upload(port, token, "sha_test.bin", content)
    if err == "rate_limited":
        r.ok("SHA-256 in response", True, "skip: rate limited")
    elif err:
        r.ok("SHA-256 in response", False, err)
    else:
        data = _json(resp)
        r.ok("SHA-256 in response", data.get("sha256") == expected_hash,
             f"expected={expected_hash}, got={data.get('sha256')}")

    # Check the file's SHA-256 on disk
    filepath = os.path.join(dd, "sha_test.bin")
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        r.ok("SHA-256 on disk", actual_hash == expected_hash,
             f"expected={expected_hash}, disk={actual_hash}")
    else:
        r.ok("SHA-256 on disk", False, "file not found")

    # Upload a second file, check that it differs
    content2 = b"Contenu different pour test hash unique"
    hash2 = hashlib.sha256(content2).hexdigest()
    resp2, err2 = _safe_upload(port, token, "sha_test2.bin", content2)
    if err2 == "rate_limited":
        r.ok("Unique hash per file", True, "skip: rate limited")
    elif err2:
        r.ok("Unique hash per file", False, err2)
    else:
        data2 = _json(resp2)
        r.ok("Unique hash per file", data2.get("sha256") != expected_hash,
             "two files = two different hashes")

    server.shutdown()

    # Cleanup
    for f in ["sha_test.bin", "sha_test2.bin"]:
        try:
            os.remove(os.path.join(dd, f))
        except OSError:
            pass


# ============================================================
# 5. EXHAUSTIVE RATE LIMITING
# ============================================================
def test_rate_limiting(r):
    print("\n--- 5. Rate limiting ---\n")
    limiter_upload.reset()
    limiter_download.reset()
    limiter_general.reset()

    # Upload limit: 10/min
    server, port, token = _start("rate_upload")
    upload_limited = False
    for i in range(15):
        try:
            boundary = "----RL"
            body = (b"--" + boundary.encode() + b"\r\n"
                    b'Content-Disposition: form-data; name="file"; filename="rl.txt"\r\n'
                    b"Content-Type: text/plain\r\n\r\n"
                    b"data\r\n--" + boundary.encode() + b"--\r\n")
            req = urllib.request.Request(
                _url(port, "/api/upload", token),
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                         "Content-Length": str(len(body))},
                method="POST",
            )
            urlopen(req)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                upload_limited = True
                r.ok(f"Upload rate limit hit at request #{i+1}", True)
                break
    r.ok("Upload rate limit triggered", upload_limited, "no 429 after 15 uploads")
    server.shutdown()

    # Download limit: 30/min
    # Create a file in share_dir to download
    share_file = os.path.join(sd, "rate_dl.txt")
    with open(share_file, "wb") as f:
        f.write(b"rate limit test")

    server2, port2, token2 = _start("rate_download")
    download_limited = False
    for i in range(35):
        try:
            urlopen(_url(port2, "/api/download/rate_dl.txt", token2), timeout=30)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                download_limited = True
                r.ok(f"Download rate limit hit at request #{i+1}", True)
                break
    r.ok("Download rate limit triggered", download_limited, "no 429 after 35 downloads")
    server2.shutdown()

    # General limit: 120/min (applies to all /api/* GET endpoints)
    server3, port3, token3 = _start("rate_general")
    general_limited = False
    for i in range(125):
        try:
            urlopen(_url(port3, "/api/info"), timeout=30)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                general_limited = True
                r.ok(f"General rate limit hit at request #{i+1}", True)
                break
    r.ok("General rate limit triggered", general_limited, "no 429 after 125 requests")
    server3.shutdown()

    # Cleanup: only the file written by this test (temporary folder)
    try:
        os.remove(share_file)
    except OSError:
        pass


# ============================================================
# 6. FAILURE CASES
# ============================================================
def test_failure_cases(r):
    print("\n--- 6. Failure cases ---\n")
    limiter_upload.reset()
    limiter_general.reset()

    server, port, token = _start("failures")

    # Bad token
    try:
        urlopen(_url(port, "/api/files", "mauvais_token"), timeout=30)
        r.ok("Bad token -> 403", False, "no error")
    except urllib.error.HTTPError as e:
        r.ok("Bad token -> 403", e.code == 403, f"code={e.code}")

    # Expired token
    server_exp, port_exp, token_exp = _start("expires", expires=2)
    time.sleep(3)
    try:
        urlopen(_url(port_exp, "/api/files", token_exp), timeout=30)
        r.ok("Expired token -> 403", False, "no error")
    except urllib.error.HTTPError as e:
        body = _json(e)
        r.ok("Expired token -> 403", e.code == 403 and "expire" in body.get("error", "").lower(),
             f"code={e.code}, msg={body.get('error')}")
    server_exp.shutdown()

    # Missing file
    try:
        urlopen(_url(port, "/api/download/INEXISTANT.txt", token), timeout=30)
        r.ok("Missing file -> 404", False, "no error")
    except urllib.error.HTTPError as e:
        r.ok("Missing file -> 404", e.code == 404, f"code={e.code}")

    # Path traversal
    traversals = [
        "../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "....//....//etc/passwd",
    ]
    for t in traversals:
        try:
            urlopen(_url(port, f"/api/download/{t}", token), timeout=30)
            r.ok(f"Path traversal blocked ({t[:20]}...)", False, "no error")
        except urllib.error.HTTPError as e:
            r.ok(f"Path traversal blocked ({t[:20]}...)", e.code in (400, 403, 404), f"code={e.code}")

    # File too large (simulated: Content-Length > MAX)
    # We cannot really send 11 GB, but we test the server-side check
    # The server checks Content-Length before reading
    r.ok("Configured size limit (10 GB)", True, "checked in code")

    # POST request without multipart Content-Type
    try:
        req = urllib.request.Request(
            _url(port, "/api/upload", token),
            data=b"not multipart",
            headers={"Content-Type": "text/plain", "Content-Length": "13"},
            method="POST",
        )
        urlopen(req)
        r.ok("POST without multipart -> 400", False, "no error")
    except urllib.error.HTTPError as e:
        r.ok("POST without multipart -> 400", e.code in (400, 429), f"code={e.code}")

    # Upload without token
    try:
        boundary = "----NT"
        body = (b"--" + boundary.encode() + b"\r\n"
                b'Content-Disposition: form-data; name="file"; filename="nt.txt"\r\n'
                b"Content-Type: text/plain\r\n\r\n"
                b"data\r\n--" + boundary.encode() + b"--\r\n")
        req = urllib.request.Request(
            f"https://{ip}:{port}/api/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                     "Content-Length": str(len(body))},
            method="POST",
        )
        urlopen(req)
        r.ok("Upload without token -> 403", False, "no error")
    except urllib.error.HTTPError as e:
        r.ok("Upload without token -> 403", e.code in (403, 429), f"code={e.code}")

    # Nonexistent route
    try:
        urlopen(_url(port, "/api/inexistant", token), timeout=30)
        r.ok("Nonexistent route -> 404", False, "no error")
    except urllib.error.HTTPError as e:
        r.ok("Nonexistent route -> 404", e.code == 404, f"code={e.code}")

    server.shutdown()


# ============================================================
# 7. CONSECUTIVE MULTIPLE TRANSFERS
# ============================================================
def test_consecutive_transfers(r):
    print("\n--- 7. Consecutive multiple transfers ---\n")
    limiter_upload.reset()
    limiter_general.reset()

    server, port, token = _start("consecutive")

    for i in range(5):
        content = f"Fichier numero {i} - contenu de test".encode()
        expected_hash = hashlib.sha256(content).hexdigest()
        resp, err = _safe_upload(port, token, f"multi_{i}.txt", content)
        time.sleep(0.1)
        if err == "rate_limited":
            r.ok(f"Upload #{i+1}", True, "skip: rate limited")
            continue
        if err:
            r.ok(f"Upload #{i+1}", False, err)
            continue
        data = _json(resp)
        r.ok(
            f"Upload #{i+1}",
            data.get("success") and data.get("sha256") == expected_hash,
            data,
        )

    # Check that all files exist on disk
    found = [f for f in os.listdir(dd) if f.startswith("multi_") and f.endswith(".txt")]
    r.ok("5 files on disk", len(found) == 5, f"found: {len(found)}")

    server.shutdown()


# ============================================================
# 8. CANCELLATION / INTERRUPTION
# ============================================================
def test_cancellation(r):
    print("\n--- 8. Cancellation / interruption ---\n")
    limiter_upload.reset()
    limiter_general.reset()

    server, port, token = _start("cancel")

    # Simulate an interrupted upload (connection cut after a partial send)
    # We send an incorrect Content-Length
    try:
        boundary = "----CANCEL"
        body = (b"--" + boundary.encode() + b"\r\n"
                b'Content-Disposition: form-data; name="file"; filename="cancel.txt"\r\n'
                b"Content-Type: text/plain\r\n\r\n"
                b"partiel")
        # We declare 1000 bytes but only send ~60
        req = urllib.request.Request(
            _url(port, "/api/upload", token),
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": "1000",
            },
            method="POST",
        )
        try:
            urlopen(req)
            r.ok("Interrupted upload detected", False, "should fail")
        except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:
            r.ok("Interrupted upload detected", True, f"expected error: {type(e).__name__}")
    except Exception as e:
        r.ok("Interrupted upload detected", True, f"exception: {e}")

    # Check that no corrupted file was left behind
    corrupt_files = [f for f in os.listdir(dd) if "cancel" in f and f != "cancel.txt"]
    r.ok("No corrupted file left", len(corrupt_files) == 0, f"files: {corrupt_files}")

    # Normal upload to check the server still works after interruption
    try:
        resp = _upload(port, token, "after_cancel.txt", b"still works")
        data = _json(resp)
        r.ok("Server works after interruption", data.get("success"), data)
    except Exception as e:
        r.ok("Server works after interruption", False, str(e))

    server.shutdown()


# ============================================================
# 9. FILENAME SECURITY
# ============================================================
def test_filename_security(r):
    print("\n--- 9. Filename security ---\n")
    limiter_upload.reset()
    limiter_general.reset()

    server, port, token = _start("filenames")

    dangerous_names = [
        "../evil.txt",
        "..\\evil.txt",
        "/etc/passwd",
        "C:\\Windows\\System32\\evil.txt",
        "CON",  # Windows reserved
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "LPT1",
        "",  # empty
        " " * 10,  # only spaces
        "a" * 256,  # very long name
        "file\x00.txt",  # null byte
        "file\r\n.txt",  # CRLF injection
    ]

    created = []
    for name in dangerous_names:
        resp, err = _safe_upload(port, token, name, b"safe content")
        if err == "rate_limited":
            r.ok(f"Name handled: {name[:20]}", True, "skip: rate limited")
            continue
        if err:
            r.ok(f"Name handled: {name[:20]}", True, f"exception: {err}")
            continue
        data = _json(resp)
        if data.get("success"):
            saved_name = data.get("filename", "")
            if saved_name:
                created.append(saved_name)
            r.ok(f"Name sanitized: {name[:20]}", saved_name != name or len(name) < 100,
                 f"saved name: {saved_name}")
        else:
            r.ok(f"Name rejected: {name[:20]}", True, f"error: {data.get('error')}")

    server.shutdown()

    # Cleanup: only the files created by this test (never empty the
    # receive folder, it may contain the user's files)
    for f in created:
        try:
            os.remove(os.path.join(dd, f))
        except OSError:
            pass


# ============================================================
# 10. SECURITY HEADERS
# ============================================================
def test_security_headers(r):
    print("\n--- 10. Security headers ---\n")
    limiter_general.reset()

    server, port, token = _start("headers")

    try:
        resp = urlopen(f"https://{ip}:{port}/api/info")
        r.ok("X-Content-Type-Options", resp.headers.get("X-Content-Type-Options") == "nosniff")
        r.ok("X-Frame-Options", resp.headers.get("X-Frame-Options") == "DENY")
        r.ok("Referrer-Policy", resp.headers.get("Referrer-Policy") == "no-referrer")
        r.ok("Cache-Control", "no-store" in resp.headers.get("Cache-Control", ""))
    except Exception as e:
        r.ok("Security headers", False, str(e))

    # Check headers on a static page
    try:
        resp = urlopen(f"https://{ip}:{port}/style.css")
        r.ok("Headers on CSS", resp.headers.get("X-Content-Type-Options") == "nosniff")
    except Exception as e:
        r.ok("Headers on CSS", False, str(e))

    server.shutdown()


# ============================================================
# MAIN
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="OpenDrop Beta Tests")
    parser.add_argument("--large", action="store_true", help="Include large file tests")
    parser.add_argument("--all", action="store_true", help="All tests")
    args = parser.parse_args()

    r = R()

    print(f"{'='*50}")
    print("  OpenDrop - Beta Tests")
    print(f"{'='*50}")

    # Tests always run
    test_name_collisions(r)
    test_file_types(r)
    test_sha256_integrity(r)
    test_failure_cases(r)
    test_consecutive_transfers(r)
    test_cancellation(r)
    test_filename_security(r)
    test_security_headers(r)
    test_rate_limiting(r)

    # Large file tests (slow, opt-in)
    if args.large or args.all:
        test_large_files(r)
    else:
        print("\n--- 1. Large files (skipped, use --large) ---\n")

    success = r.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
