import traceback
import sys

from opendrop.i18n import translate_error


class OpenDropError(Exception):
    status = 500
    message = "Internal server error"

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


class TokenInvalidError(OpenDropError):
    status = 403
    message = "Invalid session token"


class TokenExpiredError(OpenDropError):
    status = 403
    message = "Session token expired"


class OriginForbiddenError(OpenDropError):
    status = 403
    message = "Origin not allowed"


class RateLimitError(OpenDropError):
    status = 429
    message = "Too many requests, try again in a moment"


class UploadError(OpenDropError):
    status = 400
    message = "Upload failed"


class MultipartParseError(UploadError):
    message = "Invalid file format"


class FilenameInvalidError(UploadError):
    message = "Invalid file name"


class FilenameUnsafeError(UploadError):
    message = "File name not allowed"


class FileTooLargeError(UploadError):
    message = "File too large"


class DownloadError(OpenDropError):
    status = 404
    message = "File not found"


class FileDeletedError(DownloadError):
    message = "The file has been deleted"


class DiskError(OpenDropError):
    status = 507
    message = "Not enough disk space or write error"


class QuotaExceededError(OpenDropError):
    status = 507
    message = "Global receive quota reached"


# The message on the exception is always canonical English; translate at
# the edge so logs and tracebacks stay in one language.
def format_error_response(exc: Exception, lang: str = "en") -> dict:
    if isinstance(exc, OpenDropError):
        return {"error": translate_error(exc.message, lang), "code": exc.status}
    return {"error": translate_error("Internal server error", lang), "code": 500}


def log_error(exc: Exception, context: str = "") -> None:
    prefix = f"[OpenDrop ERROR] {context}" if context else "[OpenDrop ERROR]"
    print(f"{prefix}: {exc}", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr)
