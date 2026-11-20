import os
import sys
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from app import app
from scraper.database import Database
from scraper.scheduler import scraper_scheduler, calculate_next_run

class TestLiveWebAutoScheduling(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = Database()

    def test_cron_endpoint_evaluates_and_executes_due_schedule(self):
        tz = ZoneInfo("Asia/Kolkata")
        now_ist = datetime.now(tz)

        # 1. Create a schedule that is due (next_run_at in the past by 10s)
        overdue_time = (now_ist - timedelta(seconds=10)).isoformat()
        sched_data = {
            "name": "Live Web Auto Cron Test",
            "timezone": "Asia/Kolkata",
            "frequency": "daily",
            "run_times": [(now_ist - timedelta(minutes=1)).strftime("%H:%M")],
            "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "sources": ["internshala"],
            "is_enabled": True
        }
        created = scraper_scheduler.create_custom_schedule(sched_data)
        sched_id = created["id"]

        # Ensure next_run_at is overdue and monitor is idle
        created["next_run_at"] = overdue_time
        self.db.save_schedule(created)
        scraper_scheduler.live_monitor["status"] = "idle"

        # Mock execute_scrape to avoid hitting external networks during unit test
        mock_called = False
        def mock_exec(schedule_id=None, custom_params=None, trigger_source="manual", triggered_by="System"):
            nonlocal mock_called
            mock_called = True
            return {"success": True, "jobs_scanned": 5, "jobs_added": 2}

        original_exec = scraper_scheduler.execute_scrape
        scraper_scheduler.execute_scrape = mock_exec

        try:
            # 2. Call /api/cron
            res = self.client.get("/api/cron")
            self.assertEqual(res.status_code, 200)
            res_json = res.json()
            self.assertTrue(res_json.get("success"))
            self.assertTrue(mock_called, "The due schedule was not executed by /api/cron!")

            # Verify next_run_at was advanced to the future
            updated = self.db.get_schedule(sched_id)
            dt_next = datetime.fromisoformat(updated["next_run_at"])
            self.assertGreater(dt_next, now_ist, "next_run_at was not advanced to the future!")
        finally:
            scraper_scheduler.execute_scrape = original_exec
            scraper_scheduler.delete_schedule(sched_id)

    def test_monitor_endpoint_auto_triggers_due_schedules(self):
        tz = ZoneInfo("Asia/Kolkata")
        now_ist = datetime.now(tz)

        overdue_time = (now_ist - timedelta(seconds=5)).isoformat()
        sched_data = {
            "name": "Monitor Auto-Trigger Test",
            "timezone": "Asia/Kolkata",
            "frequency": "daily",
            "run_times": [(now_ist - timedelta(minutes=1)).strftime("%H:%M")],
            "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "sources": ["internshala"],
            "is_enabled": True
        }
        created = scraper_scheduler.create_custom_schedule(sched_data)
        sched_id = created["id"]
        created["next_run_at"] = overdue_time
        self.db.save_schedule(created)
        scraper_scheduler.live_monitor["status"] = "idle"

        mock_called = False
        def mock_exec(schedule_id=None, custom_params=None, trigger_source="manual", triggered_by="System"):
            nonlocal mock_called
            mock_called = True
            return {"success": True, "jobs_scanned": 1, "jobs_added": 1}

        original_exec = scraper_scheduler.execute_scrape
        scraper_scheduler.execute_scrape = mock_exec

        try:
            # Polling /api/scraper/monitor/live must automatically check and trigger due schedule
            res = self.client.get("/api/scraper/monitor/live")
            self.assertEqual(res.status_code, 200)
            # Give thread a tick
            import time
            time.sleep(0.3)
            self.assertTrue(mock_called, "Monitor polling did not auto-trigger due schedule!")
        finally:
            scraper_scheduler.execute_scrape = original_exec
            scraper_scheduler.delete_schedule(sched_id)

if __name__ == "__main__":
    unittest.main()
