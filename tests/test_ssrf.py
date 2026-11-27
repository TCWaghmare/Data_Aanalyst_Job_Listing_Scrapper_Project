"""
SSRF Protection Test Suite.
Verifies safe_fetch and /api/resume/analyze-url:
1. 127.0.0.1 must fail (loopback)
2. localhost must fail (loopback hostname)
3. 169.254.169.254 must fail (link-local / cloud metadata)
4. A redirect to 127.0.0.1 must fail (re-validating each hop)
5. file:// must fail (invalid scheme)
6. Normal public URL (mocked) must work
7. Enforces max 3 redirects
8. Enforces 2 MB response size limit
9. Enforces HTTPS only (HTTP only when ALLOW_HTTP=1)
"""

import os
import socket
from unittest.mock import patch, MagicMock
import pytest
import requests
from fastapi.testclient import TestClient

from scraper.safe_fetch import safe_fetch, validate_url, SSRFError
from app import app

client = TestClient(app)


class TestSafeFetchSSRF:
    def test_loopback_ip_fails(self):
        """127.0.0.1 must fail immediately."""
        with pytest.raises(SSRFError, match="(?i)blocked|restricted|loopback"):
            safe_fetch("https://127.0.0.1/admin")

    def test_localhost_fails(self):
        """localhost must fail immediately."""
        with pytest.raises(SSRFError, match="(?i)blocked|restricted|not permitted|Host"):
            safe_fetch("https://localhost/secret")

    def test_metadata_ip_fails(self):
        """169.254.169.254 (cloud metadata) must fail immediately."""
        with pytest.raises(SSRFError, match="(?i)blocked|restricted|link-local"):
            safe_fetch("https://169.254.169.254/latest/meta-data/")

    def test_file_scheme_fails(self):
        """file:// scheme must fail immediately."""
        with pytest.raises(SSRFError, match="(?i)forbidden|not allowed|Only 'https'"):
            safe_fetch("file:///etc/passwd")

    def test_redirect_to_loopback_fails(self):
        """A public URL that redirects to 127.0.0.1 must fail at the redirect hop."""
        mock_redirect_resp = MagicMock(spec=requests.Response)
        mock_redirect_resp.status_code = 302
        mock_redirect_resp.is_redirect = True
        mock_redirect_resp.headers = {"Location": "https://127.0.0.1/admin"}

        with patch("socket.getaddrinfo") as mock_dns:
            # First DNS call for example.com returns public IP
            mock_dns.side_effect = [
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
                # Second DNS call for 127.0.0.1 returns loopback IP
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
            ]
            with patch("requests.Session.get", return_value=mock_redirect_resp):
                with pytest.raises(SSRFError, match="(?i)blocked|restricted|127.0.0.1"):
                    safe_fetch("https://example.com/login-redirect")

    def test_normal_public_url_mocked_works(self):
        """A normal public URL (mocked) must succeed and return the response."""
        mock_resp = requests.Response()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": "36"}
        mock_resp.encoding = "utf-8"
        mock_resp._content = b"<html>Job Posting Description</html>"
        mock_resp.iter_content = MagicMock(return_value=[b"<html>Job Posting Description</html>"])

        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]):
            with patch("requests.Session.get", return_value=mock_resp):
                res = safe_fetch("https://example.com/jobs/data-analyst")
                assert res.status_code == 200
                assert res.text == "<html>Job Posting Description</html>"

    def test_allow_http_flag_behavior(self, monkeypatch):
        """HTTP is rejected by default, but allowed when ALLOW_HTTP=1 for public IPs."""
        monkeypatch.delenv("ALLOW_HTTP", raising=False)
        with pytest.raises(SSRFError, match="(?i)Insecure scheme 'http'"):
            safe_fetch("http://example.com/job")

        # When ALLOW_HTTP=1, http to public IP is allowed
        monkeypatch.setenv("ALLOW_HTTP", "1")
        mock_resp = requests.Response()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.encoding = "utf-8"
        mock_resp._content = b"OK"
        mock_resp.iter_content = MagicMock(return_value=[b"OK"])
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]):
            with patch("requests.Session.get", return_value=mock_resp):
                res = safe_fetch("http://example.com/job")
                assert res.status_code == 200

        # Even with ALLOW_HTTP=1, 127.0.0.1 must STILL fail!
        with pytest.raises(SSRFError, match="(?i)blocked|restricted"):
            safe_fetch("http://127.0.0.1/admin")

    def test_max_response_size_exceeded(self):
        """Payload exceeding 2 MB must fail."""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.is_redirect = False
        mock_resp.headers = {"Content-Length": str(3 * 1024 * 1024)}  # 3 MB

        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]):
            with patch("requests.Session.get", return_value=mock_resp):
                with pytest.raises(SSRFError, match="(?i)exceeds maximum limit of 2 MB"):
                    safe_fetch("https://example.com/large-file")

    def test_max_redirects_exceeded(self):
        """More than 3 redirects must fail."""
        mock_redirect = MagicMock(spec=requests.Response)
        mock_redirect.status_code = 302
        mock_redirect.is_redirect = True
        mock_redirect.headers = {"Location": "https://example.com/next"}

        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]):
            with patch("requests.Session.get", return_value=mock_redirect):
                with pytest.raises(SSRFError, match="(?i)Exceeded maximum redirect limit"):
                    safe_fetch("https://example.com/redirect1")


class TestApiAnalyzeUrlSSRFProtection:
    def test_api_blocks_loopback(self):
        res = client.post("/api/resume/analyze-url", json={"url": "https://127.0.0.1/job"})
        assert res.status_code == 400
        assert "SSRF" in res.text or "blocked" in res.text or "restricted" in res.text

    def test_api_blocks_localhost(self):
        res = client.post("/api/resume/analyze-url", json={"url": "https://localhost/job"})
        assert res.status_code == 400
        assert "SSRF" in res.text or "permitted" in res.text or "blocked" in res.text

    def test_api_blocks_metadata_ip(self):
        res = client.post("/api/resume/analyze-url", json={"url": "https://169.254.169.254/latest/meta-data"})
        assert res.status_code == 400
        assert "SSRF" in res.text or "blocked" in res.text or "restricted" in res.text

    def test_api_blocks_file_scheme(self):
        res = client.post("/api/resume/analyze-url", json={"url": "file:///etc/passwd"})
        assert res.status_code == 400
        assert "SSRF" in res.text or "forbidden" in res.text or "allowed" in res.text
