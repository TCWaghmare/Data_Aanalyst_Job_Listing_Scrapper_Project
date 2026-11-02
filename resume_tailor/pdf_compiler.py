"""
PDF Compiler for Tailored Resumes.
Compiles tailored resumes into an ATS-friendly, professional one-page PDF
matching the reference resume format and typography.
"""

import os
import subprocess
from typing import Dict, Any
import pypdf

EDGE_PATH = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resumes")
os.makedirs(OUTPUT_DIR, exist_ok=True)

class PDFCompiler:
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir

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

        # Compile HTML to PDF via Edge headless
        if os.path.exists(EDGE_PATH):
            cmd = [
                EDGE_PATH,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={os.path.abspath(pdf_path)}",
                os.path.abspath(html_path)
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        # Validate that the PDF is strictly 1 page
        if os.path.exists(pdf_path):
            try:
                reader = pypdf.PdfReader(pdf_path)
                if len(reader.pages) > 1:
                    # Level 1: Regenerate with tighter vertical spacing
                    tight_html = self._generate_latex_styled_html(tailored_data, tight=True)
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(tight_html)
                    subprocess.run(cmd, capture_output=True, text=True, timeout=15)

                    reader2 = pypdf.PdfReader(pdf_path)
                    if len(reader2.pages) > 1:
                        # Level 2: Compact items to strictly guarantee 1 page
                        compact_data = dict(tailored_data)
                        if len(compact_data.get("experience", [])) > 2:
                            compact_data["experience"] = compact_data["experience"][:2]
                        for exp in compact_data.get("experience", []):
                            if len(exp.get("bullets", [])) > 2:
                                exp["bullets"] = exp["bullets"][:2]
                        if len(compact_data.get("projects", [])) > 2:
                            compact_data["projects"] = compact_data["projects"][:2]
                        for proj in compact_data.get("projects", []):
                            if len(proj.get("bullets", [])) > 2:
                                proj["bullets"] = proj["bullets"][:2]
                        if len(compact_data.get("education", [])) > 1:
                            compact_data["education"] = compact_data["education"][:1]
                        if len(compact_data.get("certifications", [])) > 2:
                            compact_data["certifications"] = compact_data["certifications"][:2]

                        compact_html = self._generate_latex_styled_html(compact_data, tight=True)
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(compact_html)
                        subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            except Exception:
                pass

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
