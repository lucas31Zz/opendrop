#!/usr/bin/env bash
# OpenDrop - Linux installer (the Windows setup equivalent).
#
# Installs the application into /opt/opendrop, creates a venv with the
# PROVIDED dependencies (offline, wheels included), and adds a shortcut
# to the applications menu.
#
# User data (never in /opt):
#   ~/.opendrop/            config.json, session.json, certs/  -> cleaned by uninstall.sh
#   ~/Downloads/OpenDrop/   Received and Shared folders        -> NEVER deleted
#
# Overridable variables (for tests): PREFIX, BIN_LINK, DESKTOP_FILE, ICON_FILE, PYTHON
set -euo pipefail

PREFIX="${PREFIX:-/opt/opendrop}"
BIN_LINK="${BIN_LINK:-/usr/local/bin/opendrop-desktop}"
DESKTOP_FILE="${DESKTOP_FILE:-/usr/share/applications/opendrop.desktop}"
ICON_FILE="${ICON_FILE:-/usr/share/icons/hicolor/256x256/apps/opendrop.png}"
PYTHON="${PYTHON:-python3}"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== OpenDrop: installing =="

# --- privileges: we need to write to /opt and /usr/local (unless PREFIX is custom)
if [ ! -w "$(dirname "$PREFIX")" ]; then
    if [ "$(id -u)" -ne 0 ]; then
        echo "Error: this script must be run with sudo:" >&2
        echo "    sudo ./install.sh" >&2
        exit 1
    fi
fi

# --- bundle contents
for item in OpenDrop src web pyproject.toml requirements.txt wheels; do
    if [ ! -e "$SRC_DIR/$item" ]; then
        echo "Error: '$item' is missing from the bundle." >&2
        echo "Download the official archive from the GitHub releases." >&2
        exit 1
    fi
done

# --- Python 3.10+
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Error: $PYTHON not found." >&2
    echo "Install Python 3.10+:  sudo apt install python3 python3-venv" >&2
    exit 1
fi
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)'; then
    echo "Error: $PYTHON is too old (Python 3.10+ is required)." >&2
    exit 1
fi

# --- copy the application
echo "  Installing into $PREFIX ..."
mkdir -p "$PREFIX"
for item in OpenDrop src web pyproject.toml requirements.txt; do
    cp -R "$SRC_DIR/$item" "$PREFIX/"
done
cp "$SRC_DIR/install.sh" "$SRC_DIR/uninstall.sh" "$SRC_DIR/opendrop.desktop.in" \
   "$SRC_DIR/opendrop.png" "$PREFIX/" 2>/dev/null || true
chmod +x "$PREFIX/OpenDrop" "$PREFIX/install.sh" "$PREFIX/uninstall.sh" 2>/dev/null || true

# --- venv + offline dependencies (wheels included)
echo "  Creating the venv and installing the dependencies (offline) ..."
if ! "$PYTHON" -m venv "$PREFIX/venv"; then
    echo "Error: could not create the venv." >&2
    echo "On Debian/Kali:  sudo apt install python3-venv" >&2
    exit 1
fi
if ! "$PREFIX/venv/bin/pip" install --quiet --no-index --find-links "$SRC_DIR/wheels" \
        --requirement "$PREFIX/requirements.txt"; then
    echo "Error: could not install the dependencies (are the wheels included?)." >&2
    exit 1
fi

# --- command shortcut + applications menu
echo "  Creating shortcuts ..."
ln -sf "$PREFIX/OpenDrop" "$BIN_LINK"
if [ "$(id -u)" -eq 0 ] || [ -w "$(dirname "$DESKTOP_FILE")" ] 2>/dev/null; then
    mkdir -p "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")"
    sed -e "s|^Exec=.*|Exec=$BIN_LINK|" \
        -e "s|^Icon=.*|Icon=$ICON_FILE|" \
        "$PREFIX/opendrop.desktop.in" > "$DESKTOP_FILE"
    cp "$PREFIX/opendrop.png" "$ICON_FILE"
else
    echo "  (no permission for the applications menu: command shortcut OK)"
fi

echo
echo "== Installed =="
echo "  Launch:     $BIN_LINK   (or 'OpenDrop' from the menu)"
echo "  Data:       ~/.opendrop/          (config, session, certificates)"
echo "  Received:   ~/Downloads/OpenDrop  (Received folder)"
echo "  Shared:     ~/Downloads/OpenDrop/Partage"
echo
echo "  Uninstall (cleans the app + ~/.opendrop, NEVER the Received"
echo "  and Shared folders):   sudo ./uninstall.sh"
