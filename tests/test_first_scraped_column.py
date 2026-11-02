import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app import app, db
from scraper.models import Job

client = TestClient(app)

def test_api_jobs_includes_first_scraped_at():
    """Ensure /api/jobs returns first_scraped_at for all job listings."""
    res = client.get("/api/jobs?limit=5")
    assert res.status_code == 200
    data = res.json()
    jobs = data.get("jobs", data.get("items", []))
    assert len(jobs) > 0

    for job in jobs:
        assert "first_scraped_at" in job, "Job dictionary must contain first_scraped_at"
        assert job["first_scraped_at"] is not None
        assert len(str(job["first_scraped_at"])) > 0

def test_first_scraped_at_immutability_on_duplicate_scrapes():
    """
    Ensure that when a job is scraped multiple times,
    first_scraped_at is strictly retained from the initial scrape and never overwritten.
    """
    earliest_time = "2026-06-10T05:00:00.000000"
    subsequent_time_1 = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    subsequent_time_2 = (datetime.utcnow() + timedelta(hours=5)).isoformat()

    test_job_id = "test_immutability_job_99"
    test_job = Job(
        id=test_job_id,
        title="Senior BI Analyst - First Scrape Test",
        company="Global Analytics Corp",
        location="Bengaluru, India",
        description="Initial job description for test",
        source_name="LinkedIn",
        source_id="linkedin",
        source_url="https://linkedin.com/jobs/view/test99",
        role_category="Core Analytics",
        standard_role="Data Analyst",
        experience_level="0-1 Years",
        published_at="2026-06-10",
        discovered_at=earliest_time,
        first_scraped_at=earliest_time,
        last_checked_at=earliest_time,
        scrape_count=1,
        status="active"
    )

    # 1. First scrape
    is_new = db.save_job(test_job)
    assert is_new is True, "First save should be treated as new"

    job_after_first = db.get_job_by_id(test_job_id)
    assert job_after_first.first_scraped_at == earliest_time

    # 2. Second scrape (e.g. 2 hours later)
    test_job_2nd = Job(
        id=test_job_id,
        title="Senior BI Analyst - First Scrape Test",
        company="Global Analytics Corp",
        location="Bengaluru, India",
        description="Updated job description with more skills",
        source_name="LinkedIn",
        source_id="linkedin",
        source_url="https://linkedin.com/jobs/view/test99",
        role_category="Core Analytics",
        standard_role="Data Analyst",
        experience_level="0-1 Years",
        published_at="2026-06-10",
        discovered_at=subsequent_time_1,
        first_scraped_at=subsequent_time_1,  # New timestamp passed in
        last_checked_at=subsequent_time_1
    )
    is_new_2 = db.save_job(test_job_2nd)
    assert is_new_2 is False, "Duplicate save should return False"

    job_after_second = db.get_job_by_id(test_job_id)
    # MUST RETAIN EARLIEST TIMESTAMP!
    assert job_after_second.first_scraped_at == earliest_time, "first_scraped_at must remain the earliest timestamp"
    assert job_after_second.scrape_count == 2

    # 3. Third scrape (e.g. 5 hours later)
    test_job_3rd = Job(
        id=test_job_id,
        title="Senior BI Analyst - First Scrape Test",
        company="Global Analytics Corp",
        location="Bengaluru, India",
        description="Third scrape validation check",
        source_name="LinkedIn",
        source_id="linkedin",
        source_url="https://linkedin.com/jobs/view/test99",
        role_category="Core Analytics",
        standard_role="Data Analyst",
        experience_level="0-1 Years",
        published_at="2026-06-10",
        discovered_at=subsequent_time_2,
        first_scraped_at=subsequent_time_2,
        last_checked_at=subsequent_time_2
    )
    is_new_3 = db.save_job(test_job_3rd)
    assert is_new_3 is False

    job_after_third = db.get_job_by_id(test_job_id)
    assert job_after_third.first_scraped_at == earliest_time, "first_scraped_at must still be earliest timestamp"
    assert job_after_third.scrape_count == 3

    # Clean up test row
    with db.get_connection() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (test_job_id,))
