import pytest
from resume_tailor.analyzer import deep_job_analyzer
from resume_tailor.engine import ResumeTailorEngine
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_ten_required_skills_two_match_scores_approx_twenty():
    """
    Test: A JD with 10 required skills where 2 match must score ≈20.
    Weighted calculation: 2 matched * 3 / (10 * 3) * 100 = 20.0%.
    """
    profile = {
        "technical_tools": ["SQL", "Excel"],
        "skills": {
            "Technical": ["SQL", "Excel"]
        },
        "experience": [
            {
                "company": "Acme",
                "title": "Analyst",
                "skills": ["SQL", "Excel"],
                "bullets": ["Wrote SQL queries and automated Excel reports."]
            }
        ],
        "projects": []
    }

    job_dict = {
        "title": "Data Analyst",
        "company": "Tech Corp",
        "description": "We are seeking a Data Analyst.",
        "requirements": [
            "SQL",
            "Excel",
            "Python",
            "Power BI",
            "Tableau",
            "Snowflake",
            "dbt",
            "Airflow",
            "AWS",
            "Databricks"
        ]
    }

    analysis = deep_job_analyzer.analyze_job(job_dict, profile)

    # Verify score
    score = analysis["match_score"]
    assert pytest.approx(20.0, abs=1.0) == score, f"Expected score ≈ 20, got {score}"

    # Verify counts
    assert analysis["matched_count"] == 2
    assert analysis["total_count"] == 10
    assert analysis["missing_count"] == 8

    # Verify matched and missing keywords
    assert "SQL" in analysis["matched_keywords"]
    assert "Excel" in analysis["matched_keywords"]

    # Verify missing_keywords and skill_gap_analysis.missing_skills come from the same list
    gap_analysis = analysis["gap_analysis"]
    assert analysis["missing_keywords"] == gap_analysis["missing_skills"]
    assert len(gap_analysis["missing_skills"]) == 8
    assert "Python" in gap_analysis["missing_skills"]
    assert "Tableau" in gap_analysis["missing_skills"]
    assert "Snowflake" in gap_analysis["missing_skills"]


def test_job_with_one_matched_four_missing_scores_twenty_not_ninetyeight():
    """
    Regression test for the bug:
    One job previously scored 98% with 1 matched keyword and 4 missing,
    and skill_gap_analysis.missing_skills was empty while missing_keywords wasn't.
    """
    profile = {
        "technical_tools": ["Power BI"],
        "skills": {"BI": ["Power BI"]},
        "experience": [],
        "projects": []
    }

    job_dict = {
        "title": "BI Developer",
        "company": "Global Data Inc",
        "description": "Looking for BI Developer with Power BI, Snowflake, dbt, Airflow, and AWS expertise.",
        "requirements": [
            "Power BI",
            "Snowflake",
            "dbt",
            "Airflow",
            "AWS"
        ]
    }

    analysis = deep_job_analyzer.analyze_job(job_dict, profile)

    # 1 matched (weight 3) / 5 total (weight 15) * 100 = 20%
    score = analysis["match_score"]
    assert score == 20 or pytest.approx(20.0, abs=0.5) == score
    assert score != 98, "Score must NOT be 98% when only 1 of 5 skills match!"

    # Missing skills must NOT be empty in gap_analysis
    assert len(analysis["missing_keywords"]) == 4
    assert analysis["missing_keywords"] == analysis["gap_analysis"]["missing_skills"]
    assert len(analysis["gap_analysis"]["missing_skills"]) == 4
    assert analysis["matched_count"] == 1
    assert analysis["total_count"] == 5


def test_required_versus_preferred_weighting():
    """
    Test weighting logic:
    Required keywords have weight 3, preferred keywords have weight 1.
    """
    profile_required = {
        "technical_tools": ["SQL", "Power BI"],
        "skills": {"Core": ["SQL", "Power BI"]},
        "experience": [],
        "projects": []
    }

    job_dict = {
        "title": "Analytics Engineer",
        "company": "Cloud Data",
        "description": (
            "Job Description\n"
            "Requirements:\n"
            "- SQL\n"
            "- Power BI\n"
            "Preferred Qualifications:\n"
            "- AWS\n"
            "- Docker\n"
        ),
        "requirements": ["SQL", "Power BI"],
        "preferred_qualifications": ["AWS", "Docker"]
    }

    # Total weight: 2 required * 3 + 2 preferred * 1 = 6 + 2 = 8
    # Candidate matches 2 required: weight = 6 / 8 * 100 = 75.0%
    analysis_req = deep_job_analyzer.analyze_job(job_dict, profile_required)
    assert pytest.approx(75.0, abs=0.5) == analysis_req["match_score"]
    assert analysis_req["matched_count"] == 2
    assert analysis_req["total_count"] == 4

    # Candidate matching only preferred skills:
    profile_pref = {
        "technical_tools": ["AWS", "Docker"],
        "skills": {"DevOps": ["AWS", "Docker"]},
        "experience": [],
        "projects": []
    }
    # Candidate matches 2 preferred: weight = 2 / 8 * 100 = 25.0%
    analysis_pref = deep_job_analyzer.analyze_job(job_dict, profile_pref)
    assert pytest.approx(25.0, abs=0.5) == analysis_pref["match_score"]
    assert analysis_pref["matched_count"] == 2
    assert analysis_pref["total_count"] == 4


def test_no_floor_and_no_bonus():
    """
    Test: score = weighted matched / weighted total * 100 with NO floor (0% possible)
    and NO artificial 98% cap (100% possible).
    """
    empty_profile = {
        "technical_tools": [],
        "skills": {},
        "experience": [],
        "projects": []
    }

    job_dict = {
        "title": "Data Engineer",
        "description": "Seeking Kafka, Cassandra, Rust, Golang specialist.",
        "requirements": ["Kafka", "Cassandra", "Rust", "Golang"]
    }

    # 0 matches should score 0, NOT 50 or 75
    analysis_zero = deep_job_analyzer.analyze_job(job_dict, empty_profile)
    assert analysis_zero["match_score"] == 0
    assert analysis_zero["matched_count"] == 0
    assert analysis_zero["missing_count"] == 4

    # Perfect match should score 100, NOT capped at 98
    full_profile = {
        "technical_tools": ["Kafka", "Cassandra", "Rust", "Golang"],
        "skills": {"Tech": ["Kafka", "Cassandra", "Rust", "Golang"]},
        "experience": [],
        "projects": []
    }
    analysis_full = deep_job_analyzer.analyze_job(job_dict, full_profile)
    assert analysis_full["match_score"] == 100
    assert analysis_full["matched_count"] == 4
    assert analysis_full["missing_count"] == 0


def test_engine_and_analyzer_synchronization():
    """
    Verify ResumeTailorEngine._analyze_ats_compatibility returns identical
    synchronized missing_keywords and skill_gap_analysis.missing_skills.
    """
    engine = ResumeTailorEngine()
    profile = {
        "technical_tools": ["SQL", "Excel"],
        "skills": {"Tech": ["SQL", "Excel"]},
        "experience": [],
        "projects": []
    }

    res = engine._analyze_ats_compatibility(
        job_text="Requirements: SQL, Excel, Python, Snowflake, Tableau",
        profile=profile,
        explicit_skills=["SQL", "Excel", "Python", "Snowflake", "Tableau"],
        job_title="Data Analyst"
    )

    assert "match_score" in res
    assert "matched_count" in res
    assert "total_count" in res
    assert res["matched_count"] == 2
    assert res["total_count"] == 5
    # score = 2 * 3 / (5 * 3) * 100 = 40.0%
    assert pytest.approx(40.0, abs=1.0) == res["match_score"]

    # Both lists must match exactly
    assert res["missing_keywords"] == res["skill_gap_analysis"]["missing_skills"]
    assert len(res["missing_keywords"]) == 3


def test_tailor_full_workflow_ats_metrics():
    """
    Test full ResumeTailorEngine.tailor() produces unified ats_metrics
    with matched_count, total_count, and identical missing lists.
    """
    engine = ResumeTailorEngine()
    tailor_result = engine.tailor(
        job_title="Business Intelligence Analyst",
        company="Global Retail Corp",
        job_description="Seeking BI Analyst skilled in Power BI, SQL, Python, Snowflake, and AWS.",
        job_skills=["Power BI", "SQL", "Python", "Snowflake", "AWS"],
        requirements=["Power BI", "SQL", "Python", "Snowflake", "AWS"]
    )

    ats = tailor_result["ats_metrics"]
    assert "match_score" in ats
    assert "matched_count" in ats
    assert "total_count" in ats
    assert "matched_keywords" in ats
    assert "missing_keywords" in ats
    assert "skill_gap_analysis" in ats

    gap = ats["skill_gap_analysis"]
    assert ats["missing_keywords"] == gap["missing_skills"]
    assert ats["matched_keywords"] == gap["matched_skills"]
    assert ats["matched_count"] == gap["matched_count"]
    assert ats["total_count"] == gap["total_count"]
    assert ats["match_score"] == gap["match_score"]
    assert ats["total_count"] == ats["matched_count"] + ats["missing_count"]

