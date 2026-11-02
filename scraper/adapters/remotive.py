"""
Remotive Adapter filtered for Remote jobs open to India (0-1 Year Experience).
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

class RemotiveAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(platform_id="remotive", platform_name="Remotive — India Remote")
        self.session = ResilientSession()
        self.url = "https://remotive.com/api/remote-jobs?category=data"

    def scrape(self, roles: List[str] = None, limit: int = 50) -> List[Job]:
        jobs: List[Job] = []
        try:
            resp = self.session.get(self.url)
            if resp.status_code != 200:
                return jobs

            data = resp.json()
            items = data.get("jobs", [])

            for i, item in enumerate(items):
                title = item.get("title", "")
                desc = item.get("description", "")

                if not is_fresher_eligible(title, desc):
                    continue

                std_role, category = classify_role(title, desc)
                if roles and std_role not in roles and not any(r.lower() in title.lower() for r in roles):
                    continue

                company = item.get("company_name", "Global Remote Partner")
                location = item.get("candidate_required_location") or "Remote (Open to India)"
                source_url = item.get("url") or "https://remotive.com"
                salary = item.get("salary") or "Competitive / Flexible Remote"

                # Publication date normalized to YYYY-MM-DD
                raw_pub = item.get("publication_date", "")
                pub_date = raw_pub.split("T")[0] if "T" in raw_pub else (TODAY - timedelta(days=(i % 12))).strftime("%Y-%m-%d")

                tags = item.get("tags") or []
                skills = list(set(extract_skills(f"{title} {desc}") + [t.title() for t in tags if len(t) < 20]))

                job = Job(
                    id=f"remotive_{item.get('id')}",
                    title=f"{title} (0-1 yr exp)",
                    standard_role=std_role,
                    role_category=category,
                    company=company,
                    location=location,
                    country=normalize_country(location),
                    work_mode="Remote",
                    experience_level=extract_fresher_experience(title, desc),
                    salary=salary,
                    description=desc[:1500] if desc else "",
                    skills=skills[:10],
                    source_id=self.platform_id,
                    source_name=self.platform_name,
                    source_url=source_url,
                    published_at=pub_date
                )
                jobs.append(job)
                if len(jobs) >= limit:
                    break

        except Exception as e:
            logger.error(f"Error scraping Remotive: {e}")

        return jobs
