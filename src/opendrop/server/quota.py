"""Quota global du dossier de reception.

MAX_UPLOAD_SIZE borne chaque fichier separement ; ce module ajoute la
limite cumulee : a chaque envoi le dossier de reception est scanne (taille
totale des fichiers), et la place annoncee par Content-Length est reservee
pendant la duree de l'envoi.

La reservation est exacte : le corps de la requete est strictement borne a
Content-Length, un fichier ne peut donc jamais ecrire plus que la valeur
reservee, meme avec deux envois simultanes.

Le quota est optionnel : 0 (ou cle absente) = illimite.
"""
import os
import threading
from pathlib import Path

from opendrop.server.errors import QuotaExceededError


def directory_usage(path) -> int:
    """Taille totale en octets des fichiers du dossier, recursivement."""
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


def format_size(value: int) -> str:
    """Format court et lisible : 1536 -> '1.5 Ko'."""
    value = int(value)
    for unit, step in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("Ko", 1024)):
        if value >= step:
            return f"{value / step:.2f} {unit}"
    return f"{value} o"


class QuotaTracker:
    """Usage du dossier + reservations en cours, de facon thread-safe."""

    def __init__(self, directory, limit_bytes: int = 0):
        self.directory = directory
        try:
            # Negative = quota incoherent (config editee a la main) : on le
            # traite comme "desactive" plutot que comme une limite refusant
            # tout. L'interface, elle, refuse deja les valeurs negatives.
            self.limit_bytes = max(0, int(limit_bytes or 0))
        except (TypeError, ValueError):
            self.limit_bytes = 0
        self._reserved = 0
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.limit_bytes > 0

    def usage(self) -> int:
        """Octets deja occupes (fichiers du dossier + envois en cours)."""
        with self._lock:
            return directory_usage(self.directory) + self._reserved

    def remaining(self) -> int:
        if not self.enabled:
            return -1
        with self._lock:
            return max(0, self.limit_bytes - directory_usage(self.directory) - self._reserved)

    def reserve(self, additional: int) -> None:
        """Verifie la quota puis garde `additional` octets de reserve.

        Leve QuotaExceededError (507) si l'envoi ferait depasser le quota.
        Chaque reserve doit etre couplee a un release dans un finally.
        """
        if not self.enabled:
            return
        additional = max(0, int(additional))
        with self._lock:
            used = directory_usage(self.directory) + self._reserved
            if used + additional > self.limit_bytes:
                raise QuotaExceededError(
                    "Quota global atteint : "
                    f"{format_size(used)} utilise sur "
                    f"{format_size(self.limit_bytes)}")
            self._reserved += additional

    def release(self, additional: int) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._reserved = max(0, self._reserved - max(0, int(additional)))
