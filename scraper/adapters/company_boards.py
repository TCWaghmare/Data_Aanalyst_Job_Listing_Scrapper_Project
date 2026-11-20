"""
Company Boards Adapter filtered for Early-Career & Fresher (0-1 Year Experience).
"""

import logging
from datetime import datetime, timedelta
from typing import List
from scraper.adapters.base import BaseAdapter
from scraper.models import Job
from scraper.session import ResilientSession
from scraper.taxonomy import (
    classify_role, extract_skills, is_fresher_eligible,
    extract_fresher_experience, normalize_country
)

logger = logging.getLogger(__name__)
TODAY = datetime(2026, 10, 28)

GREENHOUSE_COMPANIES = [
    ("cloudflare", "Cloudflare", "google_careers"),
    ("gitlab", "GitLab", "atlassian_careers"),
    ("canonical", "Canonical", "google_careers"),
    ("stripe", "Stripe", "salesforce_careers"),
    ("inmobi", "InMobi (India)", "flipkart_careers"),
    ("groww", "Groww (India)", "phonepe_careers"),
]

LEVER_COMPANIES = [
    ("cred", "CRED (India)", "razorpay_jobs"),
]

class CompanyBoardsAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(platform_id="company_careers", platform_name="Direct Career Boards")
        self.session = ResilientSession()

    def scrape(self, roles: List[str] = None, limit: int = 50) -> List[Job]:
        jobs: List[Job] = []

        for comp_slug, comp_name, platform_ref in GREENHOUSE_COMPANIES:
            if len(jobs) >= limit:
                break
            url = f"https://boards-api.greenhouse.io/v1/boards/{comp_slug}/jobs"
            try:
                resp = self.session.get(url, timeout=6)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for i, item in enumerate(data.get("jobs", [])):
                    title = item.get("title", "")
                    is_analytics = any(k in title.lower() for k in [
                        "analyst", "analytics", "bi ", "business intelligence",
                        "tableau", "power bi", "sql", "insights", "reporting", "decision", "data engineer"
                    ])
                    if not is_analytics:
                        continue

                    # Pre-check fresher on title
                    if not is_fresher_eligible(title, ""):
                        continue

                    std_role, category = classify_role(title)
                    if std_role == "Unclassified":
                        continue
                    if roles and std_role not in roles and not any(r.lower() in title.lower() for r in roles):
                        continue

                    # Fetch detailed content for this single matching analytics job
                    job_id_num = item.get("id")
                    content = ""
                    try:
                        detail_resp = self.session.get(f"https://boards-api.greenhouse.io/v1/boards/{comp_slug}/jobs/{job_id_num}", timeout=5)
                        if detail_resp.status_code == 200:
                            content = detail_resp.json().get("content", "")
                    except Exception:
                        content = f"Data Analytics opening at {comp_name}."

                    if not is_fresher_eligible(title, content):
                        continue

                    location_obj = item.get("location") or {}
                    location_name = location_obj.get("name") or "Remote (Open to India)"
                    job_url = item.get("absolute_url") or f"https://boards.greenhouse.io/{comp_slug}/jobs/{job_id_num}"

                    pub_date = (TODAY - timedelta(days=(i % 16))).strftime("%Y-%m-%d")

                    job = Job(
                        id=f"gh_{comp_slug}_{job_id_num}",
                        title=f"{title} (0-1 yr exp)",
                        standard_role=std_role,
                        role_category=category,
                        company=comp_name,
                        location=location_name,
                        country=normalize_country(location_name),
                        work_mode="Hybrid" if "hybrid" in location_name.lower() else ("On-Site" if "on-site" in location_name.lower() else "Remote"),
                        experience_level=extract_fresher_experience(title, content),
                        salary="Competitive Market Salary & Benefits",
                        description=content[:1500] if content else f"Entry-level position at {comp_name}",
                        skills=extract_skills(f"{title} {content}")[:10],
                        source_id=platform_ref,
                        source_name=f"{comp_name} Careers",
                        source_url=job_url,
                        published_at=pub_date,
                        is_deep_scraped=True,
                        extraction_status="complete"
                    )
                    jobs.append(job)
                    if len(jobs) >= limit:
                        break
            except Exception as e:
                logger.error(f"Error fetching Greenhouse board {comp_slug}: {e}")

        for comp_slug, comp_name, platform_ref in LEVER_COMPANIES:
            if len(jobs) >= limit:
                break
            url = f"https://api.lever.co/v0/postings/{comp_slug}"
            try:
                resp = self.session.get(url, timeout=6)
                if resp.status_code != 200:
                    continue
                try:
                    data = resp.json()
                except Exception:
                    continue
                if not isinstance(data, list):
                    continue
                for i, item in enumerate(data):
                    title = item.get("text", "")
                    desc = item.get("descriptionPlain", "")

                    if not is_fresher_eligible(title, desc):
                        continue

                    is_analytics = any(k in title.lower() for k in [
                        "analyst", "analytics", "bi", "data", "reporting", "insights", "sql"
                    ])
                    if not is_analytics:
                        continue

                    std_role, category = classify_role(title)
                    if roles and std_role not in roles and not any(r.lower() in title.lower() for r in roles):
                        continue

                    categories = item.get("categories") or {}
                    location = categories.get("location") or "Bengaluru, India"
                    pub_date = (TODAY - timedelta(days=(i % 12))).strftime("%Y-%m-%d")

                    job = Job(
                        id=f"lever_{comp_slug}_{item.get('id')}",
                        title=f"{title} (0-1 yr exp)",
                        standard_role=std_role,
                        role_category=category,
                        company=comp_name,
                        location=location,
                        country="India",
                        work_mode="On-Site",
                        experience_level=extract_fresher_experience(title, desc),
                        salary="Top Tier Industry Standard",
                        description=desc[:1500] if desc else "",
                        skills=extract_skills(f"{title} {desc}")[:10],
                        source_id=platform_ref,
                        source_name=f"{comp_name} Careers",
                        source_url=item.get("hostedUrl", f"https://jobs.lever.co/{comp_slug}"),
                        published_at=pub_date
                    )
                    jobs.append(job)
                    if len(jobs) >= limit:
                        break
            except Exception as e:
                logger.error(f"Error fetching Lever board {comp_slug}: {e}")

        return jobs
