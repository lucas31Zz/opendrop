import html
import json
import os
import re
import socket
import ssl
import sys
import time
import threading
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn, TCPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote, quote

from opendrop.security.validation import is_safe_path
from opendrop.network.interfaces import _port_is_free
from opendrop.security.tls_cert import ensure_certificate
from opendrop.i18n import t, normalize_lang
from opendrop.qr.generator import generate_qr_png
from opendrop.server.multipart import parse_multipart_upload, CHUNK_SIZE
from opendrop.server.quota import QuotaTracker
from opendrop.server.rate_limit import limiter_general, limiter_upload, limiter_download, limiter_session
from opendrop.server.session import SessionManager
from opendrop.themes import DEFAULT_THEME, normalize_theme
from opendrop.server.errors import (
    OpenDropError, TokenInvalidError, TokenExpiredError, OriginForbiddenError,
    RateLimitError,
    MultipartParseError, FilenameInvalidError, FilenameUnsafeError,
    FileTooLargeError, FileDeletedError, DownloadError, DiskError,
    format_error_response, log_error,
)

WEB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"

# HTTPS only: no HTTP fallback (getUserMedia requires it, and the LAN
# traffic must stay encrypted).
SCHEME = "https"

MAX_UPLOAD_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB

# An upload rejected before reading (size, quota) leaves the client still
# writing: we absorb a chunk of the body before answering, otherwise the
# connection drops mid-write and the client loses the error message.
MAX_DRAIN_BYTES = 64 * 1024 * 1024
MAX_DRAIN_SECONDS = 2.0

# "Normal" socket noise: a phone probing the port, a client closing during
# the TLS handshake, etc. Not worth a Python traceback.
_TLS_NOISE = (ssl.SSLError, ConnectionResetError, ConnectionAbortedError,
              BrokenPipeError, TimeoutError)

# Handshake budget. The handshake runs in the worker thread (see
# OpenDropHandler.setup), never in accept(): a client that connects and then
# stops talking - a browser pre-connect abandoned when the phone locks, a
# Wi-Fi drop in the middle of the ClientHello - must not park the accept
# loop, otherwise nobody gets an answer and the phone sits on a black page.
TLS_HANDSHAKE_TIMEOUT = 10.0

# Idle budget for an established connection. Long enough for a screen-off
# hiccup during an upload, short enough to release a dead client quickly.
REQUEST_TIMEOUT = 30.0


class PortInUseError(RuntimeError):
    """The port is already taken (often by an older OpenDrop server)."""


def _probe_listener(port: int) -> str | None:
    """'opendrop', 'other' or None (port free).

    Fast path: when no process holds the port, a plain local bind says so
    without any connection (connecting to a free port can wait for the
    whole timeout before failing). The TLS handshake is only attempted
    when the port is actually taken.
    """
    if _port_is_free(port):
        return None
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5) as raw:
            try:
                context = ssl._create_unverified_context()
                with context.wrap_socket(raw, server_hostname="127.0.0.1") as tls:
                    tls.sendall(b"GET /api/info HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                                b"Connection: close\r\n\r\n")
                    # The reply arrives in pieces: headers can show up
                    # without the body, so read until the marker or until
                    # the connection stops (bounded by the timeout).
                    data = b""
                    deadline = time.monotonic() + 1.0
                    while time.monotonic() < deadline:
                        chunk = tls.recv(2048)
                        if not chunk:
                            break
                        data += chunk
                        if b'"port"' in data:
                            return "opendrop"
            except (ssl.SSLError, OSError, socket.timeout):
                return "other"
            return "opendrop" if b'"port"' in data else "other"
    except OSError:
        return "other"


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    # A cold page load opens ~5 connections at once (document, css, js,
    # /api/info, /api/quota) while the desktop polls every 2 s: the default
    # backlog of 5 drops SYNs and the browser retries on a blank page.
    request_queue_size = 128

    def server_bind(self):
        # HTTPServer.server_bind resolves the FQDN (reverse DNS): on some
        # machines that wait exceeds a second on every server start. The
        # local host name is enough; it is only used in error pages.
        TCPServer.server_bind(self)
        self.server_name = socket.gethostname()
        self.server_port = self.server_address[1]

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], _TLS_NOISE):
            return
        super().handle_error(request, client_address)

transfer_state = {
    "active": False,
    "filename": "",
    "size": 0,
    "received": 0,
    "done": False,
    "error": None,
    "started_at": 0,
}

transfer_lock = threading.Lock()


def _content_disposition(filename: str) -> str:
    """Content-Disposition header for an arbitrary name.

    The raw name would be latin-1 encoded (exception on non-ASCII names)
    and would accept a CRLF (header injection): a clean ASCII fallback for
    old clients, RFC 5987 for UTF-8.
    """
    ascii_fallback = "".join(
        c if 32 <= ord(c) < 127 and c not in '"' else "_" for c in filename)
    if not ascii_fallback.strip(" ."):
        ascii_fallback = "download"
    return (f'attachment; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{quote(filename)}")


# The token and the backup code travel in the query string, and the request
# line is printed by BaseHTTPRequestHandler: without this filter, a simple
# log redirection would put the secrets on disk.
_SENSITIVE_QUERY = re.compile(r"(?i)\b(token|code)=[^&\s\"']+")


def _redact_secrets(message: str) -> str:
    return _SENSITIVE_QUERY.sub(lambda m: f"{m.group(1)}=***", message)


class OpenDropHandler(BaseHTTPRequestHandler):
    server_version = "OpenDrop"
    # Do not expose the Python version: the server identifier must not
    # help target a known CVE in the interpreter.
    sys_version = ""

    def __init__(self, *args, token: str = "", download_dir: str = "", share_dir: str = "",
                 sessions: SessionManager | None = None, **kwargs):
        self._token = token
        self._download_dir = download_dir
        self._share_dir = share_dir
        self._sessions = sessions
        super().__init__(*args, **kwargs)

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler answers in HTML without security headers
        # and with internal details: short page, escaped, same headers as
        # the rest, no technical explanation.
        try:
            try:
                reason = message or HTTPStatus(code).phrase
            except ValueError:
                reason = message or "Error"
            body = (
                "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                f"<title>{html.escape(f'{code} {reason}')}</title></head>"
                f"<body><h1>{code}</h1><p>{html.escape(str(reason))}</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(code, message)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._send_security_headers()
            self.end_headers()
            if getattr(self, "command", None) != "HEAD":
                self.wfile.write(body)
        except OSError:
            pass

    def log_message(self, format, *args):
        try:
            line = format % args
        except Exception:
            line = repr(args)
        line = _redact_secrets(line)
        try:
            print(f"[OpenDrop] {self.address_string()} - {line}")
        except UnicodeEncodeError:
            safe = line.encode("ascii", errors="replace").decode("ascii")
            print(f"[OpenDrop] {self.address_string()} - {safe}")

    def setup(self):
        # TLS is terminated here, inside the worker thread. Wrapping the
        # listening socket instead would run the handshake inside accept()
        # (ssl.SSLSocket.accept), i.e. in the single serve_forever thread:
        # one client frozen mid-handshake would then freeze the whole
        # server for everyone. The handshake is bounded so a silent client
        # only costs this thread, never the accept loop.
        context = getattr(self.server, "ssl_context", None)
        if context is not None and not isinstance(self.request, ssl.SSLSocket):
            self.request.settimeout(TLS_HANDSHAKE_TIMEOUT)
            # wrap_socket detaches the raw socket and hands the descriptor
            # to the SSLSocket. The handshake is run by hand so a failure
            # still leaves us holding an object we can close, instead of
            # waiting for the garbage collector to notice an orphan.
            tls = context.wrap_socket(self.request, server_side=True,
                                      do_handshake_on_connect=False)
            try:
                tls.do_handshake()
            except BaseException:
                try:
                    tls.close()
                except OSError:
                    pass
                raise
            self.request = tls
            self.request.settimeout(REQUEST_TIMEOUT)
        super().setup()

    def finish(self):
        try:
            # The response is already on the wire (wbufsize is 0). Closing
            # while the request body is still queued makes the kernel reset
            # the connection and the client loses that response, so absorb
            # whatever the handler never read - this is the last chance.
            # It must happen before super().finish() closes self.rfile.
            self._drain_left_body()
            super().finish()
        finally:
            # shutdown_request() only ever sees the detached raw socket
            # (fd already transferred above), so the SSLSocket would be
            # closed by the garbage collector at an arbitrary moment -
            # after the response may have been lost. Release it here.
            sock = self.request
            if isinstance(sock, ssl.SSLSocket):
                try:
                    sock.close()
                except OSError:
                    pass

    def handle(self):
        self.connection.settimeout(REQUEST_TIMEOUT)
        self.close_connection = True
        self.handle_one_request()

    def _get_client_ip(self) -> str:
        # X-Forwarded-For is only honored behind a trusted proxy
        # (trust_proxy). Otherwise any LAN client could invent IPs and
        # bypass the rate limiting.
        if getattr(self.server, "trust_proxy", False):
            forwarded = self.headers.get("X-Forwarded-For")
            if forwarded:
                entries = [e.strip() for e in forwarded.split(",") if e.strip()]
                if entries:
                    return entries[-1]
        return self.client_address[0]

    def _check_origin(self) -> None:
        origin = self.headers.get("Origin")
        if not origin:
            return
        scheme = getattr(self.server, "scheme", SCHEME)
        allowed = f"{scheme}://{self.server.local_ip}:{self.server.port}"
        allowed_local = f"{scheme}://127.0.0.1:{self.server.port}"
        if origin != allowed and origin != allowed_local:
            raise OriginForbiddenError()

    def _check_token(self, query: dict) -> None:
        t = query.get("token", [None])[0]
        if not t:
            raise TokenInvalidError("Missing session token")
        if self._sessions:
            valid, reason = self._sessions.validate(t)
            if not valid:
                if reason == "expired":
                    raise TokenExpiredError()
                raise TokenInvalidError()
        else:
            from opendrop.security.tokens import validate_token
            if not validate_token(t, self._token):
                raise TokenInvalidError()

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")

    def _send_error_json(self, exc: OpenDropError) -> None:
        lang = getattr(self.server, "language", "en")
        self._send_json(format_error_response(exc, lang), exc.status)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, path: Path) -> None:
        if not path.exists():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        ip = self._get_client_ip()
        lang = getattr(self.server, "language", "en")

        try:
            self._check_origin()
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/":
                self._send_html(WEB_DIR / "index.html")
            elif path == "/style.css":
                self._send_file(WEB_DIR / "style.css", "text/css")
            elif path == "/app.js":
                self._send_file(WEB_DIR / "app.js", "application/javascript")
            elif path == "/qr":
                self._route_qr(query, ip)
            elif path.startswith("/api/"):
                if not limiter_general.allow(ip):
                    raise RateLimitError()
                if path == "/api/progress":
                    self._route_progress(query)
                elif path == "/api/info":
                    self._route_info(query)
                elif path == "/api/files":
                    self._route_files(query, ip)
                elif path == "/api/quota":
                    self._route_quota(query)
                elif path.startswith("/api/download/"):
                    self._route_download(query, path, ip)
                else:
                    self._send_json({"error": t("Unknown route", lang), "code": 404}, 404)
            else:
                self.send_error(404)
        except OpenDropError as e:
            self._send_error_json(e)
        except ConnectionResetError:
            pass
        except BrokenPipeError:
            pass
        except ssl.SSLError:
            pass
        except Exception as e:
            log_error(e, "do_GET")
            self._send_error_json(OpenDropError())

    def do_POST(self):
        ip = self._get_client_ip()
        lang = getattr(self.server, "language", "en")
        self._body_drained = False

        try:
            self._check_origin()
            if not limiter_general.allow(ip):
                raise RateLimitError()

            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/api/upload":
                self._route_upload(query, ip)
            elif path == "/api/session/unlock":
                # Absorb the (empty) body first: `finish()` would do it,
                # but answering with bytes still queued is what resets the
                # connection on some systems.
                self._drain_left_body()
                self._route_session_unlock(query, ip)
            else:
                self._drain_left_body()
                self._send_json({"error": t("Unknown route", lang), "code": 404}, 404)
        except OpenDropError as e:
            # An error answer written while the request body is still
            # queued makes the kernel reset the connection: the client then
            # loses the status line and only sees a cut connection.
            self._drain_left_body()
            self._send_error_json(e)
        except ConnectionResetError:
            pass
        except BrokenPipeError:
            pass
        except ssl.SSLError:
            pass
        except Exception as e:
            log_error(e, "do_POST")
            self._drain_left_body()
            try:
                self._send_error_json(OpenDropError())
            except Exception:
                pass

    def _drain_left_body(self) -> None:
        """Swallow a request body that was never read, before answering.

        Bounded in size and time (`_drain_body`), and done at most once per
        request: once `parse_multipart_upload` has started, the remaining
        bytes are no longer where this would look for them.
        """
        if getattr(self, "_body_drained", False):
            return
        self._body_drained = True
        headers = getattr(self, "headers", None)
        if headers is None:
            return
        try:
            length = int(headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            return
        if length <= 0:
            return
        try:
            self._drain_body(length)
        except Exception:
            # Never let a defensive read break the response path.
            pass

    def _route_qr(self, query: dict, ip: str) -> None:
        # Outside /api/: without this line the route would generate PNGs
        # unbounded, and it hands out the token embedded in the image.
        if not limiter_general.allow(ip):
            raise RateLimitError()
        self._check_token(query)
        url = f"{getattr(self.server, 'scheme', SCHEME)}://{self.server.local_ip}:{self.server.port}/?token={self._token}"
        img = generate_qr_png(url)
        if img is None:
            self._send_json(
                {"error": t("QR code unavailable",
                            getattr(self.server, "language", "en"))}, 500)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(img)))
        self.end_headers()
        self.wfile.write(img)

    def _route_progress(self, query: dict) -> None:
        self._check_token(query)
        with transfer_lock:
            state = dict(transfer_state)
        if state["active"] and state["started_at"] and state["received"] > 0:
            elapsed = time.monotonic() - state["started_at"]
            if elapsed > 0:
                speed = state["received"] / elapsed
                state["speed"] = round(speed)
                if speed > 0 and state["size"] > 0:
                    remaining = state["size"] - state["received"]
                    state["eta"] = round(remaining / speed)
                else:
                    state["eta"] = None
        self._send_json(state)

    def _route_info(self, query: dict) -> None:
        # Discovery route: the desktop (status poll) and the probe that
        # identifies an OpenDrop server call it before any authentication.
        # So it must not leak anything sensitive: session state is only
        # returned to a valid token bearer.
        data = {
            "ip": self.server.local_ip,
            "port": self.server.port,
            "lang": getattr(self.server, "language", "en"),
            # Desktop theme choice: the phone page follows it unless
            # the device overrides it locally.
            "theme": getattr(self.server, "theme", DEFAULT_THEME),
        }
        if "token" in query:
            self._check_token(query)
            if self._sessions:
                data["session"] = self._sessions.get_info()
        self._send_json(data)

    def _route_quota(self, query: dict) -> None:
        self._check_token(query)
        quota = getattr(self.server, "quota", None)
        if quota is None:
            self._send_json({"usage_bytes": 0, "limit_bytes": 0})
            return
        self._send_json({
            "usage_bytes": quota.usage(),
            "limit_bytes": quota.limit_bytes,
        })

    def _route_session_unlock(self, query: dict, ip: str) -> None:
        if not limiter_session.allow(ip):
            raise RateLimitError()
        code = query.get("code", [None])[0]
        if not self._sessions or not self._sessions.validate_code(code):
            print(f"[OpenDrop] Invalid session code ({ip})", flush=True)
            raise TokenInvalidError("Invalid session code")
        # The code opens a new session: already-connected devices are left
        # alone, and unlocking stays possible even after the main session
        # has expired.
        self._send_json({"success": True, "token": self._sessions.create()})

    def _route_files(self, query: dict, ip: str) -> None:
        self._check_token(query)
        if not limiter_download.allow(ip):
            raise RateLimitError()
        self._handle_list_files()

    def _route_download(self, query: dict, path: str, ip: str) -> None:
        self._check_token(query)
        if not limiter_download.allow(ip):
            raise RateLimitError()
        filename = unquote(path[len("/api/download/"):])
        self._handle_download_file(filename)

    def _route_upload(self, query: dict, ip: str) -> None:
        self._check_token(query)
        if not limiter_upload.allow(ip):
            raise RateLimitError("Too many uploads, try again in a moment")
        self._handle_upload()

    def _drain_body(self, content_length: int) -> None:
        """Absorb (without writing to disk) part of a rejected body.

        When we reject before reading, the client is often still writing:
        without this read the connection drops mid-upload and the browser
        loses the error message (it shows a connection cut instead of the
        507). Bounded in size and time so a slow client cannot stall us.
        """
        remaining = max(0, min(content_length, MAX_DRAIN_BYTES))
        if remaining == 0:
            return
        deadline = time.monotonic() + MAX_DRAIN_SECONDS
        old_timeout = None
        try:
            old_timeout = self.connection.gettimeout()
            self.connection.settimeout(0.5)
            while remaining > 0 and time.monotonic() < deadline:
                try:
                    chunk = self.rfile.read(min(remaining, CHUNK_SIZE))
                except OSError:
                    break
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass
        finally:
            try:
                self.connection.settimeout(old_timeout)
            except OSError:
                pass

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))

        if "multipart/form-data" not in content_type:
            raise MultipartParseError("Invalid request format")

        if content_length > MAX_UPLOAD_SIZE:
            raise FileTooLargeError("File too large (max 10 GB)")

        # Global quota: scan the folder + reserve the announced space
        # (raises 507 if the upload would exceed the quota).
        quota = getattr(self.server, "quota", None)
        if quota is not None:
            quota.reserve(content_length)

        with transfer_lock:
            transfer_state.update({
                "active": True, "filename": "", "size": content_length,
                "received": 0, "done": False, "error": None,
                "started_at": time.monotonic(),
            })

        def on_progress(received):
            with transfer_lock:
                transfer_state["received"] = received

        # From here the body is being consumed: any later error must not
        # try to re-read it (see `_drain_left_body`).
        self._body_drained = True
        try:
            safe_name, error, file_hash = parse_multipart_upload(
                self.rfile, content_type, content_length,
                self._download_dir, on_progress=on_progress,
            )
        except DiskError as e:
            with transfer_lock:
                transfer_state.update({"active": False, "error": e.message})
            raise
        except Exception as e:
            with transfer_lock:
                transfer_state.update({"active": False, "error": "File read error"})
            log_error(e, "upload parse")
            raise MultipartParseError("Cannot read the uploaded file")
        finally:
            # The reservation only covers the write itself: a failed
            # upload does not block the next ones.
            if quota is not None:
                quota.release(content_length)

        if error:
            with transfer_lock:
                transfer_state.update({"active": False, "error": error})
            if "unsafe" in error:
                raise FilenameUnsafeError(error)
            raise MultipartParseError(error)

        dest = Path(self._download_dir) / safe_name
        try:
            file_size = dest.stat().st_size
        except OSError:
            file_size = 0

        with transfer_lock:
            transfer_state.update({
                "active": False, "filename": safe_name, "size": file_size,
                "received": file_size, "done": True, "error": None,
            })

        try:
            print(f"[OpenDrop] File received: {safe_name} ({file_size} bytes) -> {dest}", flush=True)
        except UnicodeEncodeError:
            safe_name_ascii = safe_name.encode("ascii", errors="replace").decode("ascii")
            dest_ascii = str(dest).encode("ascii", errors="replace").decode("ascii")
            print(f"[OpenDrop] File received: {safe_name_ascii} ({file_size} bytes) -> {dest_ascii}", flush=True)
        # Never the server's real path: the client only needs the name,
        # size and hash (see SECURITY.md, "Routes and paths").
        resp = {"success": True, "filename": safe_name, "size": file_size}
        if file_hash:
            resp["sha256"] = file_hash
        self._send_json(resp)

    def _handle_list_files(self):
        share_dir = Path(self._share_dir)
        if not share_dir.exists():
            self._send_json({"files": []})
            return
        files = []
        try:
            for f in sorted(share_dir.iterdir()):
                if f.is_file():
                    files.append({"name": f.name, "size": f.stat().st_size})
        except OSError as e:
            log_error(e, "list_files")
            raise OpenDropError("Cannot read the share folder")
        self._send_json({"files": files})

    def _handle_download_file(self, filename: str):
        share_dir = Path(self._share_dir)
        if not is_safe_path(str(share_dir), filename):
            raise FilenameUnsafeError("Path not allowed")
        filepath = share_dir / filename
        if not filepath.exists():
            raise FileDeletedError("File not found")
        if not filepath.is_file():
            raise DownloadError("The path does not match a file")

        try:
            file_size = filepath.stat().st_size
        except OSError as e:
            log_error(e, "download stat")
            raise OpenDropError("Cannot access the file")

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", _content_disposition(filename))
        self.send_header("Content-Length", str(file_size))
        self._send_security_headers()
        self.end_headers()

        try:
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except OSError as e:
            log_error(e, "download stream")
            raise OpenDropError("File read error")


def create_server(ip: str, port: int, token: str, download_dir: str, share_dir: str,
                  session_expires_in: int = 3600, trust_proxy: bool = False,
                  session_code: str | None = None,
                  tls_cert_dir: str | Path | None = None,
                  global_quota_bytes: int = 0,
                  language: str = "en",
                  theme: str = DEFAULT_THEME) -> ThreadedHTTPServer:
    language = normalize_lang(language)
    theme = normalize_theme(theme)
    sessions = SessionManager(expires_in=session_expires_in, code=session_code)
    sessions.register(token)
    sessions.start_cleanup()
    original_init = OpenDropHandler.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, token=token, download_dir=download_dir,
                      share_dir=share_dir, sessions=sessions, **kwargs)

    handler = type("Handler", (OpenDropHandler,), {"__init__": patched_init})

    # On Windows, SO_REUSEADDR allows a double bind: two OpenDrop servers
    # could coexist on the same port with different tokens and codes (the
    # phone would then land on the wrong one). Refuse.
    listener = _probe_listener(port)
    if listener == "opendrop":
        raise PortInUseError(t(
            "Another OpenDrop server is already running on port {port}.",
            language, port=port))
    if listener == "other":
        raise PortInUseError(t(
            "Port {port} is already in use by another program.",
            language, port=port))

    server = ThreadedHTTPServer(("0.0.0.0", port), handler)
    server.local_ip = ip
    server.port = port
    server.sessions = sessions
    server.trust_proxy = trust_proxy
    server.scheme = SCHEME
    server.language = language
    # Desktop light/dark choice, mirrored to the phone page.
    server.theme = theme
    # Global receive-folder quota (0 = unlimited). The folder is scanned on
    # every upload; the reservation is thread-safe.
    server.quota = QuotaTracker(download_dir, global_quota_bytes, lang=language)

    # TLS: local self-signed certificate (regenerated when the IP changes).
    # Clients probing the port in plain text fail the handshake, which
    # handle_error swallows silently.
    #
    # The listening socket stays plain TCP on purpose: the context is handed
    # to each handler, which wraps its own connection in setup() (worker
    # thread). See the comment there for why.
    cert_path, key_path = ensure_certificate(ip, directory=tls_cert_dir)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(cert_path), str(key_path))
    server.ssl_context = context
    return server
