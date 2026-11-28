"""
Deep Job Analysis Engine for ATS Resume & Cover Letter Tailoring.
Performs comprehensive multi-dimensional job posting analysis:
- Technical Skills & Tools Taxonomy
- Soft Skills & Core Competencies
- Responsibilities & Day-to-Day Tasks
- Role Objectives & Hiring Signals
- Experience & Seniority Requirements
- Industry & Business Domain Context
- Grounded Skill Gap Analysis (Compares against Candidate Knowledge Base)
Strictly enforces TRUTHFULNESS: Never hallucinates or invents non-existent technical skills.
"""

import re
import logging
from typing import Dict, List, Any, Set, Tuple

logger = logging.getLogger("deep_job_analyzer")

# Comprehensive Technical Skill Taxonomy for Data & Analytics Roles
TECHNICAL_TAXONOMY = {
    # BI & Visualization
    "power bi": "Business Intelligence & Visualization",
    "tableau": "Business Intelligence & Visualization",
    "looker": "Business Intelligence & Visualization",
    "quicksight": "Business Intelligence & Visualization",
    "qlik sense": "Business Intelligence & Visualization",
    "qlikview": "Business Intelligence & Visualization",
    "dax": "BI Calculations & Data Modeling",
    "power query": "Data Transformation & ETL",
    "power pivot": "Data Modeling",
    "dashboard design": "Data Visualization",
    "kpi reporting": "Executive Reporting",
    "executive reporting": "Executive Reporting",
    "data visualization": "Data Visualization",

    # Spreadsheets & Data Management
    "excel": "Spreadsheets & Analytics",
    "advanced excel": "Spreadsheets & Analytics",
    "pivot tables": "Spreadsheets & Analytics",
    "xlookup": "Spreadsheets & Analytics",
    "vlookup": "Spreadsheets & Analytics",
    "sumifs": "Spreadsheets & Analytics",
    "macros": "Spreadsheets & Analytics",
    "vba": "Spreadsheets Automation",
    "powerpoint": "Presentation & Reporting",
    "mis": "Management Information Systems",
    "sales mis": "Sales Operations & MIS",
    "mis reporting": "MIS & Executive Reporting",
    "sales operations": "Sales Analytics & Operations",
    "sales reporting": "Sales Analytics",

    # Database & Querying
    "sql": "Databases & Querying",
    "mysql": "Databases & Querying",
    "postgresql": "Databases & Querying",
    "t-sql": "Databases & Querying",
    "pl/sql": "Databases & Querying",
    "sqlite": "Databases & Querying",
    "oracle": "Databases & Querying",
    "sql server": "Databases & Querying",
    "relational databases": "Databases & Querying",
    "stored procedures": "Databases & Querying",
    "ctes": "Advanced SQL",

    # Modern Data Stack & Warehousing
    "snowflake": "Cloud Data Warehousing",
    "bigquery": "Cloud Data Warehousing",
    "redshift": "Cloud Data Warehousing",
    "azure synapse": "Cloud Data Warehousing",
    "dbt": "Data Transformation & Modeling",
    "fivetran": "Data Ingestion & Pipelines",
    "hightouch": "Reverse ETL",
    "airbyte": "Data Ingestion",
    "airflow": "Workflow Orchestration",
    "etl": "Data Engineering & Pipelines",
    "elt": "Data Engineering & Pipelines",
    "data pipeline": "Data Engineering",
    "data modeling": "Data Architecture & Modeling",
    "star schema": "Dimensional Modeling",
    "snowflake schema": "Dimensional Modeling",

    # Programming & Data Science
    "python": "Programming & Data Science",
    "pandas": "Data Manipulation",
    "numpy": "Numerical Computing",
    "r": "Statistical Computing",
    "matplotlib": "Data Visualization",
    "seaborn": "Data Visualization",
    "scikit-learn": "Machine Learning",
    "statistics": "Statistical Analysis",
    "machine learning": "Data Science & ML",
    "predictive modeling": "Predictive Analytics",
    "eda": "Exploratory Data Analysis",

    # Cloud & Enterprise Platforms
    "azure": "Cloud Platforms",
    "aws": "Cloud Platforms",
    "gcp": "Cloud Platforms",
    "microsoft fabric": "Cloud Analytics",
    "git": "Version Control",
    "github": "Version Control",
    "crm": "CRM Systems",
    "salesforce": "CRM Systems",
    "hubspot": "CRM Systems",
    "zoho": "CRM Systems",
    "erp": "ERP Systems",
    "sap": "Enterprise Systems",
    "jira": "Project Management",

    # Data Quality & Governance
    "data cleaning": "Data Quality & Cleansing",
    "data validation": "Data Validation",
    "data preparation": "Data Preparation",
    "data interpretation": "Data Analysis",
    "data quality": "Data Quality Assurance",
    "exception reporting": "Anomaly Detection & MIS",
    "data governance": "Data Governance"
}

CANONICAL_NAMES = {
    "power bi": "Power BI",
    "sql": "SQL",
    "python": "Python",
    "excel": "Excel",
    "advanced excel": "Advanced Excel",
    "powerpoint": "PowerPoint",
    "dax": "DAX",
    "power query": "Power Query",
    "power pivot": "Power Pivot",
    "tableau": "Tableau",
    "looker": "Looker",
    "quicksight": "QuickSight",
    "qlik sense": "Qlik Sense",
    "qlikview": "QlikView",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "redshift": "Redshift",
    "azure synapse": "Azure Synapse",
    "dbt": "dbt",
    "fivetran": "Fivetran",
    "hightouch": "Hightouch",
    "airbyte": "Airbyte",
    "airflow": "Airflow",
    "etl": "ETL",
    "elt": "ELT",
    "data pipeline": "Data Pipeline",
    "data modeling": "Data Modeling",
    "star schema": "Star Schema",
    "snowflake schema": "Snowflake Schema",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "t-sql": "T-SQL",
    "pl/sql": "PL/SQL",
    "sqlite": "SQLite",
    "oracle": "Oracle",
    "sql server": "SQL Server",
    "ms sql server": "SQL Server",
    "relational databases": "Relational Databases",
    "stored procedures": "Stored Procedures",
    "ctes": "CTEs",
    "pivot tables": "Pivot Tables",
    "xlookup": "XLOOKUP",
    "vlookup": "VLOOKUP",
    "sumifs": "SUMIFS",
    "macros": "Macros",
    "vba": "VBA",
    "mis": "MIS",
    "sales mis": "Sales MIS",
    "mis reporting": "MIS Reporting",
    "sales operations": "Sales Operations",
    "sales reporting": "Sales Reporting",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "r": "R",
    "matplotlib": "Matplotlib",
    "seaborn": "Seaborn",
    "scikit-learn": "Scikit-Learn",
    "statistics": "Statistics",
    "machine learning": "Machine Learning",
    "predictive modeling": "Predictive Analytics",
    "eda": "Exploratory Data Analysis (EDA)",
    "azure": "Azure",
    "aws": "AWS",
    "gcp": "GCP",
    "microsoft fabric": "Microsoft Fabric",
    "fabric": "Fabric",
    "git": "Git",
    "github": "GitHub",
    "crm": "CRM",
    "salesforce": "Salesforce",
    "hubspot": "HubSpot",
    "zoho": "Zoho",
    "erp": "ERP",
    "sap": "SAP",
    "jira": "Jira",
    "spark": "Apache Spark",
    "pyspark": "PySpark",
    "kafka": "Kafka",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "data cleaning": "Data Cleaning",
    "data validation": "Data Validation",
    "data preparation": "Data Preparation",
    "data quality": "Data Quality",
    "data governance": "Data Governance",
    "exception reporting": "Exception Reporting",
    "dashboard design": "Dashboard Design",
    "kpi reporting": "KPI Reporting",
    "data visualization": "Data Visualization",
    "executive reporting": "Executive Reporting",
    "pl-300": "PL-300 Certification",
    "dp-600": "DP-600 Certification",
    "dp-900": "DP-900 Certification",
    "dp-203": "DP-203 Certification",
    "az-900": "AZ-900 Certification",
    "pmp": "PMP Certification",
    "business intelligence": "Business Intelligence",
    "data analysis": "Data Analysis",
    "trend analysis": "Trend Analysis",
    "a/b testing": "A/B Testing",
    "hypothesis testing": "Hypothesis Testing",
    "root cause analysis": "Root Cause Analysis",
    "stakeholder management": "Stakeholder Management",
    "requirements gathering": "Requirements Gathering",
    "process improvement": "Process Improvement"
}

# Soft Skills & Competencies Taxonomy
SOFT_SKILLS_TAXONOMY = {
    "problem solving": "Analytical Problem Solving",
    "communication": "Effective Stakeholder Communication",
    "collaboration": "Cross-Functional Collaboration",
    "attention to detail": "Meticulous Attention to Detail",
    "analytical thinking": "Structured Analytical Thinking",
    "critical thinking": "Critical Decision Support",
    "stakeholder management": "Executive Stakeholder Engagement",
    "presentation skills": "Executive Reporting & Presentations",
    "time management": "Prioritization & Deadline Delivery",
    "adaptability": "Fast Learner & Agile Adaptability",
    "teamwork": "Cross-Team Synergy",
    "leadership": "Project Ownership & Team Leadership",
    "process improvement": "Process Optimization & Automation"
}

DUTIES_TAXONOMY = {
    "kpi reporting": "Executive & Operational Reporting",
    "dashboard design": "Data Visualization & Dashboards",
    "data cleaning": "Data Quality & Cleansing",
    "data transformation": "ETL & Transformation",
    "data validation": "Data Quality Assurance",
    "executive reporting": "Executive Reporting",
    "trend analysis": "Data Analysis & Trends",
    "root cause analysis": "Analytical Problem Solving",
    "a/b testing": "Experimentation & Optimization",
    "hypothesis testing": "Statistical Analysis",
    "requirements gathering": "Business Analysis",
    "stakeholder management": "Stakeholder Engagement",
    "process improvement": "Process Optimization",
    "exception reporting": "Anomaly Detection & MIS"
}

CERTIFICATIONS_TAXONOMY = {
    "pl-300": "Microsoft Certified: Power BI Data Analyst Associate (PL-300)",
    "dp-600": "Microsoft Certified: Fabric Analytics Engineer Associate (DP-600)",
    "dp-900": "Microsoft Certified: Azure Data Fundamentals (DP-900)",
    "dp-203": "Microsoft Certified: Azure Data Engineer Associate (DP-203)",
    "az-900": "Microsoft Certified: Azure Fundamentals (AZ-900)",
    "aws certified": "AWS Certified Data Analytics / Cloud",
    "pmp": "Project Management Professional (PMP)",
    "tableau desktop specialist": "Tableau Desktop Specialist"
}

class DeepJobAnalysisEngine:
    def __init__(self):
        pass

    def analyze_job(
        self,
        job_or_title: Any,
        company: str = "",
        description: str = "",
        skills: List[str] = None,
        responsibilities: List[str] = None,
        requirements: List[str] = None,
        profile: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Conducts deep multi-dimensional analysis of the job description
        and performs grounded gap analysis against candidate profile.
        Supports both analyze_job(job_dict, profile) and analyze_job(title, company, description, ...).
        Uses weighted keyword extraction (required=3, preferred=1) and strict evidence matching.
        """
        qualifications = []
        preferred_qualifications = []
        ats_keywords_in = []

        if isinstance(job_or_title, dict):
            job_dict = job_or_title
            if isinstance(company, dict):
                profile = company
            job_title = job_dict.get("title") or job_dict.get("job_title", "Data Analyst")
            company = job_dict.get("company", "Target Employer")
            description = job_dict.get("description", "")
            skills = job_dict.get("skills", []) or skills
            responsibilities = job_dict.get("responsibilities", []) or job_dict.get("duties", []) or responsibilities
            requirements = job_dict.get("requirements", []) or requirements
            qualifications = job_dict.get("qualifications", [])
            preferred_qualifications = job_dict.get("preferred_qualifications", []) or job_dict.get("preferred_skills", []) or job_dict.get("nice_to_have", [])
            ats_keywords_in = job_dict.get("ats_keywords", [])
        else:
            job_title = job_or_title or "Data Analyst"
            company = company or "Target Employer"
            description = description or ""

        # 1. Extract Keywords with Weights (required = 3, preferred = 1)
        ordered_keywords, keyword_weights, keyword_categories = self._extract_keywords_and_weights(
            job_title=job_title,
            company=company,
            description=description,
            skills=skills,
            responsibilities=responsibilities,
            requirements=requirements,
            qualifications=qualifications,
            preferred_qualifications=preferred_qualifications,
            ats_keywords=ats_keywords_in
        )

        # 2. Extract Soft Skills & Behavioral Expectations
        combined_text = f"{job_title} {company} {description} {' '.join(skills or [])} {' '.join(responsibilities or [])} {' '.join(requirements or [])}".lower()
        required_soft = self._extract_soft_skills(combined_text)

        # 3. Detect Seniority & Experience Requirements
        experience_spec = self._detect_experience_level(job_title, description)

        # 4. Detect Business Domain & Hiring Signals
        domain_signals = self._detect_domain_and_hiring_signals(job_title, description, company)

        # 5. Candidate Profile Grounding & Skill Gap Analysis
        gap_analysis = self._perform_grounded_gap_analysis(
            keywords=ordered_keywords,
            keyword_weights=keyword_weights,
            keyword_categories=keyword_categories,
            required_soft=required_soft,
            profile=profile
        )

        match_score = gap_analysis["match_score"]
        matched_keywords = gap_analysis["matched_skills"]
        missing_keywords = gap_analysis["missing_skills"]
        matched_count = gap_analysis["matched_count"]
        total_count = gap_analysis["total_count"]
        missing_count = gap_analysis["missing_count"]

        technical_requirements = [
            {"name": k, "category": keyword_categories.get(k, "Technical Tool"), "weight": keyword_weights.get(k, 1)}
            for k in ordered_keywords
        ]

        return {
            "match_score": match_score,
            "ats_score": match_score,
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords,
            "matched_count": matched_count,
            "total_count": total_count,
            "missing_count": missing_count,
            "gap_analysis": gap_analysis,
            "skill_gap_analysis": gap_analysis,
            "domain_signals": domain_signals,
            "experience_requirements": experience_spec,
            "job_summary": {
                "title": job_title,
                "company": company,
                "domain": domain_signals["domain"],
                "experience_required": experience_spec["experience_text"],
                "min_years": experience_spec["min_years"],
                "max_years": experience_spec["max_years"],
                "hiring_signals": domain_signals["hiring_signals"],
                "primary_focus": domain_signals["primary_focus"]
            },
            "technical_requirements": technical_requirements,
            "soft_skill_requirements": required_soft,
            "ats_keywords": ordered_keywords,
            "recommendations": self._generate_strategic_recommendations(gap_analysis, domain_signals, profile)
        }

    def _extract_keywords_and_weights(
        self,
        job_title: str,
        company: str,
        description: str,
        skills: List[str] = None,
        responsibilities: List[str] = None,
        requirements: List[str] = None,
        qualifications: List[str] = None,
        preferred_qualifications: List[str] = None,
        ats_keywords: List[str] = None
    ) -> Tuple[List[str], Dict[str, int], Dict[str, str]]:
        """
        Extracts keywords from the JD (skills, tools, certifications, duties) with weights:
        required = 3, preferred = 1.
        """
        # Normalize list inputs
        def _to_clean_list(val: Any) -> List[str]:
            if not val:
                return []
            if isinstance(val, list):
                return [str(v).strip() for v in val if str(v).strip()]
            if isinstance(val, str):
                return [s.strip() for s in val.split("\n") if s.strip()]
            return []

        skills_list = _to_clean_list(skills)
        resp_list = _to_clean_list(responsibilities)
        req_list = _to_clean_list(requirements)
        qual_list = _to_clean_list(qualifications)
        pref_list = _to_clean_list(preferred_qualifications)
        ats_list = _to_clean_list(ats_keywords)

        # Parse description lines by section
        preferred_lines = []
        required_lines = []
        duties_lines = []
        general_lines = []

        current_section = "GENERAL"
        for line in (description or "").split("\n"):
            clean_line = line.strip()
            if not clean_line:
                continue
            lower_line = clean_line.lower()

            if any(h in lower_line for h in ["preferred qualification", "preferred skill", "nice to have", "bonus points", "good to have", "desired skill", "plus factor", "bonus skill", "additional qualification", "desirable extras", "desirable:"]):
                current_section = "PREFERRED"
                continue
            elif any(h in lower_line for h in ["requirement", "qualification", "what you'll need", "what you need", "what you will need", "minimum qualification", "basic qualification", "must have", "what we are looking for", "what we're looking for", "skills required", "required skill", "prerequisite", "about you:"]):
                current_section = "REQUIRED"
                continue
            elif any(h in lower_line for h in ["responsibilities", "duties", "what you'll do", "what you will do", "key task", "day to day", "day-to-day", "role overview"]):
                current_section = "DUTIES"
                continue
            elif any(h in lower_line for h in ["what we offer", "benefits", "perks", "compensation", "about us", "about the company", "who we are", "equal opportunity", "eeo", "about solstice", "how to apply"]):
                current_section = "OTHER"
                continue

            # Inline heading markers
            if any(m in lower_line for m in ["preferred:", "nice to have:", "plus:", "bonus:"]):
                preferred_lines.append(clean_line)
            elif any(m in lower_line for m in ["required:", "must have:", "mandatory:"]):
                required_lines.append(clean_line)
            else:
                if current_section == "PREFERRED":
                    preferred_lines.append(clean_line)
                elif current_section == "REQUIRED":
                    required_lines.append(clean_line)
                elif current_section == "DUTIES":
                    duties_lines.append(clean_line)
                elif current_section != "OTHER":
                    general_lines.append(clean_line)

        preferred_pool = preferred_lines + pref_list
        required_pool = required_lines + req_list + qual_list + ats_list
        duties_pool = duties_lines + resp_list
        general_pool = general_lines + ([job_title] if job_title else [])

        keyword_weights: Dict[str, int] = {}
        keyword_categories: Dict[str, str] = {}
        ordered_keywords: List[str] = []

        BOILERPLATE_HEADERS = {
            "about you", "what we offer", "desirable extras", "equal opportunity employer",
            "about solstice advanced materials", "about solstice", "about us", "who you are",
            "who we are", "how to apply", "application process", "key responsibilities",
            "qualifications & requirements", "qualifications and requirements",
            "minimum qualifications", "preferred qualifications", "requirements",
            "responsibilities", "duties", "overview", "job overview", "summary",
            "job summary", "benefits", "perks", "compensation", "diversity & inclusion"
        }

        def add_kw(raw_name: str, weight: int, category: str = "Technical Tool"):
            clean = raw_name.strip()
            if clean.endswith(":") or clean.endswith("?"):
                return
            # Strip bullet points and numbering
            clean = re.sub(r"^[\s\-*•\d\.\)]+", "", clean).strip()
            if not clean or len(clean) < 2:
                return
            if clean.endswith(":") or clean.endswith("?"):
                return
            # Remove leading boilerplate like "2+ years of", "strong", "experience in"
            clean = re.sub(
                r"^(?:\d+\+?\s*years?\s*(?:of)?\s*)?(?:experience\s+with|proficiency\s+in|knowledge\s+of|strong\s+|hands[- ]on\s+|demonstrated\s+experience\s+in|proven\s+track\s+record\s+in|familiarity\s+with)\s+",
                "",
                clean,
                flags=re.IGNORECASE
            ).strip()
            if not clean or len(clean) < 2:
                return

            clean_lower = clean.lower()
            if clean_lower in BOILERPLATE_HEADERS:
                return
            if any(clean_lower.startswith(prefix) for prefix in ["about ", "what we offer", "equal opportunity", "how to apply", "why join", "we offer"]):
                return

            canonical = CANONICAL_NAMES.get(clean.lower(), clean.title() if len(clean) > 3 else clean.upper())
            if canonical not in keyword_weights:
                ordered_keywords.append(canonical)
                keyword_weights[canonical] = weight
                keyword_categories[canonical] = category
            else:
                keyword_weights[canonical] = max(keyword_weights[canonical], weight)

        # 1. Process explicit items in structured lists
        for item in (req_list + qual_list + ats_list):
            lower_item = item.lower()
            is_pref = any(m in lower_item for m in ["preferred", "nice to have", "plus", "bonus", "optional", "good to have"])
            w = 1 if is_pref else 3
            if len(item) <= 50 and len(item.split()) <= 6:
                add_kw(item, w, "Required Skill" if w == 3 else "Preferred Skill")

        # 2. Process explicit items in skills
        for item in skills_list:
            lower_item = item.lower()
            is_pref = any(m in lower_item for m in ["preferred", "nice to have", "plus", "bonus", "optional", "good to have"])
            w = 1 if is_pref else 3
            if len(item) <= 50:
                add_kw(item, w, "Technical Skill")

        # 3. Process explicit items in preferred_pool
        for item in pref_list:
            if len(item) <= 50 and len(item.split()) <= 6:
                add_kw(item, 1, "Preferred Skill")

        # 4. Process explicit items in duties_pool
        for item in duties_pool:
            lower_item = item.lower()
            for duty, cat in DUTIES_TAXONOMY.items():
                if re.search(r"\b" + re.escape(duty) + r"\b", lower_item):
                    add_kw(duty, 1, cat)

        # 5. Scan text pools against Taxonomies
        # A. Required pool text
        req_text = " ".join(required_pool).lower()
        if req_text:
            for tool, cat in TECHNICAL_TAXONOMY.items():
                if re.search(r"\b" + re.escape(tool) + r"\b", req_text):
                    add_kw(tool, 3, cat)
            for cert, cat in CERTIFICATIONS_TAXONOMY.items():
                if re.search(r"\b" + re.escape(cert) + r"\b", req_text):
                    add_kw(cert, 3, cat)
            for duty, cat in DUTIES_TAXONOMY.items():
                if re.search(r"\b" + re.escape(duty) + r"\b", req_text):
                    add_kw(duty, 3, cat)

        # B. Preferred pool text
        pref_text = " ".join(preferred_pool).lower()
        if pref_text:
            for tool, cat in TECHNICAL_TAXONOMY.items():
                if re.search(r"\b" + re.escape(tool) + r"\b", pref_text):
                    add_kw(tool, 1, cat)
            for duty, cat in DUTIES_TAXONOMY.items():
                if re.search(r"\b" + re.escape(duty) + r"\b", pref_text):
                    add_kw(duty, 1, cat)

        # C. Duties pool text
        duties_text = " ".join(duties_pool).lower()
        if duties_text:
            for tool, cat in TECHNICAL_TAXONOMY.items():
                if re.search(r"\b" + re.escape(tool) + r"\b", duties_text):
                    add_kw(tool, 1, cat)
            for duty, cat in DUTIES_TAXONOMY.items():
                if re.search(r"\b" + re.escape(duty) + r"\b", duties_text):
                    add_kw(duty, 1, cat)

        # D. General pool text
        gen_text = " ".join(general_pool).lower()
        if gen_text:
            for tool, cat in TECHNICAL_TAXONOMY.items():
                if re.search(r"\b" + re.escape(tool) + r"\b", gen_text):
                    add_kw(tool, 3, cat)
            for cert, cat in CERTIFICATIONS_TAXONOMY.items():
                if re.search(r"\b" + re.escape(cert) + r"\b", gen_text):
                    add_kw(cert, 3, cat)
            for duty, cat in DUTIES_TAXONOMY.items():
                if re.search(r"\b" + re.escape(duty) + r"\b", gen_text):
                    add_kw(duty, 1, cat)

        # Fallback if no keywords found
        if not ordered_keywords:
            for s in skills_list[:5]:
                add_kw(s, 3, "Technical Skill")
            if not ordered_keywords:
                for kw in ["Data Analysis", "Reporting", "Documentation"]:
                    add_kw(kw, 3, "General Competency")

        return ordered_keywords, keyword_weights, keyword_categories

    def _extract_soft_skills(self, text_lower: str) -> List[str]:
        found = []
        for term, formal in SOFT_SKILLS_TAXONOMY.items():
            if re.search(r"\b" + re.escape(term) + r"\b", text_lower):
                if formal not in found:
                    found.append(formal)
        if not found:
            found = ["Analytical Problem Solving", "Cross-Functional Collaboration", "Meticulous Attention to Detail", "Executive Reporting"]
        return found

    def _detect_experience_level(self, title: str, description: str) -> Dict[str, Any]:
        text = f"{title} {description}".lower()
        min_years = 0
        max_years = 1
        exp_text = "0 - 1 Year (Fresher / Entry-Level)"

        m1 = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)", text)
        if m1:
            min_years = int(m1.group(1))
            max_years = int(m1.group(2))
            exp_text = f"{min_years} - {max_years} Years"
        else:
            m2 = re.search(r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)", text)
            if m2:
                years = int(m2.group(1))
                min_years = years
                max_years = years + 2
                exp_text = f"{years}+ Years"
            elif any(w in text for w in ["fresher", "entry-level", "graduate trainee", "intern", "junior", "0-1"]):
                min_years = 0
                max_years = 1
                exp_text = "0 - 1 Year (Fresher / Junior)"

        return {
            "min_years": min_years,
            "max_years": max_years,
            "experience_text": exp_text
        }

    def _detect_domain_and_hiring_signals(self, title: str, description: str, company: str) -> Dict[str, Any]:
        text = f"{title} {description} {company}".lower()
        domain = "General Business Intelligence & Analytics"
        signals = []
        focus = "Data Analysis & KPI Reporting"

        if any(w in text for w in ["sales mis", "mis executive", "sales operations", "territory", "sampling"]):
            domain = "Sales Operations & Enterprise MIS"
            signals.append("Values daily CRM validation and high accuracy in recurring sales MIS reporting.")
            signals.append("Requires strong mastery of Excel formulas (Pivot Tables, XLOOKUP, SUMIFS) for exception reporting.")
            focus = "Sales Performance Tracking & MIS Reporting"
        elif any(w in text for w in ["revenue", "financial analyst", "pricing", "billing", "audit"]):
            domain = "Financial & Revenue Operations Analytics"
            signals.append("Prioritizes financial metrics tracking (ARR, billing reconciliation, discount analysis).")
            focus = "Financial Modeling & Revenue Reporting"
        elif any(w in text for w in ["dbt", "data pipeline", "analytics engineer", "snowflake", "bigquery"]):
            domain = "Analytics Engineering & Modern Data Stack"
            signals.append("Values production-grade data modeling, modular SQL (dbt), and robust semantic schemas.")
            focus = "Data Modeling & Automated ETL Pipelines"
        elif any(w in text for w in ["power bi", "dax", "tableau", "dashboard"]):
            domain = "Business Intelligence & Executive Visualization"
            signals.append("Employer wants intuitive visual storytelling with interactive dashboards for executive leadership.")
            focus = "Interactive Dashboard Design & Star Schema Modeling"

        if not signals:
            signals.append("Looking for an adaptable analytics practitioner with strong SQL, Excel, and dashboard competencies.")

        return {
            "domain": domain,
            "hiring_signals": signals,
            "primary_focus": focus
        }

    def _check_candidate_evidence(
        self,
        kw: str,
        candidate_skills: Set[str],
        candidate_text: str,
        evidence_map: Dict[str, str]
    ) -> Tuple[bool, str]:
        kw_clean = kw.strip()
        kw_lower = kw_clean.lower()

        # 1. Exact match in candidate skills/tools
        if kw_lower in candidate_skills:
            return True, evidence_map.get(kw_lower, "Master Resume / Career Knowledge Base")

        # 2. Canonical aliases & common variations
        if kw_lower == "advanced excel" and ("excel" in candidate_skills or "pivot tables" in candidate_skills):
            return True, "Master Resume (Excel & Analytical Functions)"
        if kw_lower == "pl-300 certification" and "pl-300" in candidate_skills:
            return True, "Microsoft Certified: PL-300"
        if kw_lower == "dp-600 certification" and "dp-600" in candidate_skills:
            return True, "Microsoft Certified: DP-600"
        if kw_lower in ["power bi", "power bi developer"] and ("pl-300" in candidate_skills or "power bi" in candidate_skills):
            return True, "Master Resume (Power BI / PL-300)"
        if kw_lower in ["sql", "sql server"] and any(s in candidate_skills for s in ["sql", "mysql", "postgresql", "t-sql", "pl/sql", "sql server"]):
            return True, "Master Resume (SQL & Relational Databases)"
        if kw_lower in ["attention to detail", "meticulous attention to detail"] and any(s in candidate_skills for s in ["data validation", "data quality", "data cleaning", "validation", "quality assurance"]):
            return True, "Master Resume (Data Validation & Quality Assurance)"
        if kw_lower in ["powerpoint", "ms powerpoint"] and any(s in candidate_skills for s in ["powerpoint", "microsoft office", "excel", "power bi", "dashboard design"]):
            return True, "Master Resume (Data Visualization & Reporting Tools)"

        # 3. Substring match for multi-word phrases (len >= 3)
        if len(kw_lower) >= 3 and " " in kw_lower:
            for cs in candidate_skills:
                if len(cs) >= 3 and (kw_lower in cs or cs in kw_lower):
                    return True, evidence_map.get(cs, "Master Resume / Career Knowledge Base")

        # 4. Word boundary match in candidate full text
        if len(kw_lower) >= 2 and re.search(r"\b" + re.escape(kw_lower) + r"\b", candidate_text):
            return True, "Documented in Career Knowledge Base"

        return False, ""

    def _perform_grounded_gap_analysis(
        self,
        keywords: List[str],
        keyword_weights: Dict[str, int],
        keyword_categories: Dict[str, str],
        required_soft: List[str],
        profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compares JD keywords against candidate verified knowledge base records.
        score = weighted matched / weighted total * 100, no floor or bonus.
        missing_keywords and skill_gap_analysis.missing_skills must come from the same list.
        """
        profile = profile or {}
        candidate_skills: Set[str] = set()
        evidence_map: Dict[str, str] = {}

        # 1. Technical tools
        for tool in profile.get("technical_tools", []):
            t_clean = str(tool).strip().lower()
            if t_clean:
                candidate_skills.add(t_clean)
                evidence_map[t_clean] = "Technical Tools"

        # 2. Structured skills dictionary / list
        skills_data = profile.get("skills", {})
        if isinstance(skills_data, dict):
            for cat_name, cat_skills in skills_data.items():
                if isinstance(cat_skills, list):
                    for sk in cat_skills:
                        clean_sk = str(sk).strip().lower()
                        if clean_sk:
                            candidate_skills.add(clean_sk)
                            evidence_map[clean_sk] = f"Skills ({cat_name})"
                            sub_items = re.findall(r'\((.*?)\)', clean_sk)
                            for sub in sub_items:
                                for part in re.split(r'[,/|;]', sub):
                                    p = part.strip()
                                    if p and len(p) > 1 and not p.startswith("currently learning"):
                                        candidate_skills.add(p)
                                        evidence_map[p] = f"Skills ({cat_name})"
                            base_sk = re.sub(r'\(.*?\)', '', clean_sk).strip()
                            if base_sk:
                                candidate_skills.add(base_sk)
                                evidence_map[base_sk] = f"Skills ({cat_name})"
                elif isinstance(cat_skills, str):
                    for s in cat_skills.split(","):
                        sc = s.strip().lower()
                        if sc:
                            candidate_skills.add(sc)
                            evidence_map[sc] = f"Skills ({cat_name})"
        elif isinstance(skills_data, list):
            for sk in skills_data:
                clean_sk = str(sk).strip().lower()
                if clean_sk:
                    candidate_skills.add(clean_sk)
                    evidence_map[clean_sk] = "Skills"

        # 3. Skills lines
        for line in profile.get("skills_lines", []):
            if isinstance(line, dict):
                val = line.get("skills") or line.get("items") or ""
            else:
                val = str(line)
            for part in str(val).split(","):
                p = part.strip().lower()
                if p:
                    candidate_skills.add(p)
                    evidence_map[p] = "Master Resume Skills"

        # 4. Experience
        for exp in profile.get("experience", []):
            if not isinstance(exp, dict):
                continue
            exp_company = exp.get("company", "Experience")
            for s in exp.get("skills", []):
                sc = str(s).strip().lower()
                if sc:
                    candidate_skills.add(sc)
                    evidence_map[sc] = f"Experience at {exp_company}"
            for b in exp.get("bullets", []):
                b_lower = str(b).lower()
                for kw_item in TECHNICAL_TAXONOMY:
                    if re.search(r"\b" + re.escape(kw_item) + r"\b", b_lower):
                        candidate_skills.add(kw_item)
                        if kw_item not in evidence_map:
                            evidence_map[kw_item] = f"Experience Bullets ({exp_company})"

        # 5. Projects
        for proj in profile.get("projects", []):
            if not isinstance(proj, dict):
                continue
            p_title = proj.get("title") or proj.get("name") or "Project"
            for s in proj.get("skills", []):
                sc = str(s).strip().lower()
                if sc:
                    candidate_skills.add(sc)
                    evidence_map[sc] = f"Project: {p_title}"
            if proj.get("tools"):
                for t in str(proj["tools"]).split(","):
                    tc = t.strip().lower()
                    if tc:
                        candidate_skills.add(tc)
                        evidence_map[tc] = f"Project: {p_title}"

        # 6. Certifications
        for cert in profile.get("certifications", []):
            c_name = (cert.get("name") if isinstance(cert, dict) else str(cert)).strip().lower()
            if c_name:
                candidate_skills.add(c_name)
                evidence_map[c_name] = "Certification"
                if "pl-300" in c_name:
                    candidate_skills.add("pl-300")
                    candidate_skills.add("power bi")
                if "dp-600" in c_name:
                    candidate_skills.add("dp-600")
                    candidate_skills.add("fabric")

        # 7. Candidate full text
        candidate_text_parts = [profile.get("summary", "")]
        for exp in profile.get("experience", []):
            if isinstance(exp, dict):
                candidate_text_parts.extend(exp.get("bullets", []))
        for proj in profile.get("projects", []):
            if isinstance(proj, dict):
                candidate_text_parts.extend(proj.get("bullets", []))
                candidate_text_parts.append(proj.get("description", ""))
        for sl in profile.get("skills_lines", []):
            candidate_text_parts.append(str(sl))
        candidate_full_text = " ".join([str(p).lower() for p in candidate_text_parts if p])

        matched_skills: List[str] = []
        missing_skills: List[str] = []

        for kw in keywords:
            is_matched, ev = self._check_candidate_evidence(kw, candidate_skills, candidate_full_text, evidence_map)
            if is_matched:
                matched_skills.append(kw)
            else:
                missing_skills.append(kw)

        # Calculate exact weighted ATS score (no floor, no bonus)
        weighted_matched = sum(keyword_weights.get(k, 1) for k in matched_skills)
        weighted_total = sum(keyword_weights.get(k, 1) for k in keywords)

        if weighted_total == 0:
            match_score = 0
        else:
            raw_score = (weighted_matched / weighted_total) * 100.0
            match_score = round(raw_score, 1)
            if match_score.is_integer():
                match_score = int(match_score)

        soft_skill_alignment = []
        for soft in required_soft:
            soft_skill_alignment.append({
                "soft_skill": soft,
                "status": "Documented Evidence Available",
                "action": "Highlighted in Experience & Projects using strong action verbs."
            })

        gap_suggestions = [
            f"Candidate lacks documented experience in {m}; discuss during interview if transferable."
            for m in missing_skills[:3]
        ]

        return {
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "matched_count": len(matched_skills),
            "missing_count": len(missing_skills),
            "total_count": len(keywords),
            "match_score": match_score,
            "ats_score": match_score,
            "critical_matches": matched_skills[:5],
            "gap_suggestions": gap_suggestions,
            "soft_skill_alignment": soft_skill_alignment
        }

    def _calculate_ats_score(self, gap_analysis: Dict[str, Any], domain_signals: Dict[str, Any]) -> int:
        return gap_analysis.get("match_score", 0)

    def _generate_strategic_recommendations(
        self,
        gap_analysis: Dict[str, Any],
        domain_signals: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> List[str]:
        recs = []
        matched = [m["name"] if isinstance(m, dict) else str(m) for m in gap_analysis.get("matched_skills", [])]
        missing = [m["name"] if isinstance(m, dict) else str(m) for m in gap_analysis.get("missing_skills", [])]

        if matched:
            recs.append(f"Strategic Skill Hierarchy: Featured high-match tools ({', '.join(matched[:3])}) prominently in the Summary and Technical Skills.")
        recs.append(f"Project Alignment: Prioritized hands-on projects demonstrating {domain_signals.get('primary_focus', 'Core Competencies')}.")
        recs.append("Strict Truthfulness Enforced: No non-existent credentials or false experience added.")
        if missing:
            recs.append(f"Identified {len(missing)} Technical Skill Gaps ({', '.join(missing[:3])}) — omitted from resume to prevent ATS disqualification; framed transferable SQL/Python proficiency instead.")
        return recs

deep_job_analyzer = DeepJobAnalysisEngine()
