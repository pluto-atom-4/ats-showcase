"""HTML cleanup and boilerplate removal (Phase 6 - Issue #193).

Removes 7 categories of boilerplate patterns from HTML-parsed job descriptions:
1. Legal/compliance: "Required Qualifications", "Qualifications Experience", etc.
2. Section headers: "JD:", "Job Description:", "Overview", "Requirements"
3. Company boilerplate: "Equal Opportunity", "Affirmative Action", "We are committed"
4. Time references: "Full-time", "Part-time", "Contract", "Temporary"
5. Salary/benefits: "Competitive salary", "Health benefits", "401k"
6. Special formatting: HTML artifacts, line breaks, whitespace
7. Navigation: "Apply Now", "Share", "Save", "Next", "Previous"
"""

import logging
import re
from typing import Set

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
# Note: These patterns target section-header artifacts (header: content).
# Patterns use word boundaries \b to avoid false positives.
# "Experience" is NOT included here (too broad) - it appears in body text.
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


def get_boilerplate_patterns() -> dict[str, list[str]]:
    """Get all 7 categories of boilerplate patterns.

    Returns:
        Dictionary mapping category name to list of regex patterns
    """
    return {
        "legal_compliance": LEGAL_COMPLIANCE_PATTERNS,
        "section_headers": SECTION_HEADER_PATTERNS,
        "company_boilerplate": COMPANY_BOILERPLATE_PATTERNS,
        "time_references": TIME_REFERENCE_PATTERNS,
        "salary_benefits": SALARY_BENEFITS_PATTERNS,
        "special_formatting": SPECIAL_FORMATTING_PATTERNS,
        "navigation": NAVIGATION_PATTERNS,
    }


def is_boilerplate_phrase(text: str, category: str | None = None) -> bool:
    """Check if text matches boilerplate patterns.

    Args:
        text: Text to check
        category: Optional category to check (if None, checks all categories)

    Returns:
        True if text matches boilerplate patterns, False otherwise
    """
    if not text or not text.strip():
        return False

    all_patterns = get_boilerplate_patterns()

    if category:
        if category not in all_patterns:
            logger.warning(f"Unknown boilerplate category: {category}")
            return False
        patterns = {category: all_patterns[category]}
    else:
        patterns = all_patterns

    text_lower = text.lower()
    for pattern_list in patterns.values():
        for pattern in pattern_list:
            if re.search(pattern, text_lower, re.MULTILINE):
                return True

    return False


def remove_boilerplate(text: str) -> str:
    """Remove all boilerplate patterns from text.

    Removes patterns from 7 categories:
    1. Legal/compliance phrases
    2. Section headers
    3. Company boilerplate
    4. Time references (employment type)
    5. Salary/benefits
    6. Special formatting (HTML artifacts)
    7. Navigation text

    Args:
        text: Input text to clean

    Returns:
        Text with boilerplate removed
    """
    if not text or not text.strip():
        return ""

    cleaned = text
    patterns = get_boilerplate_patterns()

    for _category, pattern_list in patterns.items():
        for pattern in pattern_list:
            cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE | re.IGNORECASE)

    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = cleaned.strip()

    logger.debug(
        f"Removed boilerplate: {len(text)} chars → {len(cleaned)} chars "
        f"(reduction: {(len(text) - len(cleaned)) / len(text) * 100:.1f}%)"
    )

    return cleaned


def get_boilerplate_keywords() -> Set[str]:
    """Get flattened set of boilerplate keywords for filtering.

    Returns:
        Set of keywords extracted from all boilerplate patterns
    """
    simple_keywords = [
        "salary",
        "benefits",
        "equal",
        "opportunity",
        "qualifications",
        "requirements",
        "full-time",
        "part-time",
        "contract",
        "temporary",
        "401k",
        "pto",
        "vacation",
        "apply",
        "share",
        "save",
        "export",
        "control",
        "affirmative",
        "action",
        "compliance",
        "background",
        "check",
        "security",
        "clearance",
        "visa",
        "sponsorship",
    ]

    return set(simple_keywords)


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
