import pytest
from fastapi.testclient import TestClient
from app import app, db

client = TestClient(app)

def test_linkedin_tiny_and_long_url_ingest():
    """
    Validates that:
    1. Short lnkd.in URLs are automatically fetched, unshortened, and scraped.
    2. Long LinkedIn post URLs are parsed with accurate company, recruiter, contact email, and skills.
    3. Tailored resume & cover letter artifacts are auto-generated.
    4. Gmail outreach draft and redirection link are provided.
    """
    # 1. Ingest using short URL
    tiny_url = "https://lnkd.in/p/dg9wbyye"
    res1 = client.post("/api/scraper/linkedin/ingest", json={"post_text": tiny_url})
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
    data1 = res1.json()
    assert data1["success"] is True
    job1 = data1["job"]
    
    assert "Credence" in job1["company"]
    assert "Business Analyst" in job1["title"]
    assert "Priyanka" in (job1["recruiter_name"] or "")
    assert "Priyanka.Patil@in.credencerm.com" == job1["recruiter_email"]
    assert "9271293214" in (job1["contact_phone"] or "")
    assert any(s in job1["skills"] for s in ["Power BI", "Excel", "SQL", "DAX"])
    
    # Check outreach and Gmail details
    outreach = data1.get("outreach", {})
    assert outreach["has_email"] is True
    assert "Priyanka.Patil@in.credencerm.com" == outreach["recruiter_email"]
    assert "https://mail.google.com/mail/?view=cm" in outreach["gmail_url"]
    assert "Application for" in outreach["subject"]
    assert "github.com/TCWaghmare" in outreach["body"]
    assert "ATS-Tailored Resume" in outreach["body"]
    assert "Tailored Cover Letter" in outreach["body"]
    
    # Check download endpoints for generated artifacts
    job_id = job1["id"]
    res_pdf = client.get(f"/api/resume/download/pdf/{job_id}")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 500

    res_cl = client.get(f"/api/cover-letter/download/pdf/{job_id}")
    assert res_cl.status_code == 200
    assert res_cl.headers["content-type"] == "application/pdf"
    assert len(res_cl.content) > 500

    # 2. Ingest using long URL
    long_url = "https://www.linkedin.com/posts/priyanka-patil-84a301246_hiring-businessanalyst-dataanalytics-share-7521827624692654080-nd5z/?utm_source=share&utm_medium=member_desktop&rcm=ACoAAGMfzHEBSVO2pNsgeG8RyUfK9PHdb2ULCRg"
    res2 = client.post("/api/scraper/linkedin/ingest", json={"post_text": long_url})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    job2 = data2["job"]
    assert "Credence" in job2["company"]
    assert "Priyanka.Patil@in.credencerm.com" == job2["recruiter_email"]

