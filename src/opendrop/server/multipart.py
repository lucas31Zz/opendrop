import hashlib
import os
from pathlib import Path

from opendrop.security.validation import sanitize_filename, is_safe_path
from opendrop.server.errors import DiskError

CHUNK_SIZE = 64 * 1024

# Limites de lecture des petites parties du corps (jamais le fichier lui-meme)
MAX_PREAMBLE = 64 * 1024    # avant la premiere frontiere
MAX_LINE = 8 * 1024         # fin de ligne de la frontiere
MAX_HEADERS = 16 * 1024     # en-tetes de la partie


class _BodyReader:
    """Lecture flux du corps de requete, strictement bornee a content_length."""

    def __init__(self, rfile, limit: int):
        self._rfile = rfile
        self._left = max(0, limit)
        self._buf = bytearray()

    @property
    def eof(self) -> bool:
        return not self._buf and self._left <= 0

    def _fill(self, want: int = CHUNK_SIZE) -> int:
        if self._left <= 0:
            return 0
        n = min(want, self._left, CHUNK_SIZE)
        chunk = self._rfile.read(n)
        if not chunk:
            self._left = 0
            return 0
        self._left -= len(chunk)
        self._buf += chunk
        return len(chunk)

    def read_some(self, max_bytes: int) -> bytes:
        if not self._buf:
            self._fill()
        if not self._buf:
            return b""
        take = min(max_bytes, len(self._buf))
        data = bytes(self._buf[:take])
        del self._buf[:take]
        return data

    def read_until(self, marker: bytes, max_size: int) -> bytes | None:
        """Donnees avant marker (marker consomme). None si absent/trop grand/EOF."""
        while True:
            idx = self._buf.find(marker)
            if idx >= 0:
                data = bytes(self._buf[:idx])
                del self._buf[:idx + len(marker)]
                return data
            if len(self._buf) >= max_size:
                return None
            if self._fill() == 0:
                return None


def extract_boundary(content_type: str) -> str | None:
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[len("boundary="):].strip().strip('"')
            return boundary or None
    return None


def _extract_filename(headers_raw: str) -> str | None:
    for line in headers_raw.replace("\r\n", "\n").split("\n"):
        if "Content-Disposition" not in line:
            continue
        for p in line.split(";"):
            p = p.strip()
            if p.startswith("filename="):
                return p.split("=", 1)[1].strip('" ') or None
    return None


def _os_reason(e: OSError) -> str:
    """Raison courte d'une OSError, sans le chemin de fichier.

    str(e) contient le nom complet ("[Errno 28] ...: 'C:\\...'") : ce
    message part en reponse HTTP, il ne doit donc rien dire sur l'arborescence
    du serveur (voir SECURITY.md, "Chemin absolus").
    """
    reason = e.strerror or e.__class__.__name__
    return f"[Errno {e.errno}] {reason}" if e.errno else reason


def _open_dest(dest_dir: Path, safe_name: str):
    """Cree le fichier de destination en excluant les concurrents (mode xb)."""
    stem, ext = os.path.splitext(safe_name)
    counter = 0
    name = safe_name
    while True:
        dest = dest_dir / name
        try:
            return open(dest, "xb"), name
        except FileExistsError:
            counter += 1
            name = f"{stem} ({counter}){ext}"
        except OSError as e:
            raise DiskError(f"Impossible de creer le fichier: {_os_reason(e)}") from e


def _copy_file(reader: _BodyReader, out, end_marker: bytes, on_progress=None):
    """Ecrit le contenu du fichier par blocs jusqu'a end_marker.

    Retourne le hash SHA-256, ou None si le corps s'est termine avant la
    frontiere finale (upload tronque).
    """
    pending = bytearray()
    sha256 = hashlib.sha256()
    written = 0
    margin = len(end_marker) - 1

    def write(data: bytes) -> None:
        nonlocal written
        if not data:
            return
        try:
            out.write(data)
        except OSError as e:
            raise DiskError(f"Erreur d'ecriture sur disque: {_os_reason(e)}") from e
        sha256.update(data)
        written += len(data)
        if on_progress:
            on_progress(written)

    while True:
        idx = pending.find(end_marker)
        if idx >= 0:
            after = idx + len(end_marker)
            while len(pending) < after + 2 and not reader.eof:
                pending += reader.read_some(after + 2 - len(pending))
            follow = bytes(pending[after:after + 2])
            if not follow or reader.eof or follow[:2] == b"--" or follow[:1] in (b"\r", b"\n"):
                write(bytes(pending[:idx]))
                return sha256.hexdigest()
            # faux positif : la sequence trouvee fait partie du fichier
            write(bytes(pending[:after]))
            del pending[:after]
            continue

        if reader.eof:
            return None

        if len(pending) > margin:
            cut = len(pending) - margin
            write(bytes(pending[:cut]))
            del pending[:cut]

        pending += reader.read_some(CHUNK_SIZE)


def parse_multipart_upload(rfile, content_type, content_length, download_dir, on_progress=None):
    boundary = extract_boundary(content_type)
    if not boundary:
        return None, "no boundary", None

    sep = b"--" + boundary.encode()
    end_marker = b"\r\n" + sep
    reader = _BodyReader(rfile, content_length)

    # 1) premiere frontiere (le preambule eventuel est ignore)
    if reader.read_until(sep, MAX_PREAMBLE) is None:
        return None, "no start boundary", None

    # 2) fin de ligne de la frontiere (ou frontiere finale sans partie)
    line = reader.read_until(b"\n", MAX_LINE)
    if line is None:
        return None, "no header separator", None
    if line.rstrip(b"\r") == b"--":
        return None, "no filename", None

    # 3) en-tetes de la partie
    headers_raw = reader.read_until(b"\r\n\r\n", MAX_HEADERS)
    if headers_raw is None:
        headers_raw = reader.read_until(b"\n\n", MAX_HEADERS)
        if headers_raw is None:
            return None, "no header separator", None

    filename = _extract_filename(headers_raw.decode("utf-8", errors="replace"))
    if not filename:
        return None, "no filename", None

    safe_name = sanitize_filename(filename)
    dest_dir = Path(download_dir)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise DiskError(
            f"Impossible de creer le dossier de reception: {_os_reason(e)}") from e

    if not is_safe_path(str(dest_dir), safe_name):
        return None, "unsafe filename", None

    out, safe_name = _open_dest(dest_dir, safe_name)
    dest = dest_dir / safe_name

    try:
        digest = _copy_file(reader, out, end_marker, on_progress)
    except BaseException:
        _close_quiet(out)
        _remove_quiet(dest)
        raise

    # Le flush final echoue parfois au dernier bloc (disque plein) : le
    # fichier serait alors tronque sur disque alors que le hash couvre tout
    # le corps lu. On traite l'erreur, on supprime le fichier, et aucun
    # hash n'est rendu.
    try:
        out.close()
    except OSError as e:
        _close_quiet(out)
        _remove_quiet(dest)
        raise DiskError(f"Erreur d'ecriture sur disque: {_os_reason(e)}") from e

    if digest is None:
        _remove_quiet(dest)
        return None, "Transfert interrompu ou incomplet", None

    return safe_name, None, digest


def _close_quiet(f) -> None:
    try:
        f.close()
    except OSError:
        pass


def _remove_quiet(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
