"""Tests for the device registry: token, persistence, dedup, UA parsing."""
import http.client
import json
import os
import sys
import tempfile

from tests.conftest import (TestResult, _start_server, urlopen, _url,
                            SSL_CONTEXT, ip)
from opendrop.security.devices import DeviceRegistry, parse_user_agent
from opendrop.server.rate_limit import limiter_session
from opendrop.server.server import _redact_secrets

r = TestResult()


def test_registry_core():
    print("--- DeviceRegistry (unit) ---\n")
    d = tempfile.mkdtemp(prefix="od_reg_")
    reg = DeviceRegistry(d)
    path = os.path.join(d, "devices.json")

    r.check("new registry: token is 32 alnum",
            len(reg.token) == 32 and reg.token.isalnum(), reg.token)
    r.check("new registry: file NOT written yet", not os.path.exists(path))
    r.check("new registry: nothing registered", not reg.is_registered("1.2.3.4"))

    reg.register("1.2.3.4", ua="UA1", did="dX")
    r.check("register: file written on first mutation", os.path.exists(path))
    rec = reg.get("1.2.3.4")
    r.check("register: record fields", rec["ua"] == "UA1" and rec["did"] == "dX"
            and rec["share_info"] is False and bool(rec["added_at"]), rec)

    reg.register("1.2.3.4", ua="UA2", did="dX", share_info=True)
    rec = reg.get("1.2.3.4")
    r.check("upsert: share_info=True applied", rec["share_info"] is True)
    reg.register("1.2.3.4", ua="UA3", did="dX")
    r.check("upsert: share_info=None keeps existing", reg.get("1.2.3.4")["share_info"] is True)

    reg.register("5.5.5.5", did="dX")
    r.check("did dedup: old IP record removed",
            not reg.is_registered("1.2.3.4") and reg.is_registered("5.5.5.5"))
    r.check("did dedup: exactly one device", len(reg.list_devices()) == 1)

    tok = reg.token
    r.check("rotate: token changes", reg.rotate() != tok)
    r.check("rotate: devices kept", reg.is_registered("5.5.5.5"))
    r.check("remove: unknown ip False", reg.remove("9.9.9.9") is False)
    r.check("remove: known ip True", reg.remove("5.5.5.5") is True)

    reloaded = DeviceRegistry(d)
    r.check("persistence: token and empty list after remove",
            len(reloaded.token) == 32 and reloaded.list_devices() == [])

    r.check("parse UA: iPhone/Safari",
            parse_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                             "Mobile/15E148 Safari/604.1")
            == {"device": "iPhone", "browser": "Safari", "os": "iOS"})
    r.check("parse UA: empty -> all empty",
            parse_user_agent("") == {"device": "", "browser": "", "os": ""})


def _get(port, path):
    # Local http.client GET (no cross-suite import from tests.test_routes).
    conn = http.client.HTTPSConnection(ip, port, context=SSL_CONTEXT, timeout=15)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def _post(port, path):
    # Local http.client POST (no cross-suite import from test_routes).
    # A User-Agent header is sent on purpose: browsers always send one,
    # and the pair route stores it in the device record (bare
    # http.client would send none).
    conn = http.client.HTTPSConnection(ip, port, context=SSL_CONTEXT, timeout=15)
    try:
        conn.request("POST", path, headers={"User-Agent": "OpenDrop-Test/1.0"})
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def test_auth_heal():
    print("--- Registered IP + device-token heal ---\n")
    server, port, token = _start_server()
    try:
        status, headers, body = _get(port, "/api/files")
        r.check("unregistered IP, no token = 403", status == 403, status)

        server.devices.register("127.0.0.1", ua="test")
        status, _, _ = _get(port, "/api/files")
        r.check("registered IP, no token = 200", status == 200, status)
        status, _, body = _get(port, "/api/quota")
        data = json.loads(body)
        r.check("quota: device token resynced for registered IP",
                data.get("device") == server.devices.token, data)
        r.check("quota: pairing flag present and False",
                data.get("pairing") is False, data)
        # Task 2 isolation: the registry must live under the temp config
        # dir, never under the real user config dir.
        r.check("config isolated: devices.json under temp dir",
                os.path.exists(os.path.join(server.config_dir, "devices.json")))
    finally:
        server.shutdown(); server.server_close()

    server2, port2, token2 = _start_server()
    try:
        server2.devices.register("9.9.9.9", did="DID-OLD")
        status, _, _ = _get(port2, "/api/files?device=" + server2.devices.token
                            + "&did=DID-OLD")
        r.check("device param heals unregistered IP = 200", status == 200, status)
        r.check("heal: this IP now registered", server2.devices.is_registered("127.0.0.1"))
        r.check("heal: stale old-IP record with same did removed",
                not server2.devices.is_registered("9.9.9.9"))
        status, _, _ = _get(port2, "/api/files?device=0000")
        r.check("registered IP + invalid device param still 200 (order 1 beats 2)",
                status == 200, status)
    finally:
        server2.shutdown(); server2.server_close()

    server3, port3, _ = _start_server()
    try:
        status, _, _ = _get(port3, "/api/files?device=0000")
        r.check("unregistered IP + invalid device param + no token = 403",
                status == 403, status)
    finally:
        server3.shutdown(); server3.server_close()


def test_pair_status_prefs():
    print("--- Pair / status / prefs ---\n")
    server, port, token = _start_server()
    try:
        status, _, body = _get(port, "/api/device/status")
        r.check("status without token from unregistered IP = 403",
                status == 403, status)

        status, _, body = _post(port, "/api/device/prefs?share_info=1")
        r.check("prefs from unregistered IP = 403", status == 403, status)

        status, _, body = _post(port, "/api/device/pair?device="
                                + server.devices.token + "&share_info=1&did=DID-A")
        data = json.loads(body)
        r.check("pair valid token = 200 + fresh session token",
                status == 200 and len(data.get("token", "")) == 32, data)
        r.check("pair: IP registered, UA stored, share_info True",
                server.devices.is_registered("127.0.0.1")
                and bool(server.devices.get("127.0.0.1")["ua"])
                and server.devices.get("127.0.0.1")["share_info"] is True)

        status, _, body = _get(port, "/api/device/status?token=" + data["token"])
        s = json.loads(body)
        r.check("status: associated + device_token + share_info",
                s.get("associated") is True and s.get("device_token") == server.devices.token
                and s.get("share_info") is True and s.get("my_ip") == "127.0.0.1", s)

        status, _, _ = _post(port, "/api/device/pair?device=WRONG")
        r.check("pair invalid device token = 403", status == 403, status)

        status, _, _ = _post(port, "/api/device/prefs?share_info=0")
        r.check("prefs: share_info flipped off",
                status == 200 and server.devices.get("127.0.0.1")["share_info"] is False)
    finally:
        server.shutdown(); server.server_close()

    server2, port2, _ = _start_server()   # fresh: rate limit clean
    try:
        limiter_session.reset()
        got429 = 0
        for _ in range(6):
            st, _, _ = _post(port2, "/api/device/pair?device=WRONG")
            if st == 429: got429 += 1
        r.check("pair: 6th attempt in the window = 429", got429 >= 1, got429)
    finally:
        limiter_session.reset()
        server2.shutdown(); server2.server_close()


def test_desktop_endpoints():
    print("--- Desktop-only endpoints / dissociate / pairing ---\n")
    server, port, token = _start_server(session_code="ABC234")
    try:
        status, _, body = _post(port, "/api/session/unlock?code=ABC234")
        guest = json.loads(body)["token"]

        status, _, _ = _get(port, "/api/devices")
        r.check("GET /api/devices no token = 403", status == 403, status)
        status, _, _ = _get(port, "/api/devices?token=" + guest)
        r.check("GET /api/devices guest session token = 403 (main token only)",
                status == 403, status)
        status, _, body = _get(port, "/api/devices?token=" + token)
        data = json.loads(body)
        r.check("GET /api/devices main token = 200 with device_token+pairing+devices",
                status == 200 and data.get("device_token") == server.devices.token
                and data.get("pairing") is False and isinstance(data.get("devices"), list), data)

        server.devices.register("127.0.0.1", did="D1")
        status, _, body = _post(port, "/api/device/pairing?token=" + token)
        r.check("POST /api/device/pairing = 200", status == 200, json.loads(body))
        status, _, body = _get(port, "/api/quota?token=" + guest)
        r.check("quota reports pairing window open", json.loads(body).get("pairing") is True)
        server.pairing_until = 0
        status, _, body = _get(port, "/api/quota?token=" + guest)
        r.check("quota reports pairing window closed after expiry",
                json.loads(body).get("pairing") is False)

        # the guest session was created by the unlock above, from 127.0.0.1
        # (the main session has ip=None, created before any request)
        status, _, _ = _get(port, "/api/files?token=" + guest)
        r.check("guest token valid before dissociate", status == 200, status)
        tok_before = server.devices.token
        status, _, _ = _post(port, "/api/device/dissociate?token=" + token + "&ip=127.0.0.1")
        r.check("dissociate = 200, record gone", status == 200
                and not server.devices.is_registered("127.0.0.1"))
        r.check("dissociate: token NOT rotated (reset-only rule)",
                server.devices.token == tok_before, server.devices.token)
        status, _, _ = _get(port, "/api/files?token=" + guest)
        r.check("Review2: that IP's session invalidated by dissociate", status == 403, status)
        status, _, _ = _get(port, "/api/files?token=" + token)
        r.check("Review2: main/QR session SURVIVES dissociate", status == 200, status)
    finally:
        server.shutdown(); server.server_close()

    # Dissociate auth without the desktop's main token.
    server2, port2, token2 = _start_server(session_code="ABC234")
    try:
        status, _, _ = _post(port2, "/api/device/dissociate")
        r.check("dissociate from unregistered IP, no token = 403", status == 403, status)

        status, _, body = _post(port2, "/api/session/unlock?code=ABC234")
        guest2 = json.loads(body)["token"]
        server2.devices.register("127.0.0.1", did="SELF")
        status, _, _ = _post(port2, "/api/device/dissociate?token=" + guest2)
        r.check("self-dissociation (session token, no ip) removes record",
                status == 200 and not server2.devices.is_registered("127.0.0.1"))
    finally:
        server2.shutdown(); server2.server_close()


def test_reset(r):
    server, port, token = _start_server(session_code="ABC234")
    try:
        status, _, _ = _get(port, "/api/files?device=" + server.devices.token + "&did=DID-RESET")
        r.check("reset: setup registered 127.0.0.1",
                status == 200 and server.devices.is_registered("127.0.0.1"))
        status, _, body = _post(port, "/api/session/unlock?code=ABC234")
        guest = json.loads(body)["token"]
        tok_before = server.devices.token
        status, _, body = _post(port, "/api/device/reset?token=" + token)
        data = json.loads(body)
        r.check("reset: 200", status == 200, status)
        r.check("reset: token rotated + new one returned",
                server.devices.token != tok_before
                and data.get("device_token") == server.devices.token, data)
        r.check("reset: all device records removed",
                not server.devices.is_registered("127.0.0.1"))
        status, _, _ = _get(port, "/api/files?token=" + guest)
        r.check("reset: that IP's sessions invalidated", status == 403, status)
        status, _, _ = _get(port, "/api/files?token=" + token)
        r.check("reset: main session survives", status == 200, status)
        tok2 = server.devices.token
        status, _, body2 = _post(port, "/api/device/reset?token=" + token)
        d2 = json.loads(body2)
        r.check("reset: works with no devices too",
                status == 200 and d2.get("device_token") != tok2,
                (status, d2))
    finally:
        server.shutdown(); server.server_close()


def test_settings():
    print("--- POST /api/settings + redaction ---\n")
    server, port, token = _start_server()
    try:
        cfg_path = os.path.join(server.config_dir, "config.json")
        dev_path = os.path.join(server.config_dir, "devices.json")
        server.devices.register("127.0.0.1", did="D1")   # writes devices.json
        dev_before = open(dev_path, "rb").read()

        status, _, body = _post(port, "/api/settings?lang=fr&theme=light")
        r.check("settings from registered IP with NO token = 200", status == 200, status)
        r.check("settings: live-set lang+theme",
                server.language == "fr" and server.theme == "light")
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        r.check("settings: persisted to config.json in config_dir",
                cfg.get("language") == "fr" and cfg.get("theme") == "light", cfg)
        r.check("Review3: devices.json byte-identical after settings write",
                open(dev_path, "rb").read() == dev_before)
    finally:
        server.shutdown(); server.server_close()

    server2, port2, token2 = _start_server(session_code="XYZ789")
    try:
        status, _, body = _post(port2, "/api/session/unlock?code=XYZ789")
        guest = json.loads(body)["token"]
        status, _, _ = _post(port2, "/api/settings?lang=fr&token=" + guest)
        r.check("Review5: code-unlocked guest from unpaired IP = 403", status == 403, status)
        # Amendment 1 (task 3 review): the same guest token must get the
        # privacy-guaranteed status answer from an unregistered IP:
        # associated=False, and the device token / share_info stay absent.
        status, _, body = _get(port2, "/api/device/status?token=" + guest)
        s = json.loads(body)
        r.check("Review1: guest status unregistered IP = 200, associated False, "
                "no device_token/share_info",
                status == 200 and s.get("associated") is False
                and "device_token" not in s and "share_info" not in s, s)
        status, _, _ = _post(port2, "/api/settings?lang=fr&token=" + token2)
        r.check("settings: main token works from unregistered IP", status == 200, status)
    finally:
        server2.shutdown(); server2.server_close()

    r.check("redaction: device token hidden in logs",
            _redact_secrets("GET /api/files?device=SECRET123&did=D1")
            == "GET /api/files?device=***&did=D1")


def test_devices():
    test_registry_core()
    test_auth_heal()
    test_pair_status_prefs()
    test_desktop_endpoints()
    test_reset(r)
    test_settings()
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_devices() else 1)
