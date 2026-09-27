#!/usr/bin/env bash
# OpenDrop - desinstallation Linux (equivalent de l'uninstalleur Windows).
#
# SUPPRIME : /opt/opendrop (binaire, venv, web, src), le raccourci de
# commande, l'entree de menu, et les donnees applicatives de l'utilisateur
# (~/.opendrop/config.json, session.json, server.pid, certs/).
#
# NE SUPPRIME JAMAIS : les dossiers de reception et de partage (fichiers
# recus et partages, generalement ~/Downloads/OpenDrop). Leur chemin est lu
# dans config.json avant nettoyage, on ne les touche pas.
#
# Variables redefinissables (tests) : PREFIX, BIN_LINK, DESKTOP_FILE, ICON_FILE
set -euo pipefail

PREFIX="${PREFIX:-/opt/opendrop}"
BIN_LINK="${BIN_LINK:-/usr/local/bin/opendrop-desktop}"
DESKTOP_FILE="${DESKTOP_FILE:-/usr/share/applications/opendrop.desktop}"
ICON_FILE="${ICON_FILE:-/usr/share/icons/hicolor/256x256/apps/opendrop.png}"

echo "== OpenDrop : desinstallation =="

# --- utilisateur reel (sudo) et sa donnee utilisateur
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "$TARGET_USER" 2>/dev/null | cut -d: -f6)"
if [ -z "${TARGET_HOME:-}" ]; then
    TARGET_HOME="$(eval echo "~$TARGET_USER" 2>/dev/null || echo "$HOME")"
fi
DATA_DIR="$TARGET_HOME/.opendrop"

# --- arreter l'application et son serveur Python s'ils tournent
pkill -x OpenDrop 2>/dev/null || true
if [ -f "$DATA_DIR/server.pid" ]; then
    PID="$(cut -d'|' -f1 "$DATA_DIR/server.pid" 2>/dev/null || true)"
    if [ -n "${PID:-}" ] && [ -d "/proc/$PID" ]; then
        kill "$PID" 2>/dev/null || true
    fi
fi

# --- rappele les dossiers conserves AVANT d'effacer la config
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
        echo "  Dossiers conserves (jamais supprimes) :"
        echo "$DOWNS" | sed 's/^/    /'
    fi
fi

# --- application
if [ -e "$PREFIX" ]; then
    echo "  Suppression de $PREFIX ..."
    rm -rf "$PREFIX"
fi
rm -f "$BIN_LINK" "$DESKTOP_FILE" "$ICON_FILE"

# --- donnees applicatives connues SEULEMENT (pas de rm -rf du dossier)
if [ -d "$DATA_DIR" ]; then
    echo "  Nettoyage de $DATA_DIR (config, session, certificats) ..."
    rm -f "$DATA_DIR/config.json" "$DATA_DIR/session.json" "$DATA_DIR/server.pid"
    rm -rf "$DATA_DIR/certs"
    rmdir "$DATA_DIR" 2>/dev/null || true
fi

echo
echo "== Desinstalle =="
echo "  L'application, ses dependances et sa config sont retirees."
echo "  Vos fichiers recus et partages sont INTACTS (voir liste ci-dessus)."
