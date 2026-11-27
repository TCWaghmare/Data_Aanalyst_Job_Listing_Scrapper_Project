"""
Unit and integration tests for relevance scoring and ingest filtering.
Uses actual off-target titles discovered in the current database.
"""

import os
import sqlite3
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app import app
from scraper.models import Job
from scraper.database import Database
from scraper.relevance import (
    score_job,
    is_relevant_job,
    get_min_relevance,
    is_strong_title,
    DEFAULT_MIN_RELEVANCE,
)

client = TestClient(app)

# Actual off-target titles extracted from current jobs.db
OFF_TARGET_HARD_REJECT_TITLES = [
    # AI trainer
    "[Hiring] AI Trainer - Video Annotation @iMerit Technology",
    "AI Trainer (0-1 yr exp)",
    "Generalist AI Trainer $35 hour (0-1 yr exp)",
    "AI Trainers Network - German (0-1 yr exp)",
    "AI Trainers Network - English (0-1 yr exp)",
    "Video Collection (LATAM) - Freelance AI Trainer Project (0-1 yr exp)",
    # Video editor
    "Social Media Video Editor (0-1 yr exp)",
    # Customer support / customer service
    "Customer Support Representative (0-1 yr exp)",
    "Customer Service Chat Representative (0-1 yr exp)",
    "Customer Service Associate (Fresher / 0-1 yr)",
    # Business development
    "Business Development Executive",
    "Business Development Associate",
    "Business Development Specialist",
    "Business Development (Sales) Executive - Fresher",
    "Business Development Specialist - Fresher",
    # Telecaller
    "Junior Telecaller - Fresher",
    # Sales executive
    "Inside Sales Executive - Fresher",
    "Corporate Sales Executive - Fresher",
    "Corporate Sales Executive",
    "Junior Sales Executive - Fresher",
    "Training Sales Executive",
    "Sales Executive & Guest Experience",
    # Aggregator-page titles
    "Apply To The Best Remote Jobs From India",
    "74 Data Analytics Jobs",
]

# Actual off-target seniority titles extracted from current jobs.db
OFF_TARGET_SENIORITY_TITLES = [
    # Senior
    "Senior Procurement - Fresher",
    "Senior Financial Data Analyst - Fresher",
    # Lead
    "Lead Data Analyst - Risk Operations",
    "Team Lead - Data Analytics",
    # Manager
    "Store Manager - Fresher",
    "Corporate Sales Manager - Fresher",
    "Unit Manager (Sales) - Fresher",
    "Administration Manager - Fresher",
    # Head
    "Head Of Data & Analytics- Azure / Power BI (Noida) - Fresher",
    # Director
    "Executive Assistant To Managing Director - Pune (25-28K) - Fresher",
    "Executive Assistant To Director - Fresher",
    # Principal
    "Principal Data Analyst",
]

# Valid on-target analytics/BI/MIS fresher titles
VALID_ON_TARGET_TITLES = [
    "Junior Data Analyst (Fresher 2025/2026 Batch)",
    "Graduate Data Analyst - Supply Chain",
    "Associate Data Analyst - Risk Operations",
    "MIS Executive - City Operations",
    "MIS Executive – Sales Operations & Reporting",
    "Junior BI Analyst - Commercial Reporting",
    "Junior Power BI Developer (0-1 yr exp)",
    "Trainee Tableau Developer",
    "Junior SQL Analyst - Database Verification",
    "Data Visualization Analyst - Graduate Trainee",
    "Data Analytics Associate - Fresher",
    "Junior Analytics Engineer - Fresher (WFH)",
]


class TestRelevanceScoringHardRejects:
    """Tests that all off-target hard reject titles receive a score of 0."""

    @pytest.mark.parametrize("title", OFF_TARGET_HARD_REJECT_TITLES)
    def test_hard_reject_titles_from_current_db(self, title):
        job = {
            "title": title,
            "skills": ["SQL", "Excel", "Python"],
            "description": "Full job description exceeding 200 characters to ensure description length is not the cause of rejection. " * 3,
            "experience_level": "0-1 Years",
            "min_experience": 0,
        }
        score = score_job(job)
        assert score == 0, f"Expected 0 score for hard reject title: '{title}', got {score}"

        relevant, score_res, _ = is_relevant_job(job)
        assert relevant is False
        assert score_res == 0


class TestRelevanceScoringSeniorityRejects:
    """Tests that seniority keywords in title or experience trigger rejection (score 0)."""

    @pytest.mark.parametrize("title", OFF_TARGET_SENIORITY_TITLES)
    def test_seniority_reject_titles_from_current_db(self, title):
        job = {
            "title": title,
            "skills": ["SQL", "Power BI", "Tableau", "Python"],
            "description": "Full job description with analytics tools exceeding 200 characters. " * 3,
            "experience_level": "0-1 Years",
            "min_experience": 0,
        }
        score = score_job(job)
        assert score == 0, f"Expected 0 score for seniority reject title: '{title}', got {score}"

    def test_seniority_experience_reject_3_plus_years(self):
        # 3+ years in title
        job1 = {
            "title": "Data Analyst (3+ years experience)",
            "skills": ["SQL", "Python"],
            "description": "Analytics job description exceeding 200 characters in length for testing. " * 3,
        }
        assert score_job(job1) == 0

        # 3+ years in experience_level
        job2 = {
            "title": "Data Analyst",
            "skills": ["SQL", "Python"],
            "experience_level": "3-5 years",
            "description": "Analytics job description exceeding 200 characters in length for testing. " * 3,
        }
        assert score_job(job2) == 0

        # min_experience >= 3
        job3 = {
            "title": "Data Analyst",
            "skills": ["SQL", "Python"],
            "min_experience": 3,
            "description": "Analytics job description exceeding 200 characters in length for testing. " * 3,
        }
        assert score_job(job3) == 0

    def test_leadership_development_program_not_rejected_by_lead(self):
        # "Leadership" should NOT match the word boundary \blead\b
        title = "Technical Product Analyst, 2027 Leadership Development Program, ION Group, India"
        job = {
            "title": title,
            "skills": ["SQL", "Analytics", "Python"],
            "description": "Campus graduate hiring for technical product analyst with analytics skills. " * 3,
            "experience_level": "Fresher",
            "min_experience": 0,
        }
        score = score_job(job)
        assert score >= 50, f"Leadership Development Program should not be rejected by lead rule, got {score}"


class TestRelevanceDescriptionRule:
    """Tests that descriptions under 200 chars are rejected unless the title is a strong match."""

    def test_short_description_with_weak_title_rejected(self):
        job = {
            "title": "Office Assistant",
            "description": "Short description.",  # < 200 chars
            "skills": ["Filing", "Photocopying"],
        }
        assert len(job["description"]) < 200
        assert is_strong_title(job["title"]) is False
        assert score_job(job) == 0

    def test_short_description_with_computer_operator_rejected(self):
        job = {
            "title": "Computer/Data Entry Operator",
            "description": "Quick typing job in office.",  # < 200 chars
            "skills": ["Typing"],
        }
        assert len(job["description"]) < 200
        assert is_strong_title(job["title"]) is False
        assert score_job(job) == 0

    def test_short_description_with_strong_title_accepted(self):
        # Strong match titles like Junior Data Analyst should be accepted even if description < 200 chars
        job = {
            "title": "Junior Data Analyst",
            "description": "Hiring junior data analyst fresher with basic SQL.",  # < 200 chars
            "skills": ["SQL"],
        }
        assert len(job["description"]) < 200
        assert is_strong_title(job["title"]) is True
        score = score_job(job)
        assert score >= 50, f"Expected score >= 50 for strong title with short desc, got {score}"


class TestRelevancePositiveMatching:
    """Tests that legitimate on-target fresher analytics jobs score >= 50."""

    @pytest.mark.parametrize("title", VALID_ON_TARGET_TITLES)
    def test_valid_on_target_titles_from_current_db(self, title):
        job = {
            "title": title,
            "skills": ["SQL", "Excel", "Power BI"],
            "description": "Great fresher role involving data analysis, SQL queries, dynamic dashboards in Power BI and reporting. " * 3,
            "experience_level": "0-1 Years",
            "min_experience": 0,
        }
        score = score_job(job)
        assert score >= 50, f"Expected score >= 50 for valid title '{title}', got {score}"

    def test_pydantic_job_model_scoring(self):
        job = Job(
            id="test_model_job_01",
            title="Junior Data Analyst - Operations",
            company="Acme Corp",
            location="Pune, India",
            source_id="indeed",
            source_name="Indeed",
            source_url="https://example.com/job1",
            skills=["SQL", "Python", "Power BI"],
            description="Looking for an entry level fresher data analyst skilled in SQL, Python, and Power BI dashboards. " * 3,
            standard_role="Data Analyst",
            role_category="Core Analytics",
            experience_level="0-1 Years",
            min_experience=0,
        )
        score = score_job(job)
        assert 60 <= score <= 100
        relevant, s, reason = is_relevant_job(job)
        assert relevant is True
        assert s == score


class TestMinRelevanceThresholdEnv:
    """Tests configurable MIN_RELEVANCE from environment variable."""

    def test_default_min_relevance(self, monkeypatch):
        monkeypatch.delenv("MIN_RELEVANCE", raising=False)
        assert get_min_relevance() == DEFAULT_MIN_RELEVANCE

    def test_custom_min_relevance(self, monkeypatch):
        monkeypatch.setenv("MIN_RELEVANCE", "75")
        assert get_min_relevance() == 75

        # A job scoring 60 should pass at default (50) but fail at 75
        job = {
            "title": "MIS Executive",
            "skills": ["Excel", "MIS"],
            "description": "MIS reporting role for freshers. " * 10,
        }
        score = score_job(job)
        assert 50 <= score < 75
        assert is_relevant_job(job, min_threshold=50)[0] is True
        assert is_relevant_job(job, min_threshold=75)[0] is False


class TestIngestEnforcementAndDatabaseStorage:
    """Tests that irrelevant jobs are rejected at ingest and relevance_score is stored."""

    def test_ingest_rejection_in_save_job(self, tmp_path):
        db_file = str(tmp_path / "test_ingest.db")
        db = Database(db_path=db_file)

        # Off-target job from current DB: "Apply To The Best Remote Jobs From India"
        bad_job = Job(
            id="bad_job_01",
            title="Apply To The Best Remote Jobs From India",
            company="RemoteAggregator",
            location="Remote",
            source_id="remoteok",
            source_name="RemoteOK",
            source_url="https://remoteok.com/bad1",
            standard_role="Data Analyst",
            role_category="Core Analytics",
            description="Aggregator listing page for remote jobs",
        )

        # Attempt to save with enforce_relevance=True (ingest behavior)
        saved = db.save_job(bad_job, enforce_relevance=True)
        assert saved is False, "Irrelevant job should be rejected at ingest"

        # Verify not in database
        fetched = db.get_job_by_id("bad_job_01")
        assert fetched is None

        # Legitimate job should be saved with relevance_score
        good_job = Job(
            id="good_job_01",
            title="Junior Data Analyst (Fresher 2025/2026 Batch)",
            company="Analytics Hub",
            location="Pune, India",
            source_id="linkedin",
            source_name="LinkedIn",
            source_url="https://linkedin.com/good1",
            standard_role="Data Analyst",
            role_category="Core Analytics",
            skills=["SQL", "Power BI", "Excel"],
            description="Fresher data analyst opening for 2025/2026 batch involving SQL queries and Power BI dashboards. " * 3,
        )

        good_saved = db.save_job(good_job, enforce_relevance=True)
        assert good_saved is True

        fetched_good = db.get_job_by_id("good_job_01")
        assert fetched_good is not None
        assert fetched_good.relevance_score >= 50


class TestRelevanceSortInUI:
    """Tests relevance sorting both in database layer and via FastAPI endpoint."""

    def test_relevance_sort_order(self, tmp_path):
        db_file = str(tmp_path / "test_sort.db")
        db = Database(db_path=db_file)

        # Job with high relevance (90+)
        high_rel_job = Job(
            id="high_rel",
            title="Junior Data Analyst (0-1 yr exp)",
            company="High Match Corp",
            location="Pune, Maharashtra",
            source_id="indeed",
            source_name="Indeed",
            source_url="https://indeed.com/high",
            standard_role="Data Analyst",
            role_category="Core Analytics",
            skills=["SQL", "Power BI", "Tableau", "Excel", "Python"],
            description="Full-featured data analyst role requiring SQL, Power BI, Python, and analytics reporting. " * 3,
        )

        # Job with moderate relevance (~50-60)
        med_rel_job = Job(
            id="med_rel",
            title="MIS Executive",
            company="Med Match Corp",
            location="Mumbai, Maharashtra",
            source_id="naukri",
            source_name="Naukri",
            source_url="https://naukri.com/med",
            standard_role="MIS Analyst",
            role_category="Core Analytics",
            skills=["Excel"],
            description="MIS reporting and data entry in Excel for operations. " * 8,
        )

        db.save_job(high_rel_job)
        db.save_job(med_rel_job)

        jobs, total = db.get_jobs(sort_by="relevance")
        assert total == 2
        assert jobs[0].id == "high_rel"
        assert jobs[1].id == "med_rel"
        assert jobs[0].relevance_score >= jobs[1].relevance_score

    def test_api_jobs_relevance_sort(self):
        response = client.get("/api/jobs?sort_by=relevance&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data.get("sort_by") == "relevance"
        items = data["items"]
        if len(items) >= 2:
            scores = [item.get("relevance_score") or 0 for item in items]
            # Ensure non-ascending order of relevance scores
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1]
