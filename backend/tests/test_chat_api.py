"""
FastAPI Integration Tests for Conversational Chat Endpoint (Step 4.3).
Verifies POST /api/chat/query and preserves all existing endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Provides FastAPI test client."""
    return TestClient(app)


class TestChatAPIEndpoints:
    """Tests for the /api/chat routes and regression checks on existing endpoints."""

    def test_chat_endpoint_summary(self, client):
        """Verifies natural language dataset summary query."""
        res = client.post("/api/chat/query", json={"prompt": "Show dataset overview"})
        assert res.status_code == 200
        data = res.json()
        assert data["prompt"] == "Show dataset overview"
        assert data["intent"] == "summary"
        assert data["data_count"] == 3
        assert "summary" in data["data"]
        assert data["data"]["summary"]["total_profiles"] == 3
        assert "3 profile(s)" in data["summary"]

    def test_chat_endpoint_profiles(self, client):
        """Verifies natural language profile query."""
        # Querying November 2002 returns Cycles 1 and 2
        res = client.post(
            "/api/chat/query",
            json={"prompt": "Show profiles for float 1900121 in November 2002"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "query_profiles"
        assert data["parameters"]["platform_id"] == "1900121"
        assert data["data_count"] == 2
        assert len(data["data"]["profiles"]) == 2
        assert "2 ARGO profile(s)" in data["summary"]

        # Querying float 1900121 returns all 3 profiles
        res_all = client.post(
            "/api/chat/query",
            json={"prompt": "Show profiles for float 1900121"},
        )
        assert res_all.status_code == 200
        data_all = res_all.json()
        assert data_all["data_count"] == 3
        assert len(data_all["data"]["profiles"]) == 3
        assert "3 ARGO profile(s)" in data_all["summary"]

    def test_chat_endpoint_observations(self, client):
        """Verifies natural language observations query."""
        res = client.post(
            "/api/chat/query",
            json={"prompt": "Show observations for float 1900121 cycle 2 between 0 and 200m"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "query_observations"
        assert data["parameters"]["platform_id"] == "1900121"
        assert data["parameters"]["cycle_number"] == 2
        assert data["data_count"] > 0
        assert "vertical observation level(s)" in data["summary"]

    def test_chat_endpoint_out_of_domain(self, client):
        """Verifies out-of-domain handling with guidance response."""
        res = client.post(
            "/api/chat/query",
            json={"prompt": "What is the capital city of Australia?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "out_of_domain"
        assert data["data"] is None
        assert data["data_count"] == 0
        assert "FloatChat specializes in ARGO oceanographic float data" in data["summary"]

    def test_chat_endpoint_empty_results(self, client):
        """Verifies non-matching query parameters return count=0 with clear explanation."""
        res = client.post(
            "/api/chat/query",
            json={"prompt": "Show data for float 8888888"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["data_count"] == 0
        assert "No matching ARGO observations or profiles were found" in data["summary"]

    def test_chat_endpoint_empty_prompt_validation(self, client):
        """Verifies that empty string prompts trigger Pydantic 422 Unprocessable Entity."""
        res = client.post("/api/chat/query", json={"prompt": ""})
        assert res.status_code == 422

    def test_chat_alias_endpoint(self, client):
        """Verifies alias endpoint POST /api/chat works identically."""
        res = client.post("/api/chat", json={"prompt": "What data do you have?"})
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "summary"
        assert data["data_count"] == 3

    def test_regression_existing_endpoints_preserved(self, client):
        """Verifies all existing API routes remain 100% operational."""
        # 1. Health endpoint
        res_health = client.get("/api/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] == "ok"

        # 2. ARGO summary endpoint
        res_summary = client.get("/api/argo/summary")
        assert res_summary.status_code == 200
        assert res_summary.json()["total_profiles"] == 3

        # 3. ARGO profiles endpoint
        res_profiles = client.get("/api/argo/profiles")
        assert res_profiles.status_code == 200
        assert res_profiles.json()["count"] == 3

        # 4. ARGO observations endpoint
        res_obs = client.get("/api/argo/observations")
        assert res_obs.status_code == 200
        assert res_obs.json()["count"] == 135
