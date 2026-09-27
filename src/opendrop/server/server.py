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
from opendrop.qr.generator import generate_qr_png
from opendrop.server.multipart import parse_multipart_upload, CHUNK_SIZE
from opendrop.server.quota import QuotaTracker
from opendrop.server.rate_limit import limiter_general, limiter_upload, limiter_download, limiter_session
from opendrop.server.session import SessionManager
from opendrop.server.errors import (
    OpenDropError, TokenInvalidError, TokenExpiredError, OriginForbiddenError,
    RateLimitError,
    MultipartParseError, FilenameInvalidError, FilenameUnsafeError,
    FileTooLargeError, FileDeletedError, DownloadError, DiskError,
    QuotaExceededError,
    format_error_response, log_error,
)

WEB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"

# HTTPS force : pas de repli HTTP (getUserMedia + chiffrement du LAN).
SCHEME = "https"

MAX_UPLOAD_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB

# Un envoi rejete avant lecture (taille, quota) laisse le client en train
# d'ecrire : on absorbe un morceau du corps avant de repondre, sinon la
# connexion tombe pendant l'ecriture et le client perd le message d'erreur.
MAX_DRAIN_BYTES = 64 * 1024 * 1024
MAX_DRAIN_SECONDS = 2.0

# Erreurs de socket "normales" : telephone qui sonde le port, client qui
# ferme pendant le handshake TLS, etc. Pas la peine d'une trace Python.
_TLS_NOISE = (ssl.SSLError, ConnectionResetError, ConnectionAbortedError,
              BrokenPipeError, TimeoutError)


class PortInUseError(RuntimeError):
    """Le port est deja pris (souvent par un ancien serveur OpenDrop)."""


def _probe_listener(port: int) -> str | None:
    """'opendrop', 'autre' ou None (port libre).

    Chemin rapide : si aucun processus ne tient le port, un simple bind
    local le dit sans aucune connexion (une connexion sur un port libre
    peut ici attendre tout le timeout avant d'echouer). Le handshake TLS
    n'est lance que quand le port est effectivement pris.
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
                    # La reponse arrive par morceaux : les en-tetes peuvent
                    # arriver sans le corps, on lit jusqu'au marqueur ou a
                    # l'arret de la connexion (borné par le timeout).
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
                return "autre"
            return "opendrop" if b'"port"' in data else "autre"
    except OSError:
        return "autre"


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def server_bind(self):
        # HTTPServer.server_bind calcule le FQDN (resolution DNS inverse)
        # : sur certaines machines cette attente depasse une seconde a
        # chaque demarrage du serveur. Le nom d'hote local suffit, il n'est
        # utilise que dans les pages d'erreur.
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
    """En-tete Content-Disposition sur pour un nom arbitraire.

    Le nom brut serait encode en latin-1 (exception sur les noms
    non-ASCII) et accepterait un CRLF (injection d'en-tetes) : un fallback
    ASCII propre pour les vieux clients, RFC 5987 pour l'UTF-8.
    """
    ascii_fallback = "".join(
        c if 32 <= ord(c) < 127 and c not in '"' else "_" for c in filename)
    if not ascii_fallback.strip(" ."):
        ascii_fallback = "download"
    return (f'attachment; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{quote(filename)}")


# Le jeton et le code de secours voyagent dans la query string et la ligne
# de requete est imprimee par BaseHTTPRequestHandler : sans ce filtre, un
# simple redirection des journaux mettrait les secrets sur le disque.
_SENSITIVE_QUERY = re.compile(r"(?i)\b(token|code)=[^&\s\"']+")


def _redact_secrets(message: str) -> str:
    return _SENSITIVE_QUERY.sub(lambda m: f"{m.group(1)}=***", message)


class OpenDropHandler(BaseHTTPRequestHandler):
    server_version = "OpenDrop"
    # Ne pas publier la version de Python : l'identifiant du serveur ne
    # doit pas aider a cibler une CVE connue de l'interpreteur.
    sys_version = ""

    def __init__(self, *args, token: str = "", download_dir: str = "", share_dir: str = "",
                 sessions: SessionManager | None = None, **kwargs):
        self._token = token
        self._download_dir = download_dir
        self._share_dir = share_dir
        self._sessions = sessions
        super().__init__(*args, **kwargs)

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler repond en HTML sans les en-tetes de
        # securite et avec des details internes : page courte, echappee,
        # memes en-tetes que le reste, aucun explique technique.
        try:
            try:
                reason = message or HTTPStatus(code).phrase
            except ValueError:
                reason = message or "Erreur"
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

    def handle(self):
        self.connection.settimeout(10)
        self.close_connection = True
        self.handle_one_request()

    def _get_client_ip(self) -> str:
        # X-Forwarded-For n'est pris en compte que derriere un proxy de
        # confiance (trust_proxy). Sans cela, n'importe quel client du LAN
        # pourrait inventer des IP et contourner le rate limiting.
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
            raise TokenInvalidError("Token manquant")
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
        self._send_json(format_error_response(exc), exc.status)

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
                    self._send_json({"error": "Route inconnue", "code": 404}, 404)
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
                self._route_session_unlock(query, ip)
            else:
                self._send_json({"error": "Route inconnue", "code": 404}, 404)
        except OpenDropError as e:
            self._send_error_json(e)
        except ConnectionResetError:
            pass
        except BrokenPipeError:
            pass
        except ssl.SSLError:
            pass
        except Exception as e:
            log_error(e, "do_POST")
            try:
                self._send_error_json(OpenDropError())
            except Exception:
                pass

    def _route_qr(self, query: dict, ip: str) -> None:
        # Hors /api/ : sans cette ligne la route genererait des PNG sans
        # borne, et elle livre le token contenu dans l'image.
        if not limiter_general.allow(ip):
            raise RateLimitError()
        self._check_token(query)
        url = f"{getattr(self.server, 'scheme', SCHEME)}://{self.server.local_ip}:{self.server.port}/?token={self._token}"
        img = generate_qr_png(url)
        if img is None:
            self._send_json({"error": "QR code non disponible"}, 500)
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
        # Route de decouverte : le desktop (poll d'etat) et le probe qui
        # identifie un serveur OpenDrop l'appellent avant toute
        # authentification. Elle ne doit donc rien contenir de sensible :
        # l'etat des sessions ne sort que pour un porteur de token valide.
        data = {
            "ip": self.server.local_ip,
            "port": self.server.port,
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
            print(f"[OpenDrop] Code de session invalide ({ip})", flush=True)
            raise TokenInvalidError("Code de session invalide")
        # Le code ouvre une nouvelle session : on ne touche pas aux appareils
        # deja connectes, et le deblocage reste possible meme si la session
        # principale a expire.
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
            raise RateLimitError("Trop d'envois, reessayez dans un moment")
        self._handle_upload()

    def _drain_body(self, content_length: int) -> None:
        """Absorbe (sans ecrire sur disque) une partie d'un corps rejete.

        Quand on rejette avant lecture, le client est souvent encore en
        train d'ecrire : sans cette lecture, la connexion tombe en plein
        envoi et le navigateur perd le message d'erreur (il affiche alors
        une coupure de connexion a la place du 507). Borne en taille et en
        temps pour ne pas attendre un client lent.
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
            raise MultipartParseError("Format de requete invalide")

        if content_length > MAX_UPLOAD_SIZE:
            self._drain_body(content_length)
            raise FileTooLargeError("Fichier trop volumineux (max 10 Go)")

        # Quota global : scan du dossier + reservation de la place annoncee
        # (leve 507 si l'envoi ferait depasser le quota).
        quota = getattr(self.server, "quota", None)
        if quota is not None:
            try:
                quota.reserve(content_length)
            except QuotaExceededError:
                self._drain_body(content_length)
                raise

        with transfer_lock:
            transfer_state.update({
                "active": True, "filename": "", "size": content_length,
                "received": 0, "done": False, "error": None,
                "started_at": time.monotonic(),
            })

        def on_progress(received):
            with transfer_lock:
                transfer_state["received"] = received

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
                transfer_state.update({"active": False, "error": "Erreur de lecture du fichier"})
            log_error(e, "upload parse")
            raise MultipartParseError("Impossible de lire le fichier envoye")
        finally:
            # La reservation couvre la duree de l'ecriture uniquement : un
            # envoi echoue ne bloque pas les suivants.
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
            print(f"[OpenDrop] Fichier recu: {safe_name} ({file_size} octets) -> {dest}", flush=True)
        except UnicodeEncodeError:
            safe_name_ascii = safe_name.encode("ascii", errors="replace").decode("ascii")
            dest_ascii = str(dest).encode("ascii", errors="replace").decode("ascii")
            print(f"[OpenDrop] Fichier recu: {safe_name_ascii} ({file_size} octets) -> {dest_ascii}", flush=True)
        # Jamais le chemin reel du serveur : le client n'a besoin que du
        # nom, de la taille et du hash (voir SECURITY.md, "Routes et chemins").
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
            raise OpenDropError("Impossible de lire le dossier de partage")
        self._send_json({"files": files})

    def _handle_download_file(self, filename: str):
        share_dir = Path(self._share_dir)
        if not is_safe_path(str(share_dir), filename):
            raise FilenameUnsafeError("Chemin non autorise")
        filepath = share_dir / filename
        if not filepath.exists():
            raise FileDeletedError("Fichier introuvable")
        if not filepath.is_file():
            raise DownloadError("Le chemin ne correspond pas a un fichier")

        try:
            file_size = filepath.stat().st_size
        except OSError as e:
            log_error(e, "download stat")
            raise OpenDropError("Impossible d'acceder au fichier")

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
            raise OpenDropError("Erreur de lecture du fichier")


def create_server(ip: str, port: int, token: str, download_dir: str, share_dir: str,
                  session_expires_in: int = 3600, trust_proxy: bool = False,
                  session_code: str | None = None,
                  tls_cert_dir: str | Path | None = None,
                  global_quota_bytes: int = 0) -> ThreadedHTTPServer:
    sessions = SessionManager(expires_in=session_expires_in, code=session_code)
    sessions.register(token)
    sessions.start_cleanup()
    original_init = OpenDropHandler.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, token=token, download_dir=download_dir,
                      share_dir=share_dir, sessions=sessions, **kwargs)

    handler = type("Handler", (OpenDropHandler,), {"__init__": patched_init})

    # Sur Windows, SO_REUSEADDR autorise un double bind : deux serveurs
    # OpenDrop pourraient coexister sur le meme port, avec token et code
    # differents (le telephone tomberait alors sur le mauvais). On refuse.
    listener = _probe_listener(port)
    if listener == "opendrop":
        raise PortInUseError(
            f"Un autre serveur OpenDrop tourne deja sur le port {port}.")
    if listener == "autre":
        raise PortInUseError(f"Le port {port} est deja utilise par un autre programme.")

    server = ThreadedHTTPServer(("0.0.0.0", port), handler)
    server.local_ip = ip
    server.port = port
    server.sessions = sessions
    server.trust_proxy = trust_proxy
    server.scheme = SCHEME
    # Quota global du dossier de reception (0 = illimite). Le scan du
    # dossier se fait a chaque envoi, la reservation est thread-safe.
    server.quota = QuotaTracker(download_dir, global_quota_bytes)

    # TLS : certificat auto-signe local (regenere si l'IP change). Les
    # clients qui sondent le port en clair echouent au handshake, ce que
    # handle_error avale silencieusement.
    cert_path, key_path = ensure_certificate(ip, directory=tls_cert_dir)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(cert_path), str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server
