# Pairing QR/Link + Explicit Reset — Implementation Plan (amendment)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the desktop *Parrainer* button with a "Pour parrainer :" section (QR + link + open-in-browser + copy), make the pairing token change only via an explicit *Réinitialiser* action (with confirmation only when devices are registered), and pre-fill the web pairing overlay from a `#pair=<token>` link/QR hash.

**Architecture:** Server: new `POST /api/device/reset`, `dissociate` stops rotating, unused `rotate` route deleted. Web: init-time hash read pre-fills `#pair-token` and opens the existing overlay. Desktop: TabDevices gains QR (existing QRCoder dependency) + link row + reset button; the 60 s pairing-window timer is removed; the list auto-refreshes while the tab is open.

**Tech Stack:** Python stdlib server, vanilla JS web, Avalonia (QRCoder already referenced — MainWindow.axaml.cs:1105 precedent).

**Spec:** `docs/superpowers/specs/2026-10-14-device-pairing-design.md` — Amendment section 2026-10-15 (authoritative over the Endpoints rows for `dissociate`/`rotate` and the *Parrainer* bullet). Parent plan: `docs/superpowers/plans/2026-10-14-device-pairing-web-settings.md` (tasks 1-11 done; its task 12 = version bump, still runs after the user's validation of BOTH plans).

## Global Constraints

- **NO git commit at any point in this plan.** The tree stays dirty; the user validates by hand (desktop build + real phone) and only then instructs the commit (parent plan task 12 runs first).
- No new dependencies: QRCoder is already referenced by the desktop project (verify in OpenDrop.csproj); Python stdlib; vanilla JS/CSS.
- Additive only: existing ids / x:Names / behavior contracts stay green.
- Tests: homegrown framework (`python -m tests.test_devices`, `r.check`, `sys.exit(0 if ok else 1)`); UI gates = CDP probes in `%TEMP%\opencode\` (local, never committed) + `dotnet build desktop/OpenDrop/OpenDrop.csproj` (0 errors).
- PowerShell 5.1: no `&&`; one command at a time.
- Code/comments English; UI strings FR+EN (French first in FR files).
- Hermetic probes: headless server with LOCALAPPDATA redirected to a temp dir; probe token from the temp session.json; kill servers after; pair limiter 5/min → 60 s between re-pairs.
- Phone performance: no new continuous polls (the desktop 3 s timer is desktop-only, gated on tab visibility).

## Review Focus (spec-amendment silent here → most likely to bite)

1. **Stale QR/link after reset**: the QR and link must encode the NEW token immediately after reset — a stale QR pairs with a dead token → task 3 simulated check (compare displayed link token with a fresh `GET /api/devices`).
2. **Auto-refresh row flicker**: the 3 s timer must skip re-rendering when the device set is unchanged, or the *Dissocier* button moves under the cursor → task 3: skip-if-unchanged signature (count + ip set + share_info flags) + implementer observation while a row is hovered.
3. **Hash prefill when already paired**: `#pair=<current token>` on a paired browser must NOT open the overlay (pointless, closes on next tick) → task 2 probe case 2.
4. **Reset collateral**: all device records + their sessions die, main/QR session survives, token rotates → task 1 test (`test_reset`).
5. **Dissociate no-rotate honesty**: SECURITY.md documents the re-pair tradeoff; the Dissocier confirm text no longer mentions rotation → task 1 doc edit + task 3 strings check.

---

### Task 1: Server — reset route, dissociate no-rotate, remove rotate

**Files:**
- Modify: `src/opendrop/server/server.py` (POST dispatch + handlers)
- Modify: `tests/test_devices.py` (`test_desktop_endpoints` amendments + new `test_reset` section)
- Modify: `SECURITY.md` (truth-table rows + devices.json paragraph)

**Interfaces:**
- Consumes: `self._devices` (DeviceRegistry: `list_devices()`, `remove(ip)`, `rotate()`, `token`, `is_registered(ip)`), `self._sessions.invalidate_ip(ip)`, `self._require_main_token(query)`, `self._drain_left_body()`, `_start_server`/`_get`/`_post` test helpers (tests/test_devices.py).
- Produces: `POST /api/device/reset?token=<main>` → `{"success": true, "device_token": "<new 32 alnum>"}` (rotates, removes ALL records, invalidates their sessions, main/QR kept). `dissociate` effect: remove + invalidate that IP's sessions, **no rotation**. `/api/device/rotate` gone.

- [ ] **Step 1: Amend the failing tests** (tests/test_devices.py)

In `test_desktop_endpoints`:
- Capture `tok_before = server.devices.token` immediately before the dissociate POST; replace the "token rotated" assertion with:
  `r.check("dissociate: token NOT rotated (reset-only rule)", server.devices.token == tok_before, server.devices.token)`
  Keep the existing record-removed, session-invalidated, and main-session-survives assertions unchanged.
- DELETE the `/api/device/rotate` test block entirely (route is removed).

Add and wire a new section `test_reset()`:

```python
def test_reset(r):
    server, port, token = _start_server(session_code="ABC234")
    try:
        status, _, _ = _get(port, "/api/files?device=" + server.devices.token + "&did=DID-RESET")
        r.check("reset: setup registered 127.0.0.1", status == 200 and server.devices.is_registered("127.0.0.1"))
        guest = <unlock via /api/session/unlock?code=ABC234, same helper usage as test_desktop_endpoints>["token"]
        tok_before = server.devices.token
        status, body, _ = _post(port, "/api/device/reset?token=" + token)
        r.check("reset: 200", status == 200, status)
        r.check("reset: token rotated + new one returned",
                server.devices.token != tok_before and body["device_token"] == server.devices.token)
        r.check("reset: all device records removed", not server.devices.is_registered("127.0.0.1"))
        status, _, _ = _get(port, "/api/files?token=" + guest)
        r.check("reset: that IP's sessions invalidated", status == 403, status)
        status, _, _ = _get(port, "/api/files?token=" + token)
        r.check("reset: main session survives", status == 200, status)
        tok2 = server.devices.token
        status, body2, _ = _post(port, "/api/device/reset?token=" + token)
        r.check("reset: works with no devices too", status == 200 and body2["device_token"] != tok2)
    finally:
        server.shutdown(); server.server_close()
```

(Match the file's existing helper return conventions for body access.)

- [ ] **Step 2: Run to verify the failures**

Run: `python -m tests.test_devices` — Expected: new reset checks FAIL (404 route), dissociate-rotation check FAIL (still rotates), rotate-block deletion compiles.

- [ ] **Step 3: Implement** (src/opendrop/server/server.py)

- New `_route_device_reset(self, query)`: `self._drain_left_body()` at the dispatch branch (same shape as the other POSTs), `self._require_main_token(query)`, collect the registered IPs from `self._devices.list_devices()` (entries carry `ip` — verify in devices.py), `new = self._devices.rotate()`, then for each ip: `self._devices.remove(ip)` + `self._sessions.invalidate_ip(ip)`, respond `{"success": True, "device_token": new}`. No rate limiter (main-token desktop route, consistent with dissociate).
- `_route_device_dissociate`: remove the `self._devices.rotate()` call and any comment mentioning rotation.
- Delete the `/api/device/rotate` dispatch branch and its handler method.

- [ ] **Step 4: Run to green**

Run: `python -m tests.test_devices`, then `python -m tests.test_routes`, then `python -m tests.test_security` — Expected: all green, output pristine.

- [ ] **Step 5: SECURITY.md truth table**

- `dissociate` row: effect = "removes record, invalidates that IP's sessions (main/QR kept)" (drop "rotates device_token").
- DELETE the `rotate` row.
- ADD a `reset` row: main token; "rotates device_token, removes ALL records, invalidates their sessions (main/QR kept)".
- devices.json paragraph: add the sentence "The device token changes only via `POST /api/device/reset`."
- Do NOT touch the suite-count table (parent task 12 updates it).

---

### Task 2: Web — `#pair=<token>` hash pre-fill

**Files:**
- Modify: `web/app.js` (pair-overlay section, after `openPairScreen` and element wiring from task 9)
- Probe: `%TEMP%\opencode\probe-prefill.mjs` (local only)

**Interfaces:**
- Consumes: `openPairScreen(manual)` (task 9 — manual=true survives busy step-down), `storeRead(DEVICE_KEY)`, `#pair-token` input, `#btn-pair` (existing submit → `pairWithToken`).
- Produces: nothing new — the overlay's existing submit flow.

- [ ] **Step 1: Implement the pre-fill** (web/app.js, in the pair-overlay section after the element wiring)

```js
(function () {
    var m = /^#pair=([A-Za-z0-9]{32})$/.exec(location.hash || "");
    if (!m) return;
    var tok = m[1];
    history.replaceState(null, "", location.pathname + location.search);
    if (storeRead(DEVICE_KEY) === tok) return; // already paired with this token
    var input = document.getElementById("pair-token");
    if (input) input.value = tok;
    openPairScreen(true);
})();
```

Comment: reads the pairing link/QR hash (desktop "Pour parrainer" section); nothing auto-submits.

- [ ] **Step 2: Hermetic probe** (probe-prefill.mjs, pattern from probe-pair.mjs; server with LOCALAPPDATA redirected, main token from temp session.json)

1. Clean profile → open `https://127.0.0.1:<port>/#pair=<valid 32-alnum>` (fetch a device_token via `GET /api/devices?token=<main>`) → `#pair-screen` visible, `#pair-token` value === token, `location.hash === ""`. Click `#btn-pair` → page unlocked, `localStorage` token+device non-empty.
2. Same browser (now paired) → reload `#pair=<same token>` → `#pair-screen` NOT visible.
3. `#pair=abc` (malformed) → no overlay, page behaves normally.
4. Regression: re-run probe-pair.mjs, probe-settings.mjs, probe-push.mjs green (60 s spacing where the pair limiter is involved).

- [ ] **Step 3: Self-review** — the regex admits only 32 alnum; the hash is consumed only when matched; no other app.js behavior touched.

---

### Task 3: Desktop — "Pour parrainer :" section + reset + open-in-browser + auto-refresh

**Files:**
- Modify: `desktop/OpenDrop/SettingsWindow.axaml` (TabDevices rework)
- Modify: `desktop/OpenDrop/SettingsWindow.axaml.cs`
- Modify: `desktop/OpenDrop/Strings.fr.axaml` + `desktop/OpenDrop/Strings.en.axaml`

**Interfaces:**
- Consumes: task 10-11 shell (`_serverManager.UrlUpload`, `_serverManager.Port`, `_http`, `_serverManager.Token`, `DeviceTokenValue`, `LoadDevicesAsync`, `Msg.ConfirmAsync`, `Lang.T`, clipboard copy pattern); `POST /api/device/reset` (task 1); QRCoder pattern from `MainWindow.axaml.cs:1105-1130` (`QRCodeGenerator` ECC M, `PngByteQRCode.GetGraphic(8)`, MemoryStream → Avalonia `Bitmap`); shell-open precedent (grep `UseShellExecute` in desktop/).
- Produces: x:Names `PairQrImage`, `PairLinkText`, `BtnCopyLink`, `BtnOpenLink`, `BtnReset` (BtnPair removed).

- [ ] **Step 1: XAML rework** (TabDevices)

Order: token row (DevicesToken + BtnCopyToken) → `TextBlock` label `Devices.PourParrainer` → pair card (Border joining the settings card styles: `Image x:Name="PairQrImage"` ~160px, `TextBlock x:Name="PairLinkText"` full link with tooltip) + `BtnCopyLink` (`Devices.Copy` or reuse an existing copy label) + `BtnOpenLink` (`Devices.OpenBrowser`) → `Button x:Name="BtnReset"` (`Devices.Reset`) → existing devices list + `BtnRefreshDevices` + `DevicesEmptyText` + `PairHintText` (kept for the stopped state). DELETE the `BtnPair` button.

- [ ] **Step 2: Code-behind**

- Remove `BtnPair_Click`, its DispatcherTimer, and all `Devices.Waiting` usage.
- **Controller correction (post-task-3 review):** PairLink = `https://{_serverManager.Ip}:{_serverManager.Port}/#pair={DeviceTokenValue}` — clean origin. NOT `UrlUpload`: `main.py:64` builds it as `https://{ip}:{port}/?token={token}` (master QR token), which would open the phone already-unlocked (no validation gate) and burn the master key into the pairing QR. Ip/Port null (stopped) → empty link → the existing guards hide the card.
- `UpdatePairSection()`: render the QR from `PairLink` via the QRCoder pattern (try/catch → hide the card on failure); set `PairLinkText.Text = PairLink`. Call it from `LoadDevicesAsync` whenever the token display updates.
- `LoadDevicesAsync`: build a cheap signature of the rendered set (count + ip set + share_info flags); skip row re-render when unchanged (Review Focus #2).
- `BtnReset_Click`: stopped → return; if rows exist → `Msg.ConfirmAsync(this, Devices.ResetConfirm)` (cancel → return); `POST /api/device/reset?token=...` → set `DeviceTokenValue` from the response, `UpdatePairSection()`, `LoadDevicesAsync()`. No rows → same POST directly, no dialog.
- `BtnCopyLink_Click`: clipboard = PairLink, label → `Btn.Copied` 1.5 s. `BtnOpenLink_Click`: shell-open `PairLink` (`UseShellExecute = true`), try/catch silent.
- Auto-refresh: `DispatcherTimer` 3 s, started on `Tab_Click` "devices", stopped on any other tab and on window `Closed`; tick → `_ = LoadDevicesAsync()` guarded against re-entry while a load is in flight.
- Stopped state (refreshed from `_serverManager` per task 11): hide the pair card, disable BtnReset/BtnCopyLink/BtnOpenLink/BtnCopyToken, `PairHintText = Devices.Stopped`.

- [ ] **Step 3: Strings** (both files)

- ADD: `Devices.PourParrainer` "Pour parrainer :" / "To pair a device:"; `Devices.OpenBrowser` "Ouvrir dans le navigateur" / "Open in browser"; `Devices.Reset` "Réinitialiser" / "Reset"; `Devices.ResetConfirm` "Réinitialiser cassera le parrainage de tous les appareils appairés : ils devront être appairés à nouveau. Continuer ?" / "Reset will break pairing for all registered devices: they will have to be paired again. Continue?"; `Devices.Copy` "Copier" / "Copy" (only if no existing copy label fits).
- CHANGE: `Devices.DissociateConfirm` → "Retirer cet appareil ?" / "Remove this device?" (rotation mention dropped).
- REMOVE after usage-grep: `Devices.Pair`, `Devices.PairHint`, `Devices.Waiting`.

- [ ] **Step 4: Build + simulated validation**

Run: `dotnet build desktop/OpenDrop/OpenDrop.csproj` → 0 errors. Then (kill stale processes first; launch exe):
1. Appareils tab: QR card + link visible; link token matches `GET /api/devices?token=<main>` (main token from `%LOCALAPPDATA%\OpenDrop\session.json`).
2. `curl.exe -k -X POST ".../api/device/pair?device=<tok>&did=SIM"` → row appears WITHOUT clicking refresh (auto-refresh works) within ~6 s.
3. Hover a row's *Dissocier* for ~10 s → row does NOT flicker/rebuild (skip-if-unchanged).
4. *Réinitialiser* with the device present → popup appears → accept → row gone, `PairLinkText` now contains the NEW token (fetch fresh device_token), old SIM session (if any) dead.
5. *Réinitialiser* again with no devices → NO popup, direct rotation.
6. *Ouvrir dans le navigateur* → default browser opens the URL; *Copier* → clipboard holds the link.
7. Kill the server → stopped state (card hidden, actions disabled, hint). Close app, no stray processes.

- [ ] **Step 5: Report and STOP** — this is the user's manual-validation gate (real phone scans the QR) before the parent plan's task 12 (bump 0.14.0) and any commit.
