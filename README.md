# OpenDrop

> Direct file transfers on your local network: launch OpenDrop, scan the
> QR code, send. No account, no cloud, no install on your phone.

[![Tests](https://github.com/lucas31Zz/opendrop/actions/workflows/tests.yml/badge.svg)](https://github.com/lucas31Zz/opendrop/actions/workflows/tests.yml)
[![MIT License](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Windows](https://img.shields.io/badge/bureau-Windows%20%2B%20Linux-lightgrey.svg)](desktop/OpenDrop/OpenDrop.csproj)
[![Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](.github/workflows/tests.yml)


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
  *Download* tabs, quota bar up top, session lock
- **Share folder**: files dropped in there are offered to other devices,
  downloadable in one click
- **Global receive quota** (optional): rejected with a 507 before anything
  is written, live indicator (green under the limit, red once reached)
- **Safety limits**: 10 GB per file, per-IP rate limits, sanitized file
  names, validated paths, no server path leaks
- **Desktop app for Windows and Linux** (Avalonia, .NET 8): QR code,
  address, session code, quota, folders, settings, one-click server
  start/stop
- **English and French**: English is the default everywhere (installer,
  desktop app, web interface, server messages); switch the app to French
  in *Settings* (or pick it in the Windows installer)

---

## Screenshots

Coming soon (`docs/screenshots/`): the desktop app (QR code, quota,
settings) and the web interface (*Send* / *Download* tabs).

---

## Requirements

- Python **3.10+** (developed and tested on 3.12) — Windows **or Linux**
  (tests run in CI on both)
- Only needed to build the desktop app from source: **.NET 8 SDK**
  (available on Windows, Linux, and macOS)

Python dependencies:

```powershell
pip install -e .            # qrcode[pil] + cryptography, installs the "opendrop" command
```

---

## Downloads

Every GitHub release (the *Releases* tab) includes, generated automatically
on each tag:

| File | Platform | Contents |
|---|---|---|
| `OpenDrop-vX.Y.Z-win-x64-setup.exe` | Windows 10/11 x64 | full installer (admin rights), dependencies installed locally, offline |
| `OpenDrop-vX.Y.Z-win-x64.zip` | Windows 10/11 x64 | portable version (just unzip) |
| `OpenDrop-vX.Y.Z-linux-x64.tar.gz` | Linux x64 (Debian, Kali, Ubuntu...) | binary + server + wheels + install scripts |

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

Requirements: `sudo apt install python3 python3-venv` (Python 3.10+).

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

---

## Getting started

### 1. Desktop app (Windows and Linux)

The same app runs on both systems (Avalonia UI).

**From source:**

```powershell
dotnet build desktop\OpenDrop\OpenDrop.csproj
.\desktop\OpenDrop\bin\Debug\net8.0\OpenDrop.exe        # Windows
```

```bash
dotnet build desktop/OpenDrop/OpenDrop.csproj
./desktop/OpenDrop/bin/Debug/net8.0/OpenDrop            # Linux
```

**From a release**: see *Downloads* above (Windows installer, Linux tarball,
or portable archive).

The app starts the server on its own: the status card flips to **Server
running**, the address shows up, and the QR code and session code are
generated. Buttons along the bottom:

- **Start server / Stop server**
- **Settings** (folders, port, quota, new token on start, language
  English/French): once saved, the server restarts itself with the new
  config; the language switch applies immediately

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
- The desktop app runs on Linux too (same binary as the server, see
  *1. Desktop app*): QR code, quota, settings.

---

## Using it from a phone

1. Note the `https://<ip>:<port>` address shown by the app.
2. Scan the **QR code** (or type the URL with `?token=...`).
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

To regenerate the certificate: quit OpenDrop, delete the
`%LOCALAPPDATA%\OpenDrop\certs\` folder, relaunch (see SECURITY.md).

---

## Tests

Homegrown test suites (no external framework), run from the repo root:

```powershell
python -m tests.test_security     # 36/36 - tokens, paths, limits, origin, writes, logs
python -m tests.test_routes       # 44/44 - route truth table
python -m tests.test_paths        # 43/43 - no absolute paths in responses
python -m tests.test_quota        # 40/40 - quota, simultaneous reservations, 507
python -m tests.test_sessions     # 34/34 - sessions, expiration, code rotation
python -m tests.test_tls          # 15/15 - self-signed certificate, forced HTTPS
python -m tests.test_server       # 11/11 - general routes, port in use
python -m tests.test_beta         # 64/64 - full run-through
python -m tests.test_beta --large # 76/76 - file batches, traversal attempts
```

Before building, close the desktop app: a running binary blocks
`dotnet build`.

The same suites (without `--large`) run in continuous integration on
Windows and Linux, Python 3.10 and 3.12.

---

## Automatic updates (Windows)

At startup, the desktop app checks the public manifest of this repository
(`update.xml`) for a newer release. If one is found, a dialog asks whether to
download and install it:

- the setup is downloaded to the temp folder and **verified against a SHA-256
  digest** from the manifest before anything runs (aborted and deleted on
  mismatch);
- launching the installer replaces the application in `Program Files (x86)`
  and detects the running app (closed automatically);
- **your data is preserved**: `config.json`, `session.json` and the TLS
  certificate live in `%LOCALAPPDATA%\OpenDrop` and are never touched by an
  update;
- the check is **Windows-only** and reads a public manifest — no GitHub token
  is embedded in the application.

To disable the check, add `"check_updates": false` to
`%LOCALAPPDATA%\OpenDrop\config.json` and relaunch.

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
| `desktop/OpenDrop/` | Avalonia desktop app (.NET 8, Windows + Linux) that drives the server |
| `web/` | web interface (`index.html`, `app.js`, `style.css`) |
| `packaging/` | Windows installer (Inno Setup) and Linux scripts (install/uninstall) |
| `tools/` | dev utilities (icon generation) |
| `tests/` | homegrown test suites |
| `docs/` | project docs (screenshots) |
| `.github/` | continuous integration, Dependabot, issue templates |
| `SECURITY.md` | threat model |
| `CONTRIBUTING.md` | how to contribute |
| `LICENSE` | MIT license |

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
