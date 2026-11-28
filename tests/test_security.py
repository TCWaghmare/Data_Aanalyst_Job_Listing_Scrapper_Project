"""
Security Test Suite for Fresher Data Analyst Job Finder.
Tests:
1. API Key Authentication (X-API-Key required on /api/* except GET /api/health)
2. CORS Origin Whitelisting (only ALLOWED_ORIGINS, allow_credentials=False, evil origin gets no header)
3. Cron Route Protection (/api/cron requires Authorization: Bearer <CRON_SECRET>)
4. Security Headers (X-Content-Type-Options, X-Frame-Options DENY, Referrer-Policy, CSP)
5. Per-IP Rate Limiting (60 req/min general; 5 req/min on /api/resume/*, /api/scraper/run, /api/kb/upload)
"""

import os
import pytest
from fastapi.testclient import TestClient

# Set security environment variables for testing
os.environ["API_KEY"] = "test-system-secret-key-12345"
os.environ["CRON_SECRET"] = "test-cron-secret-xyz-987"
os.environ["ALLOWED_ORIGINS"] = "https://trusted-dashboard.example.com,https://app.jobfinder.local"

from app import app

client = TestClient(app)
# Mark this client as explicit security tester so test harness won't auto-inject keys
client._security_test_client = True


class TestApiKeyAuthentication:
    def test_missing_api_key_returns_401(self):
        """Requests to protected /api/* routes without X-API-Key must return 401."""
        res = client.get("/api/jobs")
        assert res.status_code == 401, f"Expected 401 without API key, got {res.status_code}"
        assert "detail" in res.json()

    def test_wrong_api_key_returns_401(self):
        """Requests with an invalid X-API-Key must return 401."""
        res = client.get("/api/jobs", headers={"X-API-Key": "invalid-wrong-key"})
        assert res.status_code == 401, f"Expected 401 for wrong API key, got {res.status_code}"
        assert "detail" in res.json()

    def test_valid_api_key_succeeds(self):
        """Requests with valid X-API-Key must pass authentication."""
        res = client.get("/api/jobs", headers={"X-API-Key": "test-system-secret-key-12345"})
        assert res.status_code == 200, f"Expected 200 with valid API key, got {res.status_code}"

    def test_health_check_exempt_from_api_key(self):
        """GET /api/health must be exempt from API key and return 200 OK."""
        res = client.get("/api/health")
        assert res.status_code == 200, f"Expected 200 on /api/health without key, got {res.status_code}"
        data = res.json()
        assert data.get("status") in ["ok", "healthy"]


class TestCorsConfiguration:
    def test_evil_origin_gets_no_cors_header(self):
        """Untrusted/evil origins must NOT receive an Access-Control-Allow-Origin header."""
        res = client.get("/api/health", headers={"Origin": "https://evil-attacker.com"})
        allow_origin = res.headers.get("access-control-allow-origin")
        assert allow_origin != "https://evil-attacker.com", (
            f"Security risk: evil origin received Access-Control-Allow-Origin: {allow_origin}"
        )
        assert allow_origin != "*", "Security risk: wildcard * origin returned for untrusted origin"

    def test_allowed_origin_gets_cors_header(self):
        """Whitelisted origins from ALLOWED_ORIGINS must receive Access-Control-Allow-Origin."""
        res = client.get("/api/health", headers={"Origin": "https://trusted-dashboard.example.com"})
        assert res.headers.get("access-control-allow-origin") == "https://trusted-dashboard.example.com"
        # allow_credentials must be False
        assert res.headers.get("access-control-allow-credentials") in [None, "false", "False"]


class TestCronProtection:
    def test_cron_without_secret_returns_401(self):
        """Requests to /api/cron without Authorization header must return 401."""
        res = client.get("/api/cron")
        assert res.status_code == 401, f"Expected 401 for /api/cron without secret, got {res.status_code}"

    def test_cron_with_wrong_secret_returns_401(self):
        """Requests to /api/cron with incorrect Bearer token must return 401."""
        res = client.get("/api/cron", headers={"Authorization": "Bearer bad-cron-token-999"})
        assert res.status_code == 401, f"Expected 401 for /api/cron with wrong token, got {res.status_code}"

    def test_cron_with_valid_secret_succeeds(self):
        """Requests to /api/cron with valid Authorization: Bearer <CRON_SECRET> must succeed."""
        res = client.get("/api/cron", headers={"Authorization": "Bearer test-cron-secret-xyz-987"})
        assert res.status_code == 200, f"Expected 200 for /api/cron with valid secret, got {res.status_code}"
        assert res.json().get("success") is True


class TestSecurityHeaders:
    def test_security_headers_present(self):
        """All responses must include standard defense-in-depth security headers."""
        res = client.get("/api/health")
        headers = res.headers
        assert headers.get("x-content-type-options") == "nosniff", "Missing X-Content-Type-Options: nosniff"
        assert headers.get("x-frame-options") == "DENY", "Missing X-Frame-Options: DENY"
        assert "referrer-policy" in headers, "Missing Referrer-Policy header"
        assert "content-security-policy" in headers, "Missing Content-Security-Policy header"

    def test_preview_routes_allow_sameorigin_framing(self):
        """Preview and document embed routes must allow same-origin framing for in-app PDF preview."""
        res = client.get(
            "/api/resume/preview/pdf/test_mock_job_id",
            headers={"X-API-Key": "test-system-secret-key-12345"}
        )
        headers = res.headers
        assert headers.get("x-frame-options") == "SAMEORIGIN", "Preview routes must use X-Frame-Options: SAMEORIGIN"
        assert "frame-ancestors 'self'" in headers.get("content-security-policy", ""), "CSP must permit same-origin frame ancestors"
        assert "frame-src 'self' blob:" in headers.get("content-security-policy", ""), "CSP must permit blob and self frame sources"


class TestRateLimiting:
    def test_strict_route_rate_limiting(self):
        """Strict routes (/api/scraper/run, /api/kb/upload, /api/resume/*) must be capped at 5 req/min."""
        headers = {"X-API-Key": "test-system-secret-key-12345", "X-Forwarded-For": "198.51.100.42"}
        statuses = []
        for _ in range(7):
            res = client.get("/api/resume/master", headers=headers)
            statuses.append(res.status_code)
        
        # At least the 6th and 7th requests must be 429 Too Many Requests
        assert 429 in statuses, f"Expected 429 Too Many Requests after 5 calls, got {statuses}"
