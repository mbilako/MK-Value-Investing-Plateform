import pytest
from pydantic import SecretStr, ValidationError

from mkvip.auth.security import (
    create_action_token,
    create_session_token,
    digest_action_token,
    digest_email_recipient,
    digest_session_token,
    hash_password,
    normalize_email,
    verify_password,
)
from mkvip.schemas.auth import RegisterRequest


def test_normalizes_email_and_hashes_password_with_argon2id() -> None:
    assert normalize_email(" Alice@Example.COM ") == "alice@example.com"
    stored = hash_password("correct horse battery")
    assert stored.startswith("$argon2id$")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("incorrect password", stored)


def test_session_token_is_random_and_only_digest_is_storable() -> None:
    first = create_session_token()
    second = create_session_token()
    assert first.raw != second.raw
    assert len(first.digest) == 64
    assert first.digest == digest_session_token(first.raw)
    assert first.digest != first.raw


def test_action_token_is_random_and_only_digest_is_storable() -> None:
    first = create_action_token()
    second = create_action_token()

    assert first.raw != second.raw
    assert first.digest == digest_action_token(first.raw)
    assert len(first.digest) == 64
    assert first.raw not in first.digest


def test_email_recipient_digest_is_normalized_and_secret_scoped() -> None:
    first = digest_email_recipient(
        " Investor@Example.com ",
        SecretStr("first-secret"),
    )
    normalized = digest_email_recipient(
        "investor@example.com",
        SecretStr("first-secret"),
    )
    other_secret = digest_email_recipient(
        "investor@example.com",
        SecretStr("second-secret"),
    )

    assert first == normalized
    assert first != other_secret
    assert len(first) == 64


@pytest.mark.parametrize("length", [0, 11, 129])
def test_registration_rejects_passwords_outside_bounds(length: int) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="alice@example.com", password="x" * length)
