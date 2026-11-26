"""
PDF Compiler for Tailored Resumes.
Compiles tailored resumes into an ATS-friendly, professional one-page PDF
matching the reference resume format and typography.
"""

import os
import io
import shutil
import subprocess
from typing import Dict, Any, List, Optional
import pypdf

def find_browser_executable() -> Optional[str]:
    """Finds available Edge, Chrome, or Chromium executable across Windows, Linux, and Mac."""
    candidates = [
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        os.path.expandvars("%LOCALAPPDATA%\\Microsoft\\Edge\\Application\\msedge.exe"),
        os.path.expandvars("%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe"),
    ]
    for name in ["msedge", "edge", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave", "chrome"]:
        p = shutil.which(name)
        if p:
            candidates.append(p)

    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

EDGE_PATH = find_browser_executable() or "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
OUTPUT_DIR = "/tmp/data/resumes" if is_serverless else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resumes")
try:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
except OSError:
    pass

class PDFCompiler:
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        try:
            if self.output_dir:
                os.makedirs(self.output_dir, exist_ok=True)
        except OSError:
            pass

    def _escape_pdf_text(self, text: str) -> str:
        if not text:
            return ""
        t = str(text).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        t = t.replace("–", "-").replace("—", "-").replace("•", "*").replace("\xa0", " ")
        t = t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return t

    def _wrap_text(self, text: str, max_chars: int = 95) -> List[str]:
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

    def _compile_pure_python_pdf(self, data: Dict[str, Any], pdf_path: str) -> str:
        """Pure-Python standard 1-page PDF generator that works in any environment without external browsers."""
        name = data.get("name") or "Candidate Name"
        contact = data.get("contact", {})
        phone = contact.get("phone") or ""
        email = contact.get("email") or ""
        linkedin = contact.get("linkedin") or ""
        github = contact.get("github") or ""
        portfolio = contact.get("portfolio") or "tejaswaghmare.me"

        contact_parts = [p for p in [phone, email, linkedin, github, portfolio] if p and "not available" not in str(p).lower()]
        contact_line = " | ".join(contact_parts)

        ops = []
        y = 756
        left_x = 36
        right_x = 576

        # 1. Name Header
        ops.append(f"BT /F1 15 Tf {left_x} {y} Td ({self._escape_pdf_text(name)}) Tj ET")
        y -= 15

        # 2. Contact Line
        if contact_line:
            ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(contact_line)}) Tj ET")
            y -= 14

        def draw_section_header(title: str, cur_y: float) -> float:
            cur_y -= 8
            ops.append(f"BT /F1 10 Tf {left_x} {cur_y} Td ({self._escape_pdf_text(title)}) Tj ET")
            line_y = cur_y - 2
            ops.append(f"0.75 w {left_x} {line_y} m {right_x} {line_y} l S")
            return cur_y - 12

        # 3. Professional Summary
        summary = data.get("summary") or ""
        if summary and "not available" not in summary.lower():
            y = draw_section_header("PROFESSIONAL SUMMARY", y)
            for line in self._wrap_text(summary, 102):
                ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(line)}) Tj ET")
                y -= 11

        # 4. Technical Skills
        skills = data.get("skills", {})
        skills_lines_data = data.get("skills_lines", [])
        tech_tools = data.get("technical_tools", [])
        if skills or skills_lines_data or tech_tools:
            y = draw_section_header("TECHNICAL SKILLS", y)
            if skills_lines_data:
                for sl in skills_lines_data[:6]:
                    cat = sl.get("category", "Skills")
                    content = sl.get("content", "")
                    line_str = f"{cat}: {content}"
                    for line in self._wrap_text(line_str, 100):
                        ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(line)}) Tj ET")
                        y -= 10.5
            elif isinstance(skills, dict) and skills:
                cat_display = {
                    "bi_visualization": "BI & Visualization",
                    "databases_sql": "Databases & SQL",
                    "analytics_statistics": "Analytics & Statistics",
                    "programming": "Programming",
                    "data_engineering": "Data Engineering",
                    "ai_tools": "AI & Tools"
                }
                for cat, items in list(skills.items())[:6]:
                    cat_name = cat_display.get(cat, cat.replace("_", " ").title())
                    line_str = f"{cat_name}: {', '.join(items) if isinstance(items, list) else items}"
                    for line in self._wrap_text(line_str, 100):
                        ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(line)}) Tj ET")
                        y -= 10.5
            elif tech_tools:
                line_str = f"Core Competencies: {', '.join(tech_tools[:18])}"
                for line in self._wrap_text(line_str, 100):
                    ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(line)}) Tj ET")
                    y -= 10.5

        # 5. Projects
        projects = data.get("projects", [])
        if projects:
            y = draw_section_header("PROJECTS", y)
            for proj in projects[:3]:
                p_title = proj.get("title", "Project")
                tools = proj.get("tools", "")
                link_text = proj.get("link_text") or "GitHub"
                p_header = f"{p_title}" + (f" | {tools}" if tools else "")
                ops.append(f"BT /F1 9 Tf {left_x} {y} Td ({self._escape_pdf_text(p_header[:75])}) Tj ET")
                ops.append(f"BT /F2 8.2 Tf {right_x - len(link_text)*5} {y} Td ({self._escape_pdf_text(link_text)}) Tj ET")
                y -= 10.5
                for b in proj.get("bullets", [])[:2]:
                    for idx, line in enumerate(self._wrap_text(b, 98)):
                        prefix = "* " if idx == 0 else "  "
                        ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(prefix + line)}) Tj ET")
                        y -= 10.5
                y -= 1

        # 6. Experience
        experience = data.get("experience", [])
        if experience:
            y = draw_section_header("EXPERIENCE", y)
            for exp in experience[:3]:
                title = exp.get("title", "Role")
                company = exp.get("company", "Company")
                dates = exp.get("dates", "").replace("--", "–")

                header_left = f"{title} | {company}"
                header_right = f"{dates}"
                ops.append(f"BT /F1 9 Tf {left_x} {y} Td ({self._escape_pdf_text(header_left[:75])}) Tj ET")
                ops.append(f"BT /F2 8.5 Tf {right_x - len(header_right)*5} {y} Td ({self._escape_pdf_text(header_right)}) Tj ET")
                y -= 10.5

                for b in exp.get("bullets", [])[:2]:
                    for idx, line in enumerate(self._wrap_text(b, 98)):
                        prefix = "* " if idx == 0 else "  "
                        ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(prefix + line)}) Tj ET")
                        y -= 10.5
                y -= 1

        # 7. Certifications
        certs = data.get("certifications", [])
        if certs:
            y = draw_section_header("CERTIFICATIONS", y)
            for c in certs[:3]:
                c_name = c.get("name") if isinstance(c, dict) else str(c)
                ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(c_name[:85])}) Tj ET")
                ops.append(f"BT /F2 8.2 Tf {right_x - 25} {y} Td (Link) Tj ET")
                y -= 10.5

        # 8. Achievements
        achievements = data.get("achievements", [])
        if achievements:
            y = draw_section_header("ACHIEVEMENTS", y)
            for a in achievements[:1]:
                a_title = a.get("title", "") if isinstance(a, dict) else str(a)
                a_desc = a.get("description", "") if isinstance(a, dict) else ""
                full_a = f"{a_title}: {a_desc}" if a_title and a_desc and a_title not in a_desc else (a_desc or a_title)
                for idx, line in enumerate(self._wrap_text(full_a, 98)):
                    prefix = "* " if idx == 0 else "  "
                    ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(prefix + line)}) Tj ET")
                    y -= 10.5

        # 9. Education
        education = data.get("education", [])
        if education:
            y = draw_section_header("EDUCATION", y)
            for edu in education[:2]:
                deg = edu.get("degree", "Degree")
                inst = edu.get("institution", "Institution")
                yr = edu.get("dates") or edu.get("year", "")
                edu_left = f"{deg} | {inst}"
                ops.append(f"BT /F1 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(edu_left[:80])}) Tj ET")
                if yr:
                    ops.append(f"BT /F2 8.5 Tf {right_x - len(str(yr))*5} {y} Td ({self._escape_pdf_text(str(yr))}) Tj ET")
                y -= 10.5

        # Assemble PDF stream
        stream_content = "\n".join(ops).encode('latin1', errors='replace')
        objects = [
            b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R /F3 7 0 R >> >> >>',
            b'<< /Length ' + str(len(stream_content)).encode('ascii') + b' >>\nstream\n' + stream_content + b'\nendstream',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>'
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

        return os.path.abspath(pdf_path)

    def compile(self, tailored_data: Dict[str, Any], job_id: str) -> str:
        """
        Compiles the tailored resume into an exact 1-page PDF.
        Returns the absolute path to the generated PDF.
        """
        clean_job_id = "".join([c if c.isalnum() else "_" for c in job_id])
        html_path = os.path.join(self.output_dir, f"tailored_{clean_job_id}.html")
        pdf_path = os.path.join(self.output_dir, f"tailored_{clean_job_id}.pdf")

        # Generate HTML template styled like LaTeX Jake's Resume
        html_content = self._generate_latex_styled_html(tailored_data)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Attempt browser headless compilation if executable is available
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
            except Exception:
                pass

        # If headless browser is absent or didn't produce the PDF, use pure Python builder
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            self._compile_pure_python_pdf(tailored_data, pdf_path)

        # Validate that the PDF is strictly 1 page
        if os.path.exists(pdf_path):
            try:
                reader = pypdf.PdfReader(pdf_path)
                if len(reader.pages) > 1 and browser_exe:
                    # Regenerate with tighter vertical spacing
                    tight_html = self._generate_latex_styled_html(tailored_data, tight=True)
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(tight_html)
                    cmd = [
                        browser_exe,
                        "--headless=new",
                        "--disable-gpu",
                        "--no-pdf-header-footer",
                        f"--print-to-pdf={os.path.abspath(pdf_path)}",
                        os.path.abspath(html_path)
                    ]
                    subprocess.run(cmd, capture_output=True, text=True, timeout=15)

                    reader2 = pypdf.PdfReader(pdf_path)
                    if len(reader2.pages) > 1:
                        # Fallback to pure Python exact 1-page generator
                        self._compile_pure_python_pdf(tailored_data, pdf_path)
            except Exception:
                pass

        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            self._compile_pure_python_pdf(tailored_data, pdf_path)

        return os.path.abspath(pdf_path)

    def _generate_latex_styled_html(self, data: Dict[str, Any], tight: bool = False) -> str:
        name = data.get("name") or "Tejas C. Waghmare"
        target_role = data.get("target_job_title") or "Data Analyst"
        contact = data.get("contact", {})
        phone = contact.get("phone") or "+91 83788 69006"
        email = contact.get("email") or "tejaswaghmare900@gmail.com"
        location = contact.get("location") or "Pune, Maharashtra"
        linkedin = contact.get("linkedin") or "linkedin.com/in/tejascwaghmare"
        linkedin_url = contact.get("linkedin_url") or f"https://{linkedin}"
        github = contact.get("github") or "github.com/TCWaghmare"
        github_url = contact.get("github_url") or f"https://{github}"
        portfolio = contact.get("portfolio") or "tejaswaghmare.me"
        portfolio_url = contact.get("portfolio_url") or "https://www.tejaswaghmare.me/"

        # Contact Line 1: Phone, Email, Location
        c1_parts = []
        if phone:
            c1_parts.append(f'<i class="fas fa-phone"></i> {phone}')
        if email:
            c1_parts.append(f'<a href="mailto:{email}" style="color: #0B5CD5; text-decoration: underline;"><i class="fas fa-envelope"></i> {email}</a>')
        if location:
            c1_parts.append(f'<i class="fas fa-map-marker-alt"></i> {location}')
        contact_line_1 = " | ".join(c1_parts)

        # Contact Line 2: LinkedIn, Portfolio, GitHub
        c2_parts = []
        if linkedin:
            c2_parts.append(f'<a href="{linkedin_url}" target="_blank" style="color: #0B5CD5; text-decoration: underline;"><i class="fab fa-linkedin"></i> {linkedin}</a>')
        if portfolio and portfolio_url:
            c2_parts.append(f'<a href="{portfolio_url}" target="_blank" style="color: #0B5CD5; text-decoration: underline;"><i class="fas fa-globe"></i> {portfolio}</a>')
        if github:
            c2_parts.append(f'<a href="{github_url}" target="_blank" style="color: #0B5CD5; text-decoration: underline;"><i class="fab fa-github"></i> {github}</a>')
        contact_line_2 = " | ".join(c2_parts)

        summary = data.get("summary") or ""

        # Calibrated strict 1-page spacing variables
        body_font = "8.6pt" if tight else "9.0pt"
        line_height = "1.25" if tight else "1.28"
        sec_margin_top = "4px" if tight else "5px"
        item_margin_bottom = "2.0px" if tight else "3.0px"

        # Technical Skills HTML
        skills_dict = data.get("skills", {})
        skills_lines_data = data.get("skills_lines", [])
        skills_lines_html = []

        if skills_lines_data:
            for sl in skills_lines_data:
                cat = sl.get("category", "Skills")
                content = sl.get("content", "")
                skills_lines_html.append(f'<div class="skills-row"><strong>{cat}:</strong> {content}</div>')
        elif skills_dict:
            cat_display_map = {
                "bi_visualization": "BI & Visualization",
                "databases_sql": "Databases & SQL",
                "analytics_statistics": "Analytics & Statistics",
                "programming": "Programming",
                "data_engineering": "Data Engineering",
                "ai_tools": "AI & Tools",
                "data_analytics": "Data Analytics",
                "cloud_database": "Cloud & Database",
                "machine_learning": "Machine Learning",
                "domains": "Domains",
                "tools_workflows": "Tools & Workflows"
            }
            for cat_key, items in skills_dict.items():
                if not items:
                    continue
                label = cat_display_map.get(cat_key, cat_key.replace("_", " ").title())
                items_str = ", ".join(items) if isinstance(items, list) else str(items)
                skills_lines_html.append(f'<div class="skills-row"><strong>{label}:</strong> {items_str}</div>')
        else:
            all_t = data.get("technical_tools", [])
            if all_t:
                skills_lines_html.append(f'<div class="skills-row"><strong>Technical Competencies:</strong> {", ".join(all_t)}</div>')

        skills_html = "".join(skills_lines_html)

        # Projects HTML
        proj_html = ""
        proj_items = data.get("projects", [])
        for proj in proj_items:
            bullets = "".join([f"<li>{b}</li>" for b in proj.get("bullets", [])]) if proj.get("bullets") else "<li>Executed key project milestones.</li>"
            link_url = proj.get("link_url") or "https://github.com/TCWaghmare"
            link_text = proj.get("link_text") or "GitHub"
            link_html = f'<a href="{link_url}" target="_blank" style="color: #0B5CD5; text-decoration: underline; font-size: 8.5pt;">{link_text}</a>'
            tools_str = f" | <em>{proj.get('tools')}</em>" if proj.get("tools") else ""
            proj_html += f"""
            <div class="resume-item" style="margin-bottom: {item_margin_bottom};">
              <div class="item-header">
                <span class="item-title">
                  <strong>{proj.get('title', 'Project')}</strong>{tools_str}
                </span>
                <span class="item-link">{link_html}</span>
              </div>
              <ul class="bullets">
                {bullets}
              </ul>
            </div>
            """

        # Experience HTML
        exp_html = ""
        exp_items = data.get("experience", [])
        for exp in exp_items:
            bullets = "".join([f"<li>{b}</li>" for b in exp.get("bullets", [])]) if exp.get("bullets") else "<li>Contributed to operational and technical deliverables.</li>"
            dates = exp.get("dates", "").replace("--", "–")
            exp_html += f"""
            <div class="resume-item" style="margin-bottom: {item_margin_bottom};">
              <div class="item-header">
                <span class="item-title"><strong>{exp.get('title', 'Role')}</strong> | <em>{exp.get('company', '')}</em></span>
                <span class="item-date"><em>{dates}</em></span>
              </div>
              <ul class="bullets">
                {bullets}
              </ul>
            </div>
            """

        # Certifications HTML
        cert_html = ""
        for cert in data.get("certifications", []):
            c_name = cert.get("name") if isinstance(cert, dict) else str(cert)
            c_url = cert.get("url", "") if isinstance(cert, dict) else ""
            link_tag = f'<a href="{c_url}" target="_blank" style="color: #0B5CD5; text-decoration: underline;">Link</a>' if c_url and c_url != "#" else "<span>Link</span>"
            cert_html += f"""
            <div class="cert-item" style="display: flex; justify-content: space-between; margin-bottom: 1px; font-size: 8.6pt;">
              <span>{c_name}</span>
              {link_tag}
            </div>
            """

        # Achievements HTML
        ach_html = ""
        ach_items = data.get("achievements", [])
        if not ach_items:
            ach_items = [{
                "title": "McKinsey.org Forward Program (2026)",
                "description": "Strengthened structured problem-solving, critical thinking, communication, and analytical decision-making, with exposure to digital and AI essentials."
            }]
        for ach in ach_items:
            if isinstance(ach, dict):
                a_title = ach.get("title", "")
                a_desc = ach.get("description", "")
                if a_title and a_desc and a_title not in a_desc:
                    item_text = f"<strong>{a_title}:</strong> {a_desc}"
                else:
                    item_text = a_desc or a_title
            else:
                item_text = str(ach)
            ach_html += f'<li style="font-size: 8.6pt; line-height: 1.25; margin-bottom: 1px;">{item_text}</li>'

        # Education HTML
        edu_html = ""
        edu_items = data.get("education", [])
        if not edu_items:
            edu_items = [
                {"degree": "B.Tech, Mechanical Engineering (CGPA: 8.04/10)", "institution": "Bajaj Institute of Technology, Wardha", "dates": "2020 – 2024"},
                {"degree": "HSC (Information Technology), 66.62% | SSC, 81.80%", "institution": "Maharashtra State Board", "dates": "2018 – 2020"}
            ]
        for edu in edu_items:
            dates = edu.get("dates", "").replace("--", "–")
            edu_html += f"""
            <div class="edu-item" style="display: flex; justify-content: space-between; font-size: 8.7pt; margin-bottom: 1.5px;">
              <span><strong>{edu.get('degree')}</strong> | {edu.get('institution')}</span>
              <span><em>{dates}</em></span>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{name} - Resume</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
  <link rel="stylesheet" href="https://fonts.cdnfonts.com/css/computer-modern">
  <style>
    @page {{
      size: a4;
      margin: 0.30in 0.50in 0.25in 0.50in;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: 'CMU Serif', 'Computer Modern Roman', 'Latin Modern Roman', 'Times New Roman', Times, serif;
      font-size: {body_font};
      line-height: {line_height};
      color: #000;
      background: #fff;
    }}
    a {{
      color: #0B5CD5;
      text-decoration: underline;
    }}
    .header {{
      text-align: center;
      margin-bottom: 4px;
    }}
    .header h1 {{
      font-size: 21pt;
      font-weight: bold;
      letter-spacing: 0.3px;
      margin-bottom: 1px;
      color: #000;
    }}
    .header .subtitle {{
      font-size: 12.5pt;
      font-weight: bold;
      margin-bottom: 3px;
      color: #111;
    }}
    .header .contact {{
      font-size: 8.4pt;
      color: #222;
      line-height: 1.35;
    }}
    .section {{
      margin-top: {sec_margin_top};
    }}
    .section-title {{
      font-size: 10.5pt;
      font-variant: small-caps;
      font-weight: bold;
      border-bottom: 0.5pt solid #000;
      padding-bottom: 1px;
      margin-bottom: 3px;
      letter-spacing: 0.4px;
    }}
    .item-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 8.9pt;
      margin-bottom: 1px;
    }}
    .bullets {{
      margin-left: 15px;
      list-style-type: disc;
    }}
    .bullets li {{
      font-size: 8.6pt;
      margin-bottom: 1px;
      line-height: 1.25;
      text-align: justify;
    }}
    .skills-block {{
      font-size: 8.6pt;
      line-height: 1.28;
    }}
    .skills-row {{
      margin-bottom: 1px;
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>{name}</h1>
    <div class="subtitle">{target_role}</div>
    <div class="contact">
      {contact_line_1}<br>
      {contact_line_2}
    </div>
  </div>

  <div class="section">
    <div class="section-title">Professional Summary</div>
    <div style="font-size: 8.7pt; text-align: justify; line-height: 1.28;">{summary}</div>
  </div>

  <div class="section">
    <div class="section-title">Technical Skills</div>
    <div class="skills-block">
      {skills_html}
    </div>
  </div>

  <div class="section">
    <div class="section-title">Projects</div>
    {proj_html}
  </div>

  <div class="section">
    <div class="section-title">Experience</div>
    {exp_html}
  </div>

  <div class="section">
    <div class="section-title">Certifications</div>
    {cert_html}
  </div>

  <div class="section">
    <div class="section-title">Achievements</div>
    <ul class="bullets">
      {ach_html}
    </ul>
  </div>

  <div class="section">
    <div class="section-title">Education</div>
    {edu_html}
  </div>
</body>
</html>
"""

# Global compiler instance
pdf_compiler = PDFCompiler()
