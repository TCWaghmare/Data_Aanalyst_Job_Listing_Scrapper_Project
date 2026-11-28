"""
Tests for Resume and Cover Letter Generation Improvements.
Validates:
1. Resume summary: Never states unheld job titles. Strictly uses the form:
   "Data analyst with <real strengths>, targeting <job title> roles".
   Uses only titles/facts from the knowledge base.
2. Cover letter:
   - Never pastes job-description text verbatim; paraphrases 2-3 key duties into natural sentences.
   - Fixes casing: SQL, Power BI, Excel, Tableau, Python; formats money as $389.3M.
   - Removes awkward fragments such as "foundation in KPIs".
   - Validator fails generation if any number, tool, employer or certification in the output isn't in the knowledge base.
3. Tests run against Cummins ("Supply Chain Analyst") and Comscore ("Survey Tabulations Analyst") jobs.
"""

import os
import re
import json
import sqlite3
import pytest

from resume_tailor.engine import ResumeTailorEngine, fix_casing_and_money as engine_fix_casing
from resume_tailor.cover_letter_builder import (
    CoverLetterBuilder,
    fix_casing_and_money as cl_fix_casing,
    remove_awkward_fragments,
    paraphrase_key_duties
)
from resume_tailor.validator import (
    validate_against_knowledge_base,
    KnowledgeBaseValidationError,
    extract_verified_kb_facts
)
from resume_tailor.knowledge_base import career_kb


@pytest.fixture(scope="module")
def unified_profile():
    return career_kb.get_unified_profile()


@pytest.fixture(scope="module")
def cummins_job():
    conn = sqlite3.connect("data/jobs.db")
    row = conn.execute(
        "SELECT id, title, company, description, skills, responsibilities, requirements FROM jobs WHERE id = 'li_apify_4485735990'"
    ).fetchone()
    conn.close()
    assert row is not None, "Cummins job 'li_apify_4485735990' not found in data/jobs.db"
    return {
        "id": row[0],
        "title": row[1],
        "company": row[2],
        "description": row[3],
        "skills": json.loads(row[4]) if row[4] else [],
        "responsibilities": json.loads(row[5]) if row[5] else [],
        "requirements": json.loads(row[6]) if row[6] else []
    }


@pytest.fixture(scope="module")
def comscore_job():
    conn = sqlite3.connect("data/jobs.db")
    row = conn.execute(
        "SELECT id, title, company, description, skills, responsibilities, requirements FROM jobs WHERE id = 'li_apify_4476839826'"
    ).fetchone()
    conn.close()
    assert row is not None, "Comscore job 'li_apify_4476839826' not found in data/jobs.db"
    return {
        "id": row[0],
        "title": row[1],
        "company": row[2],
        "description": row[3],
        "skills": json.loads(row[4]) if row[4] else [],
        "responsibilities": json.loads(row[5]) if row[5] else [],
        "requirements": json.loads(row[6]) if row[6] else []
    }


def find_verbatim_spans(source_text: str, generated_text: str, min_words: int = 5):
    """Returns any verbatim sequence of min_words or more words from source_text found in generated_text."""
    # Normalize texts to lower-case space-separated tokens
    src_words = re.findall(r'\b[a-zA-Z0-9_\$]+\b', source_text.lower())
    gen_text_lower = " " + " ".join(re.findall(r'\b[a-zA-Z0-9_\$]+\b', generated_text.lower())) + " "
    
    matches = []
    for i in range(len(src_words) - min_words + 1):
        phrase = " ".join(src_words[i:i + min_words])
        # Skip purely generic stopword sequences like "in to of on"
        if f" {phrase} " in gen_text_lower:
            matches.append(phrase)
    return matches


# ==============================================================================
# 1. RESUME SUMMARY TESTS
# ==============================================================================

def test_resume_summary_cummins_supply_chain_analyst(cummins_job):
    """
    Verify summary never states a job title the candidate hasn't held.
    Uses the form: 'Data analyst with <real strengths>, targeting <job title> roles'.
    Uses only titles/facts from the knowledge base.
    """
    engine = ResumeTailorEngine()
    result = engine.tailor(
        job_title=cummins_job["title"],
        company=cummins_job["company"],
        job_description=cummins_job["description"],
        job_skills=cummins_job["skills"],
        responsibilities=cummins_job["responsibilities"],
        requirements=cummins_job["requirements"]
    )
    summary = result["tailored_resume"]["summary"]
    
    # 1. Must use the exact required opening form
    assert summary.startswith("Data analyst with "), f"Summary did not start with 'Data analyst with ': {summary}"
    assert ", targeting Supply Chain Analyst roles." in summary, f"Summary did not target cleanly: {summary}"
    
    # 2. Never state the candidate was a Supply Chain Analyst in the past
    assert not re.search(r"\b(?:worked as|held role as|experienced|senior)\s+Supply Chain Analyst\b", summary, re.IGNORECASE)
    assert not re.search(r"\bAs a Supply Chain Analyst\b", summary, re.IGNORECASE)
    
    # 3. Only real strengths and verified credentials from KB
    assert "Excel" in summary or "Power BI" in summary or "SQL" in summary
    assert "PL-300" in summary
    assert "DP-600" in summary


def test_resume_summary_comscore_survey_tabulations_analyst(comscore_job):
    """
    Verify summary never states unheld titles for Comscore.
    Uses the form: 'Data analyst with <real strengths>, targeting <job title> roles'.
    """
    engine = ResumeTailorEngine()
    result = engine.tailor(
        job_title=comscore_job["title"],
        company=comscore_job["company"],
        job_description=comscore_job["description"],
        job_skills=comscore_job["skills"],
        responsibilities=comscore_job["responsibilities"],
        requirements=comscore_job["requirements"]
    )
    summary = result["tailored_resume"]["summary"]
    
    # 1. Must use the exact required opening form
    assert summary.startswith("Data analyst with "), f"Summary did not start with 'Data analyst with ': {summary}"
    assert f", targeting {comscore_job['title']} roles." in summary
    
    # 2. Never claim unheld title
    assert not re.search(r"\b(?:worked as|held role as|former)\s+(?:Associate\s+)?Survey Tabulations Analyst\b", summary, re.IGNORECASE)
    assert not re.search(r"\bAs an? (?:Associate\s+)?Survey Tabulations Analyst\b", summary, re.IGNORECASE)
    
    # 3. Only verified facts
    assert "PL-300" in summary
    assert "DP-600" in summary


# ==============================================================================
# 2. COVER LETTER TESTS (DUTIES, CASING, MONEY, AWKWARD FRAGMENTS)
# ==============================================================================

def test_cover_letter_cummins_supply_chain_analyst(cummins_job, unified_profile):
    """
    Cover letter for Cummins:
    - Never pastes job-description text verbatim; paraphrases 2-3 key duties into natural sentences.
    - Fixes casing: SQL, Power BI, Excel, Tableau, Python; format money as $389.3M.
    - Removes awkward fragments such as 'foundation in KPIs'.
    - Passes KB validation.
    """
    builder = CoverLetterBuilder()
    cl = builder.generate(
        job_title=cummins_job["title"],
        company=cummins_job["company"],
        job_description=cummins_job["description"],
        job_skills=cummins_job["skills"],
        profile=unified_profile,
        responsibilities=cummins_job["responsibilities"],
        requirements=cummins_job["requirements"]
    )
    
    p1 = cl["paragraphs"][0]
    p2 = cl["paragraphs"][1]
    p3 = cl["paragraphs"][2]
    full_text = cl["full_text"]
    
    # 1. Never paste JD text verbatim in p3 duty sentence
    raw_jd_and_resps = cummins_job["description"] + " " + " ".join(cummins_job["responsibilities"])
    # Check that the duty sentence in p3 has no long verbatim spans from JD (>5 words)
    duty_matches = find_verbatim_spans(raw_jd_and_resps, p3, min_words=6)
    assert len(duty_matches) == 0, f"Found verbatim JD phrases in cover letter P3: {duty_matches}"
    
    # Paraphrases 2-3 key duties naturally (demand variations, material/inventory KPIs, data integrity)
    assert "demand and forecast variations" in p3
    assert "material and inventory KPIs" in p3
    assert "data integrity" in p3
    
    # 2. Fix casing: SQL, Power BI, Excel, Tableau, Python
    assert "Excel" in full_text
    assert "SQL" in full_text
    assert "Power BI" in full_text
    assert not re.search(r"\b(?:sql|Sql)\b", full_text)
    assert not re.search(r"\b(?:power\s*bi|Power\s*Bi|powerbi)\b", full_text)
    assert not re.search(r"\b(?:excel|EXCEL)\b", full_text)
    
    # Money formatting: $389.3M
    assert "$389.3M" in full_text
    assert not re.search(r"(?<!\$)389\.3", full_text)
    
    # 3. No awkward fragments such as 'foundation in KPIs'
    assert "foundation in KPIs" not in full_text
    assert "foundation in KPI" not in full_text
    assert "foundation in key performance indicators" not in full_text
    
    # 4. Executive summary uses proper form
    assert cl["executive_summary"].startswith("Data analyst with verified hands-on proficiency in ")
    assert ", targeting Supply Chain Analyst roles." in cl["executive_summary"]
    assert not cl["executive_summary"].startswith("Qualified Supply Chain Analyst candidate")


def test_cover_letter_comscore_survey_tabulations_analyst(comscore_job, unified_profile):
    """
    Cover letter for Comscore:
    - Never pastes job-description text verbatim; paraphrases 2-3 key duties into natural sentences.
    - Fixes casing: SQL, Power BI, Excel, Tableau, Python; format money as $389.3M.
    - Removes awkward fragments such as 'foundation in KPIs'.
    - Passes KB validation.
    """
    builder = CoverLetterBuilder()
    cl = builder.generate(
        job_title=comscore_job["title"],
        company=comscore_job["company"],
        job_description=comscore_job["description"],
        job_skills=comscore_job["skills"],
        profile=unified_profile,
        responsibilities=comscore_job["responsibilities"],
        requirements=comscore_job["requirements"]
    )
    
    p3 = cl["paragraphs"][2]
    full_text = cl["full_text"]
    
    # 1. Never paste JD text verbatim
    raw_jd_and_resps = comscore_job["description"] + " " + " ".join(comscore_job["responsibilities"])
    duty_matches = find_verbatim_spans(raw_jd_and_resps, p3, min_words=6)
    assert len(duty_matches) == 0, f"Found verbatim JD phrases in cover letter P3: {duty_matches}"
    
    # Paraphrases 2-3 key duties naturally (survey datasets, data quality across tracking studies, tabular reporting)
    assert "process and evaluate survey datasets" in p3
    assert "tracking studies" in p3
    assert "tabular reporting" in p3
    
    # 2. Fix casing & money
    assert "Excel" in full_text
    assert "$389.3M" in full_text
    assert not re.search(r"\b(?:sql|Sql)\b", full_text)
    assert not re.search(r"\b(?:excel|EXCEL)\b", full_text)
    
    # 3. No awkward fragments
    assert "foundation in KPIs" not in full_text
    assert "foundation in the required core skills" not in full_text
    
    # 4. Executive summary uses proper form
    assert cl["executive_summary"].startswith("Data analyst with verified hands-on proficiency in ")
    assert f", targeting {comscore_job['title']} roles." in cl["executive_summary"]


# ==============================================================================
# 3. VALIDATOR TESTS (FAILS ON UNVERIFIED NUMBER, TOOL, EMPLOYER, CERT)
# ==============================================================================

def test_validator_fails_on_unverified_number(unified_profile):
    """Validator fails generation if any unverified number appears in the output."""
    # 1. Unverified team size
    bad_output_1 = "Led a dedicated team of 15 analysts to streamline business reporting."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified number in output: '15'"):
        validate_against_knowledge_base(bad_output_1, unified_profile)
    
    # 2. Unverified money metric
    bad_output_2 = "Managed $45M in financial transactions across regional databases."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified number in output: '\\$45M'"):
        validate_against_knowledge_base(bad_output_2, unified_profile)
    
    # 3. Unverified percentage
    bad_output_3 = "Achieved 75% increase in operational efficiency through automation."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified number in output: '75%'"):
        validate_against_knowledge_base(bad_output_3, unified_profile)
    
    # 4. Unverified record count
    bad_output_4 = "Optimized 500 database tables in relational PostgreSQL warehouse."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified number in output: '500'"):
        validate_against_knowledge_base(bad_output_4, unified_profile)


def test_validator_fails_on_unverified_tool(unified_profile):
    """Validator fails generation if any unverified tool is claimed as candidate skill/experience."""
    # 1. Claiming Tableau
    bad_output_1 = "With a solid hands-on foundation in Tableau and SQL, I am eager to contribute."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified tool in output: 'tableau'"):
        validate_against_knowledge_base(bad_output_1, unified_profile)
    
    # 2. Claiming SPSS
    bad_output_2 = "I am proficient in SPSS and advanced statistical modeling."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified tool in output: 'spss'"):
        validate_against_knowledge_base(bad_output_2, unified_profile)
    
    # 3. Claiming Snowflake in experience
    bad_output_3 = "Applied Snowflake to build scalable cloud data pipelines."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified tool in output: 'snowflake'"):
        validate_against_knowledge_base(bad_output_3, unified_profile)
    
    # 4. In structured skills dict
    bad_resume = {
        "name": "Tejas C. Waghmare",
        "skills": {
            "bi_visualization": ["Power BI", "Tableau", "Excel"]
        }
    }
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified tool in output: 'Tableau'"):
        validate_against_knowledge_base(bad_resume, unified_profile)


def test_validator_fails_on_unverified_employer(unified_profile):
    """Validator fails generation if candidate claims an employer not in the knowledge base."""
    # 1. Unverified employer in text
    bad_output_1 = "In my professional role as Analyst at Google, I managed complex pipelines."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified employer in output: 'Google'"):
        validate_against_knowledge_base(bad_output_1, unified_profile)
    
    # 2. Unverified employer in resume experience
    bad_resume = {
        "name": "Tejas C. Waghmare",
        "experience": [
            {
                "company": "Tata Consultancy Services",
                "title": "Data Analyst",
                "bullets": ["Analyzed transactional datasets."]
            }
        ]
    }
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified employer in output: 'Tata Consultancy Services'"):
        validate_against_knowledge_base(bad_resume, unified_profile)


def test_validator_fails_on_unverified_certification(unified_profile):
    """Validator fails generation if candidate claims a certification not in the knowledge base."""
    # 1. Unverified cert in text
    bad_output_1 = "I have earned industry-recognized credentials including AWS Certified Solutions Architect."
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified certification in output: 'aws certified'"):
        validate_against_knowledge_base(bad_output_1, unified_profile)
    
    # 2. Unverified cert in resume dict
    bad_resume = {
        "name": "Tejas C. Waghmare",
        "certifications": [
            {"name": "PMP - Project Management Professional"}
        ]
    }
    with pytest.raises(KnowledgeBaseValidationError, match="Unverified certification in output: 'pmp"):
        validate_against_knowledge_base(bad_resume, unified_profile)


def test_validator_passes_on_verified_kb_data(unified_profile, cummins_job, comscore_job):
    """Validator passes on 100% verified candidate knowledge base data."""
    engine = ResumeTailorEngine()
    builder = CoverLetterBuilder()
    
    # 1. Cummins resume & cover letter
    cummins_resume = engine.tailor(
        job_title=cummins_job["title"],
        company=cummins_job["company"],
        job_description=cummins_job["description"]
    )["tailored_resume"]
    assert validate_against_knowledge_base(cummins_resume, unified_profile, cummins_job["company"]) is True
    
    cummins_cl = builder.generate(
        job_title=cummins_job["title"],
        company=cummins_job["company"],
        job_description=cummins_job["description"],
        job_skills=cummins_job["skills"],
        profile=unified_profile,
        responsibilities=cummins_job["responsibilities"]
    )
    assert validate_against_knowledge_base(cummins_cl, unified_profile, cummins_job["company"]) is True
    
    # 2. Comscore resume & cover letter
    comscore_resume = engine.tailor(
        job_title=comscore_job["title"],
        company=comscore_job["company"],
        job_description=comscore_job["description"]
    )["tailored_resume"]
    assert validate_against_knowledge_base(comscore_resume, unified_profile, comscore_job["company"]) is True
    
    comscore_cl = builder.generate(
        job_title=comscore_job["title"],
        company=comscore_job["company"],
        job_description=comscore_job["description"],
        job_skills=comscore_job["skills"],
        profile=unified_profile,
        responsibilities=comscore_job["responsibilities"]
    )
    assert validate_against_knowledge_base(comscore_cl, unified_profile, comscore_job["company"]) is True


# ==============================================================================
# 4. CASING & MONEY FORMATTER HELPER TESTS
# ==============================================================================

def test_fix_casing_and_money_helper():
    """Verify tool casing (SQL, Power BI, Excel, Tableau, Python) and money formatting ($389.3M)."""
    text = (
        "Experienced in sql, Sql, power bi, Power bi, powerbi, and POWER BI. "
        "Also skilled in excel and EXCEL, tableau, and python or PYTHON. "
        "Built NYC Airbnb project with 389.3 million market value, $389.3 million, 389.3M, "
        "plus $205 million revenue and $32.8 million revenue."
    )
    result = cl_fix_casing(text)
    
    # Tool casing
    assert "SQL" in result
    assert "Power BI" in result
    assert "Excel" in result
    assert "Tableau" in result
    assert "Python" in result
    assert not re.search(r"\b(?:sql|Sql)\b", result)
    assert not re.search(r"\b(?:power\s*bi|Power\s*Bi|powerbi)\b", result)
    assert not re.search(r"\b(?:excel|EXCEL)\b", result)
    assert not re.search(r"\b(?:tableau|TABLEAU)\b", result)
    assert not re.search(r"\b(?:python|PYTHON)\b", result)
    
    # Money formatting
    assert "$389.3M" in result
    assert "$205M" in result
    assert "$32.8M" in result
    assert not re.search(r"(?<!\$)389\.3", result)


# ==============================================================================
# 5. AWKWARD FRAGMENT REMOVAL HELPER TESTS
# ==============================================================================

def test_remove_awkward_fragments_helper():
    """Verify elimination of awkward fragments such as 'foundation in KPIs'."""
    text1 = "With a solid hands-on foundation in KPIs, I am eager to contribute."
    cleaned1 = remove_awkward_fragments(text1)
    assert "foundation in KPIs" not in cleaned1
    assert "hands-on foundation in analytical KPI tracking" in cleaned1
    
    text2 = "Demonstrated foundation in key performance indicators and reporting."
    cleaned2 = remove_awkward_fragments(text2)
    assert "foundation in key performance indicators" not in cleaned2
    
    text3 = "Possesses foundation in dashboards and reporting."
    cleaned3 = remove_awkward_fragments(text3)
    assert "foundation in dashboards" not in cleaned3
