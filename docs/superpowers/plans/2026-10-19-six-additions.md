# Six Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the six approved additions - an E2E multi-browser suite, HTTP Range download resume, transfer guards (beforeunload + tab title), a PWA (manifest + service worker + icons), a desktop what's-new dialog, and release/CI infrastructure - with zero new product dependencies.

**Architecture:** Independent tasks over four subsystems (server, web, desktop, CI). Task 1 builds the E2E harness as a baseline against current behavior; every later feature task appends exactly one E2E scenario plus its own unit checks. All work stays uncommitted on `main` - the author orders every commit.

**Tech Stack:** Python 3.10+ (stdlib server, custom harness `python -m tests.<name>`), Playwright for Python (optional extra, test-only), vanilla JS web app, Avalonia/.NET 8 desktop, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-19-six-additions-design.md`

## Global Constraints

1. **NO git commit and NO git add at any point in this plan.** The author orders commits. Every task's last step is a suite run, never a commit. Verify with `git status --short` that only intended files changed.
2. **Product dependencies stay `qrcode[pil]` + `cryptography`** (pyproject `[project].dependencies`). Playwright goes only in a new `[project.optional-dependencies] e2e`. No `package.json` / `node_modules` may appear (the repo has none today).
3. **UI strings FR+EN** through the existing i18n: `t(key)` dict at `web/app.js:215` (keys like `success.title`), `Lang.T(key)` on desktop. Code and comments in English.
4. **PowerShell 5.1**: no `&&`; check `$LASTEXITCODE` after native commands; suites run as `python -m tests.<name>` from the repo root.
5. **Python 3.10 floor**: everything must run on 3.10 and 3.12 (CI matrix).
6. **Existing suites stay green**: 416 checks across 10 suites is the baseline. Per task, update only YOUR suite's own count strings in the docs (e.g. `33/33`); the grand totals are recomputed in Task 7.
7. **Test isolation**: never touch real config/receive/share folders - everything through `tests/conftest.py`'s `_WORKSPACE`. Generated big files live inside it (atexit-cleaned) and must never be staged; check `git status` after generating.
8. **Version stays 0.15.0**. New user-visible entries go under a new `## [Unreleased]` heading at the top of CHANGELOG.md (Task 2 creates the heading; later tasks append).

## Review Focus

1. **Range byte math off-by-one or a Content-Length that disagrees with the body** - a resumed download silently corrupts. Pinned by Task 2's reassembly test (`bytes=0-499` then `bytes=500-`, concatenated and byte-compared with the source) plus the single-byte edge `bytes=<size-1>-<size-1>`.
2. **An E2E suite that skips itself green** - browsers break in CI while the job stays green. Pinned by Task 1: the CI job sets `OPENDROP_E2E_REQUIRED=1`, and Step 4 proves locally that a broken-browser run exits non-zero with the flag and skips loudly without it.
3. **A stale service worker pinning users on an old UI** after a release (the updater cannot help). Pinned by Task 4: network-first shell with cache only as offline fallback (spec section 4), and an E2E reload check that the live server - not a cached copy - answers.
4. **`beforeunload` left armed after a cancel or a finish** - the user gets a "leave site?" prompt with nothing running. Pinned by Task 3's E2E: a synthetic `beforeunload` dispatched with `{cancelable: true}` has `defaultPrevented == true` mid-transfer, and `false` after both success and cancel. (The event MUST be created cancelable: a non-cancelable `Event` ignores `preventDefault`, and its `returnValue` is the legacy boolean `!canceled`, so reading `returnValue` on a plain event is always `True` and can never distinguish armed from idle - measured on all three engines.)
5. **What's-new looping every launch or blocking startup** when GitHub is unreachable. Pinned by Task 5's unit tests: `Decide` matrix (null baseline silent / equal silent / changed once), fetch failure returns null and no dialog opens, no exception escapes to App startup.

---

### Task 1: E2E harness + baseline scenarios + CI job

**Files:**
- Create: `tests/test_e2e.py`
- Modify: `pyproject.toml` (add `[project.optional-dependencies] e2e = ["playwright>=1.49"]`)
- Modify: `.github/workflows/tests.yml` (new `e2e` job after the `python` job)
- Modify: `README.md` (test section: add the `python -m tests.test_e2e` line with its real count)

**Interfaces:**
- Consumes: `tests/conftest.py` - `_start_server() -> (server, port, token)`, `_url(port, path, token)`, `dd`, `sd`, `SSL_CONTEXT`; web selectors `#file-input`, `#btn-cancel`, `#success-msg`, `#pair-token`, `#btn-pair` (all verified present).
- Produces (later tasks append, exact names):
  - `SCENARIOS: list[tuple[str, Callable, list[str]]]` - a 3-tuple per scenario (name, function, browser list) starting with `("upload_single_slice", ..., all 3)`, `("upload_multislice", ..., ["chromium", "firefox"])`, `("upload_cancel", ..., ["chromium", "firefox"])`; later tasks append their own tuples (`range_headers`, `title_beforeunload`, `pwa_manifest_sw` - all 3 browsers).
  - `BROWSERS = ["chromium", "firefox", "webkit"]`; one check per (scenario, browser); suite-style output `<N>/<N> passed, 0 failed`.
  - `_new_context(browser_name, port, token)` - browser context with `ignore_https_errors=True`, pairing through the overlay once per process (all contexts share 127.0.0.1).
  - `_hold_uploads(page, hold_pred) -> hold` - installs an in-page gate via `add_init_script` **before navigation** (the gate must be registered before `page.goto`): `XMLHttpRequest.open` stashes the URL, `send` QUEUES in-page any `/api/upload` send whose URL lacks `cancel=1` when `hold_pred(url)` is true - the request never leaves the page, the event loop keeps running, so UI interaction during the hold is fully available; `cancel=1` and all other traffic pass natively. No `page.route` anywhere: the driver's pause path must never touch an upload body. The handle exposes `settle()` (Python-side poll that lets `hold_pred`-false requests through promptly, since the predicate lives in Python) and `resume_all()` (in-page flush of the queued sends, per-entry try/except plus try/except around the evaluate). **Never `time.sleep` to open a window: in sync Playwright it blocks all Python-to-page interaction** - holding, not sleeping, is the deterministic window. Consumed by Task 1's cancel scenario (`hold_pred = lambda url: "offset=0" not in url`) and Task 3's scenario (`hold_pred = lambda url: True`, registered before `goto`).
  - Skip contract: loud `SKIPPED (<reason>)` + exit 0 without Playwright/browsers; with `OPENDROP_E2E_REQUIRED=1`, any problem exits non-zero.

- [ ] **Step 1: Declare and install the extra**

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
e2e = ["playwright>=1.49"]
```

Run: `python -m pip install -e ".[e2e]"` then `python -m playwright install chromium firefox webkit`
Expected: both exit 0 (the local `%LOCALAPPDATA%\ms-playwright` cache may already cover some browsers).

- [ ] **Step 2: Write `tests/test_e2e.py`**

Names and contracts to fix (body is the implementer's):

```python
_REQUIRED = os.environ.get("OPENDROP_E2E_REQUIRED") == "1"   # skip contract
# Scenario -> browsers matrix; webkit is excluded from the two-slice
# scenarios by a PRINTED, documented driver limitation (see below).
SCENARIOS = [("upload_single_slice", scenario_upload_single_slice, ["chromium", "firefox", "webkit"]),
             ("upload_multislice",  scenario_upload_multislice,  ["chromium", "firefox"]),
             ("upload_cancel",      scenario_upload_cancel,      ["chromium", "firefox"])]
BROWSERS = ["chromium", "firefox", "webkit"]

def _new_context(browser_name, port, token) -> BrowserContext
def _hold_uploads(page, hold_pred) -> hold   # hold.resume_all(); cancel=1 always passes
def scenario_upload_single_slice(page, server, port, token) -> None
def scenario_upload_multislice(page, server, port, token) -> None
def scenario_upload_cancel(page, server, port, token) -> None
```

- `upload_single_slice` (all 3 browsers): a 20 MB file in the conftest workspace -> `page.goto(_url(port, "/"))`; `page.locator("#file-input").set_input_files(path)`; `page.wait_for_selector("#success-msg", timeout=120_000)`; assert `sha256(os.path.join(dd, name)) == sha256(source)`; assert no `*.part` remains in `dd`.
- `upload_multislice` (chromium, firefox): the SAME lazily-generated 130 MB file (128 MiB + 2 MiB, `os.urandom`, generated ONCE per process and shared by both two-slice scenarios, inside the conftest workspace); upload; success card; SHA match; no `*.part`.
- `upload_cancel` (chromium, firefox): the same 130 MB file; gate installed before `goto`; `_hold_uploads(page, lambda url: "offset=0" not in url)` holds slice 2; `hold.settle()` lets slice 1 through; assert the staging `.part` reached 134217728 bytes (slice-1 size - the mechanical precondition that staging exists); `#btn-cancel` visible -> click; assert within 10 s: no `*.part` for this upload in `dd` and `#success-msg` never became visible; `hold.resume_all()` in a `finally` (a flush of an already-aborted send raises - swallow it).
- Known driver limitation, printed LOUDLY once at suite start (a `KNOWN_DRIVER_ISSUES` dict, one visible line, never a silent skip): Playwright-WebKit on Windows mis-streams a partial `Blob.slice` of a file-backed blob - it reads 46 bytes past the slice end (exactly the multipart epilogue length) and drops the closing boundary, so the server correctly answers 400 "Transfer interrupted or incomplete". Diagnosed 2026-10-19 with byte-level dumps: same product code green on chromium+firefox, and webkit green for whole-file uploads up to 128 MiB. Consequence: webkit is excluded ONLY from the two-slice scenarios and still runs `upload_single_slice`, so it is genuinely exercised. Re-include when Playwright fixes the driver (or if a real Safari run contradicts the diagnosis - that would make it a product bug and this ruling reopens).
- `main()`: import/launch failures -> print `SKIPPED (<reason>)` and exit 0, or exit 1 when `_REQUIRED`; with `_REQUIRED`, a scenario exception is a hard failure; without it, a scenario exception prints `FAILED` (exit 1) - skipping is only for missing tooling, never for a broken app.

- [ ] **Step 3: Run it locally**

Run: `python -m tests.test_e2e`
Expected: `7/7 passed, 0 failed` (3 scenarios, NON-rectangular matrix: `upload_single_slice` on all 3 browsers, the two two-slice scenarios on chromium+firefox only - R1/R2; later tasks grow the suite to its final 16/16); `git status --short` shows only intended files (generated data lives in the auto-cleaned conftest workspace).

- [ ] **Step 4: Prove the skip contract both ways**

Run: `$env:PLAYWRIGHT_BROWSERS_PATH = "$env:TEMP\empty-browsers"; python -m tests.test_e2e; "exit=$LASTEXITCODE"` -> `SKIPPED (...)`, exit 0.
Then: `$env:OPENDROP_E2E_REQUIRED = "1"; python -m tests.test_e2e; "exit=$LASTEXITCODE"` -> exit non-zero.
Then restore: `$env:PLAYWRIGHT_BROWSERS_PATH = $null; $env:OPENDROP_E2E_REQUIRED = $null`.

- [ ] **Step 5: Add the `e2e` job to tests.yml**

```yaml
  e2e:
    name: e2e (chromium firefox webkit)
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: python -m pip install -e ".[e2e]"
      - run: python -m playwright install --with-deps chromium firefox webkit
      - run: python -m tests.test_e2e
        env:
          OPENDROP_E2E_REQUIRED: "1"
```

- [ ] **Step 6: Regression + README**

Run: the 10 suite commands from README (test_security ... test_zip_web) -> all green; add `python -m tests.test_e2e   # N/N - multi-browser upload flows` after the test_zip_web line with the real count.
Leave everything uncommitted.

---

### Task 2: HTTP Range download resume

**Files:**
- Modify: `src/opendrop/server/server.py` - `_handle_download_file` (lines ~1194-1228); new module-level `_parse_range` near `_content_disposition` (~line 214)
- Modify: `tests/test_server.py` (current 33 checks)
- Modify: `tests/test_e2e.py` (append `("range_headers", ...)`)
- Modify: `CHANGELOG.md` (create `## [Unreleased]` + entry)
- Modify: `README.md` (test_server count string only; grand totals wait for Task 7)

**Interfaces:**
- Consumes: `_send_security_headers()`, `_content_disposition(filename)`, `CHUNK_SIZE` (64 KiB from `multipart.py`, already imported), conftest `sd`/`_url`/`_start_server`.
- Produces: `_parse_range(header: str | None, size: int) -> tuple[int, int] | str` -> inclusive `(start, end)` | `"ignore"` | `"unsatisfiable"`; the 200/206/416 response contract of spec section 2; e2e scenario name `range_headers`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_server.py` (helpers: `urlopen`/`http.client` per existing style; a generated ~1 MB file written into conftest `sd` so ranges cross many 64 KiB chunks):

1. plain download answers `Accept-Ranges: bytes` on 200;
2. `Range: bytes=0-` -> 206, `Content-Range: bytes 0-<n-1>/<n>`, body length n, body equal to source;
3. `Range: bytes=100-199` -> 206, exactly 100 bytes equal to `source[100:200]`;
4. `Range: bytes=-5` -> 206, body == last 5 bytes;
5. `Range: bytes=<size>-` (start past end) -> 416, `Content-Range: bytes */<size>`, empty body (catch `urllib.error.HTTPError`, assert `.headers` and length 0);
6. malformed `bytes=abc` and multi-range `bytes=0-1,4-5` -> 200 with the full body;
7. reassembly: `bytes=0-499` + `bytes=500-` concatenated == source (byte-compared);
8. single byte: `bytes=<size-1>-<size-1>` -> 206, 1 byte, equals `source[-1:]`.

In `tests/test_e2e.py`: `range_headers` scenario - write a 1 MB patterned file into `sd`, `page.request.get(_url(port, "/api/download/<name>"), headers={"Range": "bytes=10-19"})` -> status 206 + `content-range` header present + 10 bytes equal.

Run: `python -m tests.test_server` -> FAIL (404/200 where 206 expected). Run: `python -m tests.test_e2e` -> the range scenario FAILs.

- [ ] **Step 2: Implement `_parse_range` + `_handle_download_file`**

Behavior exactly per spec section 2. Streaming: `f.seek(start)`, loop reads `CHUNK_SIZE` capped at the bytes remaining for `(start, end)`; headers written before `end_headers()`; 416 sends no body. `Accept-Ranges: bytes` on every 200 and 206 response; 206 keeps `Content-Disposition` + security headers.

- [ ] **Step 3: Verify**

Run: `python -m tests.test_server` -> `40/40 passed, 0 failed` (or the real total). Run: `python -m tests.test_e2e` -> all scenarios x 3 browsers green.

- [ ] **Step 4: CHANGELOG + count string**

Create `## [Unreleased]` at the top of CHANGELOG.md with a `- **Downloads resume (HTTP Range):** ...` entry (FR-facing meaning, English text like the rest). Update README's `test_server 33/33` string to the real new number. Leave uncommitted.

---

### Task 3: Transfer guards (beforeunload + tab title)

**Files:**
- Modify: `web/app.js`
- Modify: `tests/test_e2e.py` (append `("title_beforeunload", ...)`)
- Modify: `CHANGELOG.md` (append under Unreleased)

**Interfaces:**
- Consumes: Task 1's `_hold_uploads(page, lambda url: True)` (install the gate BEFORE `page.goto` - it is an init script; it holds the FIRST and only slice of a small file - a hold works for a single-slice upload, no large file needed; `resume_all()` in a `finally`); selectors `#btn-cancel`, `#success-msg`; app.js landmarks: `makeUploadId` (line 1596), `sendCleanup` (1613), `sendSlice` (1646), `btnCancel` listener (2155); the zip pipeline (locate with `grep -n "AbortController" web/app.js`).
- Produces: module-level `transferActive` flag with `setTransferActive(on)`; `BASE_TITLE` captured once; one top-level `beforeunload` listener (checks the flag, `preventDefault` + `returnValue = "Transfer in progress"`); title format `` `${pct}% · OpenDrop` `` set alongside the progress bar text only while active, restored on every exit path; e2e scenario name `title_beforeunload`.

- [ ] **Step 1: Failing E2E scenario**

`title_beforeunload`, per browser (all 3 - it never relies on the two-slice path):
1. Install the gate with `_hold_uploads(page, lambda url: True)` BEFORE `page.goto`; then set a 20 MB file via `#file-input` - the single slice send is held in-page, the transfer is active, the event loop is free;
2. during the hold: `page.wait_for_function` until `document.title` matches `/% · OpenDrop$/` (RED before implementation);
3. synthetic probe `ret = page.evaluate("() => { const e = new Event('beforeunload', {cancelable: true}); window.dispatchEvent(e); return e.defaultPrevented; }")` -> assert `ret is true` (RED before implementation: no listener yet). MUST be cancelable + read `defaultPrevented` - a plain `Event`'s `returnValue` is the legacy boolean `!canceled` (always `True`) and `preventDefault` is a no-op on it, so `returnValue` can never discriminate (measured on chromium/firefox/webkit);
4. let the upload finish -> wait `#success-msg` -> assert `document.title == "OpenDrop"` and a fresh probe returns `false`;
5. cancel leg: fresh upload with the gate, probe returns `true`, click `#btn-cancel`, wait until title is back to base (<= 10 s), probe returns `false`.

Run: `python -m tests.test_e2e` -> RED on steps 2/3/5-armed probes (step 4's post-state may pass trivially - the armed probes are the red ones).

- [ ] **Step 2: Implement in `web/app.js`**

Register the listener once at module level; arm at real activity start only (zip pipeline entry + the caller of `makeUploadId`); disarm in `sendCleanup` (all paths: success, cancel, error) and in the zip finish/abort/cancel paths; a pre-send quota refusal never arms. Write the title next to the existing progress-bar update (grep the site that writes the bar percentage), using `BASE_TITLE` captured at load; restore it wherever `setTransferActive(false)` runs. Node check: `node --check web/app.js`.

- [ ] **Step 3: Verify**

Run: `python -m tests.test_e2e` -> all scenarios green; the suite total is now 13 checks (7 baseline + 3 range_headers + 3 title_beforeunload - the matrix is not rectangular: the two-slice scenarios run on chromium+firefox only). `node --check web/app.js` exit 0.

- [ ] **Step 4: CHANGELOG entry** under Unreleased. Leave uncommitted.

---

### Task 4: PWA (manifest + icons + service worker + server branches)

**Files:**
- Create: `web/manifest.webmanifest`, `web/sw.js`, `packaging/gen_web_icons.py`, `web/icons/icon-192.png`, `web/icons/icon-512.png`, `web/icons/icon-maskable-512.png`, `web/favicon.ico`
- Modify: `web/index.html` (manifest/icon/apple-touch links in `<head>`), `web/app.js` (feature-detected registration), `src/opendrop/server/server.py` (`do_GET` branch block ~462-476), `tests/test_routes.py`, `tests/test_e2e.py` (append `("pwa_manifest_sw", ...)`), `CHANGELOG.md`

**Interfaces:**
- Consumes: `_send_file(path, content_type)` (server.py ~425); test_routes' existing truth-table style (read it first); e2e runner; Pillow (`qrcode[pil]`, already installed).
- Produces: routes `/manifest.webmanifest` -> `application/manifest+json`, `/sw.js` -> `application/javascript`, `/icons/icon-192.png|icon-512.png|icon-maskable-512.png` -> `image/png`, `/favicon.ico` -> `image/x-icon` (hardcoded allowlist, everything else under `/icons/` -> 404); `web/sw.js` cache name `opendrop-shell-v1` with the network-first rule of spec section 4; e2e scenario `pwa_manifest_sw`.

- [ ] **Step 1: Failing tests**

`tests/test_routes.py` (follow its table style):
- GET `/manifest.webmanifest` -> 200, content-type `application/manifest+json`;
- GET `/sw.js` -> 200, content-type containing `javascript`;
- GET `/icons/icon-192.png` -> 200, `image/png`;
- GET `/icons/%2e%2e%2fstyle.css` -> 404 (allowlist).

E2E `pwa_manifest_sw`: `link[rel=manifest]` present; `page.request.get("/manifest.webmanifest")` content-type matches; after `page.reload()`, poll <= 5 s until `navigator.serviceWorker.getRegistration()` exists and is active.

Run: `python -m tests.test_routes` -> RED; `python -m tests.test_e2e` -> RED on the scenario.

- [ ] **Step 2: Generate the icons**

`python packaging/gen_web_icons.py` - Pillow draws the committed assets: 64x64-grid rounded square `#0f0f0f`, white envelope glyph (rectangles + polygon flap); outputs exactly the four files at 192/192, 512/512, maskable 512 (full-bleed square, glyph inside the safe circle), and a multi-size `favicon.ico`. Verify: `python -c "from PIL import Image; print(Image.open('web/icons/icon-192.png').size, Image.open('web/icons/icon-512.png').size)"` prints `(192, 192) (512, 512)`; `git status` lists the four assets.

- [ ] **Step 3: Implement**

- `manifest.webmanifest`: name/short_name "OpenDrop", `start_url: "/"`, `scope: "/"`, `display: "standalone"`, `theme_color`/`background_color` `#0f0f0f`, icons array (192, 512, maskable-512, `purpose: "maskable"`).
- `sw.js`: `SHELL = ["/", "/style.css", "/app.js", "/zip.js", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"]`; install -> `cache.addAll(SHELL)`; activate -> delete caches whose name differs from `opendrop-shell-v1`, `clients.claim()`; fetch -> return early (no interception) unless GET and pathname in SHELL; network-first (`fetch(req)` -> on success `cache.put(pathname, cloned response)` -> return response; on failure `caches.match(pathname)`). Never touch `/api/*`.
- Server branches (placed with the other static-asset branches in the existing if/elif chain - the chain is not alphabetically sorted and does not need to be), index links, `app.js` registration: `if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});`
- `node --check web/app.js web/sw.js`.

- [ ] **Step 4: Verify**

Run: `python -m tests.test_routes` -> green (real count); `python -m tests.test_e2e` -> 4 scenarios x 3 browsers green; `node --check` both files exit 0.

- [ ] **Step 5: CHANGELOG + README count string** for test_routes. Leave uncommitted.

---

### Task 5: Desktop what's-new dialog + `dotnet test` in CI

**Files:**
- Create: `desktop/OpenDrop/Services/WhatsNew.cs`, `desktop/OpenDrop.Tests/WhatsNewTests.cs`
- Modify: `desktop/OpenDrop/Strings.en.axaml` + `desktop/OpenDrop/Strings.fr.axaml` (key `WhatsNew.Title` - `Lang.cs` itself loads these resource files and holds no key/value pairs), the startup site (read `App.axaml.cs` / `MainWindow.axaml.cs` and hook AFTER the main window is shown), `.github/workflows/desktop.yml`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `UpdateService.CurrentVersion`, the `ApiHttp` client pattern (`UpdateService.cs:42-48`), `Msg.ShowAsync(owner, text, title)` (`Msg.cs:33`), `Lang.T(key)`, `FakeReleaseServer` (read its usage in `UpdateServiceCheckTests.cs`), the app's existing cross-platform settings store (read `MoveRegistry.cs` + the settings flow; do NOT introduce a registry-only store - linux-x64 must build).
- Produces (all `internal static` in `WhatsNew`):
  - `Decide(string? lastSeen, string current) -> (bool Show, string Persist)` - null -> `(false, current)`; equal -> `(false, current)`; different -> `(true, current)`;
  - `StripMarkdown(string md) -> string` - removes `**`, backticks, `[text](url)` -> `text`, keeps line breaks;
  - `FetchNotesAsync(string version, string? apiBase = null) -> Task<string?>` - GET `{apiBase or ApiBase}/releases/tags/v{version}`, parse `body` with System.Text.Json, any 404/network/parse failure -> `null`;
  - `MaybeShowAsync(Window owner)` - Decide + persist ALWAYS, fetch only when showing, on non-null `Msg.ShowAsync(owner, StripMarkdown(notes), $"OpenDrop {current} - {Lang.T("WhatsNew.Title")}")`; every exception swallowed;
  - Lang key `WhatsNew.Title`: FR `"Quoi de neuf"`, EN `"What's new"`;
  - desktop.yml step before publish: `dotnet test desktop/OpenDrop.Tests/OpenDrop.Tests.csproj -c Release`.

- [ ] **Step 1: Failing tests** (`WhatsNewTests.cs`, xUnit/NUnit style copied from the existing test files)

- `Decide`: `(null, "0.16.0")` -> show false, persist "0.16.0"; `("0.16.0", "0.16.0")` -> false/persist unchanged; `("0.15.0", "0.16.0")` -> true/persist "0.16.0".
- `StripMarkdown`: `"**A** and [b](http://x/y) and \`c\`"` -> `"A and b and c"` (multi-line input keeps its line breaks).
- `FetchNotesAsync`: against `FakeReleaseServer` - 200 body returned; 404 -> null; unreachable base (`http://127.0.0.1:<closed port>`) -> null, no throw.

Run: `dotnet test desktop/OpenDrop.Tests/OpenDrop.Tests.csproj` -> FAIL (type missing).

- [ ] **Step 2: Implement `WhatsNew.cs` + Lang key**

- [ ] **Step 3: Wire startup** - after the main window shows: `_ = WhatsNew.MaybeShowAsync(window);` (fire-and-forget, never blocking). Persist happens on every run (baseline silently established on first launch).

- [ ] **Step 4: Verify**

Run: `dotnet test desktop/OpenDrop.Tests/OpenDrop.Tests.csproj` -> all green; `dotnet build desktop/OpenDrop/OpenDrop.csproj` -> 0 errors.

- [ ] **Step 5: desktop.yml** gains the `dotnet test` step (before the publish step, after setup-dotnet).

- [ ] **Step 6: CHANGELOG entry.** Leave uncommitted.

---

### Task 6: Release / CI infrastructure

**Files:**
- Create: `.github/workflows/codeql.yml`, `tests/screenshots.py`
- Modify: `.github/workflows/release.yml` (notes extraction in EVERY `gh release create` occurrence - `grep -n "gh release create" .github/workflows/release.yml`; new `screenshots` job), `CHANGELOG.md`
- Modify: `.gitignore` only if `dist/` is not already ignored (check with `git check-ignore dist`)

**Interfaces:**
- Consumes: conftest `_start_server(**kwargs)` forwarding `language=`/`theme=` to `create_server` (params exist, `server.py:1236-1237`); the e2e skip pattern (copy it, env var `OPENDROP_SHOTS_REQUIRED`); release.yml's release-gate loop (lines 76-81) and `gh release upload` (line 82).
- Produces: `python -m tests.screenshots` (name has no `test_` prefix - never joins a suite loop) writing `dist/OpenDrop-<ref>-<fr|en>-<dark|light>.png` (ref from `GITHUB_REF_NAME`, fallback `dev`); codeql.yml for `[python, javascript]`; release notes = the CHANGELOG section body passed `--notes-file` at creation only.

- [ ] **Step 1: codeql.yml**

Standard CodeQL flow pinned to this repo's conventions: `on: push: branches: [main]`, `pull_request`, `schedule: cron "0 3 * * 1"`; `permissions: security-events: write, contents: read`; one job with `strategy.matrix.language: [python, javascript]`; steps `checkout@v7`, `github/codeql-action/init@v3` with `languages: ${{ matrix.language }}`, `autobuild@v3`, `analyze@v3`.

- [ ] **Step 2: notes extraction, verified locally**

Bash inside release.yml (runs under `shell: bash` in the attach step), before the gate loop:

```bash
ver="${GITHUB_REF_NAME#v}"
notes=$(awk -v v="$ver" '$0 ~ "^## \\[" v "\\]" {f=1; next} /^## \[/ {f=0} f' CHANGELOG.md)
if [ -n "$notes" ]; then printf '%s\n' "$notes" > release-notes.md; fi
```

and the create line gains `${notes:+--notes-file release-notes.md}` next to `--generate-notes`. gh semantics (verified in the gh manual): the file's contents are PREPENDED to the auto-generated notes, so a section that exists always LEADS the release body while the auto summary (PR list, contributors) still follows; a tag without a section keeps pure `--generate-notes`. Existing releases are never edited.

Local proof (the awk must be correct before it ships):
Run: `bash -c "awk -v v=\"0.15.0\" '\$0 ~ \"^## \\\\\[\" v \"\\\\\]\" {f=1; next} /^## \[/ {f=0} f' CHANGELOG.md"` -> run it with `GITHUB_REF_NAME=v0.15.0` against the VERBATIM release.yml snippet (write the exact shipped bytes to a .sh file and run Git's bash, `C:\Program Files\Git\bin\bash.exe` - the original one-liner form is un-runnable from PS 5.1: native-argument quoting mangles the awk program, evidenced twice). Expected: first non-empty line `### Added` (the section's `###` subheadings are kept and render fine as release notes; the first BULLET is `- **Live zip progress...`), last entry = the 416-checks bullet, and slice-equality with the `[0.15.0]` body holds - nothing from `[0.14.0]` appears.

- [ ] **Step 3: `tests/screenshots.py`**

Copy `test_e2e`'s skip skeleton (env `OPENDROP_SHOTS_REQUIRED`); for `(lang, theme)` in `("fr","dark"), ("fr","light"), ("en","dark"), ("en","light")`: `_start_server(language=..., theme=...)` on a fresh port, new browser context (`ignore_https_errors`), pair via `#pair-token`/`#btn-pair`, `page.goto(_url(port,"/"))`, wait for `.logo`, then TWO bounded gates before the shot (measured races without them - ruling R6a): (a) `document.documentElement.lang` matches the requested lang AND `data-theme` matches the requested theme (GET / serves STATIC index.html; app.js starts `LANG="en"` and applies lang/theme only on the async `/api/info` answer - without this gate fr-dark and en-dark came out byte-identical), (b) computed `#app` opacity === `"1"` (style.css's `rise-in 0.55s` entrance starts at opacity 0 and Playwright's "visible" ignores opacity - without this gate the shots were bare backdrop), then `page.screenshot(path=..., full_page=False)` at 1280x800 into `dist/`. Run locally: `python -m tests.screenshots` -> four PNGs; `git check-ignore dist` decides the `.gitignore` line.

- [ ] **Step 4: screenshots job in release.yml**

ubuntu-latest, checkout, setup-python 3.12, `pip install -e ".[e2e]"`, `python -m playwright install --with-deps chromium`, `python -m tests.screenshots` with `OPENDROP_SHOTS_REQUIRED: "1"`, then the same gate + `gh release upload` block for `dist/*.png`.

- [ ] **Step 5: Validate both workflows**

Run: `npx --yes js-yaml .github/workflows/codeql.yml` and `npx --yes js-yaml .github/workflows/release.yml` -> exit 0 (YAML parses).

- [ ] **Step 6: CHANGELOG infra line** under Unreleased. Leave uncommitted.

---

### Task 7: Consolidation + full verification gate

**Files:**
- Modify: `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md` (grand totals only, never the historical `[0.15.0]` entry); `tests/test_e2e.py` comment-only (the R4c harness note, Step 2b)

- [ ] **Step 1: Run everything and record counts**

Run in order, capture each summary line: the 10 suites (`test_security test_routes test_paths test_quota test_sessions test_tls test_server test_beta test_devices test_zip_web`), `python -m tests.test_e2e`, `python -m tests.test_beta --large`, `dotnet test desktop/OpenDrop.Tests/OpenDrop.Tests.csproj`, `dotnet build desktop/OpenDrop/OpenDrop.csproj`, `node --check web/app.js`, `node --check web/sw.js`.
Expected: every one green (beta --large: 75/75; dotnet: 0 errors).

- [ ] **Step 2: Recompute grand totals**

Run: `grep -rn "416" README.md SECURITY.md CONTRIBUTING.md CHANGELOG.md` and `grep -rn "/4[0-9][0-9]" README.md` -> update the suites total and per-suite numbers to the fresh counts everywhere EXCEPT the `## [0.15.0]` section (history stays). The `## [Unreleased]` section states the new totals (e.g. "11 suites, N checks").

- [ ] **Step 2b: R4c harness note** — in `tests/test_e2e.py`, add ONE English comment block next to the wait/probe helpers recording ruling R4c: this Playwright build does NOT await an async predicate passed to `page.wait_for_function` (a Promise object is truthy, so `async () => false` passes in 0 ms); async waits must therefore be Python-side polls via `page.evaluate` (which DOES await). Comment only - zero behavior change; the suite must still print `16/16` afterwards.

- [ ] **Step 3: Final tree audit**

Run: `git status --short` -> only intended files (new tests/workflows/web assets/desktop files + modified docs); no `dist/`, no generated data, no `package.json`/`node_modules`; `.playwright-cli/` remains untracked-and-unadded.

- [ ] **Step 4: Report**

Full green summary for the author; explicitly state that nothing is committed and the tree is ready for the commit order. NO commit.
