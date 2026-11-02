"""
Scraper Orchestration Engine.
Runs modular adapters concurrently, deduplicates results, and updates registry metrics.
"""

import concurrent.futures
import logging
import time
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any

from scraper.adapters.base import BaseAdapter
from scraper.adapters.remoteok import RemoteOKAdapter
from scraper.adapters.remotive import RemotiveAdapter
from scraper.adapters.jobicy import JobicyAdapter
from scraper.adapters.arbeitnow import ArbeitnowAdapter
from scraper.adapters.weworkremotely import WeWorkRemotelyAdapter
from scraper.adapters.company_boards import CompanyBoardsAdapter
from scraper.adapters.internshala import InternshalaAdapter
from scraper.adapters.real_market_seed import RealMarketSeedAdapter
from scraper.adapters.linkedin_recruiter import LinkedInRecruiterFeedAdapter
from scraper.adapters.apify_linkedin import ApifyLinkedInAdapter
from scraper.adapters.apify_indeed import ApifyIndeedAdapter
from scraper.adapters.apify_naukri import ApifyNaukriAdapter
from scraper.deep_scraper import deep_job_scraper
from scraper.taxonomy import analyze_job_fresher_eligibility
from scraper.database import Database
from scraper.models import Job, ScrapeRun
from scraper.registry import PlatformRegistry

logger = logging.getLogger(__name__)

class ScraperEngine:
    def __init__(self, db: Database = None, registry: PlatformRegistry = None):
        self.db = db or Database()
        self.registry = registry or PlatformRegistry()
        # Strictly align database sources with curated platforms list
        self.db.insert_or_update_platforms([p.model_dump() for p in self.registry.get_all()])

        # Registered active adapters for India and Global Remote open to India
        apify_li = ApifyLinkedInAdapter()
        apify_indeed = ApifyIndeedAdapter()
        apify_naukri = ApifyNaukriAdapter()

        self.adapters: Dict[str, BaseAdapter] = {
            "real_market_seed": RealMarketSeedAdapter(),
            "linkedin_india": apify_li,
            "apify_linkedin": apify_li,
            "indeed_india": apify_indeed,
            "apify_indeed": apify_indeed,
            "naukri": apify_naukri,
            "apify_naukri": apify_naukri,
            "linkedin_feed": LinkedInRecruiterFeedAdapter(),
            "internshala": InternshalaAdapter(),
            "remotive": RemotiveAdapter(),
            "remoteok": RemoteOKAdapter(),
            "jobicy": JobicyAdapter(),
            "weworkremotely": WeWorkRemotelyAdapter(),
            "company_careers": CompanyBoardsAdapter(),
        }

    def run_adapter(
        self,
        adapter: BaseAdapter,
        roles: List[str] = None,
        limit_per_source: int = 50,
        cities: List[str] = None,
        work_modes: List[str] = None,
        retry_count: int = 2,
        request_delay: float = 0.5
    ) -> List[Job]:
        attempts = 0
        max_attempts = max(1, retry_count + 1)
        last_error = None

        while attempts < max_attempts:
            try:
                attempts += 1
                logger.info(f"Running adapter: {adapter.platform_name} ({adapter.platform_id}), attempt {attempts}/{max_attempts}")
                if request_delay > 0 and attempts > 1:
                    time.sleep(request_delay * attempts)
                
                import inspect
                sig = inspect.signature(adapter.scrape)
                kwargs = {}
                if "cities" in sig.parameters:
                    kwargs["cities"] = cities
                if "work_modes" in sig.parameters:
                    kwargs["work_modes"] = work_modes

                jobs = adapter.scrape(
                    roles=roles,
                    limit=limit_per_source,
                    **kwargs
                )
                return jobs or []
            except Exception as e:
                last_error = e
                logger.warning(f"Adapter {adapter.platform_id} attempt {attempts} failed: {e}")
                if attempts < max_attempts:
                    time.sleep(request_delay * (attempts + 1))

        logger.error(f"Adapter {adapter.platform_id} failed after {max_attempts} attempts: {last_error}")
        raise last_error or Exception(f"Adapter {adapter.platform_id} returned no data")

    def run(
        self,
        adapter_ids: List[str] = None,
        roles: List[str] = None,
        limit_per_source: int = 50,
        cities: Optional[List[str]] = None,
        work_modes: Optional[List[str]] = None,
        max_workers: int = 4,
        smart_controls: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        run_id: Optional[str] = None,
        schedule_name: Optional[str] = None,
        trigger_source: str = "manual",
        triggered_by: str = "User (Manual)"
    ) -> ScrapeRun:
        """
        Executes scraping across all or selected adapters with real-time progress callbacks,
        priority city sequencing (Pune #1, Nagpur, Hyderabad, Aurangabad, Bengaluru),
        strict On-Site / Hybrid work mode filtering, priority sorting, retry logic, and smart controls.
        """
        run_id = run_id or str(uuid.uuid4())[:8]
        started_at = datetime.utcnow().isoformat()
        controls = smart_controls or {}

        # Location sequence priority & work mode constraints
        effective_cities = cities or controls.get("cities") or ["Pune", "Nagpur", "Hyderabad", "Aurangabad", "Bengaluru"]
        effective_work_modes = work_modes or controls.get("work_modes") or ["On-Site", "Hybrid"]

        retry_count = int(controls.get("retry_count", 2))
        request_delay = float(controls.get("request_delay", 0.5))
        update_existing = bool(controls.get("update_existing", True))
        auto_stop_on_error = bool(controls.get("auto_stop_on_error", False))
        portal_priority = controls.get("portal_priority") or []

        # Determine target adapters
        target_adapters: List[BaseAdapter] = []
        if adapter_ids:
            for aid in adapter_ids:
                if aid == "all":
                    target_adapters = list(self.adapters.values())
                    break
                elif aid in self.adapters:
                    target_adapters.append(self.adapters[aid])
        else:
            target_adapters = list(self.adapters.values())

        # Sort adapters by portal priority if specified
        if portal_priority:
            priority_map = {pid: idx for idx, pid in enumerate(portal_priority)}
            target_adapters.sort(key=lambda a: priority_map.get(a.platform_id, 999))

        run = ScrapeRun(
            run_id=run_id,
            started_at=started_at,
            status="running",
            platforms_scanned=[a.platform_id for a in target_adapters]
        )
        self.db.save_scrape_run(run)

        total_scanned = 0
        total_added = 0
        total_dups = 0
        errors: List[str] = []
        total_adapters = len(target_adapters)
        completed_adapters = 0

        if progress_callback:
            progress_callback({
                "status": "running",
                "run_id": run_id,
                "schedule_name": schedule_name or "Manual Run",
                "progress_percent": 5,
                "current_source_id": "init",
                "current_portal": "Initializing Scrapers",
                "stage": f"Starting scrape across {total_adapters} configured adapters...",
                "jobs_found": 0,
                "jobs_added": 0,
                "adapters_remaining": total_adapters
            })

        for idx, adapter in enumerate(target_adapters, 1):
            if progress_callback:
                progress_callback({
                    "status": "running",
                    "run_id": run_id,
                    "schedule_name": schedule_name or "Manual Run",
                    "progress_percent": int(5 + (idx - 1) / total_adapters * 75),
                    "current_source_id": adapter.platform_id,
                    "current_portal": adapter.platform_name,
                    "stage": f"Scraping portal {idx}/{total_adapters}: {adapter.platform_name}...",
                    "jobs_found": total_scanned,
                    "jobs_added": total_added,
                    "adapters_remaining": total_adapters - (idx - 1)
                })

            adapter_scanned = 0
            adapter_added = 0
            adapter_dups = 0

            try:
                scraped_jobs = self.run_adapter(
                    adapter,
                    roles=roles,
                    limit_per_source=limit_per_source,
                    cities=effective_cities,
                    work_modes=effective_work_modes,
                    retry_count=retry_count,
                    request_delay=request_delay
                )

                allowed_modes_lower = [m.lower() for m in effective_work_modes] if effective_work_modes else ["on-site", "hybrid"]

                for job in scraped_jobs:
                    total_scanned += 1

                    # 1. Strictly enforce Fresher Eligibility via deep JD & Title analysis (0-1 yr exp only)
                    is_fresher, reject_reason, min_e, max_e = analyze_job_fresher_eligibility(
                        title=job.title,
                        text=job.description,
                        raw_fields={"min_experience": job.min_experience, "max_experience": job.max_experience}
                    )
                    if not is_fresher:
                        logger.info(f"Engine gatekeeper filtered out non-fresher job '{job.title}' @ '{job.company}' -> {reject_reason}")
                        continue

                    # 2. Strictly enforce On-Site / Hybrid work mode (skip Remote / WFH)
                    if allowed_modes_lower and "remote" not in allowed_modes_lower:
                        if (job.work_mode or "").lower() == "remote":
                            logger.info(f"Engine filtered out Remote job '{job.title}' at '{job.company}' - strictly On-Site & Hybrid.")
                            continue

                    adapter_scanned += 1

                    # Data Validation & Deep Scraping Layer
                    if not job.is_deep_scraped and job.source_url and not job.source_url.startswith("#"):
                        try:
                            deep_res = deep_job_scraper.scrape_url(job.source_url, fallback_title=job.title, fallback_company=job.company)
                            if deep_res.get("success") and len(deep_res.get("description", "")) >= 250:
                                is_valid, reason = deep_job_scraper.validate_job_quality(deep_res)
                                new_desc = deep_res.get("description") or job.description
                                new_title = deep_res.get("title") or job.title
                                
                                # Re-verify fresher eligibility with the complete deep JD
                                is_still_fresher, deep_reject, _, _ = analyze_job_fresher_eligibility(
                                    title=new_title,
                                    text=new_desc
                                )
                                if not is_still_fresher:
                                    logger.info(f"Deep scraping revealed non-fresher requirements for '{new_title}' @ '{job.company}': {deep_reject}")
                                    continue

                                job.title = new_title
                                job.company = deep_res.get("company") or job.company
                                job.location = deep_res.get("location") or job.location
                                job.salary = deep_res.get("salary") or job.salary
                                job.experience_level = deep_res.get("experience_level") or job.experience_level
                                job.min_experience = deep_res.get("min_experience", job.min_experience)
                                job.max_experience = deep_res.get("max_experience", job.max_experience)
                                job.description = new_desc
                                job.skills = deep_res.get("skills") or job.skills
                                job.responsibilities = deep_res.get("responsibilities") or job.responsibilities
                                job.qualifications = deep_res.get("qualifications") or job.qualifications
                                job.requirements = deep_res.get("requirements") or job.requirements
                                job.ats_keywords = deep_res.get("ats_keywords") or job.ats_keywords
                                job.application_deadline = deep_res.get("application_deadline") or job.application_deadline
                                job.openings = deep_res.get("openings") or job.openings
                                job.company_details = deep_res.get("company_details") or job.company_details
                                job.is_deep_scraped = True
                                job.extraction_status = "complete" if is_valid else "incomplete_extraction"
                            else:
                                job.extraction_status = "incomplete_extraction"
                        except Exception as d_err:
                            logger.warning(f"Engine deep scrape error for {job.source_url}: {d_err}")
                            job.extraction_status = "incomplete_extraction"

                    is_new = self.db.save_job(job, update_existing=update_existing)
                    if is_new:
                        adapter_added += 1
                        total_added += 1
                    else:
                        adapter_dups += 1
                        total_dups += 1

                status_str = "success" if scraped_jobs else "zero_results"
                self.db.update_source_status(adapter.platform_id, status_str, adapter_added)
                completed_adapters += 1

            except Exception as e:
                err_msg = f"{adapter.platform_name} ({adapter.platform_id}): {str(e)}"
                errors.append(err_msg)
                logger.error(f"Error handling results from {adapter.platform_id}: {e}")
                self.db.update_source_status(adapter.platform_id, "error", 0)
                if auto_stop_on_error:
                    logger.warning("auto_stop_on_error is enabled. Halting further adapter execution.")
                    break

            if request_delay > 0:
                time.sleep(request_delay)

        run.finished_at = datetime.utcnow().isoformat()
        if not errors:
            run.status = "completed"
        elif completed_adapters > 0:
            run.status = "partially_completed"
        else:
            run.status = "failed"

        run.jobs_scanned = total_scanned
        run.jobs_added = total_added
        run.duplicates_skipped = total_dups
        run.errors_count = len(errors)
        run.error_messages = errors

        self.db.save_scrape_run(run)
        logger.info(f"Scrape run {run_id} complete. Added: {total_added}, Dups: {total_dups}, Scanned: {total_scanned}, Status: {run.status}")
        return run
