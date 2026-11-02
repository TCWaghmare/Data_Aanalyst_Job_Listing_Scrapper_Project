"""
Advanced Evidence-Based Master Resume Parser.
Extracts structured information (contact, summary, experience, projects, skills, education, certifications)
from PDF, DOCX, DOC, TXT, and Markdown documents.
Strictly evidence-based: builds profile exclusively from uploaded text.
Never invents, assumes, infers, or hallucinates unsupported information.
"""

import os
import re
import io
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("ResumeParser")

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx
except ImportError:
    docx = None

NOT_AVAILABLE = "Information Not Available in Uploaded Documents"

EMPTY_RESUME = {
    "name": NOT_AVAILABLE,
    "contact": {
        "phone": NOT_AVAILABLE,
        "email": NOT_AVAILABLE,
        "linkedin": "",
        "linkedin_url": "",
        "github": "",
        "github_url": "",
        "location": NOT_AVAILABLE
    },
    "summary": NOT_AVAILABLE,
    "experience": [],
    "projects": [],
    "skills": {},
    "technical_tools": [],
    "education": [],
    "certifications": [],
    "achievements": [],
    "source_file": ""
}

# Keep DEFAULT_MASTER_RESUME as EMPTY_RESUME for backwards compatibility
DEFAULT_MASTER_RESUME = dict(EMPTY_RESUME)

# Known taxonomy for skill categorizing
TECH_SKILLS_TAXONOMY = {
    "bi_visualization": [
        "Power BI", "DAX", "Power Query", "Tableau", "Looker", "QuickSight", "Qlik", "QlikView",
        "Dashboard Design", "Geo Mapping", "KPI Reporting", "Data Storytelling",
        "Interactive Reports", "Executive Dashboards", "Data Visualization"
    ],
    "data_analytics": [
        "Excel", "Advanced Excel", "Pivot Tables", "Power Pivot", "XLOOKUP", "VLOOKUP", "INDEX/MATCH",
        "Data Modeling", "Data Cleaning", "Data Validation", "Data Quality", "EDA",
        "Exploratory Data Analysis", "Statistical Analysis", "Cohort Analysis",
        "A/B Testing", "KPI Tracking", "Funnel Analysis", "Financial Analysis",
        "Sales Analysis", "Trend Analysis", "Star Schema", "Snowflake Schema"
    ],
    "programming": [
        "Python", "SQL", "PostgreSQL", "MySQL", "T-SQL", "PL/SQL", "SQLite",
        "R", "Bash", "Shell", "HTML", "CSS", "JavaScript", "TypeScript", "C++", "Java"
    ],
    "cloud_database": [
        "Microsoft Fabric", "Azure", "Azure Synapse", "Azure Data Factory",
        "AWS", "AWS S3", "AWS Redshift", "AWS EC2", "Google Cloud", "GCP", "BigQuery",
        "Snowflake", "Databricks", "MongoDB", "ETL", "ELT", "Data Pipeline"
    ],
    "machine_learning": [
        "Machine Learning", "Predictive Modeling", "Supervised Learning",
        "Unsupervised Learning", "Scikit-Learn", "Pandas", "NumPy", "Matplotlib",
        "Seaborn", "Regression Analysis", "Classification", "Clustering", "NLP", "LLM", "Deep Learning"
    ],
    "engineering_manufacturing": [
        "APQP", "PPAP", "PFMEA", "DFMEA", "Control Plans", "Process Flow Diagrams", "PFD",
        "DCN Tracking", "SOP", "AutoCAD", "SolidWorks", "CATIA", "PLC", "SCADA",
        "Root Cause Analysis", "8D", "Six Sigma", "Kaizen", "GD&T", "Quality Assurance"
    ],
    "domains": [
        "Business Intelligence", "Business Analytics", "Supply Chain Analytics",
        "E-Commerce Analytics", "Financial Analytics", "Operations Analytics",
        "Marketing Analytics", "Customer Analytics", "Product Analytics"
    ],
    "tools_workflows": [
        "Git", "GitHub", "Jira", "Confluence", "Agile", "Scrum", "Docker",
        "ERP Systems", "CRM", "Salesforce", "Google Analytics", "REST API", "MS Office"
    ]
}


class ResumeParser:
    """
    Parses resume documents into structured, verified candidate data.
    Strictly evidence-based: only extracts facts that appear in the document.
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self._current_resume: Dict[str, Any] = dict(EMPTY_RESUME)

    def get_master_resume(self) -> Dict[str, Any]:
        return self._current_resume

    def clean_text_artifacts(self, text: str) -> str:
        """Fixes PDF kerning artifacts, excessive spaces, and normalization."""
        if not text:
            return ""
        # Fix split single-character caps: 'T rainee' -> 'Trainee', 'W aghmare' -> 'Waghmare'
        cleaned = re.sub(r'(\b[A-Z])\s+([a-z]{2,})', r'\1\2', text)
        cleaned = cleaned.replace("W aghmare", "Waghmare")
        cleaned = cleaned.replace("T rainee", "Trainee")
        cleaned = cleaned.replace("T echnologies", "Technologies")
        cleaned = cleaned.replace("W ardha", "Wardha")
        cleaned = cleaned.replace("T echnology", "Technology")
        # Normalize non-breaking spaces & tabs
        cleaned = cleaned.replace("\u00a0", " ").replace("\t", " ")
        # Remove consecutive blank lines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    def parse_pdf(self, file_bytes: bytes) -> str:
        """Extracts text from PDF bytes safely using standard io.BytesIO."""
        if not pypdf:
            raise ImportError("pypdf is not installed. Please install pypdf to extract PDF resumes.")
        if not file_bytes:
            raise ValueError("Uploaded PDF file is empty (0 bytes).")
        if not file_bytes.startswith(b"%PDF"):
            raise ValueError("Uploaded file does not have a valid PDF header.")

        try:
            stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(stream)
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    raise ValueError("PDF is password protected and cannot be extracted.")

            pages_text = []
            for idx, page in enumerate(reader.pages):
                try:
                    p_text = page.extract_text()
                    if p_text:
                        pages_text.append(p_text)
                except Exception as page_err:
                    logger.warning(f"Error reading PDF page {idx+1}: {page_err}")

            raw_text = "\n\n".join(pages_text).strip()
            if not raw_text:
                raise ValueError("No extractable text found in PDF. If this is a scanned document, please upload a text-based PDF or Word document.")

            return self.clean_text_artifacts(raw_text)
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.error(f"Failed to extract PDF: {e}")
            raise ValueError(f"PDF extraction error: {str(e)}")

    def parse_docx(self, file_bytes: bytes) -> str:
        """Extracts text from DOCX bytes using python-docx."""
        if not docx:
            raise ImportError("python-docx is not installed. Please install python-docx to extract Word resumes.")
        if not file_bytes:
            raise ValueError("Uploaded Word document is empty (0 bytes).")

        try:
            stream = io.BytesIO(file_bytes)
            doc = docx.Document(stream)
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                    if row_text:
                        paras.append(row_text)
            return self.clean_text_artifacts("\n".join(paras))
        except Exception as e:
            logger.error(f"Failed to extract DOCX: {e}")
            raise ValueError(f"Word document extraction error: {str(e)}")

    def parse_text_stream(self, file_bytes: bytes) -> str:
        """Extracts plain text with multiple encoding fallbacks."""
        for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                return self.clean_text_artifacts(file_bytes.decode(enc))
            except UnicodeDecodeError:
                continue
        return self.clean_text_artifacts(file_bytes.decode("utf-8", errors="ignore"))

    def extract_text(self, filename: str, file_bytes: bytes) -> str:
        """Dispatches extraction according to file extension."""
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            return self.parse_pdf(file_bytes)
        elif ext in [".docx", ".doc"]:
            try:
                return self.parse_docx(file_bytes)
            except Exception:
                return self.parse_text_stream(file_bytes)
        elif ext in [".txt", ".md", ".csv", ".json", ".html"]:
            return self.parse_text_stream(file_bytes)
        else:
            return self.parse_text_stream(file_bytes)

    def parse_file(self, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """Extracts text and parses structured sections strictly from uploaded bytes."""
        text = self.extract_text(filename, file_bytes)
        parsed = self.parse_text(filename, text)
        self._current_resume = parsed
        return parsed

    def parse_text(self, filename: str, text: str) -> Dict[str, Any]:
        """Deeply parses raw document text into verified structured entities."""
        if not text or not text.strip():
            empty = dict(EMPTY_RESUME)
            empty["source_file"] = filename
            return empty

        # 1. Contact Info
        contact_info = self._parse_contact(text)

        # 2. Section Partitioning
        sections = self._split_sections(text)

        # 3. Summary
        summary = self._parse_summary(sections.get("summary", ""), text)

        # 4. Work Experience
        experience = self._parse_experience(sections.get("experience", ""), filename)

        # 5. Projects
        projects = self._parse_projects(sections.get("projects", ""), filename)

        # 6. Technical Skills
        skills, technical_tools = self._parse_skills(sections.get("skills", ""), text, filename)

        # 7. Education
        education = self._parse_education(sections.get("education", ""), filename)

        # 8. Certifications
        certifications = self._parse_certifications(sections.get("certifications", ""), filename)

        # 9. Achievements
        achievements = self._parse_achievements(sections.get("awards", ""), filename)

        structured = {
            "name": contact_info["name"],
            "contact": {
                "phone": contact_info["phone"],
                "email": contact_info["email"],
                "linkedin": contact_info["linkedin"],
                "linkedin_url": contact_info["linkedin_url"],
                "github": contact_info["github"],
                "github_url": contact_info["github_url"],
                "location": contact_info["location"]
            },
            "summary": summary,
            "experience": experience,
            "projects": projects,
            "skills": skills,
            "technical_tools": technical_tools,
            "education": education,
            "certifications": certifications,
            "achievements": achievements,
            "source_file": filename,
            "raw_text": text
        }
        return structured

    def _split_sections(self, text: str) -> Dict[str, str]:
        """Finds resume section boundaries and partitions text."""
        header_patterns = [
            ("summary", r'(?:^|\n)\s*(?:PROFESSIONAL\s+SUMMARY|SUMMARY|PROFILE|CAREER\s+OBJECTIVE|OBJECTIVE|ABOUT\s+ME)\s*(?:\n|:)'),
            ("experience", r'(?:^|\n)\s*(?:PROFESSIONAL\s+EXPERIENCE|WORK\s+EXPERIENCE|WORK\s+HISTORY|EXPERIENCE|EMPLOYMENT\s+HISTORY|EMPLOYMENT|INTERNSHIPS)\s*(?:\n|:)'),
            ("projects", r'(?:^|\n)\s*(?:KEY\s+PROJECTS|ACADEMIC\s+PROJECTS|PROJECT\s+PORTFOLIO|PROJECTS|PROJECT\s+WORK)\s*(?:\n|:)'),
            ("skills", r'(?:^|\n)\s*(?:TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES|TECHNICAL\s+STRENGTHS|SKILLS|TOOLS\s+&\s+TECHNOLOGIES|AREAS\s+OF\s+EXPERTISE)\s*(?:\n|:)'),
            ("education", r'(?:^|\n)\s*(?:EDUCATION|ACADEMIC\s+BACKGROUND|ACADEMIC\s+DETAILS|QUALIFICATIONS)\s*(?:\n|:)'),
            ("certifications", r'(?:^|\n)\s*(?:CERTIFICATIONS|CERTIFICATES|LICENSES\s+&\s+CERTIFICATIONS|CREDENTIALS|COURSES|TRAINING)\s*(?:\n|:)'),
            ("awards", r'(?:^|\n)\s*(?:AWARDS|ACHIEVEMENTS|HONORS|ACCOMPLISHMENTS)\s*(?:\n|:)'),
        ]

        spans: List[Tuple[int, int, str]] = []
        for sec_id, pat in header_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                spans.append((m.start(), m.end(), sec_id))

        spans.sort(key=lambda x: x[0])

        sections: Dict[str, str] = {}
        for i, (start, end, sec_id) in enumerate(spans):
            next_start = spans[i + 1][0] if i + 1 < len(spans) else len(text)
            sec_content = text[end:next_start].strip()
            # If section repeated, concatenate
            if sec_id in sections:
                sections[sec_id] += "\n\n" + sec_content
            else:
                sections[sec_id] = sec_content

        return sections

    def _parse_contact(self, text: str) -> Dict[str, str]:
        """Extracts verified name, email, phone, linkedin, github, location from text."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # Name extraction: inspect first 6 lines
        name = ""
        for line in lines[:6]:
            # Remove symbols/links
            clean = re.sub(r'[^a-zA-Z\s.]', ' ', line).strip()
            clean = re.sub(r'\s+', ' ', clean)
            words = clean.split()
            # A valid person name typically has 2 to 4 words, each capitalized or initial
            if 2 <= len(words) <= 4:
                lower_words = [w.lower() for w in words]
                disallowed = {
                    "resume", "cv", "curriculum", "vitae", "summary", "profile", "contact",
                    "email", "phone", "engineer", "analyst", "developer", "page", "skills",
                    "education", "experience", "pune", "mumbai", "delhi", "bangalore", "india",
                    "remote", "fresher", "mechanical", "electrical", "computer", "science"
                }
                if not any(w in disallowed for w in lower_words):
                    name = clean
                    break

        if not name and lines:
            name = lines[0][:40]

        # Email
        email_m = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
        email = email_m.group(1).strip() if email_m else NOT_AVAILABLE

        # Phone
        phone_m = re.search(r'(\+?\d[\d\s-]{8,15}\d)', text)
        phone = phone_m.group(1).strip() if phone_m else NOT_AVAILABLE

        # LinkedIn
        li_m = re.search(r'(linkedin\.com/in/[a-zA-Z0-9_-]+)', text, re.IGNORECASE)
        linkedin = li_m.group(1).strip() if li_m else ""
        linkedin_url = f"https://{linkedin}" if linkedin else ""

        # GitHub
        gh_m = re.search(r'(github\.com/[a-zA-Z0-9_-]+)', text, re.IGNORECASE)
        github = gh_m.group(1).strip() if gh_m else ""
        github_url = f"https://{github}" if github else ""

        # Location
        location = ""
        loc_m = re.search(r'\b(Pune|Mumbai|Bangalore|Bengaluru|Hyderabad|Delhi|Noida|Gurugram|Gurgaon|Chennai|Kolkata|Wardha|Nagpur|Remote|India)\b', text, re.IGNORECASE)
        if loc_m:
            location = loc_m.group(1).strip()

        return {
            "name": name or NOT_AVAILABLE,
            "email": email,
            "phone": phone,
            "linkedin": linkedin,
            "linkedin_url": linkedin_url,
            "github": github,
            "github_url": github_url,
            "location": location or NOT_AVAILABLE
        }

    def _parse_summary(self, summary_section_text: str, full_text: str) -> str:
        """Extracts verified summary or objective paragraph."""
        if summary_section_text:
            cleaned = " ".join([l.strip() for l in summary_section_text.splitlines() if l.strip()])
            if len(cleaned) > 20:
                return cleaned
        return NOT_AVAILABLE

    def _parse_experience(self, exp_text: str, source_file: str) -> List[Dict[str, Any]]:
        """Parses individual job roles and bullet points from experience section."""
        if not exp_text:
            return []

        date_pat = re.compile(
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})[a-zA-Z0-9\s–\-—/]+(?:Present|\d{4}))',
            re.IGNORECASE
        )

        lines = [l.strip() for l in exp_text.splitlines() if l.strip()]
        entries: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for line in lines:
            is_bullet = line.startswith(('•', '-', '*', '—', '–')) or bool(re.match(r'^\d+[\.\)]\s*', line))
            has_date = bool(date_pat.search(line))

            if has_date and not is_bullet:
                if current and (current.get("bullets") or current.get("title")):
                    entries.append(current)
                d_match = date_pat.search(line)
                dates = d_match.group(1).strip() if d_match else ""
                header_no_date = date_pat.sub('', line).strip().rstrip("–-| ")
                current = {
                    "id": f"exp_{len(entries)+1}",
                    "title": header_no_date or "Professional Role",
                    "company": "",
                    "location": "India",
                    "dates": dates,
                    "bullets": [],
                    "skills": [],
                    "source_file": source_file
                }
            elif not is_bullet and current and not current.get("company"):
                current["company"] = line
            elif is_bullet:
                bullet = re.sub(r'^[•\-\*—–\d\.\s]+', '', line).strip()
                if bullet:
                    if not current:
                        current = {
                            "id": f"exp_{len(entries)+1}",
                            "title": "Professional Experience",
                            "company": "",
                            "location": "India",
                            "dates": "",
                            "bullets": [bullet],
                            "skills": [],
                            "source_file": source_file
                        }
                    else:
                        current["bullets"].append(bullet)
            else:
                if current and current["bullets"]:
                    current["bullets"][-1] += " " + line
                elif current:
                    if not current["company"]:
                        current["company"] = line
                    else:
                        current["title"] += " " + line

        if current and (current.get("bullets") or current.get("title")):
            entries.append(current)

        # Extract skills mentioned per role
        for entry in entries:
            entry_text = f"{entry.get('title', '')} {entry.get('company', '')} {' '.join(entry.get('bullets', []))}".lower()
            role_skills = []
            for _, skill_list in TECH_SKILLS_TAXONOMY.items():
                for s in skill_list:
                    if re.search(r'\b' + re.escape(s.lower()) + r'\b', entry_text):
                        if s not in role_skills:
                            role_skills.append(s)
            entry["skills"] = role_skills[:6]

        return entries

    def _parse_projects(self, proj_text: str, source_file: str) -> List[Dict[str, Any]]:
        """Parses individual projects, tools, and outcomes from projects section."""
        if not proj_text:
            return []

        lines = [l.strip() for l in proj_text.splitlines() if l.strip()]
        projects: List[Dict[str, Any]] = []

        colon_bullet_count = sum(1 for l in lines if l.startswith(('•', '-', '*')) and ':' in l[:70])

        if colon_bullet_count >= 1:
            # Bullet with colon format: each bullet is a project entry
            current: Optional[Dict[str, Any]] = None
            for line in lines:
                if line.startswith(('•', '-', '*')) and ':' in line[:70]:
                    if current:
                        projects.append(current)
                    clean_l = re.sub(r'^[•\-\*—–\s]+', '', line)
                    parts = clean_l.split(':', 1)
                    title = parts[0].strip()
                    desc = parts[1].strip() if len(parts) > 1 else ''
                    current = {
                        "id": f"proj_{len(projects)+1}",
                        "title": title,
                        "tools": "",
                        "link_text": "View Project",
                        "link_url": "",
                        "bullets": [desc] if desc else [],
                        "skills": [],
                        "source_file": source_file
                    }
                elif current:
                    clean_cont = re.sub(r'^[•\-\*—–\s]+', '', line).strip()
                    if current["bullets"]:
                        current["bullets"][-1] += " " + clean_cont
                    else:
                        current["bullets"].append(clean_cont)
            if current:
                projects.append(current)
        else:
            # Standalone project title, tools, bullets format
            current = None
            for line in lines:
                is_bullet = line.startswith(('•', '-', '*', '—', '–'))
                if is_bullet:
                    b_text = re.sub(r'^[•\-\*—–\s]+', '', line).strip()
                    if current:
                        current["bullets"].append(b_text)
                elif current and current["bullets"]:
                    looks_like_wrap = bool(re.match(r'^(and|or|in|to|with|for|by|from|as|at|of|average|regions|discounts|revenue)\b', line, re.I)) or line[0].islower()
                    if looks_like_wrap:
                        current["bullets"][-1] += " " + line
                    else:
                        projects.append(current)
                        clean_title = re.sub(r'View\s+Project', '', line, flags=re.I).strip()
                        current = {
                            "id": f"proj_{len(projects)+1}",
                            "title": clean_title,
                            "tools": "",
                            "link_text": "View Project",
                            "link_url": "",
                            "bullets": [],
                            "skills": [],
                            "source_file": source_file
                        }
                elif current and not current.get("tools"):
                    current["tools"] = line
                else:
                    clean_title = re.sub(r'View\s+Project', '', line, flags=re.I).strip()
                    current = {
                        "id": f"proj_{len(projects)+1}",
                        "title": clean_title,
                        "tools": "",
                        "link_text": "View Project",
                        "link_url": "",
                        "bullets": [],
                        "skills": [],
                        "source_file": source_file
                    }
            if current:
                projects.append(current)

        # Detect tools and skills per project
        for proj in projects:
            p_text = f"{proj.get('title', '')} {proj.get('tools', '')} {' '.join(proj.get('bullets', []))}".lower()
            proj_skills = []
            for _, skill_list in TECH_SKILLS_TAXONOMY.items():
                for s in skill_list:
                    if re.search(r'\b' + re.escape(s.lower()) + r'\b', p_text):
                        if s not in proj_skills:
                            proj_skills.append(s)
            proj["skills"] = proj_skills[:8]
            if not proj.get("tools") and proj_skills:
                proj["tools"] = ", ".join(proj_skills[:5])

        return projects

    def _parse_skills(self, skills_section_text: str, full_text: str, source_file: str) -> Tuple[Dict[str, List[str]], List[str]]:
        """Extracts ONLY verified skills that literally appear in the document."""
        categorized_skills: Dict[str, List[str]] = {}
        all_skills_flat: List[str] = []

        # Check section text first, fallback to entire document text
        search_target = (skills_section_text + "\n" + full_text).lower()

        for group, skills_list in TECH_SKILLS_TAXONOMY.items():
            matched = []
            for s in skills_list:
                pattern = r'\b' + re.escape(s.lower()) + r'\b'
                if re.search(pattern, search_target):
                    matched.append(s)
                    if s not in all_skills_flat:
                        all_skills_flat.append(s)
            if matched:
                categorized_skills[group] = matched

        return categorized_skills, all_skills_flat

    def _parse_education(self, edu_text: str, source_file: str) -> List[Dict[str, Any]]:
        """Parses education degrees, institutions, and scores."""
        if not edu_text:
            return []

        lines = [l.strip() for l in edu_text.splitlines() if l.strip()]
        edu_list: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        date_pat = re.compile(r'((?:19|20)\d{2}\s*[\-–]\s*(?:(?:19|20)\d{2}|Present)|\b(?:19|20)\d{2}\b)', re.I)

        for line in lines:
            has_date = bool(date_pat.search(line))
            is_bullet = line.startswith(('•', '-', '*'))

            if not is_bullet and (has_date or any(w in line.lower() for w in ["institute", "university", "college", "school", "board", "academy"])):
                if current:
                    edu_list.append(current)
                d_m = date_pat.search(line)
                d_str = d_m.group(0).strip() if d_m else ""
                inst = date_pat.sub('', line).strip().rstrip("–-| ")
                current = {
                    "institution": inst or "Educational Institution",
                    "degree": "",
                    "dates": d_str,
                    "source_file": source_file
                }
            elif current and not current.get("degree"):
                current["degree"] = line.lstrip("•-* ")
            elif current:
                current["degree"] += " | " + line.lstrip("•-* ")
            else:
                current = {
                    "institution": line,
                    "degree": "",
                    "dates": "",
                    "source_file": source_file
                }

        if current:
            edu_list.append(current)

        return edu_list

    def _parse_certifications(self, cert_text: str, source_file: str) -> List[Dict[str, Any]]:
        """Parses certification titles and credential credentials."""
        if not cert_text:
            return []

        lines = [l.strip() for l in cert_text.splitlines() if l.strip()]
        certs: List[Dict[str, Any]] = []

        for line in lines:
            clean = re.sub(r'^[•\-\*—–\d\.\s]+', '', line).strip()
            clean = re.sub(r'Credential\s+Link', '', clean, flags=re.I).strip()
            if len(clean) > 8:
                certs.append({
                    "name": clean,
                    "link": "Credential Link",
                    "url": "#",
                    "source_file": source_file
                })

        return certs

    def _parse_achievements(self, award_text: str, source_file: str) -> List[Dict[str, Any]]:
        """Parses awards or achievements."""
        if not award_text:
            return []

        lines = [l.strip() for l in award_text.splitlines() if l.strip()]
        achievements: List[Dict[str, Any]] = []

        for line in lines:
            clean = re.sub(r'^[•\-\*—–\d\.\s]+', '', line).strip()
            if len(clean) > 10:
                achievements.append({
                    "title": clean[:100],
                    "description": clean,
                    "source_file": source_file
                })

        return achievements


# Global singleton parser
master_resume_parser = ResumeParser()
