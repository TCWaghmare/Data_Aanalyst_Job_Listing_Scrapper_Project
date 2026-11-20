import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from scraper.scheduler import ScraperScheduler, calculate_next_run
from scraper.database import Database

def test_custom_schedule_triggers_automatically():
    db = Database()
    scheduler = ScraperScheduler(db=db)
    
    # 1. Test calculation with various time formats
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    target_dt = now_ist + timedelta(seconds=2)
    time_str_12h = target_dt.strftime("%I:%M %p").lstrip("0")
    time_str_24h = target_dt.strftime("%H:%M")

    print(f"[TEST] Current IST Time: {now_ist.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[TEST] Testing 12-hour format '{time_str_12h}' and 24-hour format '{time_str_24h}'")

    res_12h = calculate_next_run("daily", [time_str_12h], tz_str="Asia/Kolkata")
    assert res_12h, "calculate_next_run failed for 12h format"

    # 2. Mock scraper execution
    triggered = False
    executed_info = {}

    def mock_execute(schedule_id=None, custom_params=None, trigger_source="manual", triggered_by="System"):
        nonlocal triggered, executed_info
        triggered = True
        executed_info = {
            "schedule_id": schedule_id,
            "trigger_source": trigger_source,
            "triggered_by": triggered_by
        }
        print(f"[TEST] Mock scraper executed for schedule_id={schedule_id}, trigger_source={trigger_source}")
        return {"success": True, "status": "completed", "jobs_scanned": 10, "jobs_added": 5}

    scheduler.execute_scrape = mock_execute

    # Create custom schedule
    sched_payload = {
        "name": "Auto Trigger Verification Test",
        "timezone": "Asia/Kolkata",
        "frequency": "daily",
        "run_times": [time_str_24h],
        "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "sources": ["all"],
        "job_portals": ["all"],
        "keywords": ["Data Analyst", "Power BI"],
        "is_enabled": True
    }
    
    custom_sched = scheduler.create_custom_schedule(sched_payload)
    sched_id = custom_sched["id"]
    print(f"[TEST] Created custom schedule: {sched_id}, Next run: {custom_sched['next_run_at']}")
    assert custom_sched["is_enabled"] is True

    # 3. Simulate clock arrival (set next_run_at to 1 second ago)
    triggered = False
    scheduler.live_monitor["status"] = "idle"
    overdue_time = (datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(seconds=1)).isoformat()
    custom_sched["next_run_at"] = overdue_time
    scheduler.db.save_schedule(custom_sched)

    # 4. Trigger due schedules check
    scheduler._check_and_trigger_due_schedules()

    # Allow thread to start
    time.sleep(0.5)

    assert triggered, "Custom schedule was NOT triggered when due time arrived!"
    assert executed_info["schedule_id"] == sched_id
    assert executed_info["trigger_source"] == "scheduled"
    assert executed_info["triggered_by"] == "Automated Scheduler"

    # Verify that next_run_at has been advanced to future
    updated_sched = scheduler.db.get_schedule(sched_id)
    print(f"[TEST] Advanced next run after execution: {updated_sched['next_run_at']}")
    dt_advanced = datetime.fromisoformat(updated_sched["next_run_at"])
    now_check = datetime.now(dt_advanced.tzinfo)
    assert dt_advanced > now_check, "next_run_at was not advanced to the future after execution!"

    # Clean up test schedule
    scheduler.delete_schedule(sched_id)
    print("[TEST] SUCCESS! Custom schedule verified: triggers automatically at scheduled time and advances accurately.")

if __name__ == "__main__":
    test_custom_schedule_triggers_automatically()
