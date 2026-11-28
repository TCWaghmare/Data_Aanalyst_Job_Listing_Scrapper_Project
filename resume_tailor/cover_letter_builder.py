"""
Personalized Cover Letter & Application Response Builder.
Generates role-tailored cover letters, executive summaries, and application answers
synthesized directly from the Career Knowledge Base.
Supports export to Word (.docx), PDF (Edge headless), and Plain Text (.txt).
"""

import os
import io
import re
import subprocess
from datetime import datetime
from typing import Dict, Any, List

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml

from resume_tailor.pdf_compiler import find_browser_executable, EDGE_PATH
from resume_tailor.validator import validate_against_knowledge_base, KnowledgeBaseValidationError


def fix_casing_and_money(text: str) -> str:
    """
    Fixes tool casing (SQL, Power BI, Excel, Tableau, Python, Power Query, DAX) and formats money as $389.3M.
    """
    if not text:
        return ""
    # Tool casing
    text = re.sub(r"\b(?:sql|Sql)\b", "SQL", text)
    text = re.sub(r"\b(?:power\s*bi|Power\s*Bi|powerbi|Powerbi|POWER\s*BI)\b", "Power BI", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:excel|EXCEL)\b", "Excel", text)
    text = re.sub(r"\b(?:tableau|TABLEAU)\b", "Tableau", text)
    text = re.sub(r"\b(?:python|PYTHON)\b", "Python", text)
    text = re.sub(r"\b(?:power\s*query|Power\s*query|powerquery)\b", "Power Query", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:dax|Dax)\b", "DAX", text)

    # Money formatting
    text = re.sub(r"(?<!\$)\b389\.3\s*(?:million|[mM])\b", "$389.3M", text)
    text = re.sub(r"\$\s*389\.3\s*(?:million|[mM])\b", "$389.3M", text)
    text = re.sub(r"\$\s*389\.3\b(?![mM])", "$389.3M", text)

    text = re.sub(r"(?<!\$)\b205\s*(?:million|[mM])\b", "$205M", text)
    text = re.sub(r"\$\s*205\s*(?:million|[mM])\b", "$205M", text)

    text = re.sub(r"(?<!\$)\b32\.8\s*(?:million|[mM])\b", "$32.8M", text)
    text = re.sub(r"\$\s*32\.8\s*(?:million|[mM])\b", "$32.8M", text)

    text = re.sub(r"\$\s*(\d+(?:\.\d+)?)\s*million\b", r"$\1M", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\$)\b(\d+(?:\.\d+)?)\s*million\s+dollars\b", r"$\1M", text, flags=re.IGNORECASE)
    return text


def remove_awkward_fragments(text: str) -> str:
    """
    Removes awkward fragments such as 'foundation in KPIs' and cleans up awkward phrasing.
    """
    if not text:
        return ""

    # 1. Fix awkward 'foundation in KPIs' phrases
    text = re.sub(
        r"\b(?:solid\s+)?(?:hands-on\s+)?foundation\s+in\s+KPIs\b",
        "hands-on foundation in analytical KPI tracking and business intelligence reporting",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"\b(?:solid\s+)?(?:hands-on\s+)?foundation\s+in\s+key\s+performance\s+indicators\b",
        "hands-on foundation in analytical KPI tracking and operational reporting",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"\b(?:solid\s+)?(?:hands-on\s+)?foundation\s+in\s+KPI\s+reporting\b",
        "hands-on foundation in KPI reporting and business intelligence",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"\b(?:solid\s+)?(?:hands-on\s+)?foundation\s+in\s+dashboards?\b",
        "hands-on foundation in dashboard engineering and visual analytics",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"\b(?:solid\s+)?(?:hands-on\s+)?foundation\s+in\s+reporting\b",
        "hands-on foundation in business intelligence reporting",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"\b(?:solid\s+)?(?:hands-on\s+)?foundation\s+in\s+the\s+required\s+core\s+skills\b",
        "solid foundation in SQL, Power BI, and Advanced Excel",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"\bproficiency\s+in\s+core\s+industry\s+tools\b",
        "proficiency in SQL, Power BI, and Advanced Excel",
        text,
        flags=re.IGNORECASE
    )

    # 2. Punctuation & Spacing cleanup
    text = re.sub(r"\s+([,\.;:])", r"\1", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()


def paraphrase_key_duties(
    job_title: str,
    responsibilities: List[str] = None,
    job_description: str = "",
    company: str = ""
) -> str:
    """
    Synthesizes 2-3 key duties from the job context into natural, professional sentences.
    Never copies verbatim text from the job description or responsibilities list.
    """
    combined = f"{job_title} {job_description} {' '.join(responsibilities or [])}".lower()

    # 1. Supply Chain / Material Planning / Inventory / Logistics (e.g. Cummins)
    if any(k in combined for k in ["supply chain", "inventory", "pfep", "material planning", "materials kpi", "demand planning", "forecast exception", "logistics"]):
        return (
            "Specifically, I am drawn to the opportunity to analyze demand and forecast variations, "
            "monitor material and inventory KPIs, and ensure rigorous data integrity across operational reporting."
        )

    # 2. Survey / Market Research / Tabulations / Studies / Polling (e.g. Comscore)
    if any(k in combined for k in ["survey", "tabulation", "tabulations", "ad tracking", "brand tracking", "effectiveness studies", "questionnaire"]):
        return (
            "In particular, I am drawn to the opportunity to process and evaluate survey datasets, "
            "verify data quality across ongoing tracking studies, and deliver clear tabular reporting to support research objectives."
        )

    # 3. Financial Analysis / FP&A / Variance / Cost / Revenue
    if any(k in combined for k in ["financial analyst", "variance analysis", "budgeting", "p&l", "revenue forecasting", "cost reduction"]):
        return (
            "Specifically, I am drawn to the opportunity to conduct performance variance analysis, "
            "track revenue and cost drivers, and synthesize transactional datasets into clear executive reporting."
        )

    # 4. Marketing Analytics / Growth / Attribution / Conversion
    if any(k in combined for k in ["marketing analyst", "campaign", "customer acquisition", "attribution", "conversion rate", "funnel"]):
        return (
            "Specifically, I am drawn to the opportunity to evaluate campaign performance metrics, "
            "analyze customer acquisition funnels, and generate actionable insights to optimize marketing initiatives."
        )

    # 5. Operations / Process Improvement / Operational Analytics
    if any(k in combined for k in ["operational analysis", "operations analyst", "process improvement", "workflow efficiency", "sla"]):
        return (
            "Specifically, I am drawn to the opportunity to analyze operational workflow metrics, "
            "identify process improvement opportunities, and deliver reliable reporting that supports cross-functional decision-making."
        )

    # 6. Dynamic Extraction & Paraphrasing for custom/arbitrary job duties
    if responsibilities:
        boilerplate_keywords = ["degree", "bachelor", "master", "medical", "pension", "leave", "insurance", "what you", "benefit", "years of"]
        duty_candidates = []
        for r in responsibilities:
            r_clean = re.sub(r'^[•\-\*\d+\.\)]\s*', '', r).strip()
            if len(r_clean) < 15 or len(r_clean) > 200:
                continue
            if any(b in r_clean.lower() for b in boilerplate_keywords):
                continue
            duty_candidates.append(r_clean)

        if duty_candidates:
            synthesized = []
            for cand in duty_candidates[:3]:
                c_sub = re.sub(
                    r'^(?:responsible for|responsible to|ability to|proven ability to|experience in|deliver exceptional|deliver|engage in|perform|provide|support|help ensure|conduct|manage|execute)\s+',
                    '',
                    cand,
                    flags=re.IGNORECASE
                )
                words = c_sub.split()
                if len(words) >= 3:
                    first_w = words[0].lower()
                    rest = " ".join(words[1:6]).rstrip(",.;:")
                    if first_w.endswith("ing"):
                        synthesized.append(f"{first_w} {rest}")
                    elif first_w.endswith("e"):
                        synthesized.append(f"{first_w[:-1]}ing {rest}")
                    else:
                        synthesized.append(f"{first_w}ing {rest}")
            if len(synthesized) >= 2:
                duties_text = ", ".join(synthesized[:-1]) + f", and {synthesized[-1]}"
                return f"Specifically, I look forward to contributing towards {duties_text}."

    # 7. Default for Business Intelligence & Data Analysis roles
    return (
        "Specifically, I am drawn to the opportunity to engineer interactive dashboards, "
        "automate KPI reporting workflows, and translate complex datasets into clear, actionable business insights."
    )


is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
OUTPUT_DIR = "/tmp/data/resumes" if is_serverless else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resumes")
try:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
except OSError:
    pass

# Monochrome Overleaf / LaTeX Styling (Jake's Resume / Overleaf Theme)
FONT_SERIF = "Times New Roman"
COLOR_BLACK = RGBColor(0, 0, 0)
COLOR_DARK = RGBColor(20, 20, 20)
COLOR_MUTED = RGBColor(60, 60, 60)

class CoverLetterBuilder:
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        try:
            if self.output_dir:
                os.makedirs(self.output_dir, exist_ok=True)
        except OSError:
            pass

    def generate(
        self,
        job_title: str,
        company: str,
        job_description: str,
        job_skills: List[str],
        profile: Dict[str, Any],
        responsibilities: List[str] = None,
        requirements: List[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a personalized cover letter, executive summary, and application responses
        grounded strictly in the candidate's verified Career Knowledge Base.
        Never states unheld titles, never pastes JD text verbatim, fixes casing and money,
        eliminates awkward fragments, and strictly validates all output entities against the KB.
        """
        name = profile.get("name", "Candidate")
        contact = profile.get("contact", {})
        email = contact.get("email", "")
        phone = contact.get("phone", "")
        linkedin = contact.get("linkedin_url") or contact.get("linkedin", "")
        github = contact.get("github_url") or contact.get("github", "")

        today_str = datetime.now().strftime("%B %d, %Y")
        clean_title = (job_title or "Data Analyst").strip()
        clean_company = (company or "Hiring Team").strip()

        # Identify key matching projects from knowledge base
        projects = profile.get("projects", [])
        best_project = projects[0] if projects else None
        second_project = projects[1] if len(projects) > 1 else None

        # Identify certifications
        certs = profile.get("certifications", [])
        cert_names = [
            re.sub(r"\s+(?:Link|\[Link\]\(.*?\))\s*$", "", (c.get("name") if isinstance(c, dict) else str(c))).strip()
            for c in certs[:3]
        ]

        # Select verified technical tools only (never non-tool terms like 'KPIs' or 'Dashboards')
        primary_tool_whitelist = [
            "Power BI", "SQL", "Excel", "Advanced Excel", "Python",
            "Microsoft Fabric", "PostgreSQL", "DAX", "Power Query", "Pandas", "NumPy"
        ]
        jd_text = f"{job_title} {job_description} {' '.join(job_skills or [])}".lower()
        matched_tools = [t for t in primary_tool_whitelist if re.search(r"\b" + re.escape(t.lower()) + r"\b", jd_text)]
        if not matched_tools:
            matched_tools = ["Power BI", "SQL", "Advanced Excel"]
        elif len(matched_tools) == 1:
            for fallback_t in ["SQL", "Power BI", "Advanced Excel"]:
                if fallback_t not in matched_tools:
                    matched_tools.append(fallback_t)
                if len(matched_tools) >= 3:
                    break

        # Format tools naturally (e.g. "Power BI, SQL, and Advanced Excel")
        if len(matched_tools) == 1:
            tools_str = matched_tools[0]
        elif len(matched_tools) == 2:
            tools_str = f"{matched_tools[0]} and {matched_tools[1]}"
        else:
            tools_str = f"{', '.join(matched_tools[:2])}, and {matched_tools[2]}"

        # 1. Generate Structured Cover Letter Paragraphs
        p1_intro = (
            f"I am writing to express my strong enthusiasm for the {clean_title} position at {clean_company}. "
            f"With a solid hands-on foundation in {tools_str}, "
            f"I am eager to contribute immediately to {clean_company}'s ongoing initiatives and deliver high-impact results."
        )

        p2_experience = ""
        if best_project:
            proj_title = best_project.get("title", "Technical Project")
            proj_bullets = best_project.get("bullets", [])
            first_bullet = proj_bullets[0] if proj_bullets else "delivered tangible project milestones."
            p2_experience = (
                f"Throughout my project portfolio, I have focused on translating requirements into practical, high-value outcomes. "
                f"For example, in my '{proj_title}' initiative, I {first_bullet.lower() if first_bullet.startswith(('Built', 'Analyzed', 'Managed', 'Led', 'Prepared', 'Developed')) else first_bullet} "
                f"This demonstrated my ability to apply disciplined methodologies, validate technical accuracy, and drive measurable project success."
            )
        elif profile.get("experience"):
            top_exp = profile["experience"][0]
            exp_role = top_exp.get("title", "Technical Specialist")
            exp_comp = top_exp.get("company", "previous organization")
            exp_bullets = top_exp.get("bullets", [])
            first_b = exp_bullets[0] if exp_bullets else "contributed to operational success and documentation."
            p2_experience = (
                f"In my professional role as {exp_role} at {exp_comp}, I have consistently focused on quality execution and operational rigor. "
                f"Specifically, I {first_b.lower() if first_b.startswith(('Built', 'Analyzed', 'Managed', 'Led', 'Prepared', 'Developed', 'Automated')) else first_b} "
                f"This reinforced my commitment to continuous improvement and technical excellence."
            )
        else:
            p2_experience = (
                f"Throughout my academic and technical training, I have developed strong foundational discipline and problem-solving capabilities. "
                f"I am dedicated to upholding the highest standards of accuracy, documentation, and rigorous execution across all responsibilities."
            )

        cert_sentence = ""
        if cert_names:
            cert_sentence = f" To substantiate my technical discipline, I have earned industry-recognized credentials including {cert_names[0]}."

        duty_sentence = paraphrase_key_duties(job_title, responsibilities, job_description, company)
        p3_skills = (
            f"Your job posting emphasizes proficiency in {tools_str}. {duty_sentence} "
            f"In my verified background, I have consistently applied these tools and analytical principles to solve complex problems and ensure high-standard deliverables.{cert_sentence} "
            f"I am highly adaptable, eager to master {clean_company}'s internal workflows, and dedicated to upholding the highest standards of data integrity."
        )

        p4_closing = (
            f"I would welcome the opportunity to discuss how my analytical skills, dedication, and problem-solving mindset can support {clean_company}'s business goals. "
            f"Thank you for your time and consideration."
        )

        raw_paragraphs = [p1_intro, p2_experience, p3_skills, p4_closing]
        body_paragraphs = [fix_casing_and_money(remove_awkward_fragments(p)) for p in raw_paragraphs]

        # 2. Executive Summary / Elevator Pitch (Strictly using "Data analyst with ..., targeting <title> roles")
        raw_exec_summary = (
            f"Data analyst with verified hands-on proficiency in {tools_str}, targeting {clean_title} roles. "
            f"Demonstrated ability to execute technical workflows, maintain high data accuracy, and deliver actionable results. "
            f"Recognized for fast learning agility, rigorous validation, and clear professional communication."
        )
        exec_summary = fix_casing_and_money(remove_awkward_fragments(raw_exec_summary))

        # 3. Application Responses (Strictly Evidence-Based)
        q2_answer = ""
        if best_project:
            p_t = best_project.get('title', 'Technical Project')
            p_tools = best_project.get('tools', tools_str)
            p_b = best_project.get('bullets', ['Executed core milestones according to rigorous standards.'])[0]
            q2_answer = (
                f"In my '{p_t}' initiative, I applied {p_tools} to solve key challenges: {p_b} "
                f"This project demonstrated my hands-on ability to deliver measurable, production-grade results."
            )
        elif profile.get("experience"):
            top_e = profile["experience"][0]
            top_b = top_e.get("bullets", ["Executed critical deliverables."])[0]
            q2_answer = (
                f"During my work as {top_e.get('title')} at {top_e.get('company')}, I achieved measurable progress: {top_b} "
                f"This experience solidified my technical discipline and problem-solving execution."
            )
        else:
            q2_answer = (
                f"Throughout my technical preparation in {tools_str}, I have focused on solving real-world challenges with verified accuracy and documentation."
            )

        q3_cert_note = f" Supported by verified credentials including {cert_names[0]}, " if cert_names else " "
        app_responses = [
            {
                "question": f"Why are you interested in joining {clean_company} as a {clean_title}?",
                "answer": fix_casing_and_money(remove_awkward_fragments(
                    f"I am excited by {clean_company}'s reputation for quality and innovation. As an analytical professional targeting {clean_title} roles, "
                    f"I want to apply my verified proficiency in {tools_str} to support strategic objectives. "
                    f"The role aligns with my dedication to precision, continuous learning, and cross-functional collaboration."
                ))
            },
            {
                "question": "Can you highlight a significant project or achievement from your background?",
                "answer": fix_casing_and_money(remove_awkward_fragments(q2_answer))
            },
            {
                "question": f"How do your skills match our requirements for {clean_title}?",
                "answer": fix_casing_and_money(remove_awkward_fragments(
                    f"My background directly demonstrates practical capability in {tools_str}.{q3_cert_note}"
                    f"I have consistently applied these skills to maintain high standards of execution, documentation, and continuous improvement."
                ))
            }
        ]

        # 4. Generate Plain Text Representation
        text_lines = [
            name.upper(),
            f"Email: {email} | Phone: {phone} | Location: India",
            f"LinkedIn: {linkedin} | GitHub: {github}",
            "",
            today_str,
            "",
            f"Hiring Team / Talent Acquisition",
            f"{clean_company}",
            f"RE: Application for {clean_title}",
            "",
            "Dear Hiring Manager,",
            "",
            body_paragraphs[0],
            "",
            body_paragraphs[1],
            "",
            body_paragraphs[2],
            "",
            body_paragraphs[3],
            "",
            "Sincerely,",
            name
        ]
        full_text = fix_casing_and_money(remove_awkward_fragments("\n".join(text_lines)))

        result_data = {
            "candidate_name": name,
            "target_role": clean_title,
            "target_company": clean_company,
            "date": today_str,
            "contact": contact,
            "paragraphs": body_paragraphs,
            "full_text": full_text,
            "executive_summary": exec_summary,
            "application_responses": app_responses,
            "matched_skills": [t for t in matched_tools if t in primary_tool_whitelist]
        }

        # 5. Strict Knowledge Base Validation Pass
        validate_against_knowledge_base(
            result_data,
            profile,
            target_company=clean_company,
            target_job_title=clean_title
        )

        return result_data

    def build_docx(self, cover_letter_data: Dict[str, Any], job_id: str) -> str:
        """
        Creates an editable Microsoft Word (.docx) document formatted with
        Overleaf LaTeX Jake's Resume serif styling (Times New Roman, monochrome).
        """
        clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
        file_path = os.path.join(self.output_dir, f"cover_letter_{clean_id}.docx")

        doc = Document()
        for section in doc.sections:
            section.top_margin = Inches(0.65)
            section.bottom_margin = Inches(0.65)
            section.left_margin = Inches(0.7)
            section.right_margin = Inches(0.7)

        name = cover_letter_data.get("candidate_name", "Tejas C. Waghmare")
        contact = cover_letter_data.get("contact", {})
        date_str = cover_letter_data.get("date", datetime.now().strftime("%B %d, %Y"))
        target_role = cover_letter_data.get("target_role", "Data Analyst")
        target_company = cover_letter_data.get("target_company", "Target Employer")
        paragraphs = cover_letter_data.get("paragraphs", [])

        # Header: Candidate Name (Centered, Small-Caps Serif Bold)
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_name.paragraph_format.space_before = Pt(0)
        p_name.paragraph_format.space_after = Pt(2)
        run_name = p_name.add_run(name.upper())
        run_name.font.name = FONT_SERIF
        run_name.font.size = Pt(17)
        run_name.font.bold = True
        run_name.font.color.rgb = COLOR_BLACK

        # Header: Contact Info Line with bottom rule
        p_contact = doc.add_paragraph()
        p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_contact.paragraph_format.space_before = Pt(0)
        p_contact.paragraph_format.space_after = Pt(14)

        contact_parts = []
        if contact.get("phone"):
            contact_parts.append(contact["phone"])
        if contact.get("email"):
            contact_parts.append(contact["email"])
        if contact.get("linkedin"):
            clean_li = contact["linkedin"].replace("https://", "").replace("www.", "")
            contact_parts.append(clean_li)
        if contact.get("github"):
            clean_gh = contact["github"].replace("https://", "").replace("www.", "")
            contact_parts.append(clean_gh)

        run_contact = p_contact.add_run("  |  ".join(contact_parts))
        run_contact.font.name = FONT_SERIF
        run_contact.font.size = Pt(8.5)
        run_contact.font.color.rgb = COLOR_DARK

        # Add horizontal bottom divider border under header
        pPr = p_contact._p.get_or_add_pPr()
        pBdr = parse_xml(
            r'<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            r'<w:bottom w:val="single" w:sz="6" w:space="3" w:color="000000"/>'
            r'</w:pBdr>'
        )
        pPr.append(pBdr)

        # Date
        p_date = doc.add_paragraph()
        p_date.paragraph_format.space_before = Pt(6)
        p_date.paragraph_format.space_after = Pt(10)
        r_date = p_date.add_run(date_str)
        r_date.font.name = FONT_SERIF
        r_date.font.size = Pt(10)
        r_date.font.color.rgb = COLOR_BLACK

        # Recipient Info
        p_to = doc.add_paragraph()
        p_to.paragraph_format.space_before = Pt(0)
        p_to.paragraph_format.space_after = Pt(2)
        r_to1 = p_to.add_run("Hiring Team / Talent Acquisition\n")
        r_to1.font.name = FONT_SERIF
        r_to1.font.size = Pt(10)
        r_to1.font.bold = True
        r_to1.font.color.rgb = COLOR_BLACK
        r_to2 = p_to.add_run(f"{target_company}\n")
        r_to2.font.name = FONT_SERIF
        r_to2.font.size = Pt(10)
        r_to2.font.color.rgb = COLOR_BLACK
        r_to3 = p_to.add_run(f"RE: Application for {target_role}")
        r_to3.font.name = FONT_SERIF
        r_to3.font.size = Pt(10)
        r_to3.font.bold = True
        r_to3.font.color.rgb = COLOR_BLACK

        # Salutation
        p_sal = doc.add_paragraph()
        p_sal.paragraph_format.space_before = Pt(10)
        p_sal.paragraph_format.space_after = Pt(8)
        r_sal = p_sal.add_run("Dear Hiring Manager,")
        r_sal.font.name = FONT_SERIF
        r_sal.font.size = Pt(10.5)
        r_sal.font.color.rgb = COLOR_BLACK

        # Body Paragraphs
        for para_text in paragraphs:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.18
            r = p.add_run(para_text)
            r.font.name = FONT_SERIF
            r.font.size = Pt(10)
            r.font.color.rgb = COLOR_BLACK

        # Sign-off
        p_sign = doc.add_paragraph()
        p_sign.paragraph_format.space_before = Pt(12)
        p_sign.paragraph_format.space_after = Pt(3)
        r_sign = p_sign.add_run("Sincerely,")
        r_sign.font.name = FONT_SERIF
        r_sign.font.size = Pt(10)
        r_sign.font.color.rgb = COLOR_BLACK

        p_myname = doc.add_paragraph()
        p_myname.paragraph_format.space_before = Pt(0)
        p_myname.paragraph_format.space_after = Pt(0)
        r_myname = p_myname.add_run(name)
        r_myname.font.name = FONT_SERIF
        r_myname.font.size = Pt(10.5)
        r_myname.font.bold = True
        r_myname.font.color.rgb = COLOR_BLACK

        doc.save(file_path)
        return file_path

    def _compile_pure_python_pdf(self, data: Dict[str, Any], pdf_path: str) -> str:
        """Pure-Python standard 1-page PDF generator for cover letters."""
        name = data.get("candidate_name", "Tejas C. Waghmare")
        contact = data.get("contact", {})
        date_str = data.get("date", datetime.now().strftime("%B %d, %Y"))
        target_role = data.get("target_role", "Data Analyst")
        target_company = data.get("target_company", "Target Employer")
        paragraphs = data.get("paragraphs", [])

        def escape_pdf(text: str) -> str:
            t = str(text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
            t = t.replace("–", "-").replace("—", "-").replace("•", "*").replace("\xa0", " ")
            return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        def wrap(text: str, max_chars: int = 90) -> List[str]:
            words = str(text).split()
            lines = []
            cur = []
            cur_len = 0
            for w in words:
                if cur_len + len(w) + (1 if cur else 0) > max_chars:
                    lines.append(" ".join(cur))
                    cur = [w]
                    cur_len = len(w)
                else:
                    cur.append(w)
                    cur_len += len(w) + (1 if len(cur) > 1 else 0)
            if cur:
                lines.append(" ".join(cur))
            return lines

        contact_parts = []
        if contact.get("phone"):
            contact_parts.append(contact["phone"])
        if contact.get("email"):
            contact_parts.append(contact["email"])
        if contact.get("linkedin"):
            contact_parts.append(contact["linkedin"])
        contact_line = " | ".join(contact_parts)

        ops = []
        y = 750
        left_x = 45
        right_x = 567

        # Name Header
        ops.append(f"BT /F1 15 Tf {left_x} {y} Td ({escape_pdf(name)}) Tj ET")
        y -= 15
        if contact_line:
            ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({escape_pdf(contact_line)}) Tj ET")
            y -= 14
        ops.append(f"0.75 w {left_x} {y} m {right_x} {y} l S")
        y -= 20

        # Date
        ops.append(f"BT /F2 9.5 Tf {left_x} {y} Td ({escape_pdf(date_str)}) Tj ET")
        y -= 18

        # Recruiter / Employer Block
        ops.append(f"BT /F1 9.5 Tf {left_x} {y} Td (Hiring Team) Tj ET")
        y -= 13
        ops.append(f"BT /F2 9.5 Tf {left_x} {y} Td ({escape_pdf(target_company)}) Tj ET")
        y -= 18

        # Subject Line
        ops.append(f"BT /F1 10 Tf {left_x} {y} Td (SUBJECT: Application for {escape_pdf(target_role)} Role) Tj ET")
        y -= 18

        # Salutation
        ops.append(f"BT /F2 9.5 Tf {left_x} {y} Td (Dear Hiring Team,) Tj ET")
        y -= 16

        # Paragraphs
        for p in paragraphs:
            for line in wrap(p, 92):
                ops.append(f"BT /F2 9 Tf {left_x} {y} Td ({escape_pdf(line)}) Tj ET")
                y -= 12
            y -= 6

        # Sign-off
        y -= 4
        ops.append(f"BT /F2 9.5 Tf {left_x} {y} Td (Sincerely,) Tj ET")
        y -= 14
        ops.append(f"BT /F1 10 Tf {left_x} {y} Td ({escape_pdf(name)}) Tj ET")

        stream_content = "\n".join(ops).encode('latin1', errors='replace')
        objects = [
            b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>',
            b'<< /Length ' + str(len(stream_content)).encode('ascii') + b' >>\nstream\n' + stream_content + b'\nendstream',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
        ]

        out = io.BytesIO()
        out.write(b'%PDF-1.4\n')
        offsets = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(out.tell())
            out.write(f'{i} 0 obj\n'.encode('ascii'))
            out.write(obj)
            out.write(b'\nendobj\n')

        startxref = out.tell()
        out.write(b'xref\n')
        out.write(f'0 {len(objects) + 1}\n'.encode('ascii'))
        out.write(b'0000000000 65535 f \n')
        for offset in offsets[1:]:
            out.write(f'{offset:010d} 00000 n \n'.encode('ascii'))

        out.write(b'trailer\n')
        out.write(f'<< /Size {len(objects) + 1} /Root 1 0 R >>\n'.encode('ascii'))
        out.write(b'startxref\n')
        out.write(f'{startxref}\n'.encode('ascii'))
        out.write(b'%%EOF\n')

        with open(pdf_path, "wb") as f:
            f.write(out.getvalue())

        return pdf_path

    def build_pdf(self, cover_letter_data: Dict[str, Any], job_id: str) -> str:
        """
        Compiles the cover letter into a clean PDF via headless browser or pure Python fallback.
        """
        clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
        html_path = os.path.join(self.output_dir, f"cover_letter_{clean_id}.html")
        pdf_path = os.path.join(self.output_dir, f"cover_letter_{clean_id}.pdf")

        html = self._generate_html(cover_letter_data)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        browser_exe = find_browser_executable()
        if browser_exe:
            cmd = [
                browser_exe,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={os.path.abspath(pdf_path)}",
                os.path.abspath(html_path)
            ]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            except Exception as e:
                print(f"[CoverLetter] Headless browser error: {e}")

        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            self._compile_pure_python_pdf(cover_letter_data, pdf_path)

        return pdf_path

    def _generate_html(self, data: Dict[str, Any]) -> str:
        name = data.get("candidate_name", "Tejas C. Waghmare")
        contact = data.get("contact", {})
        date_str = data.get("date", datetime.now().strftime("%B %d, %Y"))
        target_role = data.get("target_role", "Data Analyst")
        target_company = data.get("target_company", "Target Employer")
        paragraphs = data.get("paragraphs", [])

        # Dynamic contact line with pipe separators matching Overleaf
        contact_parts = []
        if contact.get("phone"):
            contact_parts.append(contact["phone"])
        if contact.get("email"):
            contact_parts.append(f'<a href="mailto:{contact["email"]}" style="text-decoration: underline; color: #000;">{contact["email"]}</a>')
        if contact.get("linkedin"):
            clean_li = contact["linkedin"].replace("https://", "").replace("www.", "")
            contact_parts.append(f'<a href="{contact.get("linkedin_url", f"https://{contact["linkedin"]}")}" style="text-decoration: underline; color: #000;">{clean_li}</a>')
        if contact.get("github"):
            clean_gh = contact["github"].replace("https://", "").replace("www.", "")
            contact_parts.append(f'<a href="{contact.get("github_url", f"https://{contact["github"]}")}" style="text-decoration: underline; color: #000;">{clean_gh}</a>')
        contact_line = " | ".join(contact_parts) if contact_parts else "Information Not Available in Uploaded Documents"

        body_html = "".join([f'<p style="margin: 0 0 10px 0; font-size: 10pt; line-height: 1.45; text-align: justify; color: #000;">{p}</p>' for p in paragraphs])

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{name} - Cover Letter</title>
<style>
  @page {{
    size: letter portrait;
    margin: 0.6in 0.65in 0.6in 0.65in;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: "Computer Modern Roman", "Latin Modern Roman", "Times New Roman", Times, serif;
    color: #000000;
    background: #ffffff;
    line-height: 1.45;
    font-size: 10pt;
  }}
  .header {{
    text-align: center;
    border-bottom: 1px solid #000000;
    padding-bottom: 6px;
    margin-bottom: 16px;
  }}
  .header h1 {{
    font-size: 19pt;
    font-weight: normal;
    font-variant: small-caps;
    letter-spacing: 0.5px;
    margin-bottom: 3px;
    color: #000000;
  }}
  .header .contact {{
    font-size: 8.5pt;
    color: #111111;
  }}
  .header .contact a {{
    color: #000000;
    text-decoration: underline;
  }}
  .date {{
    font-size: 10pt;
    margin-bottom: 14px;
    color: #000000;
  }}
  .recipient {{
    margin-bottom: 14px;
    line-height: 1.4;
    font-size: 10pt;
    color: #000000;
  }}
  .recipient strong {{
    color: #000000;
  }}
  .salutation {{
    font-size: 10.5pt;
    margin-bottom: 12px;
    color: #000000;
  }}
  .closing {{
    margin-top: 20px;
    font-size: 10pt;
    color: #000000;
  }}
  .sign-name {{
    font-weight: bold;
    color: #000000;
    margin-top: 4px;
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>{name}</h1>
    <div class="contact">{contact_line}</div>
  </div>

  <div class="date">{date_str}</div>

  <div class="recipient">
    <strong>Hiring Team / Talent Acquisition</strong><br>
    {target_company}<br>
    <strong>RE: Application for {target_role}</strong>
  </div>

  <div class="salutation">Dear Hiring Manager,</div>

  <div class="body">
    {body_html}
  </div>

  <div class="closing">
    Sincerely,<br>
    <div class="sign-name">{name}</div>
  </div>
</body>
</html>"""

cover_letter_builder = CoverLetterBuilder()

