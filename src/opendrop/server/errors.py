import traceback
import sys


class OpenDropError(Exception):
    status = 500
    message = "Erreur interne du serveur"

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


class TokenInvalidError(OpenDropError):
    status = 403
    message = "Token de session invalide"


class TokenExpiredError(OpenDropError):
    status = 403
    message = "Token de session expire"


class OriginForbiddenError(OpenDropError):
    status = 403
    message = "Origine non autorisee"


class RateLimitError(OpenDropError):
    status = 429
    message = "Trop de requetes, reessayez dans un moment"


class UploadError(OpenDropError):
    status = 400
    message = "Erreur lors de l'envoi du fichier"


class MultipartParseError(UploadError):
    message = "Format de fichier invalide"


class FilenameInvalidError(UploadError):
    message = "Nom de fichier invalide"


class FilenameUnsafeError(UploadError):
    message = "Nom de fichier non autorise"


class FileTooLargeError(UploadError):
    message = "Fichier trop volumineux"


class DownloadError(OpenDropError):
    status = 404
    message = "Fichier introuvable"


class FileDeletedError(DownloadError):
    message = "Le fichier a ete supprime"


class DiskError(OpenDropError):
    status = 507
    message = "Espace disque insuffisant ou erreur d'ecriture"


class QuotaExceededError(OpenDropError):
    status = 507
    message = "Quota global du dossier de reception atteint"


def format_error_response(exc: Exception) -> dict:
    if isinstance(exc, OpenDropError):
        return {"error": exc.message, "code": exc.status}
    return {"error": "Erreur interne du serveur", "code": 500}


def log_error(exc: Exception, context: str = "") -> None:
    prefix = f"[OpenDrop ERROR] {context}" if context else "[OpenDrop ERROR]"
    print(f"{prefix}: {exc}", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr)
