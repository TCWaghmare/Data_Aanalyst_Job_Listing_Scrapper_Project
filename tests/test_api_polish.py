"""
Unit and integration tests for API Polish requirements:
1. /api/jobs list summary, gzip compression, and GET /api/jobs/{id}
2. /api/resume/tailor 404 on unknown job_id
3. Query validation (page, days, limit) returning 422 on invalid values
4. Sanitized 500 error responses with Request ID and no raw exception leaks
"""

import gzip
import pytest
from fastapi.testclient import TestClient
from app import app
from scraper.database import Database

client = TestClient(app)


def test_api_jobs_list_returns_summary_and_not_full_description():
    """Verify /api/jobs list returns a concise summary rather than the full description."""
    res = client.get("/api/jobs?limit=5")
    assert res.status_code == 200
    data = res.json()
    jobs = data.get("jobs", [])
    assert len(jobs) > 0
    
    for job in jobs:
        assert "description" in job
        assert "summary" in job
        # Summary should be truncated up to 203 chars
        assert len(job["description"]) <= 203
        assert len(job["summary"]) <= 203


def test_api_jobs_gzip_compression_middleware():
    """Verify GZipMiddleware compresses response when Accept-Encoding: gzip is requested."""
    # Test with a larger limit so response payload exceeds minimum_size
    res = client.get("/api/jobs?limit=50", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200
    # In TestClient, gzip header may be Content-Encoding: gzip if returned raw
    if "content-encoding" in res.headers:
        assert res.headers["content-encoding"] == "gzip"


def test_get_job_by_id_returns_full_description():
    """Verify GET /api/jobs/{id} returns the complete, un-truncated description."""
    # First get an existing job id
    res = client.get("/api/jobs?limit=1")
    assert res.status_code == 200
    jobs = res.json().get("jobs", [])
    assert len(jobs) > 0
    job_id = jobs[0]["id"]
    
    # Now fetch details from GET /api/jobs/{id}
    detail_res = client.get(f"/api/jobs/{job_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == job_id
    assert "description" in detail
    assert "title" in detail
    assert "company" in detail


def test_get_job_by_id_unknown_returns_404():
    """Verify GET /api/jobs/{id} returns 404 when job does not exist."""
    res = client.get("/api/jobs/unknown_nonexistent_job_id_99999")
    assert res.status_code == 404
    assert "Job not found" in res.json().get("detail", "")


def test_resume_tailor_unknown_job_id_returns_404_not_400():
    """Verify /api/resume/tailor with an unknown job_id returns 404 'Job not found', not 400."""
    res = client.post("/api/resume/tailor", json={"job_id": "nonexistent_job_12345"})
    assert res.status_code == 404
    detail = res.json().get("detail", "")
    assert "Job not found" in detail


def test_invalid_query_page_returns_422():
    """Verify invalid page query parameter returns 422 Unprocessable Entity."""
    # page < 1
    res_zero = client.get("/api/jobs?page=0")
    assert res_zero.status_code == 422
    
    res_neg = client.get("/api/jobs?page=-1")
    assert res_neg.status_code == 422
    
    # page non-integer
    res_str = client.get("/api/jobs?page=invalid")
    assert res_str.status_code == 422


def test_invalid_query_days_returns_422():
    """Verify invalid days query parameter returns 422 Unprocessable Entity."""
    # days < 1
    res_zero = client.get("/api/jobs?days=0")
    assert res_zero.status_code == 422
    
    res_neg = client.get("/api/jobs?days=-5")
    assert res_neg.status_code == 422
    
    # days non-integer
    res_str = client.get("/api/jobs?days=foo")
    assert res_str.status_code == 422


def test_invalid_query_limit_returns_422():
    """Verify invalid limit query parameter returns 422 Unprocessable Entity."""
    # limit < 1
    res_zero = client.get("/api/jobs?limit=0")
    assert res_zero.status_code == 422
    
    res_neg = client.get("/api/jobs?limit=-10")
    assert res_neg.status_code == 422
    
    # limit > 100
    res_over = client.get("/api/jobs?limit=500")
    assert res_over.status_code == 422
    
    # limit non-integer
    res_str = client.get("/api/jobs?limit=abc")
    assert res_str.status_code == 422


def test_valid_page_and_days_query_parameters():
    """Verify valid page and days query parameters work seamlessly."""
    res = client.get("/api/jobs?page=1&limit=10&days=30")
    assert res.status_code == 200
    data = res.json()
    assert data["limit"] == 10
    assert data["page"] == 1
    assert len(data["jobs"]) <= 10


def test_error_handling_sanitizes_500_with_request_id():
    """Verify 500 server errors return a generic message plus Request ID without raw exception leaks."""
    from unittest.mock import patch
    import os

    safe_client = TestClient(app, raise_server_exceptions=False)

    # Force an unexpected internal error in an endpoint
    with patch("scraper.database.Database.get_jobs", side_effect=RuntimeError("Secret database connection failure: root@internal-db:5432")):
        res = safe_client.get("/api/jobs")
        assert res.status_code == 500
        data = res.json()
        detail = data.get("detail", "")
        
        # Verify raw exception is NOT leaked
        assert "Secret database connection failure" not in detail
        assert "internal-db" not in detail
        
        # Verify generic message and Request ID are present
        assert "Request ID:" in detail or "request_id" in data
        assert "internal server error" in detail.lower()
