import pytest
from fastapi.testclient import TestClient
from httpx import Response

TRUSTED_ORIGIN_HEADERS = {"Origin": "http://localhost:5173"}


def register_user(
    client: TestClient,
    email: str = "alice@example.com",
) -> Response:
    response = client.post(
        "/api/v1/auth/register",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": email,
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 201
    return response


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


def test_register_sets_secure_server_session(
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
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"
    cookie = response.headers["set-cookie"]
    assert "mkvip_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api" in cookie
    assert "Max-Age=2592000" in cookie


def test_me_and_logout_follow_cookie_lifecycle(
    database_client: TestClient,
) -> None:
    register_user(database_client)
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
) -> None:
    register_user(database_client)
    database_client.cookies.clear()

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
) -> None:
    register_user(database_client)
    database_client.cookies.clear()
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


def test_duplicate_registration_returns_conflict(
    database_client: TestClient,
) -> None:
    register_user(database_client)

    response = database_client.post(
        "/api/v1/auth/register",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": " ALICE@EXAMPLE.COM ",
            "password": "another correct password",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Cette adresse email est déjà inscrite."
    }


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


def test_auth_response_bodies_never_expose_raw_session_tokens(
    database_client: TestClient,
) -> None:
    registration = register_user(database_client)
    registration_token = registration.cookies.get("mkvip_session")
    assert registration_token is not None
    assert "token" not in registration.json()
    assert registration_token not in registration.text

    database_client.cookies.clear()
    login = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )
    login_token = login.cookies.get("mkvip_session")
    assert login.status_code == 200
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
) -> None:
    registration = register_user(database_client)
    registration_attributes = registration.headers["set-cookie"].split("; ")
    assert ("Secure" in registration_attributes) is expected_secure

    database_client.cookies.clear()
    login = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )
    login_attributes = login.headers["set-cookie"].split("; ")
    assert login.status_code == 200
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
def test_non_default_duration_aligns_registration_and_login_cookies(
    database_client: TestClient,
) -> None:
    registration = register_user(database_client)
    assert "Max-Age=604800" in registration.headers["set-cookie"]

    database_client.cookies.clear()
    login = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )
    assert login.status_code == 200
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
    assert response.status_code == 201


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
) -> None:
    registration = register_user(database_client)
    first_token = registration.cookies.get("mkvip_session")
    assert first_token is not None

    database_client.cookies.clear()
    login = database_client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )
    second_token = login.cookies.get("mkvip_session")
    assert login.status_code == 200
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
