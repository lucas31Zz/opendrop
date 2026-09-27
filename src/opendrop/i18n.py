"""English/French message catalogue.

English is the canonical language: every key is the English text itself,
and the French translations live in the table below. Unknown keys fall
back to English, so a missing translation never breaks the server.

The active language comes from the "language" config key ("en" by
default, "fr" for French). Use normalize_lang() before trusting any
value read from config or from a client.
"""

from __future__ import annotations

DEFAULT_LANG = "en"

# English text -> French translation.
_TEXT_FR: dict[str, str] = {
    # Generic fallback
    "Internal server error": "Erreur interne du serveur",
    "Error": "Erreur",
    "Error:": "Erreur :",
    # Token / session
    "Invalid session token": "Token de session invalide",
    "Session token expired": "Token de session expire",
    "Missing session token": "Token manquant",
    "Invalid session code": "Code de session invalide",
    "Origin not allowed": "Origine non autorisee",
    # Rate limiting
    "Too many requests, try again in a moment":
        "Trop de requetes, reessayez dans un moment",
    "Too many uploads, try again in a moment":
        "Trop d'envois, reessayez dans un moment",
    # Upload
    "Upload failed": "Erreur lors de l'envoi du fichier",
    "Invalid file format": "Format de fichier invalide",
    "Invalid request format": "Format de requete invalide",
    "Invalid file name": "Nom de fichier invalide",
    "File name not allowed": "Nom de fichier non autorise",
    "File too large": "Fichier trop volumineux",
    "File too large (max 10 GB)": "Fichier trop volumineux (max 10 Go)",
    "Cannot read the uploaded file": "Impossible de lire le fichier envoye",
    "File read error": "Erreur de lecture du fichier",
    # Download
    "File not found": "Fichier introuvable",
    "The file has been deleted": "Le fichier a ete supprime",
    "The path does not match a file": "Le chemin ne correspond pas a un fichier",
    "Cannot access the file": "Impossible d'acceder au fichier",
    "Path not allowed": "Chemin non autorise",
    "Cannot read the share folder": "Impossible de lire le dossier de partage",
    # Disk / quota
    "Not enough disk space or write error":
        "Espace disque insuffisant ou erreur d'ecriture",
    "Global receive quota reached":
        "Quota global du dossier de reception atteint",
    # Misc routes
    "Unknown route": "Route inconnue",
    "QR code unavailable": "QR code non disponible",
    # Port conflicts (raised by create_server)
    "Another OpenDrop server is already running on port {port}.":
        "Un autre serveur OpenDrop tourne deja sur le port {port}.",
    "Port {port} is already in use by another program.":
        "Le port {port} est deja utilise par un autre programme.",
    # Console banner (opendrop.main)
    "Server:": "Serveur:",
    "Web interface:": "Interface web:",
    "Session code:": "Code session:",
    "Received in:": "Recus dans:",
    "Shared from:": "Partage depuis:",
    "Drop files into the Share folder to share them.":
        "Mets des fichiers dans le dossier Partage pour les partager.",
    "Scan the QR code with your device.":
        "Scanner le QR code avec votre appareil.",
    "HTTPS: self-signed certificate; accept the browser warning on first access.":
        "HTTPS : certificat auto-signe, acceptez l'avertissement au 1er acces.",
    "Press Ctrl+C to stop.": "Ctrl+C pour arreter.",
    "Server stopped.": "Serveur arrete.",
    "An older server is probably still running: stop it,":
        "Un ancien serveur tourne probablement encore : arretez-le,",
    "then start OpenDrop again.": "puis relancez OpenDrop.",
}


def normalize_lang(lang: object) -> str:
    """Return "fr" for French, "en" for anything else."""
    if isinstance(lang, str) and lang.strip().lower().startswith("fr"):
        return "fr"
    return DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Translate an English key, then format it with any placeholders."""
    text = _TEXT_FR.get(key, key) if normalize_lang(lang) == "fr" else key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def translate_error(message: str, lang: str = DEFAULT_LANG) -> str:
    """Translate a canonical English error message.

    Dynamic messages (built with numbers or file names) are not in the
    catalogue and pass through unchanged.
    """
    if normalize_lang(lang) == "fr":
        return _TEXT_FR.get(message, message)
    return message
