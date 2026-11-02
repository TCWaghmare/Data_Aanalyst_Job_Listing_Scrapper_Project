"""
Unit tests for strict Fresher Job Eligibility and JD Experience Analysis.
Guarantees 100% rejection of experienced/senior jobs and acceptance of genuine fresher jobs.
"""
from scraper.taxonomy import analyze_job_fresher_eligibility, is_fresher_eligible
from scraper.models import Job
from scraper.adapters.apify_linkedin import ApifyLinkedInAdapter
from scraper.adapters.apify_indeed import ApifyIndeedAdapter
from scraper.adapters.apify_naukri import ApifyNaukriAdapter

def test_senior_titles_rejection():
    senior_titles = [
        "Senior Data Analyst",
        "Sr. Data Analyst - Operations",
        "Lead Data Analyst - Risk",
        "Principal Analytics Consultant",
        "Data Analytics Manager",
        "Head of Business Intelligence",
        "VP - Data & Analytics",
        "Data Architect",
        "Staff Analytics Engineer",
        "Data Analyst III",
        "Level 3 Business Analyst",
        "Data Analyst - Senior"
    ]
    for title in senior_titles:
        eligible, reason, min_e, max_e = analyze_job_fresher_eligibility(title=title, text="Basic SQL and reporting.")
        assert not eligible, f"Expected '{title}' to be rejected, but got eligible=True! Reason: {reason}"
        assert not is_fresher_eligible(title=title, text="Basic SQL and reporting.")

def test_jd_experience_requirements_rejection():
    experienced_jds = [
        ("Data Analyst", "We are looking for a Data Analyst. Candidates must have 3+ years of experience in SQL and Python."),
        ("Business Analyst", "Requirements: Minimum 2 years of experience in data modeling and Power BI."),
        ("Reporting Analyst", "Experience required: 4 to 6 years of industry experience."),
        ("Analytics Specialist", "Candidates must have at least 3 years of hands-on data warehousing experience."),
        ("Data Analyst, Finance", "Requires 5+ years of relevant experience."),
        ("Junior Analyst", "Must have 3+ years prior experience leading complex ETL workflows.")
    ]
    for title, jd in experienced_jds:
        eligible, reason, min_e, max_e = analyze_job_fresher_eligibility(title=title, text=jd)
        assert not eligible, f"Expected '{title}' with JD to be rejected, but got eligible=True! Reason: {reason}"

def test_genuine_fresher_acceptance():
    fresher_jobs = [
        ("Junior Data Analyst", "Looking for fresh graduates with 0-1 year experience in SQL and Excel. Freshers welcome."),
        ("Data Analyst Fresher", "2025/2026 batch freshers eligible. Training provided on Power BI and SQL."),
        ("Trainee Data Analyst", "No prior experience required. Eagerness to learn analytical tools."),
        ("Associate Data Analyst", "Entry-level position (0-1 year experience). Bachelor's degree in engineering/math."),
        ("Graduate Business Analyst", "Campus hiring 2026. Basic SQL query writing and Excel reporting."),
        ("Intern - Data Science & Analytics", "Internship role for students and recent college graduates."),
        ("Data Analyst", "Data Analyst opening in Pune. 0-2 years experience. Freshers can apply.")
    ]
    for title, jd in fresher_jobs:
        eligible, reason, min_e, max_e = analyze_job_fresher_eligibility(title=title, text=jd)
        assert eligible, f"Expected '{title}' to be accepted as fresher, but got rejected! Reason: {reason}"
        assert is_fresher_eligible(title=title, text=jd)

def test_apify_adapters_filter_experienced_jobs():
    # Test Apify LinkedIn _map_to_job rejects experienced JDs
    li = ApifyLinkedInAdapter()
    senior_item = {
        "title": "Senior Data Analyst",
        "companyName": "Tech Corp",
        "descriptionText": "Requires 5+ years of experience."
    }
    mapped = li._map_to_job(senior_item)
    assert mapped is None, "Apify LinkedIn should reject Senior Data Analyst"

    # Test Apify Indeed _map_to_job rejects experienced JDs
    indeed = ApifyIndeedAdapter()
    experienced_indeed_item = {
        "positionName": "Data Analyst",
        "company": "Finance Inc",
        "description": "Candidates must have minimum 3 years of experience."
    }
    mapped_indeed = indeed._map_to_job(experienced_indeed_item)
    assert mapped_indeed is None, "Apify Indeed should reject minimum 3 years experience"

    # Test Apify Naukri _map_to_job rejects experienced JDs
    naukri = ApifyNaukriAdapter()
    experienced_naukri_item = {
        "title": "Lead Analytics Consultant",
        "experience": {"minimum": 4, "maximum": 8, "text": "4-8 Yrs"},
        "description": {"full": "Lead our consulting analytics team."}
    }
    mapped_naukri = naukri._map_to_job(experienced_naukri_item)
    assert mapped_naukri is None, "Apify Naukri should reject 4-8 yrs lead role"

