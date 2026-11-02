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
    parser.add_argument("--all", action="store_true", help="Run scrape across active adapters")
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

    if args.all or args.sources or target_roles or args.limit:
        engine = ScraperEngine(db=db, registry=registry)
        print(f"Starting fresher scrape run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        print(f"Priority City Queue: {', '.join(args.cities)}")
        print(f"Target Work Modes: {', '.join(args.work_modes)} (Remote excluded)")
        run = engine.run(
            adapter_ids=args.sources,
            roles=target_roles,
            limit_per_source=args.limit,
            cities=args.cities,
            work_modes=args.work_modes
        )
        print(f"Scrape completed: {run.jobs_added} new jobs added, {run.duplicates_skipped} duplicates skipped, {run.jobs_scanned} total scanned.")

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

if __name__ == "__main__":
    main()
