"""
FastAPI Test Suite for ARGO Query Engine endpoints.
Verifies response schemas, spatiotemporal and depth filtering, validation rules, and error handling.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health_unaffected():
    """Verify that the existing Stage 1 /api/health endpoint remains unaffected."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "operational" in data["message"].lower()
    assert data["project"] == "FloatChat API"


def test_api_root_unaffected():
    """Verify that the root endpoint remains unaffected."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "FloatChat API"


def test_argo_dataset_summary():
    """Verify GET /api/argo/summary returns dynamic dataset stats from Parquet."""
    response = client.get("/api/argo/summary")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ready"
    assert data["total_profiles"] >= 1
    assert data["total_observations"] >= 1
    assert "1900121" in data["platforms"]
    assert data["date_min"] is not None
    assert data["lat_min"] is not None
    assert data["lon_min"] is not None


def test_argo_profiles_query_all():
    """Verify GET /api/argo/profiles returns all indexed profiles without filters."""
    response = client.get("/api/argo/profiles")
    assert response.status_code == 200
    data = response.json()

    assert "count" in data
    assert "profiles" in data
    assert data["count"] == len(data["profiles"])
    assert data["count"] >= 1

    first_profile = data["profiles"][0]
    assert "platform_id" in first_profile
    assert "cycle_number" in first_profile
    assert "latitude" in first_profile
    assert "longitude" in first_profile
    assert "position_qc" in first_profile
    assert "data_mode" in first_profile


def test_argo_profiles_query_bounding_box():
    """Verify GET /api/argo/profiles with spatial bounding box filter."""
    # Query box enclosing Indian Ocean float (-10.5 to -9.5 lat, 55.0 to 56.5 lon)
    response = client.get("/api/argo/profiles?min_lat=-10.5&max_lat=-9.5&min_lon=55.0&max_lon=56.5")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    for p in data["profiles"]:
        assert -10.5 <= p["latitude"] <= -9.5
        assert 55.0 <= p["longitude"] <= 56.5

    # Out of range bounding box (e.g. Arctic / North Atlantic)
    empty_resp = client.get("/api/argo/profiles?min_lat=60.0&max_lat=70.0&min_lon=-30.0&max_lon=-20.0")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["count"] == 0
    assert empty_resp.json()["profiles"] == []


def test_argo_profiles_query_date_range():
    """Verify GET /api/argo/profiles with date range filter."""
    # First cycle was on 2002-11-11
    response = client.get("/api/argo/profiles?start_date=2002-11-01&end_date=2002-11-15")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["profiles"][0]["cycle_number"] == 1


def test_argo_profiles_query_platform_id():
    """Verify GET /api/argo/profiles with platform_id filter."""
    response = client.get("/api/argo/profiles?platform_id=1900121")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    for p in data["profiles"]:
        assert p["platform_id"] == "1900121"

    # Non-existent platform
    non_existent = client.get("/api/argo/profiles?platform_id=9999999")
    assert non_existent.status_code == 200
    assert non_existent.json()["count"] == 0


def test_argo_observations_query():
    """Verify GET /api/argo/observations with platform, cycle, and depth filters."""
    response = client.get("/api/argo/observations?platform_id=1900121&cycle_number=1")
    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 45  # Cycle 1 has 45 vertical levels
    first_obs = data["observations"][0]
    assert first_obs["platform_id"] == "1900121"
    assert first_obs["cycle_number"] == 1
    assert "pressure_dbar" in first_obs
    assert "temperature_c" in first_obs
    assert "salinity_psu" in first_obs
    assert "pres_qc" in first_obs
    assert "temp_qc" in first_obs
    assert "psal_qc" in first_obs

    # Depth filtering: shallow ocean (0 to 50 dbar)
    shallow_resp = client.get("/api/argo/observations?platform_id=1900121&cycle_number=1&min_depth=0&max_depth=50")
    assert shallow_resp.status_code == 200
    shallow_data = shallow_resp.json()
    assert shallow_data["count"] > 0
    assert all(obs["pressure_dbar"] <= 50.0 for obs in shallow_data["observations"])


def test_argo_profile_detail_success():
    """Verify GET /api/argo/profiles/{platform_id}/{cycle_number} returns combined profile & levels."""
    response = client.get("/api/argo/profiles/1900121/1")
    assert response.status_code == 200
    data = response.json()

    assert "profile" in data
    assert "observations" in data
    assert data["profile"]["platform_id"] == "1900121"
    assert data["profile"]["cycle_number"] == 1
    assert len(data["observations"]) == 45


def test_argo_profile_detail_not_found():
    """Verify GET /api/argo/profiles/{platform_id}/{cycle_number} returns 404 for nonexistent profile."""
    response = client.get("/api/argo/profiles/1900121/999")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_argo_validation_errors():
    """Verify HTTP 400 responses for invalid range boundaries."""
    # min_lat > max_lat
    r1 = client.get("/api/argo/profiles?min_lat=20.0&max_lat=10.0")
    assert r1.status_code == 400
    assert "min_lat" in r1.json()["detail"]

    # min_lon > max_lon
    r2 = client.get("/api/argo/profiles?min_lon=80.0&max_lon=50.0")
    assert r2.status_code == 400
    assert "min_lon" in r2.json()["detail"]

    # min_depth > max_depth
    r3 = client.get("/api/argo/observations?min_depth=500.0&max_depth=100.0")
    assert r3.status_code == 400
    assert "min_depth" in r3.json()["detail"]

    # start_date > end_date
    r4 = client.get("/api/argo/profiles?start_date=2023-01-01&end_date=2022-01-01")
    assert r4.status_code == 400
    assert "start_date" in r4.json()["detail"]

    # Malformed date string
    r5 = client.get("/api/argo/profiles?start_date=not-a-valid-date")
    assert r5.status_code == 400
    assert "invalid" in r5.json()["detail"].lower()
