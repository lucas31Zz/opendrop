import json
import os
from pathlib import Path

from opendrop.themes import DEFAULT_THEME


def get_config_dir() -> Path:
    appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "OpenDrop"
    return Path.home() / ".opendrop"


def get_default_download_dir() -> Path:
    downloads = Path.home() / "Downloads" / "OpenDrop"
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads


def get_default_share_dir() -> Path:
    share = Path.home() / "Downloads" / "OpenDrop" / "Partage"
    share.mkdir(parents=True, exist_ok=True)
    return share


CONFIG_FILE = "config.json"


def load_config() -> dict:
    config_dir = get_config_dir()
    config_path = config_dir / CONFIG_FILE
    defaults = {
        "download_directory": str(get_default_download_dir()),
        "share_directory": str(get_default_share_dir()),
        "preferred_port": 8080,
        "session_expires_in": 3600,
        "trust_proxy": False,
        # UI language: "en" (default) or "fr".
        "language": "en",
        # Desktop UI theme: one id from opendrop.themes.THEMES (default
        # "dark"). Also published on /api/info so the phone page can
        # follow it.
        "theme": DEFAULT_THEME,
    }
    if config_path.exists():
        try:
            # utf-8-sig: tolerate a BOM, otherwise the whole file would be
            # skipped silently and the user's folders would be lost.
            with open(config_path, "r", encoding="utf-8-sig") as f:
                saved = json.load(f)
            defaults.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_config(config: dict) -> None:
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / CONFIG_FILE
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
