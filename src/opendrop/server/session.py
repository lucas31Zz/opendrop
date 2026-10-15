import secrets
import threading
import time

from opendrop.security.tokens import generate_token


class Session:
    def __init__(self, token: str, expires_in: int = 3600,
                 ip: str | None = None):
        self.token = token
        self.created_at = time.monotonic()
        self.expires_in = expires_in
        self.active = True
        # IP the session was created from (None for the main session,
        # created before any request). Lets the desktop invalidate every
        # session of one device (dissociate) without touching others.
        self.ip = ip

    @property
    def expired(self) -> bool:
        if not self.active:
            return True
        return (time.monotonic() - self.created_at) > self.expires_in

    @property
    def age(self) -> float:
        return time.monotonic() - self.created_at

    @property
    def remaining(self) -> float:
        return max(0, self.expires_in - self.age)


class SessionManager:
    def __init__(self, expires_in: int = 3600, cleanup_interval: int = 300,
                 code: str | None = None):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._expires_in = expires_in
        self._cleanup_interval = cleanup_interval
        self._cleanup_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Short code to type on another device. Reused from the saved state
        # when provided, otherwise regenerated: it only changes on an
        # explicit reset.
        self._code = self._resolve_code(code)
        # Main (QR) token: register() records it so invalidate_ip() can
        # never delete its own session.
        self._main_token: str | None = None

    @staticmethod
    def _resolve_code(code: str | None) -> str:
        normalized = normalize_session_code(code)
        if len(normalized) != SESSION_CODE_LENGTH:
            return generate_session_code()
        return normalized

    @property
    def code(self) -> str:
        with self._lock:
            return self._code

    def validate_code(self, code: str | None) -> bool:
        """Constant-time comparison, insensitive to case and separators."""
        normalized = normalize_session_code(code)
        expected = self.code
        if len(normalized) != len(expected):
            return False
        return secrets.compare_digest(normalized, expected)

    def start_cleanup(self) -> None:
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        self._stop_event.clear()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def stop_cleanup(self) -> None:
        self._stop_event.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=2)

    def _cleanup_loop(self) -> None:
        while not self._stop_event.is_set():
            removed = self.cleanup()
            if removed > 0:
                print(f"[OpenDrop] Expired sessions cleaned: {removed}", flush=True)
            self._stop_event.wait(self._cleanup_interval)

    def register(self, token: str) -> None:
        with self._lock:
            self._sessions[token] = Session(token, self._expires_in)
            self._main_token = token

    def create(self, ip: str | None = None) -> str:
        token = generate_token()
        with self._lock:
            self._sessions[token] = Session(token, self._expires_in, ip=ip)
        return token

    def invalidate_ip(self, ip: str) -> int:
        """Delete every session created from `ip`; the main session survives.

        Used by dissociate: one device's sessions die with its record,
        the desktop's own (main/QR) session is never touched.
        """
        with self._lock:
            doomed = [t for t, s in self._sessions.items()
                      if t != self._main_token and s.ip == ip]
            for t in doomed:
                del self._sessions[t]
        print(f"[OpenDrop] Sessions invalidated for {ip}: {len(doomed)}",
              flush=True)
        return len(doomed)

    def validate(self, token: str | None) -> tuple[bool, str]:
        if not token:
            return (False, "missing")
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return (False, "invalid")
            if session.expired:
                del self._sessions[token]
                return (False, "expired")
            return (True, "ok")

    def invalidate(self, token: str) -> bool:
        with self._lock:
            if token in self._sessions:
                del self._sessions[token]
                return True
            return False

    def cleanup(self) -> int:
        with self._lock:
            expired = [t for t, s in self._sessions.items() if s.expired]
            for t in expired:
                del self._sessions[t]
            return len(expired)

    def count(self) -> int:
        with self._lock:
            expired = [t for t, s in self._sessions.items() if s.expired]
            for t in expired:
                del self._sessions[t]
            return len(self._sessions)

    def get_info(self) -> dict:
        with self._lock:
            expired = [t for t, s in self._sessions.items() if s.expired]
            for t in expired:
                del self._sessions[t]
            return {
                "active_sessions": len(self._sessions),
                "expires_in": self._expires_in,
            }


# Without O/0, I/1, L: the code stays readable by eye and types without errors.
SESSION_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
SESSION_CODE_LENGTH = 6


def generate_session_code(length: int = SESSION_CODE_LENGTH) -> str:
    return "".join(secrets.choice(SESSION_CODE_ALPHABET) for _ in range(length))


def normalize_session_code(code: str | None) -> str:
    if not code:
        return ""
    return "".join(c for c in code.upper() if c in SESSION_CODE_ALPHABET)
