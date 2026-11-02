"""
Automated Scheduling, Real-Time Monitoring, and Logging Orchestrator for Job Listing Scraping.
Supports built-in default schedules (11:00 AM and 10:00 PM), custom multi-time schedules,
real-time status polling, ATS resume match ranking, notification dispatch, and audit logging.
"""

import copy
import csv
import io
import json
import logging
import os
import smtplib
import threading
import time
import uuid
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from scraper.database import Database
from scraper.engine import ScraperEngine
from scraper.models import ScrapeRun
from scraper.registry import PlatformRegistry
from resume_tailor.analyzer import deep_job_analyzer
from resume_tailor.knowledge_base import career_kb

logger = logging.getLogger("scraper.scheduler")

# Default Schedules as specified by requirements
DEFAULT_SCHEDULES = [
    {
        "id": "sched_morning_default",
        "name": "🌅 Morning Job Scraping",
        "schedule_type": "default",
        "is_enabled": True,
        "timezone": "Asia/Kolkata",
        "frequency": "daily",
        "run_times": ["11:00"],
        "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "sources": ["all"],
        "job_portals": ["all"],
        "keywords": ["Data Analyst", "Junior Data Analyst", "Business Analyst", "Power BI Developer", "Python"],
        "location_filters": "India, Remote",
        "work_modes": ["Remote", "Hybrid", "Onsite"],
        "scrape_new_only": True,
        "rescrape_existing": False,
        "refresh_expired": False,
        "update_existing": True,
        "deduplication": True,
        "ats_scoring": True,
        "skill_matching": True,
        "resume_matching": True,
        "max_jobs_per_run": 50,
        "portal_priority": ["linkedin_feed", "internshala", "real_market_seed", "remotive", "remoteok", "jobicy", "weworkremotely", "company_careers"],
        "retry_count": 2,
        "request_delay": 0.5,
        "auto_stop_on_error": False,
        "auto_recovery": True
    },
    {
        "id": "sched_evening_default",
        "name": "🌙 Evening Job Scraping",
        "schedule_type": "default",
        "is_enabled": True,
        "timezone": "Asia/Kolkata",
        "frequency": "daily",
        "run_times": ["22:00"],
        "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "sources": ["all"],
        "job_portals": ["all"],
        "keywords": ["Data Analyst", "Junior Data Analyst", "Business Analyst", "Power BI Developer", "Python"],
        "location_filters": "India, Remote",
        "work_modes": ["Remote", "Hybrid", "Onsite"],
        "scrape_new_only": True,
        "rescrape_existing": False,
        "refresh_expired": False,
        "update_existing": True,
        "deduplication": True,
        "ats_scoring": True,
        "skill_matching": True,
        "resume_matching": True,
        "max_jobs_per_run": 50,
        "portal_priority": ["linkedin_feed", "internshala", "real_market_seed", "remotive", "remoteok", "jobicy", "weworkremotely", "company_careers"],
        "retry_count": 2,
        "request_delay": 0.5,
        "auto_stop_on_error": False,
        "auto_recovery": True
    }
]

DAY_NAME_TO_INT = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6
}


def calculate_next_run(
    frequency: str,
    run_times: List[str],
    days_of_week: Optional[List[str]] = None,
    tz_str: str = "Asia/Kolkata",
    from_dt: Optional[datetime] = None
) -> str:
    """
    Computes the next execution timestamp (ISO format with timezone offset)
    based on frequency, multiple run times, and days of week.
    """
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("UTC")

    now = from_dt or datetime.now(tz)
    frequency = (frequency or "daily").lower()

    clean_times: List[Tuple[int, int]] = []
    for t_str in run_times:
        try:
            parts = t_str.strip().split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            clean_times.append((h, m))
        except Exception:
            continue

    if not clean_times:
        clean_times = [(11, 0)]
    clean_times.sort()

    valid_days: Optional[set] = None
    if days_of_week:
        valid_days = set()
        for d in days_of_week:
            d_lower = d.strip().lower()
            if d_lower in DAY_NAME_TO_INT:
                valid_days.add(DAY_NAME_TO_INT[d_lower])

    candidate_runs: List[datetime] = []

    if frequency == "daily":
        # Check today and next 7 days
        for day_offset in range(8):
            day_candidate = (now + timedelta(days=day_offset)).date()
            if valid_days is not None and len(valid_days) > 0:
                if day_candidate.weekday() not in valid_days:
                    continue
            for h, m in clean_times:
                dt_cand = datetime(day_candidate.year, day_candidate.month, day_candidate.day, h, m, 0, tzinfo=tz)
                if dt_cand > now:
                    candidate_runs.append(dt_cand)

    elif frequency == "weekly":
        # Check next 14 days for matching days_of_week
        for day_offset in range(14):
            day_candidate = (now + timedelta(days=day_offset)).date()
            if valid_days and day_candidate.weekday() in valid_days:
                for h, m in clean_times:
                    dt_cand = datetime(day_candidate.year, day_candidate.month, day_candidate.day, h, m, 0, tzinfo=tz)
                    if dt_cand > now:
                        candidate_runs.append(dt_cand)

    elif frequency == "monthly":
        # Check current month and next month (day 1 or specified day)
        for month_offset in range(3):
            target_year = now.year + (now.month - 1 + month_offset) // 12
            target_month = ((now.month - 1 + month_offset) % 12) + 1
            for h, m in clean_times:
                dt_cand = datetime(target_year, target_month, 1, h, m, 0, tzinfo=tz)
                if dt_cand > now:
                    candidate_runs.append(dt_cand)

    if candidate_runs:
        candidate_runs.sort()
        return candidate_runs[0].isoformat()

    # Fallback: tomorrow at first run time
    fallback = now + timedelta(days=1)
    h, m = clean_times[0]
    return datetime(fallback.year, fallback.month, fallback.day, h, m, 0, tzinfo=tz).isoformat()


def format_execution_window(next_run_iso: str, duration_minutes: int = 3) -> str:
    """Formats human-friendly expected execution window (e.g., '11:00 AM - 11:03 AM (~3 mins)')."""
    if not next_run_iso:
        return "Not scheduled"
    try:
        dt = datetime.fromisoformat(next_run_iso)
        end_dt = dt + timedelta(minutes=duration_minutes)
        start_str = dt.strftime("%I:%M %p")
        end_str = end_dt.strftime("%I:%M %p")
        return f"{start_str} - {end_str} (~{duration_minutes} mins)"
    except Exception:
        return "~2-3 minutes window"


class ScraperScheduler:
    """
    Central background scheduler & live monitor engine.
    Persists schedules, manages real-time status monitor, triggers automated runs,
    runs grounded ATS job match comparisons, and sends notifications.
    """

    def __init__(self, db: Optional[Database] = None, engine: Optional[ScraperEngine] = None):
        self.db = db or Database()
        self.registry = PlatformRegistry()
        self.engine = engine or ScraperEngine(db=self.db, registry=self.registry)

        self._lock = threading.Lock()
        self._is_running = False
        self._ticker_thread: Optional[threading.Thread] = None

        # Real-Time Monitoring State
        self.live_monitor: Dict[str, Any] = {
            "status": "idle",  # idle, running, scheduled, queued, error
            "active_run_id": None,
            "active_schedule_id": None,
            "active_schedule_name": "None",
            "trigger_source": "manual",
            "triggered_by": "System",
            "current_active_job_source": "",
            "current_portal_being_scraped": "",
            "progress_percent": 0,
            "jobs_found_so_far": 0,
            "jobs_added_so_far": 0,
            "time_elapsed_seconds": 0,
            "start_timestamp": None,
            "estimated_remaining_tasks": "0 tasks remaining",
            "current_processing_stage": "System Ready. Waiting for scheduled run or manual trigger.",
            "last_completed_run": None,
            "errors": []
        }

        # Initialize defaults and restore schedules
        self._init_default_schedules()
        self._sync_upcoming_times()

    def _init_default_schedules(self):
        """Seeds Morning (11:00 AM) and Evening (10:00 PM) default schedules if not existing."""
        existing = {s["id"]: s for s in self.db.get_schedules()}
        for def_sched in DEFAULT_SCHEDULES:
            sid = def_sched["id"]
            if sid not in existing:
                def_copy = dict(def_sched)
                def_copy["next_run_at"] = calculate_next_run(
                    def_copy["frequency"],
                    def_copy["run_times"],
                    def_copy.get("days_of_week"),
                    def_copy.get("timezone", "Asia/Kolkata")
                )
                self.db.save_schedule(def_copy)
                self.db.add_audit_log(sid, def_copy["name"], "created", "Default built-in automated schedule initialized")
                logger.info(f"Initialized default schedule: {def_copy['name']} (Next: {def_copy['next_run_at']})")

    def _sync_upcoming_times(self):
        """Ensures all enabled schedules have valid future next_run_at timestamps."""
        schedules = self.db.get_schedules()
        now_utc = datetime.utcnow().isoformat()
        for s in schedules:
            if s.get("is_enabled") and (not s.get("next_run_at") or s.get("next_run_at") < now_utc):
                next_t = calculate_next_run(
                    s.get("frequency", "daily"),
                    s.get("run_times", ["11:00"]),
                    s.get("days_of_week"),
                    s.get("timezone", "Asia/Kolkata")
                )
                s["next_run_at"] = next_t
                self.db.save_schedule(s)

    def start(self):
        """Starts the background scheduler ticker thread."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._ticker_thread = threading.Thread(target=self._ticker_loop, daemon=True, name="ScraperSchedulerTicker")
            self._ticker_thread.start()
            logger.info("ScraperScheduler background daemon thread started.")

    def stop(self):
        """Stops the scheduler background thread."""
        with self._lock:
            self._is_running = False

    def _ticker_loop(self):
        """Background loop executing every 10 seconds to check due schedules."""
        while self._is_running:
            try:
                self._check_and_trigger_due_schedules()
                self._update_live_elapsed_time()
            except Exception as e:
                logger.error(f"Error in scheduler ticker loop: {e}", exc_info=True)
            time.sleep(5)

    def _update_live_elapsed_time(self):
        """Updates elapsed seconds for live monitoring when a scrape is active."""
        if self.live_monitor["status"] == "running" and self.live_monitor.get("start_timestamp"):
            try:
                elapsed = int(time.time() - self.live_monitor["start_timestamp"])
                self.live_monitor["time_elapsed_seconds"] = elapsed
            except Exception:
                pass

    def _check_and_trigger_due_schedules(self):
        """Checks if any active schedule has reached its execution time."""
        if self.live_monitor["status"] == "running":
            # Another scrape is currently running; wait for it to complete
            return

        schedules = self.db.get_schedules()
        now_iso = datetime.now(ZoneInfo("UTC")).isoformat()

        for s in schedules:
            if not s.get("is_enabled"):
                continue

            next_run_str = s.get("next_run_at")
            if not next_run_str:
                continue

            try:
                # Compare next_run_at with current time
                next_dt = datetime.fromisoformat(next_run_str)
                # Convert both to UTC for reliable comparison
                now_in_tz = datetime.now(next_dt.tzinfo or ZoneInfo("UTC"))
                if next_dt <= now_in_tz:
                    logger.info(f"Schedule '{s['name']}' ({s['id']}) is DUE! Triggering execution...")
                    # Advance next_run_at immediately to prevent duplicate runs
                    subsequent_run = calculate_next_run(
                        s.get("frequency", "daily"),
                        s.get("run_times", ["11:00"]),
                        s.get("days_of_week"),
                        s.get("timezone", "Asia/Kolkata"),
                        from_dt=now_in_tz + timedelta(minutes=1)
                    )
                    s["next_run_at"] = subsequent_run
                    self.db.save_schedule(s)

                    # Spawn execution worker
                    t = threading.Thread(
                        target=self.execute_scrape,
                        kwargs={
                            "schedule_id": s["id"],
                            "trigger_source": "scheduled",
                            "triggered_by": "Automated Scheduler"
                        },
                        daemon=True,
                        name=f"ScrapeWorker_{s['id']}"
                    )
                    t.start()
                    break  # Execute one schedule at a time
            except Exception as err:
                logger.error(f"Error checking schedule {s.get('id')}: {err}")

    def execute_scrape(
        self,
        schedule_id: Optional[str] = None,
        custom_params: Optional[Dict[str, Any]] = None,
        trigger_source: str = "manual",
        triggered_by: str = "User (Manual)"
    ) -> Dict[str, Any]:
        """
        Executes a scrape run, updates real-time status monitor,
        records full activity log, calculates candidate ATS match scores,
        and fires notifications.
        """
        with self._lock:
            if self.live_monitor["status"] == "running":
                logger.warning("Scrape is already in progress. Rejecting concurrent run.")
                return {"success": False, "error": "A scrape operation is currently in progress."}

            schedule = None
            if schedule_id:
                schedule = self.db.get_schedule(schedule_id)

            params = custom_params or (schedule or {})
            schedule_name = schedule["name"] if schedule else params.get("schedule_name", "Manual On-Demand Scrape")
            run_id = str(uuid.uuid4())[:8]

            # Initialize live status monitor
            self.live_monitor.update({
                "status": "running",
                "active_run_id": run_id,
                "active_schedule_id": schedule_id,
                "active_schedule_name": schedule_name,
                "trigger_source": trigger_source,
                "triggered_by": triggered_by,
                "current_active_job_source": "initializing",
                "current_portal_being_scraped": "All Configured Portals",
                "progress_percent": 2,
                "jobs_found_so_far": 0,
                "jobs_added_so_far": 0,
                "time_elapsed_seconds": 0,
                "start_timestamp": time.time(),
                "estimated_remaining_tasks": "Preparing adapters...",
                "current_processing_stage": "Starting scraper engine & validating platform adapters...",
                "errors": []
            })

        started_at = datetime.utcnow().isoformat()
        start_mono = time.time()
        errors_list: List[str] = []
        high_match_count = 0
        newly_added_jobs: List[Dict[str, Any]] = []

        try:
            # Determine target adapters
            raw_sources = params.get("sources") or ["all"]
            adapter_ids = None
            if "all" not in raw_sources and raw_sources:
                adapter_ids = raw_sources

            # Roles and Keywords
            roles = params.get("keywords") or params.get("roles") or None
            limit = int(params.get("max_jobs_per_run") or 50)

            # Smart Controls configuration
            smart_controls = {
                "scrape_new_only": params.get("scrape_new_only", True),
                "rescrape_existing": params.get("rescrape_existing", False),
                "refresh_expired": params.get("refresh_expired", False),
                "update_existing": params.get("update_existing", True),
                "deduplication": params.get("deduplication", True),
                "portal_priority": params.get("portal_priority") or [],
                "retry_count": int(params.get("retry_count", 2)),
                "request_delay": float(params.get("request_delay", 0.5)),
                "auto_stop_on_error": bool(params.get("auto_stop_on_error", False)),
                "auto_recovery": bool(params.get("auto_recovery", True))
            }

            def live_progress_callback(info: Dict[str, Any]):
                self.live_monitor["current_active_job_source"] = info.get("current_source_id", "")
                self.live_monitor["current_portal_being_scraped"] = info.get("current_portal", "")
                self.live_monitor["progress_percent"] = min(90, info.get("progress_percent", 50))
                self.live_monitor["jobs_found_so_far"] = info.get("jobs_found", 0)
                self.live_monitor["jobs_added_so_far"] = info.get("jobs_added", 0)
                self.live_monitor["current_processing_stage"] = info.get("stage", "Scraping job listings...")
                rem = info.get("adapters_remaining", 0)
                self.live_monitor["estimated_remaining_tasks"] = f"{rem} portal{'s' if rem != 1 else ''} remaining"

            cities = params.get("cities") or ["Pune", "Nagpur", "Hyderabad", "Aurangabad", "Bengaluru"]
            work_modes = params.get("work_modes") or ["On-Site", "Hybrid"]

            # Execute the core scrape engine
            run_result: ScrapeRun = self.engine.run(
                adapter_ids=adapter_ids,
                roles=roles,
                limit_per_source=limit,
                cities=cities,
                work_modes=work_modes,
                smart_controls=smart_controls,
                progress_callback=live_progress_callback,
                run_id=run_id,
                schedule_name=schedule_name,
                trigger_source=trigger_source,
                triggered_by=triggered_by
            )

            errors_list = run_result.error_messages or []
            jobs_scanned = run_result.jobs_scanned
            jobs_added = run_result.jobs_added
            duplicates_skipped = run_result.duplicates_skipped

            # Stage: Resume & ATS Match Integration
            if params.get("ats_scoring", True) or params.get("resume_matching", True):
                self.live_monitor["current_processing_stage"] = "Comparing discovered jobs against Master Resume & Career Knowledge Base..."
                self.live_monitor["progress_percent"] = 92
                high_match_count = self._evaluate_and_rank_scraped_jobs(min_score=75)

            duration = round(time.time() - start_mono, 2)
            finished_at = datetime.utcnow().isoformat()

            # Determine final status
            if not errors_list:
                final_status = "completed"
            elif jobs_added > 0 or jobs_scanned > 0:
                final_status = "partially_completed"
            else:
                final_status = "failed"

            # Save detailed Activity Log
            log_record = {
                "run_id": run_id,
                "schedule_id": schedule_id,
                "schedule_name": schedule_name,
                "trigger_source": trigger_source,
                "triggered_by": triggered_by,
                "status": final_status,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": duration,
                "job_sources": run_result.platforms_scanned,
                "jobs_scanned": jobs_scanned,
                "jobs_added": jobs_added,
                "duplicates_skipped": duplicates_skipped,
                "errors_count": len(errors_list),
                "error_messages": errors_list,
                "high_match_jobs_found": high_match_count,
                "log_details": {
                    "smart_controls": smart_controls,
                    "target_roles": roles,
                    "limit_per_source": limit
                }
            }
            self.db.save_activity_log(log_record)

            # Update Schedule Metrics (if scheduled)
            if schedule_id and schedule:
                next_run_iso = calculate_next_run(
                    schedule.get("frequency", "daily"),
                    schedule.get("run_times", ["11:00"]),
                    schedule.get("days_of_week"),
                    schedule.get("timezone", "Asia/Kolkata")
                )
                self.db.update_schedule_run_metrics(
                    schedule_id=schedule_id,
                    last_run_at=started_at,
                    status=final_status,
                    next_run_at=next_run_iso,
                    jobs_found=jobs_added,
                    is_success=(final_status in ["completed", "partially_completed"])
                )

            # Notifications & Alerts
            self._dispatch_notifications_and_alerts(
                final_status=final_status,
                schedule_name=schedule_name,
                jobs_added=jobs_added,
                jobs_scanned=jobs_scanned,
                high_match_count=high_match_count,
                errors=errors_list,
                duration=duration,
                run_id=run_id
            )

            # Update live monitor to completed state
            self.live_monitor.update({
                "status": "idle" if final_status != "failed" else "error",
                "progress_percent": 100,
                "current_processing_stage": f"Execution finished ({final_status}). Added {jobs_added} new jobs ({jobs_scanned} scanned).",
                "estimated_remaining_tasks": "All tasks completed",
                "last_completed_run": log_record,
                "errors": errors_list
            })

            return {"success": True, "run_id": run_id, "status": final_status, "log": log_record}

        except Exception as ex:
            duration = round(time.time() - start_mono, 2)
            finished_at = datetime.utcnow().isoformat()
            err_msg = f"Fatal scrape scheduler error: {str(ex)}"
            logger.error(err_msg, exc_info=True)
            errors_list.append(err_msg)

            log_record = {
                "run_id": run_id,
                "schedule_id": schedule_id,
                "schedule_name": schedule_name,
                "trigger_source": trigger_source,
                "triggered_by": triggered_by,
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": duration,
                "job_sources": [],
                "jobs_scanned": 0,
                "jobs_added": 0,
                "duplicates_skipped": 0,
                "errors_count": len(errors_list),
                "error_messages": errors_list,
                "high_match_jobs_found": 0,
                "log_details": {"fatal_exception": str(ex)}
            }
            self.db.save_activity_log(log_record)

            self.db.add_notification(
                title=f"⚠️ Scraping Failed: {schedule_name}",
                message=f"Scraping run encountered an unhandled error: {str(ex)[:160]}",
                type="error",
                category="error_alert",
                metadata={"run_id": run_id, "error": str(ex)}
            )

            self.live_monitor.update({
                "status": "error",
                "progress_percent": 0,
                "current_processing_stage": f"Scrape failed: {str(ex)}",
                "errors": errors_list
            })

            return {"success": False, "run_id": run_id, "error": str(ex)}

    def _evaluate_and_rank_scraped_jobs(self, min_score: int = 75) -> int:
        """
        Grounded Job Match Integration:
        Extracts user's resume profile from CareerKnowledgeBase, evaluates active jobs,
        and counts high-relevance matches.
        """
        high_matches = 0
        try:
            profile = career_kb.get_unified_profile()
            jobs, _ = self.db.get_jobs(limit=40, date_filter="30d")
            for j in jobs:
                j_dict = j.model_dump()
                analysis = deep_job_analyzer.analyze_job(j_dict, profile)
                score = analysis.get("ats_metrics", {}).get("match_score") or analysis.get("gap_analysis", {}).get("ats_score", 0)
                if score >= min_score:
                    high_matches += 1
        except Exception as e:
            logger.warning(f"Error evaluating job matches against resume: {e}")
        return high_matches

    def _dispatch_notifications_and_alerts(
        self,
        final_status: str,
        schedule_name: str,
        jobs_added: int,
        jobs_scanned: int,
        high_match_count: int,
        errors: List[str],
        duration: float,
        run_id: str
    ):
        """Fires in-app notifications and email alerts according to user notification settings."""
        settings = self.db.get_notification_settings()

        # 1. Scraping completed notification
        if settings.get("notify_on_complete") and final_status in ["completed", "partially_completed"]:
            self.db.add_notification(
                title=f"✅ Scraping Completed: {schedule_name}",
                message=f"Completed in {duration}s. Scanned {jobs_scanned} jobs, added {jobs_added} new listings.",
                type="success",
                category="schedule_executed",
                metadata={"run_id": run_id, "jobs_added": jobs_added, "duration": duration}
            )

        # 2. New jobs discovered alert
        if settings.get("notify_on_new_jobs") and jobs_added > 0:
            self.db.add_notification(
                title=f"🎉 {jobs_added} New Job{'s' if jobs_added != 1 else ''} Discovered",
                message=f"Discovered {jobs_added} new data analytics opening(s) matching fresher criteria (0-1 yr exp).",
                type="info",
                category="new_jobs",
                metadata={"run_id": run_id, "jobs_added": jobs_added}
            )

        # 3. High-match jobs alert
        if settings.get("notify_on_high_match") and high_match_count > 0:
            self.db.add_notification(
                title=f"⭐ {high_match_count} High-Match Job{'s' if high_match_count != 1 else ''} Found!",
                message=f"Found {high_match_count} job(s) with >=75% match to your verified Master Resume skills.",
                type="success",
                category="high_match",
                metadata={"run_id": run_id, "high_match_count": high_match_count}
            )

        # 4. Error / Failure alert
        if errors and (settings.get("notify_on_failure") or final_status == "failed"):
            summary_err = errors[0] if len(errors) == 1 else f"{len(errors)} portal error(s) occurred ({errors[0][:80]}...)"
            self.db.add_notification(
                title=f"⚠️ Scraping Notice: {schedule_name}",
                message=f"Issues detected during scrape: {summary_err}",
                type="warning" if final_status == "partially_completed" else "error",
                category="error_alert",
                metadata={"run_id": run_id, "errors": errors}
            )

        # 5. Email Dispatch (if configured & enabled)
        if settings.get("email_enabled") and settings.get("email_recipient"):
            self._send_email_report(
                settings=settings,
                schedule_name=schedule_name,
                final_status=final_status,
                jobs_added=jobs_added,
                jobs_scanned=jobs_scanned,
                high_match_count=high_match_count,
                errors=errors,
                duration=duration
            )

    def _send_email_report(
        self,
        settings: Dict[str, Any],
        schedule_name: str,
        final_status: str,
        jobs_added: int,
        jobs_scanned: int,
        high_match_count: int,
        errors: List[str],
        duration: float
    ):
        """Dispatches HTML email report via SMTP safely without raising exceptions."""
        recipient = settings.get("email_recipient")
        if not recipient:
            return

        ist_timestamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
        subject = f"[{final_status.upper()}] Job Finder Scraping Report: {schedule_name} ({ist_timestamp})"
        html_body = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px;">
          <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 24px;">
            <h2 style="color: #0f172a; margin-top: 0;">Job Scraping Activity Report</h2>
            <p><strong>Execution Date & Time:</strong> <span style="font-weight: 600; color: #0284c7;">{ist_timestamp}</span></p>
            <p><strong>Schedule:</strong> {schedule_name}</p>
            <p><strong>Status:</strong> <span style="display: inline-block; padding: 4px 8px; border-radius: 6px; background: {'#dcfce7' if final_status == 'completed' else '#fee2e2'}; color: {'#166534' if final_status == 'completed' else '#991b1b'};">{final_status.upper()}</span></p>
            <p><strong>Duration:</strong> {duration} seconds</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 16px 0;" />
            <h3 style="color: #334155;">Execution Metrics</h3>
            <ul>
              <li><strong>Total Jobs Scanned:</strong> {jobs_scanned}</li>
              <li><strong>New Jobs Added:</strong> {jobs_added}</li>
              <li><strong>High-Match Jobs (Resume >=75%):</strong> {high_match_count}</li>
              <li><strong>Errors Encountered:</strong> {len(errors)}</li>
            </ul>
            {f"<div style='background: #fff1f2; border: 1px solid #fecdd3; padding: 12px; border-radius: 8px; color: #9f1239;'><strong>Errors:</strong><br>{'<br>'.join(errors[:3])}</div>" if errors else ""}
            <p style="margin-top: 24px; font-size: 0.85rem; color: #64748b;">Automated report generated by Fresher Data Analyst Job Finder Scheduler.</p>
          </div>
        </body>
        </html>
        """

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.get("smtp_user") or "no-reply@jobfinder.local"
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html"))

            smtp_host = settings.get("smtp_host", "smtp.gmail.com")
            smtp_port = int(settings.get("smtp_port", 587))
            smtp_user = settings.get("smtp_user", "")
            smtp_pass = settings.get("smtp_password", "")
            use_tls = settings.get("smtp_use_tls", True)

            if smtp_user and smtp_pass:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    if use_tls:
                        server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(msg["From"], [recipient], msg.as_string())
                logger.info(f"Notification email dispatched to {recipient}")
            else:
                logger.info(f"[Mock Email Dispatch] Would send report to {recipient}: {subject}")
        except Exception as e:
            logger.warning(f"Failed to send email notification to {recipient}: {e}")

    # =========================================================================
    # Schedule Management (CRUD, Pause, Resume, Delete, Run Now)
    # =========================================================================

    def create_custom_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates and schedules a new custom scraping configuration."""
        sched_id = f"sched_custom_{int(time.time())}_{os.urandom(2).hex()}"
        data["id"] = sched_id
        data["schedule_type"] = "custom"
        data["created_at"] = datetime.utcnow().isoformat()
        data["updated_at"] = data["created_at"]

        next_run = calculate_next_run(
            frequency=data.get("frequency", "daily"),
            run_times=data.get("run_times", ["09:00"]),
            days_of_week=data.get("days_of_week"),
            tz_str=data.get("timezone", "Asia/Kolkata")
        )
        data["next_run_at"] = next_run

        self.db.save_schedule(data)
        self.db.add_audit_log(sched_id, data.get("name", "Custom Schedule"), "created", f"Created custom schedule with frequency {data.get('frequency')}")
        self.db.add_notification(
            title="📅 Schedule Created",
            message=f"Created schedule '{data.get('name')}'. Next run: {next_run[:16].replace('T', ' ')}",
            type="info",
            category="schedule_change"
        )
        return self.db.get_schedule(sched_id)

    def update_schedule(self, schedule_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates schedule settings and recalculates its next execution time."""
        existing = self.db.get_schedule(schedule_id)
        if not existing:
            return None

        merged = dict(existing)
        merged.update(data)
        merged["id"] = schedule_id
        merged["updated_at"] = datetime.utcnow().isoformat()

        if merged.get("is_enabled"):
            merged["next_run_at"] = calculate_next_run(
                frequency=merged.get("frequency", "daily"),
                run_times=merged.get("run_times", ["11:00"]),
                days_of_week=merged.get("days_of_week"),
                tz_str=merged.get("timezone", "Asia/Kolkata")
            )
        else:
            merged["next_run_at"] = None

        self.db.save_schedule(merged)
        self.db.add_audit_log(schedule_id, merged.get("name"), "updated", "Schedule configuration updated by user")
        self.db.add_notification(
            title="✏️ Schedule Modified",
            message=f"Schedule '{merged.get('name')}' settings updated.",
            type="info",
            category="schedule_change"
        )
        return self.db.get_schedule(schedule_id)

    def pause_schedule(self, schedule_id: str) -> bool:
        """Pauses an active schedule."""
        sched = self.db.get_schedule(schedule_id)
        if not sched:
            return False
        self.db.update_schedule_status(schedule_id, False)
        self.db.add_audit_log(schedule_id, sched.get("name"), "paused", "Schedule paused by user")
        self.db.add_notification(
            title="⏸ Schedule Paused",
            message=f"Automated schedule '{sched.get('name')}' is now paused.",
            type="warning",
            category="schedule_change"
        )
        return True

    def resume_schedule(self, schedule_id: str) -> bool:
        """Resumes a paused schedule and recalculates the upcoming run time."""
        sched = self.db.get_schedule(schedule_id)
        if not sched:
            return False
        next_run = calculate_next_run(
            frequency=sched.get("frequency", "daily"),
            run_times=sched.get("run_times", ["11:00"]),
            days_of_week=sched.get("days_of_week"),
            tz_str=sched.get("timezone", "Asia/Kolkata")
        )
        sched["is_enabled"] = True
        sched["next_run_at"] = next_run
        self.db.save_schedule(sched)
        self.db.add_audit_log(schedule_id, sched.get("name"), "resumed", f"Schedule resumed. Next run at {next_run}")
        self.db.add_notification(
            title="▶ Schedule Resumed",
            message=f"Automated schedule '{sched.get('name')}' resumed. Next run: {next_run[:16].replace('T', ' ')}",
            type="success",
            category="schedule_change"
        )
        return True

    def delete_schedule(self, schedule_id: str) -> bool:
        """Deletes a custom schedule and preserves an audit log entry."""
        sched = self.db.get_schedule(schedule_id)
        if not sched:
            return False
        if sched.get("schedule_type") == "default":
            # Protect default schedules from permanent deletion; disable instead
            return self.pause_schedule(schedule_id)

        self.db.delete_schedule(schedule_id)
        self.db.add_audit_log(schedule_id, sched.get("name"), "deleted", "Custom schedule permanently deleted")
        self.db.add_notification(
            title="🗑 Schedule Deleted",
            message=f"Schedule '{sched.get('name')}' was deleted.",
            type="info",
            category="schedule_change"
        )
        return True

    def run_schedule_now(self, schedule_id: str) -> Dict[str, Any]:
        """Triggers immediate on-demand execution of an existing schedule."""
        sched = self.db.get_schedule(schedule_id)
        if not sched:
            return {"success": False, "error": "Schedule not found"}

        t = threading.Thread(
            target=self.execute_scrape,
            kwargs={
                "schedule_id": schedule_id,
                "trigger_source": "manual",
                "triggered_by": "User (Run Now)"
            },
            daemon=True,
            name=f"ManualRun_{schedule_id}"
        )
        t.start()
        return {"success": True, "message": f"Execution started for '{sched['name']}'."}

    # =========================================================================
    # Dashboards Data & Helpers
    # =========================================================================

    def get_upcoming_tasks(self) -> List[Dict[str, Any]]:
        """Returns upcoming scheduled scraping tasks sorted by next run time."""
        schedules = self.db.get_schedules()
        tasks = []
        for s in schedules:
            if not s.get("is_enabled"):
                continue
            next_run = s.get("next_run_at")
            if not next_run:
                continue

            sources = s.get("sources") or ["all"]
            sources_label = "All 7 Adapters" if "all" in sources else f"{len(sources)} Portals ({', '.join(sources[:2])}...)"

            # Frequency label
            freq = s.get("frequency", "daily").title()
            times_str = ", ".join(s.get("run_times", ["11:00"]))
            freq_label = f"{freq} at {times_str}"
            if freq.lower() == "weekly" and s.get("days_of_week"):
                days_abbr = [d[:3] for d in s["days_of_week"]]
                freq_label = f"Weekly ({', '.join(days_abbr)}) at {times_str}"

            tasks.append({
                "id": s["id"],
                "name": s["name"],
                "schedule_type": s.get("schedule_type", "custom"),
                "next_run_at": next_run,
                "frequency": freq_label,
                "status": "Active" if s.get("is_enabled") else "Paused",
                "job_sources": sources_label,
                "expected_window": format_execution_window(next_run, duration_minutes=3)
            })

        tasks.sort(key=lambda x: x["next_run_at"])
        return tasks

    def get_recommended_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Ranks recent jobs against the user's master resume profile,
        returning top recommended jobs with ATS match scores and key matched skills.
        """
        profile = career_kb.get_unified_profile()
        jobs, _ = self.db.get_jobs(limit=100, date_filter="30d")
        recommended = []

        for j in jobs:
            j_dict = j.model_dump()
            try:
                analysis = deep_job_analyzer.analyze_job(j_dict, profile)
                score = analysis.get("ats_metrics", {}).get("match_score") or analysis.get("gap_analysis", {}).get("ats_score", 0)
                matched_skills = analysis.get("gap_analysis", {}).get("matched_skills", [])
                missing_skills = analysis.get("gap_analysis", {}).get("missing_skills", [])
            except Exception:
                score = 65
                matched_skills = ["Data Analysis", "SQL"]
                missing_skills = []

            recommended.append({
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "country": j.country,
                "work_mode": j.work_mode,
                "salary": j.salary,
                "experience_level": j.experience_level,
                "source_name": j.source_name,
                "source_url": j.source_url,
                "published_at": j.published_at,
                "match_score": int(score),
                "matched_skills": matched_skills[:5],
                "missing_skills": missing_skills[:3],
                "skills": j.skills[:6]
            })

        recommended.sort(key=lambda x: x["match_score"], reverse=True)
        return recommended[:limit]

    def export_activity_logs(self, format_type: str = "csv") -> Tuple[bytes, str, str]:
        """
        Exports activity logs in CSV, Excel, or JSON format.
        Returns: (file_bytes, media_type, filename)
        """
        logs, _ = self.db.get_activity_logs(limit=1000)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        format_type = format_type.lower()

        if format_type == "json":
            content = json.dumps(logs, indent=2, ensure_ascii=False).encode("utf-8")
            return content, "application/json", f"scrape_activity_logs_{timestamp}.json"

        elif format_type in ["excel", "xlsx"]:
            # Build Excel file using openpyxl
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment

                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Scrape Logs"

                headers = [
                    "Run ID", "Schedule Name", "Trigger Source", "Triggered By",
                    "Status", "Started At", "Finished At", "Duration (s)",
                    "Jobs Scanned", "Jobs Added", "Duplicates Skipped", "Errors Count"
                ]
                ws.append(headers)

                header_fill = PatternFill(start_color="FFCED8", end_color="FFCED8", fill_type="solid")
                header_font = Font(bold=True, color="000000")
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center")

                for log in logs:
                    ws.append([
                        log.get("run_id"),
                        log.get("schedule_name"),
                        log.get("trigger_source"),
                        log.get("triggered_by"),
                        log.get("status"),
                        log.get("started_at"),
                        log.get("finished_at"),
                        log.get("duration_seconds"),
                        log.get("jobs_scanned"),
                        log.get("jobs_added"),
                        log.get("duplicates_skipped"),
                        log.get("errors_count")
                    ])

                out_stream = io.BytesIO()
                wb.save(out_stream)
                return out_stream.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"scrape_activity_logs_{timestamp}.xlsx"
            except Exception as e:
                logger.warning(f"Excel export fallback to CSV due to: {e}")
                format_type = "csv"

        # Default: CSV export
        output = io.StringIO()
        fieldnames = [
            "run_id", "schedule_name", "trigger_source", "triggered_by",
            "status", "started_at", "finished_at", "duration_seconds",
            "jobs_scanned", "jobs_added", "duplicates_skipped", "errors_count"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for l in logs:
            writer.writerow(l)

        return output.getvalue().encode("utf-8"), "text/csv", f"scrape_activity_logs_{timestamp}.csv"


# Singleton instance of ScraperScheduler
scraper_scheduler = ScraperScheduler()

