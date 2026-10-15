"""Paired-device registry: pairing token + known devices.

The registry remembers which devices (phones/tablets) have already been
paired with this instance, so the web UI can recognise them on later
visits ("Share info with this device" opt-in, remember-device label).

The token lets a device prove it was paired before; the records survive
server restarts. Like the session state, the file is only rewritten when
something actually changes: reading the registry never creates it.
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from opendrop.config.config import get_config_dir
from opendrop.security.tokens import generate_token

DEVICE_FILE = "devices.json"


def parse_user_agent(ua: str) -> dict:
    """Best-effort {"device", "browser", "os"} breakdown of a User-Agent.

    Unknown parts are empty strings. Simple ordered keyword scan: Edge
    must be matched before Chrome (and both before Safari) because every
    Chromium/WebKit UA embeds the previous names.
    """
    ua = ua or ""

    device = ""
    if "iPhone" in ua:
        device = "iPhone"
    elif "iPad" in ua:
        device = "iPad"

    # iOS UAs also contain "Mac OS X": test them first.
    os_name = ""
    if "Windows" in ua:
        os_name = "Windows"
    elif "Android" in ua:
        os_name = "Android"
    elif "iPhone OS" in ua or "iPad OS" in ua or "CPU OS" in ua:
        os_name = "iOS"
    elif "Mac OS X" in ua:
        os_name = "macOS"
    elif "Linux" in ua:
        os_name = "Linux"

    browser = ""
    for keyword, name in (("Edg", "Edge"), ("Chrome", "Chrome"),
                          ("Firefox", "Firefox"), ("Safari", "Safari")):
        if keyword in ua:
            browser = name
            break

    return {"device": device, "browser": browser, "os": os_name}


class DeviceRegistry:
    """Persistent registry of paired devices, keyed by IP.

    The HTTP server is threaded: every operation holds one lock around
    its read-modify-write section.
    """

    def __init__(self, directory: str | Path | None = None):
        base = Path(directory) if directory else get_config_dir()
        self._path = base / DEVICE_FILE
        self._lock = threading.Lock()
        self._token: str | None = None
        self._devices: dict[str, dict] = {}
        self._load()

    # --- persistence ----------------------------------------------------

    def _load(self) -> None:
        """Fill state from disk; missing/corrupt file → fresh empty state."""
        try:
            with open(self._path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        token = data.get("device_token")
        if isinstance(token, str) and token:
            self._token = token
        devices = data.get("devices")
        if isinstance(devices, dict):
            self._devices = {ip: rec for ip, rec in devices.items()
                             if isinstance(rec, dict)}

    def save(self) -> None:
        """Write state to disk (utf-8, indent 2), atomically."""
        with self._lock:
            self._save_locked()

    def _save_locked(self) -> None:
        if not self._token:
            self._token = generate_token()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_name(self._path.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"device_token": self._token,
                           "devices": self._devices}, f, indent=2)
            os.replace(tmp, self._path)
        except OSError:
            pass

    # --- token ----------------------------------------------------------

    @property
    def token(self) -> str:
        """Pairing token: 32 alnum chars, persisted only on first mutation."""
        with self._lock:
            if not self._token:
                self._token = generate_token()
            return self._token

    def rotate(self) -> str:
        """Generate a new token, persist it, and return it."""
        with self._lock:
            self._token = generate_token()
            self._save_locked()
            return self._token

    # --- devices --------------------------------------------------------

    @staticmethod
    def _copy(ip: str, rec: dict) -> dict:
        return {"ip": ip,
                "ua": rec.get("ua", ""),
                "did": rec.get("did", ""),
                "share_info": bool(rec.get("share_info", False)),
                "added_at": rec.get("added_at", "")}

    def is_registered(self, ip: str) -> bool:
        with self._lock:
            return ip in self._devices

    def get(self, ip: str) -> dict | None:
        """Copy of the record {ua, did, share_info, added_at}, or None."""
        with self._lock:
            rec = self._devices.get(ip)
            if rec is None:
                return None
            copy = self._copy(ip, rec)
            copy.pop("ip")
            return copy

    def list_devices(self) -> list[dict]:
        """Copies of every record, sorted by added_at."""
        with self._lock:
            out = [self._copy(ip, rec) for ip, rec in self._devices.items()]
        out.sort(key=lambda d: d["added_at"])
        return out

    def register(self, ip: str, ua: str = "", did: str = "",
                 share_info: bool | None = None) -> None:
        """Add or update the record for `ip`, then persist.

        A record holding the same non-empty `did` at another IP is
        removed first (a device keeps its identity when its IP changes).
        On update, `share_info=None` keeps the existing value; a new
        record gets False. `added_at` is set on create and kept on update.
        """
        with self._lock:
            if did:
                for other in list(self._devices):
                    if other != ip and self._devices[other].get("did") == did:
                        del self._devices[other]
            rec = self._devices.get(ip)
            if rec is None:
                self._devices[ip] = {
                    "ua": ua,
                    "did": did,
                    "share_info": False if share_info is None else bool(share_info),
                    "added_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                rec["ua"] = ua
                rec["did"] = did
                if share_info is not None:
                    rec["share_info"] = bool(share_info)
            self._save_locked()

    def set_share_info(self, ip: str, value: bool) -> bool:
        """Persist the user's share-info opt-in for `ip`.

        Returns False (without saving) if the device is not registered.
        """
        with self._lock:
            rec = self._devices.get(ip)
            if rec is None:
                return False
            rec["share_info"] = bool(value)
            self._save_locked()
            return True

    def remove(self, ip: str) -> bool:
        """Forget the device at `ip`; True if it existed."""
        with self._lock:
            if ip not in self._devices:
                return False
            del self._devices[ip]
            self._save_locked()
            return True
