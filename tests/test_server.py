"""Tests for upload, download, file listing, and QR code."""
import json
import os
import socket
import sys
import tempfile
import time
import urllib.request
import urllib.error

from opendrop.network.interfaces import _port_is_free, find_available_port
from opendrop.server.server import PortInUseError, create_server
from opendrop.security.devices import DeviceRegistry
from opendrop.themes import THEMES
from tests.conftest import (_WORKSPACE, _start_server, _url, _upload,
                            TestResult, cert_dir, dd, ip, sd, urlopen)

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

    # /api/info always publishes a known theme id (opendrop.themes.THEMES
    # is the single list, mirrored by ThemeManager.cs and app.js).
    try:
        resp = urlopen(_url(port, "/api/info", token))
        data = json.loads(resp.read())
        r.check("Info theme is valid", data.get("theme") in THEMES, data.get("theme"))
    except Exception as e:
        r.check("Info theme is valid", False, str(e))

    # ...and a theme written by hand in config.json falls back to "dark"
    # instead of reaching the phone page as an unknown id.
    try:
        other, _, _ = _start_server(theme="solarized")
        r.check("Unknown theme falls back to dark", other.theme == "dark", other.theme)
        other.shutdown()
    except Exception as e:
        r.check("Unknown theme falls back to dark", False, str(e))

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

    # Double bind: a second server on the same port is rejected, and the
    # server already in place is correctly identified as OpenDrop.
    try:
        cfg = tempfile.mkdtemp(prefix="opendrop_cfg_", dir=_WORKSPACE)
        create_server(ip, port, "token_doublon", dd, sd, tls_cert_dir=cert_dir,
                      devices=DeviceRegistry(cfg), config_dir=cfg)
        r.check("Second server on same port rejected", False, "no exception")
    except PortInUseError as e:
        r.check("Second server on same port rejected", "OpenDrop" in str(e), str(e))
    except Exception as e:
        r.check("Second server on same port rejected", False, str(e))

    # A port held by another program is also rejected (TLS handshake
    # fails: it is not an OpenDrop server).
    busy = socket.socket()
    busy.bind(("0.0.0.0", 0))
    busy_port = busy.getsockname()[1]
    busy.listen(5)
    try:
        cfg = tempfile.mkdtemp(prefix="opendrop_cfg_", dir=_WORKSPACE)
        create_server(ip, busy_port, "token_etranger", dd, sd, tls_cert_dir=cert_dir,
                      devices=DeviceRegistry(cfg), config_dir=cfg)
        r.check("Port occupied by another program rejected", False, "no exception")
    except PortInUseError as e:
        r.check("Port occupied by another program rejected", "another program" in str(e), str(e))
    except Exception as e:
        r.check("Port occupied by another program rejected", False, str(e))
    finally:
        busy.close()

    # Port probe: the server closes every response, so right after a
    # restart its own connections are still in TIME_WAIT on that port for
    # ~60 s. The probe must not read those leftovers as "busy", otherwise
    # find_available_port walks to port+1 and the server silently changes
    # port on every reset (Linux: 8080 -> 8081 -> 8082 while config.json
    # still says 8080). The listener is built the same way as the real one
    # (SO_REUSEADDR set), because that is what accepted sockets inherit.
    leftover = socket.socket()
    leftover.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    leftover.bind(("127.0.0.1", 0))
    leftover.listen(5)
    leftover_port = leftover.getsockname()[1]
    peer = socket.socket()
    try:
        peer.connect(("127.0.0.1", leftover_port))
        first, _ = leftover.accept()
        leftover.close()
        # The server side closes first: it is the one that ends up in
        # TIME_WAIT on 127.0.0.1:<port>.
        first.close()
        time.sleep(0.05)
        peer.close()
        time.sleep(0.3)
        r.check("TIME_WAIT leftovers do not hide the port",
                _port_is_free(leftover_port) is True)
        r.check("Preferred port kept across a restart",
                find_available_port(leftover_port) == leftover_port)
    except Exception as e:
        r.check("TIME_WAIT leftovers do not hide the port", False, str(e))
    finally:
        for s in (leftover, peer):
            try:
                s.close()
            except OSError:
                pass

    # ...while a socket that is really listening must still be reported as
    # busy: the double-bind protection above depends on it.
    live = socket.socket()
    try:
        live.bind(("0.0.0.0", 0))
        live.listen(5)
        r.check("Live listener still reported as busy",
                _port_is_free(live.getsockname()[1]) is False)
    except Exception as e:
        r.check("Live listener still reported as busy", False, str(e))
    finally:
        live.close()

    server.shutdown()

    # Cleanup: exact names written by this test (never empty the folder,
    # it may contain the user's files)
    for f in ("server_test.txt", "sha_test.txt"):
        try:
            os.remove(os.path.join(dd, f))
        except OSError:
            pass

    # A mid-body stall must not kill an upload: the connection's short
    # idle timeout reaps dead small requests, but a multi-gigabyte body
    # takes minutes and any real network gap (Wi-Fi hiccup, browser Blob
    # pacing) would otherwise abort it as "Cannot read the uploaded file"
    # (user-reported: a 4.7 GB folder zip died at the end of the upload).
    import http.client as _httpc
    import opendrop.server.server as _srv
    from tests.conftest import SSL_CONTEXT as _CTX

    _orig_req = _srv.REQUEST_TIMEOUT
    _orig_idle = getattr(_srv, "UPLOAD_IDLE_TIMEOUT", None)
    _srv.REQUEST_TIMEOUT = 1.0       # a stall this long would kill the read...
    _srv.UPLOAD_IDLE_TIMEOUT = 5.0   # ...but the upload idle window is longer
    stall_srv = None
    try:
        stall_srv, stall_port, stall_token = _start_server()
        boundary = "----STALL"
        head = (b"--" + boundary.encode() + b"\r\n"
                b'Content-Disposition: form-data; name="file"; filename="stall_test.bin"\r\n'
                b"Content-Type: application/octet-stream\r\n\r\n")
        tail = b"\r\n--" + boundary.encode() + b"--\r\n"
        content = b"x" * (2 * 1024 * 1024)   # 2 MB is enough to stall in
        conn = _httpc.HTTPSConnection("127.0.0.1", stall_port,
                                      context=_CTX, timeout=60)
        try:
            conn.putrequest("POST", f"/api/upload?token={stall_token}")
            conn.putheader("Content-Type",
                           f"multipart/form-data; boundary={boundary}")
            conn.putheader("Content-Length",
                           str(len(head) + len(content) + len(tail)))
            conn.endheaders()
            conn.send(head)
            conn.send(content[: len(content) // 2])
            time.sleep(3)   # stall: longer than REQUEST_TIMEOUT, inside the window
            conn.send(content[len(content) // 2:])
            conn.send(tail)
            resp = conn.getresponse()
            body = resp.read()
            r.check("Upload survives a mid-body stall (upload idle window)",
                    resp.status == 200, (resp.status, body[:120]))
        except Exception as e:
            r.check("Upload survives a mid-body stall (upload idle window)",
                    False, str(e))
        finally:
            conn.close()
        try:
            os.remove(os.path.join(dd, "stall_test.bin"))
        except OSError:
            pass
    finally:
        _srv.REQUEST_TIMEOUT = _orig_req
        if _orig_idle is not None:
            _srv.UPLOAD_IDLE_TIMEOUT = _orig_idle
        if stall_srv is not None:
            stall_srv.shutdown()

    # --- Chunked upload (staging): the 128 MiB-slice protocol that keeps
    # multi-gigabyte sends inside every browser's proven-small range, with
    # the committed byte count owned by the server and retries made safe
    # by truncate-to-offset before every append.
    from tests.conftest import _upload_slice, _upload_cancel
    from opendrop.server.server import transfer_state, transfer_lock
    from opendrop.server.rate_limit import limiter_upload, limiter_part
    import hashlib

    chunk_srv, chunk_port, chunk_token = _start_server()
    # Each offset-0 slice counts as a fresh upload against the 10/min
    # limiter; start this section on a clean budget so the assertions
    # are about the staging rules, not the earlier tests' consumption.
    limiter_upload.reset()
    limiter_part.reset()

    def staging_path(name, uid):
        return os.path.join(dd, f"{name}.{uid}.part")

    # 1) Three slices assemble into the exact payload, hashed whole, no .part left.
    try:
        payload = b"A" * 1000 + b"B" * 1000 + b"C" * 500
        uid = "a1b2c3d4e5f60708"
        _upload_slice(chunk_port, chunk_token, "chunky.bin", payload[0:1000], uid, 0, 2500)
        _upload_slice(chunk_port, chunk_token, "chunky.bin", payload[1000:2000], uid, 1000, 2500)
        resp = _upload_slice(chunk_port, chunk_token, "chunky.bin", payload[2000:2500],
                             uid, 2000, 2500, last=1)
        data = json.loads(resp.read())
        on_disk = open(os.path.join(dd, "chunky.bin"), "rb").read()
        left_part = any(f.endswith(".part") for f in os.listdir(dd))
        r.check("Chunked upload assembles 3 slices",
                (data.get("success") and data.get("filename") == "chunky.bin"
                 and data.get("size") == 2500
                 and data.get("sha256") == hashlib.sha256(payload).hexdigest()
                 and on_disk == payload and not left_part), data)
    except Exception as e:
        r.check("Chunked upload assembles 3 slices", False, str(e))

    # 2) A non-last slice answers the committed size and leaves the staging file.
    try:
        uid = "b2c3d4e5f6070819"
        resp = _upload_slice(chunk_port, chunk_token, "chunky2.bin", b"x" * 1000, uid, 0, 2500)
        data = json.loads(resp.read())
        part_ok = os.path.exists(staging_path("chunky2.bin", uid))
        r.check("Non-last slice answers committed size",
                (data.get("success") is True and data.get("size") == 1000
                 and "filename" not in data and part_ok), (data, part_ok))
        _upload_cancel(chunk_port, chunk_token, "chunky2.bin", uid)
    except Exception as e:
        r.check("Non-last slice answers committed size", False, str(e))

    # 3) transfer_state follows the slices (active between, done only on last).
    try:
        uid = "c3d4e5f60708192a"
        _upload_slice(chunk_port, chunk_token, "chunky3.bin", b"y" * 1000, uid, 0, 2500)
        with transfer_lock:
            mid = dict(transfer_state)
        _upload_slice(chunk_port, chunk_token, "chunky3.bin", b"z" * 1500, uid, 1000, 2500,
                      last=1)
        with transfer_lock:
            end = dict(transfer_state)
        r.check("transfer_state tracks slices",
                (mid["active"] is True and mid["done"] is False
                 and mid["received"] == 1000 and mid["size"] == 2500
                 and end["done"] is True and end["filename"] == "chunky3.bin"),
                (mid, end))
    except Exception as e:
        r.check("transfer_state tracks slices", False, str(e))

    # 4) A stale tail (lost response, killed write) is truncated to offset.
    try:
        uid = "d4e5f60708192a3b"
        _upload_slice(chunk_port, chunk_token, "chunky4.bin", b"A" * 1000, uid, 0, 402)
        resp = _upload_slice(chunk_port, chunk_token, "chunky4.bin", b"XY", uid, 400, 402,
                             last=1)
        data = json.loads(resp.read())
        on_disk = open(os.path.join(dd, "chunky4.bin"), "rb").read()
        r.check("Stale tail is truncated to offset",
                (data.get("success") and data.get("size") == 402
                 and on_disk == b"A" * 400 + b"XY"), (data, on_disk[:8]))
    except Exception as e:
        r.check("Stale tail is truncated to offset", False, str(e))

    # 5) An offset beyond the file answers 409 with the actual size (resync).
    try:
        uid = "e5f60708192a3b4c"
        _upload_slice(chunk_port, chunk_token, "chunky5.bin", b"x" * 1000, uid, 0, 5000)
        try:
            _upload_slice(chunk_port, chunk_token, "chunky5.bin", b"tail", uid, 5000, 5000,
                          last=1)
            r.check("Short offset answers 409 with actual size", False, "no 409")
        except urllib.error.HTTPError as e:
            data = json.loads(e.read())
            r.check("Short offset answers 409 with actual size",
                    (e.code == 409 and data.get("success") is False
                     and data.get("size") == 1000), (e.code, data))
        _upload_cancel(chunk_port, chunk_token, "chunky5.bin", uid)
    except Exception as e:
        r.check("Short offset answers 409 with actual size", False, str(e))

    # 6) A continuation on a staging file that does not exist answers 409 size 0.
    try:
        try:
            _upload_slice(chunk_port, chunk_token, "ghost.bin", b"zz", "f60708192a3b4c5d",
                          10, 100, last=0)
            r.check("Missing staging answers 409 size 0", False, "no 409")
        except urllib.error.HTTPError as e:
            data = json.loads(e.read())
            r.check("Missing staging answers 409 size 0",
                    (e.code == 409 and data.get("size") == 0), (e.code, data))
    except Exception as e:
        r.check("Missing staging answers 409 size 0", False, str(e))

    # 7) last with a wrong total: 409, staging kept, no final file created.
    try:
        uid = "0708192a3b4c5d6e"
        _upload_slice(chunk_port, chunk_token, "chunky7.bin", b"w" * 500, uid, 0, 9999)
        try:
            _upload_slice(chunk_port, chunk_token, "chunky7.bin", b"", uid, 500, 9999, last=1)
            r.check("last with wrong total answers 409", False, "no 409")
        except urllib.error.HTTPError as e:
            data = json.loads(e.read())
            final_absent = not os.path.exists(os.path.join(dd, "chunky7.bin"))
            staging_kept = os.path.exists(staging_path("chunky7.bin", uid))
            r.check("last with wrong total answers 409",
                    (e.code == 409 and data.get("size") == 500
                     and final_absent and staging_kept), (e.code, data))
        _upload_cancel(chunk_port, chunk_token, "chunky7.bin", uid)
    except Exception as e:
        r.check("last with wrong total answers 409", False, str(e))

    # 8) A complete same-name file is never clobbered: the final name uniquifies.
    try:
        first = os.path.join(dd, "chunky8.bin")
        with open(first, "wb") as f:
            f.write(b"original complete file")
        uid = "08192a3b4c5d6e7f"
        resp = _upload_slice(chunk_port, chunk_token, "chunky8.bin", b"new bytes", uid, 0, 9,
                             last=1)
        data = json.loads(resp.read())
        renamed = os.path.join(dd, "chunky8 (1).bin")
        r.check("Completed name is uniquified (never clobbered)",
                (data.get("filename") == "chunky8 (1).bin"
                 and open(first, "rb").read() == b"original complete file"
                 and open(renamed, "rb").read() == b"new bytes"), data)
    except Exception as e:
        r.check("Completed name is uniquified (never clobbered)", False, str(e))

    # 9) cancel unlinks the staging file; a second cancel still succeeds.
    try:
        uid = "192a3b4c5d6e7f80"
        _upload_slice(chunk_port, chunk_token, "chunky9.bin", b"j" * 100, uid, 0, 900)
        resp = _upload_cancel(chunk_port, chunk_token, "chunky9.bin", uid)
        data = json.loads(resp.read())
        gone = not os.path.exists(staging_path("chunky9.bin", uid))
        resp2 = _upload_cancel(chunk_port, chunk_token, "chunky9.bin", uid)
        data2 = json.loads(resp2.read())
        r.check("cancel unlinks staging; repeat cancel succeeds",
                (data.get("success") and gone and data2.get("success")), (data, gone, data2))
    except Exception as e:
        r.check("cancel unlinks staging; repeat cancel succeeds", False, str(e))

    # 10) A malformed upload id is rejected before anything is written.
    try:
        codes = []
        for bad_id in ("../evil", "xyz"):
            try:
                _upload_slice(chunk_port, chunk_token, "evil.bin", b"x", bad_id, 0, 1, last=1)
                codes.append("no-error")
            except urllib.error.HTTPError as e:
                codes.append(e.code)
        r.check("Invalid upload id rejected", codes == [400, 400], codes)
    except Exception as e:
        r.check("Invalid upload id rejected", False, str(e))

    # 11) Continuation slices bypass the 10/min new-upload limiter; fresh
    # uploads still count against it (the brute-force bound stays in place).
    try:
        from opendrop.server.rate_limit import limiter_upload, limiter_part
        limiter_upload.reset()
        limiter_part.reset()
        uid = "2a3b4c5d6e7f8091"
        _upload_slice(chunk_port, chunk_token, "cont.bin", b"c" * 10, uid, 0, 130)
        cont_ok = True
        for i in range(1, 12):    # 11 continuations: above the 10/min cap
            _upload_slice(chunk_port, chunk_token, "cont.bin", b"c" * 10, uid, i * 10, 130)
        limiter_429 = False
        for i in range(11):       # 11 fresh uploads: the 11th must hit 429
            try:
                _upload_slice(chunk_port, chunk_token, f"fresh{i}.bin", b"f", "3b4c5d6e7f8091a2",
                              0, 1, last=1)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    limiter_429 = True
                    break
        r.check("Continuation slices bypass upload limiter; fresh uploads keep it",
                (cont_ok and limiter_429), (cont_ok, limiter_429))
        limiter_upload.reset()
        limiter_part.reset()
    except Exception as e:
        r.check("Continuation slices bypass upload limiter; fresh uploads keep it",
                False, str(e))

    # 12) The query name is authoritative: the multipart disposition
    # filename is ignored in staging mode (protocol amendment rule).
    try:
        uid = "8091a2b3c4d5e6f7"
        payload = b"query wins"
        _upload_slice(chunk_port, chunk_token, "proto.bin", payload[:5], uid, 0, 10,
                      part_name="autre.bin")
        resp = _upload_slice(chunk_port, chunk_token, "proto.bin", payload[5:], uid, 5, 10,
                             last=1, part_name="autre.bin")
        data = json.loads(resp.read())
        autre_files = [f for f in os.listdir(dd) if f.startswith("autre")]
        r.check("Query name wins over disposition filename",
                (data.get("success") and data.get("filename") == "proto.bin"
                 and open(os.path.join(dd, "proto.bin"), "rb").read() == payload
                 and not autre_files), (data, autre_files))
    except Exception as e:
        r.check("Query name wins over disposition filename", False, str(e))

    # 13) A traversal name is sanitized and stays inside the receive folder.
    try:
        uid = "91a2b3c4d5e6f708"
        resp = _upload_slice(chunk_port, chunk_token, "../evil.bin", b"trav",
                             uid, 0, 4, last=1)
        data = json.loads(resp.read())
        inside = os.path.exists(os.path.join(dd, "evil.bin"))
        outside = os.path.exists(os.path.join(os.path.dirname(dd), "evil.bin"))
        r.check("Traversal name is contained in the receive folder",
                (data.get("success") and inside and not outside),
                (data, inside, outside))
    except Exception as e:
        r.check("Traversal name is contained in the receive folder", False, str(e))

    # 14) cancel only ever removes a .part staging file: a real received
    # file with the same name is untouched, and a traversal name is contained.
    try:
        uid = "a2b3c4d5e6f70819"
        real = os.path.join(dd, "real10.bin")
        with open(real, "wb") as f:
            f.write(b"precious")
        _upload_slice(chunk_port, chunk_token, "evilc.bin", b"c" * 50, uid, 0, 900)
        resp = _upload_cancel(chunk_port, chunk_token, "../evilc.bin", uid)
        data = json.loads(resp.read())
        real_intact = open(real, "rb").read() == b"precious"
        staging_gone = not os.path.exists(staging_path("evilc.bin", uid))
        outside = os.path.exists(os.path.join(os.path.dirname(dd), "evilc.bin"))
        r.check("cancel stays on staging, never a real file",
                (data.get("success") and real_intact and staging_gone
                 and not outside), (data, real_intact, staging_gone, outside))
    except Exception as e:
        r.check("cancel stays on staging, never a real file", False, str(e))

    # 15) A zero-byte file completes with the empty hash.
    try:
        uid = "b3c4d5e6f708192a"
        resp = _upload_slice(chunk_port, chunk_token, "zero.bin", b"", uid, 0, 0, last=1)
        data = json.loads(resp.read())
        on_disk = open(os.path.join(dd, "zero.bin"), "rb").read()
        r.check("Empty file chunked send completes",
                (data.get("success") and data.get("size") == 0
                 and data.get("sha256") == hashlib.sha256(b"").hexdigest()
                 and on_disk == b""), data)
    except Exception as e:
        r.check("Empty file chunked send completes", False, str(e))

    # 16) A lost final response stays idempotent: the retried last slice
    # (same id, offset 0 for a single-slice send) lands on the recorded
    # result instead of completing a second time into a duplicate.
    try:
        uid = "c4d5e6f708192a3b"
        resp = _upload_slice(chunk_port, chunk_token, "retry9.bin", b"data9",
                             uid, 0, 5, last=1)
        first = json.loads(resp.read())
        resp2 = _upload_slice(chunk_port, chunk_token, "retry9.bin", b"data9",
                              uid, 0, 5, last=1)
        second = json.loads(resp2.read())
        dup = os.path.exists(os.path.join(dd, "retry9 (1).bin"))
        r.check("Lost final response is answered idempotently (no duplicate)",
                (first.get("success") and second.get("success")
                 and first.get("filename") == "retry9.bin"
                 and second.get("filename") == "retry9.bin"
                 and second.get("sha256") == first.get("sha256") and not dup),
                (first, second, dup))
    except Exception as e:
        r.check("Lost final response is answered idempotently (no duplicate)",
                False, str(e))

    # Cleanup: exact names written by this section only.
    for leftover in ("chunky.bin", "chunky3.bin", "chunky4.bin", "chunky8.bin",
                     "chunky8 (1).bin", "cont.bin", "proto.bin", "evil.bin",
                     "zero.bin", "retry9.bin", "real10.bin"):
        try:
            os.remove(os.path.join(dd, leftover))
        except OSError:
            pass
    for f in os.listdir(dd):
        if f.endswith(".part") or f.startswith("fresh"):
            try:
                os.remove(os.path.join(dd, f))
            except OSError:
                pass

    chunk_srv.shutdown()

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_server() else 1)
