import json
import os
import subprocess
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from scraper.database import Database
from scraper.engine import ScraperEngine
from scraper.adapters.base import BaseAdapter
from scraper.models import Job


class DummySlowAdapter(BaseAdapter):
    def __init__(self, platform_id="slow_platform", delay=2.0):
        super().__init__(platform_id=platform_id, platform_name="Slow Platform")
        self.delay = delay

    def scrape(self, roles=None, limit=50, **kwargs):
        time.sleep(self.delay)
        return []


class DummyFailingAdapter(BaseAdapter):
    def __init__(self, platform_id="failing_platform"):
        super().__init__(platform_id=platform_id, platform_name="Failing Platform")

    def scrape(self, roles=None, limit=50, **kwargs):
        raise RuntimeError("Simulated network outage or crash")


class DummySuccessAdapter(BaseAdapter):
    def __init__(self, platform_id="success_platform"):
        super().__init__(platform_id=platform_id, platform_name="Success Platform")

    def scrape(self, roles=None, limit=50, **kwargs):
        import uuid
        uid = uuid.uuid4().hex[:8]
        return [
            Job(
                id=f"test_job_{uid}",
                title=f"Junior Data Analyst {uid}",
                standard_role="Data Analyst",
                company=f"Test Corp {uid}",
                location="Pune, India",
                country="India",
                work_mode="On-Site",
                experience_level="Fresher (0-1 yr)",
                salary="6 LPA",
                source_id=self.platform_id,
                source_name="Success Platform",
                source_url=f"https://example.com/job/{uid}",
                description="Looking for fresher Data Analyst with SQL and Python skills. 0-1 years exp.",
                skills=["SQL", "Python"]
            )
        ]


class TestScraperIsolationAndCli(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        conn = self.db.get_connection()
        conn.execute("DELETE FROM jobs WHERE id LIKE 'test_job_%'")
        conn.commit()
        conn.close()

    def test_per_adapter_timeout_isolation(self):
        """Tests that a timed-out adapter does not block other adapters and is logged to run_logs."""
        engine = ScraperEngine(db=self.db)
        slow_adapter = DummySlowAdapter(platform_id="slow_portal", delay=1.0)
        fast_adapter = DummySuccessAdapter(platform_id="fast_portal")

        engine.adapters = {
            "slow_portal": slow_adapter,
            "fast_portal": fast_adapter
        }

        # Run with 0.2s timeout so slow_portal times out
        run = engine.run(
            adapter_ids=["slow_portal", "fast_portal"],
            adapter_timeout=0.2,
            smart_controls={"request_delay": 0.0}
        )

        self.assertEqual(run.status, "partially_completed")
        self.assertEqual(run.jobs_added, 1)
        self.assertEqual(run.errors_count, 1)

        # Verify adapter breakdown summaries
        self.assertIn("slow_portal", run.adapter_summaries)
        self.assertEqual(run.adapter_summaries["slow_portal"]["status"], "timeout")
        self.assertIn("fast_portal", run.adapter_summaries)
        self.assertEqual(run.adapter_summaries["fast_portal"]["status"], "success")

        # Verify entry in run_logs table
        run_log = self.db.get_run_log(run.run_id)
        self.assertIsNotNone(run_log)
        self.assertEqual(run_log["status"], "partially_completed")
        self.assertEqual(run_log["jobs_added"], 1)
        summaries = json.loads(run_log["adapter_summaries"])
        self.assertEqual(summaries["slow_portal"]["status"], "timeout")
        self.assertEqual(summaries["fast_portal"]["status"], "success")

    def test_per_adapter_failure_isolation(self):
        """Tests that an exception in adapter A does not crash adapter B."""
        engine = ScraperEngine(db=self.db)
        failing_adapter = DummyFailingAdapter(platform_id="crash_portal")
        working_adapter = DummySuccessAdapter(platform_id="work_portal")

        engine.adapters = {
            "crash_portal": failing_adapter,
            "work_portal": working_adapter
        }

        run = engine.run(
            adapter_ids=["crash_portal", "work_portal"],
            adapter_timeout=5.0,
            smart_controls={"request_delay": 0.0}
        )

        self.assertEqual(run.status, "partially_completed")
        self.assertEqual(run.jobs_added, 1)
        self.assertEqual(run.errors_count, 1)
        self.assertEqual(run.adapter_summaries["crash_portal"]["status"], "error")
        self.assertEqual(run.adapter_summaries["work_portal"]["status"], "success")

    def test_total_failure_status(self):
        """Tests that when all attempted adapters fail, run status is 'failed'."""
        engine = ScraperEngine(db=self.db)
        failing_adapter = DummyFailingAdapter(platform_id="crash_only")

        engine.adapters = {
            "crash_only": failing_adapter
        }

        run = engine.run(
            adapter_ids=["crash_only"],
            adapter_timeout=5.0,
            smart_controls={"request_delay": 0.0}
        )

        self.assertEqual(run.status, "failed")
        self.assertEqual(run.jobs_added, 0)
        self.assertEqual(run.errors_count, 1)

        run_log = self.db.get_run_log(run.run_id)
        self.assertEqual(run_log["status"], "failed")

    def test_run_scraper_cli_total_failure_exits_nonzero(self):
        """Tests that run_scraper.py exits non-zero (1) when all adapters fail."""
        # Run a subprocess calling python run_scraper.py with an invalid adapter that fails or mock
        code = """
import sys
from unittest.mock import patch
from scraper.engine import ScraperEngine
from scraper.models import ScrapeRun

def mock_run(*args, **kwargs):
    run = ScrapeRun(run_id="fail_test", started_at="2026-01-01T00:00:00", status="failed")
    run.adapter_summaries = {}
    return run

with patch.object(ScraperEngine, "run", side_effect=mock_run):
    import run_scraper
    run_scraper.main()
"""
        proc = subprocess.run(
            [sys.executable, "-c", code, "--sources", "nonexistent"],
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 1, f"Process should exit 1 on total failure, got {proc.returncode}. Output:\n{proc.stdout}\n{proc.stderr}")

    def test_run_scraper_cli_success_exits_zero(self):
        """Tests that run_scraper.py exits 0 when scraping succeeds."""
        code = """
import sys
from unittest.mock import patch
from scraper.engine import ScraperEngine
from scraper.models import ScrapeRun

def mock_run(*args, **kwargs):
    run = ScrapeRun(run_id="succ_test", started_at="2026-01-01T00:00:00", status="completed", jobs_added=3, jobs_scanned=10)
    run.adapter_summaries = {"test": {"name": "Test", "status": "success", "jobs_added": 3, "jobs_scanned": 10, "duration_seconds": 1.2}}
    return run

with patch.object(ScraperEngine, "run", side_effect=mock_run):
    import run_scraper
    run_scraper.main()
"""
        proc = subprocess.run(
            [sys.executable, "-c", code, "--all"],
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0, f"Process should exit 0 on success, got {proc.returncode}. Output:\n{proc.stdout}\n{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
