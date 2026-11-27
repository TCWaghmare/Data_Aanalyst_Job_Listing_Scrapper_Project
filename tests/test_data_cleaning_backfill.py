"""
Unit and integration tests for job data cleaning at ingest and backfill normalization:
1. published_at ISO-8601 UTC handling (epoch sec/millis, RFC-2822, ISO with offsets, relative dates).
2. experience_level strict mapping to: fresher, 0-1, 1-2, 2+, unknown (covering all 15 variants).
3. Stripping tracking parameters (trackingId, refId, trk, utm_*) and dedup hash consistency.
4. Expiration logic (30 days) and is_active flag.
5. Ingest normalization in Job Pydantic model.
6. /api/stats calculation using published_at for freshness and jobs_older_30d.
7. End-to-end backfill script execution on test database.
"""

import datetime
from datetime import timezone
import os
import sqlite3
import tempfile
import unittest
from fastapi.testclient import TestClient

from scraper.cleaners import (
    clean_source_url,
    normalize_published_at,
    normalize_experience_level,
    compute_clean_dedup_hash,
    calculate_expires_at,
    is_job_active,
    ALLOWED_EXPERIENCE_LEVELS,
    EXPERIENCE_LEVEL_MAP,
)
from scraper.models import Job
from scraper.database import Database
from scripts.backfill_normalize import run_backfill


class TestDataCleaningAndNormalization(unittest.TestCase):

    def test_epoch_seconds_and_millis_normalization(self):
        # 1696507200 = 2023-10-05 12:00:00 UTC (Arbeitnow style epoch)
        dt_sec_int = normalize_published_at(1696507200)
        self.assertEqual(dt_sec_int, "2023-10-05T12:00:00Z")

        dt_sec_str = normalize_published_at("1696507200")
        self.assertEqual(dt_sec_str, "2023-10-05T12:00:00Z")

        # Milliseconds epoch: 1696507200000
        dt_millis_int = normalize_published_at(1696507200000)
        self.assertEqual(dt_millis_int, "2023-10-05T12:00:00Z")

        dt_millis_str = normalize_published_at("1696507200000")
        self.assertEqual(dt_millis_str, "2023-10-05T12:00:00Z")

    def test_rfc_2822_date_normalization(self):
        # We Work Remotely RSS feed samples
        rfc_sample_1 = "Fri, 27 Nov 2026 17:30:00 +0000"
        self.assertEqual(normalize_published_at(rfc_sample_1), "2026-11-27T17:30:00Z")

        rfc_sample_gmt = "Thu, 05 Oct 2023 12:00:00 GMT"
        self.assertEqual(normalize_published_at(rfc_sample_gmt), "2023-10-05T12:00:00Z")

        # RFC with non-UTC offset: 27 Nov 2026 23:00:00 +0530 is 17:30:00 UTC
        rfc_sample_ist = "Fri, 27 Nov 2026 23:00:00 +0530"
        self.assertEqual(normalize_published_at(rfc_sample_ist), "2026-11-27T17:30:00Z")

    def test_iso_8601_date_normalization(self):
        # ISO with Z
        self.assertEqual(normalize_published_at("2026-11-27T17:30:00Z"), "2026-11-27T17:30:00Z")

        # ISO with timezone offset (+05:30)
        self.assertEqual(normalize_published_at("2026-11-27T23:00:00+05:30"), "2026-11-27T17:30:00Z")

        # ISO with negative timezone offset (-05:00)
        self.assertEqual(normalize_published_at("2026-11-27T12:30:00-05:00"), "2026-11-27T17:30:00Z")

        # Simple YYYY-MM-DD
        self.assertEqual(normalize_published_at("2026-11-27"), "2026-11-27T00:00:00Z")

    def test_relative_date_normalization(self):
        res_today = normalize_published_at("today")
        self.assertTrue(res_today.endswith("Z"))

        res_yesterday = normalize_published_at("yesterday")
        self.assertTrue(res_yesterday.endswith("Z"))

        res_days_ago = normalize_published_at("3 days ago")
        self.assertTrue(res_days_ago.endswith("Z"))

    def test_experience_level_maps_all_15_variants(self):
        # All 15 existing database variants must map strictly to 'fresher' or '0-1'
        expected_mappings = {
            "0 - 1 Year": "0-1",
            "0 - 1 Year (Entry-Level)": "0-1",
            "0 - 1 Year (Fresher)": "fresher",
            "0 - 1 Year (Junior / Entry-Level)": "0-1",
            "0 - 1 Year (Junior)": "0-1",
            "0-1 Yr": "0-1",
            "0-1 Yr Exp": "0-1",
            "1 year(s)": "0-1",
            "Fresher (0 - 1 Year)": "fresher",
            "Fresher (0 Years)": "fresher",
            "Fresher (0-1 yr)": "fresher",
            "Freshers & Experienced Candidates": "fresher",
            "Freshers/Experienced": "fresher",
            "Internship / Trainee (0 Years)": "fresher",
            "No experience required": "fresher",
        }
        self.assertEqual(len(expected_mappings), 15)

        for raw_val, expected_norm in expected_mappings.items():
            result = normalize_experience_level(raw_val)
            self.assertEqual(result, expected_norm, f"Failed for variant: {raw_val}")
            self.assertIn(result, ALLOWED_EXPERIENCE_LEVELS)

        # Other categories
        self.assertEqual(normalize_experience_level("1 - 2 Years"), "1-2")
        self.assertEqual(normalize_experience_level("2-4 Years"), "2+")
        self.assertEqual(normalize_experience_level("Senior Lead 10 Years"), "2+")
        self.assertEqual(normalize_experience_level("Not specified"), "unknown")
        self.assertEqual(normalize_experience_level(None), "unknown")

    def test_tracking_parameter_stripping(self):
        # Real-world URL with trackingId, refId, trk, and utm_*
        dirty_url = (
            "https://www.linkedin.com/jobs/view/4059871234/"
            "?trackingId=AbCdEf12345%3D%3D"
            "&refId=GhIjKl67890"
            "&trk=public_jobs_topcard-title"
            "&utm_source=linkedin_share"
            "&utm_medium=member_desktop"
            "&utm_campaign=job_post"
            "&job_id=4059871234"
            "&source=search_srp"
        )
        cleaned = clean_source_url(dirty_url)

        # Tracking params must be removed
        self.assertNotIn("trackingId", cleaned)
        self.assertNotIn("refId", cleaned)
        self.assertNotIn("trk", cleaned)
        self.assertNotIn("utm_", cleaned)

        # Legitimate parameters must remain
        self.assertIn("job_id=4059871234", cleaned)
        self.assertIn("source=search_srp", cleaned)
        self.assertTrue(cleaned.startswith("https://www.linkedin.com/jobs/view/4059871234"))

    def test_dedup_hash_consistency_with_tracking_params(self):
        title = "Junior Data Analyst"
        company = "Acme Analytics"
        location = "Pune, Maharashtra, India"

        url_with_tracking = "https://example.com/job/100?trackingId=xyz&utm_source=feed"
        url_without_tracking = "https://example.com/job/100"

        hash1 = compute_clean_dedup_hash(title, company, location, url_with_tracking)
        hash2 = compute_clean_dedup_hash(title, company, location, url_without_tracking)

        # Both must produce the exact same deduplication hash
        self.assertEqual(hash1, hash2)

    def test_expiration_and_active_detection(self):
        now_utc = datetime.datetime.now(timezone.utc)

        # Active job (published 5 days ago)
        pub_5d = (now_utc - datetime.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        exp_5d = calculate_expires_at(pub_5d, default_days=30)
        self.assertTrue(is_job_active(pub_5d, exp_5d))

        # Expired job (published 35 days ago)
        pub_35d = (now_utc - datetime.timedelta(days=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        exp_35d = calculate_expires_at(pub_35d, default_days=30)
        self.assertFalse(is_job_active(pub_35d, exp_35d))

    def test_job_model_ingest_auto_cleaning(self):
        raw_url = "https://www.arbeitnow.com/view/data-analyst?trackingId=987&utm_medium=email"
        job = Job(
            id="test_ingest_1",
            title="Junior Data Analyst",
            standard_role="Data Analyst",
            company="Fintech EU",
            location="Berlin, Germany",
            experience_level="Fresher (0 - 1 Year)",
            source_id="stepstone_germany",
            source_name="Arbeitnow",
            source_url=raw_url,
            published_at="1696507200"  # Epoch seconds
        )

        # Must auto-clean at Pydantic ingest
        self.assertEqual(job.published_at, "2023-10-05T12:00:00Z")
        self.assertEqual(job.experience_level, "fresher")
        self.assertNotIn("trackingId", job.source_url)
        self.assertNotIn("utm_", job.source_url)
        self.assertIsNotNone(job.scraped_at)
        self.assertIsNotNone(job.expires_at)
        # Since it's from 2023, it must be expired and inactive
        self.assertFalse(job.is_active)
        self.assertEqual(job.status, "inactive")


class TestStatsAndDatabaseBackfill(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db = Database(db_path=self.temp_db.name)
        self.db.init_db()

    def tearDown(self):
        import gc
        gc.collect()
        try:
            if os.path.exists(self.temp_db.name):
                os.remove(self.temp_db.name)
        except Exception:
            pass

    def test_database_save_and_stats_use_published_at(self):
        now = datetime.datetime.now(timezone.utc)
        today_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        five_days_ago_iso = (now - datetime.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        forty_days_ago_iso = (now - datetime.timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Job 1: Published today (active)
        job1 = Job(
            id="job_today",
            title="Data Analyst Today",
            standard_role="Data Analyst",
            company="Company A",
            location="Pune, India",
            experience_level="0 - 1 Year (Junior)",
            source_id="test",
            source_name="Test",
            source_url="https://example.com/j1",
            published_at=today_iso
        )
        self.db.save_job(job1)

        # Job 2: Published 5 days ago (active)
        job2 = Job(
            id="job_week",
            title="BI Analyst Week",
            standard_role="BI Analyst",
            company="Company B",
            location="Nagpur, India",
            experience_level="Fresher (0 - 1 Year)",
            source_id="test",
            source_name="Test",
            source_url="https://example.com/j2",
            published_at=five_days_ago_iso
        )
        self.db.save_job(job2)

        # Job 3: Published 40 days ago (expired / inactive)
        job3 = Job(
            id="job_old",
            title="Old Analyst",
            standard_role="Data Analyst",
            company="Company C",
            location="Remote",
            experience_level="1 year(s)",
            source_id="test",
            source_name="Test",
            source_url="https://example.com/j3",
            published_at=forty_days_ago_iso
        )
        self.db.save_job(job3)

        stats = self.db.get_statistics()

        # Job 3 is > 30 days old, so active total = 2
        self.assertEqual(stats["total_jobs"], 2)
        # jobs_added_today uses published_at
        self.assertEqual(stats["jobs_added_today"], 1)
        # jobs_added_this_week uses published_at (today + 5 days ago)
        self.assertEqual(stats["jobs_added_this_week"], 2)
        # jobs_older_30d counts jobs older than 30 days based on published_at
        self.assertEqual(stats["jobs_older_30d"], 1)
        # fresher_jobs counts active fresher / 0-1 jobs
        self.assertEqual(stats["fresher_jobs"], 2)

    def test_backfill_script_normalizes_existing_messy_records(self):
        # Manually insert legacy messy records directly with raw sqlite
        with sqlite3.connect(self.temp_db.name) as conn:
            # 1. Job with RFC-2822 date, tracking param in URL, legacy experience
            conn.execute("""
                INSERT INTO jobs (
                    id, dedup_hash, title, standard_role, role_category, company,
                    location, country, work_mode, experience_level, salary,
                    source_id, source_name, source_url, published_at, discovered_at,
                    is_active, status
                ) VALUES (
                    'legacy_1', 'oldhash1', 'Junior Data Analyst', 'Data Analyst', 'Core Analytics', 'Alpha Tech',
                    'Pune, India', 'India', 'On-Site', '0 - 1 Year (Junior / Entry-Level)', '5 LPA',
                    'wwr', 'We Work Remotely', 'https://weworkremotely.com/job/1?trackingId=trk99&utm_source=rss',
                    'Fri, 27 Nov 2026 17:30:00 +0000', '2026-11-27', 1, 'active'
                )
            """)

            # 2. Duplicate of legacy_1 with different tracking parameter
            conn.execute("""
                INSERT INTO jobs (
                    id, dedup_hash, title, standard_role, role_category, company,
                    location, country, work_mode, experience_level, salary,
                    source_id, source_name, source_url, published_at, discovered_at,
                    is_active, status
                ) VALUES (
                    'legacy_1_dup', 'oldhash2', 'Junior Data Analyst', 'Data Analyst', 'Core Analytics', 'Alpha Tech',
                    'Pune, India', 'India', 'On-Site', '0 - 1 Year (Junior / Entry-Level)', '5 LPA',
                    'wwr', 'We Work Remotely', 'https://weworkremotely.com/job/1?refId=feed99&utm_campaign=blast',
                    'Fri, 27 Nov 2026 17:30:00 +0000', '2026-11-27', 1, 'active'
                )
            """)

            # 3. Job with epoch seconds date and 45 days old (should expire)
            old_epoch = int((datetime.datetime.now(timezone.utc) - datetime.timedelta(days=45)).timestamp())
            conn.execute("""
                INSERT INTO jobs (
                    id, dedup_hash, title, standard_role, role_category, company,
                    location, country, work_mode, experience_level, salary,
                    source_id, source_name, source_url, published_at, discovered_at,
                    is_active, status
                ) VALUES (
                    'legacy_2', 'oldhash3', 'Analytics Trainee', 'Data Analyst', 'Core Analytics', 'Beta Corp',
                    'Nagpur, India', 'India', 'On-Site', 'Internship / Trainee (0 Years)', '3 LPA',
                    'arbeitnow', 'Arbeitnow', 'https://arbeitnow.com/job/2',
                    ?, '2026-10-01', 1, 'active'
                )
            """, (str(old_epoch),))

            conn.commit()

        # Run backfill
        run_backfill(db_path=self.temp_db.name, cutoff_days=30, dry_run=False)

        # Verify results in database
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.row_factory = sqlite3.Row

            # Duplicate must have been removed (only 1 row with clean url remains)
            rows = conn.execute("SELECT * FROM jobs ORDER BY id ASC").fetchall()
            self.assertEqual(len(rows), 2)

            job1 = [r for r in rows if r["id"] == "legacy_1"][0]
            self.assertEqual(job1["published_at"], "2026-11-27T17:30:00Z")
            self.assertEqual(job1["experience_level"], "0-1")
            self.assertNotIn("trackingId", job1["source_url"])
            self.assertNotIn("utm_", job1["source_url"])
            self.assertEqual(job1["source_url"], "https://weworkremotely.com/job/1")
            self.assertIsNotNone(job1["scraped_at"])
            self.assertIsNotNone(job1["expires_at"])
            self.assertEqual(job1["is_active"], 1)

            job2 = [r for r in rows if r["id"] == "legacy_2"][0]
            self.assertEqual(job2["experience_level"], "fresher")
            self.assertTrue(job2["published_at"].endswith("Z"))
            # Job 2 is 45 days old -> must be inactive and status 'inactive'
            self.assertEqual(job2["is_active"], 0)
            self.assertEqual(job2["status"], "inactive")

            # Verify all distinct experience levels in the DB are strictly in ALLOWED_EXPERIENCE_LEVELS
            dist_exp = [r[0] for r in conn.execute("SELECT DISTINCT experience_level FROM jobs").fetchall()]
            for exp in dist_exp:
                self.assertIn(exp, ALLOWED_EXPERIENCE_LEVELS)


class TestApiStatsWithLiveApp(unittest.TestCase):

    def setUp(self):
        from app import app
        self.client = TestClient(app)

    def test_api_stats_returns_cleaned_metrics(self):
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("total_jobs", data)
        self.assertIn("jobs_added_today", data)
        self.assertIn("jobs_added_this_week", data)
        self.assertIn("jobs_added_this_month", data)
        self.assertIn("jobs_older_30d", data)
        self.assertIn("fresher_jobs", data)

        # Check types
        self.assertIsInstance(data["jobs_added_today"], int)
        self.assertIsInstance(data["jobs_added_this_week"], int)
        self.assertIsInstance(data["jobs_older_30d"], int)


if __name__ == "__main__":
    unittest.main()
