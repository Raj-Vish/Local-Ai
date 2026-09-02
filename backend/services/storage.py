"""Safe file storage on the server's disk.

Three rules keep this boring rather than dangerous:

  1. The uploader's filename is never used to build a path. Files get a UUID
     name, so there is nothing for "../.." to escape with.
  2. A file's real type is read from its first bytes, not from its extension.
  3. Nothing is served from a browsable directory; every read goes through a
     route that checks ownership first.
"""
import hashlib
import re
import uuid
from pathlib import Path

import filetype
from fastapi import UploadFile

from config import settings

# Extensions are for display only. Membership here is decided by the sniffed
# MIME type below, never by what the file happens to be called.
ALLOWED_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

# Enough bytes for filetype to recognise every format we accept.
_SNIFF_BYTES = 512
_CHUNK = 1024 * 1024


class UploadRejected(Exception):
    """Raised with a message meant to be shown to the person uploading."""


def storage_root() -> Path:
    return Path(settings.STORAGE_ROOT)


def user_dir(user_id: int, kind: str = "documents") -> Path:
    """Per-user folder. Tidiness and easy backup -- NOT a security boundary.

    Isolation comes from the ownership check in the route. A folder alone
    stops nobody, since nothing reads a path supplied by a client.
    """
    path = storage_root() / "users" / str(user_id) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


async def read_and_validate(upload: UploadFile) -> tuple[bytes, str, str]:
    """Return (contents, mime type, extension) or raise UploadRejected.

    The whole file is held in memory, which is fine at a 10 MB cap and makes
    hashing and type sniffing straightforward. A much larger limit would need
    streaming to a temporary file instead.
    """
    limit = settings.max_upload_bytes
    contents = bytearray()

    while chunk := await upload.read(_CHUNK):
        contents.extend(chunk)
        # Checked while reading rather than after, so an enormous upload
        # cannot fill memory before it is rejected.
        if len(contents) > limit:
            raise UploadRejected(
                f"File is larger than {settings.MAX_UPLOAD_MB} MB. "
                "Try a lower-resolution photo."
            )

    if not contents:
        raise UploadRejected("That file is empty.")

    kind = filetype.guess(bytes(contents[:_SNIFF_BYTES]))
    mime = kind.mime if kind else None

    if mime not in ALLOWED_MIME:
        # Deliberately does not name what was detected: telling an attacker
        # exactly how the sniffing works helps them get around it.
        raise UploadRejected(
            "Only PDF, JPG and PNG files are accepted. "
            "Renaming a file does not change what it is."
        )

    return bytes(contents), mime, ALLOWED_MIME[mime]


def checksum(contents: bytes) -> str:
    """SHA-256 of the bytes, used to spot the same receipt uploaded twice."""
    return hashlib.sha256(contents).hexdigest()


def save(user_id: int, contents: bytes, extension: str) -> tuple[str, str]:
    """Write the file under a generated name. Returns (stored_name, path)."""
    stored_name = f"{uuid.uuid4()}{extension}"
    destination = user_dir(user_id) / stored_name
    destination.write_bytes(contents)
    return stored_name, str(destination)


def delete(file_path: str) -> bool:
    """Remove a file. Missing is not an error -- the goal is that it is gone."""
    try:
        Path(file_path).unlink()
        return True
    except FileNotFoundError:
        return False


def resolve_for_read(file_path: str, user_id: int) -> Path:
    """Final guard before streaming a file back.

    The path comes from our own database, not from the client, so this should
    never fail. It is here so that a future bug which lets a path be
    influenced from outside cannot turn into reading arbitrary files.
    """
    path = Path(file_path).resolve()
    allowed = (storage_root() / "users" / str(user_id)).resolve()
    if not path.is_relative_to(allowed):
        raise UploadRejected("File is not accessible.")
    return path


# Anything that could be read as a path separator or a control character.
_UNSAFE_IN_NAME = re.compile(r'[/\\\x00-\x1f"]')


def safe_download_name(original: str, fallback: str = "document") -> str:
    """Filename offered to the browser on download.

    Browsers already strip path separators from a download name, but relying
    on that is thin: the value also lands in a Content-Disposition header,
    where quotes and control characters are worth removing at the source.
    """
    name = _UNSAFE_IN_NAME.sub("_", original or "").strip().strip(".")
    # Leading dots would otherwise produce a hidden file on the way out.
    name = name.lstrip(".")
    return name[:120] or fallback
