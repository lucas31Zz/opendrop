# Changelog

All notable changes to this project are documented in this file.

Format adapted from [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/lang/fr/).

## [0.5.0] - 2026-09-28

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

## [0.4.0] - 2026-09-28

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
  (documented since 0.3.0 but not read yet).

### Changed

- Main window widened (880×720, minimum 760) with a two-column layout:
  connection information on the left, share folder on the right.
- Update downloads stream to disk instead of holding the whole file in
  memory, and the SHA-256 is computed off the UI thread.

### Fixed

- The update check follows HTTP redirects again: GitHub serves release assets
  with a `302`, so without redirects every download failed right away.
- The desktop app reads `update.xml` from this repository; the 0.3.0 build
  still pointed at the retired updates mirror and could not see newer
  releases.
- The left column no longer jumps down when the QR code appears at startup.
- The startup check runs only once, even when the window is hidden to the
  tray and shown again later.


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

### Fixed

- CI: `test_routes` failed intermittently on Windows with
  `PermissionError: [WinError 32]` while removing a file the server had just
  sent; the cleanup now retries briefly
- The update manifest now uses the real release asset name (`v` prefix) and
  embeds the SHA-256 of the setup; it is committed on `main` and served from
  this public repository, so the app needs no token
- Versions aligned on 0.3.0 (`pyproject.toml` was still 0.1.0)

## [0.2.0] - 2026-09-27

### Added

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

### Changed

- `main.py` version string aligned with the release tag (`v0.2.0`)

## [0.2.0] - 2026-09-27

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
