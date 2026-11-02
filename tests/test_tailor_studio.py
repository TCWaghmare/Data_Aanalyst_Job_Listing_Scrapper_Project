import os
import pytest
from fastapi.testclient import TestClient
from app import app
from scraper.deep_scraper import deep_job_scraper

client = TestClient(app)

def test_scrape_linkedin_job_url_guest_api():
    """Verify that LinkedIn job URLs are extracted without HTTP 999 using the public guest API."""
    url = "https://www.linkedin.com/jobs/view/4446724293"
    result = deep_job_scraper.scrape_url(url)
    assert result.get("success") is True
    assert result.get("title") != ""
    assert result.get("company") != ""
    assert len(result.get("description", "")) > 100
    assert result.get("is_deep_scraped") is True

def test_analyze_job_url_endpoint():
    """Verify POST /api/resume/analyze-url scrapes and analyzes target job URL."""
    url = "https://www.linkedin.com/jobs/view/4446724293"
    resp = client.post("/api/resume/analyze-url", json={"url": url})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "job" in data
    assert "analysis" in data
    job = data["job"]
    assert job.get("title") != ""
    assert job.get("company") != ""
    assert len(job.get("description", "")) > 100

def test_tailor_resume_from_custom_manual_jd():
    """Verify POST /api/resume/tailor generates 1-page PDF, Word, LaTeX, Cover Letter and ATS metrics from manual JD."""
    payload = {
        "job_id": "test_manual_studio_job_1",
        "job_title": "Power BI & Data Analyst",
        "company": "Apex Analytics India",
        "location": "Bengaluru, India",
        "work_mode": "Hybrid",
        "description": (
            "Apex Analytics India is seeking an entry-level Power BI & Data Analyst. "
            "Key responsibilities include designing interactive executive dashboards in Microsoft Power BI, "
            "writing complex DAX measures, transforming data in Power Query, writing SQL queries against PostgreSQL "
            "and MySQL databases, and building executive sales KPI reports. Requirements: Bachelor's degree, strong SQL, "
            "DAX, Advanced Excel (Pivot tables, XLOOKUP), and data modeling."
        ),
        "skills": ["Power BI", "DAX", "SQL", "Excel", "Data Modeling", "Power Query"]
    }

    resp = client.post("/api/resume/tailor", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data.get("job_title") == "Power BI & Data Analyst"
    assert data.get("company") == "Apex Analytics India"
    assert "ats_metrics" in data
    assert "tailored_resume" in data
    assert "cover_letter" in data
    assert "latex_code" in data
    assert data.get("pdf_url") is not None
    assert data.get("docx_url") is not None
    assert data.get("cl_pdf_url") is not None
    assert data.get("cl_docx_url") is not None

    # Verify download endpoints
    clean_id = "test_manual_studio_job_1"
    pdf_resp = client.get(f"/api/resume/download/pdf/{clean_id}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"

    docx_resp = client.get(f"/api/resume/download/docx/{clean_id}")
    assert docx_resp.status_code == 200

    cl_pdf_resp = client.get(f"/api/cover-letter/download/pdf/{clean_id}")
    assert cl_pdf_resp.status_code == 200

    cl_docx_resp = client.get(f"/api/cover-letter/download/docx/{clean_id}")
    assert cl_docx_resp.status_code == 200

