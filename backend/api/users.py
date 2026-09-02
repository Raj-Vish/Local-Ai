"""The signed-in user's own profile."""
from fastapi import APIRouter, Depends

from core.deps import get_current_user
from models import User
from schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    """Who am I? Requires a valid token; used by the frontend after login."""
    return current_user
