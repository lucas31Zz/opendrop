# Device Pairing & Web Settings (v0.14.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistent device pairing (device token + authorized IPs) so a paired phone always opens the web app unlocked; desktop gains an *Appareils* settings tab with *Parrainer*; web gains a Settings page (Appareil / Apparence / Langue).

**Architecture:** A new `DeviceRegistry` persists `devices.json` (device token + IP records) in the config dir. `_check_token` learns two short-circuits before session validation: registered IP, then a `device` token param that also heals the IP. Desktop-only routes authenticate on the main token alone. The web piggybacks everything (pairing push, token resync) on the existing 5 s quota poll.

**Tech Stack:** Python 3 stdlib (http.server, threading, json), vanilla JS/CSS, Avalonia 100% native, xunit untouched. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-14-device-pairing-design.md`

## Global Constraints

- Version **0.14.0** in pyproject.toml:3, packaging/windows/OpenDrop.iss:14+17, src/opendrop/main.py:84, desktop/OpenDrop/OpenDrop.csproj:15-17; CHANGELOG `## [0.14.0] - 2026-10-14`.
- No new dependencies. Additive changes only: existing ids / x:Names / brush keys and every existing behavior contract stay green. logo/app.ico untouched. Liquid Glass accents (#4a9eff / #1f6fd0 / #0a66d6) preserved. Scrollbar work stays cancelled — do not touch it.
- Phone performance: no new continuous polls; only the existing 5 s quota poll may carry new state.
- Code and comments in English; UI strings FR+EN (`T.en`/`T.fr` web, `Strings.*.axaml` desktop).
- Tests: homegrown framework only (`r.check`, `sys.exit(0 if test_x() else 1)`), run with `python -m tests.test_x` from the repo root, Windows PowerShell 5.1 (no `&&`).
- **NO git commit at any point in this plan.** The tree stays dirty; the user validates by hand (build desktop, pair a real phone) and only then instructs the commit. Task 12 ends by reporting and stopping.
- UI gates: web tasks use CDP probes written under `%TEMP%\opencode\` (local only, never committed), modeled on `%TEMP%\opencode\probe-delete.mjs` (headless Edge, `--ignore-certificate-errors`, token read from `%LOCALAPPDATA%\OpenDrop\session.json`). Desktop tasks gate on `dotnet build desktop/OpenDrop/OpenDrop.csproj`.
- Before probes: kill `OpenDrop.exe` and any stale python server first; start the server with `python -m opendrop.main --headless` (HTTPS self-signed on 8080, serves `web/` live — reload the page after edits).

## Review Focus

1. **Stale trust after DHCP reassignment** — a phone keeps its `did` but gets a new IP, the old IP goes to another device: the old record must be gone (did-dedup), so the new occupant gets 403. Pinned in tasks 1 and 2.
2. **Dissociate collateral** — must invalidate the sessions of that IP and rotate the token, but the main/QR session must keep working. Pinned in task 4.
3. **devices.json survives config writes** — `/api/settings` writes config.json in the same directory; a mistake there silently rewrites or wipes device trust. Pinned in task 5 (byte-identical check).
4. **Pairing push during a transfer** — the overlay must never hijack a running upload; banner instead, auto-close on window expiry. Pinned in task 9 (probe with concurrent upload).
5. **Settings access matrix** — registered IP with NO token → 200; code-unlocked guest from an unpaired IP → 403. Pinned in task 5, plus TOKEN_ROUTES_GET extension in task 5.

---

### Task 1: DeviceRegistry core

**Files:**
- Create: `src/opendrop/security/devices.py`
- Test: `tests/test_devices.py`

**Interfaces:**
- Produces (tasks 2-5 consume):
  - `DEVICE_FILE = "devices.json"`
  - `parse_user_agent(ua: str) -> dict` → `{"device": str, "browser": str, "os": str}`, `""` for unknown parts.
  - `class DeviceRegistry`:
    - `__init__(self, directory: str | Path | None = None)` — `None` → `get_config_dir()` (import from `opendrop.config.config`), exactly like `session_state.py`.
    - `token` (property, `str`) — 32 alnum via `generate_token()`; generated in memory when absent; **file written only on the first mutation**.
    - `is_registered(ip: str) -> bool`
    - `get(ip: str) -> dict | None` — copy of `{ua, did, share_info, added_at}`.
    - `list_devices() -> list[dict]` — `[{"ip", "ua", "did", "share_info", "added_at"}]` copies, sorted by `added_at`.
    - `register(ip, ua="", did="", share_info=None) -> None` — dedup by `did` (a record holding the same `did` at another IP is removed first), upsert by `ip`, `share_info=None` keeps the existing value (new record → `False`), `added_at` kept on upsert, sets `added_at` on create (UTC ISO), then `save()`.
    - `set_share_info(ip, value: bool) -> bool` — False if unregistered; `save()`.
    - `remove(ip) -> bool`; `rotate() -> str` (new token, `save()`, return it); `save() -> None` (utf-8, indent 2, temp-file + `os.replace`).
  - Thread-safe: one `threading.Lock` around every read-modify-write (the HTTP server is threaded).

- [ ] **Step 1: Write the failing tests** — `tests/test_devices.py` with the framework boilerplate copied from `tests/test_sessions.py` header (`r = TestResult()`, `test_devices()` returning `r.summary()`, `__main__` exit). First section `test_registry_core()` using `tempfile.mkdtemp()`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**
  Run: `python -m tests.test_devices`
  Expected: FAIL with `ModuleNotFoundError: No module named 'opendrop.security.devices'` (or import error at top).

- [ ] **Step 3: Implement `src/opendrop/security/devices.py`**
  Mirror `session_state.py` for the path/`directory=None` handling and `config.py:get_config_dir` import. `parse_user_agent`: simple ordered keyword scan (Edge before Chrome before Safari for browser; "iPhone"/"iPad"→device, "Windows"/"Android"/"Mac OS X"/"Linux"→os); no regex library beyond `re`, no deps. Load tolerates a missing/corrupt file (→ fresh empty state, like `load_session_state`).

- [ ] **Step 4: Run to verify it passes**
  Run: `python -m tests.test_devices`
  Expected: PASS, `N/N passed, 0 failed`.

---

### Task 2: Auth integration (`_check_token` heal + quota extras + isolation)

**Files:**
- Modify: `src/opendrop/server/server.py` (`_check_token` :290, handler `__init__` :169, `create_server` :735-753 and :768-779, `_route_quota` :527, do_GET dispatch :377-386)
- Modify: `tests/conftest.py` (`_start_server` :56)

**Interfaces:**
- Consumes: `DeviceRegistry` (task 1).
- Produces (tasks 3-5, web task 7 consume):
  - `create_server(..., devices: DeviceRegistry | None = None, config_dir: str | Path | None = None)` — `config_dir=None` → `get_config_dir()`; `devices=None` → `DeviceRegistry(config_dir)`. Sets `server.devices`, `server.config_dir`, `server.pairing_until = 0.0`. `patched_init` passes `devices=devices`; handler `__init__` gains `devices: DeviceRegistry | None = None` → `self._devices`.
  - `_check_token(self, query: dict, ip: str) -> None` — order: ① `self._devices.is_registered(ip)` → return; ② `device` param present and `validate_token(device, self._devices.token)` → `self._devices.register(ip, ua=self.headers.get("User-Agent", ""), did=query.get("did", [""])[0])` → return; ③ existing session/main-token logic unchanged. **All 7 call sites updated to pass `ip`** (lines 478, 493, 522, 528, 551, 557, 564); `_route_progress` and `_route_info` and `_route_quota` gain an `ip` parameter, dispatch lines 378/380/384 pass `ip`.
  - `_route_quota(self, query, ip)` response adds `"pairing": bool` (server window open) and `"device": self._devices.token` **only if** `is_registered(ip)`. Extras go on both the quota-present and quota-absent branches (build one `extras` dict).
  - conftest `_start_server(session_expires_in=3600, session_code=None, devices=None, config_dir=None, **kwargs)`: when `config_dir is None` → `config_dir = tempfile.mkdtemp(prefix="opendrop_cfg_", dir=_WORKSPACE)`; when `devices is None` → `devices = DeviceRegistry(config_dir)`; pass both to `create_server`. Return signature unchanged `(server, port, token)`.

- [ ] **Step 1: Write the failing tests** — new section `test_auth_heal()` in `tests/test_devices.py` (server via `_start_server()` from conftest; `from tests.conftest import _start_server, urlopen, _url`):

```python
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
        r.check("invalid device param, no token = 403", status == 403, status)
    finally:
        server2.shutdown(); server2.server_close()
```

(`_get` helper: copy the 3-line `http.client` GET from `test_routes.py:_get`, or import `_request` from `tests.test_routes` — prefer a local copy to avoid cross-suite coupling.)

- [ ] **Step 2: Run to verify it fails**
  Run: `python -m tests.test_devices`
  Expected: FAIL — `test_auth_heal` 403-checks fail (route still token-only) / TypeError on `_check_token` arity.

- [ ] **Step 3: Implement** the interfaces above in `server.py` + `conftest.py`. Keep `_check_token` body readable; the heal branch prints `[OpenDrop] Device healed: <ip>` like the existing unlock log line.

- [ ] **Step 4: Run new tests, then the touched suites**
  Run: `python -m tests.test_devices`
  Expected: PASS.
  Run: `python -m tests.test_routes`
  Expected: PASS unchanged (registered-IP path is additive; fresh temp config dir per server means no leaked registration).

- [ ] **Step 5: Verify isolation** — add to `test_auth_heal`: after pair/heal, `os.path.exists(os.path.join(_WORKSPACE-independent dir))`… concretely: `r.check("config isolated: devices.json under temp dir", os.path.exists(os.path.join(server.config_dir, "devices.json")))` with `server.config_dir` from task 2's `create_server`.

---

### Task 3: pair / status / prefs endpoints

**Files:**
- Modify: `src/opendrop/server/server.py` (do_GET dispatch after `/api/info`, do_POST dispatch after `/api/session/unlock` :419-424), `src/opendrop/i18n.py` (`_TEXT_FR`)
- Test: `tests/test_devices.py`

**Interfaces:**
- Consumes: `DeviceRegistry`, `server.devices` (task 2).
- Produces (web tasks 7-9 consume):
  - `GET /api/device/status` → `_check_token`; body `{my_ip, associated, share_info?, device_token?}` — `share_info`/`device_token` only when associated.
  - `POST /api/device/pair?device=&did=&share_info=0|1` → `_drain_left_body()` first, `limiter_session.allow(ip)`, invalid device token → `TokenInvalidError("Invalid device token")`; else `register(ip, ua=self.headers.get("User-Agent",""), did=did, share_info=(share_info=="1"))`, answer `{"success": True, "token": self._sessions.create(ip=ip), "device": self._devices.token}`. New POST branches also call `_drain_left_body()` (copy the unlock branch comment/shape at :419-424).
  - `POST /api/device/prefs?share_info=0|1` → `_check_token(query, ip)` + `set_share_info` must succeed (unregistered after check impossible — IP registered or healed by `_check_token`; still verify return) → `{"success": True}`.
  - i18n: `"Invalid device token"` → `"Jeton d\'appareil invalide"` in `_TEXT_FR`.
  - `server.pairing_until` is consumed in task 4; not touched here.

- [ ] **Step 1: Write the failing tests** — section `test_pair_status_prefs()`:

```python
def test_pair_status_prefs():
    print("--- Pair / status / prefs ---\n")
    server, port, token = _start_server()
    try:
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
```

  Add a local `_post(port, path)` helper (`_get` from task 2 already exists; both are the `http.client` request helpers copied from `test_routes.py`); import `limiter_session` from `opendrop.server.rate_limit`. Add a status-without-token check in the first server: `status == 403` when called with no token from an unregistered IP.

- [ ] **Step 2: Run to verify it fails**
  Run: `python -m tests.test_devices`
  Expected: FAIL — new routes 404.

- [ ] **Step 3: Implement** the three routes + i18n key in `server.py`. Dispatch: do_GET `elif path == "/api/device/status": self._route_device_status(query, ip)`; do_POST the three `elif` branches before the `else` 404.

- [ ] **Step 4: Run to verify it passes**
  Run: `python -m tests.test_devices` → PASS. Run: `python -m tests.test_security` → PASS unchanged.

---

### Task 4: Desktop-only endpoints + session IP invalidation

**Files:**
- Modify: `src/opendrop/server/session.py` (`Session` :8-27, `register` :83, `create` :87)
- Modify: `src/opendrop/server/server.py` (do_GET/do_POST dispatch, new route methods)
- Test: `tests/test_devices.py`

**Interfaces:**
- Consumes: `server.devices`, `server.pairing_until` (task 2).
- Produces (desktop task 11, web task 9 consume):
  - `Session.__init__(self, token, expires_in=3600, ip: str | None = None)` — public `ip` attribute.
  - `SessionManager.register(self, token)` — also records `self._main_token = token` (init `self._main_token: str | None = None` in `__init__`).
  - `SessionManager.create(self, ip: str | None = None) -> str`.
  - `SessionManager.invalidate_ip(self, ip: str) -> int` — deletes every session whose `.ip == ip`, never the `_main_token`'s session; returns count.
  - `_require_main_token(self, query) -> None` — `validate_token(query.get("token",[""])[0], self._token)` else `TokenInvalidError()`.
  - `GET /api/devices` → `_require_main_token`; `{"device_token", "pairing", "devices": [{"ip","ua","did","share_info","added_at"}]}`.
  - `POST /api/device/rotate` → main token; `{"success": True, "device_token": self._devices.rotate()}`.
  - `POST /api/device/dissociate?ip=` → main token + `ip` param, or `_check_token` + registered IP without `ip` (self); effect: `remove(ip)`, `rotate()`, `self._sessions.invalidate_ip(ip)`; `{"success": True}`.
  - `POST /api/device/pairing` → main token; `self.server.pairing_until = time.monotonic() + 60`; `{"success": True, "expires_in": 60}`.
  - `_route_session_unlock` (:548) now `self._sessions.create(ip=ip)`.
  - All three new POST branches call `_drain_left_body()` first (same shape as the unlock branch comment at :419-424, as in task 3).

- [ ] **Step 1: Write the failing tests** — section `test_desktop_endpoints()`. Unlock a guest first (seeded code: `_start_server(session_code="ABC123")`, `POST /api/session/unlock?code=ABC123` → guest token):

```python
def test_desktop_endpoints():
    print("--- Desktop-only endpoints / dissociate / pairing ---\n")
    server, port, token = _start_server(session_code="ABC123")
    try:
        status, _, body = _post(port, "/api/session/unlock?code=ABC123")
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

        old_tok = server.devices.token
        status, _, body = _post(port, "/api/device/rotate?token=" + token)
        r.check("rotate: new token, IP stays registered",
                status == 200 and json.loads(body)["device_token"] != old_tok
                and server.devices.is_registered("127.0.0.1"))

        # the guest session was created by the unlock above, from 127.0.0.1
        # (the main session has ip=None, created before any request)
        status, _, _ = _get(port, "/api/files?token=" + guest)
        r.check("guest token valid before dissociate", status == 200, status)
        status, _, _ = _post(port, "/api/device/dissociate?token=" + token + "&ip=127.0.0.1")
        r.check("dissociate = 200, record gone", status == 200
                and not server.devices.is_registered("127.0.0.1"))
        status, _, _ = _get(port, "/api/files?token=" + guest)
        r.check("Review2: that IP's session invalidated by dissociate", status == 403, status)
        status, _, _ = _get(port, "/api/files?token=" + token)
        r.check("Review2: main/QR session SURVIVES dissociate", status == 200, status)
    finally:
        server.shutdown(); server.server_close()
```

  Also add: `POST /api/device/dissociate` from an unregistered IP with no token → 403; self-dissociation path (`register` own IP, POST without `ip` and without main token, using a session token) → record gone.

- [ ] **Step 2: Run to verify it fails**
  Run: `python -m tests.test_devices` → FAIL — new routes 404, `create()` ignores ip.

- [ ] **Step 3: Implement** session.py changes + server.py routes per Interfaces. `invalidate_ip` counts and returns; log `[OpenDrop] Sessions invalidated for <ip>: <n>`.

- [ ] **Step 4: Run to verify it passes**
  Run: `python -m tests.test_devices` → PASS.
  Run: `python -m tests.test_sessions` → PASS (register/create signature is backward compatible).

---

### Task 5: Settings endpoint + config dir param + redaction + route contract docs

**Files:**
- Modify: `src/opendrop/config/config.py` (`load_config` :30, `save_config` :58)
- Modify: `src/opendrop/server/server.py` (`_SENSITIVE_QUERY` :156, do_POST dispatch)
- Modify: `tests/test_routes.py` (`TOKEN_ROUTES_GET` :35)
- Modify: `SECURITY.md` (truth table :83-93)
- Test: `tests/test_devices.py`

**Interfaces:**
- Consumes: `server.config_dir`, `_check_token`, `_require_main_token` (tasks 2-4).
- Produces (web task 8 consumes): 
  - `load_config(directory: str | Path | None = None)` / `save_config(config, directory: str | Path | None = None)` — `None` → `get_config_dir()`; every existing caller stays valid.
  - `POST /api/settings?lang=&theme=` → `_drain_left_body()` first, then allowed if `_require_main_token` passes **or** `self._devices.is_registered(ip)`; else `TokenInvalidError()` (403). Normalize with `normalize_lang`/`normalize_theme`; set `self.server.language`, `self.server.theme`, and `self.server.quota.lang` when quota exists; persist: `cfg = load_config(self.server.config_dir); cfg["language"] = lang; cfg["theme"] = theme; save_config(cfg, self.server.config_dir)`. Answer `{"success": True, "lang": lang, "theme": theme}`. Missing both params → normalize defaults ("en"/DEFAULT_THEME) and still 200.
  - `_SENSITIVE_QUERY = re.compile(r"(?i)\b(token|code|device)=[^&\s\"']+")` — plus a comment that the device token is long-lived.
  - `test_routes.TOKEN_ROUTES_GET += ["/api/devices", "/api/device/status"]` (both 403 without token).
  - SECURITY.md truth table gains rows: `GET /api/devices` (main token), `GET /api/device/status` (token or registered IP), `POST /api/device/pair` (device token, 5/min), `POST /api/device/prefs` (registered IP), `POST /api/device/dissociate` (main token+ip or registered IP self; rotates token, kills that IP's sessions), `POST /api/device/rotate` (main token), `POST /api/device/pairing` (main token, 60 s), `POST /api/settings` (main token or registered IP); and one line in section "devices.json" describing the file and that config saves never touch it.

- [ ] **Step 1: Write the failing tests** — section `test_settings()`:

```python
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
        status, _, _ = _post(port2, "/api/settings?lang=fr&token=" + token2)
        r.check("settings: main token works from unregistered IP", status == 200, status)
    finally:
        server2.shutdown(); server2.server_close()

    r.check("redaction: device token hidden in logs",
            _redact_secrets("GET /api/files?device=SECRET123&did=D1")
            == "GET /api/files?device=***&did=D1")
```

  Import `_redact_secrets` from `opendrop.server.server`.

- [ ] **Step 2: Run to verify it fails**
  Run: `python -m tests.test_devices` → FAIL (route 404, `_redact_secrets` mismatch).

- [ ] **Step 3: Implement** config.py optional `directory`, the settings route, regex update, TOKEN_ROUTES_GET extension, SECURITY.md rows.

- [ ] **Step 4: Run to verify it passes + contract still green**
  Run: `python -m tests.test_devices` → PASS.
  Run: `python -m tests.test_routes` → PASS with the two new 403 checks (46 checks).

---

### Task 6: Full Python regression

**Files:**
- None (verification only; fix fallout in the files the failing suite names).

- [ ] **Step 1: Run all 9 suites, one command per line**

```
python -m tests.test_security
python -m tests.test_routes
python -m tests.test_paths
python -m tests.test_quota
python -m tests.test_sessions
python -m tests.test_tls
python -m tests.test_server
python -m tests.test_beta
python -m tests.test_devices
```

- [ ] **Step 2: Fix any fallout and re-run the failing suite** — most likely candidates: `test_quota`/`test_paths` asserting on quota response keys (new `pairing`/`device` keys are additive — keep them), or a suite asserting an exact response body (add the keys to the expectation, never remove an existing one).

- [ ] **Step 3: Record the totals** — write down each suite's `N/N` for task 12's doc updates (SECURITY.md:333-340 table, README:457, CONTRIBUTING:27 — updated in task 12 with the version bump, together).

---

### Task 7: Web device plumbing + unlock paste

**Files:**
- Modify: `web/app.js` (top IIFE :1-2, quota handler :818-849, upload :1009, downloadUrl :1410, files :1828, unlock section :343-395), `web/index.html` (session-screen :147-160), `web/style.css` (new classes)
- Probe: `%TEMP%\opencode\probe-pair.mjs` (local only)

**Interfaces:**
- Consumes: pair/status endpoints + quota extras (tasks 2-4).
- Produces (tasks 8-9 consume): 
  - `var DEVICE_KEY = "opendrop_device"`, `var DID_KEY = "opendrop_did"`; `getDid()` generates+persists 32 alnum once (`crypto.getRandomValues` fallback `Math.random`).
  - `function authQuery(extra)` → `"token=" + encodeURIComponent(token) + (dev ? "&device=" + encodeURIComponent(dev) : "") + "&did=" + encodeURIComponent(getDid()) + (extra || "")`. Replaces the four concatenations (quota, upload, downloadUrl, files). `dev = storeRead(DEVICE_KEY) || ""`.
  - Quota handler: after `renderQuota`, `if (data.device) storeWrite(DEVICE_KEY, data.device);` then `handlePairing(!!data.pairing, !!data.device);` (`handlePairing` stub no-op here, implemented in task 9).
  - Unlock screen paste: `#paste-input` (text, placeholder via `data-i18n-attr`) + `#btn-paste` inside `#session-screen`, below the unlock form; handler `pairWithToken(value, shareInfo)` → `POST /api/device/pair?device=...&did=...&share_info=...` → on 200: `storeToken(data.token); storeWrite(DEVICE_KEY, data.device); location.reload();` on 403 show `#paste-error` (new key `device.invalid`); 429 → reuse `unlock.tooMany` message.
  - New i18n keys (both langs): `device.paste`, `device.pastePlaceholder`, `device.invalid`.

- [ ] **Step 1: Implement** the plumbing (constants, getDid, authQuery, quota extras consumption, paste field + wiring + i18n keys + minimal CSS reusing `.unlock-form` styles).
- [ ] **Step 2: Probe** — `%TEMP%\opencode\probe-pair.mjs` modeled on `probe-delete.mjs`, asserting:
  1. with no localStorage: page shows `#session-screen`, `#paste-input` visible;
  2. paste a wrong token → `#paste-error` visible, still locked;
  3. fetch the real `device_token` from `GET /api/devices?token=<main>` (main token read from session.json like the existing probe) and paste it → page reloads into `#app`;
  4. after reload, the quota request URL contains `device=` and `did=` (capture via `PerformanceObserver` or check `localStorage.getItem("opendrop_device")` non-empty).
  Run: `node %TEMP%\opencode\probe-pair.mjs` with the headless server up. Expected: all assertions print OK.
- [ ] **Step 3: Regression probe** — open the page with an existing token (main token in URL) and confirm send/receive tabs render and a file list loads (existing behavior intact).

---

### Task 8: Web Settings page

**Files:**
- Modify: `web/index.html` (`#settings-btn` inside `#app` right after the quota bar; `#settings-screen` at body level after `#session-screen`), `web/app.js`, `web/style.css` (`.settings-btn` fixed top-right at `right: 64px` z-10; `#settings-screen` overlay z-30, glass card, join the rim/relative selector lists style.css:883-922)
- Probe: `%TEMP%\opencode\probe-settings.mjs`

**Interfaces:**
- Consumes: `authQuery`, `pairWithToken` (task 7), status/settings/dissociate endpoints (tasks 3-5).
- Produces: `openSettings()` fetches `GET /api/device/status` with `authQuery()` and renders:
  - **Appareil**: if associated → token text `#device-token` + `#btn-copy-token` (clipboard API with `execCommand` fallback), `#chk-share-info` checkbox (checked = `share_info`, on change → `POST /api/device/prefs?share_info=0|1`), `#btn-dissociate` (first tap arms — reuse the web's two-tap armed pattern like folder delete; second tap → `POST /api/device/dissociate`, then `storeForget(TOKEN_KEY); storeForget(DEVICE_KEY); storeForget(DID_KEY); showSessionScreen("")`). If not associated → reuse the paste field (`#settings-paste` + `#btn-settings-paste` → `pairWithToken`).
  - **Apparence**: two buttons `#set-theme-light` / `#set-theme-dark` reflecting `serverTheme`; click → `POST /api/settings?theme=X` with `authQuery()` → on 200: `storeForget(THEME_KEY); storeForget(THEME_BASE_KEY); serverTheme = X; applyTheme();` (live apply, no reload).
  - **Langue**: `#set-lang-fr` / `#set-lang-en` → `POST /api/settings?lang=X` → on 200: `location.reload()`.
  - `#settings-close` closes the overlay. Gear hidden whenever `appEl.style.display === "none"` (it lives inside `#app`, so the existing lock/unlock toggling hides it — verify, do not add JS for it unless the display toggle proves insufficient).
  - 403 on settings POST (guest) → inline `#settings-error` with key `settings.forbidden`.
  - i18n keys: `settings.open`, `settings.title`, `settings.device`, `settings.appearance`, `settings.language`, `settings.forbidden`, `device.token`, `device.copy`, `device.copied`, `device.showInfo`, `device.dissociate`, `device.needPair`, `appearance.light`, `appearance.dark`, `lang.fr`, `lang.en` (FR+EN both dicts).

- [ ] **Step 1: Implement** markup + JS + CSS per the interfaces.
- [ ] **Step 2: Probe** `probe-settings.mjs` assertions:
  1. unlocked page: gear `#settings-btn` visible, click → `#settings-screen` open;
  2. theme: click dark → `<html data-theme>` flips AND `GET /api/info` (fresh fetch) reports the new theme; reload → still new theme;
  3. language: click Français → reload → `document.documentElement.lang === "fr"`;
  4. self-dissociate (two taps) → page ends on `#session-screen`, `localStorage` token/device/did all empty;
  5. re-paste the device token on the settings paste field → back in `#app`, gear still works.
  Run: `node %TEMP%\opencode\probe-settings.mjs`. Expected: all OK.
- [ ] **Step 3: Visual regression check** — probe screenshot of the open settings screen in dark and light (CDP `Page.captureScreenshot` to `%TEMP%\opencode\`), confirm the glass rim renders and nothing overlaps the theme toggle.

---

### Task 9: Pairing overlay + banner + busy guard

**Files:**
- Modify: `web/index.html` (`#pair-screen` + `#pair-banner` at body level), `web/app.js` (`handlePairing` real implementation in the quota tick), `web/style.css` (`.pair-screen` z-40, `.pair-banner` z-35, both glass, join rim lists)
- Probe: `%TEMP%\opencode\probe-push.mjs`

**Interfaces:**
- Consumes: `handlePairing(pairing, associated)` stub from task 7, `pairWithToken` (task 7).
- Produces: `handlePairing` logic (runs on every quota tick, no new poll):
  - `busy = currentXhr !== null || sendQueue.length > 0`.
  - `pairing && !associated && !busy` → open `#pair-screen` **once per window** (flag reset when `pairing` goes false).
  - `pairing && !associated && busy` → show `#pair-banner` (a tap opens the overlay manually — the only way in while busy).
  - `!pairing` → close overlay and hide banner (window expired).
  - Overlay: explanation text + `#chk-pair-showinfo` (default unchecked → `share_info=0`) + `#pair-token` input + `#btn-pair` → `pairWithToken(value, checked ? "1" : "0")`; `#btn-pair-close` closes it (stays closed for this window).
  - i18n keys FR+EN: `pair.title`, `pair.hint`, `pair.submit`, `pair.banner`, `pair.showInfo`.

- [ ] **Step 1: Implement** the overlay markup, `handlePairing`, CSS.
- [ ] **Step 2: Probe** `probe-push.mjs` assertions (main token from session.json, phone page in a clean profile):
  1. `POST /api/device/pairing?token=<main>` → within 5 s (one quota tick) `#pair-screen` is visible;
  2. close it, re-trigger pairing → stays closed for the window, reopens only after the window resets (post a second `pairing` after clearing);
  3. **Review4**: start an upload of a large sample file (`C:\test opendrop\partage` files exist) via the page UI, then trigger pairing → `#pair-screen` stays hidden and `#pair-banner` is visible; upload completes normally;
  4. closed state: with the window closed (fresh `GET /api/quota` reports `pairing: false`), reload the phone page → `#pair-screen` and `#pair-banner` both hidden. Server-side expiry itself is already asserted in task 4 (`server.pairing_until = 0` → quota `pairing: false`); do not wait 60 s in the probe.
  Run: `node %TEMP%\opencode\probe-push.mjs`. Expected: all OK.
- [ ] **Step 3: Re-run `probe-settings.mjs` and `probe-pair.mjs`** — no regressions in tasks 7-8 flows.

---

### Task 10: Desktop Appareils tab UI + strings

**Files:**
- Modify: `desktop/OpenDrop/SettingsWindow.axaml` (tab :248-261 between network and appearance; new `TabDevices` page inside the `Panel` at :265), `desktop/OpenDrop/SettingsWindow.axaml.cs` (ctor :26, `Tab_Click` :79-90, new fields), `desktop/OpenDrop/MainWindow.axaml.cs` (:1319 call site), `desktop/OpenDrop/Strings.fr.axaml`, `desktop/OpenDrop/Strings.en.axaml`

**Interfaces:**
- Consumes: none (pure UI, no HTTP yet — task 11).
- Produces (task 11 consumes): 
  - Ctor: `public SettingsWindow(ServerManager serverManager, HttpClient http, bool serverRunning)`; fields `_serverManager`, `_http`, `_serverRunning`. MainWindow passes `_serverManager, _http, _isRunning`.
  - `TabDevices` contents (x:Names for task 11): `TextBlock DevicesToken`, `Button BtnCopyToken`, `Button BtnPair`, `TextBlock PairHintText`, `StackPanel DevicesList`, `TextBlock DevicesEmptyText`, `Button BtnRefreshDevices`.
  - New tab RadioButton: `Tag="devices"`, `Content="{DynamicResource Tab.Devices}"`, inserted between the `network` and `appearance` entries; `Tab_Click` adds `ShowPage(TabDevices, id, "devices")`.
  - Strings (both files, FR file gets French): `Tab.Devices` = "Appareils"/"Devices", `Devices.Token` ("Jeton d'appareil"/"Device token"), `Devices.Pair` ("Parrainer"/"Pair a device"), `Devices.PairHint` ("Ouvrez les réglages OpenDrop sur l'appareil, puis Appareils.",/"Open OpenDrop settings on the device, then Devices."), `Devices.Waiting` ("En attente d'un appareil… (60 s)",/"Waiting for a device… (60 s)"), `Devices.Stopped` ("Le serveur est arrêté.",/"The server is stopped."), `Devices.None` ("Aucun appareil associé.",/"No paired devices."), `Devices.Dissociate` ("Dissocier"/"Disconnect"), `Devices.DissociateConfirm` ("Retirer cet appareil et faire pivoter le jeton ?",/"Remove this device and rotate the token?").

- [ ] **Step 1: Implement** ctor change + call site + tab XAML + strings; `TabDevices` page initial state: token hidden until loaded, `DevicesEmptyText` visible.
- [ ] **Step 2: Build**
  Run: `dotnet build desktop/OpenDrop/OpenDrop.csproj`
  Expected: `0 Error(s)`.
- [ ] **Step 3: Smoke** — launch the app, open Settings, switch through all 7 tabs (pill springs onto the new one), close. (Manual, quick.)

---

### Task 11: Desktop Appareils API integration

**Files:**
- Modify: `desktop/OpenDrop/SettingsWindow.axaml.cs`

**Interfaces:**
- Consumes: task 10 x:Names; endpoints (tasks 3-5); `_http` (loopback cert bypass already configured in MainWindow :78).
- Produces: 
  - `private string DevicesUrl(string path) => $"https://127.0.0.1:{_serverManager.Port}{path}?token={Uri.EscapeDataString(_serverManager.Token ?? "")}"` (plus extra query params via `&`).
  - `private async Task LoadDevicesAsync()` — GET `/api/devices`; fills `DevicesToken` (truncated display `token[..8]…`, full value kept in a field `DeviceTokenValue` for copy), builds one row per device in `DevicesList` (Border card: IP + parsed `ua` summary shown only when `share_info` + `added_at` date + Dissocier button wired to `BtnDissociate_Click`); empty → `DevicesEmptyText`. Server stopped (`!_serverRunning` or `Port == null`) → `PairHintText = Devices.Stopped`, `BtnPair`/`BtnCopyToken` disabled.
  - `private async void BtnPair_Click(...)` — POST `/api/device/pairing`; `PairHintText = Devices.Waiting`; `DispatcherTimer` 1.5 s poll of `/api/devices` until the device count grows or 60 s elapses (then restore `Devices.PairHint`).
  - `private async void BtnCopyToken_Click(...)` — clipboard = full token, `BtnCopyToken` content → `Btn.Copied` 1.5 s (pattern from MainWindow copy code :460-476).
  - `private async void BtnDissociate_Click(object?, string ip)` — `Msg.ConfirmAsync(this, Devices.DissociateConfirm)` → POST `/api/device/dissociate&ip=...` → reload list (token display updates after rotation).
  - `private async void BtnRefreshDevices_Click(...)` → `LoadDevicesAsync()`.
  - `Tab_Click` for `"devices"` triggers `LoadDevicesAsync()` (fire-and-forget `_ = LoadDevicesAsync()` with try/catch).
  - JSON via `System.Text.Json` (`JsonDocument`), same style as MainWindow :1140-1155; failures swallowed with a muted `PairHintText` message (no crash, no popup).

- [ ] **Step 1: Implement** per interfaces.
- [ ] **Step 2: Build**
  Run: `dotnet build desktop/OpenDrop/OpenDrop.csproj` → `0 Error(s)`.
- [ ] **Step 3: Manual validation checkpoint** — start the app, open *Appareils*, copy the token, click *Parrainer*, pair a real phone using task 7's paste field, watch it appear in the list, *Dissocier* it, confirm the phone locks. **Report the result to the user and wait**: this is the user's validation gate before task 12.

---

### Task 12: Release prep (0.14.0) + doc counts

**Files:**
- Modify: `pyproject.toml:3`, `packaging/windows/OpenDrop.iss:14` and `:17`, `src/opendrop/main.py:84` (banner `OpenDrop v0.14.0`), `desktop/OpenDrop/OpenDrop.csproj:15-17`, `CHANGELOG.md` (new section under `## [0.13.0]`), `SECURITY.md:333-340` (suite counts), `README.md:457`, `CONTRIBUTING.md:27` (route suite count)

- [ ] **Step 1: Bump the version** in the four files (`0.13.0` → `0.14.0`; csproj AssemblyVersion/FileVersion/ProductVersion → `0.14.0.0`).
- [ ] **Step 2: CHANGELOG entry** — `## [0.14.0] - 2026-10-14` with `### Added`: persistent device pairing (device token, authorized IPs, self-heal on IP change), *Appareils* tab + *Parrainer*, web Settings page (Appareil/Apparence/Langue), pairing push overlay + banner; `### Security`: device token redacted from logs, main-token-only device management routes, dissociate rotates the token and kills that IP's sessions. Follow the existing entry style (FR/EN mix as in 0.13.0 — the file is English prose).
- [ ] **Step 3: Update doc counts** from the task 6 totals: SECURITY.md suite table (add the `tests.test_devices` row with its scope and count, update any changed numbers), SECURITY.md truth table route count mention, README:457 `44/44` → new total, CONTRIBUTING:27 likewise.
- [ ] **Step 4: Final full verification**
  Run the 9 `python -m tests.test_*` suites (task 6 list) and `dotnet build desktop/OpenDrop/OpenDrop.csproj`.
  Expected: all PASS, `0 Error(s)`.
- [ ] **Step 5: Report and STOP** — summarize what changed, the suite totals, and the probes run. Do **not** commit, tag, or push: the user validates first and will instruct the commit (PowerShell 5.1: `git commit -F <message-file>`; check `$LASTEXITCODE`).
