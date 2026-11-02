"""
Plain Text Resume Builder.
Generates clean, readable, ATS-scannable plain text (.txt) resumes.
"""

import os
from typing import Dict, Any

is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
OUTPUT_DIR = "/tmp/data/resumes" if is_serverless else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resumes")
try:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
except OSError:
    pass

class TxtBuilder:
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        try:
            if self.output_dir:
                os.makedirs(self.output_dir, exist_ok=True)
        except OSError:
            pass

    def build_txt(self, data: Dict[str, Any], job_id: str) -> str:
        clean_id = "".join([c if c.isalnum() else "_" for c in job_id])
        file_path = os.path.join(self.output_dir, f"tailored_{clean_id}.txt")

        name = data.get("name", "Candidate Name").upper()
        contact = data.get("contact", {})
        contact_parts = []
        if contact.get("email"):
            contact_parts.append(f"Email: {contact['email']}")
        if contact.get("phone"):
            contact_parts.append(f"Phone: {contact['phone']}")
        if contact.get("linkedin"):
            contact_parts.append(f"LinkedIn: {contact['linkedin']}")
        if contact.get("github"):
            contact_parts.append(f"GitHub: {contact['github']}")
        contact_line = " | ".join(contact_parts)

        lines = [
            "=" * 70,
            name.center(70),
            contact_line.center(70),
            "=" * 70,
            "",
            "PROFESSIONAL SUMMARY",
            "-" * 70,
            data.get("summary", ""),
            "",
            "TECHNICAL SKILLS",
            "-" * 70
        ]

        skills = data.get("skills", {})
        for cat, items in skills.items():
            if items:
                cat_title = cat.replace("_", " ").title()
                lines.append(f"• {cat_title}: {', '.join(items)}")

        lines.extend([
            "",
            "PROFESSIONAL EXPERIENCE",
            "-" * 70
        ])
        for exp in data.get("experience", []):
            lines.append(f"{exp.get('title')} | {exp.get('company')} | {exp.get('dates', '')}")
            for b in exp.get("bullets", []):
                lines.append(f"  • {b}")
            lines.append("")

        lines.extend([
            "KEY PROJECTS & PORTFOLIO",
            "-" * 70
        ])
        for p in data.get("projects", []):
            lines.append(f"{p.get('title', p.get('name'))} [Tools: {p.get('tools', '')}]")
            for b in p.get("bullets", []):
                lines.append(f"  • {b}")
            lines.append("")

        lines.extend([
            "EDUCATION",
            "-" * 70
        ])
        for edu in data.get("education", []):
            lines.append(f"• {edu.get('degree')} — {edu.get('institution')} ({edu.get('dates', '')})")

        lines.extend([
            "",
            "CERTIFICATIONS & CREDENTIALS",
            "-" * 70
        ])
        for cert in data.get("certifications", []):
            cname = cert.get("name", str(cert)) if isinstance(cert, dict) else str(cert)
            lines.append(f"• {cname}")

        text = "\n".join(lines)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        return file_path

txt_builder = TxtBuilder()

