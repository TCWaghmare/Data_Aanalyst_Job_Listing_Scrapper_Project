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

        contact_parts = [p for p in [phone, email, linkedin, github] if p and "not available" not in str(p).lower()]
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
        tech_tools = data.get("technical_tools", [])
        if skills or tech_tools:
            y = draw_section_header("TECHNICAL SKILLS", y)
            if isinstance(skills, dict) and skills:
                for cat, items in list(skills.items())[:4]:
                    cat_name = cat.replace("_", " ").title()
                    line_str = f"{cat_name}: {', '.join(items[:8])}"
                    for line in self._wrap_text(line_str, 100):
                        ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(line)}) Tj ET")
                        y -= 11
            elif tech_tools:
                line_str = f"Core Competencies: {', '.join(tech_tools[:18])}"
                for line in self._wrap_text(line_str, 100):
                    ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(line)}) Tj ET")
                    y -= 11

        # 5. Work Experience
        experience = data.get("experience", [])
        if experience:
            y = draw_section_header("WORK EXPERIENCE", y)
            for exp in experience[:2]:
                title = exp.get("title", "Role")
                company = exp.get("company", "Company")
                dates = exp.get("dates", "")
                loc = exp.get("location", "")

                header_left = f"{title} - {company}"
                header_right = f"{dates} ({loc})" if loc else dates
                ops.append(f"BT /F1 9 Tf {left_x} {y} Td ({self._escape_pdf_text(header_left)}) Tj ET")
                ops.append(f"BT /F2 8.5 Tf {right_x - len(header_right)*5} {y} Td ({self._escape_pdf_text(header_right)}) Tj ET")
                y -= 11

                for b in exp.get("bullets", [])[:2]:
                    for idx, line in enumerate(self._wrap_text(b, 98)):
                        prefix = "* " if idx == 0 else "  "
                        ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(prefix + line)}) Tj ET")
                        y -= 11
                y -= 2

        # 6. Projects
        projects = data.get("projects", [])
        if projects:
            y = draw_section_header("KEY PROJECTS", y)
            for proj in projects[:2]:
                p_title = proj.get("title", "Project")
                tools = proj.get("tools", "")
                p_header = f"{p_title}" + (f" | {tools}" if tools else "")
                ops.append(f"BT /F1 9 Tf {left_x} {y} Td ({self._escape_pdf_text(p_header)}) Tj ET")
                y -= 11
                for b in proj.get("bullets", [])[:2]:
                    for idx, line in enumerate(self._wrap_text(b, 98)):
                        prefix = "* " if idx == 0 else "  "
                        ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(prefix + line)}) Tj ET")
                        y -= 11
                y -= 2

        # 7. Education
        education = data.get("education", [])
        if education:
            y = draw_section_header("EDUCATION", y)
            for edu in education[:2]:
                deg = edu.get("degree", "Degree")
                inst = edu.get("institution", "Institution")
                yr = edu.get("year", "")
                edu_left = f"{deg} - {inst}"
                ops.append(f"BT /F1 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(edu_left)}) Tj ET")
                if yr:
                    ops.append(f"BT /F2 8.5 Tf {right_x - len(str(yr))*6} {y} Td ({self._escape_pdf_text(str(yr))}) Tj ET")
                y -= 11

        # 8. Certifications
        certs = data.get("certifications", [])
        if certs:
            y = draw_section_header("CERTIFICATIONS", y)
            cert_names = [c.get("name") if isinstance(c, dict) else str(c) for c in certs[:4]]
            line_str = " | ".join(cert_names)
            for line in self._wrap_text(line_str, 100):
                ops.append(f"BT /F2 8.5 Tf {left_x} {y} Td ({self._escape_pdf_text(line)}) Tj ET")
                y -= 11

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
        name = data.get("name") or "Candidate Name"
        contact = data.get("contact", {})
        phone = contact.get("phone") or ""
        email = contact.get("email") or ""
        linkedin = contact.get("linkedin") or ""
        linkedin_url = contact.get("linkedin_url") or (f"https://{linkedin}" if linkedin else "")
        github = contact.get("github") or ""
        github_url = contact.get("github_url") or (f"https://{github}" if github else "")

        # Dynamic header links
        header_parts = []
        if phone and "not available" not in phone.lower():
            header_parts.append(phone)
        if email and "not available" not in email.lower():
            header_parts.append(f'<a href="mailto:{email}">{email}</a>')
        if linkedin:
            header_parts.append(f'<a href="{linkedin_url}">{linkedin}</a>')
        if github:
            header_parts.append(f'<a href="{github_url}">{github}</a>')
        header_links = " | ".join(header_parts) if header_parts else "Information Not Available in Uploaded Documents"

        summary = data.get("summary") or "Information Not Available in Uploaded Documents"

        # Calibrated strict 1-page spacing variables
        body_font = "8.7pt" if tight else "9.1pt"
        line_height = "1.26" if tight else "1.28"
        sec_margin_top = "6px" if tight else "7px"
        item_margin_bottom = "3px" if tight else "4px"

        # Experience HTML
        exp_html = ""
        exp_items = data.get("experience", [])
        if exp_items:
            for exp in exp_items:
                bullets = "".join([f"<li>{b}</li>" for b in exp.get("bullets", [])]) if exp.get("bullets") else "<li>Contributed to operational and technical deliverables.</li>"
                exp_html += f"""
                <div class="resume-item" style="margin-bottom: {item_margin_bottom};">
                  <div class="item-header">
                    <span class="item-title"><strong>{exp.get('title', 'Role')}</strong></span>
                    <span class="item-date">{exp.get('dates', '')}</span>
                  </div>
                  <div class="item-subheader">
                    <span class="item-org"><em>{exp.get('company', '')}</em></span>
                    <span class="item-loc"><em>{exp.get('location', '')}</em></span>
                  </div>
                  <ul class="bullets">
                    {bullets}
                  </ul>
                </div>
                """
        else:
            exp_html = '<div style="font-size: 8.5pt; font-style: italic; color: #555;">Information Not Available in Uploaded Documents</div>'

        # Projects HTML
        proj_html = ""
        proj_items = data.get("projects", [])
        if proj_items:
            for proj in proj_items:
                bullets = "".join([f"<li>{b}</li>" for b in proj.get("bullets", [])]) if proj.get("bullets") else "<li>Executed key project milestones.</li>"
                link_url = proj.get("link_url") or ""
                link_text = proj.get("link_text") or "View Project"
                link_html = f'<a href="{link_url}" style="text-decoration: underline; color: inherit;">{link_text}</a>' if link_url and link_url != "#" else ""
                tools_line = f'<div class="item-tools" style="margin-bottom: 2px;"><em>{proj.get("tools")}</em></div>' if proj.get("tools") else ""
                proj_html += f"""
                <div class="resume-item" style="margin-bottom: {item_margin_bottom};">
                  <div class="item-header">
                    <span class="item-title">
                      <strong>{proj.get('title', 'Project')}</strong>
                    </span>
                    <span class="item-date">{link_html}</span>
                  </div>
                  {tools_line}
                  <ul class="bullets">
                    {bullets}
                  </ul>
                </div>
                """
        else:
            proj_html = '<div style="font-size: 8.5pt; font-style: italic; color: #555;">Information Not Available in Uploaded Documents</div>'

        # Skills HTML
        skills = data.get("skills", {})
        skills_lines = []
        for cat_k, items in skills.items():
            if items:
                label = cat_k.replace("_", " ").title()
                skills_lines.append(f'<strong>{label}:</strong> {", ".join(items)}')
        if not skills_lines:
            all_t = data.get("technical_tools", [])
            if all_t:
                skills_lines.append(f'<strong>Technical Competencies:</strong> {", ".join(all_t)}')
            else:
                skills_lines.append('<em>Information Not Available in Uploaded Documents</em>')
        skills_html = "<br>".join(skills_lines)

        # Education HTML
        edu_html = ""
        for edu in data.get("education", []):
            edu_html += f"""
            <div class="resume-item" style="margin-bottom: 2px;">
              <div class="item-header">
                <span class="item-title"><strong>{edu.get('institution')}</strong></span>
                <span class="item-date">{edu.get('dates')}</span>
              </div>
              <div class="item-subheader">
                <span class="item-org"><em>{edu.get('degree')}</em></span>
              </div>
            </div>
            """

        # Certifications HTML
        cert_html = ""
        for cert in data.get("certifications", []):
            cert_html += f"""
            <div class="cert-item" style="display: flex; justify-content: space-between; margin-bottom: 1.5px;">
              <span>{cert.get('name')}</span>
              <a href="{cert.get('url', '#')}" style="text-decoration: underline; color: inherit;">{cert.get('link', 'Credential Link')}</a>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{name} - Resume</title>
  <style>
    @page {{
      size: letter;
      margin: 0.38in 0.45in 0.38in 0.45in;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: "Computer Modern Roman", "Latin Modern Roman", "Times New Roman", Times, serif;
      font-size: {body_font};
      line-height: {line_height};
      color: #000;
      background: #fff;
    }}
    .header {{
      text-align: center;
      margin-bottom: 5px;
    }}
    .header h1 {{
      font-size: 19pt;
      font-weight: normal;
      font-variant: small-caps;
      letter-spacing: 0.5px;
      margin-bottom: 2px;
    }}
    .header .contact {{
      font-size: 8.5pt;
      color: #111;
    }}
    .header .contact a {{
      color: #000;
      text-decoration: underline;
    }}
    .section {{
      margin-top: {sec_margin_top};
    }}
    .section-title {{
      font-size: 10.5pt;
      font-variant: small-caps;
      font-weight: bold;
      border-bottom: 1px solid #000;
      padding-bottom: 1px;
      margin-bottom: 3px;
      letter-spacing: 0.3px;
    }}
    .item-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 9pt;
    }}
    .item-subheader {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 8.7pt;
      margin-bottom: 1px;
    }}
    .item-tools {{
      font-size: 8.2pt;
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
    }}
    .skills-block {{
      font-size: 8.6pt;
      line-height: 1.28;
    }}
    .skills-row {{
      margin-bottom: 1px;
    }}
    .cert-item {{
      font-size: 8.6pt;
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>{name}</h1>
    <div class="contact">
      {header_links}
    </div>
  </div>

  <div class="section">
    <div class="section-title">Professional Summary</div>
    <div style="font-size: 8.7pt; text-align: justify; line-height: 1.28;">{summary}</div>
  </div>

  <div class="section">
    <div class="section-title">Professional Experience</div>
    {exp_html}
  </div>

  <div class="section">
    <div class="section-title">Projects</div>
    {proj_html}
  </div>

  <div class="section">
    <div class="section-title">Technical Skills</div>
    <div class="skills-block" style="font-size: 8.7pt; line-height: 1.35;">
      {skills_html}
    </div>
  </div>

  <div class="section">
    <div class="section-title">Education</div>
    {edu_html}
  </div>

  <div class="section">
    <div class="section-title">Certifications</div>
    {cert_html}
  </div>
</body>
</html>
"""

# Global compiler instance
pdf_compiler = PDFCompiler()
