"""
Tests for Job Freshness Filters, Scrape Date Tracking, Duplicate Protection, and Analytics.
"""

import os
import tempfile
import pytest
from datetime import datetime, timedelta
from scraper.database import Database
from scraper.models import Job
from fastapi.testclient import TestClient


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(db_path=path)
    yield db
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def test_first_scraped_date_tracking_and_immutability(temp_db):
    """
    Test that first_scraped_at is permanently stored on discovery,
    never overwritten upon future re-scraping, and last_checked_at & scrape_count are updated.
    """
    first_time = (datetime.now() - timedelta(days=10)).isoformat()

    initial_job = Job(
        id="job_fresh_001",
        title="Junior Data Analyst",
        company="Acme Analytics",
        location="Bengaluru, India",
        description="SQL and Excel required for fresher role.",
        source_name="LinkedIn",
        source_id="linkedin",
        source_url="https://linkedin.com/jobs/view/99901",
        role_category="Core Analytics",
        standard_role="Data Analyst",
        experience_level="0-1 Years",
        published_at=first_time,
        discovered_at=first_time,
        first_scraped_at=first_time,
        last_checked_at=first_time,
        scrape_count=1,
        status="active"
    )

    # 1. First Discovery - returns True for newly inserted job
    is_new = temp_db.save_job(initial_job)
    assert is_new is True

    fetched1 = temp_db.get_job_by_id("job_fresh_001")
    assert fetched1 is not None
    assert fetched1.first_scraped_at == first_time
    assert fetched1.last_checked_at == first_time
    assert fetched1.scrape_count == 1
    assert fetched1.status == "active"

    # 2. Re-scraping the same job 5 days later with updated description
    second_time = (datetime.now() - timedelta(days=5)).isoformat()
    re_scraped_job = Job(
        id="job_fresh_001",
        title="Junior Data Analyst",
        company="Acme Analytics",
        location="Bengaluru, India",
        description="SQL, Excel and Tableau required for fresher role.",  # updated JD
        source_name="LinkedIn",
        source_id="linkedin",
        source_url="https://linkedin.com/jobs/view/99901",
        role_category="Core Analytics",
        standard_role="Data Analyst",
        experience_level="0-1 Years",
        published_at=first_time,
        discovered_at=second_time,
        first_scraped_at=second_time,  # Should NOT overwrite original!
        last_checked_at=second_time
    )

    is_new2 = temp_db.save_job(re_scraped_job)
    assert is_new2 is False, "Must return False indicating duplicate/re-scrape"

    # Retrieve from DB to verify persistence and immutability
    fetched2 = temp_db.get_job_by_id("job_fresh_001")
    assert fetched2 is not None
    # CRITICAL: Original first_scraped_at must be strictly preserved!
    assert fetched2.first_scraped_at == first_time
    # last_checked_at must be updated
    assert fetched2.last_checked_at >= second_time
    # scrape_count must be incremented
    assert fetched2.scrape_count == 2
    # Description was updated because changes were detected
    assert "Tableau" in fetched2.description

    # 3. Third scrape (re-validation)
    is_new3 = temp_db.save_job(re_scraped_job)
    assert is_new3 is False
    fetched3 = temp_db.get_job_by_id("job_fresh_001")
    assert fetched3.first_scraped_at == first_time  # STILL IMMUTABLE!
    assert fetched3.scrape_count == 3

    # Total jobs count in database must still be exactly 1 (no duplicates)
    all_jobs, total = temp_db.get_jobs(limit=100)
    assert total == 1


def test_scrape_freshness_filters(temp_db):
    """
    Test filtering jobs by scrape freshness: today, 24h, 3d, 7d, 30d, older_30d.
    """
    now = datetime.now()

    # Job A: First scraped 2 hours ago (Today / 24h / 3d / 7d / 30d)
    job_today = Job(
        id="job_today_01",
        title="Fresher SQL Analyst",
        company="Company A",
        location="Remote",
        description="Fresher role",
        source_name="Indeed",
        source_id="indeed",
        source_url="https://indeed.com/view/101",
        role_category="Core Analytics",
        standard_role="Data Analyst",
        first_scraped_at=(now - timedelta(hours=2)).isoformat(),
        last_checked_at=now.isoformat()
    )

    # Job B: First scraped 5 days ago (7d / 30d)
    job_5d = Job(
        id="job_5d_02",
        title="BI Developer Trainee",
        company="Company B",
        location="Mumbai, India",
        description="Power BI fresher",
        source_name="Naukri",
        source_id="naukri",
        source_url="https://naukri.com/view/102",
        role_category="Core Analytics",
        standard_role="BI Analyst",
        first_scraped_at=(now - timedelta(days=5)).isoformat(),
        last_checked_at=now.isoformat()
    )

    # Job C: First scraped 45 days ago (older_30d)
    job_old = Job(
        id="job_old_03",
        title="Data Engineer Intern",
        company="Company C",
        location="Hyderabad, India",
        description="Python intern",
        source_name="Internshala",
        source_id="internshala",
        source_url="https://internshala.com/view/103",
        role_category="Core Analytics",
        standard_role="Data Engineer",
        first_scraped_at=(now - timedelta(days=45)).isoformat(),
        last_checked_at=now.isoformat()
    )

    temp_db.save_job(job_today)
    temp_db.save_job(job_5d)
    temp_db.save_job(job_old)

    # Test 'today' freshness filter
    jobs_today, total_today = temp_db.get_jobs(scrape_freshness="today")
    assert total_today == 1
    assert jobs_today[0].title == "Fresher SQL Analyst"

    # Test '24h' freshness filter
    jobs_24h, total_24h = temp_db.get_jobs(scrape_freshness="24h")
    assert total_24h == 1
    assert jobs_24h[0].title == "Fresher SQL Analyst"

    # Test '7d' freshness filter (should include Job A and Job B)
    jobs_7d, total_7d = temp_db.get_jobs(scrape_freshness="7d")
    assert total_7d == 2

    # Test '30d' freshness filter (should include Job A and Job B)
    jobs_30d, total_30d = temp_db.get_jobs(scrape_freshness="30d")
    assert total_30d == 2

    # Test 'older_30d' freshness filter (should include Job C)
    jobs_older, total_older = temp_db.get_jobs(scrape_freshness="older_30d")
    assert total_older == 1
    assert jobs_older[0].title == "Data Engineer Intern"


def test_first_scraped_sorting(temp_db):
    """
    Test sorting by first_scraped_desc and first_scraped_asc.
    """
    now = datetime.now()

    job1 = Job(
        id="sort_job_1",
        title="Oldest Job",
        standard_role="Data Analyst",
        company="Old Co",
        location="India",
        description="desc",
        source_name="LinkedIn",
        source_id="linkedin",
        source_url="https://linkedin.com/1",
        first_scraped_at=(now - timedelta(days=20)).isoformat()
    )
    job2 = Job(
        id="sort_job_2",
        title="Middle Job",
        standard_role="Data Analyst",
        company="Mid Co",
        location="India",
        description="desc",
        source_name="LinkedIn",
        source_id="linkedin",
        source_url="https://linkedin.com/2",
        first_scraped_at=(now - timedelta(days=10)).isoformat()
    )
    job3 = Job(
        id="sort_job_3",
        title="Newest Job",
        standard_role="Data Analyst",
        company="New Co",
        location="India",
        description="desc",
        source_name="LinkedIn",
        source_id="linkedin",
        source_url="https://linkedin.com/3",
        first_scraped_at=(now - timedelta(days=1)).isoformat()
    )

    temp_db.save_job(job1)
    temp_db.save_job(job2)
    temp_db.save_job(job3)

    # Sort: Newest Scraped First (first_scraped_desc)
    jobs_desc, _ = temp_db.get_jobs(sort_by="first_scraped_desc")
    assert [j.title for j in jobs_desc] == ["Newest Job", "Middle Job", "Oldest Job"]

    # Sort: Oldest Scraped First (first_scraped_asc)
    jobs_asc, _ = temp_db.get_jobs(sort_by="first_scraped_asc")
    assert [j.title for j in jobs_asc] == ["Oldest Job", "Middle Job", "Newest Job"]


def test_freshness_statistics(temp_db):
    """
    Test get_statistics freshness fields.
    """
    now = datetime.utcnow()

    # Add 1 today, 1 3-days ago, 1 40-days ago (re-scraped twice)
    temp_db.save_job(Job(
        id="stat_job_1",
        title="Job 1", standard_role="Data Analyst", company="A", location="X", description="D",
        source_name="LinkedIn", source_id="linkedin", source_url="https://ex.com/1",
        first_scraped_at=now.isoformat()
    ))
    temp_db.save_job(Job(
        id="stat_job_2",
        title="Job 2", standard_role="Data Analyst", company="B", location="X", description="D",
        source_name="LinkedIn", source_id="linkedin", source_url="https://ex.com/2",
        first_scraped_at=(now - timedelta(days=3)).isoformat()
    ))
    j3 = Job(
        id="stat_job_3",
        title="Job 3", standard_role="Data Analyst", company="C", location="X", description="D",
        source_name="LinkedIn", source_id="linkedin", source_url="https://ex.com/3",
        first_scraped_at=(now - timedelta(days=40)).isoformat()
    )
    temp_db.save_job(j3)
    temp_db.save_job(j3)  # re-scrape to increment scrape_count

    stats = temp_db.get_statistics()
    assert stats["jobs_added_today"] == 1
    assert stats["jobs_added_this_week"] == 2
    assert stats["jobs_added_this_month"] == 2
    assert stats["jobs_older_30d"] == 1
    assert "avg_daily_discovery" in stats
    assert "new_vs_existing_ratio" in stats
    assert "growth_trend" in stats
    assert len(stats["growth_trend"]) <= 7
    assert len(stats["growth_trend"]) > 0


def test_api_freshness_endpoints():
    """
    Test FastAPI endpoints with scrape_freshness and sort_by params.
    """
    from app import app
    client = TestClient(app)

    # Test /api/jobs with scrape_freshness
    res = client.get("/api/jobs?scrape_freshness=30d")
    assert res.status_code == 200
    data = res.json()
    assert "jobs" in data
    assert "total" in data
    assert data["scrape_freshness_filter"] == "30d"

    # Test /api/jobs with first_scraped_desc sort
    res_sort = client.get("/api/jobs?sort_by=first_scraped_desc")
    assert res_sort.status_code == 200
    data_sort = res_sort.json()
    assert "jobs" in data_sort

    # Test /api/stats includes freshness fields
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "jobs_added_today" in stats
    assert "jobs_added_this_week" in stats
    assert "jobs_added_this_month" in stats
    assert "growth_trend" in stats
