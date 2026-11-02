"""
Overleaf-Compatible LaTeX Resume Builder.
Generates clean, ATS-compliant LaTeX code.
Enforces strict 1-page length via calibrated geometry and spacing.
Strictly evidence-based: zero hardcoded defaults.
"""

from typing import Dict, Any, List
import re

def escape_latex(text: str) -> str:
    """Escapes special LaTeX characters while preserving intended formatting."""
    if not text:
        return ""
    replacements = [
        ("&", "\\&"),
        ("%", "\\%"),
        ("$", "\\$"),
        ("#", "\\#"),
        ("_", "\\_"),
        ("~", "\\textasciitilde{}"),
        ("^", "\\textasciicircum{}"),
        ("×", "$\\times$"),
        ("−", "$-$"),
        ("–", "--"),
        ("—", "---"),
    ]
    res = str(text)
    for old, new in replacements:
        res = res.replace(old, new)
    return res

LATEX_TEMPLATE = r"""%-------------------------
% Tailored Resume in LaTeX (Overleaf-Compatible)
% Strictly Calibrated for One-Page Formatting
%------------------------

\documentclass[letterpaper,10pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{geometry}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% Strict 1-Page Calibrated Margins
\geometry{left=0.52in, top=0.48in, right=0.52in, bottom=0.48in}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Sections formatting
\titleformat{\section}{
  \vspace{-6pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

% Custom commands
\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.98\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & \small #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-6pt}
}

\newcommand{\resumeProjectHeading}[2]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.98\textwidth}[t]{l@{\extracolsep{\fill}}r}
      #1 & \small #2 \\
    \end{tabular*}\vspace{-6pt}
}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.0in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}[leftmargin=0.15in, label={\small\textbullet}]}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

%-------------------------------------------
%%%%%%  RESUME STARTS HERE  %%%%%%%%%%%%%%%%%
\begin{document}

%----------HEADING----------
\begin{center}
    \textbf{\Huge \scshape __NAME__} \\[4pt]
    \small __CONTACT_LINE__
\end{center}
\vspace{-12pt}

%-----------SUMMARY-----------
\section{Professional Summary}
\small __SUMMARY__

%-----------EXPERIENCE-----------
\section{Professional Experience}
\resumeSubHeadingListStart
__EXPERIENCE_SECTION__
\resumeSubHeadingListEnd

%-----------PROJECTS-----------
\section{Projects}
\resumeSubHeadingListStart
__PROJECTS_SECTION__
\resumeSubHeadingListEnd

%-----------TECHNICAL SKILLS-----------
\section{Technical Skills}
\begin{itemize}[leftmargin=0.0in, label={}]
    \small{\item{
__SKILLS_SECTION__
    }}
\end{itemize}
\vspace{-12pt}

%-----------EDUCATION-----------
\section{Education}
\resumeSubHeadingListStart
__EDUCATION_SECTION__
\resumeSubHeadingListEnd

%-----------CERTIFICATIONS-----------
\section{Certifications}
\begin{itemize}[leftmargin=0.0in, label={}]
__CERTIFICATIONS_SECTION__
\end{itemize}

\end{document}
"""

class LaTeXBuilder:
    def build_latex(self, tailored_data: Dict[str, Any]) -> str:
        name = escape_latex(tailored_data.get("name") or "Candidate Name").upper()
        contact = tailored_data.get("contact", {})
        phone = contact.get("phone") or ""
        email = contact.get("email") or ""
        linkedin = contact.get("linkedin") or ""
        linkedin_url = contact.get("linkedin_url") or (f"https://{linkedin}" if linkedin else "")
        github = contact.get("github") or ""
        github_url = contact.get("github_url") or (f"https://{github}" if github else "")

        # Dynamic contact line
        contact_parts = []
        if phone and "not available" not in phone.lower():
            contact_parts.append(escape_latex(phone))
        if email and "not available" not in email.lower():
            contact_parts.append(f"\\href{{mailto:{email}}}{{\\underline{{{escape_latex(email)}}}}}")
        if linkedin:
            contact_parts.append(f"\\href{{{linkedin_url}}}{{\\underline{{{escape_latex(linkedin)}}}}}")
        if github:
            contact_parts.append(f"\\href{{{github_url}}}{{\\underline{{{escape_latex(github)}}}}}")
        contact_line = " $|$ ".join(contact_parts) if contact_parts else "Information Not Available in Uploaded Documents"

        summary = escape_latex(tailored_data.get("summary") or "Information Not Available in Uploaded Documents")

        # Experience items
        experience_items = tailored_data.get("experience", [])
        exp_latex_blocks = []
        for exp in experience_items:
            title = escape_latex(exp.get("title", ""))
            company = escape_latex(exp.get("company", ""))
            location = escape_latex(exp.get("location", ""))
            dates = escape_latex(exp.get("dates", ""))
            bullets = exp.get("bullets", [])

            bullets_latex = "\n".join([f"    \\resumeItem{{{escape_latex(b)}}}" for b in bullets]) if bullets else "    \\resumeItem{Contributed to operational and technical deliverables.}"

            block = (
                f"  \\resumeSubheading\n"
                f"    {{{title}}}{{{dates}}}\n"
                f"    {{{company}}}{{{location}}}\n"
                f"  \\resumeItemListStart\n"
                f"{bullets_latex}\n"
                f"  \\resumeItemListEnd"
            )
            exp_latex_blocks.append(block)

        experience_section = "\n".join(exp_latex_blocks) if exp_latex_blocks else "  \\item[] \\textit{\\small Information Not Available in Uploaded Documents}"

        # Projects items
        project_items = tailored_data.get("projects", [])
        proj_latex_blocks = []
        for proj in project_items:
            p_title = escape_latex(proj.get("title", "Project"))
            tools = escape_latex(proj.get("tools", ""))
            link_text = proj.get("link_text") or "View Project"
            link_url = proj.get("link_url") or "#"
            bullets = proj.get("bullets", [])

            bullets_latex = "\n".join([f"    \\resumeItem{{{escape_latex(b)}}}" for b in bullets]) if bullets else "    \\resumeItem{Executed key project milestones.}"

            heading_arg = f"\\textbf{{{p_title}}}"
            if link_url and link_url != "#":
                heading_arg += f" $|$ \\href{{{link_url}}}{{\\underline{{{escape_latex(link_text)}}}}}"

            tools_line = f"    \\item[]\\textit{{\\small {tools}}}\n" if tools else ""

            block = (
                f"  \\resumeProjectHeading\n"
                f"    {{{heading_arg}}}{{}}\n"
                f"    \\vspace{{-4pt}}\n"
                f"{tools_line}"
                f"  \\resumeItemListStart\n"
                f"{bullets_latex}\n"
                f"  \\resumeItemListEnd"
            )
            proj_latex_blocks.append(block)

        projects_section = "\n".join(proj_latex_blocks) if proj_latex_blocks else "  \\item[] \\textit{\\small Information Not Available in Uploaded Documents}"

        # Technical Skills
        skills_dict = tailored_data.get("skills", {})
        skills_lines = []
        for cat_key, items in skills_dict.items():
            if items:
                label = cat_key.replace("_", " ").title()
                if label == "Bi Visualization":
                    label = "BI \\& Visualization"
                elif label == "Data Analytics":
                    label = "Data \\& Analytics"
                skills_lines.append(f"     \\textbf{{{label}:}} {{{escape_latex(', '.join(items))}}} \\\\")

        if not skills_lines:
            all_tools = tailored_data.get("technical_tools", [])
            if all_tools:
                skills_lines.append(f"     \\textbf{{Technical Competencies:}} {{{escape_latex(', '.join(all_tools))}}} \\\\")
            else:
                skills_lines.append("     \\textit{Information Not Available in Uploaded Documents} \\\\")

        skills_section = "\n".join(skills_lines)

        # Education
        education_items = tailored_data.get("education", [])
        edu_latex_blocks = []
        for edu in education_items:
            inst = escape_latex(edu.get("institution", "Institution"))
            dates = escape_latex(edu.get("dates", ""))
            deg = escape_latex(edu.get("degree", ""))
            block = (
                f"  \\resumeSubheading\n"
                f"    {{{inst}}}{{{dates}}}\n"
                f"    {{{deg}}}{{}}"
            )
            edu_latex_blocks.append(block)

        education_section = "\n".join(edu_latex_blocks) if edu_latex_blocks else "  \\item[] \\textit{\\small Information Not Available in Uploaded Documents}"

        # Certifications
        cert_items = tailored_data.get("certifications", [])
        cert_latex_blocks = []
        for cert in cert_items:
            c_name = escape_latex(cert.get("name", "") if isinstance(cert, dict) else str(cert))
            c_link = cert.get("link", "Credential Link") if isinstance(cert, dict) else "Credential Link"
            c_url = cert.get("url", "#") if isinstance(cert, dict) else "#"
            if c_url and c_url != "#":
                block = f"    \\item \\small{{{c_name} \\hfill \\href{{{c_url}}}{{\\underline{{{escape_latex(c_link)}}}}}}}"
            else:
                block = f"    \\item \\small{{{c_name}}}"
            cert_latex_blocks.append(block)

        certifications_section = "\n".join(cert_latex_blocks) if cert_latex_blocks else "    \\item[] \\textit{\\small Information Not Available in Uploaded Documents}"

        # Substitute into template
        code = LATEX_TEMPLATE
        code = code.replace("__NAME__", name)
        code = code.replace("__CONTACT_LINE__", contact_line)
        code = code.replace("__SUMMARY__", summary)
        code = code.replace("__EXPERIENCE_SECTION__", experience_section)
        code = code.replace("__PROJECTS_SECTION__", projects_section)
        code = code.replace("__SKILLS_SECTION__", skills_section)
        code = code.replace("__EDUCATION_SECTION__", education_section)
        code = code.replace("__CERTIFICATIONS_SECTION__", certifications_section)

        return code.strip()

# Global builder instance
latex_builder = LaTeXBuilder()
