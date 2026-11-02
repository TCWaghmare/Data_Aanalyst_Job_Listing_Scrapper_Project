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

def is_fresher_eligible(title: str, text: str) -> bool:
    """
    Checks if a job is suitable for freshers / candidates with 0-1 year experience.
    Disqualifies roles requiring seniority (Sr, Senior, Lead, Principal, Architect)
    or explicitly requiring 2+, 3+, 5+ years of experience.
    """
    combo = f"{title} {text}".lower()

    # Reject strict senior and lead roles
    if re.search(r"\b(sr\.?|senior|lead|principal|director|head\s+of|vp|architect|staff|manager)\b", combo):
        return False
    # Reject high-experience markers
    if re.search(r"\b(2\+|3\+|4\+|5\+|6\+|7\+|8\+|10\+)\b", combo):
        return False
    if re.search(r"\b(2|3|4|5|6|7|8)\s*(to|-)\s*\d+\s*years?\b", combo):
        return False
    if re.search(r"\bminimum\s+(2|3|4|5)\s+years?\b", combo):
        return False

    return True

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
