import pytest
from fastapi.testclient import TestClient
from app import app, db

client = TestClient(app)

def test_job_status_and_bookmark_endpoints():
    # Get a job from DB
    jobs, total = db.get_jobs(limit=1)
    assert len(jobs) > 0, "Expected at least 1 job in database"
    job_id = jobs[0].id

    # Test status update to 'interview'
    res = client.post(f"/api/jobs/{job_id}/status", json={"status": "interview"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "interview"
    assert data["success"] is True

    # Check that job retrieved reflects status
    job = db.get_job_by_id(job_id)
    assert job.application_status == "interview"

    # Test status update to 'applied'
    res = client.post(f"/api/jobs/{job_id}/status", json={"status": "applied"})
    assert res.status_code == 200
    job = db.get_job_by_id(job_id)
    assert job.application_status == "applied"
    assert job.is_applied is True

    # Test bookmark toggle
    res = client.post(f"/api/jobs/{job_id}/bookmark")
    assert res.status_code == 200
    data = res.json()
    assert "is_bookmarked" in data
    assert data["success"] is True

    # Reset back to new / not applied
    client.post(f"/api/jobs/{job_id}/status", json={"status": "new"})
