"""
Security and Hardening Test Suite for /api/kb/upload.
Tests:
1. Rejects .exe with 415
2. Rejects corrupt PDF with 415 or 422
3. Rejects file > 5 MB (e.g. 6 MB / 30 MB) with 413
4. Rejects empty file (0 bytes) with 422
5. Rejects path traversal file "../../evil.py" with 415
6. Sanitizes display_name to os.path.basename(filename) only
7. Accepts valid txt, pdf, docx
8. Verifies magic bytes mismatch for docx (not zip) returns 415
9. Verifies maximum 10 files per request limit (413)
"""

import io
import os
import docx
import pytest
from fastapi.testclient import TestClient

from app import app
from resume_tailor.knowledge_base import career_kb

client = TestClient(app)


class TestKbUploadHardening:
    def test_reject_exe_file_with_415(self):
        """Uploading an .exe file must be rejected with HTTP 415."""
        exe_content = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
        files = [("files", ("malware.exe", io.BytesIO(exe_content), "application/octet-stream"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 415
        assert "Unsupported file type" in res.text

    def test_reject_path_traversal_evil_py_with_415(self):
        """Uploading '../../evil.py' must be rejected with HTTP 415."""
        py_content = b"import os\nos.system('echo compromised')\n"
        files = [("files", ("../../evil.py", io.BytesIO(py_content), "text/x-python"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 415
        assert "Unsupported file type" in res.text

    def test_reject_empty_file_with_422(self):
        """Uploading an empty file (0 bytes) must be rejected with HTTP 422."""
        files = [("files", ("empty.txt", io.BytesIO(b""), "text/plain"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 422
        assert "empty" in res.text.lower()

    def test_reject_corrupt_pdf_magic_bytes_with_415(self):
        """A PDF file that does not start with %PDF magic bytes must be rejected with HTTP 415."""
        corrupt_bytes = b"NOT_A_PDF_HEADER_corrupt_garbage_data"
        files = [("files", ("corrupt_magic.pdf", io.BytesIO(corrupt_bytes), "application/pdf"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 415
        assert "%PDF" in res.text

    def test_reject_corrupt_pdf_unparseable_with_422(self):
        """A PDF that starts with %PDF but is structurally corrupt/unparseable must be rejected with HTTP 422."""
        # Starts with %PDF but has corrupt junk that cannot be parsed into text
        corrupt_pdf = b"%PDF-1.4\ncorrupt junk that has no valid xref or stream or trailer whatsoever\n%%EOF"
        files = [("files", ("corrupt_parse.pdf", io.BytesIO(corrupt_pdf), "application/pdf"))]
        initial_doc_count = len(career_kb.documents)

        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 422
        assert "text" in res.text.lower() or "parse" in res.text.lower()

        # Crucial check: Verify it was NOT added to the knowledge base
        assert len(career_kb.documents) == initial_doc_count
        assert not any(d["filename"] == "corrupt_parse.pdf" for d in career_kb.documents)

    def test_reject_large_file_with_413(self):
        """A file exceeding 5 MB must be rejected with HTTP 413."""
        # 6 MB file
        six_mb_content = b"%PDF-1.4\n" + b"A" * (6 * 1024 * 1024)
        files = [("files", ("oversized.pdf", io.BytesIO(six_mb_content), "application/pdf"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 413
        assert "exceeds the maximum allowed size of 5 MB" in res.text

    def test_reject_magic_bytes_mismatch_docx_with_415(self):
        """A .docx file that is not a valid zip archive must be rejected with HTTP 415."""
        fake_docx = b"This is plain text content pretending to be a docx file."
        files = [("files", ("fake.docx", io.BytesIO(fake_docx), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 415
        assert "ZIP archive" in res.text

    def test_reject_too_many_files_with_413(self):
        """More than 10 files in a single request must be rejected with HTTP 413."""
        many_files = [
            ("files", (f"file_{i}.txt", io.BytesIO(b"Valid content line."), "text/plain"))
            for i in range(11)
        ]
        res = client.post("/api/kb/upload", files=many_files)
        assert res.status_code == 413
        assert "maximum 10 files" in res.text

    def test_valid_txt_upload_succeeds(self):
        """A valid .txt file with text content must be accepted and indexed."""
        txt_content = b"Project: Market Basket Analysis with Python, Pandas, and Apriori Algorithm. Analyzed 10,000 retail transactions."
        files = [("files", ("sample_project.txt", io.BytesIO(txt_content), "text/plain"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["uploaded_count"] == 1
        doc = data["documents"][0]
        assert doc["display_name"] == "sample_project.txt"
        assert doc["filename"] == "sample_project.txt"

        # Cleanup
        client.delete(f"/api/kb/document/{doc['id']}")

    def test_valid_docx_upload_succeeds(self):
        """A valid .docx file must be accepted and indexed."""
        doc = docx.Document()
        doc.add_heading("Power BI Dashboard Certification", level=1)
        doc.add_paragraph("Awarded for advanced DAX formulas, Star Schema modeling, and ETL pipeline optimization in Power BI.")
        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        files = [("files", ("sample_certification.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        doc = data["documents"][0]
        assert doc["display_name"] == "sample_certification.docx"

        # Cleanup
        client.delete(f"/api/kb/document/{doc['id']}")

    def test_valid_pdf_upload_succeeds(self):
        """A valid PDF file from project root must be accepted and indexed."""
        pdf_path = "Tejas_Data_Analyst_Master_Resume.pdf"
        assert os.path.exists(pdf_path), "Master resume PDF missing from root directory"
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        files = [("files", ("valid_master_resume.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        doc = data["documents"][0]
        assert doc["display_name"] == "valid_master_resume.pdf"

        # Cleanup
        client.delete(f"/api/kb/document/{doc['id']}")

    def test_path_traversal_display_name_sanitization(self):
        """Uploading '../../safe_analysis.txt' stores display_name strictly as 'safe_analysis.txt'."""
        content = b"Financial Analytics Case Study: Automated reconciliation of bank records using SQL and Python."
        files = [("files", ("../../safe_analysis.txt", io.BytesIO(content), "text/plain"))]
        res = client.post("/api/kb/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        doc = data["documents"][0]
        assert doc["display_name"] == "safe_analysis.txt"
        assert ".." not in doc["display_name"]
        assert "/" not in doc["display_name"]
        assert "\\" not in doc["display_name"]

        # Cleanup
        client.delete(f"/api/kb/document/{doc['id']}")
