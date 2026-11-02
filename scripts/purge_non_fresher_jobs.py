import sqlite3
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.taxonomy import analyze_job_fresher_eligibility

def purge_non_fresher_jobs():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jobs.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = c.execute("SELECT id, title, company, description, min_experience, max_experience, source_name, location FROM jobs").fetchall()
    print(f"Total jobs before audit & purge: {len(rows)}")

    purged_ids = []
    purged_details = []

    for r in rows:
        jid = r["id"]
        title = r["title"] or ""
        company = r["company"] or ""
        desc = r["description"] or ""
        loc = r["location"] or ""
        src = r["source_name"] or ""
        min_e = r["min_experience"]
        max_e = r["max_experience"]

        is_fresher, reason, detected_min, detected_max = analyze_job_fresher_eligibility(
            title=title,
            text=desc,
            raw_fields={"min_experience": min_e, "max_experience": max_e}
        )

        if not is_fresher:
            purged_ids.append(jid)
            purged_details.append((title, company, loc, src, reason))

    print(f"Identified {len(purged_ids)} non-fresher / experienced jobs to purge.")

    if purged_ids:
        # Delete non-fresher jobs
        placeholders = ",".join(["?"] * len(purged_ids))
        c.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", purged_ids)
        conn.commit()
        print(f"Successfully purged {len(purged_ids)} non-fresher jobs from {db_path}!")

    # Check remaining count
    remaining = c.execute("SELECT count(*) FROM jobs").fetchone()[0]
    print(f"Total remaining 100% genuine fresher jobs in DB: {remaining}")

    print("\nSample Purged Listings:")
    for d in purged_details[:15]:
        print(f"  ❌ [{d[3]}] {d[0]} @ {d[1]} ({d[2]}) -> {d[4]}")

if __name__ == "__main__":
    purge_non_fresher_jobs()

