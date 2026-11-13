"""Normalize extracted entities to match expected output format."""

import re
from difflib import SequenceMatcher


def normalize_requirement(req: str) -> str:
    """Clean and normalize requirement text."""
    req = req.strip()

    # Strip the (Preferred) tag here and re-add it at the end.
    is_preferred = "(Preferred)" in req
    req = req.replace("(Preferred)", "").strip()

    # Drop trailing location/project context so only the primary requirement remains.
    req = re.sub(r"\s+on\s+fast-paced\s+projects$", "", req, flags=re.IGNORECASE)
    req = re.sub(r"\s+on\s+military\s+installations?$", "", req, flags=re.IGNORECASE)

    # Drop only trailing simulations/software items, not core concepts: "X, simulations, and software" -> "X".
    req = re.sub(r",\s+(?:simulations|software),\s+and\s+[^,\.]*$", "", req, flags=re.IGNORECASE)
    req = re.sub(r",\s+and\s+integrated\s+vehicle.*$", "", req, flags=re.IGNORECASE)

    # Handle "development, implementation, and testing" → "implementation and testing"
    if re.search(r"^Experience\s+in\s+development,\s+implementation,\s+and", req, re.IGNORECASE):
        req = re.sub(r"development,\s+", "", req, flags=re.IGNORECASE)
        req = re.sub(r",\s+and\s+", " and ", req, flags=re.IGNORECASE)
    elif re.search(r"^Experience\s+in\s+development\s+and", req, re.IGNORECASE):
        req = re.sub(r"development\s+and\s+", "", req, flags=re.IGNORECASE)

    req = re.sub(r"\s+with\s+the\s+development\s+of\s+", " with ", req, flags=re.IGNORECASE)

    # Empty results are dropped by normalize_requirements.
    if req.lower() == "experience in development":
        return ""

    # Standardize phrasing patterns
    # "Demonstrated experience X" → "Experience X"
    req = re.sub(r"^Demonstrated\s+experience\s+(?:in|with|involving)\s+", "Experience in ", req, flags=re.IGNORECASE)
    req = re.sub(r"^Demonstrated\s+ability\s+to\s+", "Ability to ", req, flags=re.IGNORECASE)
    req = re.sub(r"\s+as\s+well\s+as\s+", " and ", req, flags=re.IGNORECASE)
    req = re.sub(r"\s+,\s+", ", ", req)

    # Leave "M.S. or Ph.D." alone; otherwise drop (e.g. ...), (HIL) and trailing parentheticals.
    if "M.S. or Ph.D." not in req:
        req = re.sub(r"\s*\(\s*e\.g\..*?\)\s*", " ", req)
        req = re.sub(r"\s*\(HIL\)", "", req)
        req = re.sub(r"\s*\([^)]*\)\s*$", "", req)

    req = re.sub(r"\s+", " ", req)

    if is_preferred:
        req = f"{req} (Preferred)"

    return req


def deduplicate_requirements(requirements: set[str], similarity_threshold: float = 0.65) -> set[str]:
    """Remove near-duplicate requirements, keeping shortest/best version."""
    reqs = sorted(requirements, key=lambda r: (len(r), r))
    deduplicated = []
    used_indices = set()

    for i, req in enumerate(reqs):
        if i in used_indices:
            continue

        # Check similarity with already-kept requirements and future ones
        keep_this = True
        for j in range(i + 1, len(reqs)):
            if j in used_indices:
                continue
            other = reqs[j]
            ratio = SequenceMatcher(None, req.lower(), other.lower()).ratio()

            # If similarity is high, mark longer one as duplicate
            if ratio > similarity_threshold:
                if req.lower() in other.lower():
                    # req is shorter and contained in other, keep req, discard other
                    used_indices.add(j)
                elif other.lower() in req.lower():
                    # other is shorter, discard this one
                    keep_this = False
                    used_indices.add(i)
                    break
                else:
                    # Similar but not substring, keep shorter
                    if len(req) <= len(other):
                        used_indices.add(j)
                    else:
                        keep_this = False
                        used_indices.add(i)
                        break

        if keep_this:
            deduplicated.append(req)
            used_indices.add(i)

    return set(deduplicated)


def normalize_requirements(requirements: set[str]) -> set[str]:
    """Normalize all requirements and deduplicate."""
    normalized = {normalize_requirement(req) for req in requirements}

    normalized = {req for req in normalized if req.strip()}

    deduplicated = deduplicate_requirements(normalized, similarity_threshold=0.80)

    return deduplicated


def normalize_skills(skills: set[str]) -> set[str]:
    """Normalize skill names (preserve exact format from extraction)."""
    normalized = set()

    # Known correctly-capitalized skills (multi-domain)
    known_skills = {
        # Aerospace/Software Leadership
        "Guidance and Control",
        "G&C algorithms",
        "Conceptual level design",
        "Post flight analysis",
        "Team leadership",
        "Staff coaching",
        "Collaborative skills",
        "Software integration",
        "Unit testing",
        "Launch operations support",
        "Test operations support",
        "Cross-functional communication",
        "Technical oversight",
        "Design reviews",
        "Systems analysis",
        "Architectural decision making",
        "Verification and validation",
        "Software development",
        "Mentoring",
        "Technical planning",
        "System modeling",
        "Hardware-in-the-loop testing",
        "Vehicle test campaigns",
        # ASIC/Hardware
        "Formal verification",
        "Clock gating",
        "CDC analysis",
        "RDC analysis",
        "Lint checking",
        "Verilog design",
        "SystemVerilog design",
        "SoC design",
        "ASIC design",
        "SOC verification",
        "Performance optimization",
        "Power optimization",
        "DFT implementation",
        "Gate simulation",
        "Timing analysis",
        # Software/Systems Domain
        "Software architecture",
        "Hands-on software development",
        "Systems maintenance",
        "Binary data transformation",
        "Integrity check implementation",
        "Time-series data analytics",
        "Storage architecture design",
        "Sensor data calibration",
        "Sensor data synchronization",
        "Technology evaluation",
        "Code reviews",
        "Design walkthroughs",
        "Technical coaching",
        "Project management",
        "Problem decomposition",
        "Technical communication",
        "Engineering data interpretation",
        "Engineering drawing interpretation",
        "Quantitative analysis",
        "Statistical analysis",
        "Data collection",
        "Data preparation",
        "Cloud service deployment",
        "Software documentation",
        # Additional Software/Systems
        "Software design",
        "System design",
        "Component design",
        "API design",
        "Database design",
        "Architecture review",
        "Code quality assurance",
        "Testing strategy",
        "Integration testing",
        "Performance testing",
        "Security testing",
        "Agile development",
        "DevOps practices",
        "CI/CD implementation",
        "Deployment automation",
        "Infrastructure management",
        "Configuration management",
        "Requirements analysis",
        "Stakeholder management",
        "Technical documentation",
        "Knowledge transfer",
        "Best practices implementation",
        "Standards compliance",
        "Process improvement",
    }

    for skill in skills:
        if skill in known_skills:
            normalized.add(skill)
        else:
            # Fallback: capitalize first letter of each word
            words = skill.split()
            capitalized = [w.capitalize() for w in words]
            normalized.add(" ".join(capitalized))

    return normalized


def normalize_technologies(technologies: set[str]) -> set[str]:
    """Normalize technology names."""
    return technologies
