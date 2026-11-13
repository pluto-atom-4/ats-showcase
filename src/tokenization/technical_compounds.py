"""Technical compound detection for skill classification.

Issue #191 Phase 2: Enhanced technical compound patterns for reclassification.
Identifies compound phrases that should be technologies, not skills.

Technical compounds identified in Phase 3 output:
- "software development" (6x) - development methodology
- "data processing" (3x) - data pipeline work
- "engineering technology" (3x) - tech framework/platform
- "manufacturing engineering" (3x) - engineering specialization
- "system-level" (3x) - architectural design

Confidence thresholds:
- High confidence (80%+): Exact matches, pattern-based detection
- Medium confidence (60-80%): Multi-word tech+verb combinations

Categories:
1. Development Compounds: software development, engineering practices
2. Data Compounds: data processing, big data, ETL
3. Infrastructure Compounds: cloud services, deployment, orchestration
4. Architecture Compounds: system-level, integration, design patterns
"""

# High-confidence exact match patterns (Issue #191 + historical)
TECHNICAL_COMPOUND_PATTERNS = {
    # Software Development Compounds (Issue #191)
    "software development",
    "software engineering",
    "software development engineer",
    "software development platform",
    "software development lifecycle",
    "software development practices",
    "software development methodology",
    # Data Processing Compounds (Issue #191)
    "data processing",
    "data processing pipeline",
    "data processing system",
    "data processing infrastructure",
    "big data processing",
    "data processing workflow",
    "etl pipeline",
    "data pipeline",
    # Engineering Technology Compounds (Issue #191)
    "engineering technology",
    "engineering technology platform",
    "engineering technology stack",
    "engineering technology framework",
    "engineering technology solution",
    "engineering technology system",
    # Manufacturing Engineering Compounds (Issue #191)
    "manufacturing engineering",
    "manufacturing engineering process",
    "manufacturing engineering technology",
    "manufacturing engineering automation",
    "manufacturing engineering design",
    "manufacturing engineering system",
    # System-Level Compounds (Issue #191)
    "system-level",
    "system-level design",
    "system-level architecture",
    "system-level integration",
    "system-level requirements",
    "system-level planning",
    "system-level optimization",
    # Framework/library compounds
    "spring framework",
    "spring boot",
    "react native",
    "express.js",
    "web framework",
    "api framework",
    "testing framework",
    "javascript framework",
    "python framework",
    # Service compounds
    "web service",
    "microservice",
    "microservices",
    "cloud service",
    "aws service",
    "api service",
    "rest service",
    "soap service",
    # Database compounds
    "sql database",
    "nosql database",
    "relational database",
    "distributed database",
    "time series database",
    # Language/tool combinations
    "python django",
    "python flask",
    "javascript react",
    "node.js",
    "python pandas",
    "python numpy",
    # Infrastructure compounds
    "cloud infrastructure",
    "infrastructure as code",
    "container orchestration",
    "kubernetes cluster",
    "docker container",
    "ci/cd pipeline",
    # Architecture patterns
    "microservices architecture",
    "event-driven architecture",
    "distributed system",
    "scalable system",
    "high availability",
}

# Medium-confidence keyword patterns for detection
MULTI_WORD_KEYWORDS = {
    "framework",
    "library",
    "database",
    "service",
    "platform",
    "application",
    "system",
    "tool",
    "utility",
    "plugin",
    "extension",
    "architecture",
    "infrastructure",
    "pipeline",
    "workflow",
    "process",
}

# Issue #191 specific keywords for enhanced detection
ISSUE_191_KEYWORDS = {
    "software",
    "data processing",
    "engineering technology",
    "manufacturing",
    "system-level",
    "system",
}


def is_technical_compound(phrase: str) -> bool:
    """Check if phrase is a technical compound that should be a technology not a skill.

    Phase 2 Logic (Confidence Tiers):
    1. Exact match against known compounds (80%+ confidence)
    2. Multi-word detection with tech keywords (60-75% confidence)
    3. Issue #191 pattern detection (50-60% confidence)

    Args:
        phrase: Text to check

    Returns:
        True if phrase is a technical compound, False otherwise

    Examples:
        >>> is_technical_compound("software development")
        True
        >>> is_technical_compound("data processing")
        True
        >>> is_technical_compound("python")
        False
        >>> is_technical_compound("leadership")
        False
    """
    phrase_lower = phrase.lower().strip()

    if not phrase_lower or len(phrase_lower) < 3:
        return False

    words = phrase_lower.split()

    # Tier 1: exact match against known compounds
    if phrase_lower in TECHNICAL_COMPOUND_PATTERNS:
        return True

    # Tier 2: multi-word tech compounds; single words are excluded to avoid false positives
    if len(words) >= 2:
        for kw in MULTI_WORD_KEYWORDS:
            if kw in phrase_lower:
                return True

    # Tier 3: Pattern-based detection for Issue #191 compounds (50-60% confidence)
    # A multi-word phrase containing an Issue #191 keyword is likely a compound.
    if len(words) >= 2:
        for kw in ISSUE_191_KEYWORDS:
            if kw in phrase_lower:
                # Only match as part of a phrase (e.g. "software development"), not the keyword alone.
                if phrase_lower != kw and phrase_lower != kw.lower():
                    return True

    return False


def get_technical_compounds() -> set[str]:
    """Get all known technical compound patterns.

    Returns:
        Set of 60+ technical compound phrases (exact matches)

    Examples:
        >>> compounds = get_technical_compounds()
        >>> "software development" in compounds
        True
        >>> len(compounds) > 50
        True
    """
    return TECHNICAL_COMPOUND_PATTERNS.copy()


def get_compound_categories() -> dict[str, list[str]]:
    """Get technical compounds organized by category.

    Returns:
        Dictionary mapping category names to lists of compound phrases

    Categories:
        - development: Software development, engineering practices
        - data: Data processing, ETL, data pipelines
        - infrastructure: Cloud services, deployment, orchestration
        - architecture: System-level, integration, design patterns
        - frameworks: Web frameworks, libraries, tools
        - services: API services, microservices
        - database: SQL, NoSQL, distributed databases
    """
    categories = {
        "development": [
            "software development",
            "software engineering",
            "software development platform",
            "software development lifecycle",
        ],
        "data": [
            "data processing",
            "data processing pipeline",
            "data processing system",
            "big data processing",
            "etl pipeline",
            "data pipeline",
        ],
        "infrastructure": [
            "cloud infrastructure",
            "infrastructure as code",
            "container orchestration",
            "ci/cd pipeline",
        ],
        "architecture": [
            "system-level",
            "system-level design",
            "system-level architecture",
            "microservices architecture",
            "distributed system",
        ],
        "engineering": [
            "engineering technology",
            "manufacturing engineering",
            "engineering technology platform",
            "manufacturing engineering process",
        ],
        "frameworks": [
            "spring framework",
            "spring boot",
            "react native",
            "web framework",
            "javascript framework",
            "python framework",
        ],
        "services": [
            "web service",
            "microservice",
            "cloud service",
            "aws service",
            "rest service",
        ],
        "database": [
            "sql database",
            "nosql database",
            "relational database",
            "distributed database",
            "time series database",
        ],
    }
    return categories


def get_confidence_score(phrase: str) -> float:
    """Get confidence score for compound classification (0.0 to 1.0).

    Phase 2 Confidence Tiers:
    - 0.8-1.0: Exact match in TECHNICAL_COMPOUND_PATTERNS
    - 0.6-0.75: Multi-word phrase containing tech keyword
    - 0.5-0.6: Contains Issue #191 keyword and multi-word
    - 0.0: Not a compound

    Args:
        phrase: Text to evaluate

    Returns:
        Confidence score (0.0 to 1.0)

    Examples:
        >>> get_confidence_score("software development")  # Exact match
        0.95
        >>> get_confidence_score("web framework")  # Contains 'framework'
        0.7
        >>> get_confidence_score("python")  # Not compound
        0.0
    """
    phrase_lower = phrase.lower().strip()

    if not phrase_lower or len(phrase_lower) < 3:
        return 0.0

    words = phrase_lower.split()

    # Tier 1: exact match
    if phrase_lower in TECHNICAL_COMPOUND_PATTERNS:
        return 0.95

    # Tier 2: multi-word with a tech keyword
    if len(words) >= 2:
        for kw in MULTI_WORD_KEYWORDS:
            if kw in phrase_lower:
                return 0.70

    # Tier 3: Issue #191 pattern (50-60% confidence)
    if len(words) >= 2:
        for kw in ISSUE_191_KEYWORDS:
            if kw in phrase_lower and phrase_lower != kw:
                return 0.55

    return 0.0


def reclassify_compound(phrase: str, confidence_threshold: float = 0.5) -> bool:
    """Determine if a phrase should be reclassified from skills to technologies.

    Args:
        phrase: Text to evaluate
        confidence_threshold: Minimum confidence score to reclassify (default 0.5)

    Returns:
        True if should be reclassified, False otherwise

    Examples:
        >>> reclassify_compound("software development")
        True
        >>> reclassify_compound("leadership", confidence_threshold=0.5)
        False
    """
    return get_confidence_score(phrase) >= confidence_threshold
