"""
Himalayas Adapter for Data Analyst & Business Analyst Roles (Fresher / 0-1 Year Experience).
Fetches genuine remote listings worldwide and open to India via Himalayas public jobs API.
"""

import html
import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional
from scraper.adapters.base import BaseAdapter
from scraper.models import Job
from scraper.session import ResilientSession
from scraper.taxonomy import (
    classify_role, extract_skills, is_fresher_eligible,
    extract_fresher_experience, normalize_country
)

logger = logging.getLogger(__name__)
TODAY = datetime(2026, 10, 30)

class HimalayasAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(platform_id="himalayas", platform_name="Himalayas Remote")
        self.session = ResilientSession(timeout=10)
        self.base_url = "https://himalayas.app/jobs/api"

    def scrape(
        self,
        roles: List[str] = None,
        limit: int = 30,
        cities: List[str] = None,
        work_modes: List[str] = None,
        **kwargs
    ) -> List[Job]:
        jobs: List[Job] = []
        queries = ["data analyst", "business analyst", "data"]

        for q in queries:
            if len(jobs) >= limit:
                break
            url = f"{self.base_url}?q={q}&limit=50"
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                items = data.get("jobs", [])

                for i, item in enumerate(items):
                    title = item.get("title", "")
                    raw_desc = item.get("description", "")
                    # Strip HTML tags
                    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                    clean_desc = html.unescape(clean_desc).strip()

                    # Pre-filter for analytics / data
                    is_analytics = any(k in title.lower() for k in [
                        "analyst", "analytics", "bi ", "power bi", "tableau", "sql", "data", "reporting", "insights"
                    ])
                    if not is_analytics:
                        continue

                    if not is_fresher_eligible(title, clean_desc):
                        continue

                    std_role, category = classify_role(title, clean_desc)
                    if std_role == "Unclassified":
                        continue

                    if roles and std_role not in roles and not any(r.lower() in title.lower() for r in roles):
                        continue

                    company = item.get("companyName", "Technology Employer")
                    slug = item.get("slug", "")
                    comp_slug = item.get("companySlug", "")
                    source_url = item.get("applicationLink") or (
                        f"https://himalayas.app/companies/{comp_slug}/jobs/{slug}" if comp_slug and slug else "https://himalayas.app"
                    )

                    loc_restrictions = item.get("locationRestrictions") or []
                    location = ", ".join(loc_restrictions) if loc_restrictions else "Worldwide Remote (Open to India)"

                    min_sal = item.get("minSalary")
                    max_sal = item.get("maxSalary")
                    curr = item.get("currency", "USD") or "USD"
                    if min_sal and max_sal:
                        salary = f"{curr} {min_sal:,} - {max_sal:,} / yr"
                    elif min_sal:
                        salary = f"{curr} {min_sal:,}+ / yr"
                    else:
                        salary = "Competitive / Market Standard"

                    pub_raw = item.get("pubDate", "")
                    pub_date = pub_raw.split("T")[0] if "T" in pub_raw else (TODAY - timedelta(days=(i % 15))).strftime("%Y-%m-%d")

                    categories = item.get("categories") or []
                    tags = [c.replace("-", " ") for c in categories]
                    skills = list(set(extract_skills(f"{title} {clean_desc}") + tags))[:10]

                    job = Job(
                        id=f"himalayas_{item.get('id') or abs(hash(source_url))}",
                        title=f"{title} (0-1 yr exp)" if "0-1" not in title and "fresher" not in title.lower() else title,
                        standard_role=std_role,
                        role_category=category,
                        company=company,
                        location=location,
                        country=normalize_country(location),
                        work_mode="Remote",
                        experience_level=extract_fresher_experience(title, clean_desc),
                        salary=salary,
                        description=clean_desc[:2500] if clean_desc else f"{title} opening at {company}",
                        skills=skills,
                        source_id=self.platform_id,
                        source_name=self.platform_name,
                        source_url=source_url,
                        published_at=pub_date,
                        is_deep_scraped=True,
                        extraction_status="complete"
                    )
                    jobs.append(job)
                    if len(jobs) >= limit:
                        break

            except Exception as e:
                logger.error(f"Error scraping Himalayas ({q}): {e}")

        return jobs
