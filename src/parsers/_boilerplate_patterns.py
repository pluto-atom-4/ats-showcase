"""Internal boilerplate pattern definitions and utilities (Phase 1 - Issue #230).

Pre-compiled regex patterns for 7 categories of boilerplate in job descriptions:
1. Legal/compliance: "Required Qualifications", "Equal Opportunity", etc.
2. Section headers: "JD:", "Job Description:", "Requirements", etc.
3. Company boilerplate: "We are committed", "Our mission", etc.
4. Time references: "Full-time", "Part-time", "Contract", "Temporary", etc.
5. Salary/benefits: "Competitive salary", "Health benefits", "401k", etc.
6. Special formatting: HTML artifacts (&nbsp;, &amp;), whitespace
7. Navigation text: "Apply Now", "Share", "Save", "Next", etc.

All patterns are pre-compiled for performance (one-time cost at module load).
"""

import logging
import re
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# Category 1: Legal/compliance patterns
LEGAL_COMPLIANCE_PATTERNS = [
    r"(?i)required\s+qualifications(?:\s|$)",
    r"(?i)qualifications\s+experience",
    r"(?i)equal\s+opportunity",
    r"(?i)affirmative\s+action",
    r"(?i)fcra\s+disclosure",
    r"(?i)dbids",
    r"(?i)background\s+check",
    r"(?i)export\s+control",
    r"(?i)security\s+clearance",
    r"(?i)visa\s+sponsorship",
    r"(?i)compliance\s+requirements",
]

# Category 2: Section headers
# Note: "experience" is intentionally excluded (too broad).
SECTION_HEADER_PATTERNS = [
    r"(?i)\bjd\s*[:|-]",
    r"(?i)\bjob\s+description\s*[:|-]",
    r"(?i)\boverview\s*[:|-]",
    r"(?i)\brequirements\s*[:|-]",
    r"(?i)\bqualifications\s*[:|-]",
    r"(?i)\bresponsibilities\s*[:|-]",
    r"(?i)\bkey\s+responsibilities\s*[:|-]",
    r"(?i)\bwhat\s+you\s+will\s+do\s*[:|-]",
    r"(?i)\babout\s+the\s+role\s*[:|-]",
    r"(?i)\bskills\s*[:|-]",
    r"(?i)\btechnical\s+skills\s*[:|-]",
]

# Category 3: Company boilerplate
COMPANY_BOILERPLATE_PATTERNS = [
    r"(?i)we\s+are\s+committed",
    r"(?i)we\s+believe",
    r"(?i)our\s+company\s+culture",
    r"(?i)about\s+\w+\s+(?:inc|ltd|corporation|company)",
    r"(?i)company\s+mission",
    r"(?i)our\s+mission",
    r"(?i)our\s+values",
    r"(?i)diversity\s+and\s+inclusion",
]

# Category 4: Time references (employment type)
# Note: "contract" uses negative lookahead to avoid matching "contractor", "contracting"
TIME_REFERENCE_PATTERNS = [
    r"(?i)full[\s-]?time",
    r"(?i)part[\s-]?time",
    r"(?i)\bcontract\b(?!or|ing)",
    r"(?i)temporary",
    r"(?i)permanent",
    r"(?i)interim",
    r"(?i)shift\s+(?:work|position)",
]

# Category 5: Salary/benefits
SALARY_BENEFITS_PATTERNS = [
    r"(?i)salary.*?(?:\$|year|hour|annually)",
    r"(?i)\$[\d,]+.*?(?:year|hour|annually)",
    r"(?i)(?:competitive\s+)?salary",
    r"(?i)(?:health|medical)\s+benefits",
    r"(?i)401\s*\(\s*k\s*\)",
    r"(?i)retirement\s+(?:plan|benefits)",
    r"(?i)(?:dental|vision|insurance)",
    r"(?i)(?:pto|paid\s+time\s+off|vacation)",
    r"(?i)(?:base\s+)?pay",
    r"(?i)compensation",
    r"(?i)stock\s+options?",
    r"(?i)bonus(?:es)?",
]

# Category 6: Special formatting (HTML artifacts)
SPECIAL_FORMATTING_PATTERNS = [
    r"&nbsp;+",
    r"&amp;",
    r"&lt;|&gt;",
    r"&quot;",
    r"&#\d+;",
    r"\s{2,}",
    r"\n{2,}",
]

# Category 7: Navigation text
NAVIGATION_PATTERNS = [
    r"(?i)apply\s+now",
    r"(?i)share",
    r"(?i)save\s+job",
    r"(?i)next",
    r"(?i)previous",
    r"(?i)back\s+to\s+results",
    r"(?i)view\s+job",
    r"(?i)hide\s+details",
    r"(?i)show\s+more",
    r"(?i)read\s+more",
]

# Compiled once at module load.

_COMPILED_PATTERNS: Dict[str, List[re.Pattern[str]]] = {
    "legal_compliance": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in LEGAL_COMPLIANCE_PATTERNS],
    "section_headers": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in SECTION_HEADER_PATTERNS],
    "company_boilerplate": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in COMPANY_BOILERPLATE_PATTERNS],
    "time_references": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in TIME_REFERENCE_PATTERNS],
    "salary_benefits": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in SALARY_BENEFITS_PATTERNS],
    "special_formatting": [re.compile(p, re.MULTILINE) for p in SPECIAL_FORMATTING_PATTERNS],
    "navigation": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in NAVIGATION_PATTERNS],
}


def get_compiled_patterns() -> Dict[str, List[re.Pattern[str]]]:
    """Get pre-compiled regex patterns for all 7 boilerplate categories.

    Returns:
        Dictionary mapping category name to list of compiled regex patterns.
    """
    return _COMPILED_PATTERNS


def is_boilerplate_phrase(text: str, category: Optional[str] = None) -> bool:
    """Check if text matches boilerplate patterns.

    Args:
        text: Text to check
        category: Optional category to check (if None, checks all categories)

    Returns:
        True if text matches any boilerplate pattern, False otherwise
    """
    if not text or not text.strip():
        return False

    patterns = _COMPILED_PATTERNS.copy()

    if category:
        if category not in _COMPILED_PATTERNS:
            logger.warning(f"Unknown boilerplate category: {category}")
            return False
        patterns = {category: _COMPILED_PATTERNS[category]}

    for pattern_list in patterns.values():
        for compiled_pattern in pattern_list:
            if compiled_pattern.search(text):
                return True

    return False


def remove_boilerplate_fast(text: str, skip_categories: Optional[Set[str]] = None) -> str:
    """Remove boilerplate patterns from text using pre-compiled regexes.

    Args:
        text: Input text to clean
        skip_categories: Set of category names to skip (e.g., {"section_headers"})

    Returns:
        Text with boilerplate removed
    """
    if not text or not text.strip():
        return ""

    cleaned = text
    skip_set = skip_categories or set()

    for category, pattern_list in _COMPILED_PATTERNS.items():
        if category in skip_set:
            continue
        for compiled_pattern in pattern_list:
            cleaned = compiled_pattern.sub("", cleaned)

    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = cleaned.strip()

    logger.debug(
        f"Removed boilerplate: {len(text)} chars → {len(cleaned)} chars "
        f"(reduction: {(len(text) - len(cleaned)) / len(text) * 100:.1f}%)"
    )

    return cleaned


def remove_html_entities(text: str) -> str:
    """Remove or normalize HTML entities in text.

    Handles common HTML entities like &nbsp;, &amp;, etc.

    Args:
        text: Input text with potential HTML entities

    Returns:
        Text with HTML entities removed or normalized
    """
    if not text:
        return ""

    text = text.replace("&nbsp;", " ")

    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&apos;", "'")

    text = re.sub(r"&#\d+;", "", text)

    return text


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    Collapses multiple spaces/newlines to single space/newline.

    Args:
        text: Input text

    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""

    text = re.sub(r" {2,}", " ", text)

    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()
