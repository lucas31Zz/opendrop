import hashlib
import os
from pathlib import Path

from opendrop.security.validation import sanitize_filename, is_safe_path
from opendrop.server.errors import DiskError

CHUNK_SIZE = 64 * 1024

# Read limits for the small pieces of the body (never the file itself)
MAX_PREAMBLE = 64 * 1024    # before the first boundary
MAX_LINE = 8 * 1024         # end of the boundary line
MAX_HEADERS = 16 * 1024     # part headers


class _BodyReader:
    """Streaming reader for the request body, strictly bounded by content_length."""

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
        """Data before the marker (marker consumed). None if absent/too large/EOF."""
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
    """Short reason for an OSError, without the file path.

    str(e) contains the full name ("[Errno 28] ...: 'C:\\...'"): this message
    goes out in an HTTP response, so it must not reveal anything about the
    server's directory tree (see SECURITY.md, "Absolute paths").
    """
    reason = e.strerror or e.__class__.__name__
    return f"[Errno {e.errno}] {reason}" if e.errno else reason


def open_dest_exclusive(dest_dir: Path, safe_name: str):
    """Create the destination file, excluding competing writers (mode "xb").

    Public: the server also claims the final name with it when a chunked
    upload completes (before os.replace of the staging file).
    """
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
            raise DiskError(f"Cannot create file: {_os_reason(e)}") from e


def _copy_file(reader: _BodyReader, out, end_marker: bytes, on_progress=None):
    """Write the file content in blocks up to end_marker.

    Returns (SHA-256 hash, bytes written); the hash is None if the body
    ended before the final boundary (truncated upload).
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
            raise DiskError(f"Disk write error: {_os_reason(e)}") from e
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
                return sha256.hexdigest(), written
            # false positive: the sequence found is part of the file
            write(bytes(pending[:after]))
            del pending[:after]
            continue

        if reader.eof:
            return None, written

        if len(pending) > margin:
            cut = len(pending) - margin
            write(bytes(pending[:cut]))
            del pending[:cut]

        pending += reader.read_some(CHUNK_SIZE)


def _open_staging(dest_path: Path, offset: int):
    """Open a chunked-upload staging file for append at `offset`.

    Returns (handle, actual) where a success has actual=None, and a file
    shorter than offset has handle=None with actual set to its real size
    (the caller answers a 409 resync carrying that size). A tail left by
    a lost response or a killed write is truncated back to offset, which
    is what makes a slice retry idempotent.
    """
    if offset == 0:
        try:
            return open(dest_path, "w+b"), None      # truncate or create
        except OSError as e:
            raise DiskError(f"Cannot create file: {_os_reason(e)}") from e
    try:
        f = open(dest_path, "r+b")
    except FileNotFoundError:
        return None, 0
    except OSError as e:
        raise DiskError(f"Cannot open file: {_os_reason(e)}") from e
    try:
        actual = f.seek(0, os.SEEK_END)
        if actual < offset:
            _close_quiet(f)
            return None, actual
        if actual > offset:
            f.truncate(offset)
        f.seek(offset)
    except OSError as e:
        _close_quiet(f)
        raise DiskError(f"Disk write error: {_os_reason(e)}") from e
    return f, None


def parse_multipart_upload(rfile, content_type, content_length, download_dir,
                           on_progress=None, staging=None):
    """Parse one multipart upload request.

    staging=None is the legacy single-shot: the destination is created
    exclusively (uniquified) from the part's filename and removed on any
    failure. staging=(dest_path, offset) is one slice of a chunked send:
    dest_path (already validated by the caller) is appended at offset,
    a shorter file answers a resync, and committed bytes always survive
    a failure so the next slice can retry.

    Returns (safe_name, error, digest, committed): `committed` is the
    byte count on disk after the request (the final size in legacy mode).
    """
    boundary = extract_boundary(content_type)
    if not boundary:
        return None, "no boundary", None, 0

    sep = b"--" + boundary.encode()
    end_marker = b"\r\n" + sep
    reader = _BodyReader(rfile, content_length)

    # 1) first boundary (any preamble is ignored)
    if reader.read_until(sep, MAX_PREAMBLE) is None:
        return None, "no start boundary", None, 0

    # 2) end of the boundary line (or final boundary with no part)
    line = reader.read_until(b"\n", MAX_LINE)
    if line is None:
        return None, "no header separator", None, 0
    if line.rstrip(b"\r") == b"--":
        return None, "no filename", None, 0

    # 3) part headers
    headers_raw = reader.read_until(b"\r\n\r\n", MAX_HEADERS)
    if headers_raw is None:
        headers_raw = reader.read_until(b"\n\n", MAX_HEADERS)
        if headers_raw is None:
            return None, "no header separator", None, 0

    # The stream must advance in every mode, but a slice's filename is
    # the query's (the server validated it and built dest_path from it):
    # the part's own disposition is not trusted here.
    filename = _extract_filename(headers_raw.decode("utf-8", errors="replace"))
    if not filename and staging is None:
        return None, "no filename", None, 0

    dest_dir = Path(download_dir)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise DiskError(
            f"Cannot create receive folder: {_os_reason(e)}") from e

    if staging is not None:
        dest_path, offset = staging
        dest = dest_path
        safe_name = dest_path.name
        if not is_safe_path(str(dest_dir), safe_name):
            return None, "unsafe filename", None, 0
        out, actual = _open_staging(dest_path, offset)
        if out is None:
            return safe_name, "offset mismatch", None, actual
    else:
        offset = 0
        safe_name = sanitize_filename(filename)
        if not is_safe_path(str(dest_dir), safe_name):
            return None, "unsafe filename", None, 0
        out, safe_name = open_dest_exclusive(dest_dir, safe_name)
        dest = dest_dir / safe_name

    try:
        digest, written = _copy_file(reader, out, end_marker, on_progress)
    except BaseException:
        _close_quiet(out)
        # A slice keeps whatever landed: the retry re-truncates to its
        # offset. Only a legacy upload cleans up after itself.
        if staging is None:
            _remove_quiet(dest)
        raise

    # The final flush sometimes fails on the last block (disk full): the file
    # would then be truncated on disk even though the hash covers the whole
    # body that was read. Handle the error, delete the file, and return no
    # hash.
    try:
        out.close()
    except OSError as e:
        _close_quiet(out)
        if staging is None:
            _remove_quiet(dest)
        raise DiskError(f"Disk write error: {_os_reason(e)}") from e

    if digest is None:
        if staging is None:
            _remove_quiet(dest)
        return None, "Transfer interrupted or incomplete", None, 0

    try:
        committed = dest.stat().st_size
    except OSError:
        committed = written + offset

    return safe_name, None, digest, committed


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


def sha256_file(path: Path) -> str:
    """SHA-256 of a whole file, read back in blocks.

    Used for the final slice of a chunked upload: the per-slice digests
    cannot be combined, and the server is stateless between requests, so
    the one honest way to answer with the whole-file hash is a pass over
    what landed on disk.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK_SIZE)
            if not block:
                break
            h.update(block)
    return h.hexdigest()
