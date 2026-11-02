import pytest
from scraper.linkedin_intelligence import linkedin_intelligence_agent
from app import is_valid_external_post_url

def test_reject_localhost_and_internal_urls():
    """Verify quality gate strictly rejects 127.0.0.1, localhost, and javascript pseudo-protocols."""
    post_text = "Hiring freshers for Junior Data Analyst role. Must know SQL and Power BI. Send resume to hr@techfirm.in."
    
    # 127.0.0.1 test
    analyzed_local = linkedin_intelligence_agent.analyze_post(post_text=post_text, post_url="http://127.0.0.1:8000/")
    is_valid, errors = linkedin_intelligence_agent.validate_quality_gate(analyzed_local)
    assert is_valid is False
    assert any("Invalid post URL" in err for err in errors)

    # javascript: pseudo-protocol test
    analyzed_js = linkedin_intelligence_agent.analyze_post(post_text=post_text, post_url="javascript:(async function(){...})()")
    is_valid_js, errors_js = linkedin_intelligence_agent.validate_quality_gate(analyzed_js)
    assert is_valid_js is False
    assert any("Invalid post URL" in err for err in errors_js)

def test_reject_generic_search_urls():
    """Verify generic LinkedIn search queries are rejected as post URLs."""
    post_text = "Urgent opening for Data Analyst. Send CV to recruiter@dataminds.com."
    search_url = "https://www.linkedin.com/search/results/content/?keywords=data%20analyst%20job%20hiring&origin=SWITCH_SEARCH_VERTICAL"
    analyzed = linkedin_intelligence_agent.analyze_post(post_text=post_text, post_url=search_url)
    is_valid, errors = linkedin_intelligence_agent.validate_quality_gate(analyzed)
    assert is_valid is False
    assert any("search results" in err.lower() or "invalid post url" in err.lower() for err in errors)

def test_reject_scraped_app_ui_phrases():
    """Verify content scraped from Job Finder's own HTML modals is disqualified."""
    junk_text = (
        "Recruiter Direct Outreach Direct hiring manager outreach draft X RECIPIENT EMAIL "
        "SUBJECT LINE MESSAGE BODY Copy Message Close Open in Email Client"
    )
    analyzed = linkedin_intelligence_agent.analyze_post(
        post_text=junk_text, 
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:7257193849182390144/"
    )
    is_valid, errors = linkedin_intelligence_agent.validate_quality_gate(analyzed)
    assert is_valid is False
    assert any("internal job finder ui text" in err.lower() or "disqualified" in err.lower() for err in errors)

def test_reject_junk_companies():
    """Verify fake company names extracted from UI words are rejected."""
    # 1. When directly passed to quality gate
    is_valid, errors = linkedin_intelligence_agent.validate_quality_gate({
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257193849182390144/",
        "company": "Outreach Direct",
        "role_match_score": 90,
        "confidence_score": 80,
        "email": "hr@validtech.in"
    })
    assert is_valid is False
    assert any("invalid company" in err.lower() for err in errors)

    # 2. When analyze_post encounters junk company, it strips it out
    analyzed = linkedin_intelligence_agent.analyze_post(
        post_text="Hiring Data Analyst freshers. SQL, Excel required. Email hr@swiggy.in.",
        company="Outreach Direct",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:7257193849182390144/"
    )
    assert analyzed["company"] != "Outreach Direct"
    assert analyzed["company"] == "Swiggy"

def test_is_valid_external_post_url_helper():
    """Verify the frontend/backend external post URL validator logic."""
    assert is_valid_external_post_url("https://www.linkedin.com/posts/priyanka-patil-84a301246_hiring-businessanalyst-dataanalytics-activity-7521827627687497728-u15u") is True
    assert is_valid_external_post_url("https://www.linkedin.com/feed/update/urn:li:activity:7257193849182390144/") is True
    assert is_valid_external_post_url("https://lnkd.in/p/dg9wbyye") is True
    
    # Invalid URLs
    assert is_valid_external_post_url("http://127.0.0.1:8000/") is False
    assert is_valid_external_post_url("http://localhost:8000/api/...") is False
    assert is_valid_external_post_url("javascript:void(0)") is False
    assert is_valid_external_post_url("Post URL Extraction Failed") is False
    assert is_valid_external_post_url("https://www.linkedin.com/feed") is False
    assert is_valid_external_post_url("https://www.linkedin.com/feed/") is False
    assert is_valid_external_post_url("https://www.linkedin.com/search/results/content/?keywords=data+analyst") is False

def test_genuine_post_acceptance():
    """Verify authentic posts with genuine links and credentials pass smoothly."""
    analyzed = linkedin_intelligence_agent.analyze_post(
        post_text="📢 WE'RE HIRING | BUSINESS ANALYST – DATA ANALYTICS\nCredence Global Solutions | Kharadi, Pune\nSend resume to: Priyanka.Patil@in.credencerm.com",
        post_url="https://www.linkedin.com/posts/priyanka-patil-84a301246_hiring-businessanalyst-dataanalytics-activity-7521827627687497728-u15u",
        recruiter_name="Priyanka Patil"
    )
    is_valid, errors = linkedin_intelligence_agent.validate_quality_gate(analyzed)
    assert is_valid is True
    assert len(errors) == 0
    assert analyzed["email"] == "Priyanka.Patil@in.credencerm.com"
    assert "Credence" in analyzed["company"]
