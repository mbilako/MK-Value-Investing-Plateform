import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from mkvip.auth.security import normalize_email


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalized_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalized_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))


class EmailRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalized_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))


class TokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class MessageRead(BaseModel):
    message: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime
