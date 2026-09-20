from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_200_and_ok():
    """Verify GET /api/v1/health responds with HTTP 200 and status 'ok'."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "jansetu-backend"


def test_health_check_contains_required_metadata():
    """Verify health response contains all expected non-sensitive metadata fields."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "environment" in data
    assert "version" in data
    assert "timestamp" in data
    assert data["environment"] == "development"


def test_health_check_cors_headers():
    """Verify CORS headers are properly returned for allowed frontend origins."""
    headers = {"Origin": "http://localhost:3000"}
    response = client.get("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_invalid_endpoint_returns_404():
    """Verify requesting an unmapped route returns standard HTTP 404."""
    response = client.get("/api/v1/unknown-route")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
