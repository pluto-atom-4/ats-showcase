"""Domain detection and domain-specific keyphrase sets."""

import re
from enum import Enum
from typing import Set


class Domain(str, Enum):
    """Job domain types."""

    AEROSPACE = "aerospace"
    SOFTWARE = "software"
    DEFENSE = "defense"
    HARDWARE = "hardware"
    GENERAL = "general"


# Domain detection keywords
DOMAIN_SIGNALS = {
    Domain.AEROSPACE: [
        r"\baerospace\b",
        r"\bflight\s+(?:operations|vehicle|dynamics)",
        r"\bGNC\b|guidance\s+(?:and\s+)?control",
        r"\bAUV\b|autonomous\s+vehicle",
        r"\b(?:launch|takeoff|climb|descent)\b",
        r"\baircraft\s+(?:performance|dynamics)",
        r"\btelemetry\s+(?:processing|system)",
        r"\bATOP\b|optimal\s+performance",
    ],
    Domain.DEFENSE: [
        r"\b(?:Defense|DoD|military)\b",
        r"\bclassified\b|Top\s+Secret|Secret\s+Clearance",
        r"\bRocky\s+program\b|weapons\s+system",
        r"\bclosed\s+area\s+development",
        r"\bGFE\b|government\s+furnished",
    ],
    Domain.SOFTWARE: [
        r"\bdistributed\s+(?:system|software)",
        r"\bcloud\s+(?:service|infrastructure|deployment)",
        r"\bDevOps\b|CI/CD|microservices",
        r"\b(?:API|REST|GraphQL|OpenAPI)\b",
        r"\bscalable.*system\b|system.*scalable",
        r"\bsensor\s+data\b|data\s+(?:transformation|analytics|pipeline)",
        r"\b(?:ARINC|binary\s+data|telemetry)\b",
    ],
    Domain.HARDWARE: [
        r"\bASIC\b|FPGA\b|circuit\b",
        r"\bVerilog\b|SystemVerilog\b",
        r"\bHDL\b|hardware\s+design",
        r"\bsynthesis\b|place\s+and\s+route",
        r"\bDFT\b|formal\s+verification",
    ],
}


def detect_domain(job_description: str) -> Domain:
    """Detect job domain from description text."""
    text_lower = job_description.lower()

    # Count signals per domain
    domain_scores = dict.fromkeys(Domain, 0)

    for domain, patterns in DOMAIN_SIGNALS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                domain_scores[domain] += 1

    # Return domain with highest score, or GENERAL if no signals
    best_domain = max(domain_scores, key=lambda d: domain_scores[d])
    if domain_scores[best_domain] > 0:
        return best_domain
    return Domain.GENERAL


# Aerospace domain keyphrases
AEROSPACE_KEYPHRASES = {
    # Core G&C concepts
    "Guidance and Control",
    "G&C algorithms",
    # Design & analysis
    "Conceptual level design",
    "Post flight analysis",
    "Architectural decision making",
    # Leadership & team
    "Team leadership",
    "Staff coaching",
    "Mentoring",
    "Technical oversight",
    # Communication & collaboration
    "Collaborative skills",
    "Cross-functional communication",
    "Technical planning",
    # Software practices
    "Software integration",
    "Software development",
    "Unit testing",
    "Verification and validation",
    # Review & oversight
    "Design reviews",
    "Systems analysis",
    "Technical coaching",
    # Operations
    "Launch operations support",
    "Test operations support",
    # Testing & validation
    "Hardware-in-the-loop testing",
    "Vehicle test campaigns",
}

# Software domain keyphrases (Boeing, distributed systems)

SOFTWARE_KEYPHRASES = {
    # Architecture & design
    "Software architecture",
    "System design",
    "API design",
    "Database design",
    "Architecture review",
    # Development practices
    "Hands-on software development",
    "Code reviews",
    "Design walkthroughs",
    "Technical documentation",
    # Data & analytics
    "Binary data transformation",
    "Time-series data analytics",
    "Data collection",
    "Data preparation",
    "Quantitative analysis",
    "Statistical analysis",
    # Sensor & calibration
    "Sensor data calibration",
    "Sensor data synchronization",
    "Integrity check implementation",
    "Engineering data interpretation",
    "Engineering drawing interpretation",
    # Storage & systems
    "Storage architecture design",
    "Systems maintenance",
    # Testing & quality
    "Code quality assurance",
    "Testing strategy",
    # Cloud & deployment
    "Cloud service deployment",
    "CI/CD implementation",
    # Leadership & management
    "Technical leadership",
    "Project management",
    "Technical coaching",
    "Mentoring",
    # Analysis & planning
    "Problem decomposition",
    "Requirements analysis",
    "Technical communication",
    "Technology evaluation",
}

# Defense domain keyphrases (military, classified systems); overlaps software but adds defense-specific concepts

DEFENSE_KEYPHRASES = {
    # Architecture & design
    "Software architecture",
    "System design",
    "API design",
    "Database design",
    # Development & implementation
    "Hands-on software development",
    "Software development",
    "Code reviews",
    "Design walkthroughs",
    # Systems & maintenance
    "Systems maintenance",
    "Technical oversight",
    # Data & transformation
    "Binary data transformation",
    "Data transformation",
    "Time-series data analytics",
    "Sensor data calibration",
    "Sensor data synchronization",
    # Integration & testing
    "Software integration",
    "Integration testing",
    "Code quality assurance",
    "Testing strategy",
    # Architecture & deployment
    "Cloud service deployment",
    "Infrastructure management",
    # Verification
    "Verification and validation",
    # Integrity
    "Integrity check implementation",
    # Analysis
    "Engineering data interpretation",
    "Quantitative analysis",
    "Statistical analysis",
    "Problem decomposition",
    "Requirements analysis",
    # Documentation
    "Software documentation",
    "Technical documentation",
    # Leadership
    "Technical leadership",
    "Technical coaching",
    "Mentoring",
    "Project management",
    # Communication
    "Technical communication",
    "Cross-functional communication",
}

# Hardware domain keyphrases (ASIC, FPGA, chip design)

HARDWARE_KEYPHRASES = {
    # Design & verification
    "Formal verification",
    "Clock gating",
    "CDC analysis",
    "RDC analysis",
    "Lint checking",
    "Gate simulation",
    "Timing analysis",
    # Design entry
    "Verilog design",
    "SystemVerilog design",
    "SoC design",
    "ASIC design",
    # Verification
    "SOC verification",
    "Performance optimization",
    "Power optimization",
    "DFT implementation",
    # Integration & support
    "Systems maintenance",
    "Technical documentation",
    "Technical oversight",
}

# General/cross-domain keyphrases

GENERAL_KEYPHRASES = {
    "Technical leadership",
    "Mentoring",
    "Technical planning",
    "Software development",
    "Code reviews",
    "Design reviews",
    "Technical communication",
    "Problem decomposition",
    "Project management",
    "Technical coaching",
}


def get_keyphrases(domain: Domain) -> Set[str]:
    """Get keyphrase set for specified domain."""
    if domain == Domain.AEROSPACE:
        return AEROSPACE_KEYPHRASES
    elif domain == Domain.DEFENSE:
        return DEFENSE_KEYPHRASES
    elif domain == Domain.SOFTWARE:
        return SOFTWARE_KEYPHRASES
    elif domain == Domain.HARDWARE:
        return HARDWARE_KEYPHRASES
    else:
        return GENERAL_KEYPHRASES


def get_keyphrases_auto(job_description: str) -> Set[str]:
    """Auto-detect domain and return appropriate keyphrases."""
    domain = detect_domain(job_description)
    return get_keyphrases(domain)
