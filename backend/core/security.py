"""Password hashing and login tokens.

Two jobs, deliberately kept together because they are the only places in the
codebase that deal in secrets:

  1. Turn a password into a hash that cannot be reversed.
  2. Issue and read the signed token a client carries after logging in.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import settings

# bcrypt hashes at most 72 bytes and SILENTLY IGNORES the rest, which would
# make "same first 72 characters" count as the same password. Rejected at the
# schema instead, so the limit is visible to the caller rather than hidden.
BCRYPT_MAX_BYTES = 72

# Used when an email does not exist, so a failed login takes the same time
# whether or not the account is real. Without this, an attacker can tell which
# emails are registered purely by how fast the server says no.
_DUMMY_HASH = bcrypt.hashpw(b"timing-attack-placeholder", bcrypt.gensalt())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # A malformed hash in the database should fail the login, not crash it.
        return False


def waste_time_like_a_real_check() -> None:
    """Burn the same time a genuine password check would take."""
    bcrypt.checkpw(b"x", _DUMMY_HASH)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),          # who the token is for
        "iat": now,                   # when it was issued
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id inside a valid token, or None.

    The algorithm is pinned. Without that, a forged token could declare its own
    algorithm -- including "none", meaning unsigned -- and be accepted.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        # Covers expiry, a broken signature, and anything malformed.
        return None

    subject = payload.get("sub")
    if subject is None:
        return None
    try:
        return int(subject)
    except (TypeError, ValueError):
        return None
