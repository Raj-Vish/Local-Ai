"""The single place the application works out who is asking.

Every protected route depends on get_current_user. Because there is exactly
one copy of this check, a route cannot accidentally be written without it --
there is no second version to fall out of step.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.security import decode_access_token
from database import get_db
from models import User

bearer_scheme = HTTPBearer(auto_error=False, description="Paste the token from /auth/login")

_UNAUTHORISED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _UNAUTHORISED

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _UNAUTHORISED

    user = db.get(User, user_id)
    # A token can outlive the account it names -- deleted, or disabled since
    # it was issued. The database is the authority, not the token.
    if user is None or not user.is_active:
        raise _UNAUTHORISED

    return user
