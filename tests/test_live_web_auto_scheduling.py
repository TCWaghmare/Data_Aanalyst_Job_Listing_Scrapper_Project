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
        scraper_scheduler.stop()
        self.client = TestClient(app)
        self.db = Database()

    def test_cron_endpoint_enqueues_due_schedule_without_in_request_scraping(self):
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

        # Track that in-request scraper execution is NEVER invoked
        scrape_called = False
        def mock_exec(*args, **kwargs):
            nonlocal scrape_called
            scrape_called = True
            return {"success": True, "jobs_scanned": 5, "jobs_added": 2}

        original_exec = scraper_scheduler.execute_scrape
        scraper_scheduler.execute_scrape = mock_exec

        try:
            # 2. Call /api/cron
            res = self.client.get("/api/cron")
            self.assertEqual(res.status_code, 200)
            res_json = res.json()
            self.assertTrue(res_json.get("success"))
            self.assertFalse(scrape_called, "Scraping MUST NOT execute inside web request!")

            # 3. Verify next_run_at was advanced to the future
            updated = self.db.get_schedule(sched_id)
            dt_next = datetime.fromisoformat(updated["next_run_at"])
            self.assertGreater(dt_next, now_ist, "next_run_at was not advanced to the future!")

            # 4. Verify run was enqueued in run_logs with status='queued'
            queued_runs = self.db.get_queued_run_requests()
            matching = [r for r in queued_runs if r.get("schedule_id") == sched_id]
            self.assertTrue(len(matching) >= 1, "Due schedule was not enqueued in run_logs!")
            self.assertEqual(matching[0]["status"], "queued")
        finally:
            scraper_scheduler.execute_scrape = original_exec
            scraper_scheduler.delete_schedule(sched_id)

    def test_scraper_run_endpoint_enqueues_request_without_in_request_scraping(self):
        scrape_called = False
        def mock_exec(*args, **kwargs):
            nonlocal scrape_called
            scrape_called = True
            return {"success": True}

        original_exec = scraper_scheduler.execute_scrape
        scraper_scheduler.execute_scrape = mock_exec

        try:
            payload = {
                "adapter_ids": ["internshala", "remoteok"],
                "schedule_name": "Test Manual Run Enqueue",
                "roles": ["Data Analyst"]
            }
            res = self.client.post("/api/scraper/run", json=payload)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data.get("status"), "queued")
            self.assertIn("run_id", data)
            self.assertFalse(scrape_called, "POST /api/scraper/run must only enqueue, never scrape in web request!")

            # Verify entry in run_logs
            run_log = self.db.get_run_log(data["run_id"])
            self.assertIsNotNone(run_log)
            self.assertEqual(run_log["status"], "queued")
            self.assertEqual(run_log["trigger_source"], "manual")
        finally:
            scraper_scheduler.execute_scrape = original_exec

    def test_monitor_endpoint_does_not_trigger_in_request_scraping(self):
        scrape_called = False
        def mock_exec(*args, **kwargs):
            nonlocal scrape_called
            scrape_called = True
            return {"success": True}

        original_exec = scraper_scheduler.execute_scrape
        scraper_scheduler.execute_scrape = mock_exec

        try:
            res = self.client.get("/api/scraper/monitor/live")
            self.assertEqual(res.status_code, 200)
            self.assertFalse(scrape_called, "Monitor polling must not trigger in-process scraping!")
        finally:
            scraper_scheduler.execute_scrape = original_exec

if __name__ == "__main__":
    unittest.main()
