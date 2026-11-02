"""
Comprehensive End-to-End Tests for Career Knowledge Base, Multi-Document Upload,
Entity Extraction, Unified Profile Synthesis, Custom JD Tailoring, and Cover Letter Generation.
"""

import io
import json
import os
import pypdf
import pytest
from fastapi.testclient import TestClient
from app import app
from resume_tailor.knowledge_base import career_kb

client = TestClient(app)

def test_kb_documents_list():
    res = client.get("/api/kb/documents")
    assert res.status_code == 200
    data = res.json()
    assert "documents" in data
    assert "categories" in data
    assert "summary_stats" in data
    assert data["total"] >= 1
    print(f"✓ KB Documents listing passed: {data['total']} documents found")

def test_kb_profile():
    res = client.get("/api/kb/profile")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    profile = data["profile"]
    assert profile["name"] != "Information Not Available in Uploaded Documents"
    assert len(profile["technical_tools"]) >= 5
    print(f"✓ KB Profile synthesis passed: {len(profile['technical_tools'])} skills for {profile['name']}")

def test_kb_multi_file_upload_and_extraction():
    # 1. Prepare sample certificate file
    cert_content = b"Certificate of Achievement: AWS Certified Cloud Practitioner. Awarded for proficiency in AWS Cloud, S3, EC2, IAM, and Cloud Analytics."
    # 2. Prepare sample project case study
    case_content = b"Healthcare Analytics Case Study: Analyzed 100,000 patient records using Python, Pandas, SQL, and Power BI. Designed executive KPIs reducing patient wait times by 28%."

    files = [
        ("files", ("Test_AWS_Cloud_Certificate.txt", io.BytesIO(cert_content), "text/plain")),
        ("files", ("Test_Healthcare_Case_Study.txt", io.BytesIO(case_content), "text/plain"))
    ]

    res = client.post("/api/kb/upload", files=files, data={"category": "auto"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["uploaded_count"] == 2
    uploaded_ids = [d["id"] for d in data["documents"]]
    print(f"✓ Batch multi-file upload passed: {data['uploaded_count']} files processed")

    try:
        # Check that AWS was extracted into unified profile
        profile = data["unified_profile"]
        all_tools = [t.lower() for t in profile["technical_tools"]]
        assert "aws" in all_tools or any("aws" in t for t in all_tools)
        print("✓ AI Knowledge Extraction passed: AWS competence verified in profile")

        # Document detail & preview
        test_doc_id = uploaded_ids[0]
        res_detail = client.get(f"/api/kb/document/{test_doc_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["id"] == test_doc_id
        assert "extracted_summary" in detail

        # Preview file download
        res_prev = client.get(f"/api/kb/document/{test_doc_id}/preview")
        assert res_prev.status_code == 200
        assert len(res_prev.content) > 0

        # Update metadata (rename & change category)
        res_update = client.patch(f"/api/kb/document/{test_doc_id}", json={
            "display_name": "Temporary Test Certificate",
            "category": "certificate"
        })
        assert res_update.status_code == 200
        assert res_update.json()["document"]["display_name"] == "Temporary Test Certificate"
    finally:
        # Clean up test documents so knowledge base is never polluted with test/mock data
        for doc_id in uploaded_ids:
            client.delete(f"/api/kb/document/{doc_id}")
        print("✓ Test cleanup completed: temporary test documents removed cleanly")

def test_custom_jd_tailor_and_cover_letter():
    # Test arbitrary JD input (Requirement 4 & 5 & 8)
    jd_payload = {
        "job_title": "Power BI & Business Intelligence Analyst",
        "company": "Deloitte",
        "description": "Looking for Power BI Analyst with DAX, SQL, Power Query, and Excel modeling experience."
    }
    res = client.post("/api/resume/tailor-custom", json=jd_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "tailored_resume" in data
    assert "ats_metrics" in data
    assert "cover_letter" in data
    assert "files_analyzed" in data
    assert "evidence_summary" in data

    # Verify ATS metrics
    ats = data["ats_metrics"]
    assert ats["match_score"] >= 80
    assert any("power bi" in k.lower() for k in ats["matched_keywords"])
    print(f"✓ Custom JD Tailoring passed! ATS Score: {ats['match_score']}%")

    # Verify Cover Letter
    cl = data["cover_letter"]
    assert "paragraphs" in cl
    assert len(cl["paragraphs"]) >= 3
    assert "Deloitte" in cl["full_text"]
    assert len(cl["application_responses"]) >= 2
    print("✓ Personalized Cover Letter & Application Responses passed")

    # Verify download URLs are present
    assert "pdf_url" in data
    assert "docx_url" in data
    assert "txt_url" in data
    assert "cl_docx_url" in data
    assert "cl_pdf_url" in data
    assert "cl_txt_url" in data
    print("✓ All editable download URLs generated")

def test_resume_downloads_and_strict_1page_pdf():
    # Request a tailor
    res = client.post("/api/resume/tailor-custom", json={
        "job_title": "Junior Data Analyst",
        "company": "Swiggy",
        "description": "Seeking Junior Data Analyst with SQL, Python, Excel, Pivot Tables, and reporting."
    })
    assert res.status_code == 200
    data = res.json()

    # 1. Test 1-page PDF
    pdf_res = client.get(data["pdf_url"])
    assert pdf_res.status_code == 200
    reader = pypdf.PdfReader(io.BytesIO(pdf_res.content))
    assert len(reader.pages) == 1, f"Expected strictly 1 page, got {len(reader.pages)}"
    print("✓ Tailored Resume PDF verified strictly 1-page")

    # 2. Test Word (.docx) download
    docx_res = client.get(data["docx_url"])
    assert docx_res.status_code == 200
    assert len(docx_res.content) > 5000
    assert "openxmlformats" in docx_res.headers.get("content-type", "")
    print(f"✓ Tailored Resume Word (.docx) verified: {len(docx_res.content)} bytes")

    # 3. Test Plain Text (.txt) download
    txt_res = client.get(data["txt_url"])
    assert txt_res.status_code == 200
    assert "PROFESSIONAL SUMMARY" in txt_res.text
    assert "TECHNICAL SKILLS" in txt_res.text
    print("✓ Tailored Resume Plain Text (.txt) verified")

    # 4. Test Cover Letter (.docx) download
    cl_docx_res = client.get(data["cl_docx_url"])
    assert cl_docx_res.status_code == 200
    assert len(cl_docx_res.content) > 5000
    print("✓ Cover Letter Word (.docx) download verified")

    # 5. Test Cover Letter (.txt) download
    cl_txt_res = client.get(data["cl_txt_url"])
    assert cl_txt_res.status_code == 200
    assert "Swiggy" in cl_txt_res.text
    print("✓ Cover Letter Plain Text (.txt) download verified")

if __name__ == "__main__":
    test_kb_documents_list()
    test_kb_profile()
    test_kb_multi_file_upload_and_extraction()
    test_custom_jd_tailor_and_cover_letter()
    test_resume_downloads_and_strict_1page_pdf()
    print("\n🎉 ALL CAREER KNOWLEDGE BASE & TAILORING VERIFICATIONS PASSED SUCCESSFULLY!")
