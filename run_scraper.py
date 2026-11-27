"""
Command Line Interface (CLI) for Fresher Data Analyst Job Scraper (0-1 Year Exp).
Scrapes curated platforms from india_and_global_remote_job_platforms.pdf.

Usage:
  python run_scraper.py --all
  python run_scraper.py --roles "Data Analyst" "Junior Data Analyst" "Power BI Developer"
  python run_scraper.py --date-posted 7d --export csv
  python run_scraper.py --list-platforms
  python run_scraper.py --list-roles
  python run_scraper.py --stats
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

from scraper.database import Database
from scraper.engine import ScraperEngine
from scraper.registry import PlatformRegistry
from scraper.taxonomy import ALL_ROLES, CORE_ANALYTICS_ROLES, RELATED_ROLES

def export_to_csv(jobs, filepath="fresher_scraped_jobs.csv"):
    if not jobs:
        print("No jobs to export.")
        return
    fieldnames = [
        "id", "title", "standard_role", "role_category", "company", "location",
        "country", "work_mode", "experience_level", "salary", "skills",
        "source_name", "source_url", "published_at", "discovered_at"
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for j in jobs:
            row = j.model_dump()
            row["skills"] = ", ".join(row.get("skills", []))
            row.pop("description", None)
            row.pop("is_active", None)
            row.pop("source_id", None)
            writer.writerow(row)
    print(f"Exported {len(jobs)} jobs to CSV: {os.path.abspath(filepath)}")

def export_to_json(jobs, filepath="fresher_scraped_jobs.json"):
    if not jobs:
        print("No jobs to export.")
        return
    data = [j.model_dump() for j in jobs]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(jobs)} jobs to JSON: {os.path.abspath(filepath)}")

def main():
    parser = argparse.ArgumentParser(
        description="Fresher Data Analyst Job Scraper CLI (0-1 Year Experience) - India & Global Remote Open to India."
    )
    parser.add_argument("--all", action="store_true", help="Run scrape across active adapters (default)")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-adapter timeout in seconds (default: 60s)")
    parser.add_argument("--process-queue", action="store_true", help="Process queued scrape runs from run_logs first")
    parser.add_argument("--roles", nargs="+", help="Multi-select specific job roles (e.g. 'Data Analyst' 'Power BI Developer')")
    parser.add_argument("--category", choices=["core", "related", "all"], default="all", help="Role category filter")
    parser.add_argument("--country", type=str, help="Country filter (e.g. India, Remote)")
    parser.add_argument("--cities", nargs="+", default=["Pune", "Nagpur", "Hyderabad", "Aurangabad", "Bengaluru"], help="Priority city sequence (default: Pune #1, Nagpur, Hyderabad, Aurangabad, Bengaluru)")
    parser.add_argument("--work-modes", nargs="+", default=["On-Site", "Hybrid"], help="Allowed work modes (default: On-Site and Hybrid only, excluding Remote)")
    parser.add_argument("--pune-first", action="store_true", default=True, help="Enforce Pune & nearby region as first priority before other cities")
    parser.add_argument("--date-posted", choices=["24h", "3d", "7d", "14d", "30d"], default="30d", help="Filter by posting age (default: 30d)")
    parser.add_argument("--sources", nargs="+", help="Adapter IDs to run")
    parser.add_argument("--limit", type=int, default=30, help="Max jobs to fetch per source (default 30)")
    parser.add_argument("--export", choices=["csv", "json"], help="Export jobs to CSV or JSON")
    parser.add_argument("--output", type=str, help="Custom export output file path")
    parser.add_argument("--list-platforms", action="store_true", help="List the 72 curated platforms from directory PDF")
    parser.add_argument("--list-roles", action="store_true", help="List all 25 target roles")
    parser.add_argument("--stats", action="store_true", help="Show database metrics and statistics")

    args = parser.parse_args()
    db = Database()
    registry = PlatformRegistry()

    if args.list_roles:
        print("\n=======================================================")
        print("    FRESHER DATA ANALYTICS JOB ROLES (0-1 YEAR EXP)    ")
        print("=======================================================")
        print(f"\n[ CORE ANALYTICS ROLES ({len(CORE_ANALYTICS_ROLES)}) ]")
        for i, r in enumerate(CORE_ANALYTICS_ROLES, 1):
            print(f"  {i:2d}. {r}")
        print(f"\n[ RELATED ROLES ({len(RELATED_ROLES)}) ]")
        for i, r in enumerate(RELATED_ROLES, 1):
            print(f"  {i:2d}. {r}")
        print("=======================================================\n")
        return

    if args.list_platforms:
        print("\n=========================================================================================")
        print("      CURATED PLATFORMS DIRECTORY (72 PLATFORMS: INDIA & GLOBAL REMOTE OPEN TO INDIA)      ")
        print("=========================================================================================")
        platforms = registry.get_all()
        by_section = {}
        for p in platforms:
            by_section.setdefault(p.section, []).append(p)
        
        for section, plist in by_section.items():
            print(f"\n>>> {section.upper()} ({len(plist)} platforms)")
            for p in plist:
                adapter_flag = "[LIVE ADAPTER]" if p.has_adapter else "[CATALOG LINK]"
                print(f"  • {p.name:<32} | {p.country:<18} | {adapter_flag:<14} | {p.website}")
        print("\n=========================================================================================\n")
        return

    if args.stats:
        stats = db.get_statistics()
        print("\n=======================================================")
        print("          FRESHER JOB SCRAPER SYSTEM STATISTICS        ")
        print("=======================================================")
        print(f"Total Active Jobs (Past 30d): {stats['total_jobs']}")
        print(f"Fresher Openings (0-1y Exp):  {stats['fresher_jobs']}")
        print(f"Core Analytics Jobs:          {stats['core_jobs']}")
        print(f"Related Role Jobs:            {stats['related_jobs']}")
        print(f"India Jobs:                   {stats['india_jobs']}")
        print(f"Remote (Open to India) Jobs:  {stats['remote_jobs']}")
        print(f"Curated Platform Directory:   {stats['total_sources']} platforms")
        print("\nTop Fresher Roles in DB:")
        for r in stats['roles_distribution'][:8]:
            print(f"  • {r['standard_role']:<30}: {r['cnt']} jobs")
        print("=======================================================\n")
        return

    target_roles = None
    if args.roles:
        target_roles = args.roles
    elif args.category == "core":
        target_roles = CORE_ANALYTICS_ROLES
    elif args.category == "related":
        target_roles = RELATED_ROLES

    # If --export is requested, handle export first
    if args.export:
        cat_filter = ""
        if args.category == "core":
            cat_filter = "Core Analytics"
        elif args.category == "related":
            cat_filter = "Related"

        jobs, total = db.get_jobs(
            roles=target_roles,
            role_category=cat_filter,
            country=args.country or "",
            date_filter=args.date_posted or "30d",
            limit=1000
        )
        out = args.output or f"fresher_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{args.export}"
        if args.export == "csv":
            export_to_csv(jobs, out)
        else:
            export_to_json(jobs, out)
        return

    # Check for queued runs if requested or if pending
    if args.process_queue:
        queued = db.get_queued_run_requests()
        if queued:
            print(f"\nFound {len(queued)} queued scrape request(s) in run_logs. Processing queue...")
            engine = ScraperEngine(db=db, registry=registry)
            any_failure = False
            for q in queued:
                q_id = q["run_id"]
                raw_sources = q.get("adapters_scanned")
                adapter_ids = None
                if raw_sources:
                    try:
                        parsed = json.loads(raw_sources)
                        if isinstance(parsed, list) and "all" not in parsed:
                            adapter_ids = parsed
                    except Exception:
                        pass
                print(f"Processing queued run {q_id} (trigger: {q.get('trigger_source')})...")
                run = engine.run(
                    adapter_ids=adapter_ids,
                    roles=target_roles,
                    limit_per_source=args.limit,
                    cities=args.cities,
                    work_modes=args.work_modes,
                    run_id=q_id,
                    schedule_name=q.get("schedule_name"),
                    trigger_source=q.get("trigger_source", "queued"),
                    triggered_by=q.get("triggered_by", "Worker CLI"),
                    adapter_timeout=args.timeout
                )
                if run.status == "failed":
                    any_failure = True
            if any_failure:
                print("❌ One or more queued runs suffered total failure. Exiting 1.")
                sys.exit(1)
            sys.exit(0)
        else:
            print("No queued scrape runs found in run_logs.")

    # Default execution: run scrape across all adapters (or specified --sources)
    engine = ScraperEngine(db=db, registry=registry)
    print(f"\n=======================================================")
    print(f"Starting Fresher Job Scraper CLI at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Storage: {'PostgreSQL (DATABASE_URL)' if db.is_postgres else 'SQLite (' + str(db.db_path) + ')'}")
    print(f"Priority City Queue: {', '.join(args.cities)}")
    print(f"Target Work Modes: {', '.join(args.work_modes)} (Remote excluded)")
    print(f"Per-Adapter Timeout: {args.timeout}s (Failure Isolation Enabled)")
    print("=======================================================\n")

    run = engine.run(
        adapter_ids=args.sources if args.sources else None,
        roles=target_roles,
        limit_per_source=args.limit,
        cities=args.cities,
        work_modes=args.work_modes,
        adapter_timeout=args.timeout,
        trigger_source="cli",
        triggered_by="CLI/GitHub Actions Runner"
    )

    print("\n=======================================================")
    print(f"             SCRAPE RUN SUMMARY: {run.status.upper()}")
    print("=======================================================")
    print(f"Run ID:             {run.run_id}")
    print(f"Status:             {run.status}")
    print(f"Jobs Scanned:       {run.jobs_scanned}")
    print(f"Jobs Added:         {run.jobs_added}")
    print(f"Duplicates Skipped: {run.duplicates_skipped}")
    print(f"Errors Encountered: {run.errors_count}")
    print("-------------------------------------------------------")
    if getattr(run, "adapter_summaries", None):
        print("Adapter Breakdown:")
        for aid, s in run.adapter_summaries.items():
            status_icon = "✅" if s.get("status") in ["success", "zero_results"] else "❌"
            dur = s.get("duration_seconds", 0)
            scanned = s.get("jobs_scanned", 0)
            added = s.get("jobs_added", 0)
            err = f" - {s.get('error')}" if s.get("error") else ""
            print(f"  {status_icon} {s.get('name', aid):<28} | {s.get('status'):<12} | {dur}s | +{added} jobs{err}")
    print("=======================================================\n")

    if run.status == "failed":
        print("❌ Scraper run resulted in TOTAL FAILURE (0 adapters completed successfully). Exiting with code 1.")
        sys.exit(1)
    else:
        print(f"✅ Scraper run finished with status '{run.status}'. Exiting with code 0.")
        sys.exit(0)

if __name__ == "__main__":
    main()
