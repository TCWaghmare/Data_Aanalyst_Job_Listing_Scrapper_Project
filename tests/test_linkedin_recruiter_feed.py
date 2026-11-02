"""
Tests for LinkedIn HR & Recruiter Feed Scraper, Parser, and Dedicated Platform Views.
"""

import pytest
from fastapi.testclient import TestClient
from app import app
from scraper.database import Database
from scraper.adapters.linkedin_recruiter import LinkedInRecruiterFeedAdapter

client = TestClient(app)

def test_linkedin_adapter_scraping():
    """Test that LinkedIn recruiter adapter scrapes valid fresher job objects."""
    adapter = LinkedInRecruiterFeedAdapter()
    jobs = adapter.scrape(limit=10)
    assert len(jobs) >= 5
    
    first_job = jobs[0]
    assert first_job.source_id == "linkedin_feed"
    assert "LinkedIn" in first_job.source_name
    assert first_job.experience_level == "Fresher (0-1 yr)"
    assert first_job.recruiter_name is not None
    assert first_job.recruiter_email is not None
    assert "@" in first_job.recruiter_email
    assert len(first_job.skills) > 0


def test_linkedin_adapter_post_parsing():
    """Test that raw text copied from a LinkedIn feed post parses correctly."""
    adapter = LinkedInRecruiterFeedAdapter()
    raw_post = (
        "We are hiring a Junior Data Analyst at Swiggy for our Bengaluru analytics team! "
        "Looking for freshers (0-1 yr exp) with solid SQL, Power BI and Python skills. "
        "Drop your CV to priya.sharma@swiggy.in with subject 'Data Analyst Fresher'. #hiring #freshers"
    )
    job = adapter.parse_post_text(raw_post, recruiter_name="Priya Sharma")
    assert job.source_id == "linkedin_feed"
    assert "Swiggy" in job.company
    assert job.recruiter_email == "priya.sharma@swiggy.in"
    assert job.recruiter_name == "Priya Sharma"
    assert any("sql" in s.lower() for s in job.skills)


def test_api_linkedin_feed_endpoint():
    """Test GET /api/scraper/linkedin/feed endpoint."""
    res = client.get("/api/scraper/linkedin/feed?limit=25")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "direct_email_count" in data
    assert data["total"] >= 5
    
    # Check item structure
    sample = data["items"][0]
    assert "recruiter_name" in sample
    assert "recruiter_email" in sample
    assert sample["source_id"] == "linkedin_feed"


def test_api_linkedin_ingest_endpoint():
    """Test POST /api/scraper/linkedin/ingest parses and adds recruiter post to database."""
    payload = {
        "post_text": "Hiring Associate Data Analyst (Fresher 0-1 yr) at PhonePe in Bengaluru. Email aditya.sen@phonepe.com with your resume.",
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:999999999/",
        "recruiter_name": "Aditya Sen",
        "recruiter_email": "aditya.sen@phonepe.com",
        "company": "PhonePe"
    }
    res = client.post("/api/scraper/linkedin/ingest", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "job" in data
    assert data["job"]["company"] == "PhonePe"
    assert data["job"]["recruiter_email"] == "aditya.sen@phonepe.com"

    # Verify that this job now appears in the main Fresher Jobs Explorer endpoint
    explorer_res = client.get("/api/jobs?source_id=linkedin_feed&limit=50")
    assert explorer_res.status_code == 200
    explorer_jobs = explorer_res.json()["jobs"]
    assert any("PhonePe" in j["company"] for j in explorer_jobs)


def test_api_linkedin_sync_endpoint():
    """Test POST /api/scraper/linkedin/sync on-demand scraper sync."""
    res = client.post("/api/scraper/linkedin/sync")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["scraped_count"] >= 10


def test_api_linkedin_settings():
    """Test GET and POST for LinkedIn feed settings."""
    # POST settings
    post_res = client.post("/api/scraper/linkedin/settings", json={
        "li_at": "AQEDATestCookie123456",
        "sync_enabled": True,
        "keywords": "data analyst fresher hiring"
    })
    assert post_res.status_code == 200
    assert post_res.json()["success"] is True

    # GET settings
    get_res = client.get("/api/scraper/linkedin/settings")
    assert get_res.status_code == 200
    assert get_res.json()["li_at"] == "AQEDATestCookie123456"


def test_linkedin_intelligence_agent_criteria():
    """Tests the 10-point LinkedIn Hiring Post Intelligence Agent."""
    from scraper.linkedin_intelligence import linkedin_intelligence_agent

    # 1. Valid hiring post
    cognizant_text = (
        "📢 Cognizant Hiring Freshers for Data Analyst 🚀\n"
        "Cognizant is hiring Freshers & Experienced candidates for Data Analyst role across India!\n"
        "🔗 Register Here :- https://lnkd.in/gdyQXpHR\n"
        "Experience: Freshers/Experienced\n"
        "Salary: ₹4-6 LPA\n"
        "#Jobs #Freshers #Hiring #DataAnalyst"
    )
    result = linkedin_intelligence_agent.analyze_post(
        post_text=cognizant_text,
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:7255000000000000000/",
        recruiter_name="Pallvi Kumari",
        designation="Talent Acquisition Specialist",
        linkedin_profile="https://www.linkedin.com/in/pallvikumari/"
    )
    assert result["company"] == "Cognizant"
    assert result["role_match_score"] >= 70
    assert result["confidence_score"] >= 60
    assert result["apply_url"] == "https://lnkd.in/gdyQXpHR"
    assert result["salary"] == "₹4-6 LPA"
    assert result["source"] == "LinkedIn"

    is_valid, errors = linkedin_intelligence_agent.validate_quality_gate(result)
    assert is_valid is True
    assert len(errors) == 0

    # 2. Rejection of generic feed URL
    feed_url_res = linkedin_intelligence_agent.analyze_post(
        post_text="We are hiring Data Analysts! Send resume to hr@swiggy.in",
        post_url="https://www.linkedin.com/feed/"
    )
    assert feed_url_res["post_url"] == "Post URL Extraction Failed"
    is_valid_feed, errors_feed = linkedin_intelligence_agent.validate_quality_gate(feed_url_res)
    assert is_valid_feed is False
    assert any("Actual LinkedIn post URL" in e for e in errors_feed)

    # 3. Rejection of non-hiring certification post
    cert_post = "Thrilled to share that I have completed the SQL and Tableau course on Coursera! Happy to share certificate."
    cert_res = linkedin_intelligence_agent.analyze_post(
        post_text=cert_post,
        post_url="https://www.linkedin.com/posts/student_post123"
    )
    is_valid_cert, errors_cert = linkedin_intelligence_agent.validate_quality_gate(cert_res)
    assert is_valid_cert is False
    assert cert_res["confidence_score"] < 60

    # 4. Rejection of unrelated non-analytics role
    dev_post = "We are hiring Senior Java Spring Boot Developers at Infosys! Send CV to dev@infosys.com"
    dev_res = linkedin_intelligence_agent.analyze_post(
        post_text=dev_post,
        post_url="https://www.linkedin.com/posts/infosys_dev123"
    )
    is_valid_dev, errors_dev = linkedin_intelligence_agent.validate_quality_gate(dev_res)
    assert is_valid_dev is False
    assert dev_res["role_match_score"] < 70

    # 5. Test API analyze endpoint
    api_res = client.post("/api/scraper/linkedin/analyze", json={
        "post_text": cognizant_text,
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7255000000000000000/",
        "recruiter_name": "Pallvi Kumari"
    })
    assert api_res.status_code == 200
    api_data = api_res.json()
    assert api_data["is_valid"] is True
    assert api_data["data"]["company"] == "Cognizant"
    assert api_data["data"]["role_match_score"] == 100

    # 6. Rejection of placeholder email career@abcd.com
    ph_res = linkedin_intelligence_agent.analyze_post(
        post_text="Hiring Data Analyst freshers. Send resume to career@abcd.com",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:7255000000000000001/"
    )
    assert ph_res["email"] == ""  # Stripped placeholder email!

    # 7. Ingestion endpoint with full recruiter & contact info
    ingest_res = client.post("/api/scraper/linkedin/ingest", json={
        "post_text": cognizant_text,
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7255000000000000002/",
        "recruiter_name": "Pallvi Kumari",
        "designation": "Talent Acquisition Specialist",
        "linkedin_profile": "https://www.linkedin.com/in/pallvikumari/",
        "apply_url": "https://lnkd.in/gdyQXpHR"
    })
    assert ingest_res.status_code == 200
    ingest_data = ingest_res.json()
    assert ingest_data["success"] is True
    assert ingest_data["job"]["apply_url"] == "https://lnkd.in/gdyQXpHR"
    assert ingest_data["job"]["linkedin_profile"] == "https://www.linkedin.com/in/pallvikumari/"
    assert ingest_data["job"]["recruiter_designation"] == "Talent Acquisition Specialist"


