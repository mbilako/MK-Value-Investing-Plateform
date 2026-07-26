from fastapi.testclient import TestClient


def register_user(
    client: TestClient,
    email: str = "alice@example.com",
) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 201


def test_register_sets_secure_server_session(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/auth/register",
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
    assert database_client.post("/api/v1/auth/logout").status_code == 204
    assert database_client.get("/api/v1/auth/me").status_code == 401


def test_login_errors_never_reveal_account_state(
    database_client: TestClient,
) -> None:
    register_user(database_client)
    database_client.cookies.clear()
    unknown = database_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    wrong = database_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "Identifiants invalides."}


def test_rejects_untrusted_write_origin(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 403
