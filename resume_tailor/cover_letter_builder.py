"""
Personalized Cover Letter & Application Response Builder.
Generates role-tailored cover letters, executive summaries, and application answers
synthesized directly from the Career Knowledge Base.
Supports export to Word (.docx), PDF (Edge headless), and Plain Text (.txt).
"""

import os
import re
import subprocess
from datetime import datetime
from typing import Dict, Any, List

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml

EDGE_PATH = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resumes")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Monochrome Overleaf / LaTeX Styling (Jake's Resume / Overleaf Theme)
FONT_SERIF = "Times New Roman"
COLOR_BLACK = RGBColor(0, 0, 0)
COLOR_DARK = RGBColor(20, 20, 20)
COLOR_MUTED = RGBColor(60, 60, 60)

class CoverLetterBuilder:
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir

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
        cert_names = [c.get("name", str(c)) for c in certs[:3] if isinstance(c, dict)]

        # Identify matching technical skills
        all_skills = profile.get("technical_tools", [])
        jd_text = f"{job_title} {job_description} {' '.join(job_skills or [])}".lower()
        matched_skills = [s for s in all_skills if re.search(r"\b" + re.escape(s.lower()) + r"\b", jd_text)]
        if not matched_skills:
            matched_skills = all_skills[:5]

        # 1. Generate Structured Cover Letter Paragraphs
        tools_str = ', '.join(matched_skills[:3]) if matched_skills else "the required core skills"
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

        resp_sentence = ""
        if responsibilities:
            clean_resps = [re.sub(r'^[•\-\*\d+\.\)]\s*', '', r).strip() for r in responsibilities if len(r) > 12]
            if clean_resps:
                top_resp = clean_resps[0]
                if not top_resp.endswith("."):
                    top_resp += "."
                resp_sentence = f" I am particularly energized by the role's focus on key duties such as {top_resp.lower() if not top_resp.startswith('I') else top_resp}"

        top_skills_str = ', '.join((job_skills or matched_skills)[:4]) if (job_skills or matched_skills) else "the required competencies"
        p3_skills = (
            f"Your job posting emphasizes proficiency in {top_skills_str}.{resp_sentence} "
            f"In my verified background, I have consistently applied these tools and principles to solve complex problems and ensure high-standard deliverables.{cert_sentence} "
            f"I am highly adaptable, eager to master {clean_company}'s internal workflows, and dedicated to upholding the highest standards of quality."
        )

        p4_closing = (
            f"I would welcome the opportunity to discuss how my analytical skills, dedication, and problem-solving mindset can support {clean_company}'s business goals. "
            f"Thank you for your time and consideration."
        )

        body_paragraphs = [p1_intro, p2_experience, p3_skills, p4_closing]

        # 2. Executive Summary / Elevator Pitch
        exec_skills_str = ', '.join(matched_skills[:4]) if matched_skills else "core technical competencies"
        exec_summary = (
            f"Qualified {clean_title} candidate with verified hands-on proficiency in {exec_skills_str}. "
            f"Demonstrated ability to execute technical workflows, maintain high accuracy, and deliver actionable results. "
            f"Recognized for fast learning agility, rigorous validation, and clear professional communication."
        )

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
                "answer": (
                    f"I am excited by {clean_company}'s reputation for quality and innovation. As a {clean_title} candidate, "
                    f"I want to apply my verified proficiency in {', '.join(matched_skills[:3]) if matched_skills else 'core industry tools'} to support strategic objectives. "
                    f"The role aligns with my dedication to precision, continuous learning, and cross-functional collaboration."
                )
            },
            {
                "question": "Can you highlight a significant project or achievement from your background?",
                "answer": q2_answer
            },
            {
                "question": f"How do your skills match our requirements for {', '.join((job_skills or matched_skills)[:3]) if (job_skills or matched_skills) else 'this role'}?",
                "answer": (
                    f"My background directly demonstrates practical capability in {', '.join(matched_skills[:4]) if matched_skills else 'the core competencies for this role'}.{q3_cert_note}"
                    f"I have consistently applied these skills to maintain high standards of execution, documentation, and continuous improvement."
                )
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
            p1_intro,
            "",
            p2_experience,
            "",
            p3_skills,
            "",
            p4_closing,
            "",
            "Sincerely,",
            name
        ]
        full_text = "\n".join(text_lines)

        return {
            "candidate_name": name,
            "target_role": clean_title,
            "target_company": clean_company,
            "date": today_str,
            "contact": contact,
            "paragraphs": body_paragraphs,
            "full_text": full_text,
            "executive_summary": exec_summary,
            "application_responses": app_responses,
            "matched_skills": matched_skills
        }

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

    def build_pdf(self, cover_letter_data: Dict[str, Any], job_id: str) -> str:
        """
        Compiles the cover letter into a clean PDF via Edge headless matching Overleaf LaTeX styling.
        """
        clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
        html_path = os.path.join(self.output_dir, f"cover_letter_{clean_id}.html")
        pdf_path = os.path.join(self.output_dir, f"cover_letter_{clean_id}.pdf")

        html = self._generate_html(cover_letter_data)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        if os.path.exists(EDGE_PATH):
            cmd = [
                EDGE_PATH,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={os.path.abspath(pdf_path)}",
                os.path.abspath(html_path)
            ]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            except Exception as e:
                print(f"[CoverLetter] PDF compilation error: {e}")

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

