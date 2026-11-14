"""Tests for health-check endpoint."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify that root endpoint responds with project metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "FloatChat API"
    assert "version" in data
    assert data["health_check"] == "/api/health"


def test_health_check_endpoint():
    """Verify GET /api/health returns 200 OK and expected JSON schema."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "operational" in data["message"].lower()
    assert "timestamp" in data
    assert data["version"] == "0.1.0"
    assert data["project"] == "FloatChat API"
