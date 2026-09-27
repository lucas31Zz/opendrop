"""Tests for the receive folder's global quota.

Covers: folder scanning, reservations (including concurrent ones),
507 rejection, reservation release after a failed upload, and the
disabled (unlimited) quota.
"""
import http.client
import json
import os
import shutil
import sys
import threading
import time
import urllib.error

from opendrop.network.interfaces import find_available_port
from opendrop.server.errors import QuotaExceededError
from opendrop.server.quota import QuotaTracker, directory_usage, format_size
from opendrop.server.rate_limit import limiter_general, limiter_upload
from opendrop.server.server import create_server
from tests.conftest import (SSL_CONTEXT, _raw_upload, _upload, TestResult,
                            cert_dir, dd, ip, sd)

r = TestResult()

QUOTA_BASE = os.path.join(dd, "quota")


def _start_quota(limit, name):
    """Isolated server with its own receive folder (exact scan)."""
    dl = os.path.join(QUOTA_BASE, name)
    shutil.rmtree(dl, ignore_errors=True)
    os.makedirs(dl, exist_ok=True)
    port = find_available_port(15000 + int(time.time() * 1000) % 10000)
    token = "quotatoken_" + str(port)
    server = create_server(ip, port, token, dl, sd,
                           tls_cert_dir=cert_dir, global_quota_bytes=limit)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.3)
    limiter_upload.reset()
    limiter_general.reset()
    return server, port, token, dl


def _garbage_upload(port, token, size):
    """Body of the declared length but without a valid multipart boundary.

    The server reads the whole body (so the reservation is consumed),
    fails at splitting it and must then release the reservation.
    """
    garbage = b"\x00\xffOPENDROP" * (size // 10 + 1)
    garbage = garbage[:size]
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=SSL_CONTEXT, timeout=20)
    try:
        conn.request("POST", f"/api/upload?token={token}", body=garbage,
                     headers={"Content-Type": "multipart/form-data; boundary=----GARBAGE"})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _post_body(port, token, body):
    """POST /api/upload with an already built body (exact length)."""
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=SSL_CONTEXT, timeout=20)
    try:
        conn.request("POST", f"/api/upload?token={token}", body=body,
                     headers={"Content-Type": "multipart/form-data; boundary=----TEST",
                              "Content-Length": str(len(body))})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _check_upload(port, token, name, size, label):
    try:
        data = json.loads(_upload(port, token, name, b"x" * size).read())
        r.check(label, bool(data.get("success")), data)
    except Exception as e:
        r.check(label, False, str(e))


def _check_refused(port, token, declared, label):
    status, body = _raw_upload(port, token, declared)
    try:
        payload = json.loads(body)
    except ValueError:
        payload = {}
    r.check(label,
            status == 507 and "Global quota" in payload.get("error", ""),
            f"{status} {payload}")


def _get(port, path):
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=SSL_CONTEXT, timeout=10)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _get_json(port, path):
    status, body = _get(port, path)
    if status != 200:
        raise AssertionError(f"GET {path} -> {status} {body[:120]}")
    return json.loads(body)


def _unit_tests():
    print("--- Quota unit tests ---\n")

    unit_dir = os.path.join(QUOTA_BASE, "unit")
    shutil.rmtree(unit_dir, ignore_errors=True)
    os.makedirs(os.path.join(unit_dir, "sub"))
    with open(os.path.join(unit_dir, "a.bin"), "wb") as fh:
        fh.write(b"x" * 1000)
    with open(os.path.join(unit_dir, "sub", "b.bin"), "wb") as fh:
        fh.write(b"y" * 2500)

    r.check("directory_usage sums files (recursive)",
            directory_usage(unit_dir) == 3500, directory_usage(unit_dir))
    r.check("directory_usage missing folder = 0",
            directory_usage(os.path.join(QUOTA_BASE, "inexistant")) == 0)
    r.check("format_size in KB", format_size(3500).endswith("KB"), format_size(3500))
    r.check("format_size in GB", format_size(2 ** 31).endswith("GB"), format_size(2 ** 31))

    tr = QuotaTracker(unit_dir, 4000)
    r.check("Quota active", tr.enabled)
    r.check("Initial usage = folder size", tr.usage() == 3500, tr.usage())

    tr.reserve(400)
    r.check("Reservation counted", tr.usage() == 3900, tr.usage())
    try:
        tr.reserve(200)
        r.check("Reservation beyond quota rejected", False, "no exception")
    except QuotaExceededError as e:
        r.check("Reservation beyond quota rejected", "Global quota" in str(e), str(e))

    tr.release(400)
    r.check("Release frees up space", tr.usage() == 3500, tr.usage())
    try:
        tr.reserve(500)
        r.check("Exactly reaching quota accepted", True)
    except QuotaExceededError as e:
        r.check("Exactly reaching quota accepted", False, str(e))
    tr.release(500)

    illimite = QuotaTracker(unit_dir, 0)
    r.check("Quota 0 = disabled", not illimite.enabled)
    try:
        illimite.reserve(10 ** 12)
        r.check("No quota, no limit", True)
    except QuotaExceededError as e:
        r.check("No quota, no limit", False, str(e))
    r.check("remaining with no quota = -1", illimite.remaining() == -1, illimite.remaining())

    # Negative quota (hand-edited config): treated as disabled, not as a
    # limit that can never be satisfied.
    negatif = QuotaTracker(unit_dir, -5)
    r.check("Negative quota = disabled", not negatif.enabled, negatif.limit_bytes)
    try:
        negatif.reserve(10 ** 9)
        r.check("Negative quota: no rejection", True)
    except QuotaExceededError as e:
        r.check("Negative quota: no rejection", False, str(e))

    # Two simultaneous uploads cannot slip under the limit
    vide = os.path.join(QUOTA_BASE, "vide")
    os.makedirs(vide, exist_ok=True)
    conc = QuotaTracker(vide, 30000)
    pris = threading.Event()
    libere = threading.Event()

    def _hold():
        conc.reserve(20000)
        pris.set()
        libere.wait(5)
        conc.release(20000)

    t = threading.Thread(target=_hold)
    t.start()
    pris.wait(5)
    try:
        conc.reserve(20000)
        r.check("Concurrent reservation rejected", False, "both reservations went through")
    except QuotaExceededError:
        r.check("Concurrent reservation rejected", True)
    finally:
        libere.set()
        t.join(timeout=5)


def _server_tests():
    print("\n--- Quota server tests ---\n")

    # Quota at 50,000 bytes
    server, port, token, dl = _start_quota(50000, "srv1")
    try:
        _check_upload(port, token, "dedans.bin", 10000, "Upload within quota accepted")

        _check_refused(port, token, 60000, "Upload beyond quota rejected (507)")
        r.check("No file created by the rejected upload",
                sorted(os.listdir(dl)) == ["dedans.bin"], os.listdir(dl))

        # 10,000 already present + 35,000 = 45,000 <= 50,000: the scan counts
        _check_upload(port, token, "encore.bin", 35000, "Upload computing the folder usage")

        # 45,000 + 10,000 > 50,000: rejected on the scanned usage
        _check_refused(port, token, 10000, "Rejection based on folder usage")

        # Full upload beyond the quota: the client must be able to read the
        # 507 (the connection is not cut while it is still writing).
        try:
            _upload(port, token, "reel_trop.bin", b"x" * 20000)
            r.check("Real upload beyond quota: readable 507", False, "accepted")
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read())
            r.check("Real upload beyond quota: readable 507",
                    e.code == 507 and "Global quota" in payload.get("error", ""),
                    f"{e.code} {payload}")
        except Exception as e:
            r.check("Real upload beyond quota: readable 507", False, repr(e))

        for name in os.listdir(dl):
            os.remove(os.path.join(dl, name))
        _check_upload(port, token, "apres_liberation.bin", 40000,
                      "Upload after freeing space")
    finally:
        server.shutdown()
        server.server_close()

    # Reservation released even if the upload fails
    server, port, token, dl = _start_quota(20000, "srv2")
    try:
        status, body = _garbage_upload(port, token, 15000)
        r.check("Invalid body rejected", status == 400, f"{status} {body[:120]}")
        r.check("No file created by the invalid upload",
                os.listdir(dl) == [], os.listdir(dl))
        # Without the release, the 15,000 declared would stay reserved and
        # this last upload (15,000 <= 20,000) would be rejected.
        _check_upload(port, token, "apres_echec.bin", 15000,
                      "Reservation released after a failed upload")
    finally:
        server.shutdown()
        server.server_close()

    # Quota disabled (0): despite 60,000 already present, everything goes through
    server, port, token, dl = _start_quota(0, "srv3")
    try:
        with open(os.path.join(dl, "existant.bin"), "wb") as fh:
            fh.write(b"w" * 60000)
        r.check("Quota 0 = disabled on server side", not server.quota.enabled)
        _check_upload(port, token, "sans_quota.bin", 60000,
                      "Upload beyond quota accepted now that quota is disabled")
    finally:
        server.shutdown()
        server.server_close()

    # Exact fill: the quota is reserved on the Content-Length, so we send a
    # body whose length is exactly equal to the quota. That last byte must
    # go through, and the next upload must be rejected.
    server, port, token, dl = _start_quota(50000, "srv_exact")
    try:
        entete = (b"--" + b"----TEST" + b"\r\n"
                  b'Content-Disposition: form-data; name="file"; filename="plein.bin"\r\n'
                  b"Content-Type: text/plain\r\n\r\n")
        pied = b"\r\n--" + b"----TEST" + b"--\r\n"
        corps = entete + b"x" * (50000 - len(entete) - len(pied)) + pied
        statut, corps_reponse = _post_body(port, token, corps)
        r.check("Exact quota fill (50,000 bytes)",
                statut == 200 and len(corps) == 50000,
                f"{statut} len={len(corps)} {corps_reponse[:120]}")
        # The folder only contains the file content (the multipart headers
        # are not written): "framing" bytes of quota remain.
        r.check("Usage after exact fill = file size",
                server.quota.usage() == 50000 - len(entete) - len(pied),
                server.quota.usage())

        # The remaining quota no longer even covers an upload's header
        try:
            _upload(port, token, "apres_plein.bin", b"y")
            r.check("Byte after exact fill rejected", False, "accepted")
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read())
            r.check("Byte after exact fill rejected",
                    e.code == 507 and "Global quota" in payload.get("error", ""),
                    f"{e.code} {payload}")
        except Exception as e:
            r.check("Byte after exact fill rejected", False, repr(e))
        r.check("No file created after exact fill",
                sorted(os.listdir(dl)) == ["plein.bin"], os.listdir(dl))
    finally:
        server.shutdown()
        server.server_close()

    # Two real simultaneous uploads: the atomic reservation guarantees that
    # one of the two is rejected with 507 and that the total stays <= quota.
    server, port, token, dl = _start_quota(30000, "srv_conc")
    try:
        resultats = [None, None]

        def _lance(index):
            try:
                resp = _upload(port, token, f"sim_{index}.bin", b"c" * 20000)
                resultats[index] = ("ok", resp.status)
            except urllib.error.HTTPError as e:
                resultats[index] = ("err", e.code)
            except Exception as e:
                resultats[index] = ("exc", repr(e))

        threads = [threading.Thread(target=_lance, args=(i,)) for i in (0, 1)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        codes = sorted(x[1] for x in resultats)
        r.check("Simultaneous uploads: one 200 and one 507", codes == [200, 507],
                resultats)
        r.check("Simultaneous uploads: total <= quota",
                directory_usage(dl) <= 30000, directory_usage(dl))
        r.check("Simultaneous uploads: no partial file",
                sorted(os.listdir(dl)) == ["sim_0.bin"] or
                sorted(os.listdir(dl)) == ["sim_1.bin"], os.listdir(dl))
    finally:
        server.shutdown()
        server.server_close()


def _api_tests():
    print("--- Quota API (web UI) ---\n")

    server, port, token, dl = _start_quota(50000, "api")
    try:
        status, body = _get(port, "/api/quota")
        r.check("GET /api/quota without token rejected",
                status == 403, f"{status} {body[:80]}")

        with open(os.path.join(dl, "existant.bin"), "wb") as fh:
            fh.write(b"q" * 12345)
        data = _get_json(port, f"/api/quota?token={token}")
        r.check("GET /api/quota returns usage and quota",
                data.get("usage_bytes") >= 12345 and data.get("limit_bytes") == 50000,
                data)

        _check_upload(port, token, "api.bin", 4000, "Upload accepted before reading the quota")
        data = _get_json(port, f"/api/quota?token={token}")
        r.check("Usage updated after an upload",
                data.get("usage_bytes") >= 16345, data.get("usage_bytes"))
    finally:
        server.shutdown()
        server.server_close()

    server, port, token, dl = _start_quota(0, "api_off")
    try:
        data = _get_json(port, f"/api/quota?token={token}")
        r.check("Disabled quota returns limit_bytes 0",
                data.get("limit_bytes") == 0, data)
    finally:
        server.shutdown()
        server.server_close()


def test_quota():
    print("--- Quota tests ---\n")
    _unit_tests()
    _server_tests()
    _api_tests()
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_quota() else 1)
