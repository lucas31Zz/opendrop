#!/usr/bin/env bash
# OpenDrop - installation Linux (equivalent du setup Windows).
#
# Installe l'application dans /opt/opendrop, cree un venv avec les
# dependances FOURNIES (hors-ligne, wheels fournis), pose un raccourci
# dans le menu d'applications.
#
# Donnees utilisateur (jamais dans /opt) :
#   ~/.opendrop/            config.json, session.json, certs/  -> nettoyes par uninstall.sh
#   ~/Downloads/OpenDrop/   dossiers Recus et Partage          -> JAMAIS supprimes
#
# Variables redefinissables (tests) : PREFIX, BIN_LINK, DESKTOP_FILE, ICON_FILE, PYTHON
set -euo pipefail

PREFIX="${PREFIX:-/opt/opendrop}"
BIN_LINK="${BIN_LINK:-/usr/local/bin/opendrop-desktop}"
DESKTOP_FILE="${DESKTOP_FILE:-/usr/share/applications/opendrop.desktop}"
ICON_FILE="${ICON_FILE:-/usr/share/icons/hicolor/256x256/apps/opendrop.png}"
PYTHON="${PYTHON:-python3}"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== OpenDrop : installation =="

# --- privilege : il faut ecrire dans /opt et /usr/local (sauf PREFIX custom)
if [ ! -w "$(dirname "$PREFIX")" ]; then
    if [ "$(id -u)" -ne 0 ]; then
        echo "Erreur : ce script doit etre lance avec sudo :" >&2
        echo "    sudo ./install.sh" >&2
        exit 1
    fi
fi

# --- contenu du bundle
for item in OpenDrop src web pyproject.toml requirements.txt wheels; do
    if [ ! -e "$SRC_DIR/$item" ]; then
        echo "Erreur : '$item' manquant dans le bundle." >&2
        echo "Telechargez l'archive officielle depuis les releases GitHub." >&2
        exit 1
    fi
done

# --- Python 3.10+
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Erreur : $PYTHON introuvable." >&2
    echo "Installez Python 3.10+ :  sudo apt install python3 python3-venv" >&2
    exit 1
fi
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)'; then
    echo "Erreur : $PYTHON est trop ancien (il faut Python 3.10+)." >&2
    exit 1
fi

# --- copie de l'application
echo "  Installation dans $PREFIX ..."
mkdir -p "$PREFIX"
for item in OpenDrop src web pyproject.toml requirements.txt; do
    cp -R "$SRC_DIR/$item" "$PREFIX/"
done
cp "$SRC_DIR/install.sh" "$SRC_DIR/uninstall.sh" "$SRC_DIR/opendrop.desktop.in" \
   "$SRC_DIR/opendrop.png" "$PREFIX/" 2>/dev/null || true
chmod +x "$PREFIX/OpenDrop" "$PREFIX/install.sh" "$PREFIX/uninstall.sh" 2>/dev/null || true

# --- venv + dependances hors-ligne (wheels fournis)
echo "  Creation du venv et installation des dependances (hors-ligne) ..."
if ! "$PYTHON" -m venv "$PREFIX/venv"; then
    echo "Erreur : creation du venv impossible." >&2
    echo "Sur Debian/Kali :  sudo apt install python3-venv" >&2
    exit 1
fi
if ! "$PREFIX/venv/bin/pip" install --quiet --no-index --find-links "$SRC_DIR/wheels" \
        --requirement "$PREFIX/requirements.txt"; then
    echo "Erreur : installation des dependances impossible (wheels fournis ?)." >&2
    exit 1
fi

# --- raccourci de commande + menu d'applications
echo "  Raccourcis ..."
ln -sf "$PREFIX/OpenDrop" "$BIN_LINK"
if [ "$(id -u)" -eq 0 ] || [ -w "$(dirname "$DESKTOP_FILE")" ] 2>/dev/null; then
    mkdir -p "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")"
    sed -e "s|^Exec=.*|Exec=$BIN_LINK|" \
        -e "s|^Icon=.*|Icon=$ICON_FILE|" \
        "$PREFIX/opendrop.desktop.in" > "$DESKTOP_FILE"
    cp "$PREFIX/opendrop.png" "$ICON_FILE"
else
    echo "  (pas les droits pour le menu d'applications : raccourci commande OK)"
fi

echo
echo "== Installe =="
echo "  Lancement :   $BIN_LINK   (ou 'OpenDrop' depuis le menu)"
echo "  Donnees :     ~/.opendrop/          (config, session, certificats)"
echo "  Reception :   ~/Downloads/OpenDrop  (dossier Recus)"
echo "  Partage :     ~/Downloads/OpenDrop/Partage"
echo
echo "  Desinstallation (nettoie l'app + ~/.opendrop, JAMAIS les dossiers"
echo "  Recus et Partage) :   sudo ./uninstall.sh"
