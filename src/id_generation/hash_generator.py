import hashlib
import re
from typing import Optional
from urllib.parse import parse_qsl, urlparse

from src.id_generation.url_utils import (
    canonical_url_with_query_keys,
    detect_portal,
    extract_portal_id,
)

# Query params that discriminate jobs on custom portals (#763).
CUSTOM_PORTAL_ID_KEYS = ("jobId",)


def normalize_field(text: str) -> str:
    """Normalize text field: lowercase, remove non-alphanumeric chars."""
    if not text:
        return ""
    # Lowercase and remove all non-alphanumeric characters
    return re.sub(r"\W+", "", text.lower())


def _custom_portal_anchor(url: str) -> Optional[str]:
    """Anchor for a custom-portal URL carrying a non-empty jobId; else None (#763)."""
    query = parse_qsl(urlparse(url).query, keep_blank_values=False)
    if not any(k in CUSTOM_PORTAL_ID_KEYS for k, _ in query):
        return None
    return canonical_url_with_query_keys(url, CUSTOM_PORTAL_ID_KEYS)


def generate_job_id(
    company: str,
    title: str,
    location: str,
    url: Optional[str] = None,
    portal: Optional[str] = None,
) -> str:
    """
    Generate stable, unique job ID using deterministic hashing.

    Args:
        company: Company name
        title: Job title
        location: Job location
        url: Job posting URL (optional, used to extract portal ID)
        portal: Portal type (optional, inferred from URL if not provided)

    Returns:
        Job ID in format: "{portal}:{hash[:16]}"
        Example: "greenhouse:a1b2c3d4e5f6g7h8"
    """
    # Normalize inputs
    norm_company = normalize_field(company)
    norm_title = normalize_field(title)
    norm_location = normalize_field(location)

    # Try to extract portal-specific ID from URL
    anchor = None
    if url:
        anchor = extract_portal_id(url)
        if not portal:
            portal = detect_portal(url)

    # Default portal if still not detected
    if not portal:
        portal = "custom"

    # Custom portals with a jobId query param: keep only that param in the anchor
    custom_anchor = _custom_portal_anchor(url) if url and portal == "custom" else None

    # Anchor priority (#768): custom jobId > extracted portal id > cleaned URL > company
    if custom_anchor is not None:
        anchor = custom_anchor
    elif anchor:
        pass  # keep extracted portal id (gh_jid or 8-15 digit path id)
    elif url:
        from src.id_generation.url_utils import clean_canonical_url

        anchor = clean_canonical_url(url)
    else:
        # Fallback if no URL provided
        anchor = norm_company

    # Create payload for hashing
    payload = f"{norm_company}|{norm_title}|{norm_location}|{anchor}"

    # Generate SHA-256 hash and take first 16 chars
    hash_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return f"{portal}:{hash_digest[:16]}"
