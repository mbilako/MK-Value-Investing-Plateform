from dataclasses import dataclass
import hashlib
import hmac
from secrets import token_urlsafe

from pydantic import SecretStr
from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash("mkvip-dummy-password")


@dataclass(frozen=True)
class SessionToken:
    raw: str
    digest: str


@dataclass(frozen=True)
class ActionToken:
    raw: str
    digest: str


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def digest_session_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_session_token() -> SessionToken:
    raw = token_urlsafe(32)
    return SessionToken(raw=raw, digest=digest_session_token(raw))


def digest_action_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_action_token() -> ActionToken:
    raw = token_urlsafe(32)
    return ActionToken(raw=raw, digest=digest_action_token(raw))


def digest_email_recipient(email: str, secret: SecretStr | str) -> str:
    secret_value = (
        secret.get_secret_value()
        if isinstance(secret, SecretStr)
        else secret
    )
    return hmac.new(
        secret_value.encode("utf-8"),
        normalize_email(email).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
