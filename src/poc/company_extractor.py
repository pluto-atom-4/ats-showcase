"""Company name extraction from job descriptions.

Implements multiple fallback patterns to extract company names from markdown
job descriptions with varying format and structure.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def extract_company_name_enhanced(markdown: str) -> Optional[str]:
    """Extract company name from markdown with enhanced fallback chain.

    Tries patterns in order:
    1. # Company Name (h1 header)
    2. ## Company Name section
    3. company: Name field
    4. employer: Name field
    5. Prose mention (capital company name near start)
    6. Capitalized phrase pattern

    Args:
        markdown: Markdown job description

    Returns:
        Company name or None if not found
    """
    patterns = [
        (r"^#\s+([^\n]+)", "h1"),
        (r"^##\s+company\b.*?\n([^\n]+)", "h2_company"),
        (r"company:\s*([^\n]+)", "company_field"),
        (r"employer:\s*([^\n]+)", "employer_field"),
        (
            r"\b([A-Z][a-zA-Z0-9\s&]*(?:Robotics|Corp|Inc|Ltd|LLC|Technology|AI|Systems|Software|Services))\b",
            "prose_mention",
        ),
        (r"\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)?)\s+(?:is the|is a|has|announces)", "capitalized_phrase"),
    ]

    for pattern, _name in patterns:
        match = re.search(pattern, markdown, re.MULTILINE | re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            if company and len(company) > 1:
                return company

    return None


def extract_company_name(markdown: str) -> Optional[str]:
    """Legacy function: delegates to enhanced version.

    Args:
        markdown: Markdown job description

    Returns:
        Company name or None if not found
    """
    return extract_company_name_enhanced(markdown)
