"""
Comprehensive tests for persistent storage layer:
1. SQLite storage tests (tables, jobs, schedules, logs, notifications, settings, KB metadata, binary files).
2. SQL translation dialect tests (SQLite -> PostgreSQL syntax, placeholders, collations, row wrappers).
3. Live PostgreSQL tests (executed whenever TEST_DATABASE_URL is set in environment).
4. Migration script tests.
"""

import json
import os
import re
import tempfile
import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from scraper.database import (
    Database,
    DictAndIndexRow,
    translate_sql_to_postgres,
    get_default_db_path,
)
from scraper.models import Job
from app import app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


class TestSqlToPostgresDialectTranslation:
    """Tests that SQLite queries are correctly translated to PostgreSQL dialect."""

    def test_placeholder_conversion(self):
        sql = "SELECT * FROM jobs WHERE standard_role = ? AND country = ? AND min_experience <= ?"
        translated = translate_sql_to_postgres(sql)
        assert translated == "SELECT * FROM jobs WHERE standard_role = %s AND country = %s AND min_experience <= %s"

    def test_placeholder_preserves_literals_with_question_marks(self):
        sql = "SELECT * FROM jobs WHERE source_url = 'https://example.com/job?id=123' AND standard_role = ?"
        translated = translate_sql_to_postgres(sql)
        assert "https://example.com/job?id=123" in translated
        assert translated.endswith("standard_role = %s")

    def test_collate_nocase_translation(self):
        sql = "ORDER BY company COLLATE NOCASE ASC, title COLLATE NOCASE DESC"
        translated = translate_sql_to_postgres(sql)
        assert "LOWER(company) ASC" in translated
        assert "LOWER(title) DESC" in translated
        assert "COLLATE NOCASE" not in translated

    def test_insert_or_ignore_translation(self):
        sql = "INSERT OR IGNORE INTO notification_settings (id, in_app_enabled) VALUES ('default', 1)"
        translated = translate_sql_to_postgres(sql)
        assert "INSERT INTO notification_settings" in translated
        assert "ON CONFLICT DO NOTHING" in translated

    def test_datetime_now_translation(self):
        sql = "UPDATE jobs SET first_scraped_at = datetime('now') WHERE first_scraped_at IS NULL"
        translated = translate_sql_to_postgres(sql)
        assert "NOW()::text" in translated
        assert "datetime('now')" not in translated

    def test_strftime_translation(self):
        sql = "SELECT strftime('%Y-W%W', discovered_at) as week, COUNT(*) as cnt FROM jobs"
        translated = translate_sql_to_postgres(sql)
        assert "to_char(discovered_at::timestamp, 'YYYY-\"W\"IW')" in translated
        assert "strftime" not in translated

    def test_blob_to_bytea_in_create_table(self):
        sql = "CREATE TABLE IF NOT EXISTS stored_files (id TEXT PRIMARY KEY, file_data BLOB NOT NULL)"
        translated = translate_sql_to_postgres(sql)
        assert "file_data BYTEA NOT NULL" in translated

    def test_dict_and_index_row_wrapper(self):
        mapping = {"id": "job_1", "title": "Data Analyst", "salary": "₹8 LPA"}
        tuple_vals = ("job_1", "Data Analyst", "₹8 LPA")
        row = DictAndIndexRow(mapping, tuple_vals)

        # Access by column name
        assert row["id"] == "job_1"
        assert row["title"] == "Data Analyst"
        assert row.get("salary") == "₹8 LPA"
        assert row.get("missing", "default") == "default"

        # Access by index
        assert row[0] == "job_1"
        assert row[1] == "Data Analyst"
        assert row[2] == "₹8 LPA"

        # Dictionary conversions and keys
        assert dict(row) == mapping
        assert "title" in row.keys()


class TestSqliteStorageLayer:
    """Verifies SQLite backend covers all tables, jobs, settings, KB metadata, and binary file storage."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        db_file = str(tmp_path / "test_jobs.db")
        self.db = Database(db_path=db_file)
        self.db_file = db_file
        yield
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except OSError:
                pass

    def test_all_twelve_tables_initialized(self):
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [r["name"] for r in rows]

        expected_tables = [
            "jobs",
            "sources",
            "scrape_runs",
            "scrape_schedules",
            "scrape_activity_logs",
            "schedule_audit_logs",
            "notifications",
            "notification_settings",
            "linkedin_feed_settings",
            "knowledge_base_documents",
            "knowledge_base_profile",
            "stored_files",
        ]
        for t in expected_tables:
            assert t in table_names, f"Table '{t}' must exist in initialized database."

    def test_job_save_deduplication_and_filtering(self):
        test_job = Job(
            id="job_storage_test_1",
            title="Junior Data Analyst",
            standard_role="Data Analyst",
            role_category="Core Analytics",
            company="Acme Corp",
            location="Pune, Maharashtra",
            country="India",
            work_mode="On-Site",
            experience_level="0-1 years",
            salary="₹7,00,000",
            description="Fresher data analyst role involving SQL and Python.",
            skills=["SQL", "Python", "Tableau"],
            source_id="linkedin_feed",
            source_name="LinkedIn Posts",
            source_url="https://www.linkedin.com/feed/update/urn:li:activity:9999999/",
            published_at="2026-10-30",
            discovered_at="2026-10-30T10:00:00",
        )

        is_new = self.db.save_job(test_job)
        assert is_new is True, "First save of new job should return True."

        # Fetch job
        fetched = self.db.get_job_by_id("job_storage_test_1")
        assert fetched is not None
        assert fetched.title == "Junior Data Analyst"
        assert fetched.company == "Acme Corp"
        assert fetched.standard_role == "Data Analyst"
        assert "SQL" in fetched.skills

        # Re-save same job (deduplication check)
        is_new_again = self.db.save_job(test_job, update_existing=True)
        assert is_new_again is False, "Re-saving existing job must be detected as duplicate."

        # Toggle bookmark & application status
        assert self.db.toggle_job_bookmark("job_storage_test_1") is True
        assert self.db.update_job_applied("job_storage_test_1", True) is True

        updated_job = self.db.get_job_by_id("job_storage_test_1")
        assert updated_job.is_bookmarked == 1
        assert updated_job.is_applied == 1

    def test_scrape_schedules_and_activity_logs(self):
        schedule = {
            "name": "Evening Pune Scrape",
            "frequency": "daily",
            "run_times": ["18:00"],
            "location_filters": "Pune",
            "keywords": ["analyst"],
        }
        sched_id = self.db.save_schedule(schedule)
        assert sched_id is not None

        loaded_sched = self.db.get_schedule(sched_id)
        assert loaded_sched is not None
        assert loaded_sched["name"] == "Evening Pune Scrape"

        # Log activity
        log = {
            "schedule_id": sched_id,
            "schedule_name": "Evening Pune Scrape",
            "trigger_source": "manual",
            "triggered_by": "user",
            "status": "completed",
            "jobs_scanned": 25,
            "jobs_added": 5,
        }
        run_id = self.db.save_activity_log(log)
        assert run_id is not None

        loaded_log = self.db.get_activity_log(run_id)
        assert loaded_log is not None
        assert loaded_log["jobs_added"] == 5

    def test_notifications_and_notification_settings(self):
        self.db.add_notification(
            title="5 Fresh Jobs in Pune",
            message="New analytics roles matching your criteria were scraped.",
            type="success",
            category="scrape"
        )
        notifs = self.db.get_notifications(limit=10)
        assert len(notifs["items"]) >= 1
        assert notifs["items"][0]["title"] == "5 Fresh Jobs in Pune"

        settings = self.db.get_notification_settings()
        assert "in_app_enabled" in settings
        assert settings["in_app_enabled"] == 1

        self.db.save_notification_settings({"in_app_enabled": 1, "email_enabled": 0, "email_recipient": "user@test.com"})
        updated_settings = self.db.get_notification_settings()
        assert updated_settings["email_recipient"] == "user@test.com"

    def test_linkedin_feed_settings_persistence(self):
        settings = {
            "sync_enabled": True,
            "last_synced_at": "2026-10-30T15:00:00",
            "keywords": "fresher data analyst pune",
            "li_at": "SECRET_COOKIE_VALUE"  # Should NOT be stored in DB
        }
        saved = self.db.save_linkedin_feed_settings(settings)
        assert saved is True

        loaded = self.db.get_linkedin_feed_settings()
        assert loaded["sync_enabled"] is True
        assert loaded["keywords"] == "fresher data analyst pune"
        assert "li_at" not in loaded, "Session cookie must never be stored in persistent database settings."

    def test_knowledge_base_documents_and_profile_persistence(self):
        doc = {
            "id": "doc_test_123",
            "filename": "Tejas_Resume.pdf",
            "display_name": "Master Analytics Resume",
            "category": "resume",
            "file_type": "PDF",
            "file_size": 10240,
            "file_size_formatted": "10.0 KB",
            "status": "Ready for AI Usage",
            "extracted_data": {"technical_tools": ["SQL", "Python", "Power BI"], "education": []}
        }
        saved = self.db.save_kb_document(doc)
        assert saved is True

        docs = self.db.get_kb_documents()
        assert len(docs) == 1
        assert docs[0]["id"] == "doc_test_123"
        assert docs[0]["extracted_data"]["technical_tools"] == ["SQL", "Python", "Power BI"]

        # Unified Profile
        profile = {
            "name": "Tejas Waghmare",
            "role": "Data Analyst",
            "technical_skills": ["SQL", "Python", "Tableau", "Excel"],
            "experiences": []
        }
        self.db.save_kb_profile(profile)
        loaded_prof = self.db.get_kb_profile()
        assert loaded_prof["name"] == "Tejas Waghmare"
        assert "SQL" in loaded_prof["technical_skills"]

        # Delete KB doc
        self.db.delete_kb_document("doc_test_123")
        assert len(self.db.get_kb_documents()) == 0

    def test_binary_file_storage(self):
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Test Tailored Resume) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        file_id = "tailored_sample_job_1.pdf"

        # 1. Save binary file
        saved = self.db.save_file(
            file_id=file_id,
            filename=file_id,
            content=pdf_bytes,
            content_type="application/pdf",
            file_type="pdf"
        )
        assert saved is True
        assert self.db.file_exists(file_id) is True

        # 2. Retrieve binary file
        retrieved = self.db.get_file(file_id)
        assert retrieved is not None
        assert retrieved["id"] == file_id
        assert retrieved["filename"] == file_id
        assert retrieved["content_type"] == "application/pdf"
        assert retrieved["file_size"] == len(pdf_bytes)
        assert retrieved["file_data"] == pdf_bytes

        # 3. Retrieve by filename
        by_name = self.db.get_file_by_filename(file_id)
        assert by_name is not None
        assert by_name["file_data"] == pdf_bytes

        # 4. List files
        file_list = self.db.list_files(file_type="pdf")
        assert any(f["id"] == file_id for f in file_list)

        # 5. Delete file
        self.db.delete_file(file_id)
        assert self.db.file_exists(file_id) is False
        assert self.db.get_file(file_id) is None


class TestPersistentFileEndpoints:
    """Verifies that download and preview endpoints retrieve binary files directly from persistent database."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from scraper.database import Database
        self.db = Database()
        self.client = TestClient(app)
        self.headers = {"X-API-Key": os.getenv("API_KEY", "default-dev-key")}

    def test_tailored_pdf_download_from_database(self):
        clean_id = "test_db_job_download"
        pdf_filename = f"tailored_{clean_id}.pdf"
        pdf_content = b"%PDF-1.4\n%Persistent DB Resume Test Bytes\n%%EOF"

        # Save directly in database
        self.db.save_file(
            file_id=pdf_filename,
            filename=pdf_filename,
            content=pdf_content,
            content_type="application/pdf",
            file_type="pdf"
        )

        response = self.client.get(f"/api/resume/download/pdf/{clean_id}", headers=self.headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content == pdf_content

        # Clean up
        self.db.delete_file(pdf_filename)

    def test_tailored_docx_download_from_database(self):
        clean_id = "test_db_docx_download"
        docx_filename = f"tailored_{clean_id}.docx"
        docx_content = b"PK\x03\x04MockDocxBinaryData"

        self.db.save_file(
            file_id=docx_filename,
            filename=docx_filename,
            content=docx_content,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_type="docx"
        )

        response = self.client.get(f"/api/resume/download/docx/{clean_id}", headers=self.headers)
        assert response.status_code == 200
        assert "wordprocessingml.document" in response.headers["content-type"]
        assert response.content == docx_content

        self.db.delete_file(docx_filename)

    def test_cover_letter_download_from_database(self):
        clean_id = "test_db_cl_download"
        cl_filename = f"cover_letter_{clean_id}.pdf"
        cl_content = b"%PDF-1.4\n%Persistent Cover Letter Bytes\n%%EOF"

        self.db.save_file(
            file_id=cl_filename,
            filename=cl_filename,
            content=cl_content,
            content_type="application/pdf",
            file_type="pdf"
        )

        response = self.client.get(f"/api/cover-letter/download/pdf/{clean_id}", headers=self.headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == cl_content

        self.db.delete_file(cl_filename)

    def test_migration_content_type_detection(self):
        from scripts.migrate_sqlite_to_postgres import detect_content_type
        assert detect_content_type("resume.pdf") == "application/pdf"
        assert "openxmlformats" in detect_content_type("resume.docx")
        assert "text/plain" in detect_content_type("notes.txt")
        assert detect_content_type("logo.png") == "image/png"


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not configured; skipping live PostgreSQL integration tests")
class TestLivePostgresStorage:
    """Live PostgreSQL tests running against TEST_DATABASE_URL when provided."""

    @pytest.fixture(autouse=True)
    def setup_pg(self):
        self.pg_db = Database(database_url=TEST_DATABASE_URL)

    def test_live_postgres_tables_and_file_storage(self):
        # 1. Check all tables initialized
        stats = self.pg_db.get_statistics()
        assert "total_jobs" in stats

        # 2. Binary BYTEA storage in Postgres
        test_file_id = f"test_pg_file_{uuid.uuid4().hex[:6]}.pdf"
        test_bytes = b"%PDF-1.4\n%Live Postgres BYTEA storage test\n%%EOF"

        saved = self.pg_db.save_file(
            file_id=test_file_id,
            filename=test_file_id,
            content=test_bytes,
            content_type="application/pdf",
            file_type="pdf"
        )
        assert saved is True
        assert self.pg_db.file_exists(test_file_id) is True

        retrieved = self.pg_db.get_file(test_file_id)
        assert retrieved is not None
        assert retrieved["file_data"] == test_bytes

        # Clean up
        self.pg_db.delete_file(test_file_id)
        assert self.pg_db.file_exists(test_file_id) is False
