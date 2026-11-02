"""
Job Role Taxonomy and Fresher Experience Engine for Data Analytics Roles.
Focuses strictly on 0 to 1 Year Experience (Freshers, Trainees, Interns, Junior/Entry-Level).
Supports all 25 Core and Related Analytics roles.
"""

import re
from typing import Optional, Tuple, List, Dict, Any

CORE_ANALYTICS_ROLES = [
    "Data Analyst",
    "Junior Data Analyst",
    "Associate Data Analyst",
    "Business Data Analyst",
    "Business Analyst",
    "Reporting Analyst",
    "MIS Executive / MIS Analyst",
    "BI Analyst",
    "Business Intelligence Analyst",
    "Power BI Developer",
    "Tableau Developer",
    "SQL Analyst",
    "Data Visualization Analyst",
]

RELATED_ROLES = [
    "Product Analyst",
    "Operations Analyst",
    "Marketing Analyst",
    "Financial Analyst",
    "Customer Insights Analyst",
    "Risk Analyst",
    "Analytics Consultant",
    "Data Quality Analyst",
    "Junior Data Engineer",
    "Analytics Engineer",
    "Decision Scientist",
    "Junior Data Scientist",
]

ALL_ROLES = CORE_ANALYTICS_ROLES + RELATED_ROLES

ROLE_PATTERNS = [
    # Core roles
    ("Junior Data Analyst", re.compile(r"\b(jr\.?|junior|trainee|entry[- ]level|associate|intern|fresher)\s+(data\s+analyst|analytics\s+analyst)\b", re.I)),
    ("Associate Data Analyst", re.compile(r"\bassociate\s+data\s+analyst\b", re.I)),
    ("Business Data Analyst", re.compile(r"\bbusiness\s+data\s+analyst\b", re.I)),
    ("Data Visualization Analyst", re.compile(r"\b(data\s+visuali[sz]ation\s+analyst|visuali[sz]ation\s+analyst|dashboard\s+analyst)\b", re.I)),
    ("Power BI Developer", re.compile(r"\b(power\s*bi|powerbi)\s+(developer|analyst|engineer|consultant|specialist|trainee)\b", re.I)),
    ("Tableau Developer", re.compile(r"\btableau\s+(developer|analyst|engineer|consultant|specialist|trainee)\b", re.I)),
    ("SQL Analyst", re.compile(r"\bsql\s+(data\s+)?analyst\b", re.I)),
    ("MIS Executive / MIS Analyst", re.compile(r"\b(mis\s+executive|mis\s+analyst|management\s+information\s+system|mis\s+coordinator|mis\s+specialist)\b", re.I)),
    ("Business Intelligence Analyst", re.compile(r"\bbusiness\s+intelligence\s+(analyst|developer|specialist)\b", re.I)),
    ("BI Analyst", re.compile(r"\bbi\s+(analyst|developer|consultant|specialist)\b", re.I)),
    ("Reporting Analyst", re.compile(r"\b(reporting\s+analyst|reports\s+analyst|bi\s+reporting)\b", re.I)),
    ("Business Analyst", re.compile(r"\bbusiness\s+analyst\b", re.I)),
    ("Data Analyst", re.compile(r"\b(data\s+analyst|analytics\s+specialist|data\s+analytics\s+associate|lead\s+data\s+analyst|senior\s+data\s+analyst|sr\.?\s+data\s+analyst)\b", re.I)),

    # Related roles
    ("Junior Data Scientist", re.compile(r"\b(jr\.?|junior|trainee|associate|intern|entry[- ]level|fresher)\s+data\s+scientist\b", re.I)),
    ("Decision Scientist", re.compile(r"\b(decision\s+scientist|decision\s+science\s+analyst)\b", re.I)),
    ("Junior Data Engineer", re.compile(r"\b(jr\.?|junior|trainee|associate|intern|entry[- ]level|fresher)\s+data\s+engineer\b", re.I)),
    ("Analytics Engineer", re.compile(r"\banalytics\s+engineer\b", re.I)),
    ("Data Quality Analyst", re.compile(r"\b(data\s+quality|dqa)\s+analyst\b", re.I)),
    ("Analytics Consultant", re.compile(r"\b(analytics\s+consultant|data\s+consultant|bi\s+consultant)\b", re.I)),
    ("Customer Insights Analyst", re.compile(r"\b(customer\s+insights?|consumer\s+insights?|cx\s+analyst)\b", re.I)),
    ("Risk Analyst", re.compile(r"\b(risk\s+analyst|fraud\s+analyst|credit\s+risk\s+analyst)\b", re.I)),
    ("Financial Analyst", re.compile(r"\b(financial\s+analyst|finance\s+analyst|fp&a\s+analyst)\b", re.I)),
    ("Marketing Analyst", re.compile(r"\b(marketing\s+analyst|growth\s+analyst|digital\s+marketing\s+analyst)\b", re.I)),
    ("Operations Analyst", re.compile(r"\b(operations?\s+analyst|supply\s+chain\s+analyst)\b", re.I)),
    ("Product Analyst", re.compile(r"\bproduct\s+analyst\b", re.I)),
]

SKILL_KEYWORDS = [
    "SQL", "Python", "R", "Power BI", "Tableau", "Excel", "Advanced Excel",
    "Looker", "dbt", "Snowflake", "Databricks", "BigQuery", "PostgreSQL",
    "MySQL", "AWS", "Azure", "GCP", "Pandas", "NumPy", "Statistics",
    "Machine Learning", "ETL", "Data Warehousing", "Data Modeling", "Alteryx",
    "SSIS", "SSRS", "Git", "Jira", "Spark", "Airflow", "Google Analytics"
]

def classify_role(title: str, description: str = "") -> Tuple[str, str]:
    cleaned_title = title.lower()
    for role_name, pattern in ROLE_PATTERNS:
        if pattern.search(cleaned_title):
            category = "Core Analytics" if role_name in CORE_ANALYTICS_ROLES else "Related"
            return role_name, category

    if "analyst" in cleaned_title or "analytics" in cleaned_title:
        for role_name, pattern in ROLE_PATTERNS:
            if pattern.search(description[:400].lower()):
                category = "Core Analytics" if role_name in CORE_ANALYTICS_ROLES else "Related"
                return role_name, category

    return "Data Analyst", "Core Analytics"

def analyze_job_fresher_eligibility(title: str, text: str = "", raw_fields: dict = None) -> Tuple[bool, str, int, int]:
    """
    Deeply analyzes job title, full description, and raw metadata to strictly determine
    if a job is for Freshers / 0-1 year experience candidates.
    Returns: (is_fresher: bool, reason: str, min_exp: int, max_exp: int)
    """
    title_clean = (title or "").strip()
    text_clean = (text or "").strip()
    combined = f"{title_clean}\n{text_clean}".lower()
    title_lower = title_clean.lower()

    # 1. Title Checks - Hard Disqualifications
    senior_title_patterns = [
        r'\b(sr\.?|senior|lead|principal|director|head\s+of|vp|vice\s+president|chief|architect|staff)\b',
        r'\b(team\s+lead|project\s+manager|engineering\s+manager|analytics\s+manager|product\s+manager)\b',
        r'\bmanager\b',
        r'\b(ii|iii|iv|v|level\s+[2-9]|l[2-9])\b',
        r'\b(experienced|mid[- ]level|mid\s+senior)\b',
    ]

    for p in senior_title_patterns:
        if re.search(p, title_lower):
            if not re.search(r'\b(fresher|freshers|trainee|intern|internship)\b', title_lower):
                matched = re.search(p, title_lower).group(0)
                return False, f"Title contains senior/experienced indicator: '{matched}'", 2, 5

    # 2. Raw Structured Experience Checks
    if raw_fields:
        min_e = raw_fields.get("min_experience")
        max_e = raw_fields.get("max_experience")
        if min_e is not None and isinstance(min_e, (int, float)) and min_e > 1:
            return False, f"Structured metadata indicates required minimum experience: {min_e} years", int(min_e), int(max_e or min_e)

    # 3. Explicit Fresher overrides in text
    has_fresher_override = bool(re.search(
        r'\b(fresher|freshers|fresher\s+welcome|freshers\s+welcome|freshers\s+can\s+apply|no\s+experience\s+required|0\s*years?\s*experience|0-1\s*years?|0\s*to\s*1\s*years?|0\s*-\s*1\s*yr|campus\s+hiring|2024\s+batch|2025\s+batch|2026\s+batch|college\s+graduates?|recent\s+graduates?)\b',
        combined
    ))

    # 4. Job Description Experience Requirement Analysis
    disqualifying_exp_patterns = [
        (r'\b([2-9]|1\d)\+?\s*(years?|yrs?)\s+of\s+(relevant\s+|work\s+|professional\s+|industry\s+)?experience\b', "Requires {match}"),
        (r'\bminimum\s+(of\s+)?([2-9]|1\d)\s*(years?|yrs?)\b', "Requires minimum {match}"),
        (r'\bat\s+least\s+([2-9]|1\d)\s*(years?|yrs?)\b', "Requires at least {match}"),
        (r'\b([2-9]|1\d)\s*(to|-)\s*\d+\s*(years?|yrs?)\s+experience\b', "Requires {match}"),
        (r'\bexperience\s*(required|level)?\s*[:\-]\s*([2-9]|1\d)\s*(to|\-|\+)?\s*\d*\s*(years?|yrs?)\b', "Experience specified as {match}"),
        (r'\brequire(s|d)?\s+([2-9]|1\d)\+?\s*(years?|yrs?)\b', "Requires {match}"),
        (r'\b([3-9]|1\d)\+?\s*(years?|yrs?)\b', "Explicit experience requirement: {match}"),
    ]

    for p, reason_tmpl in disqualifying_exp_patterns:
        m = re.search(p, combined)
        if m:
            matched_text = m.group(0)
            start_pos = m.start()
            preceding = combined[max(0, start_pos - 10):start_pos]
            if "0" in preceding or "0 to" in preceding or "0-" in preceding:
                continue

            extracted_num = re.search(r'\d+', matched_text)
            num_val = int(extracted_num.group(0)) if extracted_num else 3
            if num_val >= 2:
                if has_fresher_override and num_val == 2 and ("0-2" in combined or "0 to 2" in combined):
                    pass
                else:
                    return False, reason_tmpl.format(match=matched_text), num_val, num_val + 2

    # 5. Senior Responsibility / Leadership Markers in Description
    senior_resp_patterns = [
        r'\b(lead\s+a\s+team\s+of|manage\s+a\s+team\s+of|supervise\s+junior|mentor\s+junior\s+analysts?)\b',
        r'\b(proven\s+track\s+record\s+of\s+leading|extensive\s+industry\s+experience)\b',
        r'\b(seasoned\s+professional|deep\s+expertise\s+in\s+managing\s+teams)\b'
    ]
    for p in senior_resp_patterns:
        if re.search(p, text_clean.lower()):
            matched_resp = re.search(p, text_clean.lower()).group(0)
            return False, f"JD contains senior responsibility: '{matched_resp}'", 3, 5

    # 6. Granular Fresher Level Assignment
    if re.search(r'\b(intern|internship|trainee|apprentice|student|campus)\b', combined):
        return True, "Internship / Trainee role (0 Years)", 0, 0
    if has_fresher_override or re.search(r'\b(entry[- ]level|junior|associate|grad|graduate)\b', combined):
        return True, "Fresher / Entry-Level analytics role (0-1 Year)", 0, 1

    return True, "Entry-level fresher compatible role (0-1 Year)", 0, 1

def is_fresher_eligible(title: str, text: str = "", raw_fields: dict = None) -> bool:
    """
    Checks if a job is suitable for freshers / candidates with 0-1 year experience.
    Uses deep multi-layer analysis on title, full description text, and metadata.
    """
    eligible, _, _, _ = analyze_job_fresher_eligibility(title=title, text=text, raw_fields=raw_fields)
    return eligible

def extract_fresher_experience(title: str, text: str) -> str:
    """
    Assigns granular 0 to 1 year experience category:
    - Fresher (0 Years)
    - 0 - 1 Year (Junior / Entry-Level)
    - Internship / Trainee
    """
    combo = f"{title} {text}".lower()
    if re.search(r"\b(intern|internship|trainee|apprentice|student|campus)\b", combo):
        return "Internship / Trainee (0 Years)"
    if re.search(r"\b(fresher|freshers|0\s*years?|no\s+experience|recent\s+graduate|entry[- ]level)\b", combo):
        return "Fresher (0 Years)"
    return "0 - 1 Year (Junior / Entry-Level)"

# Compatibility alias
extract_experience_level = extract_fresher_experience

def extract_skills(text: str) -> List[str]:
    found = []
    text_lower = f" {text.lower()} "
    for skill in SKILL_KEYWORDS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return sorted(list(set(found)))

def detect_work_mode(location: str, title: str, description: str) -> str:
    full = f"{location} {title} {description}".lower()
    # Check for explicit on-site / office keywords
    if "on-site" in full or "onsite" in full or "work from office" in full or "in-office" in full:
        if "hybrid" in full:
            return "Hybrid"
        return "On-Site"
    # Check for hybrid / flexible
    if "hybrid" in full or "flexible" in full or "2 days from home" in full or "3 days office" in full:
        return "Hybrid"
    # Check for remote (ensuring no negation)
    if "remote" in full or "work from home" in full or "wfh" in full:
        if any(neg in full for neg in ["not remote", "no remote", "cannot be remote", "non-remote", "not work from home"]):
            return "On-Site"
        return "Remote"
    return "On-Site"

def normalize_country(location: str) -> str:
    loc = location.lower()
    indian_cities = [
        "india", "pune", "pcmc", "pimpri", "hinjawadi", "hinjewadi", "nagpur",
        "hyderabad", "aurangabad", "sambhajinagar", "sambhaji nagar",
        "bangalore", "bengaluru", "mumbai", "delhi", "noida", "gurgaon",
        "gurugram", "chennai", "kolkata", "ahmedabad", "jaipur"
    ]
    for city in indian_cities:
        if city in loc:
            return "India"
    if any(k in loc for k in ["remote", "worldwide", "anywhere", "open to india"]):
        return "Remote (Open to India)"
    return "India"
