"""
Arbeitnow API Adapter.
Scrapes European & Global tech and data postings.
"""

import logging
from typing import List
from scraper.adapters.base import BaseAdapter
from scraper.models import Job
from scraper.session import ResilientSession
from scraper.taxonomy import (
    classify_role, extract_skills, extract_experience_level,
    detect_work_mode, normalize_country
)

logger = logging.getLogger(__name__)

class ArbeitnowAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(platform_id="stepstone_germany", platform_name="Arbeitnow / European Tech")
        self.session = ResilientSession()
        self.url = "https://www.arbeitnow.com/api/job-board-api"

    def scrape(self, roles: List[str] = None, limit: int = 50) -> List[Job]:
        jobs: List[Job] = []
        try:
            resp = self.session.get(self.url)
            if resp.status_code != 200:
                logger.warning(f"Arbeitnow returned {resp.status_code}")
                return jobs

            data = resp.json()
            items = data.get("data", [])

            for item in items:
                title = item.get("title", "")
                desc = item.get("description", "")
                
                # Check if analytics / data related
                is_analytics = any(k in title.lower() for k in [
                    "analyst", "analytics", "bi ", "power bi", "tableau", "sql", "data", "reporting", "scientist"
                ])
                if not is_analytics:
                    continue

                std_role, category = classify_role(title, desc)
                if roles and std_role not in roles and not any(r.lower() in title.lower() for r in roles):
                    continue

                company = item.get("company_name", "Enterprise")
                location = item.get("location", "Europe / Remote")
                source_url = item.get("url", "https://www.arbeitnow.com")
                remote_flag = item.get("remote", False)
                work_mode = "Remote" if remote_flag else detect_work_mode(location, title, desc)

                tags = item.get("tags") or []
                skills = list(set(extract_skills(f"{title} {desc}") + [t.title() for t in tags if len(t) < 20]))

                job = Job(
                    id=f"arbeitnow_{item.get('slug')}",
                    title=title,
                    standard_role=std_role,
                    role_category=category,
                    company=company,
                    location=location,
                    country=normalize_country(location),
                    work_mode=work_mode,
                    experience_level=extract_experience_level(title, desc),
                    salary="Competitive European Market Rate",
                    description=desc[:1500] if desc else "",
                    skills=skills[:10],
                    source_id="stepstone_germany",
                    source_name=self.platform_name,
                    source_url=source_url,
                    published_at=str(item.get("created_at"))
                )
                jobs.append(job)
                if len(jobs) >= limit:
                    break

        except Exception as e:
            logger.error(f"Error scraping Arbeitnow: {e}")

        return jobs

