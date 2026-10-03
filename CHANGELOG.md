# Changelog

All notable changes to this project are documented in this file.

Format adapted from [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/lang/fr/).

## [0.1.6] - 2026-10-03

### Added

- **Light / dark appearance**: *Settings → Appearance* now offers two
  themes, Light and Dark, applied instantly and persisted in the `theme`
  key of `config.json`. Default: dark.
- **The phone page follows it too**: `style.css` was rewritten on CSS
  variables with a light and a dark palette, `/api/info` reports the
  desktop choice, and a ☀/☾ button in the corner switches this device
  only. The local override is dropped on its own as soon as the PC theme
  changes, so the page never stays out of sync.

### Changed

- The whole desktop palette moved to theme resources (`Brush.*` in
  `App.axaml`), with a dedicated Light and Dark dictionary: the main
  window, the settings dialog and the message boxes resolve the same keys,
  so a surface can no longer keep a hard-coded colour that ignores the
  theme.
- The saved preference is applied before the main window is created, so
  the first frame is already in the right theme.
- The web page declares `color-scheme` and `theme-color` for both themes,
  so native widgets and the browser chrome follow the palette.

### Fixed

- **Random black / frozen page on the phone**: the TLS handshake used to
  run on the *listening* socket, i.e. inside the single accept loop. One
  client frozen mid-handshake (browser pre-connect abandoned when the
  phone locks, a Wi-Fi drop in the middle of the ClientHello, a port
  probe) stopped the server from accepting anything else, and every other
  client was left waiting on an unresponsive page. The handshake now
  happens in the worker thread that owns the connection and is bounded to
  10 s; the accept loop never waits on a client.
- The receive-folder quota scan no longer runs while holding the quota
  lock. The phone polls usage every 5 s, and a slow folder (large tree,
  OneDrive placeholders, antivirus) could previously block uploads and
  every other quota call for as long as the scan lasted.
- Listen backlog raised from 5 (the `http.server` default) to 128: a cold
  page load opens several connections at once and the default could drop
  them, which looks like a blank page.
- Idle connection timeout raised from 10 s to 30 s, so a short screen-off
  hiccup no longer kills an upload mid-transfer.
- Mobile page: every API request now carries a deadline (8–20 s) and
  repeated failures display *Server unreachable* instead of leaving the
  screen stuck on *Loading...*. A quota poll answered 401/403 (rotated
  token) now locks the session instead of keeping a dead page alive.
- Mobile page: the QR scanner no longer stacks `detect()` calls, which
  could starve the UI on a slow phone.
- Mobile page declares `color-scheme` and `theme-color`, so the
  background is deterministic while loading or when the browser shows its
  own error page.

### Removed

- **Update system**: startup check, *Settings → Updates → Check now*,
  in-place installer, `update.xml` manifest, release-workflow entry and
  the related documentation. The desktop application downloads and
  installs nothing.
- **9 fancy themes** (Neon, Midnight, Forest, Sunset, Monochrome, Rose,
  Amber, …) and the *System* option: only Light and Dark remain, and both
  language files dropped the unused names and descriptions.
- Debug log files (`theme.log`, `crash.log`, and their `.err`
  counterparts).

## [0.1.5] - 2026-09-28

### Changed

- **In-place updates**: the application now downloads a payload zip, verifies it, extracts it, and atomically replaces its own files before restarting. Configuration, sessions, certificates and the moved-files registry (`moves.json`) are preserved.
- **Elevation only when needed**: if the application folder is writable (typical user install), the update runs without UAC. For Program Files installs the worker requests elevation once; the restarted application drops back to standard rights.
- **Specific UAC decline message**: if the elevation prompt is dismissed, a clear message is shown and the current version keeps running.

## [0.1.4] - 2026-09-28

### Added

- **Put back**: a file added to the share folder with *Add files…* → *Move*
  now remembers where it came from and shows a **Put back** button on its
  row. One click (after a confirmation) moves it back to its original
  folder, even after a restart: the remembered origins are stored in
  `%LOCALAPPDATA%\OpenDrop\moves.json`. Files that are copied, renamed or
  deleted no longer point anywhere and their button disappears.
- **Open** button next to each folder line of the **FOLDERS** card
  (received and shared) to open that folder in File Explorer.
- **Double-click a file in the share folder to open it** (rename stays on
  the *Rename* button). A file that disappeared in the meantime is reported
  instead of failing silently.

## [0.1.3] - 2026-09-28

### Added

- **Share folder browser** in the main window: the right-hand panel lists
  every file of the share folder (name and size) with **Add files…**,
  **Rename**, **Delete** and **Refresh**, multiple selection, the folder path
  always visible, and a refresh whenever the window regains focus.
  - *Add files…* opens a file picker (several files at once) and then asks
    whether to **copy** or **move** them into the share folder: an existing
    file is never overwritten (a numbered name is used instead) and the
    result reports how many files were added, skipped or failed.
  - *Delete* confirms first and lists the files it removes from the disk;
    *Rename* refuses a name that is already used or invalid.
- **Close to tray (Windows)**: the close button now hides the window instead
  of stopping the server. The tray icon offers *Show* and *Quit*; the server
  keeps serving while the window is hidden, and *Quit* is the only way to
  really exit.
- **Download progress for updates**: while downloading, a dialog shows the
  percentage and the transferred / total size with a working **Cancel**, then
  a "verifying" state while the SHA-256 is checked. A failed, cancelled or
  corrupted download is reported instead of failing silently.
- **Manual update check** in *Settings → Updates* (**Check now**): reports
  "you are up to date" or offers the newer version, without restarting the
  app.
- `"check_updates": false` in `config.json` is now actually honoured
  (documented since 0.1.2 but not read yet).

### Changed

- Main window widened (880×720, minimum 760) with a two-column layout:
  connection information on the left, share folder on the right.
- Update downloads stream to disk instead of holding the whole file in
  memory, and the SHA-256 is computed off the UI thread.

### Fixed

- The update check follows HTTP redirects again: GitHub serves release assets
  with a `302`, so without redirects every download failed right away.
- The desktop app reads `update.xml` from this repository; the 0.1.2 build
  still pointed at the retired updates mirror and could not see newer
  releases.
- The left column no longer jumps down when the QR code appears at startup.
- The startup check runs only once, even when the window is hidden to the
  tray and shown again later.

## [0.1.2] - 2026-09-27

### Added

- **Automatic updates (Windows)**: at startup the desktop app reads a public
  `update.xml` manifest, and offers to download and install a newer release
  in one click. The setup is verified against a SHA-256 digest before it is
  launched. The installer reinstalls the application into `Program Files`
  only and **never touches** `%LOCALAPPDATA%` (config, session, certificate),
  so your settings survive an update. Opt out with `"check_updates": false`
  in `config.json`.
- **English/French language choice**, English everywhere by default:
  - full English rewrite of the code, comments, web interface and
    documentation; French kept as a second language
  - new `language` setting in `config.json` (`en` by default, `fr`
    optional); translated error messages on every API route, `/api/info`
    reports the active language
  - web interface picks the language from the server at startup
  - desktop app: language selector in *Settings* (English/French), applied
    live and persisted, English on first launch
  - Windows installer: *Application language* task (English/French) that
    seeds `config.json` on first install only
- Server: `format_size` and quota messages localized (`GB/MB` vs `Go/Mo`),
  banner and status lines in the selected language

### Fixed

- CI: `test_routes` failed intermittently on Windows with
  `PermissionError: [WinError 32]` while removing a file the server had just
  sent; the cleanup now retries briefly
- The update manifest now uses the real release asset name (`v` prefix) and
  embeds the SHA-256 of the setup; it is committed on `main` and served from
  this public repository, so the app needs no token
- Versions aligned on 0.1.2 (`pyproject.toml` was still 0.1.0)

## [0.1.1] - 2026-09-27

### Added

- Cross-platform desktop app: ported from WPF to **Avalonia** (.NET 8), one
  codebase for Windows (`win-x64`) and Linux (`linux-x64`), published as a
  single self-contained file
- **Windows installer** (Inno Setup): admin rights, installs into
  `Program Files (x86)`, Python dependencies installed locally from the
  bundled wheels (offline, `venv` in the install folder), start menu/desktop
  shortcuts, French/English interface, uninstaller that cleans up app data
  **without ever touching** the receive and share folders
- **Linux scripts** (`install.sh` / `uninstall.sh`): install into
  `/opt/opendrop` with a local `venv` and a menu entry
  (`opendrop-desktop`), equivalent uninstall that keeps the received and
  shared files
- Automated releases: on every `v*` tag, GitHub Actions generates
  `*-win-x64-setup.exe`, `*-win-x64.zip` and `*-linux-x64.tar.gz` (offline
  wheels included)
- App and menu icons generated by `tools/make_icon.py` (QR code)
- Linux launch: the QR code opens through `xdg-open` (and `open` on macOS)
  instead of being ignored (`os.startfile` only exists on Windows)
- README: *Linux (no desktop available)* section, *Downloads* section,
  cross-platform requirements, Linux badge
- `Operating System :: POSIX :: Linux` classifier in pyproject

### Changed

- `main.py` version string aligned with the release tag (`v0.1.1`)

### Fixed

- `server.pid`: the config folder didn't exist on the very first launch, the
  write failed silently, and an orphaned server could hold the port on the
  next start
- The desktop app now uses the `venv` created by the installer
  (`venv/Scripts/python.exe`, `venv/bin/python3`) before `python`/`python3`
  from PATH: dependencies guaranteed whatever the setup
- Desktop config path aligned with the Python server: `LOCALAPPDATA` read
  the way Python does, `~/.opendrop` fallback on Linux (desktop and server
  read the same `config.json` on both systems)
- Server launch on Linux: `python3` first (Debian/Kali have no `python`
  alias)

## [0.1.0] - 2026-09-27

First public release.

### Added

- Local HTTP(S) server: self-signed EC P-256 certificate (397 days), HTTPS
  enforced on every route, TLS 1.2+
- Session based on a random 32-character token, configurable expiration,
  manual rotation (`--rotate-token`, Reset button) or automatic, 6-character
  backup code (31^6, 5 tries/min/IP)
- Install-free web interface: *Send* / *Download* tabs, session lock, live
  quota bar (green/red)
- *Share* folder: files offered to other devices, one-click download
- Global receive quota: 507 rejection before writing, atomic reservations
  (simultaneous sends), negative values reset to 0 (unlimited)
- Safety limits: 10 GB per file, per-IP rate limits, sanitized file names,
  validated paths, no server path leaks, logs with no secrets
  (`token=***`, `code=***`)
- Windows desktop app (WPF, .NET 8): QR code, address, session code, quota,
  folders, settings, server start/stop
- Homegrown tests: 8 suites, 287 checks (299 with `--large`)
- GitHub Actions continuous integration (tests + desktop build) and
  Dependabot
