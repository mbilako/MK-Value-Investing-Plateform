import uuid
from datetime import datetime
from typing import Literal

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


class MfaChallengeRequest(BaseModel):
    challenge_token: str = Field(min_length=32, max_length=256)
    code: str = Field(min_length=6, max_length=32)


class MfaCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


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
    mfa_enabled: bool = False


class MfaChallengeRead(BaseModel):
    mfa_required: Literal[True] = True
    challenge_token: str
    expires_at: datetime


class MfaSetupRead(BaseModel):
    secret: str
    otpauth_uri: str
    expires_at: datetime


class MfaRecoveryCodesRead(BaseModel):
    recovery_codes: list[str]


class SessionRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None
    current: bool
