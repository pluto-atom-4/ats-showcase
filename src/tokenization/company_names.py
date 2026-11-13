"""Company names and organization keywords for entity filtering (Issue #194 Phase 7).

Organized by industry source to maintain semantic clarity and facilitate
future expansion. Prevents company names from being incorrectly extracted
as skills/technologies during requirement extraction.

Phase 7 (Issue #194) taxonomy includes:
- Aerospace/Defense (7): Boeing, Lockheed, Raytheon, Northrop, General Dynamics, SpaceX, Blue Origin
- Technology (9): Apple, Google, Microsoft, Meta, Amazon, Tesla, Intel, Nvidia, IBM
- Universities (8): UW, MIT, Stanford, Berkeley, CMU, Caltech, Princeton, Yale
- Robotics/Manufacturing (6): Carbon, Universal, ABB, KUKA, Boston Dynamics, ISAC
- Other Organizations (12+): staffing agencies, consulting firms, government agencies
"""

# Company keywords organized by industry source
COMPANY_KEYWORDS = {
    # Aerospace/Defense
    "aerospace_defense": {
        "boeing",
        "lockheed",
        "lockheed martin",
        "raytheon",
        "northrop",
        "northrop grumman",
        "general dynamics",
    },
    # Technology Giants
    "technology": {
        "apple",
        "google",
        "microsoft",
        "meta",
        "amazon",
        "tesla",
        "intel",
        "nvidia",
        "ibm",
    },
    # Space/Advanced Technology
    "space_tech": {
        "spacex",
        "blue origin",
    },
    # Universities & Academic Institutions
    "universities": {
        "uw",
        "mit",
        "stanford",
        "berkeley",
        "cmu",
        "caltech",
        "princeton",
        "yale",
    },
    # Robotics & Robotics Manufacturing
    "robotics_manufacturing": {
        "carbon",
        "universal",
        "abb",
        "kuka",
        "boston dynamics",
        "isac",
    },
    # Staffing & Recruitment Agencies
    "staffing_agencies": {
        "heidrick",
        "recruiter",
        "staffing",
        "talent",
        "agency",
    },
    # Consulting & Professional Services
    "consulting": {
        "consulting",
        "accenture",
        "deloitte",
        "pwc",
    },
    # Government & Regulatory Bodies
    "government": {
        "government",
        "federal",
        "department of",
    },
    # Financial & Business Services
    "financial_services": {
        "goldman",
        "jpmorgan",
        "bank of america",
    },
}

COMPANY_NAMES = set()
for category_companies in COMPANY_KEYWORDS.values():
    COMPANY_NAMES.update(category_companies)


def is_company_keyword(text: str, word_boundary: bool = True) -> bool:
    """Check if text matches a company name keyword.

    Args:
        text: Text to check
        word_boundary: If True, use word-boundary matching (case-insensitive);
                      if False, use substring matching

    Returns:
        True if text matches a company keyword, False otherwise
    """
    if not text or not text.strip():
        return False

    text_lower = text.lower().strip()

    if word_boundary:
        return text_lower in COMPANY_NAMES

    else:
        for company in COMPANY_NAMES:
            if company in text_lower:
                return True
        return False


def get_company_keywords() -> set[str]:
    """Get all company keywords.

    Returns:
        Set of all company name terms across all sources (50+ terms)
    """
    return COMPANY_NAMES.copy()


def get_company_keywords_by_source(source: str) -> set[str]:
    """Get company keywords for a specific industry source.

    Args:
        source: One of: aerospace_defense, technology, space_tech, universities,
               robotics_manufacturing, staffing_agencies, consulting, government,
               financial_services

    Returns:
        Set of company keywords in that source, or empty set if source not found
    """
    return COMPANY_KEYWORDS.get(source, set()).copy()


def get_company_sources() -> list[str]:
    """Get list of company keyword sources.

    Returns:
        List of source category names
    """
    return list(COMPANY_KEYWORDS.keys())


def count_company_keywords() -> dict[str, int]:
    """Get count of company keywords by source.

    Returns:
        Dict mapping source name to keyword count
    """
    return {source: len(keywords) for source, keywords in COMPANY_KEYWORDS.items()}
