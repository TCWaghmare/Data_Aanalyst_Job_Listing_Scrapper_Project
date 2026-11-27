"""
Data cleaning and normalization utilities for job ingest and database backfill.

Ensures:
1. published_at is strictly ISO-8601 UTC (handles epoch seconds/millis, RFC-2822, ISO formats, relative strings).
2. experience_level is strictly one of: 'fresher', '0-1', '1-2', '2+', 'unknown'.
3. source_url has tracking params (trackingId, refId, trk, utm_*) stripped.
4. dedup_hash is computed from cleaned source_url plus normalized title and company.
5. scraped_at is tracked separately and expires_at is computed (30 days from published_at).
"""

import datetime
from datetime import timezone
import email.utils
import hashlib
import re
import urllib.parse
from typing import Any, Dict, Optional, Tuple

TRACKING_PARAMS = {"trackingid", "refid", "trk"}

ALLOWED_EXPERIENCE_LEVELS = {"fresher", "0-1", "1-2", "2+", "unknown"}
EXPERIENCE_ENUMS = ALLOWED_EXPERIENCE_LEVELS

# Explicit mapping of all current database and scraper variants to the 5 standard categories
EXPERIENCE_LEVEL_MAP = {
    "Fresher (0 Years)": "fresher",
    "Internship / Trainee (0 Years)": "fresher",
    "No experience required": "fresher",
    "Fresher (0 - 1 Year)": "fresher",
    "Fresher (0-1 yr)": "fresher",
    "0 - 1 Year (Fresher)": "fresher",
    "Freshers & Experienced Candidates": "fresher",
    "Freshers/Experienced": "fresher",
    "0 - 1 Year": "0-1",
    "0 - 1 Year (Entry-Level)": "0-1",
    "0 - 1 Year (Junior / Entry-Level)": "0-1",
    "0 - 1 Year (Junior)": "0-1",
    "0-1 Yr": "0-1",
    "0-1 Yr Exp": "0-1",
    "1 year(s)": "0-1",
}


def clean_source_url(url: str) -> str:
    """
    Strips tracking query parameters (trackingId, refId, trk, utm_*)
    from a source URL while preserving legitimate functional parameters.
    """
    if not url:
        return ""
    try:
        parts = urllib.parse.urlsplit(url.strip())
        if not parts.query:
            return url.strip().rstrip("/")
        query_params = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        cleaned_params = []
        for k, v in query_params:
            k_lower = k.lower().strip()
            if k_lower in TRACKING_PARAMS or k_lower.startswith("utm_"):
                continue
            cleaned_params.append((k, v))
        new_query = urllib.parse.urlencode(cleaned_params)
        new_parts = parts._replace(query=new_query)
        res = urllib.parse.urlunsplit(new_parts).rstrip("/")
        return res if not res.endswith("://") else res
    except Exception:
        return url.strip().rstrip("/")


def normalize_published_at(val: Any) -> Optional[str]:
    """
    Converts various date representations to a strict ISO-8601 UTC string (YYYY-MM-DDTHH:MM:SSZ).
    Handles:
    - Epoch seconds (int/float/str, e.g. 1696507200)
    - Epoch milliseconds (int/float/str, e.g. 1696507200000)
    - RFC-2822 dates (e.g. 'Fri, 27 Nov 2026 17:30:00 +0000', 'Thu, 05 Oct 2023 12:00:00 GMT')
    - ISO-8601 strings (e.g. '2026-11-27T17:30:00Z', '2026-11-27T23:00:00+05:30', '2026-11-27')
    - Python datetime objects
    - Relative date strings (e.g. '2 days ago', 'yesterday', 'today')
    """
    if val is None:
        return None

    # 1. Direct Python datetime
    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 2. Numeric epoch timestamps (seconds or milliseconds)
    if isinstance(val, (int, float)):
        ts = float(val)
        if ts > 1e11:  # Epoch in milliseconds
            ts /= 1000.0
        return datetime.datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "undefined", "n/a"):
        return None

    # Check for string digits representing epoch timestamp
    if s.isdigit() and len(s) >= 9:
        ts = float(s)
        if ts > 1e11:
            ts /= 1000.0
        return datetime.datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 3. Relative string expressions
    rel_m = re.match(r"^(\d+)\s+(minute|hour|day|week|month)s?\s+ago$", s, re.IGNORECASE)
    if rel_m:
        qty = int(rel_m.group(1))
        unit = rel_m.group(2).lower()
        now_dt = datetime.datetime.now(timezone.utc)
        if unit == "minute":
            dt = now_dt - datetime.timedelta(minutes=qty)
        elif unit == "hour":
            dt = now_dt - datetime.timedelta(hours=qty)
        elif unit == "day":
            dt = now_dt - datetime.timedelta(days=qty)
        elif unit == "week":
            dt = now_dt - datetime.timedelta(weeks=qty)
        elif unit == "month":
            dt = now_dt - datetime.timedelta(days=qty * 30)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    if s.lower() in ("today", "just now"):
        return datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if s.lower() == "yesterday":
        dt = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 4. RFC-2822 Date format (e.g. from WeWorkRemotely RSS feed)
    try:
        rfc_dt = email.utils.parsedate_to_datetime(s)
        if rfc_dt is not None:
            if rfc_dt.tzinfo is None:
                rfc_dt = rfc_dt.replace(tzinfo=timezone.utc)
            return rfc_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass

    # 5. ISO-8601 string parsing
    try:
        clean_s = s.replace("Z", "+00:00")
        iso_dt = datetime.datetime.fromisoformat(clean_s)
        if iso_dt.tzinfo is None:
            iso_dt = iso_dt.replace(tzinfo=timezone.utc)
        return iso_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass

    # 6. Fallback common date patterns: YYYY-MM-DD
    date_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if date_match:
        y, m, d = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
        dt = datetime.datetime(y, m, d, tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return None


def normalize_experience_level(raw: Optional[str]) -> str:
    """
    Normalizes any experience level string to one of the 5 allowed categories:
    'fresher', '0-1', '1-2', '2+', 'unknown'
    """
    if not raw:
        return "unknown"

    s = str(raw).strip()
    if s in ALLOWED_EXPERIENCE_LEVELS:
        return s

    # Exact match from known dictionary mapping
    if s in EXPERIENCE_LEVEL_MAP:
        return EXPERIENCE_LEVEL_MAP[s]

    low = s.lower()

    # Rule 1: Fresher / 0 years / Intern / Trainee
    if any(k in low for k in ["fresher", "intern", "trainee", "no experience", "recent grad", "campus"]) or re.search(r"\b0\s*(?:yr|year)s?\b", low):
        return "fresher"

    # Regex check for numeric ranges: e.g. "0-1", "0-2", "1-2", "2-4", "3-5"
    m_range = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:yr|year)?", low)
    if m_range:
        min_yr = int(m_range.group(1))
        max_yr = int(m_range.group(2))
        if min_yr == 0 and max_yr <= 1:
            return "0-1"
        elif min_yr <= 1 and max_yr <= 2:
            return "1-2"
        else:
            return "2+"

    m_plus = re.search(r"(\d+)\+?\s*(?:yr|year)", low)
    if m_plus:
        yr = int(m_plus.group(1))
        if yr == 0:
            return "fresher"
        elif yr == 1:
            return "0-1"
        elif yr == 2:
            return "1-2"
        else:
            return "2+"

    # Rule 2: 0-1 years / 1 year entry level
    if any(k in low for k in ["0-1", "0 - 1", "0 to 1", "0- 1", "0 -1", "entry", "junior", "1 year"]):
        return "0-1"

    # Rule 3: 1-2 years
    if any(k in low for k in ["1-2", "1 - 2", "1 to 2", "2 year"]):
        return "1-2"

    # Rule 4: 2+ years / experienced
    if any(k in low for k in ["2+", "3+", "4+", "5+", "mid", "senior", "lead", "experienced"]):
        return "2+"

    return "unknown"


def compute_clean_dedup_hash(title: str, company: str, location: str = "", source_url: str = "") -> str:
    """
    Recomputes dedup hash from the cleaned source URL plus normalized title and company.
    If source_url is absent, falls back to normalized title, company, and location.
    """
    def clean_str(s: str) -> str:
        s = (s or "").lower()
        s = re.sub(r"[^\w\s]", "", s)
        return " ".join(s.split())

    clean_t = clean_str(title)
    clean_c = clean_str(company)
    clean_u = clean_source_url(source_url).lower().rstrip("/")

    if clean_u:
        base = f"{clean_t}|{clean_c}|{clean_u}"
    else:
        clean_l = clean_str(location)
        base = f"{clean_t}|{clean_c}|{clean_l}" if clean_l else f"{clean_t}|{clean_c}"

    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def calculate_expires_at(published_at_iso: Optional[str], default_days: int = 30) -> str:
    """
    Calculates expiration timestamp (30 days from published_at, or now if published_at is None).
    """
    if published_at_iso:
        dt = normalize_published_at(published_at_iso)
        if dt:
            parsed = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
            exp = parsed + datetime.timedelta(days=default_days)
            return exp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    exp = datetime.datetime.now(timezone.utc) + datetime.timedelta(days=default_days)
    return exp.strftime("%Y-%m-%dT%H:%M:%SZ")


def is_job_active(published_at_iso: Optional[str], expires_at_iso: Optional[str] = None, max_age_days: int = 30) -> bool:
    """
    Determines if a job is active:
    Returns False if older than max_age_days (30 days) from published_at or if current time > expires_at.
    """
    now_utc = datetime.datetime.now(timezone.utc)

    if expires_at_iso:
        try:
            exp_dt = datetime.datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if now_utc >= exp_dt:
                return False
        except Exception:
            pass

    if published_at_iso:
        norm_pub = normalize_published_at(published_at_iso)
        if norm_pub:
            try:
                pub_dt = datetime.datetime.fromisoformat(norm_pub.replace("Z", "+00:00"))
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if (now_utc - pub_dt).total_seconds() > (max_age_days * 86400):
                    return False
            except Exception:
                pass

    return True
