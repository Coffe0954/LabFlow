from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["student", "teacher", "admin"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    full_name: str = Field(min_length=2, max_length=200)
    group: str | None = Field(default=None, max_length=50)


class LoginIn(BaseModel):
    # При входе формат email не проверяем — достаточно найти пользователя.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    group: str | None
    role: Role


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserAdminUpdate(BaseModel):
    role: Role | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    group: str | None = Field(default=None, max_length=50)
