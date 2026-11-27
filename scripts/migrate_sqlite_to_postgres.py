#!/usr/bin/env python3
"""
Idempotent SQLite to PostgreSQL Data & File Migration Script.
Copies all tables, settings, knowledge-base documents, unified profile,
and binary files from local SQLite/disk storage to PostgreSQL.

Safe to run multiple times: uses ON CONFLICT DO UPDATE / DO NOTHING.
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
from typing import Dict, List, Any, Optional

# Ensure project root is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scraper.database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MigrateSqliteToPostgres")


def detect_content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext == "pdf":
        return "application/pdf"
    elif ext == "docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext in ["txt", "md", "csv", "json"]:
        return "text/plain; charset=utf-8"
    elif ext == "html":
        return "text/html; charset=utf-8"
    elif ext == "tex":
        return "text/plain; charset=utf-8"
    elif ext in ["png", "jpg", "jpeg", "webp"]:
        return f"image/{ext if ext != 'jpg' else 'jpeg'}"
    return "application/octet-stream"


def migrate(
    sqlite_path: str,
    database_url: str,
    documents_dir: str,
    resumes_dir: str,
    kb_file: str,
    linkedin_settings_file: str
) -> Dict[str, int]:
    summary: Dict[str, int] = {}

    if not os.path.exists(sqlite_path):
        logger.warning(f"SQLite file not found at {sqlite_path}. Skipping SQLite table migration.")
    else:
        logger.info(f"Connecting to source SQLite database: {sqlite_path}")

    logger.info(f"Connecting to target PostgreSQL database: {database_url[:25]}...")
    pg_db = Database(database_url=database_url)
    logger.info("PostgreSQL database initialized and verified.")

    # 1. Migrate SQLite Tables
    if os.path.exists(sqlite_path):
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row

        tables_to_migrate = [
            ("sources", "id"),
            ("jobs", "id"),
            ("scrape_runs", "run_id"),
            ("run_logs", "run_id"),
            ("scrape_schedules", "id"),
            ("scrape_activity_logs", "run_id"),
            ("schedule_audit_logs", "id"),
            ("notifications", "id"),
            ("notification_settings", "id"),
        ]

        for table_name, pk_col in tables_to_migrate:
            try:
                # Check if table exists in SQLite
                check = sqlite_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
                ).fetchone()
                if not check:
                    continue

                rows = sqlite_conn.execute(f"SELECT * FROM {table_name}").fetchall()
                if not rows:
                    summary[table_name] = 0
                    continue

                col_names = list(rows[0].keys())
                placeholders = ",".join(["%s"] * len(col_names))
                cols_str = ",".join(col_names)

                # Build ON CONFLICT clause
                if pk_col and len(col_names) > 1:
                    updates = [f"{c} = excluded.{c}" for c in col_names if c != pk_col]
                    conflict_action = f"ON CONFLICT ({pk_col}) DO UPDATE SET {', '.join(updates)}"
                elif pk_col:
                    conflict_action = f"ON CONFLICT ({pk_col}) DO NOTHING"
                else:
                    conflict_action = ""

                insert_sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders}) {conflict_action}".strip()

                migrated_count = 0
                with pg_db.get_connection() as conn:
                    for r in rows:
                        vals = tuple(r[c] for c in col_names)
                        conn.execute(insert_sql, vals)
                        migrated_count += 1

                summary[table_name] = migrated_count
                logger.info(f"Migrated {migrated_count} rows in '{table_name}'.")

            except Exception as e:
                logger.error(f"Error migrating table '{table_name}': {e}")
                summary[table_name] = -1

        sqlite_conn.close()

    # 2. Migrate Knowledge Base metadata
    if os.path.exists(kb_file):
        try:
            with open(kb_file, "r", encoding="utf-8") as f:
                kb_data = json.load(f)
            docs = kb_data.get("documents", [])
            profile = kb_data.get("unified_profile", {})

            if docs:
                pg_db.save_kb_documents(docs)
                summary["kb_documents"] = len(docs)
                logger.info(f"Migrated {len(docs)} knowledge base documents from {kb_file}.")
            if profile:
                pg_db.save_kb_profile(profile)
                summary["kb_profile"] = 1
                logger.info("Migrated knowledge base unified profile.")
        except Exception as e:
            logger.error(f"Error migrating {kb_file}: {e}")
            summary["kb_documents"] = -1

    # 3. Migrate LinkedIn Settings
    if os.path.exists(linkedin_settings_file):
        try:
            with open(linkedin_settings_file, "r", encoding="utf-8") as f:
                li_settings = json.load(f)
            if isinstance(li_settings, dict):
                li_settings.pop("li_at", None)
                li_settings.pop("li_at_configured", None)
                pg_db.save_linkedin_feed_settings(li_settings)
                summary["linkedin_settings"] = 1
                logger.info("Migrated LinkedIn feed settings (secrets excluded).")
        except Exception as e:
            logger.error(f"Error migrating {linkedin_settings_file}: {e}")
            summary["linkedin_settings"] = -1

    # 4. Migrate Uploaded Documents
    files_migrated = 0
    if os.path.isdir(documents_dir):
        for fname in os.listdir(documents_dir):
            fpath = os.path.join(documents_dir, fname)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "rb") as fp:
                        content = fp.read()
                    ctype = detect_content_type(fname)
                    ext = os.path.splitext(fname)[1].lower().lstrip(".")
                    # Save under both filename and stripped doc_id
                    pg_db.save_file(fname, fname, content, content_type=ctype, file_type=ext)
                    # If format is doc_xxxx_filename, also index by doc_xxxx
                    m = re.match(r"^(doc_[a-f0-9]{8})_", fname)
                    if m:
                        pg_db.save_file(m.group(1), fname, content, content_type=ctype, file_type=ext)
                    files_migrated += 1
                except Exception as e:
                    logger.warning(f"Error migrating document {fname}: {e}")
        summary["uploaded_documents"] = files_migrated
        logger.info(f"Migrated {files_migrated} uploaded documents into stored_files.")

    # 5. Migrate Resumes and Cover Letters
    resumes_migrated = 0
    if os.path.isdir(resumes_dir):
        for fname in os.listdir(resumes_dir):
            fpath = os.path.join(resumes_dir, fname)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "rb") as fp:
                        content = fp.read()
                    ctype = detect_content_type(fname)
                    ext = os.path.splitext(fname)[1].lower().lstrip(".")
                    pg_db.save_file(fname, fname, content, content_type=ctype, file_type=ext)
                    resumes_migrated += 1
                except Exception as e:
                    logger.warning(f"Error migrating resume file {fname}: {e}")
        summary["generated_resumes"] = resumes_migrated
        logger.info(f"Migrated {resumes_migrated} generated resumes & cover letters into stored_files.")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data and local files to PostgreSQL idempotently.")
    parser.add_argument("--sqlite-path", default=os.path.join(ROOT_DIR, "data", "jobs.db"), help="Path to jobs.db SQLite file")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL"), help="Target PostgreSQL connection URL")
    parser.add_argument("--documents-dir", default=os.path.join(ROOT_DIR, "data", "documents"), help="Path to data/documents directory")
    parser.add_argument("--resumes-dir", default=os.path.join(ROOT_DIR, "data", "resumes"), help="Path to data/resumes directory")
    parser.add_argument("--kb-file", default=os.path.join(ROOT_DIR, "data", "knowledge_base.json"), help="Path to knowledge_base.json")
    parser.add_argument("--linkedin-settings-file", default=os.path.join(ROOT_DIR, "data", "linkedin_feed_settings.json"), help="Path to linkedin_feed_settings.json")

    args = parser.parse_args()

    if not args.database_url:
        logger.error("DATABASE_URL must be specified via --database-url or environment variable DATABASE_URL.")
        sys.exit(1)

    print("=" * 60)
    print("      SQLITE TO POSTGRESQL MIGRATION RUNNER")
    print("=" * 60)
    summary = migrate(
        sqlite_path=args.sqlite_path,
        database_url=args.database_url,
        documents_dir=args.documents_dir,
        resumes_dir=args.resumes_dir,
        kb_file=args.kb_file,
        linkedin_settings_file=args.linkedin_settings_file
    )

    print("\nMigration Complete Summary:")
    for k, v in summary.items():
        print(f"  - {k}: {v} records/files migrated")
    print("\nAll data is idempotently synchronized.")


if __name__ == "__main__":
    main()
