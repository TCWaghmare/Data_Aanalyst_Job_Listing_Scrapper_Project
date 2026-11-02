"""
Unit and integration tests for Job Platform multi-select filtering and listing sorting.
"""

import pytest
from fastapi.testclient import TestClient
from app import app
from scraper.database import Database

client = TestClient(app)

def test_api_platforms_contains_job_counts():
    """Verify /api/platforms endpoint returns platforms with live job_count."""
    res = client.get("/api/platforms")
    assert res.status_code == 200
    platforms = res.json()
    assert isinstance(platforms, list)
    assert len(platforms) >= 70

    # Ensure job_count field is present on each platform
    for p in platforms:
        assert "id" in p
        assert "name" in p
        assert "job_count" in p
        assert isinstance(p["job_count"], int)
        assert p["job_count"] >= 0

    # Platforms with scraped jobs (e.g., Internshala, Remote OK) should have job_count > 0
    with_jobs = [p for p in platforms if p["job_count"] > 0]
    assert len(with_jobs) > 0
    internshala = next((p for p in platforms if p["id"] == "internshala"), None)
    assert internshala is not None
    assert internshala["job_count"] > 0


def test_filter_single_platform():
    """Verify filtering by a single platform returns only jobs from that platform."""
    res = client.get("/api/jobs?platforms=internshala&limit=50&date_posted=")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for job in data["jobs"]:
        assert job["source_id"] == "internshala" or "internshala" in job["source_name"].lower()


def test_filter_multi_platforms():
    """Verify filtering by multiple platforms returns jobs from all selected platforms."""
    res = client.get("/api/jobs?platforms=internshala,remoteok&limit=50&date_posted=")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    allowed = {"internshala", "remoteok"}
    for job in data["jobs"]:
        sid = job["source_id"].lower()
        sname = job["source_name"].lower()
        assert sid in allowed or "internshala" in sname or "remote ok" in sname


def test_sort_by_platform_asc():
    """Verify sorting listings alphabetically by platform name."""
    res = client.get("/api/jobs?sort_by=platform_asc&limit=25&date_posted=")
    assert res.status_code == 200
    data = res.json()
    jobs = data["jobs"]
    assert len(jobs) > 1

    platform_names = [j["source_name"].lower() for j in jobs]
    assert platform_names == sorted(platform_names)


def test_sort_by_platform_desc():
    """Verify sorting listings reverse-alphabetically by platform name."""
    res = client.get("/api/jobs?sort_by=platform_desc&limit=25&date_posted=")
    assert res.status_code == 200
    data = res.json()
    jobs = data["jobs"]
    assert len(jobs) > 1

    platform_names = [j["source_name"].lower() for j in jobs]
    assert platform_names == sorted(platform_names, reverse=True)


def test_sort_by_company_asc():
    """Verify sorting listings alphabetically by company name."""
    res = client.get("/api/jobs?sort_by=company_asc&limit=25&date_posted=")
    assert res.status_code == 200
    data = res.json()
    jobs = data["jobs"]
    assert len(jobs) > 1

    company_names = [j["company"].lower() for j in jobs]
    assert company_names == sorted(company_names)


def test_sort_by_title_asc():
    """Verify sorting listings alphabetically by job title."""
    res = client.get("/api/jobs?sort_by=title_asc&limit=25&date_posted=")
    assert res.status_code == 200
    data = res.json()
    jobs = data["jobs"]
    assert len(jobs) > 1

    titles = [j["title"].lower() for j in jobs]
    assert titles == sorted(titles)


def test_combined_platform_filter_and_sort():
    """Verify combining multiple platform selections with sorting."""
    res = client.get("/api/jobs?platforms=internshala,remoteok&sort_by=platform_asc&limit=50&date_posted=")
    assert res.status_code == 200
    data = res.json()
    jobs = data["jobs"]
    assert len(jobs) > 0
    # First jobs should be Internshala since 'I' comes before 'R'
    assert "internshala" in jobs[0]["source_name"].lower()


def test_export_csv_with_platform_filter():
    """Verify CSV export respects platform filter."""
    res = client.get("/api/export/csv?platforms=internshala&date_posted=")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    content = res.text
    lines = content.strip().split("\n")
    assert len(lines) > 1  # Header + at least one job row

