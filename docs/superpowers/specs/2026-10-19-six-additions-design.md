# Six additions - design (2026-10-19)

Approved by the author after brainstorming ("les 6 me vont, vas y").
Six additions, each standing alone; the E2E suite is the only shared
element and grows one scenario per addition as it lands.

## 1. E2E multi-browser suite (the author's manual Zen test, automated)

- `tests/test_e2e.py`, run as `python -m tests.test_e2e`, using the
  Python Playwright binding declared ONLY in a new
  `[project.optional-dependencies] e2e` extra - zero product
  dependencies (product deps stay `qrcode[pil]` + `cryptography`).
- Browsers: chromium, firefox, webkit - the "works in every browser"
  claim becomes executable.
- Real server from `tests/conftest.py` (`_start_server`), HTTPS
  self-signed, contexts created with `ignore_https_errors=True`.
  The browser pairs through the real overlay (`#pair-token` +
  `#btn-pair`); a paired IP opens the app unlocked.
- Baseline scenarios: (a) `upload_single_slice` - a 20 MB upload on
  all three browsers reaches the success card, SHA-256 matches, no
  `*.part` left; (b) `upload_multislice` - a 130 MB file (128 MiB +
  2 MiB = two slices, so the chunked path is exercised) on
  chromium + firefox, same assertions; (c) `upload_cancel` - the same
  two-slice file with slice 2 HELD by an in-page gate installed
  before navigation (holding, never sleeping: in sync Playwright a
  sleep inside a route handler blocks all page interaction), then
  `#btn-cancel` clicked - the staging file disappears and the
  success card never shows.
- Known driver limitation (printed loudly at suite start, never a
  silent skip): Playwright-WebKit on Windows mis-streams a partial
  `Blob.slice` of a file-backed blob (46-byte overrun, closing
  boundary lost -> the server rightly answers 400 incomplete), so
  webkit runs only the single-slice scenario. Diagnosed 2026-10-19
  with byte-level dumps; the product code is green on chromium and
  firefox and webkit is green up to whole-file 128 MiB uploads.
  Re-include webkit in the two-slice scenarios when the driver is
  fixed, or immediately if a real Safari run contradicts the
  diagnosis (that would make it a product bug).
- Skip contract: if Playwright or the browsers are missing, print a
  loud `SKIPPED (reason)` line and exit 0 - unless
  `OPENDROP_E2E_REQUIRED=1` (set in CI), where any skip or launch
  failure is a red suite.
- CI: one `e2e` job in tests.yml (ubuntu-latest, Python 3.12). The
  existing 10-suite matrix loop is untouched.

## 2. Download resume (HTTP Range)

- `_handle_download_file` (server.py) answers `Accept-Ranges: bytes`
  on every 200 and 206 response (RFC 9110 permits omitting it on the
  416 error response).
- Single ranges only: `bytes=a-b` (inclusive), `bytes=a-`, `bytes=-n`.
  Valid -> 206 with `Content-Range: bytes a-b/size` and
  `Content-Length = b-a+1`; Content-Disposition and the security
  headers stay on the 206.
- Start past the end of the file, or a zero-length suffix -> 416 with
  `Content-Range: bytes */size` and an empty body.
- Malformed syntax and multi-range headers -> ignore, plain 200
  (RFC 9110 lets a server ignore a Range it does not want).
- Parser: `_parse_range(header: str | None, size: int) -> tuple[int, int] | str`
  returning an inclusive `(start, end)` tuple, `"ignore"`, or
  `"unsatisfiable"` - a pure function, testable without a server.

## 3. Transfer guards (web)

- While a zip or a send is actually in flight, `beforeunload` calls
  `preventDefault` and sets `returnValue` (constant message
  "Transfer in progress"); the listener is registered once at module
  level and checks a single `transferActive` flag.
- The tab title shows `<pct>% · OpenDrop` during the flight
  (language-neutral format on purpose) and is restored to the captured
  base title on EVERY exit path: success, cancel, zip cancel, errors.
- Arming happens at real activity start only (zip pipeline entry, the
  caller of `makeUploadId`); disarming in `sendCleanup` and the zip
  abort/finish paths. A quota refusal before any activity never arms.
- No Notification API: the permission prompt is not worth the UI.

## 4. PWA

- `web/manifest.webmanifest`: standalone display, `#0f0f0f`
  theme/background, icons 192 + 512 + maskable 512.
- Icons generated once with Pillow (already a product dep via
  `qrcode[pil]`) by a committed generator `packaging/gen_web_icons.py`
  writing `web/icons/icon-192.png`, `web/icons/icon-512.png`,
  `web/icons/icon-maskable-512.png`, `web/favicon.ico`; the generated
  files are the committed assets.
- `web/sw.js`: NETWORK-FIRST for the shell (navigation + an exact
  allowlist of static paths), cache only as an offline fallback, old
  caches deleted on activate - a stale UI after a release is the
  classic PWA bug and is designed out. `/api/**` (including
  `/api/download` and its Range responses) is never intercepted.
- Server: explicit branches for `/manifest.webmanifest`
  (`application/manifest+json`), `/sw.js` (`application/javascript`),
  `/icons/<allowlist>` (image/png), `/favicon.ico` - hardcoded
  allowlist, no new traversal surface.
- `index.html` gains manifest + icon links; `app.js` registers the
  service worker feature-detected and failure-silent.

## 5. What's-new dialog (desktop)

- Startup, after the main window is up, compares the stored
  `LastWhatsNewVersion` with `UpdateService.CurrentVersion`:
  first run (no stored value) = silent baseline; equal = silent;
  different = show once, then persist the current version.
- Notes: GET `/releases/tags/v<version>` on a static client built
  with UpdateService's ApiHttp pattern (same 20 s timeout/UA/Accept,
  dedicated instance - product-invisible), `System.Text.Json` `body` field - no new
  dependency; markdown stripped by a small regex (`**`, backticks,
  `[text](url)` -> `text`); fetch failure or missing release = no
  dialog, never an exception reaching startup.
- Display: `Msg.ShowAsync`, title from `Lang.T("WhatsNew.Title")`
  (FR "Quoi de neuf", EN "What's new") + the version.
- Storage: the cross-platform settings store the desktop app ALREADY
  uses (read MoveRegistry.cs and the settings flow first) - no new
  store, no registry-only solution (the app also builds linux-x64).
- `dotnet test` gains a CI step (desktop.yml runs no tests today).

## 6. Release / CI infrastructure

- CodeQL workflow: python + javascript, push to main + PR + weekly.
- release.yml: extract the `## [<version>]` section of CHANGELOG.md
  and pass it `--notes-file` when the release is CREATED (gh prepends
  the file's contents to its auto-generated notes, so the section
  always leads the body; existing release bodies are never
  overwritten; no section -> the current `--generate-notes` output
  alone).
- Release screenshots: `tests/screenshots.py` (no `test_` prefix, so
  it never joins the suite loop) starts servers with the
  `language=`/`theme=` create_server kwargs, pairs, captures
  FR/EN x dark/light of the Send page into `dist/`, uploaded to the
  release by a small ubuntu job.
- desktop.yml: `dotnet test` step before publish.

## Out of scope

Folder drag-drop E2E (the zip engine already has 47 checks in
test_zip_web), multi-range refinement, Notification API, i18n of the
tab-title format, version bump (stays 0.15.0 until the author orders
the next release).
