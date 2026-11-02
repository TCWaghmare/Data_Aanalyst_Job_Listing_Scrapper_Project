"""
SQLite storage engine with multi-role filtering, date recency, deduplication, and indexing.
Optimized for 0-1 year fresher analytics jobs.
"""

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from zoneinfo import ZoneInfo

from scraper.models import Job, Platform, ScrapeRun

def get_default_db_path() -> str:
    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    if is_serverless:
        tmp_dir = "/tmp/data"
        tmp_db = os.path.join(tmp_dir, "jobs.db")
        bundled_db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jobs.db")
        try:
            os.makedirs(tmp_dir, exist_ok=True)
            if not os.path.exists(tmp_db) and os.path.exists(bundled_db):
                import shutil
                shutil.copy2(bundled_db, tmp_db)
        except Exception:
            pass
        return tmp_db
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jobs.db")

DB_PATH = get_default_db_path()

def compute_dedup_hash(title: str, company: str, location: str, source_url: str = "") -> str:
    def clean(s: str) -> str:
        s = (s or "").lower()
        s = re.sub(r"[^\w\s]", "", s)
        return " ".join(s.split())

    clean_t = clean(title)
    clean_c = clean(company)
    clean_l = clean(location)
    clean_u = (source_url or "").split("?")[0].rstrip("/").lower()

    base = f"{clean_t}|{clean_c}|{clean_l}"
    if clean_u:
        base += f"|{clean_u}"

    return hashlib.sha256(base.encode("utf-8")).hexdigest()

class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = get_default_db_path()
        else:
            self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            try:
                os.makedirs(db_dir, exist_ok=True)
            except OSError:
                pass
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except sqlite3.OperationalError:
            pass
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                dedup_hash TEXT UNIQUE,
                title TEXT NOT NULL,
                standard_role TEXT NOT NULL,
                role_category TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                country TEXT NOT NULL,
                work_mode TEXT NOT NULL,
                experience_level TEXT NOT NULL,
                salary TEXT,
                description TEXT,
                skills TEXT,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                published_at TEXT,
                discovered_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                is_applied INTEGER DEFAULT 0,
                applied_at TEXT
            )
            """)

            # Ensure new columns exist
            column_definitions = {
                "is_applied": "INTEGER DEFAULT 0",
                "applied_at": "TEXT",
                "responsibilities": "TEXT",
                "qualifications": "TEXT",
                "requirements": "TEXT",
                "ats_keywords": "TEXT",
                "min_experience": "INTEGER DEFAULT 0",
                "max_experience": "INTEGER DEFAULT 1",
                "application_deadline": "TEXT",
                "openings": "TEXT",
                "company_details": "TEXT",
                "department": "TEXT",
                "employment_type": "TEXT",
                "is_deep_scraped": "INTEGER DEFAULT 0",
                "extraction_status": "TEXT DEFAULT 'complete'",
                "first_scraped_at": "TEXT",
                "last_checked_at": "TEXT",
                "created_at": "TEXT",
                "updated_at": "TEXT",
                "scrape_count": "INTEGER DEFAULT 1",
                "status": "TEXT DEFAULT 'active'",
                "application_status": "TEXT DEFAULT 'new'",
                "is_bookmarked": "INTEGER DEFAULT 0",
                "match_score": "REAL DEFAULT 0.0",
                "recruiter_email": "TEXT",
                "recruiter_name": "TEXT",
                "company_logo": "TEXT",
                "recruiter_designation": "TEXT",
                "linkedin_profile": "TEXT",
                "contact_phone": "TEXT",
                "contact_whatsapp": "TEXT",
                "apply_url": "TEXT",
                "company_website": "TEXT",
                "company_linkedin": "TEXT",
                "role_match_score": "INTEGER",
                "confidence_score": "INTEGER"
            }
            existing_cols = [c[1] for c in conn.execute("PRAGMA table_info(jobs)").fetchall()]
            for col_name, col_type in column_definitions.items():
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")

            # Backfill first_scraped_at & scrape tracking metadata for existing jobs
            conn.execute("""
            UPDATE jobs SET
                first_scraped_at = COALESCE(first_scraped_at, discovered_at, datetime('now')),
                last_checked_at = COALESCE(last_checked_at, discovered_at, datetime('now')),
                created_at = COALESCE(created_at, discovered_at, datetime('now')),
                updated_at = COALESCE(updated_at, discovered_at, datetime('now')),
                scrape_count = COALESCE(scrape_count, 1),
                status = COALESCE(status, CASE WHEN is_active = 1 THEN 'active' ELSE 'inactive' END)
            WHERE first_scraped_at IS NULL OR last_checked_at IS NULL OR scrape_count IS NULL
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_role ON jobs(standard_role)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(role_category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source_name ON jobs(source_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_published ON jobs(published_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_discovered ON jobs(discovered_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_first_scraped ON jobs(first_scraped_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_last_checked ON jobs(last_checked_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_applied ON jobs(is_applied)")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                section TEXT NOT NULL,
                country TEXT NOT NULL,
                website TEXT NOT NULL,
                search_url_template TEXT,
                integration_type TEXT,
                has_adapter INTEGER DEFAULT 0,
                is_enabled INTEGER DEFAULT 1,
                last_scanned_at TEXT,
                last_status TEXT DEFAULT 'pending',
                last_job_count INTEGER DEFAULT 0,
                notes TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                platforms_scanned TEXT,
                jobs_scanned INTEGER DEFAULT 0,
                jobs_added INTEGER DEFAULT 0,
                duplicates_skipped INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                error_messages TEXT
            )
            """)

            # Automated Scheduling, Activity Logs, Audit, and Notification Tables
            conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                schedule_type TEXT DEFAULT 'custom',
                is_enabled INTEGER DEFAULT 1,
                timezone TEXT DEFAULT 'Asia/Kolkata',
                frequency TEXT DEFAULT 'daily',
                run_times TEXT NOT NULL,
                days_of_week TEXT DEFAULT '[]',
                sources TEXT DEFAULT '["all"]',
                job_portals TEXT DEFAULT '["all"]',
                keywords TEXT DEFAULT '[]',
                location_filters TEXT DEFAULT '',
                work_modes TEXT DEFAULT '[]',
                scrape_new_only INTEGER DEFAULT 1,
                rescrape_existing INTEGER DEFAULT 0,
                refresh_expired INTEGER DEFAULT 0,
                update_existing INTEGER DEFAULT 1,
                deduplication INTEGER DEFAULT 1,
                ats_scoring INTEGER DEFAULT 1,
                skill_matching INTEGER DEFAULT 1,
                resume_matching INTEGER DEFAULT 1,
                max_jobs_per_run INTEGER DEFAULT 50,
                portal_priority TEXT DEFAULT '[]',
                retry_count INTEGER DEFAULT 2,
                request_delay REAL DEFAULT 0.5,
                auto_stop_on_error INTEGER DEFAULT 0,
                auto_recovery INTEGER DEFAULT 1,
                next_run_at TEXT,
                last_run_at TEXT,
                last_run_status TEXT DEFAULT 'pending',
                last_success_at TEXT,
                total_runs_count INTEGER DEFAULT 0,
                total_jobs_found INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_activity_logs (
                run_id TEXT PRIMARY KEY,
                schedule_id TEXT,
                schedule_name TEXT NOT NULL,
                trigger_source TEXT NOT NULL,
                triggered_by TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL DEFAULT 0,
                job_sources TEXT,
                jobs_scanned INTEGER DEFAULT 0,
                jobs_added INTEGER DEFAULT 0,
                duplicates_skipped INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                error_messages TEXT,
                high_match_jobs_found INTEGER DEFAULT 0,
                log_details TEXT,
                created_at TEXT NOT NULL
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule_audit_logs (
                id TEXT PRIMARY KEY,
                schedule_id TEXT NOT NULL,
                schedule_name TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'info',
                category TEXT NOT NULL DEFAULT 'general',
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                metadata TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_settings (
                id TEXT PRIMARY KEY DEFAULT 'default',
                in_app_enabled INTEGER DEFAULT 1,
                email_enabled INTEGER DEFAULT 0,
                email_recipient TEXT DEFAULT '',
                smtp_host TEXT DEFAULT 'smtp.gmail.com',
                smtp_port INTEGER DEFAULT 587,
                smtp_user TEXT DEFAULT '',
                smtp_password TEXT DEFAULT '',
                smtp_use_tls INTEGER DEFAULT 1,
                notify_on_complete INTEGER DEFAULT 1,
                notify_on_new_jobs INTEGER DEFAULT 1,
                notify_on_high_match INTEGER DEFAULT 1,
                notify_on_failure INTEGER DEFAULT 1,
                webhook_enabled INTEGER DEFAULT 0,
                webhook_url TEXT DEFAULT ''
            )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON scrape_schedules(is_enabled)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_logs_status ON scrape_activity_logs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON scrape_activity_logs(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(is_read, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_time ON schedule_audit_logs(timestamp DESC)")

            # Initialize Default Notification Settings if not present
            conn.execute("""
            INSERT OR IGNORE INTO notification_settings (id, in_app_enabled, email_enabled, notify_on_complete, notify_on_new_jobs, notify_on_high_match, notify_on_failure)
            VALUES ('default', 1, 0, 1, 1, 1, 1)
            """)

    def reset_for_curated_platforms(self, platforms_data: List[dict]):
        """Align sources strictly with the curated platforms list."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM sources")
            for p in platforms_data:
                conn.execute("""
                INSERT INTO sources (id, name, category, section, country, website, search_url_template, integration_type, has_adapter, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["id"], p["name"], p["category"], p["section"], p["country"],
                    p["website"], p.get("search_url_template", ""), p.get("integration_type", "catalog_link"),
                    1 if p.get("has_adapter") else 0, p.get("notes", "")
                ))

    def insert_or_update_platforms(self, platforms_data: List[dict]):
        with self.get_connection() as conn:
            for p in platforms_data:
                conn.execute("""
                INSERT INTO sources (id, name, category, section, country, website, search_url_template, integration_type, has_adapter, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    category=excluded.category,
                    section=excluded.section,
                    country=excluded.country,
                    website=excluded.website,
                    search_url_template=excluded.search_url_template,
                    integration_type=excluded.integration_type,
                    has_adapter=excluded.has_adapter,
                    notes=excluded.notes
                """, (
                    p["id"], p["name"], p["category"], p["section"], p["country"],
                    p["website"], p.get("search_url_template", ""), p.get("integration_type", "catalog_link"),
                    1 if p.get("has_adapter") else 0, p.get("notes", "")
                ))

    def save_job(self, job: Job, update_existing: bool = True) -> bool:
        dedup_hash = compute_dedup_hash(job.title, job.company, job.location, job.source_url)
        now_iso = datetime.utcnow().isoformat()
        first_scraped = job.first_scraped_at or job.discovered_at or now_iso
        initial_last_checked = job.last_checked_at or now_iso
        initial_created = job.created_at or first_scraped
        initial_updated = job.updated_at or now_iso
        initial_scrape_count = job.scrape_count if job.scrape_count is not None else 1
        initial_status = job.status or "active"

        with self.get_connection() as conn:
            existing = conn.execute(
                "SELECT id, description, salary, is_deep_scraped, first_scraped_at, scrape_count FROM jobs WHERE dedup_hash = ? OR id = ?",
                (dedup_hash, job.id)
            ).fetchone()

            if existing:
                # NON-NEGOTIABLE RULES:
                # 1. Never overwrite or reset first_scraped_at / created_at
                # 2. Update last_checked_at and updated_at on every validation
                # 3. Increment scrape_count
                # 4. Refresh details if changes exist
                cur_count = existing["scrape_count"] if existing["scrape_count"] is not None else 1
                new_scrape_count = cur_count + 1

                if update_existing:
                    skills_json = json.dumps(job.skills, ensure_ascii=False) if job.skills else None
                    conn.execute("""
                    UPDATE jobs SET
                        is_active = 1,
                        status = 'active',
                        last_checked_at = ?,
                        updated_at = ?,
                        scrape_count = ?,
                        salary = CASE WHEN ? != 'Not Disclosed' AND ? != '' THEN ? ELSE salary END,
                        description = CASE WHEN length(?) > length(COALESCE(description, '')) THEN ? ELSE description END,
                        skills = CASE WHEN ? IS NOT NULL AND length(?) > 2 THEN ? ELSE skills END,
                        is_deep_scraped = CASE WHEN ? = 1 THEN 1 ELSE is_deep_scraped END,
                        extraction_status = CASE WHEN ? = 'complete' THEN 'complete' ELSE extraction_status END,
                        recruiter_email = COALESCE(?, recruiter_email),
                        recruiter_name = COALESCE(?, recruiter_name),
                        company_logo = COALESCE(?, company_logo),
                        recruiter_designation = COALESCE(?, recruiter_designation),
                        linkedin_profile = COALESCE(?, linkedin_profile),
                        contact_phone = COALESCE(?, contact_phone),
                        contact_whatsapp = COALESCE(?, contact_whatsapp),
                        apply_url = COALESCE(?, apply_url),
                        company_website = COALESCE(?, company_website),
                        company_linkedin = COALESCE(?, company_linkedin),
                        role_match_score = COALESCE(?, role_match_score),
                        confidence_score = COALESCE(?, confidence_score)
                    WHERE dedup_hash = ?
                    """, (
                        now_iso, now_iso, new_scrape_count,
                        job.salary, job.salary, job.salary,
                        job.description, job.description,
                        skills_json, skills_json, skills_json,
                        1 if job.is_deep_scraped else 0,
                        job.extraction_status,
                        job.recruiter_email,
                        job.recruiter_name,
                        job.company_logo,
                        getattr(job, "recruiter_designation", None),
                        getattr(job, "linkedin_profile", None),
                        getattr(job, "contact_phone", None),
                        getattr(job, "contact_whatsapp", None),
                        getattr(job, "apply_url", None),
                        getattr(job, "company_website", None),
                        getattr(job, "company_linkedin", None),
                        getattr(job, "role_match_score", None),
                        getattr(job, "confidence_score", None),
                        dedup_hash
                    ))
                else:
                    conn.execute("""
                    UPDATE jobs SET
                        is_active = 1,
                        status = 'active',
                        last_checked_at = ?,
                        updated_at = ?,
                        scrape_count = ?
                    WHERE dedup_hash = ?
                    """, (now_iso, now_iso, new_scrape_count, dedup_hash))
                return False

            fuzzy_match = conn.execute(
                "SELECT id, scrape_count FROM jobs WHERE LOWER(title) = LOWER(?) AND LOWER(company) = LOWER(?)",
                (job.title.strip(), job.company.strip())
            ).fetchone()
            if fuzzy_match:
                cur_count = fuzzy_match["scrape_count"] if fuzzy_match["scrape_count"] is not None else 1
                new_scrape_count = cur_count + 1
                if update_existing:
                    conn.execute("""
                    UPDATE jobs SET
                        is_active = 1,
                        status = 'active',
                        last_checked_at = ?,
                        updated_at = ?,
                        scrape_count = ?,
                        source_url = CASE WHEN ? != '' AND ? != 'Post URL Extraction Failed' THEN ? ELSE source_url END,
                        recruiter_email = COALESCE(?, recruiter_email),
                        recruiter_name = CASE WHEN ? != '' AND ? NOT LIKE 'http%' THEN ? ELSE recruiter_name END,
                        recruiter_designation = COALESCE(?, recruiter_designation),
                        linkedin_profile = COALESCE(?, linkedin_profile),
                        contact_phone = COALESCE(?, contact_phone),
                        contact_whatsapp = COALESCE(?, contact_whatsapp),
                        apply_url = COALESCE(?, apply_url),
                        role_match_score = COALESCE(?, role_match_score),
                        confidence_score = COALESCE(?, confidence_score)
                    WHERE id = ?
                    """, (
                        now_iso, now_iso, new_scrape_count,
                        job.source_url, job.source_url, job.source_url,
                        job.recruiter_email,
                        job.recruiter_name, job.recruiter_name, job.recruiter_name,
                        getattr(job, "recruiter_designation", None),
                        getattr(job, "linkedin_profile", None),
                        getattr(job, "contact_phone", None),
                        getattr(job, "contact_whatsapp", None),
                        getattr(job, "apply_url", None),
                        getattr(job, "role_match_score", None),
                        getattr(job, "confidence_score", None),
                        fuzzy_match["id"]
                    ))
                else:
                    conn.execute("""
                    UPDATE jobs SET
                        is_active = 1,
                        status = 'active',
                        last_checked_at = ?,
                        updated_at = ?,
                        scrape_count = ?
                    WHERE id = ?
                    """, (now_iso, now_iso, new_scrape_count, fuzzy_match["id"]))
                return False

            skills_json = json.dumps(job.skills, ensure_ascii=False)
            responsibilities_json = json.dumps(job.responsibilities, ensure_ascii=False)
            qualifications_json = json.dumps(job.qualifications, ensure_ascii=False)
            requirements_json = json.dumps(job.requirements, ensure_ascii=False)
            ats_keywords_json = json.dumps(job.ats_keywords, ensure_ascii=False)

            conn.execute("""
            INSERT INTO jobs (
                id, dedup_hash, title, standard_role, role_category, company,
                location, country, work_mode, experience_level, min_experience, max_experience,
                salary, description, skills, responsibilities, qualifications, requirements, ats_keywords,
                application_deadline, openings, company_details, department, employment_type,
                source_id, source_name, source_url, published_at, discovered_at,
                first_scraped_at, last_checked_at, created_at, updated_at, scrape_count, status,
                is_active, is_applied, applied_at, is_deep_scraped, extraction_status,
                recruiter_email, recruiter_name, company_logo,
                recruiter_designation, linkedin_profile, contact_phone, contact_whatsapp,
                apply_url, company_website, company_linkedin, role_match_score, confidence_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id, dedup_hash, job.title, job.standard_role, job.role_category, job.company,
                job.location, job.country, job.work_mode, job.experience_level, job.min_experience, job.max_experience,
                job.salary, job.description, skills_json, responsibilities_json, qualifications_json, requirements_json, ats_keywords_json,
                job.application_deadline, job.openings, job.company_details, job.department, job.employment_type,
                job.source_id, job.source_name, job.source_url, job.published_at, first_scraped,
                first_scraped, initial_last_checked, initial_created, initial_updated, initial_scrape_count, initial_status,
                1 if job.is_active else 0, 1 if job.is_applied else 0, job.applied_at, 1 if job.is_deep_scraped else 0,
                getattr(job, "extraction_status", "complete"),
                job.recruiter_email, job.recruiter_name, job.company_logo,
                getattr(job, "recruiter_designation", None),
                getattr(job, "linkedin_profile", None),
                getattr(job, "contact_phone", None),
                getattr(job, "contact_whatsapp", None),
                getattr(job, "apply_url", None),
                getattr(job, "company_website", None),
                getattr(job, "company_linkedin", None),
                getattr(job, "role_match_score", None),
                getattr(job, "confidence_score", None)
            ))
            return True

    def get_jobs(self,
                 query: str = "",
                 role: str = "",
                 roles: Optional[List[str]] = None,
                 role_category: str = "",
                 country: str = "",
                 city: str = "",
                 cities: Optional[List[str]] = None,
                 source_id: str = "",
                 platforms: Optional[List[str]] = None,
                 work_mode: str = "",
                 experience_level: str = "",
                 skill: str = "",
                 applied: Optional[str] = "",
                 date_filter: str = "",
                 scrape_freshness: str = "",
                 sort_by: str = "date_desc",
                 limit: int = 50,
                 offset: int = 0) -> Tuple[List[Job], int]:
        """
        Search and filter jobs with multi-role support, multi-city support, multi-platform support, scrape freshness, and configurable sorting.
        """
        conditions = ["is_active = 1"]
        params = []

        if query:
            q_like = f"%{query}%"
            conditions.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR skills LIKE ? OR recruiter_name LIKE ?)")
            params.extend([q_like, q_like, q_like, q_like, q_like])

        # Multi-role filter or single role filter
        selected_roles = []
        if roles:
            selected_roles.extend([r for r in roles if r])
        if role and role not in selected_roles:
            selected_roles.append(role)

        if selected_roles:
            placeholders = ",".join(["?"] * len(selected_roles))
            conditions.append(f"standard_role IN ({placeholders})")
            params.extend(selected_roles)

        if role_category:
            conditions.append("role_category = ?")
            params.append(role_category)

        if country:
            if country == "India":
                conditions.append("(country = 'India' OR location LIKE '%India%')")
            elif country == "Remote":
                conditions.append("(work_mode = 'Remote' OR country LIKE '%Remote%')")
            else:
                conditions.append("country = ?")
                params.append(country)

        # Multi-city or single city filter
        selected_cities = []
        if cities:
            for c in cities:
                if "," in c:
                    selected_cities.extend([x.strip() for x in c.split(",") if x.strip()])
                elif c and c.strip():
                    selected_cities.append(c.strip())
        if city and city not in selected_cities:
            selected_cities.append(city)

        if selected_cities:
            city_conditions = []
            for sc in selected_cities:
                sc_lower = sc.lower()
                if "pune" in sc_lower or "pcmc" in sc_lower or "hinjawadi" in sc_lower:
                    city_conditions.append("(LOWER(location) LIKE '%pune%' OR LOWER(location) LIKE '%pcmc%' OR LOWER(location) LIKE '%pimpri%' OR LOWER(location) LIKE '%hinjawadi%' OR LOWER(location) LIKE '%hinjewadi%' OR LOWER(location) LIKE '%magarpatta%' OR LOWER(location) LIKE '%kharadi%')")
                elif "nagpur" in sc_lower:
                    city_conditions.append("LOWER(location) LIKE '%nagpur%'")
                elif "hyderabad" in sc_lower or "secunderabad" in sc_lower:
                    city_conditions.append("(LOWER(location) LIKE '%hyderabad%' OR LOWER(location) LIKE '%secunderabad%' OR LOWER(location) LIKE '%cyberabad%')")
                elif "aurangabad" in sc_lower or "sambhaji" in sc_lower:
                    city_conditions.append("(LOWER(location) LIKE '%aurangabad%' OR LOWER(location) LIKE '%sambhajinagar%' OR LOWER(location) LIKE '%sambhaji nagar%')")
                elif "bengaluru" in sc_lower or "bangalore" in sc_lower:
                    city_conditions.append("(LOWER(location) LIKE '%bengaluru%' OR LOWER(location) LIKE '%bangalore%')")
                elif "mumbai" in sc_lower or "thane" in sc_lower or "vashi" in sc_lower:
                    city_conditions.append("(LOWER(location) LIKE '%mumbai%' OR LOWER(location) LIKE '%thane%' OR LOWER(location) LIKE '%vashi%')")
                elif "delhi" in sc_lower or "gurgaon" in sc_lower or "gurugram" in sc_lower or "noida" in sc_lower or "ncr" in sc_lower:
                    city_conditions.append("(LOWER(location) LIKE '%delhi%' OR LOWER(location) LIKE '%gurgaon%' OR LOWER(location) LIKE '%gurugram%' OR LOWER(location) LIKE '%noida%' OR LOWER(location) LIKE '%ghaziabad%' OR LOWER(location) LIKE '%faridabad%')")
                elif "chennai" in sc_lower:
                    city_conditions.append("LOWER(location) LIKE '%chennai%'")
                elif "kolkata" in sc_lower:
                    city_conditions.append("LOWER(location) LIKE '%kolkata%'")
                elif "ahmedabad" in sc_lower or "gandhinagar" in sc_lower:
                    city_conditions.append("(LOWER(location) LIKE '%ahmedabad%' OR LOWER(location) LIKE '%gandhinagar%')")
                elif "jaipur" in sc_lower:
                    city_conditions.append("LOWER(location) LIKE '%jaipur%'")
                elif "indore" in sc_lower:
                    city_conditions.append("LOWER(location) LIKE '%indore%'")
                elif "coimbatore" in sc_lower:
                    city_conditions.append("LOWER(location) LIKE '%coimbatore%'")
                elif "chandigarh" in sc_lower:
                    city_conditions.append("LOWER(location) LIKE '%chandigarh%'")
                elif "bhubaneswar" in sc_lower:
                    city_conditions.append("LOWER(location) LIKE '%bhubaneswar%'")
                elif "remote" in sc_lower:
                    city_conditions.append("(work_mode = 'Remote' OR LOWER(location) LIKE '%remote%' OR LOWER(country) LIKE '%remote%' OR LOWER(location) LIKE '%work from home%' OR LOWER(location) LIKE '%worldwide%')")
                elif "pan india" in sc_lower:
                    city_conditions.append("(LOWER(location) LIKE '%pan india%' OR LOWER(location) LIKE '%multiple%' OR (country = 'India' AND LOWER(location) = 'india'))")
                else:
                    city_conditions.append("LOWER(location) LIKE ?")
                    params.append(f"%{sc_lower}%")
            if city_conditions:
                conditions.append(f"({' OR '.join(city_conditions)})")

        # Multi-platform or single platform filter
        selected_platforms = []
        if platforms:
            for p in platforms:
                if "," in p:
                    selected_platforms.extend([x.strip() for x in p.split(",") if x.strip()])
                elif p and p.strip():
                    selected_platforms.append(p.strip())
        if source_id and source_id not in selected_platforms:
            selected_platforms.append(source_id)

        if selected_platforms:
            plat_conditions = []
            for sp in selected_platforms:
                plat_conditions.append("(source_id = ? OR LOWER(source_name) = ? OR LOWER(source_name) LIKE ?)")
                params.extend([sp, sp.lower(), f"%{sp.lower()}%"])
            conditions.append(f"({' OR '.join(plat_conditions)})")

        if work_mode:
            if work_mode in ("onsite_hybrid", "On-Site / Hybrid", "onsite_and_hybrid", "no_remote"):
                conditions.append("work_mode IN ('On-Site', 'Hybrid')")
            elif work_mode == "On-Site":
                conditions.append("work_mode = 'On-Site'")
            elif work_mode == "Hybrid":
                conditions.append("work_mode = 'Hybrid'")
            elif work_mode == "Remote":
                conditions.append("work_mode = 'Remote'")
            else:
                conditions.append("work_mode = ?")
                params.append(work_mode)

        if experience_level:
            conditions.append("experience_level LIKE ?")
            params.append(f"%{experience_level}%")

        if skill:
            conditions.append("skills LIKE ?")
            params.append(f"%{skill}%")

        if applied:
            if applied.lower() in ("true", "1", "applied"):
                conditions.append("is_applied = 1")
            elif applied.lower() in ("false", "0", "not_applied", "unapplied"):
                conditions.append("(is_applied = 0 OR is_applied IS NULL)")

        now = datetime.utcnow()

        # Scrape Freshness Filter (based strictly on first_scraped_at / first discovery date)
        has_freshness_filter = bool(scrape_freshness and scrape_freshness not in ("", "all"))
        if has_freshness_filter:
            if scrape_freshness == "today":
                cutoff = now.strftime("%Y-%m-%d")
                conditions.append("COALESCE(first_scraped_at, discovered_at) >= ?")
                params.append(cutoff)
            elif scrape_freshness == "24h":
                cutoff = (now - timedelta(hours=24)).isoformat()
                conditions.append("COALESCE(first_scraped_at, discovered_at) >= ?")
                params.append(cutoff)
            elif scrape_freshness == "3d":
                cutoff = (now - timedelta(days=3)).isoformat()
                conditions.append("COALESCE(first_scraped_at, discovered_at) >= ?")
                params.append(cutoff)
            elif scrape_freshness == "7d":
                cutoff = (now - timedelta(days=7)).isoformat()
                conditions.append("COALESCE(first_scraped_at, discovered_at) >= ?")
                params.append(cutoff)
            elif scrape_freshness == "30d":
                cutoff = (now - timedelta(days=30)).isoformat()
                conditions.append("COALESCE(first_scraped_at, discovered_at) >= ?")
                params.append(cutoff)
            elif scrape_freshness == "older_30d":
                cutoff = (now - timedelta(days=30)).isoformat()
                conditions.append("(COALESCE(first_scraped_at, discovered_at) < ? OR first_scraped_at IS NULL)")
                params.append(cutoff)

        # Date posted filter on published_at (only when scrape freshness is not actively overriding)
        if not has_freshness_filter and date_filter and date_filter not in ("", "all"):
            if date_filter == "24h":
                cutoff = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                conditions.append("published_at >= ?")
                params.append(cutoff)
            elif date_filter == "3d":
                cutoff = (now - timedelta(days=3)).strftime("%Y-%m-%d")
                conditions.append("published_at >= ?")
                params.append(cutoff)
            elif date_filter == "7d":
                cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%d")
                conditions.append("published_at >= ?")
                params.append(cutoff)
            elif date_filter == "14d":
                cutoff = (now - timedelta(days=14)).strftime("%Y-%m-%d")
                conditions.append("published_at >= ?")
                params.append(cutoff)
            elif date_filter == "30d":
                cutoff = (now - timedelta(days=35)).strftime("%Y-%m-%d")
                conditions.append("(published_at >= ? OR published_at IS NULL)")
                params.append(cutoff)

        where_clause = " WHERE " + " AND ".join(conditions)

        # City & Work Mode Priority Expression:
        # 1. Pune & Nearby (PCMC, Hinjawadi, etc.)
        # 2. Nagpur
        # 3. Hyderabad
        # 4. Aurangabad (Chhatrapati Sambhajinagar)
        # 5. Bengaluru
        # 6. Other / Pan-India
        # Sub-ordered: On-Site (1) -> Hybrid (2) -> Remote (3)
        city_priority_case = """
        CASE 
          WHEN (LOWER(location) LIKE '%pune%' OR LOWER(location) LIKE '%pcmc%' OR LOWER(location) LIKE '%pimpri%' OR LOWER(location) LIKE '%hinjawadi%' OR LOWER(location) LIKE '%hinjewadi%' OR LOWER(location) LIKE '%magarpatta%' OR LOWER(location) LIKE '%kharadi%') THEN 1
          WHEN LOWER(location) LIKE '%nagpur%' THEN 2
          WHEN (LOWER(location) LIKE '%hyderabad%' OR LOWER(location) LIKE '%secunderabad%' OR LOWER(location) LIKE '%cyberabad%') THEN 3
          WHEN (LOWER(location) LIKE '%aurangabad%' OR LOWER(location) LIKE '%sambhajinagar%' OR LOWER(location) LIKE '%sambhaji%') THEN 4
          WHEN (LOWER(location) LIKE '%bengaluru%' OR LOWER(location) LIKE '%bangalore%') THEN 5
          ELSE 6
        END ASC,
        CASE 
          WHEN work_mode = 'On-Site' THEN 1
          WHEN work_mode = 'Hybrid' THEN 2
          ELSE 3
        END ASC
        """

        # Dynamic sorting clause
        if sort_by == "pune_first":
            order_clause = f"ORDER BY {city_priority_case}, published_at DESC NULLS LAST, COALESCE(first_scraped_at, discovered_at) DESC"
        elif sort_by == "date_asc":
            order_clause = "ORDER BY published_at ASC NULLS LAST, discovered_at ASC"
        elif sort_by == "first_scraped_desc":
            order_clause = f"ORDER BY {city_priority_case}, COALESCE(first_scraped_at, discovered_at) DESC NULLS LAST"
        elif sort_by == "first_scraped_asc":
            order_clause = "ORDER BY COALESCE(first_scraped_at, discovered_at) ASC NULLS LAST"
        elif sort_by == "platform_asc":
            order_clause = "ORDER BY source_name COLLATE NOCASE ASC, published_at DESC NULLS LAST"
        elif sort_by == "platform_desc":
            order_clause = "ORDER BY source_name COLLATE NOCASE DESC, published_at DESC NULLS LAST"
        elif sort_by == "company_asc":
            order_clause = "ORDER BY company COLLATE NOCASE ASC, published_at DESC NULLS LAST"
        elif sort_by == "company_desc":
            order_clause = "ORDER BY company COLLATE NOCASE DESC, published_at DESC NULLS LAST"
        elif sort_by == "title_asc":
            order_clause = "ORDER BY title COLLATE NOCASE ASC, published_at DESC NULLS LAST"
        elif sort_by == "title_desc":
            order_clause = "ORDER BY title COLLATE NOCASE DESC, published_at DESC NULLS LAST"
        else: # default: "date_desc" (with Pune & priority city hierarchy + On-Site/Hybrid preference)
            order_clause = f"ORDER BY {city_priority_case}, published_at DESC NULLS LAST, COALESCE(first_scraped_at, discovered_at) DESC"

        with self.get_connection() as conn:
            count_sql = f"SELECT COUNT(*) FROM jobs{where_clause}"
            total = conn.execute(count_sql, params).fetchone()[0]

            fetch_sql = f"""
            SELECT * FROM jobs{where_clause}
            {order_clause}
            LIMIT ? OFFSET ?
            """
            rows = conn.execute(fetch_sql, params + [limit, offset]).fetchall()
            jobs = [self._row_to_job(r) for r in rows]
            return jobs, total

    def _row_to_job(self, row) -> Job:
        col_keys = row.keys()
        def safe_json_list(col_name: str) -> List[str]:
            if col_name in col_keys and row[col_name]:
                try:
                    val = json.loads(row[col_name])
                    return val if isinstance(val, list) else [str(val)]
                except Exception:
                    return [str(row[col_name])]
            return []

        return Job(
            id=row["id"],
            title=row["title"],
            standard_role=row["standard_role"],
            role_category=row["role_category"],
            company=row["company"],
            location=row["location"],
            country=row["country"],
            work_mode=row["work_mode"],
            experience_level=row["experience_level"],
            min_experience=row["min_experience"] if "min_experience" in col_keys and row["min_experience"] is not None else 0,
            max_experience=row["max_experience"] if "max_experience" in col_keys and row["max_experience"] is not None else 1,
            salary=row["salary"] or "Not Disclosed",
            description=row["description"] or "",
            skills=safe_json_list("skills"),
            responsibilities=safe_json_list("responsibilities"),
            qualifications=safe_json_list("qualifications"),
            requirements=safe_json_list("requirements"),
            ats_keywords=safe_json_list("ats_keywords"),
            application_deadline=row["application_deadline"] if "application_deadline" in col_keys else None,
            openings=row["openings"] if "openings" in col_keys else None,
            company_details=row["company_details"] if "company_details" in col_keys else None,
            department=row["department"] if "department" in col_keys else None,
            employment_type=row["employment_type"] if "employment_type" in col_keys else None,
            source_id=row["source_id"],
            source_name=row["source_name"],
            source_url=row["source_url"],
            published_at=row["published_at"],
            discovered_at=row["discovered_at"],
            first_scraped_at=row["first_scraped_at"] if "first_scraped_at" in col_keys and row["first_scraped_at"] else (row["discovered_at"] if "discovered_at" in col_keys else None),
            last_checked_at=row["last_checked_at"] if "last_checked_at" in col_keys and row["last_checked_at"] else (row["discovered_at"] if "discovered_at" in col_keys else None),
            created_at=row["created_at"] if "created_at" in col_keys and row["created_at"] else (row["first_scraped_at"] if "first_scraped_at" in col_keys and row["first_scraped_at"] else (row["discovered_at"] if "discovered_at" in col_keys else None)),
            updated_at=row["updated_at"] if "updated_at" in col_keys and row["updated_at"] else (row["last_checked_at"] if "last_checked_at" in col_keys and row["last_checked_at"] else None),
            scrape_count=row["scrape_count"] if "scrape_count" in col_keys and row["scrape_count"] is not None else 1,
            status=row["status"] if "status" in col_keys and row["status"] else ("active" if row["is_active"] else "inactive"),
            application_status=row["application_status"] if "application_status" in col_keys and row["application_status"] else ("applied" if (bool(row["is_applied"]) if "is_applied" in col_keys else False) else "new"),
            is_bookmarked=bool(row["is_bookmarked"]) if "is_bookmarked" in col_keys and row["is_bookmarked"] else False,
            match_score=float(row["match_score"]) if "match_score" in col_keys and row["match_score"] is not None else 0.0,
            recruiter_email=row["recruiter_email"] if "recruiter_email" in col_keys else None,
            recruiter_name=row["recruiter_name"] if "recruiter_name" in col_keys else None,
            company_logo=row["company_logo"] if "company_logo" in col_keys else None,
            recruiter_designation=row["recruiter_designation"] if "recruiter_designation" in col_keys else None,
            linkedin_profile=row["linkedin_profile"] if "linkedin_profile" in col_keys else None,
            contact_phone=row["contact_phone"] if "contact_phone" in col_keys else None,
            contact_whatsapp=row["contact_whatsapp"] if "contact_whatsapp" in col_keys else None,
            apply_url=row["apply_url"] if "apply_url" in col_keys else None,
            company_website=row["company_website"] if "company_website" in col_keys else None,
            company_linkedin=row["company_linkedin"] if "company_linkedin" in col_keys else None,
            role_match_score=row["role_match_score"] if "role_match_score" in col_keys else None,
            confidence_score=row["confidence_score"] if "confidence_score" in col_keys else None,
            is_active=bool(row["is_active"]),
            is_applied=bool(row["is_applied"]) if "is_applied" in col_keys and row["is_applied"] else False,
            applied_at=row["applied_at"] if "applied_at" in col_keys else None,
            is_deep_scraped=bool(row["is_deep_scraped"]) if "is_deep_scraped" in col_keys and row["is_deep_scraped"] else False,
            extraction_status=row["extraction_status"] if "extraction_status" in col_keys and row["extraction_status"] else "complete"
        )

    def get_job_by_id(self, job_id: str) -> Optional[Job]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            return self._row_to_job(row)

    def update_job_deep_details(self, job_id: str, deep_data: Dict[str, Any]) -> bool:
        """Updates full scraped job description, structured sections, and metadata."""
        with self.get_connection() as conn:
            fields = []
            params = []
            
            allowed = [
                "title", "company", "location", "country", "work_mode", "experience_level",
                "min_experience", "max_experience", "salary", "description",
                "application_deadline", "openings", "company_details", "department",
                "employment_type", "published_at", "is_deep_scraped", "extraction_status"
            ]
            for f in allowed:
                if f in deep_data and deep_data[f] is not None:
                    fields.append(f"{f} = ?")
                    params.append(deep_data[f])

            list_fields = ["skills", "responsibilities", "qualifications", "requirements", "ats_keywords"]
            for lf in list_fields:
                if lf in deep_data and deep_data[lf] is not None:
                    fields.append(f"{lf} = ?")
                    params.append(json.dumps(deep_data[lf], ensure_ascii=False))

            if not fields:
                return False

            sql = f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?"
            params.append(job_id)
            cursor = conn.execute(sql, params)
            return cursor.rowcount > 0

    def update_job_applied(self, job_id: str, is_applied: bool) -> bool:
        applied_at = datetime.utcnow().isoformat() if is_applied else None
        new_status = "applied" if is_applied else "new"
        with self.get_connection() as conn:
            cur = conn.execute(
                "UPDATE jobs SET is_applied = ?, applied_at = ?, application_status = ? WHERE id = ?",
                (1 if is_applied else 0, applied_at, new_status, job_id)
            )
            return cur.rowcount > 0

    def update_job_status(self, job_id: str, status: str) -> bool:
        norm_status = (status or "new").lower().strip()
        is_applied = (1 if norm_status == "applied" else 0)
        applied_at = datetime.utcnow().isoformat() if is_applied else None
        with self.get_connection() as conn:
            cur = conn.execute(
                "UPDATE jobs SET application_status = ?, is_applied = ?, applied_at = COALESCE(applied_at, ?) WHERE id = ?",
                (norm_status, is_applied, applied_at, job_id)
            )
            return cur.rowcount > 0

    def toggle_job_bookmark(self, job_id: str) -> bool:
        with self.get_connection() as conn:
            row = conn.execute("SELECT is_bookmarked, application_status FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return False
            cur_bookmarked = bool(row["is_bookmarked"]) if "is_bookmarked" in row.keys() else False
            new_bookmarked = 0 if cur_bookmarked else 1
            new_status = "saved" if new_bookmarked else "new"
            conn.execute(
                "UPDATE jobs SET is_bookmarked = ?, application_status = CASE WHEN ? = 1 THEN 'saved' ELSE (CASE WHEN application_status = 'saved' THEN 'new' ELSE application_status END) END WHERE id = ?",
                (new_bookmarked, new_bookmarked, job_id)
            )
            return bool(new_bookmarked)

    def get_sources(self) -> List[dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM sources ORDER BY section ASC, name ASC").fetchall()
            return [dict(r) for r in rows]

    def update_source_status(self, source_id: str, status: str, count: int):
        with self.get_connection() as conn:
            conn.execute("""
            UPDATE sources SET
                last_scanned_at = ?,
                last_status = ?,
                last_job_count = ?
            WHERE id = ?
            """, (datetime.utcnow().isoformat(), status, count, source_id))

    def save_scrape_run(self, run: ScrapeRun):
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO scrape_runs (
                run_id, started_at, finished_at, status, platforms_scanned,
                jobs_scanned, jobs_added, duplicates_skipped, errors_count, error_messages
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                finished_at=excluded.finished_at,
                status=excluded.status,
                platforms_scanned=excluded.platforms_scanned,
                jobs_scanned=excluded.jobs_scanned,
                jobs_added=excluded.jobs_added,
                duplicates_skipped=excluded.duplicates_skipped,
                errors_count=excluded.errors_count,
                error_messages=excluded.error_messages
            """, (
                run.run_id, run.started_at, run.finished_at, run.status,
                json.dumps(run.platforms_scanned), run.jobs_scanned,
                run.jobs_added, run.duplicates_skipped, run.errors_count,
                json.dumps(run.error_messages)
            ))

    def get_statistics(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            total_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
            core_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND role_category='Core Analytics'").fetchone()[0]
            related_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND role_category='Related'").fetchone()[0]
            india_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND (country='India' OR location LIKE '%India%')").fetchone()[0]
            remote_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND (work_mode='Remote' OR country LIKE '%Remote%')").fetchone()[0]
            fresher_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND (experience_level LIKE '%Fresher%' OR experience_level LIKE '%0 - 1%' OR experience_level LIKE '%Intern%')").fetchone()[0]
            applied_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND is_applied=1").fetchone()[0]
            total_sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            active_adapters = conn.execute("SELECT COUNT(*) FROM sources WHERE has_adapter=1").fetchone()[0]

            roles_dist = conn.execute("""
            SELECT standard_role, COUNT(*) as cnt
            FROM jobs WHERE is_active=1
            GROUP BY standard_role
            ORDER BY cnt DESC
            LIMIT 15
            """).fetchall()

            platform_dist = conn.execute("""
            SELECT source_name, COUNT(*) as cnt
            FROM jobs WHERE is_active=1
            GROUP BY source_name
            ORDER BY cnt DESC
            LIMIT 10
            """).fetchall()

            latest_run = conn.execute("""
            SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT 1
            """).fetchone()

            # Advanced Scrape Freshness & Job History Intelligence Metrics
            now = datetime.utcnow()
            today_str = now.strftime("%Y-%m-%d")
            week_str = (now - timedelta(days=7)).isoformat()
            month_str = (now - timedelta(days=30)).isoformat()

            jobs_added_today = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE is_active=1 AND COALESCE(first_scraped_at, discovered_at) >= ?",
                (today_str,)
            ).fetchone()[0]

            jobs_added_this_week = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE is_active=1 AND COALESCE(first_scraped_at, discovered_at) >= ?",
                (week_str,)
            ).fetchone()[0]

            jobs_added_this_month = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE is_active=1 AND COALESCE(first_scraped_at, discovered_at) >= ?",
                (month_str,)
            ).fetchone()[0]

            jobs_older_30d = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE is_active=1 AND (COALESCE(first_scraped_at, discovered_at) < ? OR first_scraped_at IS NULL)",
                (month_str,)
            ).fetchone()[0]

            distinct_days = conn.execute(
                "SELECT COUNT(DISTINCT SUBSTR(COALESCE(first_scraped_at, discovered_at), 1, 10)) FROM jobs WHERE is_active=1"
            ).fetchone()[0] or 1
            avg_daily_discovery = round(total_jobs / max(1, distinct_days), 1)

            single_scrape_jobs = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE is_active=1 AND (scrape_count = 1 OR scrape_count IS NULL)"
            ).fetchone()[0]
            revalidated_jobs = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE is_active=1 AND scrape_count > 1"
            ).fetchone()[0]
            new_vs_existing_ratio = f"{round((single_scrape_jobs / max(1, total_jobs)) * 100, 1)}% New"

            growth_rows = conn.execute("""
                SELECT SUBSTR(COALESCE(first_scraped_at, discovered_at), 1, 10) as day, COUNT(*) as cnt
                FROM jobs WHERE is_active=1
                GROUP BY day
                ORDER BY day DESC
                LIMIT 7
            """).fetchall()
            growth_trend = [{"day": r["day"], "count": r["cnt"]} for r in reversed(growth_rows)]

            return {
                "total_jobs": total_jobs,
                "core_jobs": core_jobs,
                "related_jobs": related_jobs,
                "india_jobs": india_jobs,
                "remote_jobs": remote_jobs,
                "fresher_jobs": fresher_jobs,
                "applied_jobs": applied_jobs,
                "total_sources": total_sources,
                "active_adapters": active_adapters,
                "jobs_added_today": jobs_added_today,
                "jobs_added_this_week": jobs_added_this_week,
                "jobs_added_this_month": jobs_added_this_month,
                "jobs_older_30d": jobs_older_30d,
                "avg_daily_discovery": avg_daily_discovery,
                "single_scrape_jobs": single_scrape_jobs,
                "revalidated_jobs": revalidated_jobs,
                "new_vs_existing_ratio": new_vs_existing_ratio,
                "growth_trend": growth_trend,
                "roles_distribution": [dict(r) for r in roles_dist],
                "platform_distribution": [dict(r) for r in platform_dist],
                "latest_run": dict(latest_run) if latest_run else None
            }

    def get_platform_job_counts(self) -> Dict[str, int]:
        """Returns active job counts keyed by source_id and lowercased source_name."""
        counts: Dict[str, int] = {}
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT source_id, source_name, COUNT(*) as cnt
                FROM jobs WHERE is_active = 1
                GROUP BY source_id, source_name
            """).fetchall()
            for r in rows:
                sid = (r["source_id"] or "").strip().lower()
                sname = (r["source_name"] or "").strip().lower()
                cnt = r["cnt"]
                if sid:
                    counts[sid] = counts.get(sid, 0) + cnt
                if sname and sname != sid:
                    counts[sname] = counts.get(sname, 0) + cnt
        return counts

    def get_city_counts(self) -> List[Dict[str, Any]]:
        """Returns list of curated cities and live vacancy counts for active fresher jobs."""
        city_defs = [
            # Priority Locations (User Preferred Sequence: Pune #1, Nagpur, Hyderabad, Aurangabad, Bengaluru)
            {"id": "Pune", "name": "Pune & Nearby (PCMC / Hinjawadi)", "category": "Priority Locations", "patterns": ["%pune%", "%pcmc%", "%pimpri%", "%hinjawadi%", "%hinjewadi%", "%magarpatta%", "%kharadi%"]},
            {"id": "Nagpur", "name": "Nagpur", "category": "Priority Locations", "patterns": ["%nagpur%"]},
            {"id": "Hyderabad", "name": "Hyderabad / Secunderabad", "category": "Priority Locations", "patterns": ["%hyderabad%", "%secunderabad%", "%cyberabad%"]},
            {"id": "Aurangabad", "name": "Aurangabad / Sambhaji Nagar", "category": "Priority Locations", "patterns": ["%aurangabad%", "%sambhajinagar%", "%sambhaji%"]},
            {"id": "Bengaluru", "name": "Bengaluru / Bangalore", "category": "Priority Locations", "patterns": ["%bengaluru%", "%bangalore%"]},

            # Top Tech Hubs
            {"id": "Mumbai", "name": "Mumbai / Navi Mumbai / Thane", "category": "Top Tech Hubs", "patterns": ["%mumbai%", "%thane%", "%vashi%"]},
            {"id": "Delhi NCR", "name": "Delhi NCR (Gurugram / Noida / Delhi)", "category": "Top Tech Hubs", "patterns": ["%delhi%", "%gurgaon%", "%gurugram%", "%noida%", "%ghaziabad%", "%faridabad%"]},
            {"id": "Chennai", "name": "Chennai", "category": "Top Tech Hubs", "patterns": ["%chennai%"]},

            # Emerging Hubs
            {"id": "Kolkata", "name": "Kolkata", "category": "Emerging Hubs", "patterns": ["%kolkata%"]},
            {"id": "Ahmedabad", "name": "Ahmedabad / Gandhinagar", "category": "Emerging Hubs", "patterns": ["%ahmedabad%", "%gandhinagar%"]},
            {"id": "Jaipur", "name": "Jaipur", "category": "Emerging Hubs", "patterns": ["%jaipur%"]},
            {"id": "Indore", "name": "Indore", "category": "Emerging Hubs", "patterns": ["%indore%"]},
            {"id": "Coimbatore", "name": "Coimbatore", "category": "Emerging Hubs", "patterns": ["%coimbatore%"]},
            {"id": "Chandigarh", "name": "Chandigarh", "category": "Emerging Hubs", "patterns": ["%chandigarh%"]},
            {"id": "Bhubaneswar", "name": "Bhubaneswar", "category": "Emerging Hubs", "patterns": ["%bhubaneswar%"]},

            # Flexible / Remote
            {"id": "Pan India", "name": "Pan India / Multiple Locations", "category": "Remote & Flexible", "patterns": ["%pan india%", "%multiple%"]},
            {"id": "Remote", "name": "Remote / Work From Home", "category": "Remote & Flexible", "patterns": ["%remote%", "%work from home%", "%worldwide%"]}
        ]
        with self.get_connection() as conn:
            results = []
            for c in city_defs:
                conds = " OR ".join(["LOWER(location) LIKE ?" for _ in c["patterns"]])
                if c["id"] == "Remote":
                    conds += " OR work_mode = 'Remote' OR LOWER(country) LIKE '%remote%'"
                elif c["id"] == "Pan India":
                    conds += " OR location = 'India' OR (country = 'India' AND location LIKE '%multiple%')"
                count = conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE is_active = 1 AND ({conds})",
                    c["patterns"]
                ).fetchone()[0]
                results.append({
                    "id": c["id"],
                    "name": c["name"],
                    "category": c["category"],
                    "count": count
                })
            return results

    # =========================================================================
    # Automated Schedules, Activity Logs, Notifications & Analytics Engine
    # =========================================================================

    def _row_to_schedule(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for json_field in ["run_times", "days_of_week", "sources", "job_portals", "keywords", "work_modes", "portal_priority"]:
            val = d.get(json_field)
            if isinstance(val, str):
                try:
                    d[json_field] = json.loads(val)
                except Exception:
                    d[json_field] = []
            elif val is None:
                d[json_field] = []
        d["is_enabled"] = bool(d.get("is_enabled", 1))
        d["scrape_new_only"] = bool(d.get("scrape_new_only", 1))
        d["rescrape_existing"] = bool(d.get("rescrape_existing", 0))
        d["refresh_expired"] = bool(d.get("refresh_expired", 0))
        d["update_existing"] = bool(d.get("update_existing", 1))
        d["deduplication"] = bool(d.get("deduplication", 1))
        d["ats_scoring"] = bool(d.get("ats_scoring", 1))
        d["skill_matching"] = bool(d.get("skill_matching", 1))
        d["resume_matching"] = bool(d.get("resume_matching", 1))
        d["auto_stop_on_error"] = bool(d.get("auto_stop_on_error", 0))
        d["auto_recovery"] = bool(d.get("auto_recovery", 1))
        return d

    def get_schedules(self, schedule_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            if schedule_type:
                rows = conn.execute(
                    "SELECT * FROM scrape_schedules WHERE schedule_type = ? ORDER BY created_at ASC",
                    (schedule_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM scrape_schedules ORDER BY CASE WHEN schedule_type='default' THEN 0 ELSE 1 END, created_at ASC"
                ).fetchall()
            return [self._row_to_schedule(r) for r in rows]

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM scrape_schedules WHERE id = ?", (schedule_id,)).fetchone()
            if not row:
                return None
            return self._row_to_schedule(row)

    def save_schedule(self, s: Dict[str, Any]) -> str:
        sched_id = s.get("id") or f"sched_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(2).hex()}"
        now_iso = datetime.utcnow().isoformat()
        created_at = s.get("created_at") or now_iso
        updated_at = now_iso

        def dump_json(val, default="[]"):
            if val is None:
                return default
            if isinstance(val, (list, dict)):
                return json.dumps(val, ensure_ascii=False)
            return str(val)

        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO scrape_schedules (
                id, name, schedule_type, is_enabled, timezone, frequency,
                run_times, days_of_week, sources, job_portals, keywords,
                location_filters, work_modes, scrape_new_only, rescrape_existing,
                refresh_expired, update_existing, deduplication, ats_scoring,
                skill_matching, resume_matching, max_jobs_per_run, portal_priority,
                retry_count, request_delay, auto_stop_on_error, auto_recovery,
                next_run_at, last_run_at, last_run_status, last_success_at,
                total_runs_count, total_jobs_found, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                schedule_type=excluded.schedule_type,
                is_enabled=excluded.is_enabled,
                timezone=excluded.timezone,
                frequency=excluded.frequency,
                run_times=excluded.run_times,
                days_of_week=excluded.days_of_week,
                sources=excluded.sources,
                job_portals=excluded.job_portals,
                keywords=excluded.keywords,
                location_filters=excluded.location_filters,
                work_modes=excluded.work_modes,
                scrape_new_only=excluded.scrape_new_only,
                rescrape_existing=excluded.rescrape_existing,
                refresh_expired=excluded.refresh_expired,
                update_existing=excluded.update_existing,
                deduplication=excluded.deduplication,
                ats_scoring=excluded.ats_scoring,
                skill_matching=excluded.skill_matching,
                resume_matching=excluded.resume_matching,
                max_jobs_per_run=excluded.max_jobs_per_run,
                portal_priority=excluded.portal_priority,
                retry_count=excluded.retry_count,
                request_delay=excluded.request_delay,
                auto_stop_on_error=excluded.auto_stop_on_error,
                auto_recovery=excluded.auto_recovery,
                next_run_at=COALESCE(excluded.next_run_at, scrape_schedules.next_run_at),
                updated_at=excluded.updated_at
            """, (
                sched_id, s.get("name", "Untitled Schedule"), s.get("schedule_type", "custom"),
                1 if s.get("is_enabled", True) else 0, s.get("timezone", "Asia/Kolkata"), s.get("frequency", "daily"),
                dump_json(s.get("run_times", ["11:00"])), dump_json(s.get("days_of_week", [])),
                dump_json(s.get("sources", ["all"])), dump_json(s.get("job_portals", ["all"])),
                dump_json(s.get("keywords", [])), str(s.get("location_filters", "")),
                dump_json(s.get("work_modes", [])), 1 if s.get("scrape_new_only", True) else 0,
                1 if s.get("rescrape_existing", False) else 0, 1 if s.get("refresh_expired", False) else 0,
                1 if s.get("update_existing", True) else 0, 1 if s.get("deduplication", True) else 0,
                1 if s.get("ats_scoring", True) else 0, 1 if s.get("skill_matching", True) else 0,
                1 if s.get("resume_matching", True) else 0, int(s.get("max_jobs_per_run", 50)),
                dump_json(s.get("portal_priority", [])), int(s.get("retry_count", 2)),
                float(s.get("request_delay", 0.5)), 1 if s.get("auto_stop_on_error", False) else 0,
                1 if s.get("auto_recovery", True) else 0, s.get("next_run_at"), s.get("last_run_at"),
                s.get("last_run_status", "pending"), s.get("last_success_at"),
                int(s.get("total_runs_count", 0)), int(s.get("total_jobs_found", 0)),
                created_at, updated_at
            ))
        return sched_id

    def update_schedule_status(self, schedule_id: str, is_enabled: bool) -> bool:
        with self.get_connection() as conn:
            cur = conn.execute(
                "UPDATE scrape_schedules SET is_enabled = ?, updated_at = ? WHERE id = ?",
                (1 if is_enabled else 0, datetime.utcnow().isoformat(), schedule_id)
            )
            return cur.rowcount > 0

    def update_schedule_run_metrics(
        self,
        schedule_id: str,
        last_run_at: str,
        status: str,
        next_run_at: Optional[str] = None,
        jobs_found: int = 0,
        is_success: bool = True
    ):
        with self.get_connection() as conn:
            now_iso = datetime.utcnow().isoformat()
            if is_success:
                conn.execute("""
                UPDATE scrape_schedules SET
                    last_run_at = ?,
                    last_run_status = ?,
                    last_success_at = ?,
                    next_run_at = COALESCE(?, next_run_at),
                    total_runs_count = total_runs_count + 1,
                    total_jobs_found = total_jobs_found + ?,
                    updated_at = ?
                WHERE id = ?
                """, (last_run_at, status, now_iso, next_run_at, jobs_found, now_iso, schedule_id))
            else:
                conn.execute("""
                UPDATE scrape_schedules SET
                    last_run_at = ?,
                    last_run_status = ?,
                    next_run_at = COALESCE(?, next_run_at),
                    total_runs_count = total_runs_count + 1,
                    updated_at = ?
                WHERE id = ?
                """, (last_run_at, status, next_run_at, now_iso, schedule_id))

    def delete_schedule(self, schedule_id: str) -> bool:
        with self.get_connection() as conn:
            cur = conn.execute("DELETE FROM scrape_schedules WHERE id = ?", (schedule_id,))
            return cur.rowcount > 0

    def save_activity_log(self, log: Dict[str, Any]) -> str:
        run_id = log.get("run_id") or str(uuid.uuid4())[:8]
        now_iso = datetime.utcnow().isoformat()

        def dump_json(val, default="[]"):
            if val is None:
                return default
            if isinstance(val, (list, dict)):
                return json.dumps(val, ensure_ascii=False)
            return str(val)

        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO scrape_activity_logs (
                run_id, schedule_id, schedule_name, trigger_source, triggered_by,
                status, started_at, finished_at, duration_seconds, job_sources,
                jobs_scanned, jobs_added, duplicates_skipped, errors_count,
                error_messages, high_match_jobs_found, log_details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                status=excluded.status,
                finished_at=excluded.finished_at,
                duration_seconds=excluded.duration_seconds,
                jobs_scanned=excluded.jobs_scanned,
                jobs_added=excluded.jobs_added,
                duplicates_skipped=excluded.duplicates_skipped,
                errors_count=excluded.errors_count,
                error_messages=excluded.error_messages,
                high_match_jobs_found=excluded.high_match_jobs_found,
                log_details=excluded.log_details
            """, (
                run_id, log.get("schedule_id"), log.get("schedule_name", "Manual Scrape"),
                log.get("trigger_source", "manual"), log.get("triggered_by", "User (Manual)"),
                log.get("status", "running"), log.get("started_at", now_iso), log.get("finished_at"),
                float(log.get("duration_seconds", 0.0)), dump_json(log.get("job_sources", [])),
                int(log.get("jobs_scanned", 0)), int(log.get("jobs_added", 0)),
                int(log.get("duplicates_skipped", 0)), int(log.get("errors_count", 0)),
                dump_json(log.get("error_messages", [])), int(log.get("high_match_jobs_found", 0)),
                dump_json(log.get("log_details", {})), log.get("created_at", now_iso)
            ))
        return run_id

    def get_activity_logs(
        self,
        date_range: Optional[str] = None,
        status: Optional[str] = None,
        job_portal: Optional[str] = None,
        schedule_name: Optional[str] = None,
        trigger_source: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        conditions = ["1=1"]
        params: List[Any] = []

        if status and status.lower() != "all":
            conditions.append("LOWER(status) = LOWER(?)")
            params.append(status)

        if trigger_source and trigger_source.lower() != "all":
            conditions.append("LOWER(trigger_source) = LOWER(?)")
            params.append(trigger_source)

        if schedule_name and schedule_name.lower() != "all":
            conditions.append("schedule_name LIKE ?")
            params.append(f"%{schedule_name}%")

        if job_portal and job_portal.lower() != "all":
            conditions.append("job_sources LIKE ?")
            params.append(f"%{job_portal}%")

        if query:
            q_like = f"%{query}%"
            conditions.append("(run_id LIKE ? OR schedule_name LIKE ? OR triggered_by LIKE ? OR error_messages LIKE ?)")
            params.extend([q_like, q_like, q_like, q_like])

        if date_range:
            now = datetime.utcnow()
            if date_range == "today":
                cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                conditions.append("started_at >= ?")
                params.append(cutoff)
            elif date_range == "7d":
                cutoff = (now - timedelta(days=7)).isoformat()
                conditions.append("started_at >= ?")
                params.append(cutoff)
            elif date_range == "30d":
                cutoff = (now - timedelta(days=30)).isoformat()
                conditions.append("started_at >= ?")
                params.append(cutoff)

        where_clause = " AND ".join(conditions)

        with self.get_connection() as conn:
            count_sql = f"SELECT COUNT(*) FROM scrape_activity_logs WHERE {where_clause}"
            total = conn.execute(count_sql, params).fetchone()[0]

            data_sql = f"""
            SELECT * FROM scrape_activity_logs
            WHERE {where_clause}
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
            """
            rows = conn.execute(data_sql, params + [limit, offset]).fetchall()

            results = []
            for r in rows:
                item = dict(r)
                for j_field in ["job_sources", "error_messages", "log_details"]:
                    val = item.get(j_field)
                    if isinstance(val, str):
                        try:
                            item[j_field] = json.loads(val)
                        except Exception:
                            item[j_field] = [] if j_field != "log_details" else {}
                results.append(item)
            return results, total

    def get_activity_log(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM scrape_activity_logs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            for j_field in ["job_sources", "error_messages", "log_details"]:
                val = item.get(j_field)
                if isinstance(val, str):
                    try:
                        item[j_field] = json.loads(val)
                    except Exception:
                        item[j_field] = [] if j_field != "log_details" else {}
            return item

    def add_audit_log(self, schedule_id: str, schedule_name: str, action: str, details: str = ""):
        with self.get_connection() as conn:
            audit_id = f"aud_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(2).hex()}"
            conn.execute("""
            INSERT INTO schedule_audit_logs (id, schedule_id, schedule_name, action, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (audit_id, schedule_id, schedule_name, action, details, datetime.utcnow().isoformat()))

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM schedule_audit_logs ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def add_notification(
        self,
        title: str,
        message: str,
        type: str = "info",
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        notif_id = f"notif_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(2).hex()}"
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        now_utc = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO notifications (id, title, message, type, category, is_read, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """, (notif_id, title, message, type, category, now_utc, meta_json))
        return notif_id

    def get_notifications(self, limit: int = 50, unread_only: bool = False) -> Dict[str, Any]:
        with self.get_connection() as conn:
            unread_count = conn.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0").fetchone()[0]
            if unread_only:
                rows = conn.execute(
                    "SELECT * FROM notifications WHERE is_read = 0 ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()

            items = []
            ist_tz = ZoneInfo("Asia/Kolkata")
            for r in rows:
                d = dict(r)
                if isinstance(d.get("metadata"), str):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except Exception:
                        d["metadata"] = {}
                d["is_read"] = bool(d.get("is_read", 0))

                # Human-readable date and time formatted in Indian Time Zone (IST)
                raw_created = d.get("created_at") or ""
                if raw_created:
                    try:
                        clean_iso = raw_created.strip()
                        if not clean_iso.endswith("Z") and not re.search(r"[-+]\d{2}(:\d{2})?$", clean_iso):
                            clean_iso += "Z"
                        dt = datetime.fromisoformat(clean_iso.replace("Z", "+00:00"))
                        dt_ist = dt.astimezone(ist_tz)
                        d["created_at_ist"] = dt_ist.strftime("%d %b %Y, %I:%M %p IST")
                    except Exception:
                        d["created_at_ist"] = raw_created
                else:
                    d["created_at_ist"] = ""

                items.append(d)
            return {"items": items, "unread_count": unread_count}

    def mark_notification_read(self, notification_id: str) -> bool:
        with self.get_connection() as conn:
            cur = conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            return cur.rowcount > 0

    def mark_all_notifications_read(self) -> int:
        with self.get_connection() as conn:
            cur = conn.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
            return cur.rowcount

    def get_notification_settings(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM notification_settings WHERE id = 'default'").fetchone()
            if not row:
                return {
                    "id": "default",
                    "in_app_enabled": True,
                    "email_enabled": False,
                    "email_recipient": "",
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587,
                    "smtp_user": "",
                    "smtp_password": "",
                    "smtp_use_tls": True,
                    "notify_on_complete": True,
                    "notify_on_new_jobs": True,
                    "notify_on_high_match": True,
                    "notify_on_failure": True,
                    "webhook_enabled": False,
                    "webhook_url": ""
                }
            d = dict(row)
            d["in_app_enabled"] = bool(d.get("in_app_enabled", 1))
            d["email_enabled"] = bool(d.get("email_enabled", 0))
            d["smtp_use_tls"] = bool(d.get("smtp_use_tls", 1))
            d["notify_on_complete"] = bool(d.get("notify_on_complete", 1))
            d["notify_on_new_jobs"] = bool(d.get("notify_on_new_jobs", 1))
            d["notify_on_high_match"] = bool(d.get("notify_on_high_match", 1))
            d["notify_on_failure"] = bool(d.get("notify_on_failure", 1))
            d["webhook_enabled"] = bool(d.get("webhook_enabled", 0))
            return d

    def save_notification_settings(self, s: Dict[str, Any]):
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO notification_settings (
                id, in_app_enabled, email_enabled, email_recipient, smtp_host,
                smtp_port, smtp_user, smtp_password, smtp_use_tls,
                notify_on_complete, notify_on_new_jobs, notify_on_high_match,
                notify_on_failure, webhook_enabled, webhook_url
            ) VALUES ('default', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                in_app_enabled=excluded.in_app_enabled,
                email_enabled=excluded.email_enabled,
                email_recipient=excluded.email_recipient,
                smtp_host=excluded.smtp_host,
                smtp_port=excluded.smtp_port,
                smtp_user=excluded.smtp_user,
                smtp_password=excluded.smtp_password,
                smtp_use_tls=excluded.smtp_use_tls,
                notify_on_complete=excluded.notify_on_complete,
                notify_on_new_jobs=excluded.notify_on_new_jobs,
                notify_on_high_match=excluded.notify_on_high_match,
                notify_on_failure=excluded.notify_on_failure,
                webhook_enabled=excluded.webhook_enabled,
                webhook_url=excluded.webhook_url
            """, (
                1 if s.get("in_app_enabled", True) else 0,
                1 if s.get("email_enabled", False) else 0,
                s.get("email_recipient", ""),
                s.get("smtp_host", "smtp.gmail.com"),
                int(s.get("smtp_port", 587)),
                s.get("smtp_user", ""),
                s.get("smtp_password", ""),
                1 if s.get("smtp_use_tls", True) else 0,
                1 if s.get("notify_on_complete", True) else 0,
                1 if s.get("notify_on_new_jobs", True) else 0,
                1 if s.get("notify_on_high_match", True) else 0,
                1 if s.get("notify_on_failure", True) else 0,
                1 if s.get("webhook_enabled", False) else 0,
                s.get("webhook_url", "")
            ))

    def get_scraping_analytics(self) -> Dict[str, Any]:
        """Calculates comprehensive historical scraping metrics, trends, and productivity."""
        with self.get_connection() as conn:
            # Basic run counts
            total_runs = conn.execute("SELECT COUNT(*) FROM scrape_activity_logs").fetchone()[0]
            if total_runs == 0:
                # Fallback to scrape_runs if activity logs is fresh
                total_runs = conn.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0]
                total_scanned = conn.execute("SELECT COALESCE(SUM(jobs_scanned), 0) FROM scrape_runs").fetchone()[0]
                total_added = conn.execute("SELECT COALESCE(SUM(jobs_added), 0) FROM scrape_runs").fetchone()[0]
                successful_runs = conn.execute("SELECT COUNT(*) FROM scrape_runs WHERE status LIKE '%complete%'").fetchone()[0]
                failed_runs = conn.execute("SELECT COUNT(*) FROM scrape_runs WHERE status = 'failed'").fetchone()[0]
                avg_duration = 24.5
            else:
                total_scanned = conn.execute("SELECT COALESCE(SUM(jobs_scanned), 0) FROM scrape_activity_logs").fetchone()[0]
                total_added = conn.execute("SELECT COALESCE(SUM(jobs_added), 0) FROM scrape_activity_logs").fetchone()[0]
                successful_runs = conn.execute("SELECT COUNT(*) FROM scrape_activity_logs WHERE status = 'completed'").fetchone()[0]
                failed_runs = conn.execute("SELECT COUNT(*) FROM scrape_activity_logs WHERE status = 'failed'").fetchone()[0]
                avg_duration_row = conn.execute("SELECT AVG(duration_seconds) FROM scrape_activity_logs WHERE duration_seconds > 0").fetchone()
                avg_duration = round(avg_duration_row[0] or 0.0, 1) if avg_duration_row else 0.0

            # Total unique active jobs in db
            total_unique_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active = 1").fetchone()[0]

            # Most productive job portal
            top_portal_row = conn.execute("""
                SELECT source_name, COUNT(*) as cnt
                FROM jobs WHERE is_active = 1
                GROUP BY source_name
                ORDER BY cnt DESC LIMIT 1
            """).fetchone()
            top_portal = top_portal_row["source_name"] if top_portal_row else "Internshala"

            # Best performing schedule
            best_schedule_row = conn.execute("""
                SELECT schedule_name, SUM(jobs_added) as total_added
                FROM scrape_activity_logs
                WHERE schedule_name IS NOT NULL AND schedule_name != ''
                GROUP BY schedule_name
                ORDER BY total_added DESC LIMIT 1
            """).fetchone()
            best_schedule = best_schedule_row["schedule_name"] if best_schedule_row else "🌅 Morning Job Scraping"

            # Jobs found per day (past 14 days)
            daily_rows = conn.execute("""
                SELECT substr(discovered_at, 1, 10) as day, COUNT(*) as cnt
                FROM jobs
                WHERE discovered_at IS NOT NULL
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
            """).fetchall()
            jobs_per_day = [{"date": r["day"], "count": r["cnt"]} for r in reversed(daily_rows)]

            # Jobs found per week (past 8 weeks)
            weekly_rows = conn.execute("""
                SELECT strftime('%Y-W%W', discovered_at) as week, COUNT(*) as cnt
                FROM jobs
                WHERE discovered_at IS NOT NULL
                GROUP BY week
                ORDER BY week DESC
                LIMIT 8
            """).fetchall()
            jobs_per_week = [{"week": r["week"], "count": r["cnt"]} for r in reversed(weekly_rows)]

            # Jobs found per month (past 6 months)
            monthly_rows = conn.execute("""
                SELECT substr(discovered_at, 1, 7) as month, COUNT(*) as cnt
                FROM jobs
                WHERE discovered_at IS NOT NULL
                GROUP BY month
                ORDER BY month DESC
                LIMIT 6
            """).fetchall()
            jobs_per_month = [{"month": r["month"], "count": r["cnt"]} for r in reversed(monthly_rows)]

            # Portal breakdown (top 8 portals)
            portal_breakdown = conn.execute("""
                SELECT source_name, COUNT(*) as cnt
                FROM jobs WHERE is_active = 1
                GROUP BY source_name
                ORDER BY cnt DESC
                LIMIT 8
            """).fetchall()

            return {
                "total_runs": total_runs,
                "total_scraped": total_scanned,
                "total_unique_jobs": total_unique_jobs,
                "total_added": total_added,
                "successful_runs": successful_runs,
                "failed_runs": failed_runs,
                "success_rate": round((successful_runs / total_runs * 100), 1) if total_runs > 0 else 100.0,
                "avg_processing_time_sec": avg_duration,
                "most_productive_portal": top_portal,
                "best_performing_schedule": best_schedule,
                "jobs_per_day": jobs_per_day,
                "jobs_per_week": jobs_per_week,
                "jobs_per_month": jobs_per_month,
                "portal_breakdown": [{"portal": r["source_name"], "count": r["cnt"]} for r in portal_breakdown]
            }
