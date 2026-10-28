#!/usr/bin/env bash
# Builds the Linux archive shipped with the releases:
#   dist/OpenDrop-<tag>-linux-x64.tar.gz
# containing: Tauri desktop binary + src/ + web/ + wheels + install.sh +
# uninstall.sh + menu entry.
#
# Usage: packaging/linux/build-tarball.sh <tag>     (from the repo root)
set -euo pipefail

TAG="${1:-dev}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LINUX_DIR="$ROOT/packaging/linux"
PUBLISH_DIR="${PUBLISH_DIR:-$ROOT/publish/linux}"
OUT_DIR="$ROOT/dist"
STAGE_ROOT="$OUT_DIR/stage"
STAGE="$STAGE_ROOT/OpenDrop"

echo "== Building the Linux bundle $TAG =="

rm -rf "$STAGE_ROOT"
mkdir -p "$STAGE" "$OUT_DIR"

# Staged binary (Tauri release, renamed to OpenDrop) + its neighbours
test -d "$PUBLISH_DIR" || { echo "Error: $PUBLISH_DIR missing (copy the Tauri release binary + web/ into it)." >&2; exit 1; }
cp -R "$PUBLISH_DIR"/. "$STAGE/"

# web/ from the repo, so the archive never depends on what CI staged
# (self-correcting if the job forgot it: install.sh refuses a bundle
# without web/). Replaced, not merged: cp -R into an existing directory
# would nest it as web/web when the publish dir already shipped one.
rm -rf "$STAGE/web"
cp -R "$ROOT/web" "$STAGE/web"

# Python server + metadata
cp -R "$ROOT/src" "$STAGE/src"
cp "$ROOT/pyproject.toml" "$ROOT/requirements.txt" "$ROOT/README.md" \
   "$ROOT/LICENSE" "$ROOT/SECURITY.md" "$STAGE/"

# Install/menu scripts + icon
cp "$LINUX_DIR/install.sh" "$LINUX_DIR/uninstall.sh" \
   "$LINUX_DIR/opendrop.desktop.in" "$LINUX_DIR/opendrop.png" "$STAGE/"

# Offline wheels (native Linux deps, same versions as requirements.txt)
# for each minor Python version: pillow/cffi depend on the ABI.
echo "  Downloading the wheels ..."
for v in 3.10 3.11 3.12 3.13 3.14 3.15; do
    python3 -m pip download --quiet --requirement "$ROOT/requirements.txt" \
        --dest "$STAGE/wheels" --only-binary=:all: --python-version "$v" \
        || { echo "Error: Python $v wheels are unavailable." >&2; exit 1; }
done

chmod +x "$STAGE/OpenDrop" "$STAGE/install.sh" "$STAGE/uninstall.sh"

# Minimal sanity checks
test -f "$STAGE/web/index.html"
test -f "$STAGE/src/opendrop/main.py"
test -f "$STAGE/pyproject.toml"
ls "$STAGE"/wheels/*.whl >/dev/null

ARCHIVE="$OUT_DIR/OpenDrop-$TAG-linux-x64.tar.gz"
tar -C "$STAGE_ROOT" -czf "$ARCHIVE" OpenDrop
echo "OK: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"
