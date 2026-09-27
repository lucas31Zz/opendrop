#!/usr/bin/env bash
# OpenDrop - Linux uninstaller (the Windows uninstaller equivalent).
#
# DELETES: /opt/opendrop (binary, venv, web, src), the command shortcut,
# the menu entry, and the user's application data
# (~/.opendrop/config.json, session.json, server.pid, certs/).
#
# NEVER DELETES: the receive and share folders (received and shared files,
# usually ~/Downloads/OpenDrop). Their paths are read from config.json
# before cleanup, so they are left untouched.
#
# Overridable variables (for tests): PREFIX, BIN_LINK, DESKTOP_FILE, ICON_FILE
set -euo pipefail

PREFIX="${PREFIX:-/opt/opendrop}"
BIN_LINK="${BIN_LINK:-/usr/local/bin/opendrop-desktop}"
DESKTOP_FILE="${DESKTOP_FILE:-/usr/share/applications/opendrop.desktop}"
ICON_FILE="${ICON_FILE:-/usr/share/icons/hicolor/256x256/apps/opendrop.png}"

echo "== OpenDrop: uninstalling =="

# --- real user (sudo) and their user data
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "$TARGET_USER" 2>/dev/null | cut -d: -f6)"
if [ -z "${TARGET_HOME:-}" ]; then
    TARGET_HOME="$(eval echo "~$TARGET_USER" 2>/dev/null || echo "$HOME")"
fi
DATA_DIR="$TARGET_HOME/.opendrop"

# --- stop the application and its Python server if they are running
pkill -x OpenDrop 2>/dev/null || true
if [ -f "$DATA_DIR/server.pid" ]; then
    PID="$(cut -d'|' -f1 "$DATA_DIR/server.pid" 2>/dev/null || true)"
    if [ -n "${PID:-}" ] && [ -d "/proc/$PID" ]; then
        kill "$PID" 2>/dev/null || true
    fi
fi

# --- remind which folders are kept BEFORE wiping the config
if [ -f "$DATA_DIR/config.json" ]; then
    DOWNS="$(python3 - "$DATA_DIR/config.json" <<'PY' 2>/dev/null || true
import json, sys, os
try:
    c = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    print(c.get("download_directory") or os.path.expanduser("~/Downloads/OpenDrop"))
    print(c.get("share_directory") or os.path.expanduser("~/Downloads/OpenDrop/Partage"))
except Exception:
    pass
PY
)"
    if [ -n "$DOWNS" ]; then
        echo "  Kept folders (never deleted):"
        echo "$DOWNS" | sed 's/^/    /'
    fi
fi

# --- application
if [ -e "$PREFIX" ]; then
    echo "  Removing $PREFIX ..."
    rm -rf "$PREFIX"
fi
rm -f "$BIN_LINK" "$DESKTOP_FILE" "$ICON_FILE"

# --- known application data ONLY (never rm -rf the whole folder)
if [ -d "$DATA_DIR" ]; then
    echo "  Cleaning up $DATA_DIR (config, session, certificates) ..."
    rm -f "$DATA_DIR/config.json" "$DATA_DIR/session.json" "$DATA_DIR/server.pid"
    rm -rf "$DATA_DIR/certs"
    rmdir "$DATA_DIR" 2>/dev/null || true
fi

echo
echo "== Uninstalled =="
echo "  The application, its dependencies and its config have been removed."
echo "  Your received and shared files are INTACT (see the list above)."
