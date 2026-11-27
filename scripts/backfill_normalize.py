#!/usr/bin/env python3
"""
Backfill and Data Normalization Script.
Cleans and standardizes all existing job data in SQLite / PostgreSQL:
1. published_at -> ISO-8601 UTC (%Y-%m-%dT%H:%M:%SZ), handles epoch sec/millis and RFC-2822.
2. scraped_at -> ISO-8601 UTC.
3. experience_level -> mapped strictly to fresher, 0-1, 1-2, 2+, unknown.
4. source_url -> strips tracking parameters (trackingId, refId, trk, utm_*).
5. dedup_hash -> recomputed from cleaned URL, title, and company.
6. expires_at & is_active -> marks inactive if older than 30 days.
"""

import argparse
import logging
import os
import sys
from typing import Dict, List, Any, Optional

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scraper.database import Database
from scraper.cleaners import (
    clean_source_url,
    normalize_published_at,
    normalize_experience_level,
    compute_clean_dedup_hash,
    calculate_expires_at,
    is_job_active,
    ALLOWED_EXPERIENCE_LEVELS
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BackfillNormalize")


def run_backfill(db_path: Optional[str] = None, database_url: Optional[str] = None, cutoff_days: int = 30, dry_run: bool = False):
    db = Database(db_path=db_path)
    db.init_db()

    logger.info("Connecting to database...")
    with db.get_connection() as conn:
        # 1. Print existing experience level distribution
        logger.info("=== PRE-BACKFILL: DISTINCT EXPERIENCE LEVELS ===")
        pre_exp_rows = conn.execute("SELECT experience_level, COUNT(*) as cnt FROM jobs GROUP BY experience_level ORDER BY cnt DESC").fetchall()
        for r in pre_exp_rows:
            logger.info(f"  {repr(r['experience_level'])}: {r['cnt']}")

        # 2. Fetch all jobs
        jobs_rows = conn.execute("""
            SELECT id, title, company, location, source_url, published_at, scraped_at,
                   first_scraped_at, discovered_at, created_at, experience_level, expires_at, is_active
            FROM jobs
            ORDER BY id ASC
        """).fetchall()

        total_jobs = len(jobs_rows)
        logger.info(f"Loaded {total_jobs} total jobs to inspect and normalize.")

        updated_count = 0
        duplicates_removed = 0
        expired_count = 0
        active_count = 0
        seen_hashes = {}

        updates = []
        deletes = []

        for row in jobs_rows:
            job_id = row["id"]
            title = row["title"] or ""
            company = row["company"] or ""
            location = row["location"] or ""
            raw_url = row["source_url"] or ""

            # URL & Dedup Hash
            cleaned_url = clean_source_url(raw_url)
            new_hash = compute_clean_dedup_hash(title, company, location, cleaned_url)

            # Check dedup collision
            if new_hash in seen_hashes:
                # Duplicate row found when tracking params are stripped
                deletes.append(job_id)
                duplicates_removed += 1
                continue
            seen_hashes[new_hash] = job_id

            # published_at
            raw_pub = row["published_at"] or row["first_scraped_at"] or row["discovered_at"] or row["created_at"]
            norm_published = normalize_published_at(raw_pub)

            # scraped_at
            raw_scraped = row["scraped_at"] or row["first_scraped_at"] or row["discovered_at"] or row["created_at"] or norm_published
            norm_scraped = normalize_published_at(raw_scraped)

            # experience_level
            norm_exp = normalize_experience_level(row["experience_level"])

            # expires_at & is_active
            expires_at = calculate_expires_at(norm_published, default_days=cutoff_days)
            active_bool = is_job_active(norm_published, expires_at)
            is_active = 1 if active_bool else 0

            if is_active == 0:
                expired_count += 1
            else:
                active_count += 1

            status_val = "active" if is_active == 1 else "inactive"

            updates.append((
                new_hash,
                cleaned_url,
                norm_published,
                norm_scraped,
                norm_exp,
                expires_at,
                is_active,
                status_val,
                job_id
            ))
            updated_count += 1

        if not dry_run:
            logger.info(f"Executing updates for {len(updates)} jobs and removing {len(deletes)} duplicates...")
            for del_id in deletes:
                conn.execute("DELETE FROM jobs WHERE id = ?", (del_id,))

            for upd in updates:
                conn.execute("""
                    UPDATE jobs SET
                        dedup_hash = ?,
                        source_url = ?,
                        published_at = ?,
                        scraped_at = ?,
                        experience_level = ?,
                        expires_at = ?,
                        is_active = ?,
                        status = ?
                    WHERE id = ?
                """, upd)

            conn.commit()
            logger.info("Database commit successful.")
        else:
            logger.info("[DRY RUN] No database writes were committed.")

        # 3. Print post-backfill statistics
        logger.info("=== POST-BACKFILL SUMMARY ===")
        logger.info(f"Total rows inspected: {total_jobs}")
        logger.info(f"Updated rows:         {updated_count}")
        logger.info(f"Duplicates removed:   {duplicates_removed}")
        logger.info(f"Active jobs:          {active_count}")
        logger.info(f"Inactive/Expired:     {expired_count}")

        post_exp_rows = conn.execute("SELECT experience_level, COUNT(*) as cnt FROM jobs GROUP BY experience_level ORDER BY cnt DESC").fetchall()
        logger.info("=== POST-BACKFILL: DISTINCT EXPERIENCE LEVELS ===")
        all_valid = True
        for r in post_exp_rows:
            is_valid = r["experience_level"] in ALLOWED_EXPERIENCE_LEVELS
            if not is_valid:
                all_valid = False
            valid_mark = "[VALID]" if is_valid else "[INVALID!]"
            logger.info(f"  {valid_mark} {repr(r['experience_level'])}: {r['cnt']}")

        if all_valid:
            logger.info("ALL experience levels successfully normalized to strict enums: fresher, 0-1, 1-2, 2+, unknown.")
        else:
            logger.error("WARNING: Non-enum experience levels found!")

        # 4. Sample normalized dates
        sample_rows = conn.execute("SELECT id, title, published_at, scraped_at, expires_at FROM jobs ORDER BY published_at DESC LIMIT 5").fetchall()
        logger.info("=== SAMPLE NORMALIZED JOBS (LATEST 5) ===")
        for s in sample_rows:
            logger.info(f"  ID: {s['id'][:15]}... | Pub: {s['published_at']} | Scraped: {s['scraped_at']} | Exp: {s['expires_at']}")


def main():
    parser = argparse.ArgumentParser(description="Backfill and normalize job database records.")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file.")
    parser.add_argument("--database-url", default=None, help="PostgreSQL connection string.")
    parser.add_argument("--cutoff-days", type=int, default=30, help="Cutoff days for expiration.")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without committing.")
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    run_backfill(db_path=args.db_path, database_url=args.database_url, cutoff_days=args.cutoff_days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
