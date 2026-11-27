import os
import itertools
import pytest
from fastapi.testclient import TestClient

# Ensure test security secrets are present for the entire test session
os.environ.setdefault("API_KEY", "test-system-secret-key-12345")
os.environ.setdefault("CRON_SECRET", "test-cron-secret-xyz-987")
os.environ.setdefault("ALLOWED_ORIGINS", "https://trusted-dashboard.example.com,https://app.jobfinder.local")

_orig_request = TestClient.request
_ip_counter = itertools.count(1)

def _patched_request(self, method, url, *args, **kwargs):
    # If the client is marked for security testing, do not auto-inject headers
    if getattr(self, "_security_test_client", False):
        return _orig_request(self, method, url, *args, **kwargs)

    headers = kwargs.get("headers")
    if headers is None:
        headers = {}
    else:
        headers = dict(headers)

    header_keys_lower = [k.lower() for k in headers.keys()]

    # Auto-inject API key for existing functional test suite
    if "x-api-key" not in header_keys_lower:
        headers["X-API-Key"] = os.getenv("API_KEY", "test-system-secret-key-12345")

    # Auto-inject cron bearer token for existing scheduled test suite
    if "/api/cron" in str(url) and "authorization" not in header_keys_lower:
        headers["Authorization"] = f"Bearer {os.getenv('CRON_SECRET', 'test-cron-secret-xyz-987')}"

    # Auto-inject unique client IP for functional tests to prevent false-positive rate limit blocks
    if "x-forwarded-for" not in header_keys_lower:
        headers["X-Forwarded-For"] = f"10.99.{(next(_ip_counter) % 250) + 1}.1"

    kwargs["headers"] = headers
    return _orig_request(self, method, url, *args, **kwargs)

TestClient.request = _patched_request
