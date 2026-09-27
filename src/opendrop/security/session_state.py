"""Persistent session state: token + session code.

These secrets survive server restarts so that the QR code and the session
code stay valid. They only change on explicit request (the app's Reset
button, or the "new token on startup" option).

Separate file from config.json: the parameters are rewritten by the desktop
app, while the secrets must never be rewritten along with them.
"""
import json
from pathlib import Path

from opendrop.config.config import get_config_dir

STATE_FILE = "session.json"


def _state_path(directory: str | Path | None = None) -> Path:
    base = Path(directory) if directory else get_config_dir()
    return base / STATE_FILE


def load_session_state(directory: str | Path | None = None) -> dict | None:
    """Return {"token", "code"} or None if missing/unusable."""
    path = _state_path(directory)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    token = data.get("token")
    if not isinstance(token, str) or not token:
        return None
    code = data.get("code")
    if not isinstance(code, str) or not code:
        code = None
    return {"token": token, "code": code}


def save_session_state(token: str, code: str,
                       directory: str | Path | None = None) -> None:
    path = _state_path(directory)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"token": token, "code": code}, f, indent=2)
    except OSError:
        pass
