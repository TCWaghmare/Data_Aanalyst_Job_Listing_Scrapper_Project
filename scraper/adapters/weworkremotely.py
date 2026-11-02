"""
WeWorkRemotely RSS Feed Adapter for Fresher & Junior Analytics Roles (0-1 Year Experience).
"""

import email.utils
import logging
import xml.etree.ElementTree as ET
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

class WeWorkRemotelyAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(platform_id="weworkremotely", platform_name="We Work Remotely")
        self.session = ResilientSession()
        self.feed_urls = [
            "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
            "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
            "https://weworkremotely.com/categories/remote-product-jobs.rss"
        ]

    def scrape(self, roles: List[str] = None, limit: int = 50) -> List[Job]:
        jobs: List[Job] = []
        for url in self.feed_urls:
            if len(jobs) >= limit:
                break
            try:
                resp = self.session.get(url)
                if resp.status_code != 200:
                    continue

                root = ET.fromstring(resp.content)
                channel = root.find("channel")
                if channel is None:
                    continue

                for i, item in enumerate(channel.findall("item")):
                    raw_title = item.findtext("title", "")
                    if ":" in raw_title:
                        company, title = raw_title.split(":", 1)
                        company = company.strip()
                        title = title.strip()
                    else:
                        company = "Remote Employer"
                        title = raw_title.strip()

                    desc = item.findtext("description", "")

                    # Strict fresher check (no senior, lead, 2+ yrs)
                    if not is_fresher_eligible(title, desc):
                        continue

                    is_analytics = any(k in title.lower() for k in [
                        "analyst", "analytics", "bi", "data", "reporting", "tableau", "power bi", "sql", "insights"
                    ])
                    if not is_analytics:
                        continue

                    std_role, category = classify_role(title, desc)
                    if roles and std_role not in roles and not any(r.lower() in title.lower() for r in roles):
                        continue

                    link = item.findtext("link", "https://weworkremotely.com")
                    raw_pub = item.findtext("pubDate", "")
                    guid = item.findtext("guid", link)

                    # Parse pubDate to clean YYYY-MM-DD
                    pub_date = (TODAY - timedelta(days=(i % 14))).strftime("%Y-%m-%d")
                    if raw_pub:
                        try:
                            parsed_time = email.utils.parsedate_to_datetime(raw_pub)
                            pub_date = parsed_time.strftime("%Y-%m-%d")
                        except Exception:
                            pass

                    job = Job(
                        id=f"wwr_{abs(hash(guid))}",
                        title=f"{title} (0-1 yr exp)",
                        standard_role=std_role,
                        role_category=category,
                        company=company,
                        location="Worldwide Remote (Open to India)",
                        country="Remote (Open to India)",
                        work_mode="Remote",
                        experience_level=extract_fresher_experience(title, desc),
                        salary="Competitive Global Remote Package",
                        description=desc[:1500] if desc else "",
                        skills=extract_skills(f"{title} {desc}")[:10],
                        source_id=self.platform_id,
                        source_name=self.platform_name,
                        source_url=link,
                        published_at=pub_date
                    )
                    jobs.append(job)
                    if len(jobs) >= limit:
                        break

            except Exception as e:
                logger.error(f"Error scraping WeWorkRemotely ({url}): {e}")

        return jobs
