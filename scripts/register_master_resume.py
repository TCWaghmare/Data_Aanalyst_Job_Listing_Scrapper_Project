import os
import sys
sys.path.insert(0, '.')

from resume_tailor.knowledge_base import career_kb

txt_file = 'Tejas_Data_Analyst_Master_Resume.txt'

# Clear older/duplicate docs and establish Tejas_Data_Analyst_Master_Resume.txt as the canonical Master Resume
career_kb.documents = []

with open(txt_file, 'rb') as f:
    txt_bytes = f.read()

doc_txt = career_kb.add_document(
    filename='Tejas_Data_Analyst_Master_Resume.txt',
    file_bytes=txt_bytes,
    category='resume',
    display_name='Tejas Data Analyst Master Resume (Overleaf LaTeX)'
)
print("Registered Canonical LaTeX Master Resume:", doc_txt.get("id"), doc_txt.get("status"))

# Verify unified profile
profile = career_kb.get_unified_profile()
print("\n--- CANONICAL UNIFIED PROFILE ---")
print("Name:", profile.get("name"))
print("Summary:", profile.get("summary"))
print("Skills Count:", len(profile.get("technical_tools", [])))
print("Skills Categories:", list(profile.get("skills", {}).keys()))
print("Projects Count:", len(profile.get("projects", [])))
for p in profile.get("projects", []):
    print(" - Project:", p.get("title"), "| Tools:", p.get("tools"), "| Link:", p.get("link_url"))
    for b in p.get("bullets", []):
        print("     *", b[:80] + "...")
print("Experience Count:", len(profile.get("experience", [])))
for e in profile.get("experience", []):
    print(" - Exp:", e.get("title"), "| Company:", e.get("company"), "| Dates:", e.get("dates"))
    for b in e.get("bullets", []):
        print("     *", b[:80] + "...")
print("Certifications Count:", len(profile.get("certifications", [])))
for c in profile.get("certifications", []):
    print(" - Cert:", c.get("name"), "| Link:", c.get("url"))
print("Achievements:", len(profile.get("achievements", [])))
for a in profile.get("achievements", []):
    print(" - Ach:", a.get("title"), "|", a.get("description"))
print("Education:", len(profile.get("education", [])))
for ed in profile.get("education", []):
    print(" - Edu:", ed.get("degree"), "|", ed.get("institution"), "|", ed.get("dates"))
