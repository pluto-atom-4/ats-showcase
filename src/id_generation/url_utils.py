import re
from typing import Optional
from urllib.parse import urlparse, urlunparse


def clean_canonical_url(url: str) -> str:
    """Strip tracking params and fragments to keep URL stable for hashing."""
    parsed = urlparse(url)
    # Reconstruct without query string or fragment
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def extract_portal_id(url: str) -> Optional[str]:
    """Extract portal-specific ID from URL (e.g., gh_jid, job ID in path)."""
    parsed = urlparse(url)

    # Try to extract Greenhouse job ID from query params
    if "gh_jid=" in parsed.query:
        match = re.search(r"gh_jid=(\d+)", parsed.query)
        if match:
            return match.group(1)

    # Try to extract numeric ID from URL path (/jobs/12345, /view/98765, etc.)
    path_match = re.search(r"/(\d{8,15})", parsed.path)
    if path_match:
        return path_match.group(1)

    return None


def detect_portal(url: str) -> str:
    """Infer portal type from URL domain and parameters."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Check for Greenhouse job ID in query params (priority)
    if "gh_jid=" in parsed.query:
        return "greenhouse"

    # Check domain-based detection
    if "greenhouse.io" in domain or "job-boards.greenhouse.io" in domain:
        return "greenhouse"
    elif "myworkdayjobs.com" in domain or "wd1.myworkdayjobs.com" in domain:
        return "workday"
    elif "lever.co" in domain:
        return "lever"
    else:
        return "custom"
