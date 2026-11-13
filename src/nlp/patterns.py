"""Pattern definitions for NER extraction."""

import re
from typing import Set

# Technology stack patterns (exact matches + variations)
TECH_PATTERNS = {
    # Languages
    "Java": [r"\bJava\b(?!\s*Script)"],
    "C++": [r"\bC\+\+\b"],
    "C": [r"\bC\b(?!\+)"],
    "C#": [r"\bC#\b"],
    "Python": [r"\bPython\b"],
    "JavaScript": [r"\bJavaScript\b", r"\bJS\b"],
    "TypeScript": [r"\bTypeScript\b"],
    "Go": [r"\bGo\b(?!\s+(?:language|programming))"],
    "Rust": [r"\bRust\b"],
    "Verilog": [r"\bVerilog\b"],
    "SystemVerilog": [r"\bSystemVerilog\b", r"System\s+Verilog"],
    # Data/Big Data
    "Apache Parquet": [r"Apache\s+Parquet", r"\bParquet\b"],
    "Apache ORC": [r"Apache\s+ORC", r"\bORC\b(?!\s+orchestra)"],
    "HDF5": [r"\bHDF5\b", r"\bHDF\s+5\b"],
    "Delta Lake": [r"Delta\s+Lake"],
    "Apache Spark": [r"Apache\s+Spark", r"\bSpark\b"],
    "Hadoop": [r"\bHadoop\b"],
    "Elasticsearch": [r"\bElasticsearch\b"],
    # Databases
    "PostgreSQL": [r"\bPostgreSQL\b", r"\bPostgres\b"],
    "MongoDB": [r"\bMongoDB\b"],
    "MySQL": [r"\bMySQL\b"],
    "Oracle": [r"\bOracle\s+Database\b", r"\bOracle\b(?!\s+Corporation)"],
    # Frameworks
    "Spring Framework": [r"Spring\s+Framework", r"\bSpring\b(?!\s+Boot)"],
    "Spring Boot": [r"Spring\s+Boot"],
    "React": [r"\bReact\b", r"\bReactJS\b"],
    "Angular": [r"\bAngular\b"],
    "Vue": [r"\bVue\.js\b", r"\bVue\b"],
    "Hibernate": [r"\bHibernate\b"],
    # ARINC protocols
    "ARINC 429": [r"ARINC\s+429"],
    "ARINC 717": [r"ARINC\s+717"],
    "ARINC 767": [r"ARINC\s+767"],
    # DevOps/Cloud
    "AWS": [r"\bAWS\b", r"\bAmazon\s+Web\s+Services\b"],
    "Azure": [r"\bAzure\b"],
    "Kubernetes": [r"\bKubernetes\b", r"\bK8s\b"],
    "Docker": [r"\bDocker\b"],
    "Jenkins": [r"\bJenkins\b"],
    "Git": [r"\bGit\b"],
    "Maven": [r"\bMaven\b"],
    "Gradle": [r"\bGradle\b"],
    # APIs/Standards
    "REST": [r"\bREST\b", r"\bRESTful\b"],
    "GraphQL": [r"\bGraphQL\b"],
    "OpenAPI": [r"\bOpenAPI\b"],
    "SOAP": [r"\bSOAP\b"],
    # Other
    "AI": [r"\bAI\b", r"\bartificial\s+intelligence\b"],
    "MATLAB": [r"\bMATLAB\b"],
    "Simulink": [r"\bSimulink\b"],
    "AI-assisted coding techniques": [
        r"AI-assisted\s+coding",
        r"AI\s+coding\s+techniques",
    ],
    "DOORS Next Generation": [r"DOORS\s+Next\s+Generation", r"DOORS\s+NG"],
    "JIRA": [r"\bJIRA\b"],
    "ARM": [r"\bARM\b"],
}

# Skill keyphrases extracted directly from job requirements; multi-domain.
SKILL_KEYPHRASES = {
    # Aerospace/Software Leadership (Blue Origin)
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
    # ASIC/Hardware Design
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
    # Software/Systems Domain (Boeing + general)
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
    # Additional Software/Systems patterns
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

# Fallback: single keywords for skills extraction
SKILL_KEYWORDS = {
    "leadership",
    "team leadership",
    "staff coaching",
    "mentoring",
    "management",
    "verification",
    "validation",
    "integration",
    "testing",
    "simulation",
    "modeling",
    "design",
    "architecture",
    "algorithm",
    "optimization",
    "performance",
    "analysis",
    "planning",
    "review",
    "oversight",
    "communication",
    "collaboration",
    "autonomy",
}

REQUIREMENT_PATTERNS = {
    "years_experience": r"(\d+)\+?\s+years\s+(?:of\s+)?experience",
    "degree": r"(?:BS|MS|B\.S\.|M\.S\.|PhD|Ph\.D\.)",
    "skill_requirement": r"(?:required|must|must have|essential|needed)",
    "citizen_status": r"(?:U\.S\.\s+citizen|permanent\s+resident|refugee|asylee)",
}

# Bullet lines starting with "*", then with "•" or "-".
SKILL_EXTRACTION_PATTERNS = [
    r"(?:^|\n)\*\s+(.+?)(?:\n|\Z)",
    r"(?:^|\n)(?:•|-)\s+(.+?)(?:\n|\Z)",
]


def extract_technologies(text: str) -> Set[str]:
    """Extract known technologies from text."""
    techs = set()
    for tech_name, patterns in TECH_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                techs.add(tech_name)
                break
    return techs


def extract_requirement_spans(text: str) -> dict[str, list[str]]:
    """Extract requirement-related spans."""
    reqs: dict[str, list[str]] = {
        "years_experience": [],
        "degrees": [],
        "citizen_status": [],
    }

    for match in re.finditer(REQUIREMENT_PATTERNS["years_experience"], text):
        reqs["years_experience"].append(match.group(0))

    for match in re.finditer(REQUIREMENT_PATTERNS["degree"], text):
        reqs["degrees"].append(match.group(0))

    for match in re.finditer(REQUIREMENT_PATTERNS["citizen_status"], text):
        reqs["citizen_status"].append(match.group(0))

    return reqs


def extract_skill_candidates(text: str) -> Set[str]:
    """Extract skill candidates from bullet points."""
    candidates = set()

    for pattern in SKILL_EXTRACTION_PATTERNS:
        for match in re.finditer(pattern, text, re.MULTILINE):
            line = match.group(1).strip()
            line = re.sub(r"[\d\*\-\•]$", "", line).strip()
            if len(line) > 5:
                candidates.add(line)

    return candidates
