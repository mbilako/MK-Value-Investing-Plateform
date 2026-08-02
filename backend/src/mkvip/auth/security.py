import base64
import hashlib
import hmac
import struct
from dataclasses import dataclass
from secrets import token_bytes, token_urlsafe
from urllib.parse import quote

from cryptography.fernet import Fernet
from pwdlib import PasswordHash
from pydantic import SecretStr

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


def digest_rate_limit_subject(value: str, secret: SecretStr | str) -> str:
    secret_value = secret.get_secret_value() if isinstance(secret, SecretStr) else secret
    return hmac.new(
        secret_value.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def create_totp_secret() -> str:
    return base64.b32encode(token_bytes(20)).decode("ascii").rstrip("=")


def totp_uri(secret: str, email: str, issuer: str = "MK-VIP") -> str:
    label = quote(f"{issuer}:{email}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
        "&algorithm=SHA1&digits=6&period=30"
    )


def verify_totp_code(secret: str, code: str, timestamp: int) -> bool:
    normalized_code = code.replace(" ", "").replace("-", "")
    if not normalized_code.isdigit() or len(normalized_code) != 6:
        return False
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    for offset in (-1, 0, 1):
        counter = (timestamp // 30) + offset
        digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
        position = digest[-1] & 0x0F
        value = (
            struct.unpack(">I", digest[position : position + 4])[0] & 0x7FFFFFFF
        ) % 1_000_000
        if hmac.compare_digest(f"{value:06d}", normalized_code):
            return True
    return False


def encrypt_mfa_secret(secret: str, encryption_key: SecretStr | str) -> str:
    key = (
        encryption_key.get_secret_value()
        if isinstance(encryption_key, SecretStr)
        else encryption_key
    )
    return Fernet(key.encode("ascii")).encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_mfa_secret(ciphertext: str, encryption_key: SecretStr | str) -> str:
    key = (
        encryption_key.get_secret_value()
        if isinstance(encryption_key, SecretStr)
        else encryption_key
    )
    return Fernet(key.encode("ascii")).decrypt(ciphertext.encode("ascii")).decode("ascii")


def create_recovery_codes(count: int) -> list[str]:
    return [
        f"{token_urlsafe(6).upper()[:5]}-{token_urlsafe(6).upper()[:5]}"
        for _ in range(count)
    ]
