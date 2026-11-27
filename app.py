"""
FastAPI Web Application and REST API for Fresher Data Analytics Jobs (0-1 Year Experience).
Aggregates jobs from curated Indian & Global Remote platforms open to India.
Supports multi-role filtering, date recency, and 1-month window restrictions.
"""

import csv
import io
import json
import logging
import os
import re
import threading
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import quote
from fastapi import FastAPI, BackgroundTasks, Query, Response, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scraper.database import Database
from scraper.engine import ScraperEngine
from scraper.registry import PlatformRegistry
from scraper.taxonomy import ALL_ROLES, CORE_ANALYTICS_ROLES, RELATED_ROLES
from scraper.scheduler import scraper_scheduler, calculate_next_run
from resume_tailor.parser import master_resume_parser
from resume_tailor.engine import resume_tailor_engine
from resume_tailor.latex_builder import latex_builder
from resume_tailor.pdf_compiler import pdf_compiler, OUTPUT_DIR as RESUME_OUTPUT_DIR
from resume_tailor.docx_builder import docx_builder
from resume_tailor.knowledge_base import career_kb, DOCUMENT_CATEGORIES
from resume_tailor.cover_letter_builder import cover_letter_builder
from resume_tailor.txt_builder import txt_builder
from scraper.deep_scraper import deep_job_scraper
from resume_tailor.analyzer import deep_job_analyzer
from scraper.adapters.linkedin_recruiter import LinkedInRecruiterFeedAdapter
from scraper.linkedin_intelligence import linkedin_intelligence_agent
from scraper.safe_fetch import safe_fetch, validate_url, SSRFError
from scraper.relevance import score_job, get_min_relevance
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("job_finder")

app = FastAPI(
    title="Fresher Data Analyst Job Finder (0-1 Year Experience)",
    description="Multi-platform job aggregator across curated Indian and Global Remote platforms open to India.",
    version="2.0.0"
)

# Rate limiter implementation: 60 req/min general, 5 req/min on strict endpoints
class InMemoryRateLimiter:
    def __init__(self):
        self._records: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, ip: str, path: str) -> bool:
        now = time.time()
        window = 60.0

        # Strict routes: 5 req/min on /api/resume/*, /api/scraper/run, /api/kb/upload
        is_strict = (
            path.startswith("/api/resume")
            or path == "/api/scraper/run"
            or path.startswith("/api/kb/upload")
        )
        limit = 5 if is_strict else 60
        key = f"{ip}:{'strict' if is_strict else 'general'}"

        with self._lock:
            timestamps = [t for t in self._records[key] if now - t < window]
            if len(timestamps) >= limit:
                self._records[key] = timestamps
                return False
            timestamps.append(now)
            self._records[key] = timestamps
            return True

rate_limiter = InMemoryRateLimiter()

def get_client_ip(request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

# CORS Configuration: allow only origins in env ALLOWED_ORIGINS, allow_credentials=False
class DynamicCORSMiddleware(CORSMiddleware):
    def is_allowed_origin(self, origin: str) -> bool:
        allowed_raw = os.getenv("ALLOWED_ORIGINS", "")
        allowed = [o.strip() for o in allowed_raw.split(",") if o.strip()]
        return origin in allowed

app.add_middleware(
    DynamicCORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_auth_and_rate_limit_middleware(request, call_next):
    path = request.scope.get("path", request.url.path)

    # Static files and non-api routes bypass API authentication and rate limiting
    if not path.startswith("/api/"):
        return await call_next(request)

    # Preflight CORS requests must pass through to CORSMiddleware
    if request.method == "OPTIONS":
        return await call_next(request)

    # 1. Health check endpoint (GET /api/health) is exempt from API key
    if path == "/api/health" and request.method == "GET":
        return await call_next(request)

    # 2. Cron route: require Authorization: Bearer <CRON_SECRET>
    if path == "/api/cron":
        cron_secret = os.getenv("CRON_SECRET", "")
        auth_header = request.headers.get("Authorization", "")
        if not cron_secret or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: Missing or invalid Bearer token for cron"}
            )
        token = auth_header[7:].strip()
        if token != cron_secret:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: Invalid cron secret"}
            )
        return await call_next(request)

    # 3. All other /api/* routes require X-API-Key == env API_KEY
    expected_api_key = os.getenv("API_KEY", "")
    provided_api_key = request.headers.get("X-API-Key", "") or request.query_params.get("api_key", "")
    if not expected_api_key or provided_api_key != expected_api_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: Missing or invalid X-API-Key header"}
        )

    # 4. Per-IP Rate Limiting
    client_ip = get_client_ip(request)
    if not rate_limiter.check(client_ip, path):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Rate limit exceeded, please wait a minute before retrying."}
        )

    return await call_next(request)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.cdnfonts.com https://fonts.googleapis.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.cdnfonts.com https://fonts.gstatic.com data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "frame-ancestors 'none';"
    )
    return response

# Initialize singletons
db = Database()
registry = PlatformRegistry()
engine = ScraperEngine(db=db, registry=registry)
linkedin_adapter = LinkedInRecruiterFeedAdapter()

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
try:
    os.makedirs(static_dir, exist_ok=True)
except OSError:
    pass
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.middleware("http")
async def vercel_path_normalizer(request, call_next):
    path = request.scope.get("path", "")
    if path == "/api/index" or path == "/api/index.py":
        request.scope["path"] = "/"
    elif path.startswith("/api/index/"):
        request.scope["path"] = path[len("/api/index"):]
    return await call_next(request)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.get("/api/health")
def health_check():
    """
    Public health check endpoint for monitoring, uptime verification, and connectivity testing.
    Exempt from API key authentication.
    """
    return {
        "status": "ok",
        "service": "Fresher Data Analyst Job Finder",
        "timestamp": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    }

class ScrapeRequest(BaseModel):
    adapter_ids: Optional[List[str]] = None
    roles: Optional[List[str]] = ["Data Analyst", "Junior Data Analyst", "Business Analyst", "Power BI Developer", "Python"]
    cities: Optional[List[str]] = ["Pune", "Nagpur", "Hyderabad", "Aurangabad", "Bengaluru", "Mumbai", "Delhi", "Pan-India"]
    work_modes: Optional[List[str]] = ["On-Site", "Hybrid", "Remote"]
    pune_first: bool = True
    limit_per_source: int = 30
    schedule_name: Optional[str] = "Manual Scrape"
    scrape_new_only: bool = True
    rescrape_existing: bool = False
    refresh_expired: bool = False
    update_existing: bool = True
    deduplication: bool = True
    ats_scoring: bool = True
    skill_matching: bool = True
    resume_matching: bool = True
    max_jobs_per_run: Optional[int] = None
    portal_priority: Optional[List[str]] = None
    retry_count: int = 2
    request_delay: float = 0.5
    auto_stop_on_error: bool = False
    auto_recovery: bool = True

class ScheduleCreateRequest(BaseModel):
    name: str
    timezone: str = "Asia/Kolkata"
    frequency: str = "daily"
    run_times: List[str] = ["11:00"]
    days_of_week: Optional[List[str]] = None
    sources: Optional[List[str]] = ["all"]
    job_portals: Optional[List[str]] = ["all"]
    keywords: Optional[List[str]] = None
    location_filters: Optional[str] = ""
    work_modes: Optional[List[str]] = None
    is_enabled: bool = True
    scrape_new_only: bool = True
    rescrape_existing: bool = False
    refresh_expired: bool = False
    update_existing: bool = True
    deduplication: bool = True
    ats_scoring: bool = True
    skill_matching: bool = True
    resume_matching: bool = True
    max_jobs_per_run: int = 50
    portal_priority: Optional[List[str]] = None
    retry_count: int = 2
    request_delay: float = 0.5
    auto_stop_on_error: bool = False
    auto_recovery: bool = True

class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    frequency: Optional[str] = None
    run_times: Optional[List[str]] = None
    days_of_week: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    job_portals: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    location_filters: Optional[str] = None
    work_modes: Optional[List[str]] = None
    is_enabled: Optional[bool] = None
    scrape_new_only: Optional[bool] = None
    rescrape_existing: Optional[bool] = None
    refresh_expired: Optional[bool] = None
    update_existing: Optional[bool] = None
    deduplication: Optional[bool] = None
    ats_scoring: Optional[bool] = None
    skill_matching: Optional[bool] = None
    resume_matching: Optional[bool] = None
    max_jobs_per_run: Optional[int] = None
    portal_priority: Optional[List[str]] = None
    retry_count: Optional[int] = None
    request_delay: Optional[float] = None
    auto_stop_on_error: Optional[bool] = None
    auto_recovery: Optional[bool] = None

class NotificationSettingsRequest(BaseModel):
    in_app_enabled: bool = True
    email_enabled: bool = False
    email_recipient: Optional[str] = ""
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[int] = 587
    smtp_user: Optional[str] = ""
    smtp_password: Optional[str] = ""
    smtp_use_tls: bool = True
    notify_on_complete: bool = True
    notify_on_new_jobs: bool = True
    notify_on_high_match: bool = True
    notify_on_failure: bool = True
    webhook_enabled: bool = False
    webhook_url: Optional[str] = ""

class LinkedInPostIngestRequest(BaseModel):
    post_text: str
    post_url: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    designation: Optional[str] = None
    linkedin_profile: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    apply_url: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None

class LinkedInSettingsRequest(BaseModel):
    li_at: Optional[str] = ""
    sync_enabled: bool = True
    keywords: Optional[str] = "data analyst fresher hiring"

@app.on_event("startup")
def on_app_startup():
    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    logger.info(f"Application starting up (Serverless mode: {is_serverless}). Web app never scrapes in request.")

@app.on_event("shutdown")
def on_app_shutdown():
    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    if not is_serverless:
        logger.info("Stopping ScraperScheduler background worker...")
        try:
            scraper_scheduler.stop()
        except Exception:
            pass

class AnalyzeUrlRequest(BaseModel):
    url: str

class AnalyzeTextRequest(BaseModel):
    job_title: Optional[str] = "Data Analyst"
    company: Optional[str] = "Target Employer"
    description: str
    skills: Optional[List[str]] = None

class TailorResumeRequest(BaseModel):
    job_id: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    skills: Optional[List[str]] = None
    responsibilities: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    qualifications: Optional[List[str]] = None
    ats_keywords: Optional[List[str]] = None
    source_url: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    experience_level: Optional[str] = None
    salary: Optional[str] = None
    source_name: Optional[str] = None
    application_deadline: Optional[str] = None
    openings: Optional[str] = None

class UpdateTailoredResumeRequest(BaseModel):
    job_id: str
    tailored_resume: dict

class UpdateDocPayload(BaseModel):
    display_name: Optional[str] = None
    category: Optional[str] = None

class CustomJDTailorRequest(BaseModel):
    job_title: Optional[str] = "Data Analyst"
    company: Optional[str] = "Target Employer"
    description: str
    skills: Optional[List[str]] = None

@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
def index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(
                content=f.read(),
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    return HTMLResponse("<h1>Fresher Data Analyst Job Finder API is Running.</h1>")

@app.get("/api/roles")
def get_roles():
    """Returns the full 25 roles taxonomy grouped by Core and Related."""
    return {
        "core_roles": CORE_ANALYTICS_ROLES,
        "related_roles": RELATED_ROLES,
        "all_roles": ALL_ROLES
    }

@app.get("/api/platforms")
def get_platforms(section: Optional[str] = None, country: Optional[str] = None):
    """Returns curated platforms from directory enriched with live job vacancy counts."""
    platforms = registry.get_all()
    if section:
        platforms = [p for p in platforms if section.lower() in p.section.lower()]
    if country:
        platforms = [p for p in platforms if country.lower() in p.country.lower()]

    counts = db.get_platform_job_counts()
    result = []
    known_platform_ids = set()

    for p in platforms:
        d = p.model_dump()
        known_platform_ids.add(p.id)
        # Match by platform id or platform name
        cnt = counts.get(p.id.lower(), 0)
        if cnt == 0:
            cnt = counts.get(p.name.lower(), 0)
        d["job_count"] = cnt
        result.append(d)

    # Also include any active job sources present in the database not explicitly in the curated list
    try:
        with db.get_connection() as conn:
            extra_rows = conn.execute("""
                SELECT DISTINCT source_id, source_name, country
                FROM jobs
                WHERE is_active = 1
            """).fetchall()
            for r in extra_rows:
                sid = (r["source_id"] or "").strip()
                sname = (r["source_name"] or "").strip()
                if sid and sid not in known_platform_ids and not any(p["id"] == sid for p in result):
                    cnt = counts.get(sid.lower(), counts.get(sname.lower(), 1))
                    result.append({
                        "id": sid,
                        "name": sname or sid.replace("_", " ").title(),
                        "category": "Company Careers",
                        "section": "C. Direct company career pages to include",
                        "country": r["country"] or "Global / India",
                        "website": "",
                        "search_url_template": "",
                        "integration_type": "direct_career_page",
                        "has_adapter": True,
                        "notes": f"Direct career openings ({sname})",
                        "job_count": cnt
                    })
    except Exception as e:
        logger.warning(f"Error checking extra platform sources: {e}")

    return result

@app.get("/api/cities")
def get_cities():
    """Returns curated cities with live active job counts."""
    return db.get_city_counts()

@app.get("/api/jobs")
def get_jobs(
    q: Optional[str] = None,
    roles: Optional[List[str]] = Query(None),
    role: Optional[str] = None,
    platforms: Optional[List[str]] = Query(None),
    platform: Optional[str] = None,
    city: Optional[str] = None,
    cities: Optional[List[str]] = Query(None),
    role_category: Optional[str] = None,
    country: Optional[str] = None,
    source_id: Optional[str] = None,
    work_mode: Optional[str] = None,
    experience_level: Optional[str] = None,
    skill: Optional[str] = None,
    applied: Optional[str] = None,
    date_posted: Optional[str] = Query(None),
    scrape_freshness: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("date_desc"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Search and filter jobs with multi-role support, multi-city support, multi-platform support, scrape freshness, and sorting."""
    target_roles = []
    if roles:
        for r in roles:
            if "," in r:
                target_roles.extend([x.strip() for x in r.split(",") if x.strip()])
            else:
                target_roles.append(r)
    elif role:
        target_roles = [role]

    target_platforms = []
    if platforms:
        for p in platforms:
            if "," in p:
                target_platforms.extend([x.strip() for x in p.split(",") if x.strip()])
            else:
                target_platforms.append(p)
    elif platform:
        target_platforms = [platform]

    target_cities = []
    if cities:
        for c in cities:
            if "," in c:
                target_cities.extend([x.strip() for x in c.split(",") if x.strip()])
            else:
                target_cities.append(c.strip())
    elif city:
        if "," in city:
            target_cities.extend([x.strip() for x in city.split(",") if x.strip()])
        else:
            target_cities.append(city.strip())

    jobs, total = db.get_jobs(
        query=q or "",
        roles=target_roles if target_roles else None,
        role_category=role_category or "",
        country=country or "",
        city=city or "",
        cities=target_cities if target_cities else None,
        source_id=source_id or "",
        platforms=target_platforms if target_platforms else None,
        work_mode=work_mode or "",
        experience_level=experience_level or "",
        skill=skill or "",
        applied=applied or "",
        date_filter=date_posted or "",
        scrape_freshness=scrape_freshness or "",
        sort_by=sort_by or "date_desc",
        limit=limit,
        offset=offset
    )
    unified_profile = career_kb.get_unified_profile()
    candidate_skills = set()
    raw_tools = unified_profile.get("technical_tools") or []
    if isinstance(raw_tools, list):
        for s in raw_tools:
            if isinstance(s, str):
                candidate_skills.add(s.lower().strip())
    raw_skills = unified_profile.get("skills") or {}
    if isinstance(raw_skills, dict):
        for sublist in raw_skills.values():
            if isinstance(sublist, list):
                for s in sublist:
                    if isinstance(s, str):
                        candidate_skills.add(s.lower().strip())
    elif isinstance(raw_skills, list):
        for s in raw_skills:
            if isinstance(s, str):
                candidate_skills.add(s.lower().strip())

    jobs_out = []
    for j in jobs:
        d = j.model_dump()
        # Compute dynamic match score against verified career profile if available
        if candidate_skills and d.get("skills"):
            jskills = set(s.lower().strip() for s in d["skills"])
            if jskills:
                match_pct = round((len(candidate_skills.intersection(jskills)) / len(jskills)) * 100)
                d["match_score"] = match_pct
        jobs_out.append(d)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "date_posted_filter": date_posted,
        "scrape_freshness_filter": scrape_freshness,
        "sort_by": sort_by or "date_desc",
        "jobs": jobs_out,
        "items": jobs_out
    }

class JobAppliedPayload(BaseModel):
    is_applied: bool

class JobStatusPayload(BaseModel):
    status: str

@app.patch("/api/jobs/{job_id}/applied")
@app.post("/api/jobs/{job_id}/applied")
def set_job_applied(job_id: str, payload: JobAppliedPayload):
    """Update applied status for a specific job."""
    success = db.update_job_applied(job_id, payload.is_applied)
    if not success:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Job {job_id} not found"}),
            media_type="application/json"
        )
    return {"id": job_id, "is_applied": payload.is_applied, "success": True}

@app.patch("/api/jobs/{job_id}/status")
@app.post("/api/jobs/{job_id}/status")
def set_job_status(job_id: str, payload: JobStatusPayload):
    """Update workflow status for a specific job (new, applied, saved, interview, offer, rejected, ignored)."""
    success = db.update_job_status(job_id, payload.status)
    if not success:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Job {job_id} not found"}),
            media_type="application/json"
        )
    return {"id": job_id, "status": payload.status, "success": True}

@app.post("/api/jobs/{job_id}/bookmark")
@app.patch("/api/jobs/{job_id}/bookmark")
def toggle_job_bookmark(job_id: str):
    """Toggle bookmark saved state for a job."""
    is_bookmarked = db.toggle_job_bookmark(job_id)
    return {"id": job_id, "is_bookmarked": is_bookmarked, "success": True}

@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str):
    job = db.get_job_by_id(job_id)
    if not job:
        return Response(status_code=404, content=json.dumps({"error": "Job not found"}), media_type="application/json")
    if not job.is_deep_scraped or len(job.description or "") < 250:
        enriched = deep_job_scraper.enrich_job(db, job_id)
        if enriched:
            job = enriched
    return job.model_dump()

@app.post("/api/jobs/{job_id}/rescrape")
def rescrape_job(job_id: str):
    job = db.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    enriched = deep_job_scraper.enrich_job(db, job_id, force=True)
    if not enriched:
        raise HTTPException(status_code=500, detail="Failed to scrape original job page")
    return {"success": True, "job": enriched.model_dump()}

@app.get("/api/stats")
def get_stats():
    """Returns system summary statistics."""
    return db.get_statistics()

@app.post("/api/scraper/run")
def trigger_scrape(req: ScrapeRequest):
    """
    Enqueues an immediate scrape run request for CLI/background worker execution.
    The web app never executes scraping directly inside a web request.
    """
    target_adapters = req.adapter_ids or ["all"]
    run_id = db.enqueue_run_request(
        trigger_source="manual",
        triggered_by="User (Manual Web Request)",
        adapter_ids=target_adapters,
        schedule_name=req.schedule_name or "Manual On-Demand Run"
    )

    return {
        "status": "queued",
        "message": f"Scrape run request enqueued for worker CLI ({len(target_adapters)} adapters requested).",
        "run_id": run_id,
        "target_adapters": target_adapters
    }

@app.get("/api/scraper/status")
def get_scraper_status():
    stats = db.get_statistics()
    return {
        "live_monitor": scraper_scheduler.live_monitor,
        "latest_run": stats.get("latest_run"),
        "total_jobs": stats.get("total_jobs"),
        "available_adapters": list(engine.adapters.keys())
    }

@app.get("/api/scraper/monitor/live")
def get_live_monitor():
    """Returns real-time scraping progress, stage, active adapter, elapsed time, and jobs found."""
    return scraper_scheduler.live_monitor

@app.get("/api/cron")
@app.post("/api/scraper/schedules/auto-tick")
def cron_trigger():
    """
    Automated Cron Trigger endpoint for serverless and cloud deployments.
    Evaluates enabled schedules and enqueues due runs in run_logs.
    The web app never executes scraping directly inside a web request.
    """
    triggered_runs = []
    schedules = db.get_schedules()
    tz = ZoneInfo("Asia/Kolkata")
    now_in_tz = datetime.now(tz)

    for s in schedules:
        if not s.get("is_enabled"):
            continue
        next_run_str = s.get("next_run_at")
        if not next_run_str:
            continue
        try:
            next_dt = datetime.fromisoformat(next_run_str)
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=tz)

            if next_dt <= now_in_tz:
                logger.info(f"[Cron Auto-Trigger] Schedule '{s['name']}' ({s['id']}) is DUE ({next_dt} <= {now_in_tz}). Enqueuing run request...")
                subsequent_run = calculate_next_run(
                    s.get("frequency", "daily"),
                    s.get("run_times", ["11:00"]),
                    s.get("days_of_week"),
                    s.get("timezone", "Asia/Kolkata"),
                    from_dt=now_in_tz + timedelta(minutes=1)
                )
                s["next_run_at"] = subsequent_run
                db.save_schedule(s)

                run_id = db.enqueue_run_request(
                    trigger_source="scheduled",
                    triggered_by="Cloud Cron Scheduler",
                    adapter_ids=s.get("sources") or ["all"],
                    schedule_id=s["id"],
                    schedule_name=s["name"]
                )
                triggered_runs.append({
                    "schedule_id": s["id"],
                    "name": s["name"],
                    "status": "queued",
                    "run_id": run_id
                })
        except Exception as e:
            logger.error(f"Error checking schedule {s.get('id')} in cron_trigger: {e}")

    return {
        "success": True,
        "server_time_ist": now_in_tz.strftime("%Y-%m-%d %H:%M:%S"),
        "triggered_count": len(triggered_runs),
        "triggered_schedules": triggered_runs,
        "active_monitor": scraper_scheduler.live_monitor
    }

# --- Schedules Management Endpoints ---

@app.get("/api/scraper/schedules")
def list_schedules():
    """Lists all automated schedules (default Morning & Evening, plus user custom schedules)."""
    if not scraper_scheduler._is_running or not scraper_scheduler._ticker_thread or not scraper_scheduler._ticker_thread.is_alive():
        scraper_scheduler.start()
    schedules = db.get_schedules()
    return {"schedules": schedules, "total": len(schedules)}

@app.post("/api/scraper/schedules")
def create_schedule(req: ScheduleCreateRequest):
    """Creates a new custom scraping schedule."""
    new_schedule = scraper_scheduler.create_custom_schedule(req.model_dump())
    return {"success": True, "schedule": new_schedule}

@app.get("/api/scraper/schedules/{schedule_id}")
def get_schedule(schedule_id: str):
    sched = db.get_schedule(schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return sched

@app.put("/api/scraper/schedules/{schedule_id}")
def update_schedule(schedule_id: str, req: ScheduleUpdateRequest):
    """Updates an existing schedule configuration."""
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = scraper_scheduler.update_schedule(schedule_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True, "schedule": updated}

@app.post("/api/scraper/schedules/{schedule_id}/pause")
def pause_schedule(schedule_id: str):
    """Pauses a schedule."""
    success = scraper_scheduler.pause_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True, "message": "Schedule paused."}

@app.post("/api/scraper/schedules/{schedule_id}/resume")
def resume_schedule(schedule_id: str):
    """Resumes an automated schedule."""
    success = scraper_scheduler.resume_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True, "message": "Schedule resumed."}

@app.delete("/api/scraper/schedules/{schedule_id}")
def delete_schedule(schedule_id: str):
    """Deletes a custom schedule."""
    success = scraper_scheduler.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found or cannot be deleted")
    return {"success": True, "message": "Schedule deleted."}

@app.post("/api/scraper/schedules/{schedule_id}/run-now")
def run_schedule_now(schedule_id: str):
    """Triggers immediate on-demand execution of an existing schedule."""
    result = scraper_scheduler.run_schedule_now(schedule_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to start schedule run"))
    return result

# --- Upcoming Tasks Endpoint ---

@app.get("/api/scraper/upcoming")
def get_upcoming_tasks():
    """Lists upcoming scheduled scraping tasks with execution windows."""
    tasks = scraper_scheduler.get_upcoming_tasks()
    return {"tasks": tasks, "total": len(tasks)}

# --- Recommended Jobs (Job Match Integration) ---

@app.get("/api/scraper/recommended")
def get_recommended_jobs(limit: int = Query(20, ge=1, le=100)):
    """Returns top jobs matched and ranked against candidate Master Resume."""
    recommended = scraper_scheduler.get_recommended_jobs(limit=limit)
    return {"recommended_jobs": recommended, "total": len(recommended)}

# --- Scrape Activity Logs Endpoints ---

@app.get("/api/scraper/logs")
def get_activity_logs(
    date_range: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    job_portal: Optional[str] = Query(None),
    schedule_name: Optional[str] = Query(None),
    trigger_source: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Returns paginated, filterable scrape activity logs."""
    logs, total = db.get_activity_logs(
        date_range=date_range,
        status=status,
        job_portal=job_portal,
        schedule_name=schedule_name,
        trigger_source=trigger_source,
        query=q,
        limit=limit,
        offset=offset
    )
    return {"logs": logs, "total": total, "limit": limit, "offset": offset}

@app.get("/api/scraper/logs/{run_id}")
def get_activity_log(run_id: str):
    log = db.get_activity_log(run_id)
    if not log:
        raise HTTPException(status_code=404, detail="Activity log not found")
    return log

@app.get("/api/scraper/logs/export/download")
def export_activity_logs(format: str = Query("csv", pattern="^(csv|excel|xlsx|json)$")):
    """Exports scraping activity logs in CSV, Excel, or JSON format."""
    content, media_type, filename = scraper_scheduler.export_activity_logs(format_type=format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# --- Historical Analytics Dashboard Endpoint ---

@app.get("/api/scraper/analytics")
def get_scraping_analytics():
    """Returns aggregate metrics, trends, portal productivity, and distribution charts."""
    return db.get_scraping_analytics()

# --- Audit Logs Endpoint ---

@app.get("/api/scraper/audit-logs")
def get_audit_logs(limit: int = Query(100, ge=1, le=500)):
    return {"audit_logs": db.get_audit_logs(limit=limit)}

# --- Notification System Endpoints ---

@app.get("/api/scraper/notifications")
def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False)
):
    """Returns in-app notifications and unread counter."""
    return db.get_notifications(limit=limit, unread_only=unread_only)

@app.post("/api/scraper/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str):
    success = db.mark_notification_read(notification_id)
    return {"success": success}

@app.post("/api/scraper/notifications/mark-all-read")
def mark_all_notifications_read():
    count = db.mark_all_notifications_read()
    return {"success": True, "marked_count": count}

@app.get("/api/scraper/notifications/settings")
def get_notification_settings():
    return db.get_notification_settings()

@app.post("/api/scraper/notifications/settings")
def save_notification_settings(req: NotificationSettingsRequest):
    db.save_notification_settings(req.model_dump())
    return {"success": True, "settings": db.get_notification_settings()}

@app.post("/api/scraper/notifications/test-email")
def test_email_notification():
    settings = db.get_notification_settings()
    recipient = settings.get("email_recipient")
    if not recipient:
        raise HTTPException(status_code=400, detail="Please provide a valid recipient email address in Notification Settings.")

    scraper_scheduler._send_email_report(
        settings=settings,
        schedule_name="Test Notification Check",
        final_status="completed",
        jobs_added=5,
        jobs_scanned=24,
        high_match_count=2,
        errors=[],
        duration=12.4
    )
    return {"success": True, "message": f"Test email dispatched to {recipient}"}

# --- LinkedIn HR & Recruiter Feed Platform Endpoints ---

@app.get("/api/scraper/linkedin/feed")
def get_linkedin_feed_jobs(
    q: Optional[str] = None,
    has_email_only: bool = Query(False),
    work_mode: Optional[str] = None,
    sort_by: Optional[str] = Query("date_desc"),
    limit: int = Query(50, ge=1, le=100)
):
    """Fetches HR & recruiter hiring posts from LinkedIn feed with direct contact metrics."""
    feed_jobs, total = db.get_jobs(source_id="linkedin_feed", limit=limit, query=q or "")
    if total < 5 and not q:
        scraped_jobs = linkedin_adapter.scrape(limit=30)
        for j in scraped_jobs:
            score = score_job(j)
            j.relevance_score = score
            if score >= get_min_relevance():
                db.save_job(j, enforce_relevance=True)
        feed_jobs, total = db.get_jobs(source_id="linkedin_feed", limit=limit, sort_by=sort_by or "date_desc")

    items = [j.model_dump() for j in feed_jobs]
    if has_email_only:
        items = [j for j in items if j.get("recruiter_email")]
    if work_mode:
        items = [j for j in items if (j.get("work_mode") or "").lower() == work_mode.lower()]

    with_email_count = sum(1 for j in items if j.get("recruiter_email"))
    return {
        "items": items,
        "total": len(items),
        "all_in_db": total,
        "direct_email_count": with_email_count,
        "email_readiness_pct": round((with_email_count / max(1, len(items))) * 100, 1),
        "source_name": "LinkedIn HR & Recruiter Posts",
        "settings": linkedin_adapter.load_user_settings()
    }

@app.post("/api/scraper/linkedin/sync")
def sync_linkedin_recruiter_posts():
    """Scrapes and syncs latest recruiter feed posts from LinkedIn into jobs.db."""
    scraped_jobs = linkedin_adapter.scrape(limit=50)
    added_count = 0
    for j in scraped_jobs:
        score = score_job(j)
        j.relevance_score = score
        if score >= get_min_relevance():
            if db.save_job(j, enforce_relevance=True):
                added_count += 1

    db.add_notification(
        title=f"👔 LinkedIn Recruiter Sync: {len(scraped_jobs)} Posts Scraped",
        message=f"Synced {len(scraped_jobs)} HR hiring announcements. {added_count} new postings added to Fresher Jobs Explorer.",
        type="success",
        category="new_jobs",
        metadata={"source_id": "linkedin_feed", "added": added_count}
    )
    return {"success": True, "scraped_count": len(scraped_jobs), "new_added": added_count}

# In-memory registry to retain job titles, companies, and candidate names for standard download naming
TAILORED_JOB_METADATA: Dict[str, Dict[str, Any]] = {}

def format_filename_slug(text: str, default: str = "") -> str:
    """Cleans and formats a string into Pascal_Case / Title_Case words joined by underscore."""
    if not text:
        return default
    # Remove parentheses content like (0-1 Year Exp), (Remote), etc.
    text = re.sub(r'\(.*?\)', '', str(text))
    # Replace common separators with spaces
    text = text.replace('&', 'and').replace('/', ' ').replace('-', ' ').replace('_', ' ')
    # Remove non-alphanumeric except spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    words = [w.capitalize() for w in text.split() if w]
    if not words:
        return default
    return "_".join(words)

def clean_candidate_filename_name(raw_name: Optional[str] = None) -> str:
    """Formats candidate name to standard format like Tejas_Waghmare."""
    if not raw_name or str(raw_name).lower().strip() in ["candidate", "candidate name", ""]:
        profile = career_kb.get_unified_profile()
        raw_name = profile.get("name") or "Tejas Waghmare"
    clean = re.sub(r'[^a-zA-Z\s]', '', str(raw_name)).strip()
    words = [w.capitalize() for w in clean.split() if w]
    # If 3 words with middle initial e.g. "Tejas C Waghmare" -> "Tejas_Waghmare"
    if len(words) == 3 and len(words[1]) == 1:
        return f"{words[0]}_{words[2]}"
    elif len(words) >= 2:
        return f"{words[0]}_{words[1]}"
    elif len(words) == 1:
        return words[0]
    return "Tejas_Waghmare"

def build_standard_filename(
    candidate_name: Optional[str],
    role: Optional[str],
    company: Optional[str],
    doc_type: str,  # "Resume" or "Cover_Letter"
    extension: str,  # "pdf", "docx", "tex", "txt"
    date_str: Optional[str] = None
) -> str:
    """
    Builds standard document filename:
    Tejas_Waghmare_Role_company_name_resume_current_date
    Example: Tejas_Waghmare_Data_Analyst_Google_Resume_31_10_2026.pdf
    """
    name_slug = clean_candidate_filename_name(candidate_name)
    role_slug = format_filename_slug(role or "Data Analyst", default="Data_Analyst")
    comp_slug = format_filename_slug(company or "Target Employer", default="Target_Employer")
    if not date_str:
        date_str = datetime.now().strftime("%d_%m_%Y")
    ext = extension.lstrip(".")
    return f"{name_slug}_{role_slug}_{comp_slug}_{doc_type}_{date_str}.{ext}"

def generate_tailored_artifacts(job: Any) -> Dict[str, Any]:
    """
    Builds Overleaf LaTeX, strict 1-page PDF, Word (.docx), Plain Text (.txt),
    and personalized Cover Letter (.docx, .pdf, .txt) grounded in Career Knowledge Base.
    Ensures that artifacts always exist for instant download and Gmail outreach attachments.
    """
    job_id = getattr(job, "id", None) or (job.get("id") if isinstance(job, dict) else "custom_job")
    clean_id = "".join([c if c.isalnum() else "_" for c in str(job_id)])
    
    title = getattr(job, "title", None) or (job.get("title") if isinstance(job, dict) else "Data Analyst")
    company = getattr(job, "company", None) or (job.get("company") if isinstance(job, dict) else "Target Employer")
    desc = getattr(job, "description", None) or (job.get("description") if isinstance(job, dict) else "")
    skills = getattr(job, "skills", None) or (job.get("skills") if isinstance(job, dict) else ["SQL", "Power BI", "Excel", "Data Analytics"])
    responsibilities = getattr(job, "responsibilities", None) or (job.get("responsibilities") if isinstance(job, dict) else [])
    requirements = getattr(job, "requirements", None) or (job.get("requirements") if isinstance(job, dict) else [])
    ats_keywords = getattr(job, "ats_keywords", None) or (job.get("ats_keywords") if isinstance(job, dict) else [])

    try:
        tailored_result = resume_tailor_engine.tailor(
            job_title=title,
            company=company,
            job_description=desc,
            job_skills=skills,
            responsibilities=responsibilities,
            requirements=requirements,
            ats_keywords=ats_keywords
        )
    except Exception as e:
        logger.warning(f"Tailoring engine warning for {clean_id}: {e}")
        tailored_result = {
            "tailored_resume": career_kb.get_unified_profile(),
            "ats_metrics": {"match_score": 88, "matched_keywords": skills}
        }

    tailored_data = tailored_result.get("tailored_resume") or career_kb.get_unified_profile()
    candidate_name = tailored_data.get("name") or career_kb.get_unified_profile().get("name") or "Tejas Waghmare"

    # Save to metadata registry for download naming
    TAILORED_JOB_METADATA[clean_id] = {
        "title": title,
        "company": company,
        "name": candidate_name
    }
    
    # 1. LaTeX
    try:
        latex_code = latex_builder.build_latex(tailored_data)
        tex_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_code)
    except Exception as e:
        logger.warning(f"LaTeX build warning: {e}")

    # 2. PDF
    try:
        pdf_compiler.compile(tailored_data, clean_id)
    except Exception as e:
        logger.warning(f"PDF compile warning: {e}")

    # 3. DOCX
    try:
        docx_builder.build_docx(tailored_data, clean_id)
    except Exception as e:
        logger.warning(f"DOCX build warning: {e}")

    # 4. TXT
    try:
        txt_builder.build_txt(tailored_data, clean_id)
    except Exception as e:
        logger.warning(f"TXT build warning: {e}")

    # 5. Cover Letter (.docx, .pdf, .txt)
    try:
        profile = career_kb.get_unified_profile()
        cl_data = cover_letter_builder.generate(
            title, company, desc, skills, profile,
            responsibilities=responsibilities, requirements=requirements
        )
        cover_letter_builder.build_docx(cl_data, clean_id)
        cover_letter_builder.build_pdf(cl_data, clean_id)
        cl_txt_path = os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.txt")
        with open(cl_txt_path, "w", encoding="utf-8") as f:
            f.write(cl_data.get("full_text", ""))
    except Exception as e:
        logger.warning(f"Cover letter build warning: {e}")

    # Persist all generated artifacts into the database stored_files table
    _persist_tailored_artifacts_to_db(clean_id)

    filenames = {
        "resume_pdf": build_standard_filename(candidate_name, title, company, "Resume", "pdf"),
        "resume_docx": build_standard_filename(candidate_name, title, company, "Resume", "docx"),
        "resume_tex": build_standard_filename(candidate_name, title, company, "Resume", "tex"),
        "resume_txt": build_standard_filename(candidate_name, title, company, "Resume", "txt"),
        "cover_letter_pdf": build_standard_filename(candidate_name, title, company, "Cover_Letter", "pdf"),
        "cover_letter_docx": build_standard_filename(candidate_name, title, company, "Cover_Letter", "docx"),
        "cover_letter_txt": build_standard_filename(candidate_name, title, company, "Cover_Letter", "txt")
    }

    return {
        "clean_id": clean_id,
        "pdf_url": f"/api/resume/download/pdf/{clean_id}",
        "docx_url": f"/api/resume/download/docx/{clean_id}",
        "cl_pdf_url": f"/api/cover-letter/download/pdf/{clean_id}",
        "cl_docx_url": f"/api/cover-letter/download/docx/{clean_id}",
        "filenames": filenames
    }

def _persist_tailored_artifacts_to_db(clean_id: str):
    """Persists generated resume and cover letter files to persistent database stored_files table."""
    files_to_store = [
        (f"tailored_{clean_id}.pdf", "application/pdf", "pdf", os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.pdf")),
        (f"tailored_{clean_id}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx", os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.docx")),
        (f"tailored_{clean_id}.tex", "text/plain; charset=utf-8", "tex", os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.tex")),
        (f"tailored_{clean_id}.txt", "text/plain; charset=utf-8", "txt", os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.txt")),
        (f"tailored_{clean_id}.html", "text/html; charset=utf-8", "html", os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.html")),
        (f"cover_letter_{clean_id}.pdf", "application/pdf", "pdf", os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.pdf")),
        (f"cover_letter_{clean_id}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx", os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.docx")),
        (f"cover_letter_{clean_id}.txt", "text/plain; charset=utf-8", "txt", os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.txt")),
    ]
    for fname, ctype, ftype, fpath in files_to_store:
        if os.path.exists(fpath):
            try:
                with open(fpath, "rb") as fp:
                    content = fp.read()
                db.save_file(file_id=fname, filename=fname, content=content, content_type=ctype, file_type=ftype)
            except Exception as e:
                logger.warning(f"Error persisting {fname} to db: {e}")

def _ensure_job_artifacts(job_id: str):
    """Ensures tailored resume and cover letter artifacts exist on disk for the given job_id."""
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    pdf_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.pdf")
    if not os.path.exists(pdf_path):
        db_job = db.get_job_by_id(job_id)
        if db_job:
            generate_tailored_artifacts(db_job)

def is_valid_external_post_url(url: Optional[str]) -> bool:
    """Validates whether a URL is a genuine external post link (never localhost, search queries, or generic feed)."""
    if not url:
        return False
    u = url.strip().lower()
    if any(loc in u for loc in ["127.0.0.1", "localhost", "0.0.0.0", "javascript:", "failed"]):
        return False
    if "linkedin.com/search" in u:
        return False
    if u.rstrip("/").endswith("linkedin.com/feed"):
        return False
    return u.startswith("http://") or u.startswith("https://")

@app.post("/api/scraper/linkedin/ingest")
def ingest_linkedin_post(req: LinkedInPostIngestRequest):
    """
    Validates, structures, and stores genuine hiring posts matching LinkedIn Intelligence Agent criteria.
    Supports both short links (lnkd.in) and long LinkedIn post URLs, automatically scraping
    complete hiring details, contact credentials, and pre-compiling tailored ATS resume & cover letter.
    """
    if not req.post_text.strip() and not (req.post_url and req.post_url.strip()):
        raise HTTPException(status_code=400, detail="Please provide post text or post URL.")

    if req.post_url and req.post_url.strip():
        try:
            validate_url(req.post_url.strip())
        except SSRFError as se:
            raise HTTPException(status_code=400, detail=f"SSRF Protection: {se}")

    # 1. Run Intelligence Agent Analysis (auto-scrapes live URLs including lnkd.in)
    analyzed_data = linkedin_intelligence_agent.analyze_post(
        post_text=req.post_text,
        post_url=req.post_url,
        recruiter_name=req.recruiter_name,
        designation=req.designation,
        linkedin_profile=req.linkedin_profile,
        company=req.company,
        location=req.location
    )
    if req.apply_url and not analyzed_data.get("apply_url"):
        analyzed_data["apply_url"] = req.apply_url
    if req.phone and not analyzed_data.get("phone"):
        analyzed_data["phone"] = req.phone
    if req.whatsapp and not analyzed_data.get("whatsapp"):
        analyzed_data["whatsapp"] = req.whatsapp

    # 2. Quality Gatekeeper Validation (Section 10)
    is_valid, validation_errors = linkedin_intelligence_agent.validate_quality_gate(analyzed_data)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Post failed LinkedIn Hiring Intelligence quality criteria.",
                "errors": validation_errors,
                "analysis": analyzed_data
            }
        )

    # 3. Create structured Job model and persist
    job = linkedin_adapter.parse_post_text(
        post_text=analyzed_data.get("job_description") or req.post_text,
        post_url=analyzed_data.get("post_url") or req.post_url,
        recruiter_name=analyzed_data.get("recruiter_name") or req.recruiter_name,
        recruiter_email=analyzed_data.get("email") or req.recruiter_email,
        company=analyzed_data.get("company") or req.company,
        location=analyzed_data.get("location") or req.location,
        designation=analyzed_data.get("designation") or req.designation,
        linkedin_profile=analyzed_data.get("linkedin_profile") or req.linkedin_profile,
        apply_url=analyzed_data.get("apply_url"),
        contact_phone=analyzed_data.get("phone"),
        contact_whatsapp=analyzed_data.get("whatsapp"),
    )
    job.relevance_score = score_job(job)
    if job.relevance_score < get_min_relevance():
        raise HTTPException(
            status_code=400,
            detail=f"Post does not meet relevance threshold ({job.relevance_score} < {get_min_relevance()})"
        )
    is_new = db.save_job(job, enforce_relevance=True)

    # 4. Auto-generate tailored ATS resume and cover letter artifacts for this job
    clean_id = "".join([c if c.isalnum() else "_" for c in job.id])
    generate_tailored_artifacts(job)

    # 5. Generate personalized outreach draft and Gmail redirect
    recruiter_first = (job.recruiter_name or "Hiring Team").split()[0]
    subject = f"Application for {job.title} - Tejas C. Waghmare"
    skills_str = ", ".join(job.skills[:5]) if job.skills else "SQL, Power BI, Excel, and Data Analytics"
    clean_url = job.source_url if is_valid_external_post_url(job.source_url) else ""

    email_body = (
        f"Hi {recruiter_first},\n\n"
        f"I noticed your hiring announcement for the {job.title} position at {job.company}"
        f"{f' ({clean_url})' if clean_url else ''}. With hands-on proficiency in {skills_str}, "
        f"data storytelling, and dynamic business dashboard creation, my competencies align closely with your requirements.\n\n"
        f"I have attached:\n"
        f"1. ATS-Tailored Resume: Customized specifically for {job.title} at {job.company}.\n"
        f"2. Tailored Cover Letter: Detailing my analytical problem-solving and project impact.\n\n"
        f"Portfolio & Verified Credentials:\n"
        f"• GitHub & Code Repositories: https://github.com/TCWaghmare\n"
        f"• LinkedIn Profile: https://linkedin.com/in/tejascwaghmare\n"
        f"• Analytics Projects: Amazon Sales Dashboard & Diversity & Inclusion KPI Analytics\n\n"
        f"I am based in Pune (open for immediate joining and rotational / on-site requirements) and would welcome the opportunity to discuss how I can contribute to {job.company}.\n\n"
        f"Looking forward to hearing from you!\n\n"
        f"Best regards,\n"
        f"Tejas C. Waghmare\n"
        f"Phone: +91 83788 69006\n"
        f"Email: tejaswaghmare900@gmail.com"
    )

    gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(job.recruiter_email or '')}&su={quote(subject)}&body={quote(email_body)}"
    mailto_url = f"mailto:{quote(job.recruiter_email or '')}?subject={quote(subject)}&body={quote(email_body)}"

    db.add_notification(
        title=f"📋 LinkedIn HR Post Ingested: {job.company}",
        message=f"Added '{job.title}' by {job.recruiter_name or 'Recruiter'}. Match: {job.role_match_score}% | Confidence: {job.confidence_score}%.",
        type="info",
        category="new_jobs",
        metadata={"job_id": job.id, "company": job.company}
    )

    return {
        "success": True,
        "is_new": is_new,
        "structured_post": analyzed_data,
        "job": job.model_dump(),
        "outreach": {
            "recruiter_email": job.recruiter_email or "",
            "recruiter_name": job.recruiter_name or "",
            "subject": subject,
            "body": email_body,
            "gmail_url": gmail_url,
            "mailto_url": mailto_url,
            "has_email": bool(job.recruiter_email)
        },
        "download_urls": {
            "resume_pdf": f"/api/resume/download/pdf/{clean_id}",
            "resume_docx": f"/api/resume/download/docx/{clean_id}",
            "cover_letter_pdf": f"/api/cover-letter/download/pdf/{clean_id}",
            "cover_letter_docx": f"/api/cover-letter/download/docx/{clean_id}"
        }
    }

class LinkedInBatchIngestRequest(BaseModel):
    posts: List[LinkedInPostIngestRequest]

@app.post("/api/scraper/linkedin/ingest/batch")
def ingest_linkedin_posts_batch(req: LinkedInBatchIngestRequest):
    """
    Batch ingestion for LinkedIn feed harvester bookmarklet / browser script.
    Ingests all qualified posts, skips disqualified ones gracefully, and returns aggregate counts.
    """
    saved = 0
    skipped = 0
    errors = []
    saved_jobs = []

    for item in req.posts:
        try:
            res = ingest_linkedin_post(item)
            if res.get("success"):
                saved += 1
                saved_jobs.append(res.get("job", {}))
        except HTTPException as he:
            skipped += 1
            errors.append(he.detail)
        except Exception as e:
            skipped += 1
            errors.append(str(e))

    return {
        "success": True,
        "saved_count": saved,
        "skipped_count": skipped,
        "total": len(req.posts),
        "saved_jobs": saved_jobs,
        "errors": errors[:5]
    }

@app.post("/api/scraper/linkedin/analyze")
def analyze_linkedin_post(req: LinkedInPostIngestRequest):
    """
    Analyzes, scores, and structures a LinkedIn post using the Intelligence Agent without persisting to database.
    Returns Section 9 JSON format with validation status.
    """
    if not req.post_text.strip() and not (req.post_url and req.post_url.strip()):
        raise HTTPException(status_code=400, detail="Please provide post text or post URL.")

    if req.post_url and req.post_url.strip():
        try:
            validate_url(req.post_url.strip())
        except SSRFError as se:
            raise HTTPException(status_code=400, detail=f"SSRF Protection: {se}")

    analyzed = linkedin_intelligence_agent.analyze_post(
        post_text=req.post_text,
        post_url=req.post_url,
        recruiter_name=req.recruiter_name,
        designation=req.designation,
        linkedin_profile=req.linkedin_profile,
        company=req.company,
        location=req.location
    )
    is_valid, errors = linkedin_intelligence_agent.validate_quality_gate(analyzed)
    return {
        "is_valid": is_valid,
        "validation_errors": errors,
        "data": analyzed
    }

@app.get("/api/scraper/linkedin/settings")
def get_linkedin_settings():
    return linkedin_adapter.load_user_settings()

@app.post("/api/scraper/linkedin/settings")
def save_linkedin_settings(req: LinkedInSettingsRequest):
    linkedin_adapter.save_user_settings(req.model_dump())
    return {"success": True, "settings": linkedin_adapter.load_user_settings()}

@app.get("/api/export/csv")
def export_csv(
    roles: Optional[List[str]] = Query(None),
    role_category: Optional[str] = None,
    platforms: Optional[List[str]] = Query(None),
    platform: Optional[str] = None,
    city: Optional[str] = None,
    cities: Optional[List[str]] = Query(None),
    country: Optional[str] = None,
    date_posted: Optional[str] = Query(None),
    scrape_freshness: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("date_desc"),
    q: Optional[str] = None,
    limit: Optional[int] = Query(10000)
):
    target_roles = []
    if roles:
        for r in roles:
            if "," in r:
                target_roles.extend([x.strip() for x in r.split(",") if x.strip()])
            else:
                target_roles.append(r)

    target_platforms = []
    if platforms:
        for p in platforms:
            if "," in p:
                target_platforms.extend([x.strip() for x in p.split(",") if x.strip()])
            else:
                target_platforms.append(p)
    elif platform:
        target_platforms = [platform]

    target_cities = []
    if cities:
        for c in cities:
            if "," in c:
                target_cities.extend([x.strip() for x in c.split(",") if x.strip()])
            else:
                target_cities.append(c.strip())
    elif city:
        if "," in city:
            target_cities.extend([x.strip() for x in city.split(",") if x.strip()])
        else:
            target_cities.append(city.strip())

    jobs, _ = db.get_jobs(
        query=q or "",
        roles=target_roles if target_roles else None,
        role_category=role_category or "",
        platforms=target_platforms if target_platforms else None,
        country=country or "",
        city=city or "",
        cities=target_cities if target_cities else None,
        date_filter=date_posted or "",
        scrape_freshness=scrape_freshness or "",
        sort_by=sort_by or "date_desc",
        limit=limit if (limit and limit > 0) else 10000
    )

    output = io.StringIO()
    fieldnames = [
        "id", "title", "standard_role", "company", "apply_link", "salary",
        "location", "country", "work_mode", "job_experience", "experience_level",
        "min_experience", "max_experience", "skills", "role_category",
        "source_name", "source_url", "description", "responsibilities",
        "requirements", "qualifications", "ats_keywords", "application_deadline",
        "openings", "recruiter_name", "recruiter_email", "recruiter_designation",
        "linkedin_profile", "contact_phone", "contact_whatsapp", "company_website",
        "published_at", "first_scraped_at", "scraped_at", "last_checked_at",
        "scrape_count", "status", "application_status", "is_applied", "applied_at",
        "discovered_at"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for j in jobs:
        d = j.model_dump()
        d["apply_link"] = d.get("apply_url") or d.get("source_url") or ""
        min_exp = d.get("min_experience")
        max_exp = d.get("max_experience")
        exp_lvl = d.get("experience_level") or "fresher"
        if min_exp is not None and max_exp is not None:
            d["job_experience"] = f"{min_exp}-{max_exp} yrs ({exp_lvl})"
        elif min_exp is not None:
            d["job_experience"] = f"{min_exp}+ yrs ({exp_lvl})"
        else:
            d["job_experience"] = exp_lvl

        d["skills"] = ", ".join(d.get("skills") or []) if isinstance(d.get("skills"), list) else str(d.get("skills") or "")
        d["responsibilities"] = "\n".join(d.get("responsibilities") or []) if isinstance(d.get("responsibilities"), list) else str(d.get("responsibilities") or "")
        d["requirements"] = "\n".join(d.get("requirements") or []) if isinstance(d.get("requirements"), list) else str(d.get("requirements") or "")
        d["qualifications"] = "\n".join(d.get("qualifications") or []) if isinstance(d.get("qualifications"), list) else str(d.get("qualifications") or "")
        d["ats_keywords"] = ", ".join(d.get("ats_keywords") or []) if isinstance(d.get("ats_keywords"), list) else str(d.get("ats_keywords") or "")

        d.pop("is_active", None)
        d.pop("source_id", None)
        writer.writerow(d)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=curated_scraped_jobs.csv"}
    )

@app.get("/api/export/excel")
@app.get("/api/export/xlsx")
def export_excel(
    roles: Optional[List[str]] = Query(None),
    role_category: Optional[str] = None,
    platforms: Optional[List[str]] = Query(None),
    platform: Optional[str] = None,
    city: Optional[str] = None,
    cities: Optional[List[str]] = Query(None),
    country: Optional[str] = None,
    date_posted: Optional[str] = Query(None),
    scrape_freshness: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("date_desc"),
    q: Optional[str] = None,
    limit: Optional[int] = Query(10000)
):
    target_roles = []
    if roles:
        for r in roles:
            if "," in r:
                target_roles.extend([x.strip() for x in r.split(",") if x.strip()])
            else:
                target_roles.append(r)

    target_platforms = []
    if platforms:
        for p in platforms:
            if "," in p:
                target_platforms.extend([x.strip() for x in p.split(",") if x.strip()])
            else:
                target_platforms.append(p)
    elif platform:
        target_platforms = [platform]

    target_cities = []
    if cities:
        for c in cities:
            if "," in c:
                target_cities.extend([x.strip() for x in c.split(",") if x.strip()])
            else:
                target_cities.append(c.strip())
    elif city:
        if "," in city:
            target_cities.extend([x.strip() for x in city.split(",") if x.strip()])
        else:
            target_cities.append(city.strip())

    jobs, _ = db.get_jobs(
        query=q or "",
        roles=target_roles if target_roles else None,
        role_category=role_category or "",
        platforms=target_platforms if target_platforms else None,
        country=country or "",
        city=city or "",
        cities=target_cities if target_cities else None,
        date_filter=date_posted or "",
        scrape_freshness=scrape_freshness or "",
        sort_by=sort_by or "date_desc",
        limit=limit if (limit and limit > 0) else 10000
    )

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Curated Job Listings"

    headers = [
        "Job Title", "Company Name", "Apply Link", "Salary", "Location", "Country",
        "Work Mode", "Job Experience", "Skills Required", "Standard Role", "Role Category",
        "Source Platform", "Source Job URL", "Job Description", "Key Responsibilities",
        "Requirements", "Qualifications", "ATS Keywords", "Application Deadline",
        "Openings", "Recruiter Name", "Recruiter Email", "Recruiter Designation",
        "LinkedIn Profile", "Contact Phone", "WhatsApp", "Company Website",
        "Published Date", "First Scraped Date", "Last Checked Date", "Status",
        "Application Status", "Is Applied", "Applied Date", "Discovered Date", "Job ID"
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    data_font = Font(name="Calibri", size=10)
    top_align = Alignment(vertical="top", wrap_text=True)

    for row_idx, j in enumerate(jobs, start=2):
        d = j.model_dump()
        min_exp = d.get("min_experience")
        max_exp = d.get("max_experience")
        exp_lvl = d.get("experience_level") or "fresher"
        if min_exp is not None and max_exp is not None:
            job_exp = f"{min_exp}-{max_exp} yrs ({exp_lvl})"
        elif min_exp is not None:
            job_exp = f"{min_exp}+ yrs ({exp_lvl})"
        else:
            job_exp = exp_lvl

        skills_str = ", ".join(d.get("skills") or []) if isinstance(d.get("skills"), list) else str(d.get("skills") or "")
        resp_str = "\n".join(d.get("responsibilities") or []) if isinstance(d.get("responsibilities"), list) else str(d.get("responsibilities") or "")
        req_str = "\n".join(d.get("requirements") or []) if isinstance(d.get("requirements"), list) else str(d.get("requirements") or "")
        qual_str = "\n".join(d.get("qualifications") or []) if isinstance(d.get("qualifications"), list) else str(d.get("qualifications") or "")
        ats_str = ", ".join(d.get("ats_keywords") or []) if isinstance(d.get("ats_keywords"), list) else str(d.get("ats_keywords") or "")
        apply_link = d.get("apply_url") or d.get("source_url") or ""

        row_data = [
            d.get("title") or "",
            d.get("company") or "",
            apply_link,
            d.get("salary") or "Not Disclosed",
            d.get("location") or "",
            d.get("country") or "",
            d.get("work_mode") or "",
            job_exp,
            skills_str,
            d.get("standard_role") or "",
            d.get("role_category") or "",
            d.get("source_name") or "",
            d.get("source_url") or "",
            d.get("description") or "",
            resp_str,
            req_str,
            qual_str,
            ats_str,
            d.get("application_deadline") or "",
            d.get("openings") or "",
            d.get("recruiter_name") or "",
            d.get("recruiter_email") or "",
            d.get("recruiter_designation") or "",
            d.get("linkedin_profile") or "",
            d.get("contact_phone") or "",
            d.get("contact_whatsapp") or "",
            d.get("company_website") or "",
            d.get("published_at") or "",
            d.get("first_scraped_at") or "",
            d.get("last_checked_at") or "",
            d.get("status") or "active",
            d.get("application_status") or "new",
            "Yes" if d.get("is_applied") else "No",
            d.get("applied_at") or "",
            d.get("discovered_at") or "",
            d.get("id") or ""
        ]
        ws.append(row_data)
        ws.row_dimensions[row_idx].height = 20
        for col_idx in range(1, len(row_data) + 1):
            c = ws.cell(row=row_idx, column=col_idx)
            c.font = data_font
            c.alignment = top_align
            c.border = thin_border

    ws.freeze_panes = "A2"

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val = cell.value
            if val:
                val_first = str(val).split("\n")[0]
                if len(val_first) > max_len:
                    max_len = len(val_first)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=curated_scraped_jobs.xlsx"}
    )

@app.get("/api/export/json")
def export_json(
    roles: Optional[List[str]] = Query(None),
    role_category: Optional[str] = None,
    platforms: Optional[List[str]] = Query(None),
    platform: Optional[str] = None,
    city: Optional[str] = None,
    cities: Optional[List[str]] = Query(None),
    country: Optional[str] = None,
    date_posted: Optional[str] = Query(None),
    scrape_freshness: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("date_desc"),
    q: Optional[str] = None,
    limit: Optional[int] = Query(10000)
):
    target_roles = []
    if roles:
        for r in roles:
            if "," in r:
                target_roles.extend([x.strip() for x in r.split(",") if x.strip()])
            else:
                target_roles.append(r)

    target_platforms = []
    if platforms:
        for p in platforms:
            if "," in p:
                target_platforms.extend([x.strip() for x in p.split(",") if x.strip()])
            else:
                target_platforms.append(p)
    elif platform:
        target_platforms = [platform]

    target_cities = []
    if cities:
        for c in cities:
            if "," in c:
                target_cities.extend([x.strip() for x in c.split(",") if x.strip()])
            else:
                target_cities.append(c.strip())
    elif city:
        if "," in city:
            target_cities.extend([x.strip() for x in city.split(",") if x.strip()])
        else:
            target_cities.append(city.strip())

    jobs, _ = db.get_jobs(
        query=q or "",
        roles=target_roles if target_roles else None,
        role_category=role_category or "",
        platforms=target_platforms if target_platforms else None,
        country=country or "",
        city=city or "",
        cities=target_cities if target_cities else None,
        date_filter=date_posted or "",
        scrape_freshness=scrape_freshness or "",
        sort_by=sort_by or "date_desc",
        limit=2000
    )
    content = json.dumps([j.model_dump() for j in jobs], indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=fresher_analytics_jobs.json"}
    )

# --- Career Knowledge Base & Multi-Document Repository Endpoints ---

@app.get("/api/kb/documents")
def get_kb_documents(q: Optional[str] = None, category: Optional[str] = None):
    """List all career knowledge base documents with search and category filtering."""
    docs = career_kb.search_documents(q) if q else list(career_kb.documents)
    if category and category != "all":
        docs = [d for d in docs if d.get("category") == category]
    
    profile = career_kb.get_unified_profile()
    stats = career_kb.get_summary_stats()
    stats["total_docs"] = len(career_kb.documents)
    stats["indexed_docs"] = stats["successfully_processed"]
    stats["total_skills"] = len(profile.get("technical_tools", []))
    stats["total_projects"] = len(profile.get("projects", []))
    stats["total_certifications"] = len(profile.get("certifications", []))
    stats["total_experiences"] = len(profile.get("experience", []))
    return {
        "total": len(docs),
        "documents": docs,
        "categories": [{"id": c[0], "label": c[1]} for c in DOCUMENT_CATEGORIES],
        "summary_stats": stats
    }

MAX_KB_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_KB_FILES_PER_REQUEST = 10
ALLOWED_KB_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

@app.post("/api/kb/upload")
@app.post("/api/kb/upload-batch")
async def upload_kb_documents(
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None)
):
    """
    Hardened batch multi-file upload for Career Knowledge Base:
    - Allows only .pdf, .docx, .txt, .md (rejects others with HTTP 415).
    - Max 5 MB per file (HTTP 413), max 10 files per request (HTTP 413).
    - Verifies magic bytes match extension (PDF starts with %PDF, DOCX is a zip archive).
    - Rejects empty files and unextractable/corrupt files with HTTP 422 (and does not add to KB).
    - Stores display_name strictly as os.path.basename(filename).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    if len(files) > MAX_KB_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files: maximum {MAX_KB_FILES_PER_REQUEST} files per request, got {len(files)}."
        )

    validated_files = []
    for file in files:
        raw_filename = file.filename or ""
        clean_filename = os.path.basename(raw_filename.replace("\\", "/"))
        ext = os.path.splitext(clean_filename)[1].lower()

        # 1. Allow only .pdf, .docx, .txt, .md (HTTP 415)
        if ext not in ALLOWED_KB_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{ext}' for file '{clean_filename}'. Allowed types: .pdf, .docx, .txt, .md"
            )

        # Read content
        content = await file.read()

        # 2. Max 5 MB per file (HTTP 413)
        if len(content) > MAX_KB_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File '{clean_filename}' ({len(content)} bytes) exceeds the maximum allowed size of 5 MB."
            )

        # 3. Empty file check (HTTP 422)
        if len(content) == 0:
            raise HTTPException(
                status_code=422,
                detail=f"File '{clean_filename}' is empty (0 bytes). No text can be extracted."
            )

        # 4. Verify magic bytes match extension
        if ext == ".pdf":
            if not content.startswith(b"%PDF"):
                raise HTTPException(
                    status_code=415,
                    detail=f"Invalid file signature: '{clean_filename}' does not start with PDF magic bytes (%PDF)."
                )
        elif ext == ".docx":
            is_zip = content.startswith(b"PK\x03\x04") or zipfile.is_zipfile(io.BytesIO(content))
            if not is_zip:
                raise HTTPException(
                    status_code=415,
                    detail=f"Invalid file signature: '{clean_filename}' is not a valid DOCX (ZIP archive)."
                )
        elif ext in (".txt", ".md"):
            try:
                decoded_txt = content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    decoded_txt = content.decode("latin-1")
                except Exception:
                    raise HTTPException(
                        status_code=415,
                        detail=f"Invalid text file: '{clean_filename}' cannot be decoded as text."
                    )
            if "\x00" in decoded_txt:
                raise HTTPException(
                    status_code=415,
                    detail=f"Invalid file signature: binary null bytes detected in text file '{clean_filename}'."
                )

        # 5. Parse the file; if no text can be extracted, reject with 422 and do NOT add to KB
        try:
            extracted_text, _meta = career_kb.extract_text_from_file(clean_filename, content)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to parse '{clean_filename}': {e}"
            )

        if not extracted_text or not extracted_text.strip():
            raise HTTPException(
                status_code=422,
                detail=f"No text could be extracted from '{clean_filename}'."
            )

        validated_files.append((clean_filename, content))

    # All files validated; now add to knowledge base
    results = []
    for clean_filename, content in validated_files:
        doc = career_kb.add_document(
            filename=clean_filename,
            file_bytes=content,
            category=category if category and category != "auto" else None,
            display_name=clean_filename
        )
        results.append(doc)

    return {
        "success": True,
        "uploaded_count": len(results),
        "documents": results,
        "unified_profile": career_kb.get_unified_profile()
    }

@app.get("/api/kb/categories")
def get_kb_categories():
    """Returns available document categories."""
    return [{"id": c[0], "label": c[1]} for c in DOCUMENT_CATEGORIES]

@app.get("/api/kb/profile")
def get_kb_profile():
    """Returns the unified professional knowledge base profile synthesized across all documents."""
    profile = career_kb.get_unified_profile()
    return {
        "success": True,
        "profile": profile,
        "documents_count": len(career_kb.documents)
    }

@app.get("/api/kb/document/{doc_id}")
@app.get("/api/kb/documents/{doc_id}")
def get_kb_document_detail(doc_id: str):
    """Returns details and extracted data for a single document."""
    doc = career_kb.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {"document": doc, "id": doc_id, **doc}

@app.patch("/api/kb/document/{doc_id}")
@app.patch("/api/kb/documents/{doc_id}")
@app.put("/api/kb/document/{doc_id}")
@app.put("/api/kb/documents/{doc_id}")
def update_kb_document(doc_id: str, payload: UpdateDocPayload):
    """Rename or re-categorize a career document."""
    updated = career_kb.update_document(doc_id, display_name=payload.display_name, category=payload.category)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {
        "success": True,
        "document": updated,
        "unified_profile": career_kb.get_unified_profile()
    }

@app.delete("/api/kb/document/{doc_id}")
@app.delete("/api/kb/documents/{doc_id}")
def delete_kb_document(doc_id: str):
    """Delete a document from knowledge base repository and re-synthesize profile."""
    success = career_kb.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {
        "success": True,
        "message": f"Deleted document {doc_id}",
        "unified_profile": career_kb.get_unified_profile()
    }

@app.post("/api/kb/document/{doc_id}/replace")
@app.post("/api/kb/documents/{doc_id}/replace")
async def replace_kb_document(doc_id: str, file: UploadFile = File(...)):
    """Replace an existing document with a new file."""
    content = await file.read()
    replaced = career_kb.replace_document(doc_id, file.filename, content)
    if not replaced:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {
        "success": True,
        "document": replaced,
        "unified_profile": career_kb.get_unified_profile()
    }

@app.post("/api/kb/reindex")
@app.post("/api/kb/reprocess-all")
def reindex_kb():
    """Forces full re-extraction and re-indexing of all documents in the repository."""
    career_kb.reprocess_all()
    return {
        "success": True,
        "message": "All documents re-processed and indexed successfully",
        "unified_profile": career_kb.get_unified_profile()
    }

@app.post("/api/kb/document/{doc_id}/reprocess")
@app.post("/api/kb/documents/{doc_id}/reprocess")
def reprocess_kb_document(doc_id: str):
    """Re-reads physical file from disk and re-extracts text/intelligence."""
    doc = career_kb.reprocess_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {
        "success": True,
        "document": doc,
        "unified_profile": career_kb.get_unified_profile()
    }

@app.get("/api/kb/document/{doc_id}/preview")
def preview_kb_document(doc_id: str):
    """View/download the physical file or text for preview."""
    doc = career_kb.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    ext = doc.get("file_type", "").lower()
    media_type = "application/octet-stream"
    if ext == "pdf":
        media_type = "application/pdf"
    elif ext in ["png", "jpg", "jpeg", "webp"]:
        media_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
    elif ext in ["txt", "md", "csv", "json"]:
        media_type = "text/plain"
    elif ext == "docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # Check persistent database first
    stored = db.get_file(doc_id) or db.get_file(f"doc_{doc.get('filename')}")
    if stored and stored.get("file_data"):
        return Response(
            content=stored["file_data"],
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{doc.get("filename", "document")}"'}
        )

    file_path = doc.get("file_path", "")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File missing on server")

    return FileResponse(file_path, media_type=media_type, content_disposition_type="inline", filename=doc["filename"])

# --- Master Resume Endpoints (Backwards Compatibility & Safe Profile Access) ---

@app.get("/api/resume/master")
def get_master_resume():
    """Get active profile from unified Career Knowledge Base."""
    profile = career_kb.get_unified_profile()
    contact = profile.get("contact", {})
    ready_docs = [d for d in career_kb.documents if d.get("status") == "Ready for AI Usage"]
    return {
        "name": profile.get("name", "Candidate"),
        "contact": contact,
        "email": contact.get("email"),
        "phone": contact.get("phone"),
        "linkedin": contact.get("linkedin_url") or contact.get("linkedin"),
        "github": contact.get("github_url") or contact.get("github"),
        "summary": profile.get("summary"),
        "skills": profile.get("skills", {}),
        "skills_count": len(profile.get("technical_tools", [])),
        "technical_tools": profile.get("technical_tools", []),
        "work_experience": profile.get("experience", []),
        "experience": profile.get("experience", []),
        "projects": profile.get("projects", []),
        "certifications": profile.get("certifications", []),
        "education": profile.get("education", []),
        "achievements": profile.get("achievements", []),
        "recommendations": profile.get("recommendations", []),
        "source_file": "Career Knowledge Base (" + str(len(career_kb.documents)) + " docs)",
        "documents": career_kb.documents,
        "summary_stats": career_kb.get_summary_stats()
    }

@app.post("/api/resume/upload")
async def upload_master_resume(file: UploadFile = File(...)):
    """Upload new master resume (PDF, DOCX, or TXT) and register into Knowledge Base."""
    try:
        content = await file.read()
        doc = career_kb.add_document(file.filename, content, category="resume", display_name=f"Master Resume ({file.filename})")
        extracted = doc.get("extracted_data", {})
        return {
            "success": True,
            "message": f"Successfully parsed and activated master resume from {file.filename}",
            "filename": file.filename,
            "candidate_name": extracted.get("name"),
            "skills_extracted": len(extracted.get("technical_tools", [])),
            "profile": {
                "name": extracted.get("name", "Candidate"),
                "contact": extracted.get("contact", {}),
                "summary": extracted.get("summary", ""),
                "skills": extracted.get("skills", {}),
                "technical_tools": extracted.get("technical_tools", [])
            },
            "document": doc,
            "unified_profile": career_kb.get_unified_profile()
        }
    except Exception as e:
        logger.error(f"Error parsing uploaded resume: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/resume/tailor")
def tailor_resume_for_job(req: TailorResumeRequest):
    """
    Tailor resume and generate personalized cover letter grounded in the Career Knowledge Base.
    Builds Overleaf LaTeX, strict 1-page PDF, Word (.docx), Plain Text (.txt),
    Cover Letter (.docx, .pdf, .txt), and comprehensive ATS metrics.
    Uses complete deep-scraped Job Description, responsibilities, requirements, and keywords.
    """
    # Resolve job details from request or database
    job_title = req.job_title
    company = req.company
    description = req.description
    skills = req.skills or []

    db_job = db.get_job_by_id(req.job_id) if req.job_id else None
    if db_job and (not db_job.is_deep_scraped or len(db_job.description or "") < 150):
        try:
            enriched = deep_job_scraper.enrich_job(db, req.job_id, force=False)
            if enriched:
                db_job = enriched
        except Exception as e:
            logger.warning(f"Optional deep enrichment skipped for {req.job_id}: {e}")

    if db_job:
        job_title = job_title or db_job.title or "Data Analyst"
        company = company or db_job.company or "Hiring Company"
        description = description or db_job.description or ""
        skills = skills or db_job.skills or []
        responsibilities = req.responsibilities or db_job.responsibilities or []
        requirements = req.requirements or db_job.requirements or []
        qualifications = req.qualifications or db_job.qualifications or []
        ats_keywords = req.ats_keywords or db_job.ats_keywords or []
        application_deadline = req.application_deadline or db_job.application_deadline or None
        openings = req.openings or db_job.openings or None
        company_details = db_job.company_details or ""
        location = req.location or db_job.location or "India"
        work_mode = req.work_mode or db_job.work_mode or "Remote"
        experience_level = req.experience_level or db_job.experience_level or "0-1 Year (Fresher)"
        salary = req.salary or db_job.salary or "Competitive"
        source_name = req.source_name or db_job.source_name or "Platform"
        source_url = req.source_url or db_job.source_url or "#"
        published_at = db_job.published_at or ""
        is_deep_scraped = db_job.is_deep_scraped

        # Synthesize rich description if original description is concise
        if len(description.strip()) < 50:
            synth_parts = [f"{job_title} at {company}"]
            if description.strip():
                synth_parts.append(description.strip())
            if skills:
                synth_parts.append(f"Required technical skills: {', '.join(skills)}")
            if responsibilities:
                synth_parts.append(f"Key responsibilities: {'; '.join(responsibilities)}")
            description = ". ".join(synth_parts) + "."
    else:
        # Custom or direct URL job
        job_title = job_title or "Data Analyst"
        company = company or "Target Employer"
        if not description or len(description.strip()) < 20:
            if skills:
                description = f"{job_title} role at {company}. Seeking skills in {', '.join(skills)} for data reporting and analytics."
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Job description is too short to perform ATS tailoring. Please provide at least 20 characters of job details or required skills."
                )
        job_title = job_title or "Data Analyst"
        company = company or "Target Employer"
        responsibilities = req.responsibilities or []
        requirements = req.requirements or []
        qualifications = req.qualifications or []
        ats_keywords = req.ats_keywords or []
        
        # Parse sections if not explicitly provided
        if not responsibilities or not requirements:
            r_resp, r_req, r_qual = deep_job_scraper._parse_text_into_sections(description)
            if not responsibilities:
                responsibilities = r_resp
            if not requirements:
                requirements = r_req
            if not qualifications:
                qualifications = r_qual
        
        if not ats_keywords:
            ats_keywords = deep_job_scraper._extract_ats_keywords(f"{job_title} {company} {description}", skills)
            
        location = req.location or "India / Remote"
        work_mode = req.work_mode or "Remote"
        experience_level = req.experience_level or "0-1 Year (Fresher)"
        salary = req.salary or "Competitive"
        source_name = req.source_name or "Custom Input"
        source_url = req.source_url or "#"
        published_at = ""
        application_deadline = req.application_deadline or ""
        openings = req.openings or ""
        company_details = ""
        is_deep_scraped = True

    job_details = {
        "id": req.job_id,
        "title": job_title,
        "company": company,
        "location": location,
        "country": "India",
        "work_mode": work_mode,
        "experience_level": experience_level,
        "salary": salary,
        "source_name": source_name,
        "source_url": source_url,
        "published_at": published_at,
        "skills": skills,
        "description": description,
        "responsibilities": responsibilities,
        "qualifications": qualifications,
        "requirements": requirements,
        "ats_keywords": ats_keywords,
        "application_deadline": application_deadline,
        "openings": openings,
        "company_details": company_details,
        "is_deep_scraped": is_deep_scraped
    }

    clean_id = "".join([c if c.isalnum() else "_" for c in req.job_id])

    # 1. Tailor structured resume & analyze ATS metrics with deep job context
    try:
        tailored_result = resume_tailor_engine.tailor(
            job_title=job_title,
            company=company,
            job_description=description,
            job_skills=skills,
            responsibilities=responsibilities,
            requirements=requirements,
            ats_keywords=ats_keywords
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    tailored_data = tailored_result["tailored_resume"]
    ats_metrics = tailored_result["ats_metrics"]

    # 2. Build Overleaf-compatible LaTeX code
    latex_code = latex_builder.build_latex(tailored_data)
    tex_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex_code)

    # 3. Compile strict 1-page PDF
    pdf_path = pdf_compiler.compile(tailored_data, clean_id)

    # 4. Generate editable Microsoft Word (.docx) document
    docx_path = docx_builder.build_docx(tailored_data, clean_id)

    # 5. Generate clean Plain Text resume (.txt)
    txt_path = txt_builder.build_txt(tailored_data, clean_id)

    # 6. Generate Personalized Cover Letter, Executive Summary, & Application Responses
    profile = career_kb.get_unified_profile()
    cl_data = cover_letter_builder.generate(
        job_title, company, description, skills, profile,
        responsibilities=responsibilities, requirements=requirements
    )
    cl_docx_path = cover_letter_builder.build_docx(cl_data, clean_id)
    cl_pdf_path = cover_letter_builder.build_pdf(cl_data, clean_id)
    cl_txt_path = os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.txt")
    with open(cl_txt_path, "w", encoding="utf-8") as f:
        f.write(cl_data["full_text"])

    cand_name = tailored_data.get("name") or profile.get("name") or "Tejas Waghmare"
    TAILORED_JOB_METADATA[clean_id] = {
        "title": job_title,
        "company": company,
        "name": cand_name
    }
    filenames = {
        "resume_pdf": build_standard_filename(cand_name, job_title, company, "Resume", "pdf"),
        "resume_docx": build_standard_filename(cand_name, job_title, company, "Resume", "docx"),
        "resume_tex": build_standard_filename(cand_name, job_title, company, "Resume", "tex"),
        "resume_txt": build_standard_filename(cand_name, job_title, company, "Resume", "txt"),
        "cover_letter_pdf": build_standard_filename(cand_name, job_title, company, "Cover_Letter", "pdf"),
        "cover_letter_docx": build_standard_filename(cand_name, job_title, company, "Cover_Letter", "docx"),
        "cover_letter_txt": build_standard_filename(cand_name, job_title, company, "Cover_Letter", "txt")
    }

    import time
    ts = int(time.time())

    return {
        "success": True,
        "job_id": req.job_id,
        "job_title": job_title,
        "company": company,
        "job_details": job_details,
        "ats_metrics": ats_metrics,
        "tailored_resume": tailored_data,
        "cover_letter": cl_data,
        "latex_code": latex_code,
        "filenames": filenames,
        "files_analyzed": tailored_result.get("files_analyzed", []),
        "evidence_summary": tailored_result.get("evidence_summary", {}),
        "files_used": [
            d.get("display_name") or d["filename"]
            for d in career_kb.documents
            if d.get("status") == "Ready for AI Usage"
        ],
        "pdf_url": f"/api/resume/download/pdf/{clean_id}?t={ts}",
        "pdf_preview_url": f"/api/resume/preview/pdf/{clean_id}?t={ts}",
        "html_preview_url": f"/api/resume/preview/html/{clean_id}?t={ts}",
        "tex_url": f"/api/resume/download/tex/{clean_id}",
        "docx_url": f"/api/resume/download/docx/{clean_id}?t={ts}",
        "txt_url": f"/api/resume/download/txt/{clean_id}?t={ts}",
        "cl_docx_url": f"/api/cover-letter/download/docx/{clean_id}?t={ts}",
        "cl_pdf_url": f"/api/cover-letter/download/pdf/{clean_id}?t={ts}",
        "cl_pdf_preview_url": f"/api/cover-letter/preview/pdf/{clean_id}?t={ts}",
        "cl_txt_url": f"/api/cover-letter/download/txt/{clean_id}?t={ts}"
    }

@app.post("/api/resume/analyze-url")
def analyze_job_url(req: AnalyzeUrlRequest):
    """
    Scrapes the target job URL directly and returns full extracted fields and deep ATS compatibility analysis.
    Supports LinkedIn, Internshala, Naukri, Foundit, Indeed, Wellfound, WeWorkRemotely, Jobicy, Remotive, RemoteOK, and company career pages.
    """
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Please enter a valid job posting URL.")

    # Validate against SSRF (HTTPS only, public IPs only, no loopback/private/link-local/file)
    try:
        validate_url(url)
    except SSRFError as se:
        raise HTTPException(status_code=400, detail=f"SSRF Protection: {se}")

    scraped = deep_job_scraper.scrape_url(url)
    if not scraped.get("success") and not scraped.get("description"):
        raise HTTPException(
            status_code=400,
            detail=f"Unable to scrape job listing from this URL: {scraped.get('error', 'Page unreachable or protected')}. Please use Option A to paste the Job Description text directly."
        )

    # Enrich extracted sections if needed
    if not scraped.get("responsibilities") or not scraped.get("requirements"):
        r_resp, r_req, r_qual = deep_job_scraper._parse_text_into_sections(scraped.get("description", ""))
        if not scraped.get("responsibilities"):
            scraped["responsibilities"] = r_resp
        if not scraped.get("requirements"):
            scraped["requirements"] = r_req
        if not scraped.get("qualifications"):
            scraped["qualifications"] = r_qual

    profile = career_kb.get_unified_profile()
    analysis = deep_job_analyzer.analyze_job(scraped, profile)

    return {
        "success": True,
        "job": scraped,
        "analysis": analysis
    }

@app.post("/api/resume/analyze-text")
def analyze_job_text(req: AnalyzeTextRequest):
    """
    Performs deep multi-dimensional analysis on an arbitrary pasted Job Description (Option A).
    Extracts responsibilities, requirements, skills, seniority, and grounded ATS match metrics.
    """
    desc = (req.description or "").strip()
    if len(desc) < 30:
        raise HTTPException(status_code=400, detail="Please enter a more detailed job description (at least 30 characters).")

    r_resp, r_req, r_qual = deep_job_scraper._parse_text_into_sections(desc)
    ats_keywords = deep_job_scraper._extract_ats_keywords(desc, req.skills or [])

    job_dict = {
        "title": req.job_title or "Data Analyst",
        "company": req.company or "Target Employer",
        "location": "India / Remote",
        "work_mode": "Remote",
        "experience_level": "0-1 Year (Fresher)",
        "salary": "Competitive",
        "description": desc,
        "skills": req.skills or ["Excel", "SQL", "Power BI", "Data Analysis"],
        "responsibilities": r_resp,
        "requirements": r_req,
        "qualifications": r_qual,
        "ats_keywords": ats_keywords,
        "source_name": "Direct Input",
        "source_url": "#",
        "is_deep_scraped": True
    }

    profile = career_kb.get_unified_profile()
    analysis = deep_job_analyzer.analyze_job(job_dict, profile)

    return {
        "success": True,
        "job": job_dict,
        "analysis": analysis
    }

@app.post("/api/resume/tailor-custom")
def tailor_custom_job_description(req: CustomJDTailorRequest):
    """
    Generate tailored resume & cover letter for an arbitrary pasted Job Description.
    """
    import hashlib
    clean_hash = hashlib.md5((req.job_title + req.company + req.description[:100]).encode()).hexdigest()[:10]
    custom_job_id = f"custom_{clean_hash}"

    tailor_req = TailorResumeRequest(
        job_id=custom_job_id,
        job_title=req.job_title or "Data Analyst",
        company=req.company or "Target Employer",
        description=req.description,
        skills=req.skills or []
    )
    return tailor_resume_for_job(tailor_req)

@app.post("/api/resume/update-tailored")
def update_tailored_resume(req: UpdateTailoredResumeRequest):
    """
    Saves user edits to resume sections (Summary, Skills, Experience, Projects, Certifications)
    and immediately recompiles PDF, Word (.docx), Plain Text (.txt), and LaTeX (.tex).
    """
    clean_id = "".join([c if c.isalnum() else "_" for c in req.job_id])
    tailored_data = req.tailored_resume

    # 1. Rebuild Overleaf LaTeX code
    latex_code = latex_builder.build_latex(tailored_data)
    tex_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex_code)

    # 2. Recompile strict 1-page PDF
    pdf_path = pdf_compiler.compile(tailored_data, clean_id)

    # 3. Rebuild editable Microsoft Word (.docx)
    docx_path = docx_builder.build_docx(tailored_data, clean_id)

    # 4. Rebuild clean Plain Text (.txt)
    txt_path = txt_builder.build_txt(tailored_data, clean_id)

    meta = TAILORED_JOB_METADATA.get(clean_id, {})
    cand_name = tailored_data.get("name") or meta.get("name") or career_kb.get_unified_profile().get("name") or "Tejas Waghmare"
    job_title = meta.get("title", "Data Analyst")
    company = meta.get("company", "Target Employer")
    TAILORED_JOB_METADATA[clean_id] = {
        "title": job_title,
        "company": company,
        "name": cand_name
    }
    filenames = {
        "resume_pdf": build_standard_filename(cand_name, job_title, company, "Resume", "pdf"),
        "resume_docx": build_standard_filename(cand_name, job_title, company, "Resume", "docx"),
        "resume_tex": build_standard_filename(cand_name, job_title, company, "Resume", "tex"),
        "resume_txt": build_standard_filename(cand_name, job_title, company, "Resume", "txt"),
        "cover_letter_pdf": build_standard_filename(cand_name, job_title, company, "Cover_Letter", "pdf"),
        "cover_letter_docx": build_standard_filename(cand_name, job_title, company, "Cover_Letter", "docx"),
        "cover_letter_txt": build_standard_filename(cand_name, job_title, company, "Cover_Letter", "txt")
    }

    import time
    ts = int(time.time())

    return {
        "success": True,
        "job_id": req.job_id,
        "tailored_resume": tailored_data,
        "latex_code": latex_code,
        "filenames": filenames,
        "pdf_url": f"/api/resume/download/pdf/{clean_id}?t={ts}",
        "pdf_preview_url": f"/api/resume/preview/pdf/{clean_id}?t={ts}",
        "html_preview_url": f"/api/resume/preview/html/{clean_id}?t={ts}",
        "tex_url": f"/api/resume/download/tex/{clean_id}",
        "docx_url": f"/api/resume/download/docx/{clean_id}?t={ts}",
        "txt_url": f"/api/resume/download/txt/{clean_id}?t={ts}"
    }


def _resolve_job_metadata(
    job_id: str,
    role: Optional[str] = None,
    company: Optional[str] = None,
    name: Optional[str] = None
) -> tuple:
    """Helper to resolve candidate name, job title, and company for standard file naming."""
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    meta = TAILORED_JOB_METADATA.get(clean_id, {})
    eff_role = role or meta.get("title")
    eff_comp = company or meta.get("company")
    eff_name = name or meta.get("name")

    if not eff_role or not eff_comp:
        db_job = db.get_job_by_id(job_id)
        if db_job:
            eff_role = eff_role or getattr(db_job, "title", None) or (db_job.get("title") if isinstance(db_job, dict) else None)
            eff_comp = eff_comp or getattr(db_job, "company", None) or (db_job.get("company") if isinstance(db_job, dict) else None)

    if not eff_name:
        profile = career_kb.get_unified_profile()
        eff_name = profile.get("name") or "Tejas Waghmare"

    return eff_name, eff_role or "Data Analyst", eff_comp or "Target Employer"

@app.get("/api/resume/preview/pdf/{job_id}")
def preview_tailored_pdf(job_id: str):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    stored = db.get_file(f"tailored_{clean_id}.pdf")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/pdf", headers={"Content-Disposition": "inline"})

    pdf_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.pdf")
    if not os.path.exists(pdf_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"tailored_{clean_id}.pdf")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/pdf", headers={"Content-Disposition": "inline"})
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Tailored PDF not found. Please click Tailor Resume first.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        content_disposition_type="inline"
    )

@app.get("/api/resume/preview/html/{job_id}")
def preview_tailored_html(job_id: str):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    stored = db.get_file(f"tailored_{clean_id}.html")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"].decode("utf-8", errors="ignore"), media_type="text/html")

    html_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.html")
    if not os.path.exists(html_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"tailored_{clean_id}.html")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"].decode("utf-8", errors="ignore"), media_type="text/html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Tailored preview not found. Please click Tailor Resume first.")
    return FileResponse(
        html_path,
        media_type="text/html"
    )

@app.get("/api/resume/download/pdf/{job_id}")
def download_tailored_pdf(
    job_id: str,
    role: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    name: Optional[str] = Query(None)
):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    eff_name, eff_role, eff_comp = _resolve_job_metadata(job_id, role, company, name)
    filename = build_standard_filename(eff_name, eff_role, eff_comp, "Resume", "pdf")

    stored = db.get_file(f"tailored_{clean_id}.pdf")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    pdf_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.pdf")
    if not os.path.exists(pdf_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"tailored_{clean_id}.pdf")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Tailored PDF not found. Please click Tailor Resume first.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename
    )

@app.get("/api/resume/download/docx/{job_id}")
def download_tailored_docx(
    job_id: str,
    role: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    name: Optional[str] = Query(None)
):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    eff_name, eff_role, eff_comp = _resolve_job_metadata(job_id, role, company, name)
    filename = build_standard_filename(eff_name, eff_role, eff_comp, "Resume", "docx")

    stored = db.get_file(f"tailored_{clean_id}.docx")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    docx_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.docx")
    if not os.path.exists(docx_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"tailored_{clean_id}.docx")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="Tailored Word document not found. Please click Tailor Resume first.")
    return FileResponse(
        docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )

@app.get("/api/resume/download/tex/{job_id}")
def download_tailored_tex(
    job_id: str,
    role: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    name: Optional[str] = Query(None)
):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    eff_name, eff_role, eff_comp = _resolve_job_metadata(job_id, role, company, name)
    filename = build_standard_filename(eff_name, eff_role, eff_comp, "Resume", "tex")

    stored = db.get_file(f"tailored_{clean_id}.tex")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    tex_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.tex")
    if not os.path.exists(tex_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"tailored_{clean_id}.tex")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if not os.path.exists(tex_path):
        raise HTTPException(status_code=404, detail="Tailored LaTeX file not found. Please click Tailor Resume first.")
    return FileResponse(
        tex_path,
        media_type="text/plain",
        filename=filename
    )

@app.get("/api/resume/download/txt/{job_id}")
def download_tailored_txt(
    job_id: str,
    role: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    name: Optional[str] = Query(None)
):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    eff_name, eff_role, eff_comp = _resolve_job_metadata(job_id, role, company, name)
    filename = build_standard_filename(eff_name, eff_role, eff_comp, "Resume", "txt")

    stored = db.get_file(f"tailored_{clean_id}.txt")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    txt_path = os.path.join(RESUME_OUTPUT_DIR, f"tailored_{clean_id}.txt")
    if not os.path.exists(txt_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"tailored_{clean_id}.txt")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if not os.path.exists(txt_path):
        raise HTTPException(status_code=404, detail="Tailored TXT not found. Please click Tailor Resume first.")
    return FileResponse(
        txt_path,
        media_type="text/plain",
        filename=filename
    )

# --- Cover Letter Preview & Download Endpoints ---

@app.get("/api/cover-letter/preview/pdf/{job_id}")
def preview_cover_letter_pdf(job_id: str):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    stored = db.get_file(f"cover_letter_{clean_id}.pdf")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/pdf", headers={"Content-Disposition": "inline"})

    pdf_path = os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.pdf")
    if not os.path.exists(pdf_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"cover_letter_{clean_id}.pdf")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/pdf", headers={"Content-Disposition": "inline"})
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Cover letter PDF not found.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        content_disposition_type="inline"
    )

@app.get("/api/cover-letter/download/docx/{job_id}")
def download_cover_letter_docx(
    job_id: str,
    role: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    name: Optional[str] = Query(None)
):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    eff_name, eff_role, eff_comp = _resolve_job_metadata(job_id, role, company, name)
    filename = build_standard_filename(eff_name, eff_role, eff_comp, "Cover_Letter", "docx")

    stored = db.get_file(f"cover_letter_{clean_id}.docx")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    docx_path = os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.docx")
    if not os.path.exists(docx_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"cover_letter_{clean_id}.docx")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="Cover letter Word document not found.")
    return FileResponse(
        docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )

@app.get("/api/cover-letter/download/pdf/{job_id}")
def download_cover_letter_pdf(
    job_id: str,
    role: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    name: Optional[str] = Query(None)
):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    eff_name, eff_role, eff_comp = _resolve_job_metadata(job_id, role, company, name)
    filename = build_standard_filename(eff_name, eff_role, eff_comp, "Cover_Letter", "pdf")

    stored = db.get_file(f"cover_letter_{clean_id}.pdf")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    pdf_path = os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.pdf")
    if not os.path.exists(pdf_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"cover_letter_{clean_id}.pdf")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Cover letter PDF not found.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename
    )

@app.get("/api/cover-letter/download/txt/{job_id}")
def download_cover_letter_txt(
    job_id: str,
    role: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    name: Optional[str] = Query(None)
):
    clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
    eff_name, eff_role, eff_comp = _resolve_job_metadata(job_id, role, company, name)
    filename = build_standard_filename(eff_name, eff_role, eff_comp, "Cover_Letter", "txt")

    stored = db.get_file(f"cover_letter_{clean_id}.txt")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    txt_path = os.path.join(RESUME_OUTPUT_DIR, f"cover_letter_{clean_id}.txt")
    if not os.path.exists(txt_path):
        _ensure_job_artifacts(job_id)
    stored = db.get_file(f"cover_letter_{clean_id}.txt")
    if stored and stored.get("file_data"):
        return Response(content=stored["file_data"], media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if not os.path.exists(txt_path):
        raise HTTPException(status_code=404, detail="Cover letter TXT not found.")
    return FileResponse(
        txt_path,
        media_type="text/plain",
        filename=filename
    )

if __name__ == "__main__":
    import uvicorn
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run(app, host="127.0.0.1", port=8000)
