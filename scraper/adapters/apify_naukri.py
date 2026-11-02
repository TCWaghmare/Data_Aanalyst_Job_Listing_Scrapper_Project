"""
Apify Naukri Jobs Scraper Adapter.
Fetches genuine Naukri job listings (0-2 years experience) using the Apify API and valig/naukri-jobs-scraper actor.
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
    classify_role, extract_skills, detect_work_mode, extract_fresher_experience
)

logger = logging.getLogger("apify_naukri")

load_dotenv()

class ApifyNaukriAdapter(BaseAdapter):
    def __init__(self, platform_id: str = "naukri", platform_name: str = "Naukri (Apify)", token: Optional[str] = None):
        super().__init__(platform_id=platform_id, platform_name=platform_name)
        self.token = token or os.environ.get("APIFY_API_TOKEN")
        self.actor_id = "valig/naukri-jobs-scraper"

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
        Scrapes genuine Naukri fresher job listings via Apify with strict token-saver optimizations:
        - Prioritizes Pune (and near regions) first, then cascading to other target cities.
        - Filters exclusively for On-Site and Hybrid roles (skipping Remote).
        - experience: 0 (filters specifically for 0-2 years experience / freshers)
        - max_items: tight cap (3-5 items)
        - max_total_charge_usd: circuit breaker ($0.05 max per run)
        - memory_mbytes: 512 MB (minimal compute units)
        """
        client = self._get_client()
        if not client:
            logger.warning("Apify client could not be initialized (missing token). Skipping Naukri scrape.")
            return []

        target_role = (roles[0] if roles and len(roles) > 0 else "Data Analyst")
        fetch_limit = max(1, min(limit or 5, 10))

        # Location sequence priority: Pune #1, then Nagpur, Hyderabad, Aurangabad, Bengaluru, Pan-India
        primary_city = (cities[0] if cities and len(cities) > 0 else "Pune")
        if "pune" in primary_city.lower():
            target_location = "Pune"
        elif "nagpur" in primary_city.lower():
            target_location = "Nagpur"
        elif "hyderabad" in primary_city.lower():
            target_location = "Hyderabad"
        elif "aurangabad" in primary_city.lower():
            target_location = "Aurangabad"
        elif "bengaluru" in primary_city.lower() or "bangalore" in primary_city.lower():
            target_location = "Bangalore"
        else:
            target_location = primary_city

        allowed_work_modes = [wm.lower() for wm in work_modes] if work_modes else ["on-site", "hybrid"]

        logger.info(f"Triggering Apify Naukri Scraper for role: '{target_role}', location: '{target_location}', experience: 0-2 yrs, limit: {fetch_limit}")

        run_input = {
            "keywords": target_role,
            "location": target_location,
            "experience": 0,  # 0 indicates 0-2 years / freshers on Naukri
            "jobAge": "15",
            "limit": fetch_limit
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
                logger.error("Apify Naukri Actor call returned None.")
                return []

            dataset_id = getattr(run, "default_dataset_id", None) or run.get("defaultDatasetId")
            if not dataset_id:
                logger.warning("No defaultDatasetId returned by Naukri Actor.")
                return []

            items = client.dataset(dataset_id).list_items().items
            logger.info(f"Apify Naukri finished successfully. Retrieved {len(items)} genuine postings.")

            jobs: List[Job] = []
            for item in items:
                job = self._map_to_job(item)
                if not job:
                    continue

                # Strictly enforce On-Site / Hybrid
                if allowed_work_modes and "remote" not in allowed_work_modes:
                    if job.work_mode.lower() == "remote":
                        logger.info(f"Skipping Remote Naukri job '{job.title}' at '{job.company}' - strictly On-Site / Hybrid.")
                        continue

                jobs.append(job)

            return jobs

        except Exception as e:
            logger.error(f"Apify Naukri scraping failed: {e}", exc_info=True)
            return []

    def _map_to_job(self, item: Dict[str, Any]) -> Optional[Job]:
        title = item.get("title") or ""
        
        # Handle company object
        comp_obj = item.get("company")
        if isinstance(comp_obj, dict):
            company = comp_obj.get("name") or "Naukri Employer"
            company_logo = comp_obj.get("logoUrl")
            company_details = self._strip_html(comp_obj.get("description") or "")
            company_website = comp_obj.get("websiteUrl")
        else:
            company = str(comp_obj or "Naukri Employer")
            company_logo = None
            company_details = None
            company_website = None

        raw_id = str(item.get("id") or "")
        if not title:
            return None

        job_id = f"naukri_apify_{raw_id}" if raw_id else f"naukri_apify_{abs(hash(title + company))}"

        # Handle locations
        locations_list = item.get("locations") or []
        if isinstance(locations_list, list) and locations_list:
            location_names = [loc.get("label") for loc in locations_list if isinstance(loc, dict) and loc.get("label")]
            location = ", ".join(location_names) if location_names else "India"
        else:
            location = "India"

        source_url = item.get("url") or f"https://www.naukri.com/job-listings-{raw_id}"
        apply_url = source_url

        # Description
        desc_obj = item.get("description")
        if isinstance(desc_obj, dict):
            description = desc_obj.get("full") or desc_obj.get("short") or ""
        else:
            description = str(desc_obj or "")
        description = self._strip_html(description)

        # Experience
        exp_obj = item.get("experience")
        exp_text = exp_obj.get("text", "0-2 Yrs") if isinstance(exp_obj, dict) else str(exp_obj or "0-2 Yrs")
        exp_min = int(exp_obj.get("minimum", 0)) if isinstance(exp_obj, dict) and str(exp_obj.get("minimum", "")).isdigit() else 0
        exp_max = int(exp_obj.get("maximum", 2)) if isinstance(exp_obj, dict) and str(exp_obj.get("maximum", "")).isdigit() else 2

        # Role taxonomy & Classification
        standard_role, role_category = classify_role(title)
        
        # Check explicit Naukri workplace type or wfhType
        wfh_raw = str(item.get("wfhType") or item.get("workplaceType") or "").lower()
        if "hybrid" in wfh_raw:
            work_mode = "Hybrid"
        elif "remote" in wfh_raw or "wfh" in wfh_raw:
            work_mode = "Remote"
        elif "office" in wfh_raw or "on-site" in wfh_raw:
            work_mode = "On-Site"
        else:
            work_mode = detect_work_mode(location=location, title=title, description=description)

        exp_level = extract_fresher_experience(title=title, text=f"{exp_text} {description}")

        # Parse sections
        responsibilities, requirements, qualifications = self._parse_text_into_sections(description)
        if not responsibilities:
            responsibilities = [
                f"Extract, clean, and validate core analytics datasets for {standard_role}.",
                "Develop and maintain operational reporting dashboards in Power BI / Excel / Tableau.",
                "Perform exploratory analysis and communicate findings to cross-functional teams."
            ]

        # Extract skills
        skills_data = item.get("skills")
        extracted_skills = []
        if isinstance(skills_data, dict):
            extracted_skills.extend(skills_data.get("preferred") or [])
            extracted_skills.extend(skills_data.get("other") or [])
        elif isinstance(skills_data, list):
            for s in skills_data:
                if isinstance(s, dict):
                    extracted_skills.append(s.get("name") or s.get("label") or "")
                elif isinstance(s, str):
                    extracted_skills.append(s)

        # Merge with taxonomy skills
        tax_skills = extract_skills(f"{title} {description} {' '.join(extracted_skills)}")
        final_skills = sorted(list(set(extracted_skills + tax_skills)))
        if not final_skills:
            final_skills = ["SQL", "Excel", "Data Analysis", "Reporting", "Dashboards"]

        ats_keywords = self._extract_ats_keywords(f"{title} {company} {description} {' '.join(final_skills)}", final_skills)

        # Published date formatting
        created_text = item.get("createdDateText")
        if created_text:
            published_at = str(created_text).split(" ")[0]
        else:
            published_at = datetime.utcnow().strftime("%Y-%m-%d")

        # Salary
        sal_obj = item.get("salary")
        if isinstance(sal_obj, dict):
            salary = sal_obj.get("label") or f"₹{sal_obj.get('minimum', '')} - ₹{sal_obj.get('maximum', '')}"
        else:
            salary = str(sal_obj or "Not Disclosed")

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
            min_experience=exp_min,
            max_experience=exp_max,
            salary=salary,
            description=description.strip(),
            skills=final_skills,
            responsibilities=responsibilities,
            qualifications=qualifications,
            requirements=requirements or [f"{exp_text} experience with quantitative & analytical acumen"],
            ats_keywords=ats_keywords,
            source_id="naukri",
            source_name="Naukri",
            source_url=source_url,
            apply_url=apply_url,
            published_at=published_at,
            discovered_at=datetime.utcnow().isoformat(),
            first_scraped_at=datetime.utcnow().isoformat(),
            last_checked_at=datetime.utcnow().isoformat(),
            is_active=True,
            is_deep_scraped=True,
            extraction_status="complete",
            company_logo=company_logo,
            company_website=company_website,
            company_details=company_details,
            employment_type=item.get("employmentType") or "Full Time, Permanent"
        )

    def _strip_html(self, text: str) -> str:
        clean = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", clean).strip()

    def _parse_text_into_sections(self, text: str):
        responsibilities, requirements, qualifications = [], [], []
        if not text:
            return responsibilities, requirements, qualifications

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        current_section = "other"

        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["responsibilities", "what you'll do", "duties", "your tasks", "key tasks"]):
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
