"""Registration and login."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from core.security import (
    create_access_token, hash_password, verify_password, waste_time_like_a_real_check,
)
from database import get_db
from models import User
from schemas import TokenOut, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Create an account.

    Email is matched case-insensitively: signing up as Raj@x.com and later as
    raj@x.com should be one account, not two.
    """
    email = payload.email.lower()

    clash = db.execute(
        select(User).where(
            (func.lower(User.email) == email) | (User.employee_id == payload.employee_id)
        )
    ).scalar_one_or_none()

    if clash is not None:
        field = "Email" if clash.email.lower() == email else "Employee ID"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{field} is already registered.",
        )

    user = User(
        employee_id=payload.employee_id,
        full_name=payload.full_name,
        email=email,
        # The only place a raw password is touched. It is never stored, logged
        # or returned.
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(func.lower(User.email) == payload.email.lower())
    ).scalar_one_or_none()

    if user is None:
        # Hash anyway so a missing account takes as long as a wrong password.
        waste_time_like_a_real_check()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            # Deliberately identical to the message above: saying "no such
            # user" would confirm which emails are registered.
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    return TokenOut(
        access_token=create_access_token(user.user_id),
        expires_in_minutes=settings.JWT_EXPIRE_MINUTES,
        user=UserOut.model_validate(user),
    )
