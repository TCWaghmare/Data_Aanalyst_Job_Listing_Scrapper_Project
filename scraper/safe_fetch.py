"""
Safe HTTP Fetch Utility with SSRF Protection.
Enforces:
1. HTTPS only (HTTP permitted only if env ALLOW_HTTP=1).
2. Hostname resolution rejecting loopback, private (10/8, 172.16/12, 192.168/16),
   link-local (169.254/16), IPv6 equivalents, and non-global IPs.
3. Manual redirect following up to max 3 hops, re-validating every target hop.
4. 10-second default timeout.
5. 2 MB maximum response payload limit.
"""

import os
import socket
import logging
import ipaddress
import urllib.parse
from typing import Tuple, Optional, Dict, Any, Union
import requests

logger = logging.getLogger("safe_fetch")

MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB
DEFAULT_TIMEOUT = 10.0                 # 10 seconds
MAX_REDIRECTS = 3                      # max 3 hops


class SSRFError(ValueError):
    """Raised when an SSRF security check fails."""
    pass


def is_disallowed_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """
    Returns True if the IP address belongs to loopback, private, link-local,
    multicast, reserved, unspecified, or non-global IP spaces.
    """
    # Unpack IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    return (
        not ip.is_global
        or ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url(url: str) -> Tuple[str, str, int]:
    """
    Validates a URL against strict SSRF constraints:
    - Scheme must be https (http only if env ALLOW_HTTP=1).
    - Hostname must be resolvable and cannot point to loopback, private,
      link-local, multicast, or non-global IP addresses.
    Returns (scheme, hostname, port).
    Raises SSRFError if the URL violates security policies.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("Invalid URL: must be a non-empty string.")

    cleaned_url = url.strip()
    try:
        parsed = urllib.parse.urlsplit(cleaned_url)
    except Exception as e:
        raise SSRFError(f"Malformed URL: {e}")

    scheme = (parsed.scheme or "").lower()
    allow_http = os.getenv("ALLOW_HTTP", "").strip() == "1"

    if scheme == "https":
        default_port = 443
    elif scheme == "http":
        if not allow_http:
            raise SSRFError(f"Insecure scheme 'http' is not permitted. Only 'https' is allowed.")
        default_port = 80
    else:
        raise SSRFError(f"Scheme '{scheme}' is forbidden. Only 'https' is allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL is missing a valid hostname.")

    hostname = hostname.strip().lower()
    if hostname.startswith("[") and hostname.endswith("]"):
        hostname = hostname[1:-1]

    # Explicit reject for common local/metadata hostnames
    if hostname in ("localhost", "localhost.localdomain", "metadata.google.internal"):
        raise SSRFError(f"Host '{hostname}' is not permitted.")

    port = parsed.port or default_port

    # Resolve all IP addresses for the hostname
    try:
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise SSRFError(f"Could not resolve hostname '{hostname}': {e}")
    except Exception as e:
        raise SSRFError(f"DNS resolution failure for '{hostname}': {e}")

    if not addr_info:
        raise SSRFError(f"No IP addresses resolved for hostname '{hostname}'.")

    for entry in addr_info:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFError(f"Invalid resolved IP '{ip_str}'.")

        if is_disallowed_ip(ip_obj):
            raise SSRFError(f"Access to restricted IP '{ip_str}' for host '{hostname}' is blocked.")

    return scheme, hostname, port


def safe_fetch(url: str, **kwargs) -> requests.Response:
    """
    Safely fetches a user-supplied URL with SSRF protection:
    - only https (http only if env ALLOW_HTTP=1)
    - resolve the hostname; reject loopback, private (10/8, 172.16/12, 192.168/16),
      link-local (169.254/16), and IPv6 equivalents
    - follow redirects manually, max 3, re-validating each hop
    - timeout 10s, max response 2 MB
    """
    max_redirects = kwargs.pop("max_redirects", MAX_REDIRECTS)
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    max_response_bytes = kwargs.pop("max_response_bytes", MAX_RESPONSE_BYTES)
    headers = kwargs.pop("headers", None)
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    current_url = url
    session = kwargs.pop("session", None) or requests.Session()

    for hop in range(max_redirects + 1):
        # 1. Validate the current URL and all resolved IPs before connecting
        validate_url(current_url)

        # 2. Fetch with allow_redirects=False and stream=True
        try:
            resp = session.get(
                current_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
                **kwargs
            )
        except requests.exceptions.SSLError:
            # Fallback with verify=False if corporate/recruiter SSL certificate chain fails
            logger.warning(f"SSL verification failed for {current_url}. Retrying with verify=False.")
            resp = session.get(
                current_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
                verify=False,
                **kwargs
            )

        # 3. Check for manual redirect
        if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
            if hop >= max_redirects:
                resp.close()
                raise SSRFError(f"Exceeded maximum redirect limit of {max_redirects} hops.")

            location = resp.headers.get("Location")
            if not location:
                # Redirect status without Location header: return as-is
                break

            resp.close()
            # Resolve relative and absolute redirect targets
            next_url = urllib.parse.urljoin(current_url, location)
            current_url = next_url
            continue

        # 4. Enforce max response size of 2 MB
        content_length = resp.headers.get("Content-Length")
        if content_length and content_length.isdigit() and int(content_length) > max_response_bytes:
            resp.close()
            raise SSRFError(f"Response size ({content_length} bytes) exceeds maximum limit of 2 MB.")

        chunks = []
        total_bytes = 0
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                total_bytes += len(chunk)
                if total_bytes > max_response_bytes:
                    resp.close()
                    raise SSRFError("Response size exceeds maximum limit of 2 MB.")
                chunks.append(chunk)

        resp._content = b"".join(chunks)
        return resp

    return resp
