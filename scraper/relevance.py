"""
Relevance scoring module to filter out off-target and irrelevant job postings.

Rules:
1. Positive signals: Title and skills match data analyst, BI, MIS, analytics, SQL, Power BI, Tableau, Excel, Python.
2. Hard reject: Title contains AI trainer, video editor, customer support, business development, telecaller, sales executive,
   or an aggregator-page title like 'Apply To The Best Remote Jobs'.
3. Seniority reject: Title or experience contains senior, lead, manager, principal, head, director, 3+ years.
4. Short description reject: Reject descriptions under 200 characters unless the title is a strong match.
5. Minimum threshold: Configurable via env var MIN_RELEVANCE (default: 50).
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

DEFAULT_MIN_RELEVANCE = 50


def get_min_relevance() -> int:
    """Returns the minimum relevance threshold from environment variable MIN_RELEVANCE (default 50)."""
    val = os.getenv("MIN_RELEVANCE", str(DEFAULT_MIN_RELEVANCE))
    try:
        return int(val)
    except (ValueError, TypeError):
        return DEFAULT_MIN_RELEVANCE


# --- Hard Reject Patterns (Immediate 0 score) ---
# Hard reject: title contains AI trainer, video editor, customer support, business development, telecaller, sales executive,
# or an aggregator-page title like "Apply To The Best Remote Jobs".
HARD_REJECT_PATTERNS = [
    # AI trainer
    (re.compile(r"\bai\s*trainers?\b", re.IGNORECASE), "AI trainer"),
    # Video editor
    (re.compile(r"\bvideo\s*editors?\b", re.IGNORECASE), "video editor"),
    # Customer support / customer service
    (re.compile(r"\bcustomer\s*(?:support|service)\b", re.IGNORECASE), "customer support"),
    # Business development
    (re.compile(r"\bbusiness\s*development\b", re.IGNORECASE), "business development"),
    # Telecaller
    (re.compile(r"\btele-?callers?\b", re.IGNORECASE), "telecaller"),
    # Sales executive
    (re.compile(r"\bsales\s*(?:\([^)]*\)\s*)?executives?\b", re.IGNORECASE), "sales executive"),
    # Aggregator-page title like "Apply To The Best Remote Jobs"
    (re.compile(r"\bapply\s+to\s+(?:the\s+)?best\s+remote\s+jobs\b", re.IGNORECASE), "aggregator title"),
    (re.compile(r"^\s*\d+\+?\s+[\w\s/-]+jobs\b", re.IGNORECASE), "aggregator count title"),  # e.g. "74 Data Analytics Jobs"
    (re.compile(r"\bbest\s+remote\s+jobs\b", re.IGNORECASE), "aggregator title"),
    (re.compile(r"^\s*remote\s+jobs\s+in\b", re.IGNORECASE), "aggregator title"),
    (re.compile(r"\bapply\s+to\s+remote\s+jobs\b", re.IGNORECASE), "aggregator title"),
]

# --- Seniority Reject Patterns (Immediate 0 score) ---
# Seniority reject: senior, lead, manager, principal, head, director, 3+ years.
SENIORITY_TITLE_PATTERNS = [
    (re.compile(r"\b(?:senior|sr\b|sr\.)", re.IGNORECASE), "senior"),
    # Use word boundary so "leadership" in "Leadership Development Program" is NOT matched
    (re.compile(r"\blead(?:s)?\b", re.IGNORECASE), "lead"),
    # Word boundary so "management" in "Data management" is NOT matched, but "Store Manager", "Unit Manager" are matched
    (re.compile(r"\bmanager(?:s)?\b", re.IGNORECASE), "manager"),
    (re.compile(r"\bprincipal\b", re.IGNORECASE), "principal"),
    (re.compile(r"\bhead\b", re.IGNORECASE), "head"),
    (re.compile(r"\bdirector(?:s)?\b", re.IGNORECASE), "director"),
]

SENIORITY_EXP_PATTERNS = [
    re.compile(r"\b(?:[3-9]|\d{2,})\s*\+\s*(?:years?|yrs?)?\b", re.IGNORECASE),
    re.compile(r"\b(?:[3-9]|\d{2,})\s*-\s*\d+\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"\b(?:[3-9]|\d{2,})\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"\b3\+\s*(?:years?|yrs?)?\b", re.IGNORECASE),
]

# --- Strong Match Title Patterns (Required if description < 200 chars) ---
STRONG_TITLE_PATTERNS = [
    re.compile(r"\bdata\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bdata\s+analytics\b", re.IGNORECASE),
    re.compile(r"\bdata\s+analysis\b", re.IGNORECASE),
    re.compile(r"\bbusiness\s+(?:data\s+)?analyst\b", re.IGNORECASE),
    re.compile(r"\bdata\s+visualization\b", re.IGNORECASE),
    re.compile(r"\bvisualization\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bbi\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bbi\s+developer\b", re.IGNORECASE),
    re.compile(r"\bbusiness\s+intelligence\b", re.IGNORECASE),
    re.compile(r"\bmis\s+executive\b", re.IGNORECASE),
    re.compile(r"\bmis\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bmis\b", re.IGNORECASE),
    re.compile(r"\bpower\s*bi\b", re.IGNORECASE),
    re.compile(r"\btableau\b", re.IGNORECASE),
    re.compile(r"\bsql\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bsql\s+developer\b", re.IGNORECASE),
    re.compile(r"\breporting\s+analyst\b", re.IGNORECASE),
    re.compile(r"\boperations\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bproduct\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bfinancial\s+analyst\b", re.IGNORECASE),
    re.compile(r"\banalytics\s+(?:consultant|engineer|specialist|associate)\b", re.IGNORECASE),
    re.compile(r"\bdata\s+scientist\b", re.IGNORECASE),
    re.compile(r"\bdecision\s+scientist\b", re.IGNORECASE),
]

# --- Positive Target Keywords & Skills ---
# Core positive targets: data analyst, BI, MIS, analytics, SQL, Power BI, Tableau, Excel, Python
CORE_ROLES = [
    (re.compile(r"\bdata\s+analyst\b", re.IGNORECASE), 45),
    (re.compile(r"\bdata\s+analytics\b", re.IGNORECASE), 45),
    (re.compile(r"\bbusiness\s+(?:data\s+)?analyst\b", re.IGNORECASE), 45),
    (re.compile(r"\bdata\s+visualization(?:\s+analyst)?\b", re.IGNORECASE), 45),
    (re.compile(r"\bbi\s+analyst\b", re.IGNORECASE), 45),
    (re.compile(r"\bbusiness\s+intelligence\b", re.IGNORECASE), 45),
    (re.compile(r"\bmis\b", re.IGNORECASE), 40),
    (re.compile(r"\bpower\s*bi\b", re.IGNORECASE), 35),
    (re.compile(r"\btableau\b", re.IGNORECASE), 35),
    (re.compile(r"\bsql\s+(?:analyst|developer)\b", re.IGNORECASE), 35),
    (re.compile(r"\b(?:reporting|operations|product|financial)\s+analyst\b", re.IGNORECASE), 35),
    (re.compile(r"\banalytics\b", re.IGNORECASE), 30),
    (re.compile(r"\bdata\s+(?:scientist|engineer)\b", re.IGNORECASE), 25),
]

TITLE_SKILL_BONUS = [
    (re.compile(r"\bsql\b", re.IGNORECASE), 10),
    (re.compile(r"\bpower\s*bi\b", re.IGNORECASE), 10),
    (re.compile(r"\btableau\b", re.IGNORECASE), 10),
    (re.compile(r"\bexcel\b", re.IGNORECASE), 8),
    (re.compile(r"\bpython\b", re.IGNORECASE), 8),
]

FRESHER_TITLE_BONUS = re.compile(
    r"\b(?:junior|jr\b|jr\.|fresher|trainee|graduate|intern|associate|entry\s*level|0-1(?:\s*yr|\s*years?)?)\b",
    re.IGNORECASE,
)

TARGET_SKILLS = [
    ("sql", re.compile(r"\bsql\b", re.IGNORECASE), 10),
    ("power bi", re.compile(r"\bpower\s*bi\b", re.IGNORECASE), 10),
    ("tableau", re.compile(r"\btableau\b", re.IGNORECASE), 10),
    ("excel", re.compile(r"\bexcel\b", re.IGNORECASE), 8),
    ("python", re.compile(r"\bpython\b", re.IGNORECASE), 8),
    ("bi", re.compile(r"\b(?:bi|business\s+intelligence)\b", re.IGNORECASE), 8),
    ("analytics", re.compile(r"\b(?:analytics|data\s+analysis)\b", re.IGNORECASE), 8),
    ("mis", re.compile(r"\bmis\b", re.IGNORECASE), 8),
]


def _extract_job_data(job: Any) -> Tuple[str, List[str], str, Optional[int], str]:
    """Helper to safely extract (title, skills, description, min_experience, experience_level)."""
    if isinstance(job, dict):
        title = str(job.get("title") or "").strip()
        raw_skills = job.get("skills") or []
        description = str(job.get("description") or "").strip()
        min_exp = job.get("min_experience")
        exp_level = str(job.get("experience_level") or "").strip()
    else:
        title = str(getattr(job, "title", "") or "").strip()
        raw_skills = getattr(job, "skills", []) or []
        description = str(getattr(job, "description", "") or "").strip()
        min_exp = getattr(job, "min_experience", None)
        exp_level = str(getattr(job, "experience_level", "") or "").strip()

    skills: List[str] = []
    if isinstance(raw_skills, list):
        skills = [str(s).strip() for s in raw_skills if str(s).strip()]
    elif isinstance(raw_skills, str):
        raw_str = raw_skills.strip()
        if raw_str.startswith("[") and raw_str.endswith("]"):
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, list):
                    skills = [str(s).strip() for s in parsed if str(s).strip()]
                else:
                    skills = [raw_str]
            except Exception:
                skills = [s.strip() for s in raw_str.split(",") if s.strip()]
        else:
            skills = [s.strip() for s in raw_str.split(",") if s.strip()]

    return title, skills, description, min_exp, exp_level


def is_strong_title(title: str) -> bool:
    """Checks whether a title is a strong match for core analytics/data/BI/MIS roles."""
    for pattern in STRONG_TITLE_PATTERNS:
        if pattern.search(title):
            return True
    return False


def score_job(job: Any) -> int:
    """
    Evaluates a job and returns an integer relevance score from 0 to 100.

    Rules applied:
    - Hard reject (AI trainer, video editor, customer support, business development,
      telecaller, sales executive, aggregator page title): returns 0.
    - Seniority reject (senior, lead, manager, principal, head, director, 3+ years): returns 0.
    - Short description reject: descriptions under 200 chars return 0 unless the title is a strong match.
    - Positive match: scores points based on title and skills matching data analyst, BI, MIS, analytics,
      SQL, Power BI, Tableau, Excel, Python.
    """
    title, skills, description, min_exp, exp_level = _extract_job_data(job)

    if not title:
        return 0

    # 1. Hard Reject Rule (Title contains irrelevant roles or aggregator-page titles)
    for pattern, _reason in HARD_REJECT_PATTERNS:
        if pattern.search(title):
            return 0

    # 2. Seniority Reject Rule (Senior, lead, manager, principal, head, director, 3+ years)
    for pattern, _reason in SENIORITY_TITLE_PATTERNS:
        if pattern.search(title):
            return 0

    # Check 3+ years experience in title, experience_level, or min_experience
    for pattern in SENIORITY_EXP_PATTERNS:
        if pattern.search(title) or pattern.search(exp_level):
            return 0

    if min_exp is not None:
        try:
            if float(min_exp) >= 3.0:
                return 0
        except (ValueError, TypeError):
            pass

    # 3. Short description reject: descriptions under 200 chars unless the title is a strong match
    has_strong_title = is_strong_title(title)
    if len(description.strip()) < 200 and not has_strong_title:
        return 0

    # 4. Positive Scoring
    title_score = 0

    # Role matching in title (take highest matching core role)
    for role_pat, pts in CORE_ROLES:
        if role_pat.search(title):
            title_score = max(title_score, pts)
            break

    # Skill bonus in title
    for skill_pat, pts in TITLE_SKILL_BONUS:
        if skill_pat.search(title):
            title_score += pts

    # Fresher bonus in title
    if FRESHER_TITLE_BONUS.search(title):
        title_score += 10

    # Cap title score at 55
    title_score = min(55, title_score)

    # Skills matching (check skills list and description)
    skills_text = " ".join(skills).lower()
    desc_lower = description.lower()
    skills_score = 0

    for _skill_name, pat, pts in TARGET_SKILLS:
        if pat.search(skills_text) or pat.search(desc_lower):
            skills_score += pts

    # Cap skills score at 35
    skills_score = min(35, skills_score)

    # Description analytics keywords bonus (up to 10 pts)
    desc_score = 0
    desc_keywords = [
        r"\bdata\s+analyst\b",
        r"\banalytics\b",
        r"\bsql\b",
        r"\bpower\s*bi\b",
        r"\btableau\b",
        r"\bexcel\b",
        r"\bpython\b",
        r"\bdashboards?\b",
        r"\breporting\b",
    ]
    for kw in desc_keywords:
        if re.search(kw, desc_lower):
            desc_score += 2
    desc_score = min(10, desc_score)

    # Experience level bonus (fresher alignment)
    exp_bonus = 0
    if min_exp == 0 or "fresher" in exp_level.lower() or "0-1" in exp_level.lower():
        exp_bonus = 5

    total_score = title_score + skills_score + desc_score + exp_bonus

    # If title is a strong match but skills/description are minimal, ensure baseline score
    if has_strong_title and total_score < 50:
        total_score = 50

    return max(0, min(100, int(round(total_score))))


def is_relevant_job(job: Any, min_threshold: Optional[int] = None) -> Tuple[bool, int, str]:
    """
    Evaluates whether a job meets the minimum relevance threshold.
    Returns (is_relevant, score, reason).
    """
    threshold = min_threshold if min_threshold is not None else get_min_relevance()
    score = score_job(job)
    if score >= threshold:
        return True, score, f"Meets threshold ({score} >= {threshold})"
    return False, score, f"Below threshold ({score} < {threshold})"
