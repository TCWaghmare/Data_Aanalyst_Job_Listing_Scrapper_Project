"""
Data models for jobs, platforms, and scraper metrics.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Job(BaseModel):
    id: str
    title: str
    standard_role: str
    role_category: str = "Core Analytics"
    company: str
    location: str = "Remote / Flexible"
    country: str = "Global"
    work_mode: str = "Remote"
    experience_level: str = "Fresher (0-1 yr)"
    min_experience: Optional[int] = 0
    max_experience: Optional[int] = 1
    salary: str = "Not Disclosed"
    description: str = ""
    skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    ats_keywords: List[str] = Field(default_factory=list)
    application_deadline: Optional[str] = None
    openings: Optional[str] = None
    company_details: Optional[str] = None
    department: Optional[str] = None
    employment_type: Optional[str] = None
    source_id: str
    source_name: str
    source_url: str
    published_at: Optional[str] = None
    discovered_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    first_scraped_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    scrape_count: int = 1
    status: str = "active"
    application_status: str = "new"
    is_bookmarked: bool = False
    match_score: float = 0.0
    recruiter_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_designation: Optional[str] = None
    linkedin_profile: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_whatsapp: Optional[str] = None
    apply_url: Optional[str] = None
    company_website: Optional[str] = None
    company_linkedin: Optional[str] = None
    role_match_score: Optional[int] = None
    confidence_score: Optional[int] = None
    company_logo: Optional[str] = None
    is_active: bool = True
    is_applied: bool = False
    applied_at: Optional[str] = None
    is_deep_scraped: bool = False
    extraction_status: str = "complete"

class Platform(BaseModel):
    id: str
    name: str
    category: str
    section: str
    country: str
    website: str
    search_url_template: str
    integration_type: str
    has_adapter: bool = False
    notes: str = ""

class ScrapeRun(BaseModel):
    run_id: str
    started_at: str
    finished_at: Optional[str] = None
    status: str = "running"
    platforms_scanned: List[str] = Field(default_factory=list)
    jobs_scanned: int = 0
    jobs_added: int = 0
    duplicates_skipped: int = 0
    errors_count: int = 0
    error_messages: List[str] = Field(default_factory=list)

