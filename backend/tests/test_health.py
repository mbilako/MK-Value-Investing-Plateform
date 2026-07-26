from fastapi.testclient import TestClient

from mkvip.main import app


def test_health_endpoint_reports_api_ready() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "name": "MK-VIP API",
        "status": "ready",
        "version": "0.7.0",
    }
