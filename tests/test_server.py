"""Tests for upload, download, file listing, and QR code."""
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error

from opendrop.network.interfaces import _port_is_free, find_available_port
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

    # Double bind: a second server on the same port is rejected, and the
    # server already in place is correctly identified as OpenDrop.
    try:
        create_server(ip, port, "token_doublon", dd, sd, tls_cert_dir=cert_dir)
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
        create_server(ip, busy_port, "token_etranger", dd, sd, tls_cert_dir=cert_dir)
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

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_server() else 1)
