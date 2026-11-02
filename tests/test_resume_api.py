import io
import json
import os
import pypdf
import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

def test_master_resume_and_tailoring():
    # 1. Master resume test
    res = client.get('/api/resume/master')
    assert res.status_code == 200
    master = res.json()
    assert "name" in master
    assert "skills" in master

    # 2. Get first job to tailor
    res = client.get('/api/jobs?limit=1')
    assert res.status_code == 200
    jobs = res.json().get('jobs', [])
    if not jobs:
        return
    job = jobs[0]

    # 3. Tailor resume for this job
    res = client.post('/api/resume/tailor', json={'job_id': job['id']})
    assert res.status_code == 200
    tailor_res = res.json()
    assert 'ats_metrics' in tailor_res
    assert 'pdf_url' in tailor_res

    # 4. Test PDF download & verify strictly 1-page
    pdf_res = client.get(tailor_res['pdf_url'])
    assert pdf_res.status_code == 200
    reader = pypdf.PdfReader(io.BytesIO(pdf_res.content))
    assert len(reader.pages) == 1

    # 5. Test Overleaf LaTeX .tex download
    tex_res = client.get(tailor_res['tex_url'])
    assert tex_res.status_code == 200
    tex_content = tex_res.text
    assert r'\documentclass' in tex_content
    assert r'\begin{document}' in tex_content
    assert r'\end{document}' in tex_content

    # 6. Test preview routes
    pdf_prev = client.get(tailor_res['pdf_preview_url'])
    assert pdf_prev.status_code == 200
    assert 'application/pdf' in pdf_prev.headers['content-type']

    html_prev = client.get(tailor_res['html_preview_url'])
    assert html_prev.status_code == 200

    # 7. Word Document download
    docx_res = client.get(tailor_res['docx_url'])
    assert docx_res.status_code == 200
    assert len(docx_res.content) > 1000

    # 8. Test in-place edit
    edited_resume = dict(tailor_res['tailored_resume'])
    edited_resume['summary'] = "Updated Custom Summary: Skilled Senior Data Analyst."
    edit_res = client.post('/api/resume/update-tailored', json={
        'job_id': job['id'],
        'tailored_resume': edited_resume
    })
    assert edit_res.status_code == 200
    assert "Senior Data Analyst" in edit_res.json()['tailored_resume']['summary']


def test_oracle_cloud_url_scraping_and_tailoring():
    """Test deep scraping and ATS resume tailoring from an Oracle Cloud HCM Candidate Experience URL."""
    oracle_url = (
        "https://ibzdjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/SolsticeAdvancedMaterials/job/108113/?utm_medium=jobshare&utm_source=External+Job+Share"
    )

    # 1. Test analyzing / scraping the URL
    res = client.post("/api/resume/analyze-url", json={"url": oracle_url})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    scraped = data["job"]
    assert scraped["title"] == "Data Analyst"
    assert "Solstice Advanced Materials" in scraped["company"]
    assert "Pune" in scraped["location"]
    assert len(scraped["description"]) >= 250
    assert len(scraped["responsibilities"]) >= 5
    assert len(scraped["requirements"]) >= 3

    # 2. Test tailoring ATS resume directly from scraped payload (Option B workflow)
    tailor_res = client.post("/api/resume/tailor", json={
        "job_id": f"scraped_oracle_test_{os.urandom(3).hex()}",
        "job_title": scraped["title"],
        "company": scraped["company"],
        "description": scraped["description"],
        "skills": scraped["skills"],
        "responsibilities": scraped["responsibilities"],
        "requirements": scraped["requirements"],
        "qualifications": scraped["qualifications"],
        "ats_keywords": scraped["ats_keywords"],
        "source_url": oracle_url,
        "location": scraped["location"],
        "work_mode": scraped["work_mode"],
        "experience_level": scraped["experience_level"],
        "salary": scraped["salary"],
        "source_name": "Oracle Cloud HCM"
    })
    assert tailor_res.status_code == 200, tailor_res.text
    tailor_data = tailor_res.json()
    assert tailor_data["success"] is True
    assert tailor_data["ats_metrics"]["match_score"] > 60
    assert "pdf_url" in tailor_data
    assert "docx_url" in tailor_data
    assert "tex_url" in tailor_data
    assert "cl_pdf_url" in tailor_data

