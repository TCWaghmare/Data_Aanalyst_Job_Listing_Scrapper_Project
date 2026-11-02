"""
Jobicy Adapter for Fresher & Junior Data Analytics Roles (0-1 Year Experience).
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

class JobicyAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(platform_id="jobicy", platform_name="Jobicy")
        self.session = ResilientSession()
        self.url = "https://jobicy.com/api/v2/remote-jobs?count=50&industry=data-science"

    def scrape(self, roles: List[str] = None, limit: int = 50) -> List[Job]:
        jobs: List[Job] = []
        try:
            resp = self.session.get(self.url)
            if resp.status_code != 200:
                return jobs

            data = resp.json()
            items = data.get("jobs", [])

            for i, item in enumerate(items):
                title = item.get("jobTitle", "")
                desc = item.get("jobDescription", "")

                if not is_fresher_eligible(title, desc):
                    continue

                std_role, category = classify_role(title, desc)
                if roles and std_role not in roles and not any(r.lower() in title.lower() for r in roles):
                    continue

                company = item.get("companyName", "Technology Employer")
                location = item.get("jobGeo", "Worldwide Remote (Open to India)")
                source_url = item.get("url", "https://jobicy.com")
                salary_min = item.get("annualSalaryMin")
                salary_max = item.get("annualSalaryMax")
                currency = item.get("salaryCurrency", "USD")

                salary = f"{currency} {salary_min:,} - {salary_max:,} / yr" if salary_min and salary_max else "Competitive / Market Standard"

                raw_pub = item.get("pubDate", "")
                pub_date = raw_pub.split("T")[0] if "T" in raw_pub else (TODAY - timedelta(days=(i % 14))).strftime("%Y-%m-%d")

                job = Job(
                    id=f"jobicy_{item.get('id')}",
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
                    skills=extract_skills(f"{title} {desc}")[:10],
                    source_id=self.platform_id,
                    source_name=self.platform_name,
                    source_url=source_url,
                    published_at=pub_date
                )
                jobs.append(job)
                if len(jobs) >= limit:
                    break

        except Exception as e:
            logger.error(f"Error scraping Jobicy: {e}")

        return jobs
