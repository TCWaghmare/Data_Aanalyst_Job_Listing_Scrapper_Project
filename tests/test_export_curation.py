"""
Comprehensive tests for CSV and Excel job export and curation functionality.
Verifies columns, formatting, openpyxl output, and API key authentication options.
"""

import io
import os
import csv
import pytest
import openpyxl
from fastapi.testclient import TestClient
from app import app
from scraper.database import Database

client = TestClient(app)


def test_export_csv_curation_columns_and_content():
    """Verify CSV export contains all requested parameters and accurate data."""
    res = client.get("/api/export/csv?limit=10000")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    
    csv_text = res.text
    assert "id,title,standard_role" in csv_text
    
    reader = csv.DictReader(io.StringIO(csv_text))
    headers = reader.fieldnames
    
    # Required parameters specified by user
    required_cols = [
        "id", "title", "standard_role", "company", "apply_link", "salary",
        "location", "skills", "job_experience", "description",
        "responsibilities", "requirements", "qualifications", "ats_keywords"
    ]
    for col in required_cols:
        assert col in headers, f"Missing column {col} in CSV export"

    rows = list(reader)
    assert len(rows) > 0, "Expected at least one job in CSV export"
    
    first = rows[0]
    assert first["title"], "Job title should not be empty"
    assert first["company"], "Company should not be empty"
    assert "apply_link" in first


def test_export_excel_curation_headers_and_structure():
    """Verify Excel export creates valid .xlsx workbook with all required columns."""
    res = client.get("/api/export/excel?limit=10000")
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res.headers["content-type"]
    
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    assert "Curated Job Listings" in wb.sheetnames
    
    ws = wb["Curated Job Listings"]
    headers = [cell.value for cell in ws[1]]
    
    expected_headers = [
        "Job Title", "Company Name", "Apply Link", "Salary", "Location", "Country",
        "Work Mode", "Job Experience", "Skills Required", "Standard Role", "Role Category",
        "Source Platform", "Source Job URL", "Job Description", "Key Responsibilities",
        "Requirements", "Qualifications", "ATS Keywords", "Application Deadline",
        "Openings", "Recruiter Name", "Recruiter Email", "Recruiter Designation",
        "LinkedIn Profile", "Contact Phone", "WhatsApp", "Company Website",
        "Published Date", "First Scraped Date", "Last Checked Date", "Status",
        "Application Status", "Is Applied", "Applied Date", "Discovered Date", "Job ID"
    ]
    
    for h in expected_headers:
        assert h in headers, f"Missing header '{h}' in Excel export"
        
    assert ws.max_row > 1, "Expected at least one data row in Excel export"


def test_export_xlsx_alias_endpoint():
    """Verify /api/export/xlsx is an alias for /api/export/excel."""
    res = client.get("/api/export/xlsx?limit=10")
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    assert "Curated Job Listings" in wb.sheetnames


def test_export_with_query_param_api_key_auth():
    """Verify that ?api_key= query param allows direct browser export navigation."""
    sec_client = TestClient(app)
    sec_client._security_test_client = True
    
    api_key = os.getenv("API_KEY", "test-system-secret-key-12345")
    
    # 1. Without header or query param -> 401
    res_unauth = sec_client.get("/api/export/csv")
    assert res_unauth.status_code == 401
    
    # 2. With query param api_key -> 200
    res_query_auth = sec_client.get(f"/api/export/csv?api_key={api_key}")
    assert res_query_auth.status_code == 200
    assert "text/csv" in res_query_auth.headers["content-type"]
    
    # 3. Excel with query param api_key -> 200
    res_excel_auth = sec_client.get(f"/api/export/excel?api_key={api_key}")
    assert res_excel_auth.status_code == 200
