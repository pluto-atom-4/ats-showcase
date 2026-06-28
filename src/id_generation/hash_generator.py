import hashlib
import re
from typing import Optional

from src.id_generation.url_utils import detect_portal, extract_portal_id


def normalize_field(text: str) -> str:
    """Normalize text field: lowercase, remove non-alphanumeric chars."""
    if not text:
        return ""
    # Lowercase and remove all non-alphanumeric characters
    return re.sub(r"\W+", "", text.lower())


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

    # If no portal ID found, use canonical URL as anchor
    if not anchor and url:
        from src.id_generation.url_utils import clean_canonical_url

        anchor = clean_canonical_url(url)
    else:
        # Fallback if no URL provided
        anchor = norm_company

    # Default portal if still not detected
    if not portal:
        portal = "custom"

    # Create payload for hashing
    payload = f"{norm_company}|{norm_title}|{norm_location}|{anchor}"

    # Generate SHA-256 hash and take first 16 chars
    hash_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return f"{portal}:{hash_digest[:16]}"
