"""Etat de session persistant : token + code de session.

Ces secrets survivent aux redemarrages du serveur pour que le QR code et le
code de session restent valides. Ils ne changent que sur demande explicite
(bouton Reset de l'app, ou option "nouveau token au demarrage").

Fichier separe de config.json : les parametres sont reecrits par l'app
desktop, les secrets ne doivent jamais partir avec eux.
"""
import json
from pathlib import Path

from opendrop.config.config import get_config_dir

STATE_FILE = "session.json"


def _state_path(directory: str | Path | None = None) -> Path:
    base = Path(directory) if directory else get_config_dir()
    return base / STATE_FILE


def load_session_state(directory: str | Path | None = None) -> dict | None:
    """Retourne {"token", "code"} ou None si absent/inutilisable."""
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
