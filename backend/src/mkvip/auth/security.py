from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash("mkvip-dummy-password")


@dataclass(frozen=True)
class SessionToken:
    raw: str
    digest: str


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def digest_session_token(raw: str) -> str:
    return sha256(raw.encode("utf-8")).hexdigest()


def create_session_token() -> SessionToken:
    raw = token_urlsafe(32)
    return SessionToken(raw=raw, digest=digest_session_token(raw))
