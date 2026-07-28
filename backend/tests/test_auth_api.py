import asyncio
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mkvip.models.user import UserOrm
from tests.auth_helpers import (
    TRUSTED_ORIGIN_HEADERS,
    RecordingEmailSender,
    register_and_verify_user,
    register_pending_user,
    register_verify_and_login_user,
)

GENERIC_MESSAGE = {
    "message": (
        "Si cette adresse peut être inscrite, "
        "un email de vérification a été envoyé."
    )
}


GENERIC_PASSWORD_RESET_MESSAGE = {
    "message": (
        "Si cette adresse est inscrite, "
        "un email de r\u00e9initialisation a \u00e9t\u00e9 envoy\u00e9."
    )
}


def set_session_token(client: TestClient, token: str) -> None:
    client.cookies.clear()
    client.cookies.set("mkvip_session", token, path="/api")


def contains_input_key(value: object) -> bool:
    if isinstance(value, dict):
        return "input" in value or any(
            contains_input_key(item)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(contains_input_key(item) for item in value)
    return False


def test_registration_returns_pending_message_without_cookie(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
) -> None:
    response = database_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor@example.com",
            "password": "correct horse battery",
        },
        headers=trusted_origin_headers,
    )

    assert response.status_code == 202
    assert "mkvip_session" not in response.cookies
    assert response.json() == GENERIC_MESSAGE
    assert email_sender.messages[0][:2] == (
        "email_verification",
        "investor@example.com",
    )


def test_duplicate_pending_and_verified_registration_share_generic_response(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
    api_clock,
) -> None:
    token = register_pending_user(database_client, email_sender)
    duplicate_pending = database_client.post(
        "/api/v1/auth/register",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": " ALICE@EXAMPLE.COM ",
            "password": "another correct password",
        },
    )
    assert duplicate_pending.status_code == 202
    assert duplicate_pending.json() == GENERIC_MESSAGE
    assert len(email_sender.messages) == 1

    assert database_client.post(
        "/api/v1/auth/verify-email",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"token": token},
    ).status_code == 204
    api_clock.advance(timedelta(seconds=61))
    duplicate_verified = database_client.post(
        "/api/v1/auth/register",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "third correct password",
        },
    )
    assert duplicate_verified.status_code == 202
    assert duplicate_verified.json() == GENERIC_MESSAGE
    assert len(email_sender.messages) == 1


def test_verification_returns_204_then_consumed_token_returns_400(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    token = register_pending_user(database_client, email_sender)

    first = database_client.post(
        "/api/v1/auth/verify-email",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"token": token},
    )
    consumed = database_client.post(
        "/api/v1/auth/verify-email",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"token": token},
    )
    invalid = database_client.post(
        "/api/v1/auth/verify-email",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"token": "x" * 32},
    )

    assert first.status_code == 204
    assert consumed.status_code == 400
    assert invalid.status_code == 400


def test_expired_verification_returns_410(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
    api_clock,
) -> None:
    token = register_pending_user(database_client, email_sender)
    api_clock.advance(timedelta(hours=24, seconds=1))

    response = database_client.post(
        "/api/v1/auth/verify-email",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"token": token},
    )

    assert response.status_code == 410


def test_unverified_login_returns_403_only_for_correct_password(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    register_pending_user(database_client, email_sender)

    correct = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )
    wrong = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": "alice@example.com", "password": "wrong-password"},
    )

    assert correct.status_code == 403
    assert correct.json() == {
        "detail": "Vérifie ton adresse email avant de te connecter."
    }
    assert wrong.status_code == 401


def test_resend_issues_fresh_token_for_active_pending_account(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
    api_clock,
) -> None:
    first = register_pending_user(database_client, email_sender)
    api_clock.advance(timedelta(seconds=61))

    response = database_client.post(
        "/api/v1/auth/resend-verification",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": " ALICE@EXAMPLE.COM "},
    )

    assert response.status_code == 202
    assert response.json() == GENERIC_MESSAGE
    assert len(email_sender.messages) == 2
    assert email_sender.messages[-1][2] != first


def test_resend_is_generic_without_delivery_for_ineligible_and_limited(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
    api_clock,
    database_session_factory,
) -> None:
    register_and_verify_user(database_client, email_sender, "verified@example.com")
    register_pending_user(database_client, email_sender, "inactive@example.com")

    async def deactivate_user() -> None:
        async with database_session_factory() as session:
            user = await session.scalar(
                select(UserOrm).where(
                    UserOrm.email == "inactive@example.com"
                )
            )
            assert user is not None
            user.is_active = False
            await session.commit()

    asyncio.run(deactivate_user())
    baseline = len(email_sender.messages)
    cases = [
        "unknown@example.com",
        "verified@example.com",
        "inactive@example.com",
    ]
    for email in cases:
        api_clock.advance(timedelta(seconds=61))
        response = database_client.post(
            "/api/v1/auth/resend-verification",
            headers=TRUSTED_ORIGIN_HEADERS,
            json={"email": email},
        )
        assert response.status_code == 202
        assert response.json() == GENERIC_MESSAGE
    limited = database_client.post(
        "/api/v1/auth/resend-verification",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": "inactive@example.com"},
    )
    assert limited.status_code == 202
    assert limited.json() == GENERIC_MESSAGE
    assert len(email_sender.messages) == baseline


def test_password_reset_request_is_generic_and_sends_known_account_email(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
) -> None:
    register_and_verify_user(
        database_client,
        email_sender,
        "investor@example.com",
    )

    response = database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "investor@example.com"},
        headers=trusted_origin_headers,
    )

    assert response.status_code == 202
    assert response.json() == GENERIC_PASSWORD_RESET_MESSAGE
    assert email_sender.messages[-1][:2] == (
        "password_reset",
        "investor@example.com",
    )


def test_password_reset_request_is_generic_without_unknown_account_email(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
) -> None:
    response = database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "unknown@example.com"},
        headers=trusted_origin_headers,
    )

    assert response.status_code == 202
    assert response.json() == GENERIC_PASSWORD_RESET_MESSAGE
    assert email_sender.messages == []


def test_password_reset_request_is_generic_for_inactive_and_limited_accounts(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
    database_session_factory,
) -> None:
    register_and_verify_user(
        database_client,
        email_sender,
        "inactive@example.com",
    )

    async def deactivate_user() -> None:
        async with database_session_factory() as session:
            user = await session.scalar(
                select(UserOrm).where(
                    UserOrm.email == "inactive@example.com"
                )
            )
            assert user is not None
            user.is_active = False
            await session.commit()

    asyncio.run(deactivate_user())
    baseline = len(email_sender.messages)
    inactive = database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "inactive@example.com"},
        headers=trusted_origin_headers,
    )
    limited = database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "inactive@example.com"},
        headers=trusted_origin_headers,
    )

    assert inactive.status_code == limited.status_code == 202
    assert inactive.json() == limited.json() == GENERIC_PASSWORD_RESET_MESSAGE
    assert len(email_sender.messages) == baseline

    register_and_verify_user(
        database_client,
        email_sender,
        "limited@example.com",
    )
    first = database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "limited@example.com"},
        headers=trusted_origin_headers,
    )
    after_first = len(email_sender.messages)
    limited = database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "limited@example.com"},
        headers=trusted_origin_headers,
    )

    assert first.status_code == limited.status_code == 202
    assert first.json() == limited.json() == GENERIC_PASSWORD_RESET_MESSAGE
    assert len(email_sender.messages) == after_first
    assert email_sender.messages[-1][:2] == (
        "password_reset",
        "limited@example.com",
    )


def test_password_reset_confirmation_changes_password_and_revokes_session(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
) -> None:
    login = register_verify_and_login_user(database_client, email_sender)
    assert login.cookies.get("mkvip_session") is not None
    request = database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "alice@example.com"},
        headers=trusted_origin_headers,
    )
    assert request.status_code == 202
    reset_token = email_sender.messages[-1][2]

    confirmation = database_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": reset_token,
            "password": "new correct horse battery",
        },
        headers=trusted_origin_headers,
    )

    assert confirmation.status_code == 204
    assert "set-cookie" not in confirmation.headers
    assert database_client.get("/api/v1/auth/me").status_code == 401
    old_password = database_client.post(
        "/api/v1/auth/login",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
        headers=trusted_origin_headers,
    )
    new_password = database_client.post(
        "/api/v1/auth/login",
        json={
            "email": "alice@example.com",
            "password": "new correct horse battery",
        },
        headers=trusted_origin_headers,
    )
    assert old_password.status_code == 401
    assert new_password.status_code == 200


def test_password_reset_confirmation_rejects_invalid_and_consumed_tokens(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
) -> None:
    register_and_verify_user(database_client, email_sender)
    database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "alice@example.com"},
        headers=trusted_origin_headers,
    )
    reset_token = email_sender.messages[-1][2]
    first = database_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "password": "new secure password"},
        headers=trusted_origin_headers,
    )
    consumed = database_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "password": "another secure password"},
        headers=trusted_origin_headers,
    )
    invalid = database_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": "x" * 32, "password": "another secure password"},
        headers=trusted_origin_headers,
    )

    assert first.status_code == 204
    assert consumed.status_code == 400
    assert invalid.status_code == 400


def test_password_reset_confirmation_rejects_verification_token(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
) -> None:
    verification_token = register_pending_user(database_client, email_sender)

    response = database_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": verification_token,
            "password": "new secure password",
        },
        headers=trusted_origin_headers,
    )

    assert response.status_code == 400


def test_password_reset_confirmation_rejects_expired_token(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
    api_clock,
) -> None:
    register_and_verify_user(database_client, email_sender)
    database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "alice@example.com"},
        headers=trusted_origin_headers,
    )
    reset_token = email_sender.messages[-1][2]
    api_clock.advance(timedelta(minutes=30, seconds=1))

    response = database_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "password": "new secure password"},
        headers=trusted_origin_headers,
    )

    assert response.status_code == 410


def test_password_reset_confirmation_rejects_noncompliant_password(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
) -> None:
    submitted_secret = "too-short"

    response = database_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": "x" * 32, "password": submitted_secret},
        headers=trusted_origin_headers,
    )

    assert response.status_code == 422
    assert submitted_secret not in response.text
    assert not contains_input_key(response.json())


def test_me_and_logout_follow_cookie_lifecycle(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    register_verify_and_login_user(database_client, email_sender)
    assert database_client.get("/api/v1/auth/me").status_code == 200
    assert (
        database_client.post(
            "/api/v1/auth/logout",
            headers=TRUSTED_ORIGIN_HEADERS,
        ).status_code
        == 204
    )
    assert database_client.get("/api/v1/auth/me").status_code == 401


def test_successful_login_returns_user_and_new_session(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    register_and_verify_user(database_client, email_sender)

    response = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"
    assert response.cookies.get("mkvip_session") is not None


def test_login_errors_never_reveal_account_state(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    register_and_verify_user(database_client, email_sender)
    unknown = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    wrong = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "Identifiants invalides."}


@pytest.mark.parametrize("path", ["register", "login"])
def test_invalid_auth_password_is_not_reflected_in_validation_error(
    database_client: TestClient,
    path: str,
) -> None:
    submitted_secret = "S" * 129

    response = database_client.post(
        f"/api/v1/auth/{path}",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": submitted_secret,
        },
    )

    assert response.status_code == 422
    assert submitted_secret not in response.text
    assert not contains_input_key(response.json())
    assert any(
        "at most 128 characters" in error["msg"]
        for error in response.json()["detail"]
    )


def test_auth_response_body_never_exposes_raw_session_token(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    login = register_verify_and_login_user(database_client, email_sender)
    login_token = login.cookies.get("mkvip_session")
    assert login_token is not None
    assert "token" not in login.json()
    assert login_token not in login.text


@pytest.mark.parametrize(
    ("database_client", "expected_secure"),
    [
        ({"session_cookie_secure": False}, False),
        ({"session_cookie_secure": True}, True),
    ],
    indirect=["database_client"],
)
def test_session_cookie_secure_flag_follows_settings(
    database_client: TestClient,
    expected_secure: bool,
    email_sender: RecordingEmailSender,
) -> None:
    login = register_verify_and_login_user(database_client, email_sender)
    login_attributes = login.headers["set-cookie"].split("; ")
    assert ("Secure" in login_attributes) is expected_secure

    logout = database_client.post(
        "/api/v1/auth/logout",
        headers=TRUSTED_ORIGIN_HEADERS,
    )
    logout_attributes = logout.headers["set-cookie"].split("; ")
    assert logout.status_code == 204
    assert ("Secure" in logout_attributes) is expected_secure


@pytest.mark.parametrize(
    "database_client",
    [{"session_duration_days": 7}],
    indirect=True,
)
def test_non_default_duration_controls_login_cookie(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    login = register_verify_and_login_user(database_client, email_sender)
    assert "Max-Age=604800" in login.headers["set-cookie"]


def test_allows_trusted_write_origin(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/auth/register",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 202


def test_rejects_untrusted_write_origin(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 403


def test_rejects_missing_write_origin(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("raw_token", [None, "invalid-session-token"])
def test_logout_clears_cookie_without_valid_session(
    database_client: TestClient,
    raw_token: str | None,
) -> None:
    if raw_token is not None:
        set_session_token(database_client, raw_token)

    response = database_client.post(
        "/api/v1/auth/logout",
        headers=TRUSTED_ORIGIN_HEADERS,
    )

    assert response.status_code == 204
    deletion_cookie = response.headers["set-cookie"]
    assert "mkvip_session=" in deletion_cookie
    assert "HttpOnly" in deletion_cookie
    assert "SameSite=strict" in deletion_cookie
    assert "Path=/api" in deletion_cookie
    assert "Max-Age=0" in deletion_cookie


def test_logout_revokes_only_the_presented_session(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    first_login = register_verify_and_login_user(database_client, email_sender)
    first_token = first_login.cookies.get("mkvip_session")
    assert first_token is not None

    database_client.cookies.clear()
    second_login = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )
    second_token = second_login.cookies.get("mkvip_session")
    assert second_login.status_code == 200
    assert second_token is not None

    set_session_token(database_client, first_token)
    assert (
        database_client.post(
            "/api/v1/auth/logout",
            headers=TRUSTED_ORIGIN_HEADERS,
        ).status_code
        == 204
    )

    set_session_token(database_client, first_token)
    assert database_client.get("/api/v1/auth/me").status_code == 401
    set_session_token(database_client, second_token)
    assert database_client.get("/api/v1/auth/me").status_code == 200
