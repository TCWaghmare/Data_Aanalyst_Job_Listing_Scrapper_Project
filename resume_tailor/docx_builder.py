"""
DOCX Builder for Tailored Resumes.
Generates fully editable Microsoft Word (.docx) documents matching the professional
LaTeX reference resume styling (Jake's Resume layout) with clean typography, borders,
and cross-platform compatibility (Microsoft Word, Google Docs, LibreOffice).
"""

import os
from typing import Dict, Any, List
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
OUTPUT_DIR = "/tmp/data/resumes" if is_serverless else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resumes")
try:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
except OSError:
    pass

# Monochrome Overleaf / LaTeX Styling (Jake's Resume Theme)
FONT_SERIF = "Times New Roman"
COLOR_BLACK = RGBColor(0, 0, 0)
COLOR_DARK = RGBColor(20, 20, 20)
COLOR_MUTED = RGBColor(60, 60, 60)

class DocxBuilder:
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        try:
            if self.output_dir:
                os.makedirs(self.output_dir, exist_ok=True)
        except OSError:
            pass

    def build_docx(self, data: Dict[str, Any], job_id: str) -> str:
        """
        Builds a professionally formatted .docx file from tailored resume data
        matching the Overleaf LaTeX Jake's Resume style (Image 2).
        Returns the absolute path to the generated .docx file.
        """
        clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
        file_path = os.path.join(self.output_dir, f"tailored_{clean_id}.docx")

        doc = Document()

        # Set tight professional margins (0.45 in) to match 1-page geometry
        for section in doc.sections:
            section.top_margin = Inches(0.42)
            section.bottom_margin = Inches(0.42)
            section.left_margin = Inches(0.45)
            section.right_margin = Inches(0.45)
            section.header_distance = Inches(0.2)
            section.footer_distance = Inches(0.2)

        name = data.get("name", "Candidate Name")
        contact = data.get("contact", {})
        summary = data.get("summary", "")
        experience = data.get("experience", [])
        projects = data.get("projects", [])
        skills = data.get("skills", {})
        education = data.get("education", [])
        certifications = data.get("certifications", [])

        # 1. Header: Candidate Name
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_name.paragraph_format.space_before = Pt(0)
        p_name.paragraph_format.space_after = Pt(2)
        r_name = p_name.add_run(name.upper())
        r_name.font.name = FONT_SERIF
        r_name.font.size = Pt(17)
        r_name.font.bold = True
        r_name.font.color.rgb = COLOR_BLACK

        # 2. Contact details line
        p_contact = doc.add_paragraph()
        p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_contact.paragraph_format.space_before = Pt(0)
        p_contact.paragraph_format.space_after = Pt(4)

        contact_entries = []
        if contact.get("phone"):
            contact_entries.append((contact["phone"], None))
        if contact.get("email"):
            contact_entries.append((contact["email"], f"mailto:{contact['email']}"))
        if contact.get("linkedin"):
            clean_li = contact["linkedin"].replace("https://", "").replace("www.", "")
            li_url = contact.get("linkedin_url") or f"https://{contact['linkedin']}"
            contact_entries.append((clean_li, li_url))
        if contact.get("github"):
            clean_gh = contact["github"].replace("https://", "").replace("www.", "")
            gh_url = contact.get("github_url") or f"https://{contact['github']}"
            contact_entries.append((clean_gh, gh_url))
        portfolio = contact.get("portfolio") or "tejaswaghmare.me"
        portfolio_url = contact.get("portfolio_url") or "https://www.tejaswaghmare.me/"
        if portfolio and portfolio_url:
            clean_port = portfolio.replace("https://", "").replace("www.", "")
            contact_entries.append((clean_port, portfolio_url))

        for idx, (disp_text, link_url) in enumerate(contact_entries):
            if idx > 0:
                r_sep = p_contact.add_run("  |  ")
                r_sep.font.name = FONT_SERIF
                r_sep.font.size = Pt(8.5)
                r_sep.font.color.rgb = COLOR_MUTED
            if link_url:
                self._add_hyperlink(p_contact, link_url, disp_text, font_size_pt=8.5, underline=True)
            else:
                r_c = p_contact.add_run(disp_text)
                r_c.font.name = FONT_SERIF
                r_c.font.size = Pt(8.5)
                r_c.font.color.rgb = COLOR_DARK

        # 3. Professional Summary
        if summary:
            self._add_heading(doc, "Professional Summary")
            p_sum = doc.add_paragraph()
            p_sum.paragraph_format.space_before = Pt(1)
            p_sum.paragraph_format.space_after = Pt(3)
            p_sum.paragraph_format.line_spacing = 1.15
            r_sum = p_sum.add_run(summary)
            r_sum.font.name = FONT_SERIF
            r_sum.font.size = Pt(9)
            r_sum.font.color.rgb = COLOR_DARK

        # 4. Professional Experience
        if experience:
            self._add_heading(doc, "Professional Experience")
            for exp in experience:
                # 2-column borderless table for title (left) and dates (right)
                table = doc.add_table(rows=2, cols=2)
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                self._remove_table_borders(table)
                table.autofit = False

                # Row 0: Title & Dates
                cell_00 = table.cell(0, 0)
                cell_01 = table.cell(0, 1)
                cell_00.width = Inches(5.2)
                cell_01.width = Inches(2.3)

                p00 = cell_00.paragraphs[0]
                p00.paragraph_format.space_before = Pt(2)
                p00.paragraph_format.space_after = Pt(0)
                r00 = p00.add_run(exp.get("title", ""))
                r00.font.name = FONT_SERIF
                r00.font.size = Pt(9.5)
                r00.font.bold = True
                r00.font.color.rgb = COLOR_BLACK

                p01 = cell_01.paragraphs[0]
                p01.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p01.paragraph_format.space_before = Pt(2)
                p01.paragraph_format.space_after = Pt(0)
                r01 = p01.add_run(exp.get("dates") or exp.get("period", ""))
                r01.font.name = FONT_SERIF
                r01.font.size = Pt(8.5)
                r01.font.color.rgb = COLOR_MUTED

                # Row 1: Company & Location
                cell_10 = table.cell(1, 0)
                cell_11 = table.cell(1, 1)
                cell_10.width = Inches(5.2)
                cell_11.width = Inches(2.3)

                p10 = cell_10.paragraphs[0]
                p10.paragraph_format.space_before = Pt(0)
                p10.paragraph_format.space_after = Pt(1)
                r10 = p10.add_run(exp.get("company", ""))
                r10.font.name = FONT_SERIF
                r10.font.size = Pt(9)
                r10.font.italic = True
                r10.font.color.rgb = COLOR_DARK

                p11 = cell_11.paragraphs[0]
                p11.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p11.paragraph_format.space_before = Pt(0)
                p11.paragraph_format.space_after = Pt(1)
                r11 = p11.add_run(exp.get("location", ""))
                r11.font.name = FONT_SERIF
                r11.font.size = Pt(8.5)
                r11.font.italic = True
                r11.font.color.rgb = COLOR_MUTED

                # Bullets
                for bullet in exp.get("bullets", []):
                    p_b = doc.add_paragraph(style="List Bullet")
                    p_b.paragraph_format.space_before = Pt(0)
                    p_b.paragraph_format.space_after = Pt(1)
                    p_b.paragraph_format.line_spacing = 1.12
                    r_b = p_b.add_run(bullet)
                    r_b.font.name = FONT_SERIF
                    r_b.font.size = Pt(8.5)
                    r_b.font.color.rgb = COLOR_DARK

        # 5. Projects
        if projects:
            self._add_heading(doc, "Projects")
            for proj in projects:
                table = doc.add_table(rows=1, cols=2)
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                self._remove_table_borders(table)
                table.autofit = False

                c0 = table.cell(0, 0)
                c1 = table.cell(0, 1)
                c0.width = Inches(5.8)
                c1.width = Inches(1.7)

                p0 = c0.paragraphs[0]
                p0.paragraph_format.space_before = Pt(2)
                p0.paragraph_format.space_after = Pt(0)
                r_title = p0.add_run(proj.get("title") or proj.get("name", ""))
                r_title.font.name = FONT_SERIF
                r_title.font.size = Pt(9.5)
                r_title.font.bold = True
                r_title.font.color.rgb = COLOR_BLACK

                tools = proj.get("tools") or proj.get("tech_stack", "")
                if tools:
                    r_pipe = p0.add_run("  |  ")
                    r_pipe.font.name = FONT_SERIF
                    r_pipe.font.size = Pt(8.5)
                    r_pipe.font.color.rgb = COLOR_MUTED

                    r_tools = p0.add_run(tools)
                    r_tools.font.name = FONT_SERIF
                    r_tools.font.size = Pt(8.5)
                    r_tools.font.italic = True
                    r_tools.font.color.rgb = COLOR_DARK

                p1 = c1.paragraphs[0]
                p1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p1.paragraph_format.space_before = Pt(2)
                p1.paragraph_format.space_after = Pt(0)
                link_url = proj.get("link_url") or "#"
                link_text = proj.get("link_text", "View Project")
                if link_url and link_url != "#":
                    self._add_hyperlink(p1, link_url, link_text, font_size_pt=8.5, underline=True)
                else:
                    r_link = p1.add_run(link_text)
                    r_link.font.name = FONT_SERIF
                    r_link.font.size = Pt(8.5)
                    r_link.font.underline = True
                    r_link.font.color.rgb = COLOR_BLACK

                for bullet in proj.get("bullets", []):
                    p_b = doc.add_paragraph(style="List Bullet")
                    p_b.paragraph_format.space_before = Pt(0)
                    p_b.paragraph_format.space_after = Pt(1)
                    p_b.paragraph_format.line_spacing = 1.12
                    r_b = p_b.add_run(bullet)
                    r_b.font.name = FONT_SERIF
                    r_b.font.size = Pt(8.5)
                    r_b.font.color.rgb = COLOR_DARK

        # 6. Technical Skills
        if skills:
            self._add_heading(doc, "Technical Skills")
            cat_labels = {
                "bi_visualization": "BI & Visualization",
                "data_analytics": "Data Analytics",
                "programming": "Programming",
                "machine_learning": "Machine Learning",
                "domains": "Domains",
                "tools_workflows": "Tools & Workflows",
                "languages": "Languages",
                "bi_tools": "BI Tools",
                "databases": "Databases",
                "frameworks_and_tools": "Frameworks & Tools",
                "core_competencies": "Core Competencies"
            }

            for cat_key, items in skills.items():
                if not items:
                    continue
                label = cat_labels.get(cat_key, cat_key.replace("_", " ").title())
                p_skill = doc.add_paragraph()
                p_skill.paragraph_format.space_before = Pt(0)
                p_skill.paragraph_format.space_after = Pt(1.5)
                p_skill.paragraph_format.line_spacing = 1.12

                r_lbl = p_skill.add_run(f"{label}: ")
                r_lbl.font.name = FONT_SERIF
                r_lbl.font.size = Pt(8.5)
                r_lbl.font.bold = True
                r_lbl.font.color.rgb = COLOR_BLACK

                items_text = ", ".join(items) if isinstance(items, list) else str(items)
                r_val = p_skill.add_run(items_text)
                r_val.font.name = FONT_SERIF
                r_val.font.size = Pt(8.5)
                r_val.font.color.rgb = COLOR_DARK

        # 7. Education
        if education:
            self._add_heading(doc, "Education")
            for edu in education:
                table = doc.add_table(rows=1, cols=2)
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                self._remove_table_borders(table)
                table.autofit = False

                c0 = table.cell(0, 0)
                c1 = table.cell(0, 1)
                c0.width = Inches(5.8)
                c1.width = Inches(1.7)

                p0 = c0.paragraphs[0]
                p0.paragraph_format.space_before = Pt(1)
                p0.paragraph_format.space_after = Pt(0)
                r0 = p0.add_run(edu.get("institution", ""))
                r0.font.name = FONT_SERIF
                r0.font.size = Pt(9)
                r0.font.bold = True
                r0.font.color.rgb = COLOR_BLACK

                p1 = c1.paragraphs[0]
                p1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p1.paragraph_format.space_before = Pt(1)
                p1.paragraph_format.space_after = Pt(0)
                r1 = p1.add_run(edu.get("dates") or edu.get("year", ""))
                r1.font.name = FONT_SERIF
                r1.font.size = Pt(8.5)
                r1.font.color.rgb = COLOR_MUTED

                degree = edu.get("degree", "")
                if degree:
                    p_deg = doc.add_paragraph()
                    p_deg.paragraph_format.space_before = Pt(0)
                    p_deg.paragraph_format.space_after = Pt(2)
                    r_deg = p_deg.add_run(degree)
                    r_deg.font.name = FONT_SERIF
                    r_deg.font.size = Pt(8.5)
                    r_deg.font.italic = True
                    r_deg.font.color.rgb = COLOR_DARK

        # 8. Certifications
        if certifications:
            self._add_heading(doc, "Certifications")
            for cert in certifications:
                p_c = doc.add_paragraph(style="List Bullet")
                p_c.paragraph_format.space_before = Pt(0)
                p_c.paragraph_format.space_after = Pt(1)
                c_name = cert.get("name") if isinstance(cert, dict) else str(cert)
                r_c = p_c.add_run(c_name)
                r_c.font.name = FONT_SERIF
                r_c.font.size = Pt(8.5)
                r_c.font.color.rgb = COLOR_DARK

                if isinstance(cert, dict) and cert.get("link"):
                    r_sp = p_c.add_run("  —  ")
                    r_sp.font.name = FONT_SERIF
                    r_sp.font.size = Pt(8)
                    r_sp.font.color.rgb = COLOR_MUTED

                    c_url = cert.get("url") or "#"
                    c_link = cert.get("link", "Credential Link")
                    if c_url and c_url != "#":
                        self._add_hyperlink(p_c, c_url, c_link, font_size_pt=8, underline=True)
                    else:
                        r_clink = p_c.add_run(c_link)
                        r_clink.font.name = FONT_SERIF
                        r_clink.font.size = Pt(8)
                        r_clink.font.underline = True
                        r_clink.font.color.rgb = COLOR_BLACK

        # Save document
        doc.save(file_path)
        return os.path.abspath(file_path)

    def _add_hyperlink(self, paragraph, url: str, text: str, font_name: str = FONT_SERIF, font_size_pt: float = 8.5, is_bold: bool = False, is_italic: bool = False, underline: bool = True, color_rgb: RGBColor = COLOR_BLACK):
        """Adds a clickable hyperlink to a python-docx paragraph."""
        if not url or url == "#":
            run = paragraph.add_run(text)
            run.font.name = font_name
            run.font.size = Pt(font_size_pt)
            run.font.bold = is_bold
            run.font.italic = is_italic
            run.font.underline = underline
            run.font.color.rgb = color_rgb
            return run

        try:
            part = paragraph.part
            r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
            hyperlink = parse_xml(f'<w:hyperlink xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="{r_id}"/>')
            rPr_parts = [
                f'<w:rFonts w:ascii="{font_name}" w:hAnsi="{font_name}"/>',
                f'<w:sz w:val="{int(font_size_pt * 2)}"/>',
                '<w:color w:val="000000"/>'
            ]
            if is_bold:
                rPr_parts.append('<w:b/>')
            if is_italic:
                rPr_parts.append('<w:i/>')
            if underline:
                rPr_parts.append('<w:u w:val="single"/>')
            rPr_str = "".join(rPr_parts)
            r_xml = f'<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:rPr>{rPr_str}</w:rPr><w:t>{text}</w:t></w:r>'
            r = parse_xml(r_xml)
            hyperlink.append(r)
            paragraph._p.append(hyperlink)
        except Exception:
            run = paragraph.add_run(text)
            run.font.name = font_name
            run.font.size = Pt(font_size_pt)
            run.font.bold = is_bold
            run.font.italic = is_italic
            run.font.underline = underline
            run.font.color.rgb = color_rgb

    def _add_heading(self, doc: Document, title: str):
        """Adds a professional small-caps heading with an underline/bottom border matching Overleaf."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(5)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True

        run = p.add_run(title.upper())
        run.font.name = FONT_SERIF
        run.font.size = Pt(10)
        run.font.bold = True
        run.font.color.rgb = COLOR_BLACK

        # Add horizontal bottom border to paragraph
        pPr = p._p.get_or_add_pPr()
        pBdr = parse_xml(
            r'<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            r'<w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/>'
            r'</w:pBdr>'
        )
        pPr.append(pBdr)

    def _remove_table_borders(self, table):
        """Removes all borders from a table for seamless two-column layout."""
        tblPr = table._tbl.tblPr
        tblBorders = parse_xml(
            r'<w:tblBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            r'<w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            r'<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            r'<w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            r'<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            r'<w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            r'<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            r'</w:tblBorders>'
        )
        tblPr.append(tblBorders)

docx_builder = DocxBuilder()
