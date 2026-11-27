"""
Re-export safe_fetch and SSRFError from scraper.safe_fetch for resume_tailor module compatibility.
"""

from scraper.safe_fetch import safe_fetch, validate_url, SSRFError, is_disallowed_ip

__all__ = ["safe_fetch", "validate_url", "SSRFError", "is_disallowed_ip"]
