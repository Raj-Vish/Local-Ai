"""The shape of every request and response.

Pydantic checks incoming data before a route ever runs, so a route can trust
what it is given. Anything that fails these rules gets a 422 with a message
naming the field, without a line of validation code in the route itself.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from core.security import BCRYPT_MAX_BYTES


class UserRegister(BaseModel):
    employee_id: str = Field(min_length=2, max_length=32, examples=["EMP001"])
    full_name: str = Field(min_length=2, max_length=120, examples=["Raj Vishwakarma"])
    email: EmailStr = Field(examples=["raj@company.com"])
    password: str = Field(min_length=8, max_length=128, examples=["a-good-password"])

    @field_validator("password")
    @classmethod
    def within_bcrypt_limit(cls, v: str) -> str:
        # Long passwords are fine; silently ignored characters are not.
        if len(v.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(
                f"Password must be at most {BCRYPT_MAX_BYTES} bytes "
                "(accented and non-Latin characters count as more than one)."
            )
        return v

    @field_validator("employee_id")
    @classmethod
    def tidy_employee_id(cls, v: str) -> str:
        # Stored uppercase so EMP001 and emp001 cannot become two accounts.
        return v.strip().upper()

    @field_validator("full_name")
    @classmethod
    def tidy_name(cls, v: str) -> str:
        return " ".join(v.split())


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    employee_id: str
    full_name: str
    email: EmailStr
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut
