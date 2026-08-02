from fastapi.testclient import TestClient

from mkvip.main import app


def test_health_endpoint_reports_api_ready() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "name": "MK-VIP API",
        "status": "ready",
        "version": "0.11.0",
    }


def test_readiness_endpoint_checks_database(database_client: TestClient) -> None:
    response = database_client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {
        "name": "MK-VIP API",
        "status": "ready",
        "version": "0.11.0",
    }


def test_health_endpoint_returns_request_id() -> None:
    response = TestClient(app).get(
        "/api/v1/health",
        headers={"X-Request-ID": "sprint-1f-check"},
    )

    assert response.headers["X-Request-ID"] == "sprint-1f-check"
