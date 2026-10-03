"""Quota for the receive folder as a whole.

MAX_UPLOAD_SIZE bounds each file individually; this module adds the
cumulative limit: on every upload the receive folder is scanned (total size
of the files), and the space announced by Content-Length is reserved for the
duration of the upload.

The reservation is exact: the request body is strictly bounded by
Content-Length, so a file can never write more than the reserved value, even
with two simultaneous uploads.

The quota is optional: 0 (or missing key) = unlimited.
"""
import os
import threading
from pathlib import Path

from opendrop.server.errors import QuotaExceededError


def directory_usage(path) -> int:
    """Total size in bytes of the folder's files, recursively."""
    base = Path(path)
    if not base.is_dir():
        return 0
    total = 0
    for root, _dirs, files in os.walk(base):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def format_size(value: int, lang: str = "en") -> str:
    """Short, readable format: 1536 -> '1.50 KB' (English) or '1.50 Ko' (French)."""
    value = int(value)
    if lang == "fr":
        units = (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("Ko", 1024))
        zero = "o"
    else:
        units = (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024))
        zero = "B"
    for unit, step in units:
        if value >= step:
            return f"{value / step:.2f} {unit}"
    return f"{value} {zero}"


class QuotaTracker:
    """Folder usage + reservations in flight, thread-safe."""

    def __init__(self, directory, limit_bytes: int = 0, lang: str = "en"):
        self.directory = directory
        self.lang = lang
        try:
            # Negative = inconsistent quota (config edited by hand): treat it
            # as "disabled" rather than as a limit that refuses everything.
            # The UI, for its part, already rejects negative values.
            self.limit_bytes = max(0, int(limit_bytes or 0))
        except (TypeError, ValueError):
            self.limit_bytes = 0
        self._reserved = 0
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.limit_bytes > 0

    def usage(self) -> int:
        """Bytes already in use (folder files + uploads in progress).

        The folder scan deliberately runs OUTSIDE the lock: the phone polls
        this every 5 s, and a slow tree (large folder, OneDrive placeholders,
        antivirus on the file just uploaded) would otherwise block every
        reserve()/release() - and with them the uploads themselves.
        """
        used = directory_usage(self.directory)
        with self._lock:
            return used + self._reserved

    def remaining(self) -> int:
        if not self.enabled:
            return -1
        used = directory_usage(self.directory)
        with self._lock:
            return max(0, self.limit_bytes - used - self._reserved)

    def reserve(self, additional: int) -> None:
        """Check the quota, then hold `additional` bytes in reserve.

        Raises QuotaExceededError (507) if the upload would push usage over
        the quota. Every reservation must be paired with a release in a
        finally block.
        """
        if not self.enabled:
            return
        additional = max(0, int(additional))
        with self._lock:
            used = directory_usage(self.directory) + self._reserved
            if used + additional > self.limit_bytes:
                if self.lang == "fr":
                    raise QuotaExceededError(
                        "Quota global atteint : "
                        f"{format_size(used, self.lang)} utilise sur "
                        f"{format_size(self.limit_bytes, self.lang)}")
                raise QuotaExceededError(
                    "Global quota reached: "
                    f"{format_size(used, self.lang)} used of "
                    f"{format_size(self.limit_bytes, self.lang)}")
            self._reserved += additional

    def release(self, additional: int) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._reserved = max(0, self._reserved - max(0, int(additional)))
