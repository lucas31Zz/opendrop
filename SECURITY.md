# OpenDrop - Threat Model

## Goal

OpenDrop is a file transfer tool for local networks (LAN).
It's meant for personal use, on a home or office network.

Install and getting started: see [README.md](README.md).

---

## What OpenDrop protects

### 1. Unauthorized access

- Every session gets a random 32-character token ([a-zA-Z0-9],
  62^32 combinations)
- Tokens expire after a configurable period
  (`session_expires_in` in config.json, default: 1 hour)
- Expired tokens are cleaned up automatically
- A periodic sweep of expired sessions runs in the background
- The request origin (`Origin`) is checked against the server's real URL
  (HTTPS + IP + port): any foreign origin, and especially an HTTP origin,
  gets 403
- Without a QR code, the session code (6 characters, unambiguous alphabet:
  31 letters/digits with no O/0/I/1/L, so 31^6 = 887 503 681 combinations)
  unlocks the device: it's capped at 5 tries / minute / IP, the comparison
  runs in constant time (`secrets.compare_digest`), and it ignores case and
  separators
- The code doesn't expire on its own: it lives as long as `session.json`
  and only changes on rotation (desktop Reset button, `--rotate-token`,
  "New token on start" checkbox). On rotation, the previous code goes invalid
  right away (tested)
- The code still works once the token has expired: that's the backup
  function (tested)
- Unlocking hands out a fresh 32-character token with the same rights: each
  unlocked device gets its own token, no rights are granular
- Every route marked "token required" in the section 5 table is enforced
  server-side; a missing or expired token gives 403

### 2. Dangerous paths

- On upload, the name is reduced to its basename, dangerous characters
  (`< > : " / \ | ? *`, control chars) are swapped for `_`, leading and
  trailing dots and spaces are dropped, and Windows reserved names (CON,
  PRN, COM1...) are rejected: only the file name is left
- On download, the path is resolved against the share folder (is_safe_path,
  with `realpath`): any attempt to get out of the folder (`..`, the `/`
  separator, a symlink) gives 400 "Path not allowed"
- Only files inside the share folder are downloadable

### 3. Denial of service

- Rate limiting per IP:
  - Upload: 10 requests / minute
  - Download: 30 requests / minute
  - General (all /api/ and /qr routes): 120 requests / minute
  - Session unlock: 5 requests / minute
- Size limit: 10 GB per file (MAX_UPLOAD_SIZE). The request body is
  strictly bounded by Content-Length: lying about the length doesn't let you
  go past the limit, and a truncated upload is rejected then deleted
- That limit applies per file, not to everything received: see the "Filling
  the disk" section (optional global quota) for the rest
- Uploads are read and written as a stream (64 KB chunks): a 10 GB file is
  never loaded into memory all at once
- The client IP is always the one on the TCP connection; X-Forwarded-For is
  only honored when "trust_proxy" is enabled in config.json (trusted proxy),
  otherwise it would be trivial to spoof to dodge rate limiting

### 4. Information leaks

- No tracebacks in HTTP responses
- Generic error messages for internal errors
- The server's real paths are never exposed (see section 6)
- The `Server` header only carries `OpenDrop`, no Python version
- HTML error responses are short, escaped, and carry the same security
  headers as everything else

### 5. Routes and tokens

Truth table tested by `python -m tests.test_routes`:

| Route | Access | Note |
|---|---|---|
| `POST /api/upload` | token required | rate limit 10/min per IP |
| `GET /api/files` | token required | lists the share folder (files offered) |
| `GET /api/progress` | token required | upload progress |
| `GET /api/quota` | token required | usage + global quota |
| `GET /api/download/*` | token required | rate limit 30/min per IP |
| `GET /qr` | token required | rate limit 120/min (the PNG embeds the token) |
| `POST /api/session/unlock` | 6-character code | rate limit 5/min per IP, response = token |
| `GET /api/info` | public | discovery route (ip + port) for the desktop app and the probe; the `session` block (active session count, duration) only goes out to a valid token holder, and a bad token gives 403 |
| `GET /`, `/style.css`, `/app.js` | public | web interface shell, no secrets |
| unknown `/api/*` route | - | 404 JSON `{"error": ..., "code": 404}` |
| unknown HTML page | - | short 404 HTML, no internal detail |

- Neither the token nor the session code shows up in HTML pages, errors, or
  `/api/info`; only `/qr` (by design) and the `POST /api/session/unlock`
  response (delivered to whoever holds the code) carry the token
- The download filename is encoded with an ASCII fallback first, then
  `filename*=UTF-8''...`: a non-Latin-1 name no longer breaks the header,
  and no control character (CR/LF) can be injected into it

### 6. Absolute paths

Tested by `python -m tests.test_paths`:

- The upload response only carries `filename`, `size` and `sha256`: the
  server's real path (`str(dest)`) isn't in it anymore, it only shows up in
  the server console
- `GET /api/files` only returns `{name, size}` per file
- `GET /api/progress` contains no paths (state: file, size, received, speed,
  error)
- Error messages are fixed strings (`errors.py`): no raw `OSError`, no
  stack trace, no folder path
- Disk write errors (`DiskError`) only carry the system reason
  (`[Errno 28] No space left on device`): no file or folder name, so it
  shows up neither in the 507 response nor in the error message displayed
- Server logs mask secrets: `?token=...` and `?code=...` are replaced with
  `token=***` / `code=***` before printing. Piping the server's output to a
  file therefore puts neither the token nor the code on disk
- The assets (`/`, `/style.css`, `/app.js`) contain no local path: the
  interface only knows relative URLs
- The receive folder and the share folder are shown in the app's Settings:
  local interface only, never served over the network
- Traces with real paths (`[OpenDrop] File received: ... -> C:\...`) go to
  the server's console/local logs, not into an HTTP response

---

## What OpenDrop does NOT protect

### Network

- Traffic is encrypted in transit: HTTPS enforced, TLS 1.2 minimum (see the
  "TLS certificate" section)
- The certificate is self-signed: no authority vouches for the server's
  identity. An attacker sitting on the same network can present their own
  certificate; always accept the one from the OpenDrop machine, never
  another device's
- The token sits in the URL (?token=...): it can end up in browser history,
  bookmarks, and the server's logs
- An old http:// QR code no longer works: the server only listens on HTTPS.
  Rescan the QR code shown by the desktop app

### Authenticity

- OpenDrop doesn't check who the devices are
- Anyone with the token can send/receive files
- Access security rests on the cryptographic unpredictability of the token
  (32 random characters)

### Data

- No encryption at rest
- The SHA-256 is computed while writing, byte by byte, over what actually
  hits the disk, and it's only handed back once the final body boundary has
  been seen: a truncated upload or a write that fails on the last block
  gives 400/507, the partial file is deleted, and no hash is returned.
  Nothing compares it automatically on the receiving side: the web interface
  displays it, the sender has to check it
- Deleted files aren't wiped irreversibly

### Filling the disk

- The 10 GB limit is per file, not across all the files received: nothing
  stops someone from sending dozens of files under 10 GB until the
  destination disk is full
- Optional global quota on the receive folder
  (`global_quota_bytes` in config.json, in bytes; 0 or missing key =
  unlimited). Set in the app's Settings, "Global quota for the receive
  folder" field: an integer (no unit = GB, hence "500 means 500 GB") or with
  a unit (go, mo, kb, tb; "500 mo" means 500 MB), comma or period accepted,
  0 = unlimited. An unreadable value is refused (error message), never
  ignored in silence; a negative value (hand-edited config) is reset to 0,
  that is unlimited, rather than being read as a limit nothing can satisfy.
  The quota is checked against the header (Content-Length) before anything
  is received: a send that would push the total over is refused with 507
  ("Global quota reached: X used of Y") without writing any file, after
  swallowing a piece of the body so the client can actually read the message
  - The reservation is atomic (locked): two simultaneous sends can't both
    slip under the limit, one of them is refused with 507 and the total
    stays at or below the quota (tested)
  - The quota allows hitting the exact weight (comparison `>`: usage + size
    = quota passes, the next byte is refused), tested over HTTP
  - By default the quota is off: filling the disk stays possible with no
    overall limit until the user sets one
  - Every reservation is released, even when the write fails or the body is
    invalid: no phantom space goes missing
- Before saving a quota above 20% of the disk's free space, the app shows a
  warning ("Proceed at your own risk") and only saves if the user confirms
- Live tracking: the desktop app shows "usage / quota" (green while under
  the limit, red after that, refreshed every 3 s without a restart) and the
  web interface shows the same line on top of the "Send" and "Download"
  tabs. The web app hits GET /api/quota (token required, otherwise 403)
  every 5 s and after each send; the "usage_bytes" field includes uploads
  in progress (reservation included)
- No free-space check before writing: a lack of room is only caught while
  writing. The quota, for its part, only counts the files already in the
  receive folder: it says nothing about the disk space actually left, nor
  about what other folders or apps do with it
- In that case the server answers 507 (Out of disk space), deletes the
  partial file, and fails cleanly: no truncated file is left behind. Same
  goes when closing the file fails on the last block (final flush): the 507
  comes back and the hash isn't delivered
- Upload rate limiting (10/min) slows the pace down without capping the
  total volume

### Validation

- OpenDrop doesn't validate file contents
- Dangerous files (.exe, .bat, etc.) can be received
- It's on the user to check what they open

---

## TLS certificate

OpenDrop only speaks HTTPS. The certificate is generated locally on first
launch: it's self-signed, so the browser shows a trust warning the first
time you connect. That's expected.

### Location

- Folder: `%LOCALAPPDATA%\OpenDrop\certs\`
- Files: `server.crt` (certificate) and `server.key` (private key, 600
  permissions)
- Algorithm: EC P-256 key, self-signed, SHA-256, 397-day validity
- SAN: `localhost`, the machine name, `127.0.0.1`, and the current LAN IP

### Automatic regeneration

The certificate is regenerated when the server starts if:

- the file is missing or unreadable,
- it expires in less than 30 days,
- the current IP is no longer in the SAN (DHCP change),
- the key no longer matches the certificate,
- the serverAuth EKU extension is missing (required by iOS/Safari).

### Manual regeneration

1. Quit OpenDrop (the desktop app and its server).
2. Delete the `%LOCALAPPDATA%\OpenDrop\certs\` folder.
3. Relaunch OpenDrop: a new certificate is created automatically.

The token, the QR code and the session code do NOT change when you
regenerate (they only change on the Reset button, the timer, or the "New
token on start" checkbox). When in doubt, rescanning the QR code shown by
the desktop app is always safe: that's the source of truth.

### First visit from a phone

The self-signed certificate brings up a warning screen. Don't tap "Stop":
accept the one from the OpenDrop machine only.

Chrome / Android:

1. "Your connection is not private"
2. "Advanced"
3. "Proceed to *your-ip* (unsafe)"

Safari / iOS:

1. "This connection is not private"
2. "Show website details"
3. "Visit this website"

Firefox:

1. "The connection is not secure"
2. "Continue to this site (unsafe)"

If the certificate was regenerated (IP changed, expiry, certs folder
deleted), the warning comes back: you have to accept it again.

### Picking a stable IP

The certificate carries your current IP. If the router hands out a
different one (DHCP), the certificate is regenerated and the warning comes
back on every phone. To avoid that: reserve the machine's IP in your
router's DHCP settings (fixed lease / DHCP reservation). The IP then stays
the same and the certificate stays valid until it expires (397 days).

### What the encryption covers

- Done: the URL, the token and the file contents travel encrypted across
  the LAN. Passive sniffing (tcpdump, Wireshark) only sees TLS
- Limit: no identity check by a trusted authority (self-signed
  certificate). The user has to accept it by hand; accepting another
  device's certificate would make the protection pointless
- Not done: encryption at rest, nor any attestation of the identity of the
  devices holding the token

---

## Verification

Everything above is covered by automated tests (run from the repo root,
Python 3.12, no external framework):

| Command | What it proves | Result |
|---|---|---|
| `python -m tests.test_security` | tokens, paths, size limits, origin, incomplete body, write failure, logs with no secrets | 36/36 |
| `python -m tests.test_routes` | route truth table (section 5) | 44/44 |
| `python -m tests.test_paths` | no absolute path in any response (section 6) | 43/43 |
| `python -m tests.test_quota` | global quota, simultaneous reservations, exact fill, 507 | 40/40 |
| `python -m tests.test_sessions` | sessions, expiration, session code, rotation through `opendrop.main` | 34/34 |
| `python -m tests.test_tls` | self-signed certificate, key/cert, EKU, renewal, forced HTTPS | 15/15 |
| `python -m tests.test_server` | general routes, port already in use, TIME_WAIT probe, fast startup | 14/14 |
| `python -m tests.test_beta` (+ `--large`) | full run-through, file batches, traversal attempts | 64/64 and 76/76 |

---

## Threat Model

| Threat | Protection | Status |
|---|---|---|
| Access with no token | Token required on every route that carries data; `/api/info` public with no secrets (see section 5) | Done |
| Request from another site | Origin (`Origin`) checked against the server's real URL: 403 otherwise | Done |
| Brute force on the session code | 6-character code (31^6), 5 tries / minute / IP, rotation on demand | Done |
| Token brute-force | 32 random characters (62^32 combinations) | Done |
| Expired token | Configurable expiration + automatic cleanup; the backup code keeps working | Done |
| Path traversal | Path validation with is_safe_path | Done |
| Filling the disk | 10 GB per file + optional global quota (507, atomic reservation) | Partial |
| DoS by requests | Rate limiting per IP | Done |
| Stack trace leak | No tracebacks in responses | Done |
| Absolute path leak | Responses with no server path (upload = name + size + hash), disk errors with no path | Done |
| Secret leak in logs | `token=` and `code=` replaced with `***` in the server logs | Done |
| Network interception | HTTPS enforced (TLS 1.2+), self-signed certificate | Done |
| Encryption in transit | HTTPS enforced on every API route | Done |
| Encryption at rest | Not protected | Future |
| Identity attestation | Self-signed certificate, manual acceptance (tested: not approved by default) | Limited |
| Integrity check | SHA-256 returned only when the body is complete; displayed, no automatic comparison | Done |

---

## Reporting a vulnerability

If you find a security flaw, don't publish it anywhere public (not here,
not in an issue). Two channels, in order of preference:

1. **GitHub private form**: repo *Security* tab >
   *Report a vulnerability*. The report is encrypted and stays confidential.
2. **E-mail**: lucasbertholon1@gmail.com (subject: "OpenDrop - security").

Please include the route involved, the steps to reproduce, and any potential
impact. Reply within a few days; no retaliation against a good-faith
report.

---

## License

OpenDrop is released under the [MIT](LICENSE) license - see also
[CONTRIBUTING.md](CONTRIBUTING.md). Use it at your own risk.
