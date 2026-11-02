"""
Unit and integration tests for City / Location multi-select filtering and date posted removal.
"""

import pytest
from fastapi.testclient import TestClient
from app import app
from scraper.database import Database

client = TestClient(app)

def test_api_cities_endpoint():
    """Verify /api/cities endpoint returns cities with categories and counts."""
    res = client.get("/api/cities")
    assert res.status_code == 200
    cities = res.json()
    assert isinstance(cities, list)
    assert len(cities) >= 10

    for c in cities:
        assert "id" in c
        assert "name" in c
        assert "category" in c
        assert "count" in c
        assert isinstance(c["count"], int)
        assert c["count"] >= 0

    # Ensure major tech hubs exist in response
    ids = [c["id"] for c in cities]
    assert "Bengaluru" in ids
    assert "Mumbai" in ids
    assert "Pune" in ids
    assert "Delhi NCR" in ids
    assert "Hyderabad" in ids
    assert "Remote" in ids


def test_filter_single_city():
    """Verify filtering by single city returns matching jobs."""
    res = client.get("/api/jobs?city=Bengaluru&limit=50")
    assert res.status_code == 200
    data = res.json()
    assert "jobs" in data
    assert data["total"] > 0
    for job in data["jobs"]:
        loc = (job.get("location") or "").lower()
        assert "bengaluru" in loc or "bangalore" in loc


def test_filter_multi_cities_comma_separated():
    """Verify filtering by multiple cities comma-separated returns jobs from either city."""
    res = client.get("/api/jobs?cities=Bengaluru,Pune&limit=50")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for job in data["jobs"]:
        loc = (job.get("location") or "").lower()
        assert "bengaluru" in loc or "bangalore" in loc or "pune" in loc


def test_filter_multi_cities_repeated_query():
    """Verify filtering by multiple cities with repeated query param returns jobs."""
    res = client.get("/api/jobs?city=Bengaluru&city=Mumbai&limit=50")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for job in data["jobs"]:
        loc = (job.get("location") or "").lower()
        assert any(k in loc for k in ["bengaluru", "bangalore", "mumbai", "thane", "vashi"])


def test_filter_city_remote():
    """Verify filtering by Remote city matches Remote work mode or remote locations."""
    res = client.get("/api/jobs?city=Remote&limit=50")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for job in data["jobs"]:
        is_remote = (
            job.get("work_mode") == "Remote" or
            "remote" in (job.get("location") or "").lower() or
            "remote" in (job.get("country") or "").lower() or
            "work from home" in (job.get("location") or "").lower() or
            "worldwide" in (job.get("location") or "").lower()
        )
        assert is_remote


def test_date_posted_not_restricted_by_default():
    """Verify default /api/jobs request is not artificially restricted to 30 days."""
    res = client.get("/api/jobs")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 200


def test_export_csv_with_city_filter():
    """Verify CSV export respects city filter."""
    res = client.get("/api/export/csv?cities=Bengaluru,Mumbai")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    csv_text = res.text
    assert "id,title,standard_role" in csv_text


def test_export_json_with_city_filter():
    """Verify JSON export respects city filter."""
    res = client.get("/api/export/json?city=Bengaluru")
    assert res.status_code == 200
    jobs = res.json()
    assert isinstance(jobs, list)
    for j in jobs:
        loc = (j.get("location") or "").lower()
        assert "bengaluru" in loc or "bangalore" in loc
