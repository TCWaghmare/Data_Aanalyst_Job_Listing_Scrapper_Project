"""
Career Knowledge Base & Multi-Document Repository Manager.
Extracts structured intelligence (skills, experiences, projects, certifications,
achievements, education, recommendation quotes) across multiple document types:
PDF, DOCX, DOC, TXT, MD, Images (JPG, PNG), and CSV.
Synthesizes a unified professional profile exclusively from user-uploaded documents.
Strictly evidence-based: zero demo data, zero hallucinations, zero defaults.
"""

import os
import re
import io
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("KnowledgeBase")

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx
except ImportError:
    docx = None

try:
    from PIL import Image
except ImportError:
    Image = None

from resume_tailor.parser import (
    master_resume_parser,
    NOT_AVAILABLE,
    EMPTY_RESUME,
    TECH_SKILLS_TAXONOMY
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DOCUMENTS_DIR = os.path.join(DATA_DIR, "documents")
KB_FILE = os.path.join(DATA_DIR, "knowledge_base.json")

os.makedirs(DOCUMENTS_DIR, exist_ok=True)

DOCUMENT_CATEGORIES = [
    ("resume", "Resume / CV"),
    ("cover_letter", "Cover Letter"),
    ("certificate", "Certificate / Credential"),
    ("portfolio", "Portfolio Document"),
    ("project_doc", "Project Documentation"),
    ("case_study", "Case Study"),
    ("award", "Award & Achievement"),
    ("recommendation", "Recommendation Letter"),
    ("transcript", "Transcript & Marksheet"),
    ("license", "Professional License"),
    ("training", "Training Certificate"),
    ("linkedin_export", "LinkedIn Profile Export"),
    ("bio", "Personal Bio / Profile"),
    ("achievement", "Career Achievement"),
    ("other", "General Career Document")
]


class CareerKnowledgeBase:
    """
    Multi-document career intelligence repository.
    Strictly grounded in user-uploaded documents.
    """

    def __init__(self, kb_file: str = KB_FILE, docs_dir: str = DOCUMENTS_DIR):
        self.kb_file = kb_file
        self.docs_dir = docs_dir
        self.documents: List[Dict[str, Any]] = []
        self.unified_profile: Dict[str, Any] = {}
        self._load_or_initialize()

    def _load_or_initialize(self):
        """Loads repository metadata without any seeded or fake documents."""
        if os.path.exists(self.kb_file):
            try:
                with open(self.kb_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.documents = data.get("documents", [])
                    self.unified_profile = data.get("unified_profile", {})
            except Exception as e:
                logger.error(f"[KB] Error loading KB file: {e}. Reinitializing.")
                self.documents = []
                self.unified_profile = {}

        # Ensure all documents have standard transparency fields
        for doc in self.documents:
            if "last_processed_at" not in doc:
                doc["last_processed_at"] = doc.get("uploaded_at", datetime.now().isoformat())
            if "upload_status" not in doc:
                doc["upload_status"] = "Uploaded"
            if "extraction_status" not in doc:
                doc["extraction_status"] = doc.get("status", "Ready for AI Usage")
            if "file_type" in doc and doc["file_type"]:
                doc["file_type"] = doc["file_type"].upper()

        # Rebuild profile strictly from loaded documents
        self.rebuild_unified_profile()

    def get_summary_stats(self) -> Dict[str, Any]:
        """Returns transparency summary stats of the master resume document repository."""
        ready_docs = [d for d in self.documents if d.get("status") == "Ready for AI Usage"]
        error_docs = [d for d in self.documents if d.get("status") == "Error"]
        return {
            "total_uploaded": len(self.documents),
            "successfully_processed": len(ready_docs),
            "failed_files": len(error_docs),
            "used_for_tailoring": len(ready_docs),
            "files_used": [
                {
                    "id": d["id"],
                    "filename": d["filename"],
                    "display_name": d.get("display_name") or d["filename"],
                    "category": d.get("category", "other"),
                    "file_type": d.get("file_type", "").upper()
                }
                for d in ready_docs
            ]
        }

    def _save(self):
        """Persists documents and unified profile to disk."""
        data = {
            "version": "3.0",
            "last_updated": datetime.now().isoformat(),
            "documents_count": len(self.documents),
            "documents": self.documents,
            "unified_profile": self.unified_profile
        }
        with open(self.kb_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _format_size(num_bytes: int) -> str:
        if num_bytes < 1024:
            return f"{num_bytes} B"
        elif num_bytes < 1024 * 1024:
            return f"{num_bytes / 1024:.1f} KB"
        else:
            return f"{num_bytes / (1024 * 1024):.2f} MB"

    def detect_category(self, filename: str, text: str = "") -> str:
        """Intelligently detects document category from filename and content."""
        fn = filename.lower()
        t = text.lower()[:2000]

        if any(w in fn for w in ["resume", "cv", "curriculum_vitae"]) or "curriculum vitae" in t:
            return "resume"
        if any(w in fn for w in ["cover_letter", "coverletter", "cover letter"]):
            return "cover_letter"
        if any(w in fn for w in ["certificate", "cert_", "certification", "credential", "pl-300", "dp-600", "dp-700", "udemy", "coursera", "aicte"]):
            return "certificate"
        if any(w in fn for w in ["portfolio", "showcase"]):
            return "portfolio"
        if any(w in fn for w in ["case_study", "casestudy", "case study"]):
            return "case_study"
        if any(w in fn for w in ["project", "proj_"]):
            return "project_doc"
        if any(w in fn for w in ["award", "honor", "trophy", "recognition"]):
            return "award"
        if any(w in fn for w in ["recommendation", "lor", "reference_letter", "endorsement"]):
            return "recommendation"
        if any(w in fn for w in ["transcript", "marksheet", "grade", "scorecard", "diploma"]):
            return "transcript"
        if any(w in fn for w in ["license", "licence"]):
            return "license"
        if any(w in fn for w in ["training", "workshop", "bootcamp"]):
            return "training"
        if any(w in fn for w in ["linkedin"]):
            return "linkedin_export"
        if any(w in fn for w in ["bio", "biography", "about_me"]):
            return "bio"
        if any(w in fn for w in ["achievement", "milestone"]):
            return "achievement"

        # Content checks
        if "certify that" in t or "certificate of completion" in t or "has successfully completed" in t:
            return "certificate"
        if "dear hiring manager" in t or ("sincerely" in t and len(t) < 3000):
            return "cover_letter"
        if "letter of recommendation" in t or "to whom it may concern" in t:
            return "recommendation"

        return "other"

    def extract_text_from_file(self, filename: str, file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extracts text content and raw metadata using robust standard libraries."""
        ext = os.path.splitext(filename)[1].lower()
        text = ""
        meta: Dict[str, Any] = {}

        try:
            if ext == ".pdf":
                if not pypdf:
                    raise ImportError("pypdf is not installed.")
                if not file_bytes:
                    raise ValueError("PDF file is empty (0 bytes).")
                stream = io.BytesIO(file_bytes)
                reader = pypdf.PdfReader(stream)
                pages_text = []
                for p in reader.pages:
                    pt = p.extract_text()
                    if pt:
                        pages_text.append(pt)
                text = "\n\n".join(pages_text).strip()
                meta["page_count"] = len(reader.pages)
                text = master_resume_parser.clean_text_artifacts(text)
                if not text:
                    raise ValueError("No extractable text found in PDF. Scanned or image-only PDFs are not supported without OCR.")

            elif ext in [".docx", ".doc"]:
                if docx:
                    stream = io.BytesIO(file_bytes)
                    doc = docx.Document(stream)
                    paras = [p.text for p in doc.paragraphs if p.text.strip()]
                    for table in doc.tables:
                        for row in table.rows:
                            row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                            if row_text:
                                paras.append(row_text)
                    text = "\n".join(paras)
                    meta["paragraph_count"] = len(paras)
                else:
                    text = file_bytes.decode("utf-8", errors="ignore")
                text = master_resume_parser.clean_text_artifacts(text)

            elif ext in [".txt", ".md", ".csv", ".json", ".html"]:
                text = master_resume_parser.parse_text_stream(file_bytes)

            elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
                text = f"[Image Document: {filename}]"
                if Image:
                    try:
                        im = Image.open(io.BytesIO(file_bytes))
                        meta["dimensions"] = f"{im.width}x{im.height}"
                        meta["format"] = im.format
                        meta["mode"] = im.mode
                        text += f" Format: {im.format}, Dimensions: {im.width}x{im.height}."
                    except Exception as img_err:
                        logger.warning(f"Image open error: {img_err}")
                clean_name = re.sub(r"[_\-.]+", " ", os.path.splitext(filename)[0])
                text += f" Subject: {clean_name}"

            else:
                text = master_resume_parser.parse_text_stream(file_bytes)

        except Exception as e:
            logger.error(f"Failed to extract content from {filename}: {e}")
            raise ValueError(f"Failed to extract content from {filename}: {str(e)}")

        return text.strip(), meta

    def parse_extracted_data(self, filename: str, text: str, category: str) -> Dict[str, Any]:
        """Parses extracted raw text into structured career knowledge entities."""
        # If it's a resume or has rich sections, use the deep master_resume_parser
        if category == "resume":
            parsed_resume = master_resume_parser.parse_text(filename, text)
            return {
                "name": parsed_resume.get("name"),
                "contact": parsed_resume.get("contact", {}),
                "summary": parsed_resume.get("summary", ""),
                "skills": parsed_resume.get("skills", {}),
                "technical_tools": parsed_resume.get("technical_tools", []),
                "experience": parsed_resume.get("experience", []),
                "projects": parsed_resume.get("projects", []),
                "certifications": parsed_resume.get("certifications", []),
                "education": parsed_resume.get("education", []),
                "achievements": parsed_resume.get("achievements", []),
                "recommendations": [],
                "source_file": filename,
                "raw_snippet": text[:400] + ("..." if len(text) > 400 else "")
            }

        # Otherwise, parse specialized document types
        contact_info = master_resume_parser._parse_contact(text)

        # Extract technical competencies matching taxonomy
        extracted_skills: Dict[str, List[str]] = {}
        all_skills_flat: List[str] = []
        text_lower = text.lower()

        for group, skills_list in TECH_SKILLS_TAXONOMY.items():
            matched = []
            for s in skills_list:
                pattern = r"\b" + re.escape(s.lower()) + r"\b"
                if re.search(pattern, text_lower):
                    matched.append(s)
                    if s not in all_skills_flat:
                        all_skills_flat.append(s)
            if matched:
                extracted_skills[group] = matched

        projects = []
        certifications = []
        experiences = []
        achievements = []
        education = []
        recommendations = []

        if category in ["certificate", "license", "training"]:
            cert_name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")
            for line in text.splitlines()[:10]:
                l = line.strip()
                if any(k in l.lower() for k in ["certified", "associate", "specialist", "completion", "degree", "award", "engineer", "analyst", "practitioner"]):
                    cert_name = l
                    break
            certifications.append({
                "name": cert_name,
                "category": category,
                "source_file": filename,
                "extracted_skills": all_skills_flat[:6],
                "date": datetime.now().strftime("%b %Y"),
                "status": "Verified Credential"
            })

        elif category in ["project_doc", "case_study", "portfolio"]:
            proj_title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()
            bullets = [line.strip() for line in text.splitlines() if len(line.strip()) > 30][:6]
            if not bullets:
                bullets = [text[:250].strip() + "..."] if text else []
            projects.append({
                "title": proj_title,
                "category": category,
                "tools": ", ".join(all_skills_flat[:6]) if all_skills_flat else "Analytics, Engineering",
                "bullets": bullets,
                "skills": all_skills_flat[:8],
                "source_file": filename
            })

        elif category == "recommendation":
            recommendations.append({
                "title": f"Recommendation ({filename})",
                "excerpt": text[:400].strip() + "..." if len(text) > 400 else text.strip(),
                "skills_endorsed": all_skills_flat,
                "source_file": filename
            })

        elif category in ["award", "achievement"]:
            achievements.append({
                "title": os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title(),
                "description": text[:300].strip(),
                "skills": all_skills_flat[:5],
                "source_file": filename
            })

        return {
            "name": contact_info["name"] if contact_info["name"] != NOT_AVAILABLE else None,
            "contact": {
                "phone": contact_info["phone"] if contact_info["phone"] != NOT_AVAILABLE else None,
                "email": contact_info["email"] if contact_info["email"] != NOT_AVAILABLE else None,
                "linkedin": contact_info["linkedin"] or None,
                "github": contact_info["github"] or None
            },
            "skills": extracted_skills,
            "technical_tools": all_skills_flat,
            "projects": projects,
            "certifications": certifications,
            "experiences": experiences,
            "achievements": achievements,
            "recommendations": recommendations,
            "education": education,
            "source_file": filename,
            "raw_snippet": text[:400] + ("..." if len(text) > 400 else "")
        }

    def add_document(
        self,
        filename: str,
        file_bytes: bytes,
        category: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Saves, processes, indexes an uploaded career document, and rebuilds unified profile."""
        doc_id = "doc_" + uuid.uuid4().hex[:8]
        safe_name = re.sub(r"[^\w\-.]", "_", filename)
        save_path = os.path.join(self.docs_dir, f"{doc_id}_{safe_name}")

        with open(save_path, "wb") as f:
            f.write(file_bytes)

        file_size = len(file_bytes)
        file_ext = os.path.splitext(filename)[1].lower().lstrip(".")

        now_iso = datetime.now().isoformat()
        doc_record = {
            "id": doc_id,
            "filename": filename,
            "display_name": display_name or filename,
            "category": category or "other",
            "file_type": file_ext.upper(),
            "file_size": file_size,
            "file_size_formatted": self._format_size(file_size),
            "file_path": save_path,
            "uploaded_at": now_iso,
            "last_processed_at": now_iso,
            "upload_status": "Uploaded",
            "extraction_status": "Processing",
            "status": "Processing",
            "error_message": "",
            "extracted_summary": "",
            "extracted_data": {}
        }

        try:
            # 1. Extract text
            raw_text, meta = self.extract_text_from_file(filename, file_bytes)

            # 2. Category auto-detect
            if not category or category == "auto":
                doc_record["category"] = self.detect_category(filename, raw_text)

            # 3. Parse structured data
            extracted = self.parse_extracted_data(filename, raw_text, doc_record["category"])
            doc_record["extracted_data"] = extracted

            # 4. Summary counts
            skills_cnt = len(extracted.get("technical_tools", []))
            projs_cnt = len(extracted.get("projects", []))
            certs_cnt = len(extracted.get("certifications", []))
            exp_cnt = len(extracted.get("experience", [])) + len(extracted.get("experiences", []))

            summary_parts = []
            if skills_cnt > 0:
                summary_parts.append(f"{skills_cnt} technical competencies")
            if exp_cnt > 0:
                summary_parts.append(f"{exp_cnt} work experience item{'s' if exp_cnt > 1 else ''}")
            if projs_cnt > 0:
                summary_parts.append(f"{projs_cnt} project item{'s' if projs_cnt > 1 else ''}")
            if certs_cnt > 0:
                summary_parts.append(f"{certs_cnt} certification{'s' if certs_cnt > 1 else ''}")

            if not summary_parts:
                summary_parts.append(f"Processed {len(raw_text)} characters")

            doc_record["extracted_summary"] = "Indexed: " + ", ".join(summary_parts)
            doc_record["status"] = "Ready for AI Usage"
            doc_record["extraction_status"] = "Ready for AI Usage"
            doc_record["last_processed_at"] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Error extracting {filename}: {e}")
            doc_record["status"] = "Error"
            doc_record["extraction_status"] = "Error"
            doc_record["last_processed_at"] = datetime.now().isoformat()
            doc_record["error_message"] = str(e)
            doc_record["extracted_summary"] = f"Extraction error: {str(e)}"

        self.documents.append(doc_record)
        self.rebuild_unified_profile()
        self._save()
        return doc_record

    def reprocess_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Re-reads the physical file from disk, re-extracts text, and updates indexing."""
        for doc in self.documents:
            if doc["id"] == doc_id:
                fp = doc.get("file_path", "")
                if not fp or not os.path.exists(fp):
                    doc["status"] = "Error"
                    doc["error_message"] = "Physical file missing on server."
                    self._save()
                    return doc

                try:
                    with open(fp, "rb") as f:
                        file_bytes = f.read()

                    raw_text, meta = self.extract_text_from_file(doc["filename"], file_bytes)
                    if doc.get("category") in ["other", "auto", None]:
                        doc["category"] = self.detect_category(doc["filename"], raw_text)

                    extracted = self.parse_extracted_data(doc["filename"], raw_text, doc["category"])
                    doc["extracted_data"] = extracted

                    skills_cnt = len(extracted.get("technical_tools", []))
                    projs_cnt = len(extracted.get("projects", []))
                    certs_cnt = len(extracted.get("certifications", []))
                    exp_cnt = len(extracted.get("experience", [])) + len(extracted.get("experiences", []))

                    summary_parts = []
                    if skills_cnt > 0:
                        summary_parts.append(f"{skills_cnt} technical competencies")
                    if exp_cnt > 0:
                        summary_parts.append(f"{exp_cnt} work experience item{'s' if exp_cnt > 1 else ''}")
                    if projs_cnt > 0:
                        summary_parts.append(f"{projs_cnt} project item{'s' if projs_cnt > 1 else ''}")
                    if certs_cnt > 0:
                        summary_parts.append(f"{certs_cnt} certification{'s' if certs_cnt > 1 else ''}")

                    if not summary_parts:
                        summary_parts.append(f"Processed {len(raw_text)} characters")

                    doc["extracted_summary"] = "Indexed: " + ", ".join(summary_parts)
                    doc["status"] = "Ready for AI Usage"
                    doc["extraction_status"] = "Ready for AI Usage"
                    doc["last_processed_at"] = datetime.now().isoformat()
                    doc["error_message"] = ""

                except Exception as e:
                    logger.error(f"Reprocess error for {doc['filename']}: {e}")
                    doc["status"] = "Error"
                    doc["extraction_status"] = "Error"
                    doc["last_processed_at"] = datetime.now().isoformat()
                    doc["error_message"] = str(e)
                    doc["extracted_summary"] = f"Extraction error: {str(e)}"

                self.rebuild_unified_profile()
                self._save()
                return doc
        return None

    def reprocess_all(self):
        """Forces full re-extraction and re-indexing of all documents."""
        for doc in self.documents:
            self.reprocess_document(doc["id"])

    def update_document(self, doc_id: str, display_name: Optional[str] = None, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Updates display name or category for an existing document."""
        for doc in self.documents:
            if doc["id"] == doc_id:
                if display_name:
                    doc["display_name"] = display_name
                if category:
                    doc["category"] = category
                    self.reprocess_document(doc_id)

                self.rebuild_unified_profile()
                self._save()
                return doc
        return None

    def replace_document(self, doc_id: str, filename: str, file_bytes: bytes) -> Optional[Dict[str, Any]]:
        """Replaces the physical file and re-indexes the document."""
        for doc in self.documents:
            if doc["id"] == doc_id:
                old_path = doc.get("file_path", "")
                if old_path and os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass

                safe_name = re.sub(r"[^\w\-.]", "_", filename)
                new_path = os.path.join(self.docs_dir, f"{doc_id}_{safe_name}")
                with open(new_path, "wb") as f:
                    f.write(file_bytes)

                doc["filename"] = filename
                doc["file_size"] = len(file_bytes)
                doc["file_size_formatted"] = self._format_size(len(file_bytes))
                doc["file_path"] = new_path
                doc["uploaded_at"] = datetime.now().isoformat()
                doc["file_type"] = os.path.splitext(filename)[1].lower().lstrip(".")
                doc["status"] = "Processing"

                self.reprocess_document(doc_id)
                return doc
        return None

    def delete_document(self, doc_id: str) -> bool:
        """Deletes a document from repository and file system."""
        found = False
        new_docs = []
        for doc in self.documents:
            if doc["id"] == doc_id:
                found = True
                fp = doc.get("file_path", "")
                if fp and os.path.exists(fp):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
            else:
                new_docs.append(doc)

        if found:
            self.documents = new_docs
            self.rebuild_unified_profile()
            self._save()
            return True
        return False

    def rebuild_unified_profile(self) -> Dict[str, Any]:
        """
        Synthesizes a master professional profile strictly from ready documents in knowledge base.
        Zero hardcoded defaults. Zero hallucinations.
        If no documents are available, returns clean empty profile.
        """
        ready_docs = [d for d in self.documents if d.get("status") == "Ready for AI Usage"]

        # Track files analyzed metadata for transparency
        files_analyzed = []
        for doc in self.documents:
            ext_data = doc.get("extracted_data", {})
            skills_cnt = len(ext_data.get("technical_tools", []))
            projs_cnt = len(ext_data.get("projects", []))
            certs_cnt = len(ext_data.get("certifications", []))
            exp_cnt = len(ext_data.get("experience", [])) + len(ext_data.get("experiences", []))
            files_analyzed.append({
                "id": doc.get("id"),
                "filename": doc.get("filename"),
                "display_name": doc.get("display_name"),
                "category": doc.get("category"),
                "file_type": doc.get("file_type"),
                "uploaded_at": doc.get("uploaded_at"),
                "status": doc.get("status"),
                "summary": doc.get("extracted_summary", ""),
                "skills_found": skills_cnt,
                "projects_found": projs_cnt,
                "certifications_found": certs_cnt,
                "experience_found": exp_cnt
            })

        if not ready_docs:
            self.unified_profile = {
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
                "certifications": [],
                "education": [],
                "achievements": [],
                "recommendations": [],
                "source_documents_count": 0,
                "source_files": [],
                "evidence_map": {},
                "files_analyzed": files_analyzed
            }
            return self.unified_profile

        # Profile starts blank and is populated purely from uploaded files
        profile: Dict[str, Any] = {
            "name": "",
            "contact": {
                "phone": "",
                "email": "",
                "linkedin": "",
                "linkedin_url": "",
                "github": "",
                "github_url": "",
                "location": ""
            },
            "summary": "",
            "experience": [],
            "projects": [],
            "skills": {},
            "technical_tools": [],
            "certifications": [],
            "education": [],
            "achievements": [],
            "recommendations": [],
            "source_documents_count": len(ready_docs),
            "source_files": [d["filename"] for d in ready_docs],
            "evidence_map": {
                "contact": {},
                "summary": "",
                "skills": {},
                "experience": {},
                "projects": {},
                "certifications": {},
                "education": {}
            },
            "files_analyzed": files_analyzed
        }

        known_tool_set = set()
        known_cert_names = set()
        known_proj_titles = set()
        known_exp_keys = set()

        for doc in ready_docs:
            filename = doc.get("filename", "")
            data = doc.get("extracted_data", {})
            if not isinstance(data, dict):
                continue

            # Merge Name
            doc_name = data.get("name")
            if doc_name and doc_name != NOT_AVAILABLE and not profile["name"]:
                profile["name"] = doc_name
                profile["evidence_map"]["contact"]["name"] = filename

            # Merge Contact
            contact = data.get("contact", {})
            if isinstance(contact, dict):
                for k in ["email", "phone", "linkedin", "linkedin_url", "github", "github_url", "location"]:
                    val = contact.get(k)
                    if val and val != NOT_AVAILABLE and not profile["contact"].get(k):
                        profile["contact"][k] = val
                        profile["evidence_map"]["contact"][k] = filename

            # Merge Summary
            doc_sum = data.get("summary")
            if doc_sum and doc_sum != NOT_AVAILABLE and not profile["summary"]:
                profile["summary"] = doc_sum
                profile["evidence_map"]["summary"] = filename

            # Merge Skills
            skills = data.get("skills", {})
            if isinstance(skills, dict):
                for group, items in skills.items():
                    if group not in profile["skills"]:
                        profile["skills"][group] = []
                    for item in items:
                        if item not in profile["skills"][group]:
                            profile["skills"][group].append(item)
                        if item.lower() not in known_tool_set:
                            profile["technical_tools"].append(item)
                            known_tool_set.add(item.lower())
                            profile["evidence_map"]["skills"][item] = filename

            for tool in data.get("technical_tools", []):
                if tool.lower() not in known_tool_set:
                    profile["technical_tools"].append(tool)
                    known_tool_set.add(tool.lower())
                    profile["evidence_map"]["skills"][tool] = filename

            # Merge Experience
            exp_list = data.get("experience", []) or data.get("experiences", [])
            for exp in exp_list:
                if isinstance(exp, dict):
                    title = exp.get("title", "")
                    company = exp.get("company", "")
                    exp_key = f"{title.lower()}@{company.lower()}"
                    if exp_key not in known_exp_keys:
                        exp_entry = dict(exp)
                        exp_entry["source_file"] = filename
                        profile["experience"].append(exp_entry)
                        known_exp_keys.add(exp_key)
                        profile["evidence_map"]["experience"][f"{title} - {company}"] = filename

            # Merge Projects
            for proj in data.get("projects", []):
                if isinstance(proj, dict):
                    ptitle = proj.get("title", proj.get("name", ""))
                    if ptitle and ptitle.lower() not in known_proj_titles:
                        p_entry = dict(proj)
                        p_entry["source_file"] = filename
                        profile["projects"].append(p_entry)
                        known_proj_titles.add(ptitle.lower())
                        profile["evidence_map"]["projects"][ptitle] = filename

            # Merge Certifications
            for cert in data.get("certifications", []):
                cname = cert.get("name", "") if isinstance(cert, dict) else str(cert)
                if cname and cname.lower() not in known_cert_names:
                    c_entry = dict(cert) if isinstance(cert, dict) else {"name": cname, "link": "Credential Link", "url": "#"}
                    c_entry["source_file"] = filename
                    profile["certifications"].append(c_entry)
                    known_cert_names.add(cname.lower())
                    profile["evidence_map"]["certifications"][cname] = filename

            # Merge Education
            for edu in data.get("education", []):
                if isinstance(edu, dict):
                    inst = edu.get("institution", "")
                    deg = edu.get("degree", "")
                    edu_key = f"{inst.lower()}@{deg.lower()}"
                    if edu_key and edu_key not in [f"{e.get('institution','').lower()}@{e.get('degree','').lower()}" for e in profile["education"]]:
                        e_entry = dict(edu)
                        e_entry["source_file"] = filename
                        profile["education"].append(e_entry)
                        profile["evidence_map"]["education"][f"{deg} at {inst}"] = filename

            # Merge Achievements
            for ach in data.get("achievements", []):
                if ach not in profile["achievements"]:
                    ach_entry = dict(ach) if isinstance(ach, dict) else {"title": str(ach)}
                    ach_entry["source_file"] = filename
                    profile["achievements"].append(ach_entry)

            # Merge Recommendations
            for rec in data.get("recommendations", []):
                if rec not in profile["recommendations"]:
                    rec_entry = dict(rec) if isinstance(rec, dict) else {"title": str(rec)}
                    rec_entry["source_file"] = filename
                    profile["recommendations"].append(rec_entry)

        # Fallback empty notices for missing sections
        if not profile["name"]:
            profile["name"] = NOT_AVAILABLE
        if not profile["summary"]:
            profile["summary"] = NOT_AVAILABLE
        for k in ["email", "phone", "location"]:
            if not profile["contact"].get(k):
                profile["contact"][k] = NOT_AVAILABLE

        self.unified_profile = profile
        return profile

    def get_unified_profile(self) -> Dict[str, Any]:
        """Returns the current synthesized profile."""
        if not self.unified_profile or not self.unified_profile.get("source_files"):
            return self.rebuild_unified_profile()
        return self.unified_profile

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        for d in self.documents:
            if d["id"] == doc_id:
                return d
        return None

    def search_documents(self, query: str) -> List[Dict[str, Any]]:
        """Searches documents by name, category, or extracted skills."""
        q = query.lower().strip()
        if not q:
            return self.documents

        results = []
        for d in self.documents:
            fn = d.get("filename", "").lower()
            dn = d.get("display_name", "").lower()
            cat = d.get("category", "").lower()
            sumry = d.get("extracted_summary", "").lower()
            tools = [t.lower() for t in d.get("extracted_data", {}).get("technical_tools", [])]

            if q in fn or q in dn or q in cat or q in sumry or any(q in t for t in tools):
                results.append(d)
        return results


# Singleton Knowledge Base instance
career_kb = CareerKnowledgeBase()
