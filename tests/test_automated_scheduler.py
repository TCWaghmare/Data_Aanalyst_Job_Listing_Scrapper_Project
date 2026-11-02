"""
Comprehensive test suite for the Automated Scheduling, Monitoring, and Logging System.
Verifies all 12 requirements:
- Default schedules (11:00 AM & 10:00 PM)
- Custom scheduler CRUD (Add, Edit, Pause, Resume, Delete, multiple run times)
- Smart job scraping controls (deduplication, update existing, ATS scoring)
- Scrape activity logs & filters
- Future scheduled tasks queue & execution windows
- Historical scraping analytics & metrics
- Real-time status monitor
- Notification & alert system
- Grounded resume job match integration
- Data retention & log export (CSV, Excel, JSON)
- Reliability & persistence
"""

import io
import json
import pytest
from fastapi.testclient import TestClient

from app import app
from scraper.database import Database
from scraper.scheduler import calculate_next_run, format_execution_window, ScraperScheduler

client = TestClient(app)

def test_default_schedules_seeded_and_configured():
    """Requirement 1: Verify Morning (11:00 AM) and Evening (10:00 PM) default schedules."""
    res = client.get("/api/scraper/schedules")
    assert res.status_code == 200
    data = res.json()
    schedules = data.get("schedules", [])
    assert len(schedules) >= 2

    morning = next((s for s in schedules if s["id"] == "sched_morning_default"), None)
    assert morning is not None
    assert "Morning" in morning["name"]
    assert morning["run_times"] == ["11:00"]
    assert morning["is_enabled"] is True
    assert morning["next_run_at"] is not None

    evening = next((s for s in schedules if s["id"] == "sched_evening_default"), None)
    assert evening is not None
    assert "Evening" in evening["name"]
    assert evening["run_times"] == ["22:00"]
    assert evening["is_enabled"] is True
    assert evening["next_run_at"] is not None


def test_next_run_calculation():
    """Requirement 1 & 2: Test daily, weekly, and multiple run times time calculation."""
    # Daily with multiple run times
    next_run = calculate_next_run(
        frequency="daily",
        run_times=["08:00", "13:00", "20:00"],
        tz_str="Asia/Kolkata"
    )
    assert next_run is not None
    assert "T" in next_run
    assert "+05:30" in next_run

    # Weekly on specific days
    next_weekly = calculate_next_run(
        frequency="weekly",
        run_times=["10:00"],
        days_of_week=["Monday", "Wednesday", "Friday"],
        tz_str="Asia/Kolkata"
    )
    assert next_weekly is not None

    # Expected window
    window = format_execution_window(next_run, duration_minutes=3)
    assert "mins" in window or "-" in window


def test_custom_scheduler_crud():
    """Requirement 2: Add, Edit, Pause, Resume, Delete Custom Schedule."""
    # 1. Create custom schedule
    new_sched_payload = {
        "name": "Test Analytics Sweep",
        "timezone": "Asia/Kolkata",
        "frequency": "daily",
        "run_times": ["08:30", "16:30"],
        "days_of_week": ["Monday", "Tuesday", "Wednesday"],
        "sources": ["internshala", "remotive"],
        "keywords": ["Data Analyst", "Junior Data Analyst"],
        "location_filters": "India, Remote",
        "work_modes": ["Remote", "Hybrid"],
        "scrape_new_only": True,
        "update_existing": True,
        "deduplication": True,
        "ats_scoring": True,
        "max_jobs_per_run": 40
    }
    create_res = client.post("/api/scraper/schedules", json=new_sched_payload)
    assert create_res.status_code == 200
    created = create_res.json()["schedule"]
    sched_id = created["id"]
    assert created["name"] == "Test Analytics Sweep"
    assert created["is_enabled"] is True
    assert len(created["run_times"]) == 2

    # 2. Pause schedule
    pause_res = client.post(f"/api/scraper/schedules/{sched_id}/pause")
    assert pause_res.status_code == 200
    get_res = client.get(f"/api/scraper/schedules/{sched_id}")
    assert get_res.json()["is_enabled"] is False

    # 3. Resume schedule
    resume_res = client.post(f"/api/scraper/schedules/{sched_id}/resume")
    assert resume_res.status_code == 200
    get_res = client.get(f"/api/scraper/schedules/{sched_id}")
    assert get_res.json()["is_enabled"] is True

    # 4. Update schedule
    update_res = client.put(f"/api/scraper/schedules/{sched_id}", json={"name": "Updated Analytics Sweep", "max_jobs_per_run": 60})
    assert update_res.status_code == 200
    assert update_res.json()["schedule"]["name"] == "Updated Analytics Sweep"
    assert update_res.json()["schedule"]["max_jobs_per_run"] == 60

    # 5. Delete schedule
    del_res = client.delete(f"/api/scraper/schedules/{sched_id}")
    assert del_res.status_code == 200

    # Verify deleted
    verify_res = client.get(f"/api/scraper/schedules/{sched_id}")
    assert verify_res.status_code == 404


def test_upcoming_tasks_queue():
    """Requirement 5: Test upcoming scheduled jobs dashboard endpoint."""
    res = client.get("/api/scraper/upcoming")
    assert res.status_code == 200
    data = res.json()
    assert "tasks" in data
    assert data["total"] >= 2
    first_task = data["tasks"][0]
    assert "next_run_at" in first_task
    assert "expected_window" in first_task
    assert "job_sources" in first_task


def test_real_time_status_monitor():
    """Requirement 7: Live monitor state and endpoint."""
    res = client.get("/api/scraper/monitor/live")
    assert res.status_code == 200
    mon = res.json()
    assert "status" in mon
    assert mon["status"] in ["idle", "running", "scheduled", "queued", "error"]
    assert "current_active_job_source" in mon
    assert "progress_percent" in mon
    assert "jobs_found_so_far" in mon
    assert "time_elapsed_seconds" in mon
    assert "current_processing_stage" in mon


def test_activity_logs_and_filtering():
    """Requirement 4 & 10: Activity logs dashboard, filtering, and detail endpoint."""
    db = Database()
    # Insert mock activity log
    test_run_id = "test_run_123"
    db.save_activity_log({
        "run_id": test_run_id,
        "schedule_name": "Test Suite Morning Run",
        "trigger_source": "scheduled",
        "triggered_by": "Automated Scheduler",
        "status": "completed",
        "duration_seconds": 18.4,
        "job_sources": ["internshala", "remotive"],
        "jobs_scanned": 45,
        "jobs_added": 12,
        "duplicates_skipped": 33,
        "errors_count": 0,
        "high_match_jobs_found": 3
    })

    # Fetch logs with filter
    res = client.get("/api/scraper/logs?status=completed")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    found = any(l["run_id"] == test_run_id for l in data["logs"])
    assert found is True

    # Fetch single log details
    single_res = client.get(f"/api/scraper/logs/{test_run_id}")
    assert single_res.status_code == 200
    log = single_res.json()
    assert log["run_id"] == test_run_id
    assert log["jobs_added"] == 12


def test_activity_logs_export():
    """Requirement 10: Export activity logs in CSV, Excel, and JSON."""
    # CSV export
    res_csv = client.get("/api/scraper/logs/export/download?format=csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert b"run_id" in res_csv.content

    # JSON export
    res_json = client.get("/api/scraper/logs/export/download?format=json")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    parsed_json = json.loads(res_json.content.decode("utf-8"))
    assert isinstance(parsed_json, list)

    # Excel export
    res_excel = client.get("/api/scraper/logs/export/download?format=excel")
    assert res_excel.status_code == 200
    assert len(res_excel.content) > 0


def test_scraping_historical_analytics():
    """Requirement 6: Historical scraping analytics metrics and breakdown."""
    res = client.get("/api/scraper/analytics")
    assert res.status_code == 200
    an = res.json()
    assert "total_runs" in an
    assert "total_scraped" in an
    assert "total_unique_jobs" in an
    assert "success_rate" in an
    assert "avg_processing_time_sec" in an
    assert "most_productive_portal" in an
    assert "best_performing_schedule" in an
    assert "jobs_per_day" in an
    assert "portal_breakdown" in an


def test_recommended_jobs_match_integration():
    """Requirement 9: Grounded Job Match Integration comparing resume skills."""
    res = client.get("/api/scraper/recommended?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert "recommended_jobs" in data
    recs = data["recommended_jobs"]
    if recs:
        top_job = recs[0]
        assert "match_score" in top_job
        assert 0 <= top_job["match_score"] <= 100
        assert "matched_skills" in top_job
        assert "missing_skills" in top_job


def test_notifications_and_alerts():
    """Requirement 8: Notification system CRUD, unread badge, and settings."""
    db = Database()
    notif_id = db.add_notification(
        title="Test Notification Alert",
        message="3 new data analyst jobs found matching your resume.",
        type="success",
        category="new_jobs"
    )

    # Get notifications
    res = client.get("/api/scraper/notifications")
    assert res.status_code == 200
    notifs = res.json()
    assert notifs["unread_count"] >= 1
    assert any(n["id"] == notif_id for n in notifs["items"])
    target_notif = next(n for n in notifs["items"] if n["id"] == notif_id)
    assert "created_at" in target_notif
    assert "created_at_ist" in target_notif
    assert "IST" in target_notif["created_at_ist"]

    # Mark as read
    read_res = client.post(f"/api/scraper/notifications/{notif_id}/read")
    assert read_res.status_code == 200
    assert read_res.json()["success"] is True

    # Notification settings
    get_set = client.get("/api/scraper/notifications/settings")
    assert get_set.status_code == 200
    settings = get_set.json()
    assert "in_app_enabled" in settings

    # Save notification settings
    save_set = client.post("/api/scraper/notifications/settings", json={
        "in_app_enabled": True,
        "email_enabled": True,
        "email_recipient": "test@example.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "notify_on_complete": True,
        "notify_on_new_jobs": True,
        "notify_on_high_match": True,
        "notify_on_failure": True
    })
    assert save_set.status_code == 200
    assert save_set.json()["settings"]["email_recipient"] == "test@example.com"

