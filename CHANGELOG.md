# Changelog

All notable changes to this project are documented in this file.

Format adapted from [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/lang/fr/).

## [0.9.0] - 2026-10-07

### Added

- **Tabbed Settings window**: the single scrolling form is replaced by a
  sidebar of six tabs (General, Storage, Security, Network, Appearance,
  Updates) built from styled `RadioButton`s plus a content area that
  shows only the selected page. The window keeps its fixed height, every
  page scrolls on its own, and the controls and save logic are exactly
  the ones the old form used.
- **Reserved palette keys** in both themes: `Brush.Surface2`,
  `Brush.ShadowColor`, `Brush.Glow`, `Brush.GlowSoft`, `Brush.IconFar`,
  `Brush.IconNear` and `Brush.IconHover`. Nothing reads them yet - they
  are the hooks the depth and proximity effects will use, so they exist
  (with quiet values) before anything depends on them.
- `src/opendrop/themes.py`: the theme catalogue (`THEMES`, plus
  `normalize_theme`) now has a single home on the server side.

### Changed

- `ThemeManager` exposes the themes as an extensible list of
  `ThemeDefinition` (config id + translation key) instead of two
  constants, and the settings combo box is built from that list in the
  current language instead of hardcoded `ComboBoxItem`s.
- `main.py` and `server.py` validate the theme through `opendrop.themes`
  instead of a hardcoded `("light", "dark")`; `config.py` takes its
  default from the same module.
- The web page validates `data-theme` against the same list
  (`VALID_THEMES` in `app.js`); `style.css` still ships only the light
  and dark blocks.
- `tests/test_server.py`: `/api/info` must publish a known theme and an
  unknown theme in the config falls back to `dark` (16/16).

## [0.8.1] - 2026-10-04

### Changed

- **New app icon**: the window, tray and installer icon on Windows and the
  menu icon on Linux now use the project logo instead of a generated QR
  code pointing at the repository. `tools/make_icon.py` reads
  `docs/screenshots/OpenDrop_Logo.webp` and writes `app.ico` (seven sizes,
  16 → 256) plus `packaging/linux/opendrop.png`; the unused
  `desktop/OpenDrop/app.png` by-product is dropped.
- Dependencies: `QRCoder` 1.4.3 → 1.8.0 (desktop),
  `actions/upload-artifact` 4 → 7 (workflow).

## [0.8.0] - 2026-10-04

### Added

- **Discord button** in the desktop title bar: it opens the OpenDrop
  server invite (`https://discord.gg/vREBPZuvhV`) in the default browser,
  with a tooltip translated in both languages (123 → 126 strings per
  language). The README gained a Discord badge and a *Community* section,
  and `CONTRIBUTING.md` sends questions there.
- **Updates can be cancelled and resumed**: the progress window has a
  *Cancel* button (closing the window cancels as well), and an interrupted
  download picks up where it stopped with an HTTP `Range: bytes=N-`
  request instead of starting over — a `416`, or a response that ignores
  the range, purges the cached file and downloads it again from scratch.
- **A release without a published `sha256:` digest is refused** before any
  transfer (`Up.NoDigest`): the updater never falls back to an unverified
  download, whatever the GitHub response looks like.
- The Windows setup helper reports its exit code back to the app, so a
  failed installation is surfaced at the next start (`Up.InstallFailed`)
  instead of staying silent.
- README: *FAQ*, *Troubleshooting*, *Known limitations* and *Release
  process* sections.

### Fixed

- **An older setup could be installed over a newer version**: the Windows
  installer now compares the installed release and refuses to downgrade,
  instead of silently replacing a newer build by an older one.
- The token countdown was still in English and clipped on its left edge
  in French.

### Changed

- Installer message boxes are skipped in silent mode (they used to block
  `/VERYSILENT` forever) and the setup reports `1`/`2`/`3` instead of a
  uniform `0`, which made every failure look like a success.
- Dead `Console.WriteLine` output removed from the desktop entry point and
  the Python server; test identifiers renamed to English.
- Dependabot watches the desktop project (NuGet) alongside Python, and the
  private checklist is now ignored.
- Release numbers follow semantic versioning (the `0.1.x` line became
  `0.2.0` … `0.7.0`).

## [0.7.0] - 2026-10-04

### Added

- **Automatic updates**: OpenDrop now looks for a newer release when it
  starts (three seconds after the window is up, never before, and
  without a word if GitHub cannot be reached) and from
  *Settings → Updates*, which also shows the running version and the
  outcome of the check.
  - Windows: the matching `setup.exe` is downloaded, checked against the
    SHA-256 digest GitHub publishes with the asset, and handed to a
    detached helper that waits for OpenDrop to exit and runs it with
    `/VERYSILENT`. Same `AppId`, so the new version replaces the old one
    in place: a single entry in *Programs and features*, the previous
    installation is overwritten rather than uninstalled (an uninstaller
    would delete the settings), and `%LOCALAPPDATA%\OpenDrop` is outside
    `{app}` so the configuration survives untouched.
  - Linux: the `tar.gz` is verified the same way, then applied either in
    place (archive unpacked by hand: the running binary is renamed first
    to dodge `ETXTBSY`, dependencies are refreshed from the bundled
    wheels, no network needed) or through the bundled `install.sh` run
    with `pkexec` when the installation lives in `/opt`.
  - The new process starts only once the old one is gone, through a
    helper waiting on its PID: the single-instance lock would otherwise
    make it hand the signal back and quit.
  - *Skip this version* is remembered in `config.json` (`skip_version`)
    and silenced for that version only; *Later* keeps the offer for the
    next start. Drafts, pre-releases and releases without a `vX.Y.Z` tag
    are never offered.
- The new dialogue, the progress bar and the *Updates* section are
  translated in both languages (105 → 123 strings per language).

### Fixed

- **Installing over a running copy could fail with "Text file busy"**:
  `install.sh` now moves the running binary aside before replacing it,
  so an update can be applied while the previous version is still up.

## [0.6.1] - 2026-10-03

### Fixed

- **The port crept up on every reset (Linux)**: restarting the server
  moved it from 8080 to 8081, then 8082 and so on, while `config.json`
  still said 8080 — a manually entered port never stayed either. The
  server closes every response, so its own connections linger in
  `TIME_WAIT` on that port for ~60 s after a restart; the "is this port
  free?" probe bound *without* `SO_REUSEADDR` and read those leftovers as
  another program holding the port, so `find_available_port` stepped to
  the next one. Windows was unaffected, because a plain bind succeeds
  over `TIME_WAIT` there. The probe now sets `SO_REUSEADDR` on POSIX: it
  ignores the leftovers but still refuses to bind while a socket is
  really listening (that needs `SO_REUSEPORT`), which is the case it has
  to detect — and it now matches what the real server does
  (`allow_reuse_address`), so probe and server finally agree.

### Added

- Three port-probe checks in `tests.test_server` (11 → 14): `TIME_WAIT`
  leftovers do not hide a port, the preferred port survives a restart,
  a live listener is still reported as busy.

## [0.6.0] - 2026-10-03

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
- A rejected POST could lose its own status code: the server answered
  while the request body was still queued, the kernel then reset the
  connection, and the client saw a cut connection instead of the
  400/429/507 (it showed up as `RemoteDisconnected` in the Linux CI).
  The unread body is now absorbed first, bounded in size and time, and
  only until the upload parser starts consuming it.
- The TLS connection is released in the handler instead of by the garbage
  collector: `wrap_socket()` hands the descriptor to a new object, so the
  framework's `shutdown_request()` could no longer close anything and the
  response used to depend on when the collector showed up. A handshake
  that fails is closed on the spot as well.
- The theme preference now goes through the same config path as every
  other component: `ThemeManager` resolved the shell folder instead of the
  `LOCALAPPDATA` environment variable, so a redirected profile (tests,
  sandboxed runs) saw its real `config.json` rewritten while the rest of
  the app wrote to the redirected one.
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

## [0.5.1] - 2026-09-28

### Changed

- **In-place updates**: the application now downloads a payload zip, verifies it, extracts it, and atomically replaces its own files before restarting. Configuration, sessions, certificates and the moved-files registry (`moves.json`) are preserved.
- **Elevation only when needed**: if the application folder is writable (typical user install), the update runs without UAC. For Program Files installs the worker requests elevation once; the restarted application drops back to standard rights.
- **Specific UAC decline message**: if the elevation prompt is dismissed, a clear message is shown and the current version keeps running.

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

## [0.3.0] - 2026-09-27

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
- Versions aligned on 0.3.0 (`pyproject.toml` was still 0.1.0)

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

### Changed

- `main.py` version string aligned with the release tag (`v0.2.0`)

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
