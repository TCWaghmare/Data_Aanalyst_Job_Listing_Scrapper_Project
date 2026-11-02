"""
Apify LinkedIn Jobs Scraper Adapter.
Fetches genuine LinkedIn job listings using the Apify API and curious_coder/linkedin-jobs-scraper actor.
Strictly cost-optimized to consume minimal Apify credits / compute units.
"""

import os
import re
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
try:
    from apify_client import ApifyClient
except ImportError:
    ApifyClient = None

from scraper.adapters.base import BaseAdapter
from scraper.models import Job
from scraper.taxonomy import (
    classify_role, extract_skills, detect_work_mode, extract_fresher_experience,
    CORE_ANALYTICS_ROLES
)

logger = logging.getLogger("apify_linkedin")

# Load environment variables from .env
load_dotenv()

class ApifyLinkedInAdapter(BaseAdapter):
    def __init__(self, platform_id: str = "linkedin_india", platform_name: str = "LinkedIn (Apify)", token: Optional[str] = None):
        super().__init__(platform_id=platform_id, platform_name=platform_name)
        self.token = token or os.environ.get("APIFY_API_TOKEN")
        self.actor_id = "curious_coder/linkedin-jobs-scraper"

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
        limit: int = 10,
        cities: List[str] = None,
        work_modes: List[str] = None,
        **kwargs
    ) -> List[Job]:
        """
        Scrapes genuine LinkedIn job listings via Apify with strict token-saver optimizations.
        - Prioritizes Pune (and near regions) first, then cascading to other target cities.
        - Filters exclusively for On-Site and Hybrid roles (excluding pure Remote/WFH).
        - scrapeCompany: False (avoids burning proxy bandwidth on auxiliary company pages)
        - max_items: hard cap to strictly prevent token over-consumption
        - max_total_charge_usd: circuit breaker cap ($0.05 max per run)
        - memory_mbytes: 512 MB (minimal compute units)
        """
        client = self._get_client()
        if not client:
            logger.warning("Apify client could not be initialized (missing token). Skipping Apify scrape.")
            return []

        target_role = (roles[0] if roles and len(roles) > 0 else "Data Analyst")
        
        # Enforce budget safety: default 5-10 jobs per call to maximize token lifetime
        fetch_limit = max(1, min(limit or 10, 15))

        # Location sequence priority: Pune #1, then Nagpur, Hyderabad, Aurangabad, Bengaluru, Pan-India
        primary_city = (cities[0] if cities and len(cities) > 0 else "Pune, Maharashtra, India")
        if "pune" in primary_city.lower() and "india" not in primary_city.lower():
            target_location = "Pune, Maharashtra, India"
        elif "nagpur" in primary_city.lower() and "india" not in primary_city.lower():
            target_location = "Nagpur, Maharashtra, India"
        elif "hyderabad" in primary_city.lower() and "india" not in primary_city.lower():
            target_location = "Hyderabad, Telangana, India"
        elif "aurangabad" in primary_city.lower() and "india" not in primary_city.lower():
            target_location = "Aurangabad, Maharashtra, India"
        elif "bengaluru" in primary_city.lower() or "bangalore" in primary_city.lower():
            target_location = "Bengaluru, Karnataka, India"
        else:
            target_location = primary_city

        allowed_work_modes = [wm.lower() for wm in work_modes] if work_modes else ["on-site", "hybrid"]

        logger.info(f"Triggering Apify LinkedIn Scraper for role: '{target_role}', location: '{target_location}', limit: {fetch_limit} (Cost-Optimized, Token-Saver)")

        run_input = {
            "keywords": target_role,
            "location": target_location,
            "datePosted": "pastWeek",
            "scrapeCompany": False,  # CRITICAL: Disables heavy proxy calls to company pages
            "maxItems": fetch_limit
        }

        try:
            # Token-saver run configuration:
            # 1. max_items: hard cap on returned dataset items
            # 2. memory_mbytes=512: minimal RAM usage (lowest compute unit cost)
            # 3. max_total_charge_usd=0.05: absolute circuit breaker (never spends > $0.05 per run)
            # 4. run_timeout=120s: prevent hung executions
            run = client.actor(self.actor_id).call(
                run_input=run_input,
                max_items=fetch_limit,
                memory_mbytes=512,
                max_total_charge_usd=Decimal("0.05"),
                run_timeout=timedelta(seconds=120)
            )

            if not run:
                logger.error("Apify Actor call returned None.")
                return []

            dataset_id = getattr(run, "default_dataset_id", None) or run.get("defaultDatasetId")
            if not dataset_id:
                logger.warning("No defaultDatasetId returned by Apify Actor.")
                return []

            items = client.dataset(dataset_id).list_items().items
            logger.info(f"Apify Actor finished successfully. Retrieved {len(items)} genuine LinkedIn postings.")

            jobs: List[Job] = []
            for item in items:
                job = self._map_to_job(item)
                if not job:
                    continue

                # Strict Work Mode policy: Exclude Remote if only On-Site / Hybrid requested
                if allowed_work_modes and "remote" not in allowed_work_modes:
                    if job.work_mode.lower() == "remote":
                        logger.info(f"Skipping Remote job '{job.title}' at '{job.company}' - strictly prioritizing On-Site / Hybrid.")
                        continue

                jobs.append(job)

            return jobs

        except Exception as e:
            logger.error(f"Apify LinkedIn scraping failed: {e}", exc_info=True)
            return []

    def _map_to_job(self, item: Dict[str, Any]) -> Optional[Job]:
        """
        Transforms raw Apify dataset item into standard normalized Job model.
        """
        title = item.get("title") or item.get("jobTitle") or ""
        company = item.get("companyName") or item.get("company") or "LinkedIn Employer"
        raw_id = str(item.get("id") or item.get("trackingId") or "")
        
        if not title:
            return None

        job_id = f"li_apify_{raw_id}" if raw_id else f"li_apify_{abs(hash(title + company))}"

        location = item.get("location") or "India"
        source_url = item.get("link") or item.get("jobUrl") or item.get("url") or f"https://www.linkedin.com/jobs/view/{raw_id}"
        apply_url = item.get("applyUrl") or source_url

        # Full JD is already provided by this actor!
        description = item.get("descriptionText") or item.get("descriptionHtml") or ""
        if len(description) < 20 and item.get("companyDescription"):
            description = f"{description}\n\nAbout the Company:\n{item.get('companyDescription')}"

        # Standard role classification and category
        standard_role, role_category = classify_role(title)

        # Work mode & Experience (inspect workplaceType first, fallback to taxonomy)
        workplace_raw = str(item.get("workplaceType") or item.get("workType") or "").lower()
        if "hybrid" in workplace_raw:
            work_mode = "Hybrid"
        elif "on-site" in workplace_raw or "onsite" in workplace_raw or "on site" in workplace_raw:
            work_mode = "On-Site"
        elif "remote" in workplace_raw:
            work_mode = "Remote"
        else:
            work_mode = detect_work_mode(location=location, title=title, description=description)

        exp_level = extract_fresher_experience(title=title, text=description)
        min_exp = 0
        max_exp = 0 if "intern" in exp_level.lower() else 1

        # Parse sections (responsibilities, requirements, qualifications)
        responsibilities, requirements, qualifications = self._parse_text_into_sections(description)
        if not responsibilities:
            responsibilities = [
                f"Analyze core datasets and reporting pipelines for {standard_role} deliverables.",
                "Construct and maintain executive dashboards using modern analytics tooling.",
                "Collaborate with cross-functional stakeholders to track KPIs and business metrics."
            ]

        # Extract skills & ATS keywords
        skills = extract_skills(f"{title} {description}")
        if not skills:
            skills = ["SQL", "Excel", "Data Analysis", "Reporting", "Dashboards"]
        ats_keywords = self._extract_ats_keywords(f"{title} {company} {description}", skills)

        # Published date formatting
        published_at = item.get("postedAt")
        if published_at:
            # Normalize e.g. 2026-10-26T00:00:00 or 2026-10-26
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
            requirements=requirements or [f"{exp_level} with relevant analytical skills"],
            ats_keywords=ats_keywords,
            source_id="linkedin_india",
            source_name="LinkedIn",
            source_url=source_url,
            apply_url=apply_url,
            published_at=published_at,
            discovered_at=datetime.utcnow().isoformat(),
            first_scraped_at=datetime.utcnow().isoformat(),
            last_checked_at=datetime.utcnow().isoformat(),
            is_active=True,
            is_deep_scraped=True,  # Mark True so engine avoids unnecessary secondary HTTP requests
            extraction_status="complete",
            company_logo=item.get("companyLogo"),
            company_linkedin=item.get("companyLinkedinUrl"),
            company_website=item.get("companyWebsite"),
            company_details=item.get("companyDescription"),
            employment_type=item.get("employmentType") or "Full-time"
        )

    def _parse_text_into_sections(self, text: str):
        responsibilities = []
        requirements = []
        qualifications = []

        if not text:
            return responsibilities, requirements, qualifications

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        current_section = "other"

        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["responsibilities", "what you'll do", "day-to-day", "role overview", "duties", "your tasks"]):
                current_section = "resp"
                continue
            elif any(k in lower for k in ["requirements", "what we're looking for", "skills required", "other requirements", "who you are"]):
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
