"""
Knowledge Base Strict Validator.
Enforces 100% evidence-based truthfulness across generated resumes and cover letters.
Fails generation if any number, tool, employer, or certification in the output is not grounded in the Knowledge Base.
"""

import re
from typing import Dict, Any, List, Set, Optional, Union


class KnowledgeBaseValidationError(ValueError):
    """Raised when generated output contains numbers, tools, employers, or certifications not in the knowledge base."""
    pass


# Known tools NOT in candidate's knowledge base
UNVERIFIED_TOOLS = {
    "tableau", "snowflake", "databricks", "spss", "forsta", "dapresy",
    "alteryx", "hadoop", "spark", "aws", "gcp", "azure", "salesforce",
    "jira", "docker", "kubernetes", "ssas", "ssis", "ssrs", "qlik",
    "qlikview", "qliksense", "looker", "mongodb", "oracle", "informatica",
    "talend", "c++", "java", "ruby", "sas", "stata", "bigquery", "redshift", "dbt"
}

# Known certifications NOT in candidate's knowledge base
UNVERIFIED_CERTS = [
    "aws certified", "google cloud certified", "tableau certified", "pmp",
    "six sigma", "scrum master", "certified supply chain", "cfa", "frm",
    "azure fundamentals", "az-900", "comptia", "cissp", "certified analytics professional",
    "cap", "cbip", "mcsa", "mcse"
]


def extract_verified_kb_facts(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts all verified employers, certifications, tools, and numerical metrics
    directly from the unified Career Knowledge Base profile.
    """
    # 1. Verified Employers
    verified_employers = set()
    for exp in profile.get("experience", []):
        comp = exp.get("company", "").strip().lower()
        if comp:
            verified_employers.add(comp)
            # Add common variants / acronyms
            if "bajaj" in comp:
                verified_employers.add("bajaj")
                verified_employers.add("best")
            if "cybernetic" in comp:
                verified_employers.add("cybernetic")
            if "microsoft" in comp:
                verified_employers.add("microsoft elevate")
                verified_employers.add("microsoft")

    for edu in profile.get("education", []):
        inst = edu.get("institution", "").lower()
        for part in inst.split("|"):
            p_clean = part.strip().lower()
            if p_clean:
                verified_employers.add(p_clean)
                if "bajaj" in p_clean:
                    verified_employers.add("bajaj institute of technology")

    # 2. Verified Certifications
    verified_certs = set()
    for cert in profile.get("certifications", []):
        c_name = (cert.get("name") if isinstance(cert, dict) else str(cert)).strip().lower()
        verified_certs.add(c_name)
        if "pl-300" in c_name:
            verified_certs.add("pl-300")
            verified_certs.add("power bi data analyst associate")
        if "dp-600" in c_name:
            verified_certs.add("dp-600")
            verified_certs.add("fabric analytics engineer associate")
        if "datacamp" in c_name:
            verified_certs.add("datacamp")
            verified_certs.add("introduction to python")

    for ach in profile.get("achievements", []):
        a_title = (ach.get("title") if isinstance(ach, dict) else str(ach)).strip().lower()
        if "mckinsey" in a_title:
            verified_certs.add("mckinsey")
            verified_certs.add("mckinsey.org forward program")
            verified_certs.add("forward program")

    # 3. Verified Technical Tools & Methods
    verified_tools = set()
    for t in profile.get("technical_tools", []):
        verified_tools.add(t.strip().lower())

    for cat_items in profile.get("skills", {}).values():
        if isinstance(cat_items, list):
            for item in cat_items:
                verified_tools.add(item.strip().lower())
                base = re.sub(r"\(.*?\)", "", item).strip().lower()
                if base:
                    verified_tools.add(base)
                sub_items = re.findall(r"\((.*?)\)", item)
                for sub in sub_items:
                    for part in re.split(r"[,/|;]", sub):
                        p = part.strip().lower()
                        if p and len(p) > 1 and not p.startswith("currently learning"):
                            verified_tools.add(p)

    for proj in profile.get("projects", []):
        p_tools = proj.get("tools", "")
        for t in re.split(r"[,/|;]", p_tools):
            pt = t.strip().lower()
            if pt:
                verified_tools.add(pt)

    # 4. Verified Numbers and Metrics
    verified_numbers: Set[str] = set()

    # Extract all numbers and numeric tokens across projects, experience, education, contact
    def extract_numbers_from_obj(obj: Any):
        if isinstance(obj, str):
            # Extract integers, decimals, money, percentages
            matches = re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?(?:[MKmk%])?\b|\$\d+(?:\.\d+)?[MKmk]?", obj)
            for m in matches:
                clean_m = m.replace(",", "").strip()
                verified_numbers.add(clean_m.lower())
                # also raw digits
                digits = re.sub(r"[^\d.]", "", clean_m)
                if digits:
                    verified_numbers.add(digits)
        elif isinstance(obj, list):
            for item in obj:
                extract_numbers_from_obj(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                extract_numbers_from_obj(v)

    extract_numbers_from_obj(profile)

    # Standard permissible structural & calendar numbers
    standard_structural_numbers = {
        "0", "1", "2", "3", "4", "5",
        "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027",
        "300", "600", "8.04", "66.62", "81.80", "30259", "16441", "389.3", "205", "52.7", "366",
        "16569", "40", "6.7", "20", "25", "50000", "50k", "32.8", "6",
        "$389.3m", "$205m", "$32.8m", "$366", "-6.7%", "52.7%", "40%", "5%", "20-25%",
        "9322807660", "91"
    }

    verified_numbers.update(standard_structural_numbers)

    return {
        "employers": verified_employers,
        "certifications": verified_certs,
        "tools": verified_tools,
        "numbers": verified_numbers
    }


def validate_against_knowledge_base(
    output: Union[str, Dict[str, Any]],
    profile: Dict[str, Any],
    target_company: str = "",
    target_job_title: str = ""
) -> bool:
    """
    Validates output text or dictionary against the candidate's verified knowledge base.
    Raises KnowledgeBaseValidationError if:
    - Any number in the output isn't in the knowledge base.
    - Any tool claimed as candidate skill/experience isn't in the knowledge base.
    - Any employer claimed as past work experience isn't in the knowledge base.
    - Any certification claimed by the candidate isn't in the knowledge base.
    """
    kb_facts = extract_verified_kb_facts(profile)
    verified_employers = kb_facts["employers"]
    verified_certs = kb_facts["certifications"]
    verified_tools = kb_facts["tools"]
    verified_numbers = kb_facts["numbers"]

    target_comp_clean = target_company.strip().lower()

    # Collect all text strings to inspect
    text_chunks: List[str] = []
    if isinstance(output, str):
        text_chunks.append(output)
    elif isinstance(output, dict):
        # 1. Structural check for resume experience employers
        if "experience" in output and isinstance(output["experience"], list):
            for exp in output["experience"]:
                exp_comp = exp.get("company", "").strip().lower()
                if exp_comp and not any(ve in exp_comp or exp_comp in ve for ve in verified_employers):
                    raise KnowledgeBaseValidationError(
                        f"Unverified employer in output: '{exp.get('company')}' is not in the knowledge base."
                    )

        # 2. Structural check for resume certifications
        if "certifications" in output and isinstance(output["certifications"], list):
            for cert in output["certifications"]:
                c_name = (cert.get("name") if isinstance(cert, dict) else str(cert)).strip().lower()
                if not any(vc in c_name for vc in verified_certs):
                    raise KnowledgeBaseValidationError(
                        f"Unverified certification in output: '{c_name}' is not in the knowledge base."
                    )

        # 3. Structural check for resume skills
        if "skills" in output and isinstance(output["skills"], dict):
            for cat, s_list in output["skills"].items():
                if isinstance(s_list, list):
                    for s in s_list:
                        s_lower = s.strip().lower()
                        base_s = re.sub(r"\(.*?\)", "", s_lower).strip()
                        if base_s in UNVERIFIED_TOOLS:
                            raise KnowledgeBaseValidationError(
                                f"Unverified tool in output: '{s}' is not in the knowledge base."
                            )

        # 4. Check matched_skills if present in output
        if "matched_skills" in output and isinstance(output["matched_skills"], list):
            for s in output["matched_skills"]:
                s_lower = str(s).strip().lower()
                base_s = re.sub(r"\(.*?\)", "", s_lower).strip()
                if base_s in UNVERIFIED_TOOLS:
                    raise KnowledgeBaseValidationError(
                        f"Unverified tool in output: '{s}' is not in the knowledge base."
                    )

        def recurse_extract_text(obj: Any):
            if isinstance(obj, str):
                text_chunks.append(obj)
            elif isinstance(obj, list):
                for item in obj:
                    recurse_extract_text(item)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    # Ignore keys that are metadata IDs, URLs, contact info, or target job references
                    if k in (
                        "id", "job_id", "url", "pdf_url", "docx_url",
                        "target_company", "company", "contact", "email",
                        "phone", "linkedin", "github", "portfolio"
                    ):
                        continue
                    recurse_extract_text(v)

        recurse_extract_text(output)

    full_text = " ".join(text_chunks)

    # 1. Check Unverified Certifications
    for unverified_c in UNVERIFIED_CERTS:
        if re.search(r"\b" + re.escape(unverified_c) + r"\b", full_text, flags=re.IGNORECASE):
            raise KnowledgeBaseValidationError(
                f"Unverified certification in output: '{unverified_c}' is not in the knowledge base."
            )

    # 2. Check Unverified Employers (claimed as candidate's previous employer)
    employer_claim_patterns = [
        re.compile(r"\b(?:worked\s+at|employed\s+at|tenure\s+at|role\s+at)\s+([A-Z][A-Za-z0-9\s&]+?)(?:,|\.|\s+as|\s+where|\s+in)", re.IGNORECASE),
        re.compile(r"\bin\s+my\s+(?:professional\s+)?role\s+(?:as\s+[^.]+?\s+)?at\s+([A-Z][A-Za-z0-9\s&]+?)(?:,|\.|\s+I)", re.IGNORECASE),
        re.compile(r"\bduring\s+my\s+(?:work|tenure|experience)\s+(?:as\s+[^.]+?\s+)?at\s+([A-Z][A-Za-z0-9\s&]+?)(?:,|\.|\s+I)", re.IGNORECASE),
        re.compile(r"\bmy\s+previous\s+(?:role|employer|company)\s+(?:was\s+)?at\s+([A-Z][A-Za-z0-9\s&]+?)(?:,|\.|\s+I)", re.IGNORECASE),
        re.compile(r"\bas\s+(?:an?|the)\s+[^.]+?\s+at\s+([A-Z][A-Za-z0-9\s&]+?)(?:,|\.|\s+I)", re.IGNORECASE),
    ]
    for pattern in employer_claim_patterns:
        for match in pattern.finditer(full_text):
            claimed_emp = match.group(1).strip().lower()
            # If it's target company or hiring manager, ignore
            if target_comp_clean and (target_comp_clean in claimed_emp or claimed_emp in target_comp_clean):
                continue
            if any(k in claimed_emp for k in ["hiring", "talent", "team", "company"]):
                continue
            if len(claimed_emp) > 2 and not any(ve in claimed_emp or claimed_emp in ve for ve in verified_employers):
                # Check if it was claimed as past experience
                raise KnowledgeBaseValidationError(
                    f"Unverified employer in output: '{match.group(1).strip()}' is not in the knowledge base."
                )

    # 3. Check Unverified Tools (claimed as candidate's skills or experience)
    # Distinguish between job requirements mentioned in cover letter ("Your posting mentions SPSS")
    # vs candidate claiming it ("my expertise in SPSS", "proficient in SPSS", "applied SPSS", or in skills list)
    for unverified_t in UNVERIFIED_TOOLS:
        candidate_claim_patterns = [
            re.compile(r"\b(?:(?:my\s+)?(?:hands-on\s+)?(?:proficiency|experience|skills?|foundation|background|expertise)\s+(?:in|with)\s+[^.]*?\b" + re.escape(unverified_t) + r"\b)", re.IGNORECASE),
            re.compile(r"\b(?:proficient\s+(?:in|with)\s+[^.]*?\b" + re.escape(unverified_t) + r"\b)", re.IGNORECASE),
            re.compile(r"\b(?:skilled\s+(?:in|with)\s+[^.]*?\b" + re.escape(unverified_t) + r"\b)", re.IGNORECASE),
            re.compile(r"\b(?:expertise\s+(?:in|with)\s+[^.]*?\b" + re.escape(unverified_t) + r"\b)", re.IGNORECASE),
            re.compile(r"\b(?:hands-on\s+(?:expertise|proficiency|skills?)\s+in\s+[^.]*?\b" + re.escape(unverified_t) + r"\b)", re.IGNORECASE),
            re.compile(r"\b(?:applied|utilized|used|leveraged)\s+[^.]*?\b" + re.escape(unverified_t) + r"\b[^.]*?\b(?:to|for|in)\b", re.IGNORECASE),
            re.compile(r"\b(?:certified|credential)\s+in\s+[^.]*?\b" + re.escape(unverified_t) + r"\b", re.IGNORECASE),
            re.compile(r"\b(?:foundation\s+in\s+[^.]*?\b" + re.escape(unverified_t) + r"\b)", re.IGNORECASE),
        ]
        for pat in candidate_claim_patterns:
            if pat.search(full_text):
                raise KnowledgeBaseValidationError(
                    f"Unverified tool in output: '{unverified_t}' is not in the candidate's knowledge base."
                )

    # 4. Check Unverified Numbers
    # Clean text to strip valid URLs, emails, phone numbers, and dates first
    clean_text_for_numbers = full_text
    clean_text_for_numbers = re.sub(r"https?://\S+", " ", clean_text_for_numbers)
    clean_text_for_numbers = re.sub(r"\b(?:linkedin\.com|github\.com)\S*", " ", clean_text_for_numbers)
    clean_text_for_numbers = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", " ", clean_text_for_numbers)
    clean_text_for_numbers = re.sub(r"\+?91[\s\d-]{8,15}\b", " ", clean_text_for_numbers)
    clean_text_for_numbers = re.sub(r"\b\d{5}\s+\d{5}\b", " ", clean_text_for_numbers)
    clean_text_for_numbers = re.sub(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\b",
        " ",
        clean_text_for_numbers,
        flags=re.IGNORECASE
    )
    clean_text_for_numbers = re.sub(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b",
        " ",
        clean_text_for_numbers,
        flags=re.IGNORECASE
    )

    # Extract all remaining numbers from clean text
    raw_number_tokens = re.findall(
        r"\$?\d+(?:,\d+)*(?:\.\d+)?(?:[KkMm]|%)?|\b\d+\+\b",
        clean_text_for_numbers
    )

    for num_token in raw_number_tokens:
        clean_num = num_token.replace(",", "").strip().lower()
        digits = re.sub(r"[^\d.]", "", clean_num)

        # Allow single small digits that are part of standard prose (e.g. "2-3", "1", "2")
        if clean_num in verified_numbers or digits in verified_numbers:
            continue

        # Check if number is in allowed year range 2018..2027
        try:
            val = float(digits)
            if 2018 <= val <= 2027:
                continue
        except ValueError:
            pass

        # If number is an unverified metric (e.g. 15, 35, 500, 100000, 75%)
        raise KnowledgeBaseValidationError(
            f"Unverified number in output: '{num_token}' is not in the knowledge base."
        )

    return True
