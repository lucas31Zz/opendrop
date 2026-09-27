#!/usr/bin/env bash
# Assemble l'archive Linux distribuee dans les releases :
#   dist/OpenDrop-<tag>-linux-x64.tar.gz
# contenant : binaire self-contained + src/ + web/ + wheels + install.sh +
# uninstall.sh + entree de menu.
#
# Usage : packaging/linux/build-tarball.sh <tag>     (depuis la racine)
set -euo pipefail

TAG="${1:-dev}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LINUX_DIR="$ROOT/packaging/linux"
PUBLISH_DIR="${PUBLISH_DIR:-$ROOT/publish/linux}"
OUT_DIR="$ROOT/dist"
STAGE_ROOT="$OUT_DIR/stage"
STAGE="$STAGE_ROOT/OpenDrop"

echo "== Assemblage du bundle Linux $TAG =="

rm -rf "$STAGE_ROOT"
mkdir -p "$STAGE" "$OUT_DIR"

# Binaire publie (single-file + lib natives + web/ via le csproj)
test -d "$PUBLISH_DIR" || { echo "Erreur : $PUBLISH_DIR absent (dotnet publish -r linux-x64)." >&2; exit 1; }
cp -R "$PUBLISH_DIR"/. "$STAGE/"

# Serveur Python + metadonnees
cp -R "$ROOT/src" "$STAGE/src"
cp "$ROOT/pyproject.toml" "$ROOT/requirements.txt" "$ROOT/README.md" \
   "$ROOT/LICENSE" "$ROOT/SECURITY.md" "$STAGE/"

# Scripts d'installation/menu + icone
cp "$LINUX_DIR/install.sh" "$LINUX_DIR/uninstall.sh" \
   "$LINUX_DIR/opendrop.desktop.in" "$LINUX_DIR/opendrop.png" "$STAGE/"

# Wheels hors-ligne (dep natives linux, memmes versions que requirements.txt)
# pour chaque version mineure de Python : pillow/cffi dependent de l'ABI.
echo "  Telechargement des wheels ..."
for v in 3.10 3.11 3.12 3.13 3.14; do
    python3 -m pip download --quiet --requirement "$ROOT/requirements.txt" \
        --dest "$STAGE/wheels" --only-binary=:all: --python-version "$v" \
        || { echo "Erreur : wheels python $v indisponibles." >&2; exit 1; }
done

chmod +x "$STAGE/OpenDrop" "$STAGE/install.sh" "$STAGE/uninstall.sh"

# Verifications minimales
test -f "$STAGE/web/index.html"
test -f "$STAGE/src/opendrop/main.py"
test -f "$STAGE/pyproject.toml"
ls "$STAGE"/wheels/*.whl >/dev/null

ARCHIVE="$OUT_DIR/OpenDrop-$TAG-linux-x64.tar.gz"
tar -C "$STAGE_ROOT" -czf "$ARCHIVE" OpenDrop
echo "OK : $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"
