import os
import re

DANGEROUS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
DANGEROUS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_filename(name: str) -> str:
    name = os.path.basename(name)
    name = DANGEROUS_CHARS.sub("_", name)
    name = name.strip(". ")
    if not name:
        name = "unnamed_file"
    stem, ext = os.path.splitext(name)
    if stem.upper() in DANGEROUS_NAMES:
        stem = f"_{stem}"
    return stem + ext


def is_safe_path(base_dir: str, target: str) -> bool:
    resolved = os.path.realpath(os.path.join(base_dir, target))
    base = os.path.realpath(base_dir)
    return resolved.startswith(base + os.sep) or resolved == base
