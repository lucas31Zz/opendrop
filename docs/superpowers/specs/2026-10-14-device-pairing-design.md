# Device Pairing & Web Settings — Design Spec (v0.14.0)

## Goal

Persistent device pairing: a phone that pairs once (paste of the device token,
or a pushed pairing overlay after the desktop clicks *Parrainer*) is
automatically trusted forever from its IP — no code, no QR, even after its
session expires. Desktop gains an "Appareils" settings tab with a *Parrainer*
button; the web gains a full Settings page (Appareil + Apparence + Langue).

## User stories

1. **Phone**: pair once → every later visit to the web app opens unlocked
   (registered IP short-circuits token checks).
2. **Desktop**: Settings → *Appareils*: copy the device token, *Parrainer*
   (opens a 60 s window in which any phone can pair), list registered devices
   (IP, user agent, share_info, date), *Dissocier* one.
3. **Web**: gear button (visible only when unlocked) → Settings page:
   - **Appareil**: paired status, my IP, show_info toggle, self-dissociate,
     or a paste field to pair when not yet paired;
   - **Apparence**: light/dark, pushed to the server (POST /api/settings);
   - **Langue**: fr/en, pushed to the server, page reloads.

## Data model

`devices.json`, in the config directory (same dir as config.json/session.json):

```json
{
  "device_token": "<32 alphanumeric>",
  "devices": {
    "192.168.1.24": {
      "ua": "Mozilla/5.0 (iPhone; ...)",
      "did": "<stable per-browser id>",
      "share_info": false,
      "added_at": "2026-10-14T10:00:00+00:00"
    }
  }
}
```

- `device_token`: `generate_token()` (32 chars), **persisted on first mutation
  only** (file absent → generated in memory, not written).
- One record per IP. `share_info` default **false** (opt-in).
- `did` dedup: when a record registers with a `did` already present at another
  IP, the old-IP record is removed (DHCP change must not leave stale trust).
- Never rewritten by config saves (same rule as session.json: separate file).

## Auth model

`_check_token(query, ip)`, in order:

1. IP registered in `DeviceRegistry` → OK (works with absent/expired token —
   this is the feature).
2. `device` param equals `device_token` (constant-time) → **heal**: register
   this IP (upsert; same-IP keeps `share_info`, new IP defaults false; dedup by
   `did`) → OK.
3. Existing session-token / main-token validation (unchanged).

Web sends `token` + `device` + `did` on every API call via a new
`authQuery()` helper.

## Endpoints

| Route | Auth | Returns / effect |
|---|---|---|
| `GET /api/devices` | main token only (`validate_token(t, self._token)`) | `{device_token, pairing, devices:[{ip, ua, share_info, added_at}]}` |
| `GET /api/device/status` | `_check_token` | `{my_ip, associated, share_info?, device_token?}` — token only if associated |
| `POST /api/device/pair?device=&did=&share_info=0\|1` | limiter_session (5/min), valid device token | registers IP+UA, returns `{success, token:<fresh session>}` (goes to TOKEN_KEY → paste-on-unlock) |
| `POST /api/device/prefs?share_info=0\|1` | registered IP (self) | `{success}` |
| `POST /api/device/dissociate[?ip=]` | main token + ip, or registered IP (self, no ip) | removes record, rotates `device_token`, invalidates sessions created from that IP (main/QR session kept) → `{success}` |
| `POST /api/device/rotate` | main token | rotates token, IPs stay → `{success, device_token}` |
| `POST /api/device/pairing` | main token | `pairing_until = now + 60s` → `{success, expires_in:60}` |
| `POST /api/settings?lang=&theme=` | main token **or** registered IP (guest 403) | live-sets `server.language`/`server.theme` (+`quota.lang`), persists config.json → `{success, lang, theme}` |

**Quota poll extras** (existing 5 s poll — zero new requests):
`pairing: bool` always; `device: <device_token>` only when the caller's IP is
registered (lets the web self-heal its stored token after rotation and detect
the pairing push).

## Sessions

- `Session` gains `ip: str | None`; `SessionManager._main_token` set in
  `register()`; `create(ip)`; new `invalidate_ip(ip) -> int` skips
  `_main_token`.
- **Known bound**: a holder of the main QR token survives dissociate until the
  next session rotation.

## Web UX

- Storage keys: `opendrop_token`, `opendrop_device`, `opendrop_did`
  (did generated once, 32 alnum).
- `authQuery()` replaces the four concatenations at app.js 823 (quota),
  1009 (upload), 1412 (download URL), 1828 (files).
- Quota tick: `data.device` → refresh stored token; `pairing && !data.device
  && !busy` → auto-open `#pair-screen`; busy (`currentXhr || sendQueue.length`)
  → show `#pair-banner` instead (**never hijack a running upload**);
  `pairing === false` → auto-close overlay and banner.
- Unlock screen: paste field `#paste-input`/`#btn-paste` → pair → store
  token+device → reload.
- Settings gear `#settings-btn` (fixed, top-right, left of the theme toggle),
  hidden with the app when locked. `#settings-screen` holds the three sections.
  Lang change → POST then `location.reload()`; theme change → POST then live
  apply (`serverTheme` + `applyTheme()`).
- Pair overlay: `share_info` checkbox (default unchecked → 0), token input,
  validate → pair → reload. Self-dissociate clears token+device+did → lock.
- New strings in `T.en` and `T.fr`. New glass surfaces join the
  `.glass-rim::before` selector list (style.css:883-892) and the
  `position: relative` list (style.css:913-922).
- z-index: settings-screen 30, pair-banner 35, pair-screen 40 (existing:
  theme-toggle 10, scroll-thumb 20).

## Desktop UX

- New *Appareils* tab: `RadioButton Tag="devices"` between **network** and
  **appearance** (SettingsWindow.axaml:255-258), page `TabDevices`.
- Content: device token + copy, *Parrainer* (60 s window, waiting state),
  device list built in code (precedent: `PopulateThemeCombo`),
  per-row *Dissocier* behind `Msg.ConfirmAsync`.
- Ctor becomes `SettingsWindow(ServerManager serverManager, HttpClient http,
  bool serverRunning)`; call site MainWindow.axaml.cs:1319. Reuse MainWindow's
  `_http` (loopback cert bypass). Server stopped → hint + disabled actions.
- New strings in `Strings.fr.axaml` + `Strings.en.axaml` (`Tab.Devices`,
  `Devices.*`, `Btn.Pair`...).

## Security

- `_SENSITIVE_QUERY` (server.py:156) gains `device` → redacted in logs.
- Every new route must 403 without credentials (`tests/test_routes.py`
  TOKEN_ROUTES_GET extended with `/api/devices`, `/api/device/status`;
  POST 403s asserted in test_devices).
- SECURITY.md truth table + test counts, README:457 and CONTRIBUTING:27 counts
  updated to actual totals.

## Global constraints

- Version **0.14.0**: pyproject.toml:3, packaging/windows/OpenDrop.iss:14+17,
  main.py:84 banner, OpenDrop.csproj:15-17, CHANGELOG entry.
- No new dependencies (Python stdlib, vanilla JS, 100% Avalonia).
- Additive only: existing ids / x:Names / brush keys and existing behavior
  contracts stay green. logo/app.ico untouched; Liquid Glass accents
  (#4a9eff / #1f6fd0 / #0a66d6) preserved; scrollbar work stays cancelled.
- Phone performance: no new continuous polls; piggyback the 5 s quota poll.
- Tests: homegrown framework (`python -m tests.test_devices`, `r.check`,
  `sys.exit(0 if ... else 1)`); 9 Python suites; UI gates = CDP probes in
  `%TEMP%\opencode\` (local, never committed) + `dotnet build`.
- No `git commit` until the user validates. PowerShell 5.1: no `&&`;
  `git commit -F <file>`; check `$LASTEXITCODE`.
- Code/comments English; UI strings FR+EN; user-facing messages French first.

## Review focus (spec is silent here → most likely to bite)

1. **Stale IP trust after DHCP reassignment**: a phone moves, a new device
   gets its old IP — must NOT inherit trust → did-dedup test (task 1-2).
2. **Dissociate collateral**: must kill that IP's sessions but never the
   main/QR session → tests for both sides (task 4).
3. **devices.json untouched by config saves**: `/api/settings` writes
   config.json in the same dir; a mistake rewrites/loses device trust → test
   that a settings POST leaves devices.json byte-identical (task 5).
4. **Pairing push during an upload**: overlay must not hijack; banner instead,
   and auto-close on window expiry → probe with a concurrent upload (task 9).
5. **Settings access matrix**: registered IP with NO token → 200; code-unlocked
   guest from an unpaired IP → 403 → truth-table test both (task 5).

## Amendment 2026-10-15 — QR/link pairing + explicit reset (user-requested)

Approved in chat. This amendment **supersedes**: the *Parrainer* button +
waiting-timer flow in Desktop UX; rows 5-6 of the Endpoints table
(`dissociate` rotation effect, `rotate` route). Everything else stands.

1. Desktop *Appareils* tab gains a **"Pour parrainer :"** section replacing
   the *Parrainer* button: a QR code of the pairing link, the link
   `https://<ip>:<port>/#pair=<device_token>` (clean origin — deliberately
   WITHOUT the `?token=<main>` query of `url_upload`: the pairing page must
   open locked so "validate or not" stays the access gate, and the master
   key never appears in the pairing QR) shown with a **copy** button and an
   **"Ouvrir dans le navigateur"** button (shell-open, default browser), and
   one **Réinitialiser** button that regenerates QR + link + the copyable
   device token together. QR via the existing QRCoder dependency
   (MainWindow.axaml.cs:1105 precedent: ECC M, box 8, PNG → Avalonia Bitmap).
2. Web: a `#pair=<32 alnum>` hash on load pre-fills `#pair-token` and opens
   the pair overlay with manual-open semantics; nothing auto-submits; the
   hash is stripped after being consumed. Skipped (hash still stripped) when
   the stored device token already equals the hash token.
3. New `POST /api/device/reset` (main token, drained first): rotates
   `device_token`, removes ALL device records, invalidates their sessions
   (main/QR session kept) → `{success, device_token}`. Desktop shows a
   confirmation dialog **only when ≥1 device is registered**; with no devices
   the reset fires directly (server does no confirmation).
4. `POST /api/device/dissociate` **no longer rotates** the device token:
   removes the record + invalidates that IP's sessions only. Known tradeoff
   (user's explicit choice): a dissociated device can re-pair with the
   still-valid token until an explicit reset.
5. `POST /api/device/rotate` **removed** (was unused) — the token changes
   only via `/api/device/reset`, structurally.
6. Desktop device list auto-refreshes (~3 s DispatcherTimer) while the
   Appareils tab is visible; the render is skipped when the device set is
   unchanged (no row flicker under the cursor).
7. Strings: Dissocier confirmation drops the rotation mention; new
   ResetConfirm (FR+EN) explains that resetting breaks pairing of all
   registered devices and they must be paired again.
