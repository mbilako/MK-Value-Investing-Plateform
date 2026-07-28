from fastapi.testclient import TestClient
from httpx import Response

TRUSTED_ORIGIN_HEADERS = {"Origin": "http://localhost:5173"}


class RecordingEmailSender:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send_verification_email(self, recipient: str, token: str) -> None:
        self.messages.append(("email_verification", recipient, token))

    def send_password_reset_email(self, recipient: str, token: str) -> None:
        self.messages.append(("password_reset", recipient, token))


def register_pending_user(
    client: TestClient,
    email_sender: RecordingEmailSender,
    email: str = "alice@example.com",
) -> str:
    response = client.post(
        "/api/v1/auth/register",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": email, "password": "correct horse battery"},
    )
    assert response.status_code == 202
    return email_sender.messages[-1][2]


def register_and_verify_user(
    client: TestClient,
    email_sender: RecordingEmailSender,
    email: str = "alice@example.com",
) -> None:
    token = register_pending_user(client, email_sender, email)
    response = client.post(
        "/api/v1/auth/verify-email",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"token": token},
    )
    assert response.status_code == 204


def register_verify_and_login_user(
    client: TestClient,
    email_sender: RecordingEmailSender,
    email: str = "alice@example.com",
) -> Response:
    register_and_verify_user(client, email_sender, email)
    response = client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": email, "password": "correct horse battery"},
    )
    assert response.status_code == 200
    return response
