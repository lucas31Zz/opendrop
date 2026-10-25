# OpenDrop

![OpenDrop logo](docs/screenshots/OpenDrop_Logo.webp)

> Direct file transfers on your local network: launch OpenDrop, scan the
> QR code, send. No account, no cloud, no install on your phone.

[![Tests](https://github.com/lucas31Zz/opendrop/actions/workflows/tests.yml/badge.svg)](https://github.com/lucas31Zz/opendrop/actions/workflows/tests.yml)
[![Latest release](https://img.shields.io/github/v/release/lucas31Zz/opendrop)](https://github.com/lucas31Zz/opendrop/releases/latest)
[![MIT License](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Windows](https://img.shields.io/badge/bureau-Windows%20%2B%20Linux-lightgrey.svg)](desktop/src-tauri/tauri.conf.json)
[![Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](.github/workflows/tests.yml)
[![Discord](https://img.shields.io/badge/Discord-server-5865F2?logo=discord&logoColor=white)](https://discord.gg/vREBPZuvhV)


```text
PC (OpenDrop)  --->  QR CODE  --->  phone / tablet / another PC
                     |                    |
                  6-character code        v
                                    web interface (HTTPS)
                                             |
                                    Send / Download
                                             |
                                    direct transfer
                                        over the LAN
```

The file never leaves your local network: OpenDrop is a peer-to-peer HTTP(S)
server running on your machine, nothing goes over the internet.

---

## What it does

- **HTTPS required**: self-signed certificate generated on first launch
- **Token-based sessions**: 32 random characters, configurable expiration,
  manual rotation (Reset button) or automatic (timer), plus a 6-character
  backup code to unlock a device
- **Web interface** in the browser, no install needed: *Send* and
  *Download* tabs, quota bar up top, session lock; several files per
  send, and whole folders zipped in the browser on their way
- **Share folder**: files dropped in there are offered to other devices,
  downloadable in one click
- **A workspace in the browser**: the *Download* tab searches, switches
  between one, two or four files per row, and sorts files into virtual
  folders that live on the device only (drag them in, or *Move to…* on a
  phone - the share folder on the PC is never modified); a selection
  downloads as a single zip
- **Global receive quota** (optional): rejected with a 507 before anything
  is written, live indicator (green under the limit, red once reached)
- **Safety limits**: storage quota (the real ceiling), per-IP rate limits,
  sanitized file names, validated paths, no server path leaks
- **Desktop app for Windows and Linux** (Tauri 2 + React): system tray,
  one window per machine, integrated title bar, QR code, address,
  session code, quota, folders, settings, one-click server start/stop
- **Shared files from the app**: drag files or folders from the Explorer
  onto the *Shared files* panel and they are copied into the share folder;
  select like the Explorer (rubber band on empty space, Ctrl/Shift,
  Ctrl+A), rename several at once (`report`, `report (2)`...) and delete
  them with the Delete key
- **English and French**: English is the default everywhere (installer,
  desktop app, web interface, server messages); switch the app to French
  in *Settings* (or pick it in the Windows installer)
- **Light or dark**: one theme switch in *Settings* covers the desktop
  window, the dialogs and the phone page; the web interface follows it and
  keeps its own ☀/☾ button for this device
- **Liquid Glass**: translucent layers, tinted blurs and accent
  gradients over a slow aurora, dark by default with a full light theme;
  tab indicators spring, cards settle in, and every animation switches
  off when the OS asks for reduced motion (touch devices skip the
  background work entirely)

---

## Screenshots

### Desktop app

The main window: QR code, server address, session code, receive quota,
folders, and the Start/Stop/Settings buttons along the bottom.

![Desktop app - dark](docs/screenshots/desktop.png)

The same window in the light theme (*Settings > Appearance*):

![Desktop app - light](docs/screenshots/desktop-light.png)

The left column scrolls; here it is from top to bottom (QR code, address,
session code, token refresh, folders, quota):

![Desktop app - scrollable column](docs/screenshots/desktop-scroll.png)

### Settings

Configure folders, port, storage quota, token rotation, appearance
(light/dark) and language. A sidebar lists the six tabs (General,
Storage, Security, Network, Appearance, Updates) and only the selected
page is shown, so the window keeps a fixed size; pages taller than the
window scroll on their own:

| Dark | Light |
|---|---|
| ![Settings - dark](docs/screenshots/settings-scroll.png) | ![Settings - light](docs/screenshots/settings-light-scroll.png) |

### Web interface

Send files and download from the Share folder directly in your browser —
no install needed, in the same light/dark theme as the app.

**Send tab:**

| Dark | Light |
|---|---|
| ![Web interface - Send (dark)](docs/screenshots/web-send-dark.png) | ![Web interface - Send (light)](docs/screenshots/web-send-light.png) |

**Download tab:**

| Dark | Light |
|---|---|
| ![Web interface - Download (dark)](docs/screenshots/web-download-dark.png) | ![Web interface - Download (light)](docs/screenshots/web-download-light.png) |

**Settings panel** (gear, top right):

| Dark | Light |
|---|---|
| ![Web interface - Settings (dark)](docs/screenshots/web-settings-dark.png) | ![Web interface - Settings (light)](docs/screenshots/web-settings-light.png) |

---

## Requirements

- Python **3.10+** (developed and tested on 3.12) — Windows **or Linux**
  (tests run in CI on both); required at runtime by the desktop app too
- Only needed to build the desktop app from source: **Node 20+** and
  **Rust** (install it with [rustup](https://rustup.rs)) — no .NET
  required any more
- Linux, only to *run* the desktop app:
  `sudo apt install libwebkit2gtk-4.1-0 libayatana-appindicator3-1`
  (WebView + tray)

Python dependencies:

```powershell
pip install -e .            # qrcode[pil] + cryptography, installs the "opendrop" command
```

---

## Downloads

Every GitHub release (the *Releases* tab) includes, generated automatically
on each tag (`v0.2.0` onwards - `v0.1.0` predates the release workflow and
ships no file):

| File | Platform | Contents |
|---|---|---|
| `OpenDrop-vX.Y.Z-win-x64-setup.exe` | Windows 10/11 x64 | full installer: Tauri desktop app + server + wheels (admin rights, offline) |
| `OpenDrop-vX.Y.Z-win-x64.zip` | Windows 10/11 x64 | portable version (just unzip): Tauri desktop app + server |
| `OpenDrop-vX.Y.Z-linux-x64.tar.gz` | Linux x64 (Debian, Kali, Ubuntu...) | Tauri binary + server + wheels + install scripts |

### Windows: installer

1. Download the `*-win-x64-setup.exe` and run it (admin rights required).
2. Choose the installer language, the application language (English or
   French, English by default), then confirm the install into
   `C:\Program Files (x86)\OpenDrop`.
3. Python **3.10+** must already be present (check *Add python.exe to
   PATH*): the installer sets up the dependencies in a local `venv` from
   the bundled wheels, with no network access.

Uninstall: *Windows Settings > Apps > OpenDrop* (or `uninstall.exe` in the
install folder). The uninstaller removes the app, its `venv`, and the app
data (`config.json`, `session.json`, `server.pid`, `certs\` in
`%LOCALAPPDATA%\OpenDrop`) but **never touches your receive or share
folders** (received and shared files are left exactly as they are).

### Linux: tarball

Requirements: `sudo apt install python3 python3-venv` (Python 3.10+), plus
the desktop runtime libraries
`libwebkit2gtk-4.1-0 libayatana-appindicator3-1`.

```bash
tar -xzf OpenDrop-vX.Y.Z-linux-x64.tar.gz
cd OpenDrop
sudo ./install.sh          # /opt/opendrop + local venv + app menu
opendrop-desktop           # or from the menu
```

Uninstall (keeps your *Received* and *Shared* folders):

```bash
sudo ./uninstall.sh
```

`install.sh` writes to `/opt/opendrop` (app) and `~/.opendrop/` (data);
received and shared files themselves stay in `~/Downloads/OpenDrop`.

### Portable version

Unzip the archive and run `OpenDrop.exe` (Windows) or `./OpenDrop` (Linux).
The app needs Python 3.10+ and the dependencies:

```powershell
pip install -r requirements.txt     # or reuse the venv from an install
```

### Automatic updates

OpenDrop checks the latest GitHub release when it starts and whenever you
ask it to from *Settings > Updates*. Only releases tagged `vX.Y.Z` are
offered, never a draft or a pre-release, and nothing is installed before
you click *Update now*.

- **Windows**: the first `setup.exe` asset is downloaded to
  `%TEMP%\opendrop-update-<tag>.<ext>` (a partial `.part` file is kept,
  so an interrupted download resumes), checked against the SHA-256
  `digest` published with the asset, and handed to Windows with elevation
  (`runas`) once OpenDrop has closed. A digest mismatch deletes the file
  and aborts. The installer replaces the previous installation in place —
  a single entry in *Apps*, your settings kept.
- **Linux**: the tarball is downloaded and verified the same way, then
  extracted. Installed in `/opt`? A polkit password dialog (`pkexec`)
  runs the bundled `install.sh`; running from an unpacked folder? The
  files are replaced in place.
  `~/.opendrop` and your receive/share folders are never touched.

*Skip this version* is remembered for that release only (a
`localStorage` key per tag, in the app's webview).

---

## Getting started

### 1. Desktop app (Windows and Linux)

The same app runs on both systems (Tauri 2 + React).

**From source:**

```powershell
cd desktop
npm ci
npm run tauri dev        # dev app: Vite on localhost:1420, engine auto-spawned
```

```bash
cd desktop
npm ci
npm run tauri dev
```

Release build (what users run):

```powershell
npm run tauri build      # exe: desktop/src-tauri/target/release/opendrop.exe
```

```bash
npm run tauri build      # binary: desktop/src-tauri/target/release/opendrop
```

`npm run tauri build` embeds the web assets automatically. If you invoke
`cargo build --release` by hand instead, add
`--features tauri/custom-protocol`, otherwise the binary keeps looking
for the dev server on `localhost:1420`.

**From a release**: see *Downloads* above (Windows installer, Linux tarball,
or portable archive).

The app starts the server on its own: the status card flips to **Server
running**, the address shows up, and the QR code and session code are
generated. Buttons along the bottom:

- **Start server / Stop server**
- **Settings** (folders, port, quota, new token on start, language
  English/French, theme light/dark): once saved, the server restarts
  itself with the new config; the language and theme switches apply
  immediately

### 2. Server only (no desktop UI)

Works on Windows, Linux, and macOS:

```powershell
opendrop                      # after pip install -e .
# or
$env:PYTHONPATH = "src"; python -m opendrop.main
```

Useful options:

| Option | Effect |
|---|---|
| `--headless` | no QR window or browser (for GUI/automated use) |
| `--port 9090` | forces a port other than `preferred_port` |
| `--rotate-token` | forces a new token and a new session code |

### 3. Linux (no desktop available)

On a machine or a VM (Kali, Ubuntu, etc.):

```bash
git clone https://github.com/lucas31Zz/opendrop.git
cd opendrop
pip install -e .
opendrop
```

The terminal prints the `https://<ip>:<port>` address, the session code, and
the path of the QR code; the PNG opens on its own with `xdg-open` if a
desktop is present, otherwise open the URL by hand in your browser.

- No display (SSH, server): `opendrop --headless` prints a JSON line
  (`ip`, `port`, `token`, `session_code`, `url_upload`) for scripts.
- If your phone won't connect, check the firewall:
  `sudo ufw allow 8080` (or whichever port you're using).
- The desktop app runs on Linux too (Tauri build, see *1. Desktop app*):
  QR code, quota, settings.

---

## Using it from a phone

1. Note the `https://<ip>:<port>` address shown by the app.
2. Scan the **QR code**: with the phone's camera app, or with the
   *Scan QR code* button on the session screen (it scans in the page
   itself - Safari, Chrome, Brave, Firefox, anything modern). Typing the
   URL with `?token=...` by hand still works too.
3. On first visit the browser shows a self-signed certificate warning:
   accept the one from the OpenDrop machine only (step-by-step in
   [SECURITY.md](SECURITY.md)).
4. If the screen says **Session locked**, type the **6-character code**
   shown in the desktop app.
5. Use the **Send** tab to send a file, the **Download** tab to grab the
   ones in the *Share* folder.

The top line shows `usage / quota` and updates on its own (every 5 s, and
after each send). Green: under the limit. Red: quota reached.

---

## Folders and quota

| Folder | Role |
|---|---|
| **Receive folder** | where received files land (PC side) |
| **Share folder** | files offered to other devices (PC side) |

Both are changed in **Settings** (browse + Save).

**Global receive quota** (Settings > Storage):

- `0` = unlimited (the default)
- no unit means GB: `500` counts as 500 GB; with a unit: `500 mb`,
  `0.5 gb`, `10.75` (comma or period, French-style `500 mo` / `0,5 go`
  also accepted)
- an unreadable value is rejected with an error message, never silently
  ignored; a negative value in `config.json` is reset to 0 (unlimited)
- above 20% of the disk's free space, a warning asks you to confirm before
  saving
- a send that would push past the quota is rejected with **507** before
  anything is written; two sends at the same time can't both slip under the
  limit
- the indicator also shows up in the main window, refreshed every 3 s
  without a restart

---

## Configuration files

| File | Contents |
|---|---|
| `%LOCALAPPDATA%\OpenDrop\config.json` | folders, port, quota, options |
| `%LOCALAPPDATA%\OpenDrop\session.json` | current token + session code |
| `%LOCALAPPDATA%\OpenDrop\certs\server.crt` / `server.key` | self-signed TLS certificate (EC P-256, 397 days) |

On Linux/macOS the same folder is `~/.opendrop/` (the receive and share
folders, though, stay in `~/Downloads/OpenDrop`).

`config.json` keys:

| Key | Default | Meaning |
|---|---|---|
| `download_directory` | `%USERPROFILE%\Downloads\OpenDrop` | receive folder |
| `share_directory` | `%USERPROFILE%\Downloads\OpenDrop\Partage` | share folder |
| `preferred_port` | `8080` | requested port (falls back to a free one if it's taken) |
| `session_expires_in` | `3600` | token lifetime, in seconds |
| `global_quota_bytes` | `0` | total receive-folder quota, in bytes |
| `generate_new_token` | `false` | new token on every launch |
| `trust_proxy` | `false` | trust `X-Forwarded-For` (known proxies only) |
| `language` | `en` | interface language: server messages, web UI and desktop app (`en` or `fr`) |
| `theme` | `dark` | desktop and web appearance (`light` or `dark`) |

To regenerate the certificate: quit OpenDrop, delete the
`%LOCALAPPDATA%\OpenDrop\certs\` folder, relaunch (see SECURITY.md).

---

## Troubleshooting

| Symptom | What to do |
|---|---|
| The phone won't open the address | Same Wi-Fi/network as the PC, no guest network (they are usually isolated); then allow the port through the firewall: `sudo ufw allow 8080` (Linux). Re-scan the QR code: the address changes when the PC's IP or port changes |
| The browser says *Not secure* / certificate warning | Expected: the certificate is self-signed. Continue to the OpenDrop address only, never another site. To start fresh, delete `certs\` (see above) |
| *Session locked* on the phone | Type the 6-character code shown in the desktop app. The code rotates when the token does |
| *Port already in use* at start | An older server is still running: stop it (Stop server, or close the app), then start again. Otherwise OpenDrop moves to the next free port automatically |
| Upload rejected with **507** (quota bar red) | The receive folder is full against the quota: raise it or set `0` (unlimited) in *Settings > Storage* |
| No update is offered | Only releases tagged `vX.Y.Z` are offered (never a draft or pre-release), GitHub must be reachable, and *Skip this version* silences that version only |
| A second window opens instead of the running one | The single-instance signal failed; the second instance runs anyway as a fallback. Close one of them |
| The QR code never opens | Open the printed `https://<ip>:<port>` URL by hand (`xdg-open`/`startfile` may be missing) |
| The installer says Python is missing | Install Python 3.10+ from python.org, check *Add python.exe to PATH*, run the setup again |
| A file you expected is not listed | The *Download* tab lists the **Share** folder only: drop the file into it (or use *Add* in the desktop app) |

---

## FAQ

**Do I need an account or the internet?**
No. OpenDrop is a local HTTP(S) server on your PC; the transfer stays on
your LAN, nothing is uploaded anywhere.

**Does my phone need an app?**
No. Scan the QR code and use the browser.

**Does it work over the internet?**
No, by design: everything is bound to your local network. Do not expose
the port to the internet.

**Is it encrypted?**
Traffic is HTTPS with a self-signed certificate. Files on disk are *not*
encrypted - see [SECURITY.md](SECURITY.md) and *Security* above.

**How long does a session last?**
`session_expires_in` seconds (3600 by default). The token can also be
rotated on demand (Reset / `--rotate-token`) or on every launch.

**Where do files go?**
Received files land in the *Receive folder*, files to share are read from
the *Share folder*. Both are changed in *Settings*.

**How large can a file be?**
No fixed per-file cap: the optional global receive quota is the only
ceiling (0 = unlimited).

**Can I run it on macOS?**
The server only (`opendrop`): the desktop app targets Windows and Linux.

**How do I update?**
*Settings > Updates* (or automatically at start); the app downloads the
release, checks its SHA-256, and installs it after it closes. See
*Automatic updates* above.

**How do I run it without a window (scripts, VM)?**
`opendrop --headless` prints a JSON line with the URL, token and session
code.

---

## Known limitations

- **LAN only**: no discovery across networks, no internet mode, no NAT
  traversal.
- **No encryption at rest**, and the transfer SHA-256 is not compared
  automatically (*Security* above).
- **The token lives in the URL**: it can end up in your browser history;
  anyone holding the token or the session code can send and receive.
- **Sequential uploads** in the web interface: several files (or zipped
  folders) go one after the other, never in parallel; the phone's file
  list refreshes manually (*Refresh* button).
- **Phone to phone**: a phone can send to the PC, but the *Download* tab
  only offers the *Share* folder, so one phone cannot pull what another
  phone just sent.
- **A cancelled or interrupted update** leaves a partial file in
  `%TEMP%\opendrop-update` until the next attempt reuses or drops it.
- **No transfer resume**: an interrupted upload or download must be started
  again.
- **Windows installer**: Python 3.10+ must already be installed (the
  installer only ships the wheels).
- **Per-IP rate limits** (5 unlock attempts/minute) and the optional
  global receive quota.

---

## Tests

Homegrown test suites (no external framework), run from the repo root:

```powershell
python -m tests.test_security     # 35/35 - tokens, paths, origin, writes, logs
python -m tests.test_routes       # 50/50 - route truth table
python -m tests.test_paths        # 41/41 - no absolute paths in responses
python -m tests.test_quota        # 40/40 - quota, simultaneous reservations, 507
python -m tests.test_sessions     # 34/34 - sessions, expiration, code rotation
python -m tests.test_tls          # 15/15 - self-signed certificate, forced HTTPS
python -m tests.test_server       # 42/42 - general routes, theme fallback, port in use, TIME_WAIT probe, upload idle window, chunked-upload staging
python -m tests.test_beta         # 63/63 - full run-through
python -m tests.test_beta --large # 75/75 - file batches, traversal attempts
python -m tests.test_devices      # 62/62 - device pairing, registered IPs, reset
python -m tests.test_zip_web      # 47/47 - ZIP64, password zips, browser zip engine
python -m tests.test_e2e          # 16/16 - multi-browser upload flows
```

Before building, close the desktop app: a running `OpenDrop.exe` blocks
`npm run tauri build`.

The same suites (without `--large`) run in continuous integration on
Windows and Linux, Python 3.10 and 3.12.

---

## Security

The full threat model (routes, tokens, quota, certificate, limits) is
documented in [SECURITY.md](SECURITY.md). In short:

- everything goes over HTTPS, with a self-signed certificate you have to
  accept by hand;
- the token lives in the URL: it can end up in your browser history; the
  server logs, meanwhile, print `token=***` and `code=***`;
- no encryption at rest: whatever lands on disk is stored in plain text;
  the SHA-256 handed back to the sender isn't compared automatically;
- anyone holding the token or the session code can send/receive.

---

## Repository layout

| Folder | Role |
|---|---|
| `src/opendrop/` | Python server (HTTPS, routes, sessions, quota, TLS) |
| `desktop/` | Tauri desktop app: `desktop/src` (React + TypeScript frontend), `desktop/src-tauri` (Rust core: engine spawn, tray/window, updater) |
| `web/` | web interface (`index.html`, `app.js`, `style.css`) |
| `packaging/` | Windows installer (Inno Setup) and Linux scripts (install/uninstall) |
| `tools/` | dev utilities (icon generation); `tools/screenshots/` is local-only and gitignored |
| `tests/` | homegrown test suites |
| `docs/` | project docs (screenshots) |
| `.github/` | continuous integration, Dependabot, issue templates |
| `SECURITY.md` | threat model |
| `CONTRIBUTING.md` | how to contribute |
| `LICENSE` | MIT license |

### How the pieces talk to each other

```text
                       starts / stops (process, pid file)
 desktop app  ────────────────────────────────────────────►  python -m opendrop.main --headless
 (Tauri)       ◄──── polls https://127.0.0.1:<port>/api/info ────┐
       │                                                        │
       │ GET /releases/latest (update check)                    │ HTTPS + token
       ▼                                                        ▼
   GitHub Releases ◄─── SHA-256 of asset ──── updater        phone browser
   (setup.exe/tar.gz)                      (src-tauri)       (web interface)
```

| Component | Role |
|---|---|
| `src/opendrop/main.py` | entry point: config, IP/port, token, QR, headless JSON |
| `src/opendrop/server/` | HTTPS server: routes (`server.py`), multipart parsing (`multipart.py`), quota (`quota.py`), sessions (`session.py`), rate limits (`rate_limit.py`), typed errors (`errors.py`) |
| `src/opendrop/security/` | tokens, session state, path/file-name validation, TLS certificate |
| `src/opendrop/config/`, `network/`, `qr/`, `i18n.py` | configuration, local IP and free port, QR rendering, translations |
| `web/` | the phone UI: one `fetch` per API route (`/api/info`, `/api/upload`, `/api/files`, `/api/quota`, `/api/download/<name>`, `/api/session/unlock`); `/api/progress` exists server-side but no client calls it yet |
| `desktop/src-tauri/src/main.rs` | the desktop core: `spawn_engine` (interpreter resolution: installer `venv` first, then PATH, `PYTHONPATH` for the repo layout), orphan reaping, tray and window (one window per machine, close-to-hide), the updater (GitHub releases, `vX.Y.Z` tags, per-OS asset, SHA-256 digest, Windows `runas` / Linux `pkexec`) |
| `desktop/src/App.tsx`, `desktop/src/whatsnew.ts` | the React UI: settings pane, update toast, one `invoke` per Tauri command; `whatsnew.ts` holds the FR + EN release note shown once per version; the server tree is killed when the app exits |
| `.github/workflows/` | `tests.yml` (suites), `desktop.yml` (build), `release.yml` (assets attached to the release on a `v*` tag) |

The desktop app never parses the server's stdout: it reads the running
configuration back through `/api/info` (address, port, quota, language,
theme). Everything else the UI shows comes from the same API the phone
uses.

---

## Release process

Maintainers only; contributors never need this.

1. **Choose the version** (semantic): patch for fixes, minor for features,
   major for breaking changes.
2. **Bump it everywhere** so they all agree — `pyproject.toml`,
   `src/opendrop/main.py`, `packaging/windows/OpenDrop.iss` (and its
   line-13 comment), `desktop/src-tauri/tauri.conf.json`,
   `desktop/src-tauri/Cargo.toml`, `desktop/package.json` (plus
   `Cargo.lock` and `package-lock.json`, refreshed by the builds).
3. **Update `CHANGELOG.md`**: new `## [X.Y.Z] - YYYY-MM-DD` section at the
   top, following Keep a Changelog — the release workflow extracts the
   notes from it — **and rewrite `desktop/src/whatsnew.ts`** for the new
   version (the popup users see once per release, FR + EN).
4. **Run everything** (all suites, `--large`, `npx tsc --noEmit`,
   `npm run build`, `npm run tauri build`) — CI must be green on the
   commit you tag.
5. **Tag and push**:

   ```powershell
   git tag -a vX.Y.Z -m "OpenDrop vX.Y.Z"
   git push origin main vX.Y.Z
   ```

   The `v` prefix is mandatory: the desktop app only offers releases whose
   tag matches `vX.Y.Z`.
6. **The `release` workflow does the rest**: on every `v*` tag it builds
   the Windows setup + portable zip and the Linux tarball, creates the
   release (title + generated notes) if it does not exist, and attaches
   the three assets with `--clobber`. Nothing is pushed by hand.
7. **Verify**: the three assets are present, digest published, tests
   badge green, and *Latest* points at the new tag.

Rolling back or re-releasing: never move a published tag — publish a new
patch release instead. To repair assets, re-run the workflow (`gh run
rerun`) or let the next tag recreate them; a release created without
assets can be deleted and rebuilt by re-running the tag's workflow.

---

## Community

Questions, setup help, and ideas are discussed on the
[OpenDrop Discord](https://discord.gg/vREBPZuvhV). The desktop app opens it
from the Discord button in the title bar.

---

## Contributing

Fixes and features are welcome: see
[CONTRIBUTING.md](CONTRIBUTING.md). The test suites also run in continuous
integration (GitHub Actions) on every push and pull request.

Found a vulnerability? Use the repo's *Security* tab or the e-mail listed in
[SECURITY.md](SECURITY.md) - no public issues.

Expected behavior in the community: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## License

Distributed under the [MIT](LICENSE) license. Use it at your own risk.
Version history: [CHANGELOG.md](CHANGELOG.md).
