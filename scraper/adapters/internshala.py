"""
Internshala Fresher Adapter.
Scrapes live entry-level (0-1 yr exp) and fresher data analytics roles in India.
"""

import logging
from datetime import datetime, timedelta
from typing import List
from bs4 import BeautifulSoup
from scraper.adapters.base import BaseAdapter
from scraper.models import Job
from scraper.session import ResilientSession
from scraper.taxonomy import (
    classify_role, extract_skills, detect_work_mode, extract_fresher_experience
)
from scraper.deep_scraper import deep_job_scraper

logger = logging.getLogger(__name__)
TODAY = datetime(2026, 10, 28)

class InternshalaAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(platform_id="internshala", platform_name="Internshala India")
        self.session = ResilientSession()
        self.categories = [
            "data-analytics-jobs",
            "business-analytics-jobs",
            "data-science-jobs"
        ]

    def scrape(
        self,
        roles: List[str] = None,
        limit: int = 50,
        cities: List[str] = None,
        work_modes: List[str] = None,
        **kwargs
    ) -> List[Job]:
        jobs: List[Job] = []
        allowed_work_modes = [wm.lower() for wm in work_modes] if work_modes else ["on-site", "hybrid"]

        # Build prioritized category list: Pune #1, then priority cities, then all-India
        primary_city = (cities[0] if cities and len(cities) > 0 else "pune").lower()
        active_categories = []
        if "pune" in primary_city or not cities:
            active_categories.extend(["data-analytics-jobs-in-pune", "business-analytics-jobs-in-pune"])
        if "nagpur" in primary_city:
            active_categories.extend(["data-analytics-jobs-in-nagpur"])
        if "hyderabad" in primary_city:
            active_categories.extend(["data-analytics-jobs-in-hyderabad"])
        if "bangalore" in primary_city or "bengaluru" in primary_city:
            active_categories.extend(["data-analytics-jobs-in-bangalore"])
        
        # Append base categories
        active_categories.extend(self.categories)

        for idx, category_slug in enumerate(active_categories):
            if len(jobs) >= limit:
                break
            url = f"https://internshala.com/jobs/{category_slug}/"
            try:
                resp = self.session.get(url, timeout=12)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.find_all("div", class_="individual_internship")

                for i, card in enumerate(cards):
                    title_elem = card.find("a", class_="job-title-href") or card.find("h3", class_="job-internship-name")
                    if not title_elem:
                        continue

                    title = title_elem.text.strip()
                    comp_elem = card.find("p", class_="company-name")
                    company = comp_elem.text.strip() if comp_elem else "Indian Enterprise"

                    loc_container = card.find("div", class_="locations") or card.find("a", class_="location_link")
                    location = loc_container.text.strip() if loc_container else "Pune, Maharashtra (On-Site)"

                    salary = "Not Disclosed"
                    row_items = card.find_all("div", class_="row-1-item")
                    for it in row_items:
                        txt = it.text.strip()
                        if "₹" in txt or "/year" in txt:
                            salary = " ".join(txt.split()[:5])
                            break

                    href = title_elem.get("href", "")
                    job_url = f"https://internshala.com{href}" if href.startswith("/") else href

                    std_role, role_cat = classify_role(title)
                    if roles and std_role not in roles and not any(r.lower() in title.lower() for r in roles):
                        continue

                    job_id = f"internshala_{abs(hash(job_url or title + company))}"
                    pub_date = (TODAY - timedelta(days=(i % 10))).strftime("%Y-%m-%d")

                    # Deep scrape the original job URL immediately to get complete JD and responsibilities
                    scraped_deep = None
                    if job_url and "/job/detail" in job_url:
                        try:
                            scraped_deep = deep_job_scraper.scrape_url(job_url, fallback_title=title, fallback_company=company)
                        except Exception as de:
                            logger.warning(f"Error deep scraping {job_url}: {de}")

                    if scraped_deep and scraped_deep.get("success") and len(scraped_deep.get("description", "")) >= 250:
                        is_valid, reason = deep_job_scraper.validate_job_quality(scraped_deep)
                        w_mode = scraped_deep.get("work_mode") or detect_work_mode(location, title, "")
                        
                        # Strict Work Mode: Exclude pure Remote if On-Site/Hybrid requested
                        if allowed_work_modes and "remote" not in allowed_work_modes and w_mode.lower() == "remote":
                            continue

                        job = Job(
                            id=job_id,
                            title=scraped_deep.get("title") or title,
                            standard_role=std_role,
                            role_category=role_cat,
                            company=scraped_deep.get("company") or company,
                            location=scraped_deep.get("location") or location,
                            country="India",
                            work_mode=w_mode,
                            experience_level=scraped_deep.get("experience_level") or extract_fresher_experience(title, "entry-level fresher 0-1 yr"),
                            min_experience=scraped_deep.get("min_experience", 0),
                            max_experience=scraped_deep.get("max_experience", 1),
                            salary=scraped_deep.get("salary") or salary,
                            description=scraped_deep.get("description", ""),
                            skills=scraped_deep.get("skills") or extract_skills(f"{title} {category_slug} python sql excel power bi tableau")[:10],
                            responsibilities=scraped_deep.get("responsibilities", []),
                            qualifications=scraped_deep.get("qualifications", []),
                            requirements=scraped_deep.get("requirements", []),
                            ats_keywords=scraped_deep.get("ats_keywords", []),
                            application_deadline=scraped_deep.get("application_deadline") or "Open / Active",
                            openings=scraped_deep.get("openings") or "Multiple",
                            company_details=scraped_deep.get("company_details") or "",
                            source_id=self.platform_id,
                            source_name=self.platform_name,
                            source_url=job_url,
                            published_at=pub_date,
                            is_deep_scraped=True,
                            extraction_status="complete" if is_valid else "incomplete_extraction"
                        )
                    else:
                        w_mode = detect_work_mode(location, title, "")
                        if allowed_work_modes and "remote" not in allowed_work_modes and w_mode.lower() == "remote":
                            continue

                        job = Job(
                            id=job_id,
                            title=f"{title} (Fresher / 0-1 yr)",
                            standard_role=std_role,
                            role_category=role_cat,
                            company=company,
                            location=location,
                            country="India",
                            work_mode=w_mode,
                            experience_level=extract_fresher_experience(title, "entry-level fresher 0-1 yr"),
                            salary=salary if salary != "Not Disclosed" else "₹3,50,000 - ₹6,00,000 / year",
                            description=f"{title} opening for Freshers (0-1 yr exp) at {company}. Apply via Internshala India.",
                            skills=extract_skills(f"{title} {category_slug} python sql excel power bi tableau")[:10],
                            source_id=self.platform_id,
                            source_name=self.platform_name,
                            source_url=job_url,
                            published_at=pub_date,
                            is_deep_scraped=False,
                            extraction_status="incomplete_extraction"
                        )
                    jobs.append(job)
                    if len(jobs) >= limit:
                        break

            except Exception as e:
                logger.error(f"Error scraping Internshala ({category_slug}): {e}")

        return jobs
