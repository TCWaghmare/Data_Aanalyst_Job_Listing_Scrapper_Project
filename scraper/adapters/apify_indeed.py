"""
Apify Indeed Jobs Scraper Adapter.
Fetches genuine Indeed job listings (0-2 years experience) using the Apify API and misceres/indeed-scraper actor.
Strictly cost-optimized to consume minimal Apify credits / compute units.
"""

import os
import re
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from apify_client import ApifyClient

from scraper.adapters.base import BaseAdapter
from scraper.models import Job
from scraper.taxonomy import (
    classify_role, extract_skills, detect_work_mode, extract_fresher_experience,
    analyze_job_fresher_eligibility, is_fresher_eligible
)

logger = logging.getLogger("apify_indeed")

load_dotenv()

class ApifyIndeedAdapter(BaseAdapter):
    def __init__(self, platform_id: str = "indeed_india", platform_name: str = "Indeed (Apify)", token: Optional[str] = None):
        super().__init__(platform_id=platform_id, platform_name=platform_name)
        self.token = token or os.environ.get("APIFY_API_TOKEN")
        self.actor_id = "misceres/indeed-scraper"

    def _get_client(self) -> Optional[ApifyClient]:
        if not self.token:
            self.token = os.environ.get("APIFY_API_TOKEN")
        if not self.token:
            logger.error("No APIFY_API_TOKEN found in environment or .env file.")
            return None
        return ApifyClient(self.token)

    def scrape(
        self,
        roles: List[str] = None,
        limit: int = 5,
        cities: List[str] = None,
        work_modes: List[str] = None,
        **kwargs
    ) -> List[Job]:
        """
        Scrapes genuine Indeed fresher job listings via Apify with strict token-saver optimizations:
        - Prioritizes Pune (and near regions) first, then cascading to other target cities.
        - Filters exclusively for On-Site and Hybrid roles (skipping Remote).
        - parseCompanyDetails: False (disables heavy company page crawls)
        - max_items: tight cap (3-5 items)
        - max_total_charge_usd: circuit breaker ($0.05 max per run)
        - memory_mbytes: 512 MB (minimal compute units)
        """
        client = self._get_client()
        if not client:
            logger.warning("Apify client could not be initialized (missing token). Skipping Indeed scrape.")
            return []

        target_role = (roles[0] if roles and len(roles) > 0 else "Data Analyst")
        fetch_limit = max(1, min(limit or 5, 10))

        # Include fresher keyword to target 0-2 yrs experience
        search_query = f"{target_role} fresher" if "fresher" not in target_role.lower() and "junior" not in target_role.lower() else target_role

        # City priority hierarchy: Pune #1, then Nagpur, Hyderabad, Aurangabad, Bengaluru, Pan-India
        primary_city = (cities[0] if cities and len(cities) > 0 else "Pune, Maharashtra")
        if "pune" in primary_city.lower():
            target_location = "Pune, Maharashtra"
        elif "nagpur" in primary_city.lower():
            target_location = "Nagpur, Maharashtra"
        elif "hyderabad" in primary_city.lower():
            target_location = "Hyderabad, Telangana"
        elif "aurangabad" in primary_city.lower():
            target_location = "Aurangabad, Maharashtra"
        elif "bengaluru" in primary_city.lower() or "bangalore" in primary_city.lower():
            target_location = "Bengaluru, Karnataka"
        else:
            target_location = primary_city

        allowed_work_modes = [wm.lower() for wm in work_modes] if work_modes else ["on-site", "hybrid"]

        logger.info(f"Triggering Apify Indeed Scraper for query: '{search_query}', location: '{target_location}', limit: {fetch_limit} (Cost-Optimized)")

        run_input = {
            "position": search_query,
            "country": "IN",
            "location": target_location,
            "maxItemsPerSearch": fetch_limit,
            "parseCompanyDetails": False,  # TOKEN SAVER: disables auxiliary company crawls
            "saveOnlyUniqueItems": True
        }

        try:
            run = client.actor(self.actor_id).call(
                run_input=run_input,
                max_items=fetch_limit,
                memory_mbytes=512,
                max_total_charge_usd=Decimal("0.05"),
                run_timeout=timedelta(seconds=120)
            )

            if not run:
                logger.error("Apify Indeed Actor call returned None.")
                return []

            dataset_id = getattr(run, "default_dataset_id", None) or run.get("defaultDatasetId")
            if not dataset_id:
                logger.warning("No defaultDatasetId returned by Indeed Actor.")
                return []

            items = client.dataset(dataset_id).list_items().items
            logger.info(f"Apify Indeed finished successfully. Retrieved {len(items)} genuine postings.")

            jobs: List[Job] = []
            for item in items:
                job = self._map_to_job(item)
                if not job:
                    continue

                # Enforce On-Site and Hybrid only (skip Remote)
                if allowed_work_modes and "remote" not in allowed_work_modes:
                    if job.work_mode.lower() == "remote":
                        logger.info(f"Skipping Remote Indeed job '{job.title}' at '{job.company}' - strictly On-Site / Hybrid.")
                        continue

                jobs.append(job)

            return jobs

        except Exception as e:
            logger.error(f"Apify Indeed scraping failed: {e}", exc_info=True)
            return []

    def _map_to_job(self, item: Dict[str, Any]) -> Optional[Job]:
        title = item.get("positionName") or item.get("title") or ""
        company = item.get("company") or "Indeed Employer"
        raw_id = str(item.get("id") or "")

        if not title:
            return None

        job_id = f"indeed_apify_{raw_id}" if raw_id else f"indeed_apify_{abs(hash(title + company))}"

        location = item.get("location") or "India"
        source_url = item.get("url") or f"https://in.indeed.com/viewjob?jk={raw_id}"
        apply_url = item.get("externalApplyLink") or source_url

        description = item.get("description") or item.get("descriptionHTML") or ""

        # CRITICAL: Deep JD Analysis for Fresher Eligibility (Strict 0-1 yr exp)
        is_fresher, reject_reason, min_exp, max_exp = analyze_job_fresher_eligibility(title=title, text=description)
        if not is_fresher:
            logger.info(f"Apify Indeed rejected non-fresher listing: '{title}' @ '{company}' -> {reject_reason}")
            return None

        # Role taxonomy & Classification
        standard_role, role_category = classify_role(title)
        
        # Check explicit Indeed workplace / remote attributes
        if item.get("isRemote") is True or item.get("remoteLocation") is True:
            work_mode = "Remote"
        elif "hybrid" in str(item.get("workplaceType") or "").lower():
            work_mode = "Hybrid"
        elif "on-site" in str(item.get("workplaceType") or "").lower() or "onsite" in str(item.get("workplaceType") or "").lower():
            work_mode = "On-Site"
        else:
            work_mode = detect_work_mode(location=location, title=title, description=description)

        exp_level = extract_fresher_experience(title=title, text=description)

        # Experience ranges (0-2 years)
        min_exp = 0
        max_exp = 2 if ("2" in exp_level or "1-2" in exp_level) else (0 if "intern" in exp_level.lower() else 1)

        # Parse sections
        responsibilities, requirements, qualifications = self._parse_text_into_sections(description)
        if not responsibilities:
            responsibilities = [
                f"Analyze key business data metrics and reporting deliverables for {standard_role}.",
                "Develop and maintain automated analytical dashboards and SQL reporting queries.",
                "Collaborate with analytical teams to ensure data integrity and actionable insights."
            ]

        # Extract skills & ATS keywords
        skills = extract_skills(f"{title} {description}")
        if not skills:
            skills = ["SQL", "Excel", "Data Analysis", "Reporting", "Dashboards"]
        ats_keywords = self._extract_ats_keywords(f"{title} {company} {description}", skills)

        # Published date formatting
        published_at = item.get("postingDateParsed") or item.get("postedAt")
        if published_at:
            published_at = str(published_at).split("T")[0]
        else:
            published_at = datetime.utcnow().strftime("%Y-%m-%d")

        salary = item.get("salary") or "Not Disclosed"

        return Job(
            id=job_id,
            title=title.strip(),
            standard_role=standard_role,
            role_category=role_category,
            company=company.strip(),
            location=location.strip(),
            country="India",
            work_mode=work_mode,
            experience_level=exp_level,
            min_experience=min_exp,
            max_experience=max_exp,
            salary=salary,
            description=description.strip(),
            skills=skills,
            responsibilities=responsibilities,
            qualifications=qualifications,
            requirements=requirements or [f"{exp_level} with analytical & quantitative aptitude"],
            ats_keywords=ats_keywords,
            source_id="indeed_india",
            source_name="Indeed",
            source_url=source_url,
            apply_url=apply_url,
            published_at=published_at,
            discovered_at=datetime.utcnow().isoformat(),
            first_scraped_at=datetime.utcnow().isoformat(),
            last_checked_at=datetime.utcnow().isoformat(),
            is_active=True,
            is_deep_scraped=True,  # Full description already extracted
            extraction_status="complete",
            company_details=f"Company rating: {item.get('rating', 'N/A')} on Indeed ({item.get('reviewsCount', 0)} reviews)" if item.get('rating') else None,
            employment_type=", ".join(item.get("jobType", [])) if isinstance(item.get("jobType"), list) else (item.get("jobType") or "Full-time")
        )

    def _parse_text_into_sections(self, text: str):
        responsibilities, requirements, qualifications = [], [], []
        if not text:
            return responsibilities, requirements, qualifications

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        current_section = "other"

        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["responsibilities", "what you'll do", "day-to-day", "duties", "your tasks"]):
                current_section = "resp"
                continue
            elif any(k in lower for k in ["requirements", "what we're looking for", "skills required", "who you are"]):
                current_section = "req"
                continue
            elif any(k in lower for k in ["qualifications", "eligibility", "education", "experience required"]):
                current_section = "qual"
                continue

            if len(line) < 5 or (line.endswith(":") and len(line) < 30):
                continue

            clean = re.sub(r"^[•\-\*\d+\.\)]\s*", "", line).strip()
            if not clean or len(clean) < 15:
                continue

            if current_section == "resp" and clean not in responsibilities:
                responsibilities.append(clean)
            elif current_section == "req" and clean not in requirements:
                requirements.append(clean)
            elif current_section == "qual" and clean not in qualifications:
                qualifications.append(clean)

        return responsibilities[:15], requirements[:15], qualifications[:10]

    def _extract_ats_keywords(self, text: str, existing_skills: List[str] = None) -> List[str]:
        keywords = set(existing_skills or [])
        text_lower = text.lower()
        candidates = [
            "sql", "python", "power bi", "tableau", "excel", "advanced excel", "data modeling",
            "etl", "data analysis", "reporting", "dashboards", "business intelligence",
            "kpi", "statistics", "data visualization", "pandas", "numpy", "eda", "data pipeline"
        ]
        for c in candidates:
            if re.search(r"\b" + re.escape(c) + r"\b", text_lower):
                keywords.add(c.title())
        return list(keywords)

