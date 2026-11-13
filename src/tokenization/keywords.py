"""Technology keywords for NLP entity extraction.

Organized by category for easy maintenance and discoverability.
Includes 44 baseline keywords + 42 Phase 2 additions (Issue #185) + 33 Phase 5 additions (161 total).

Phase 5 (Issue #192) additions focus on aerospace/defense/manufacturing domains:
- Engineering tools: ANSYS, Nastran, Optistruct, Creo, SolidWorks, CATIA, Windchill, Simulink, COMSOL
- Signal processing: FFT, IFFT, CORDIC, MAC (multiply-accumulate)
- Cloud/DevOps: ArgoCD, Flux, GitOps, Harbor, Quay
- Data tools: TimescaleDB, ClickHouse, DVC, Pydantic, SQLAlchemy, Celery
- IoT/Protocols: MQTT, AMQP, WebSocket, CoAP
- Manufacturing: CAM, CNC, PLM, ERP, MRP
"""

TECH_KEYWORDS = {
    # Programming Languages
    "languages": {
        "python",
        "javascript",
        "typescript",
        "java",
        "c#",
        "csharp",
        "go",
        "rust",
        "php",
        "ruby",
        "c++",
        "scala",
        "kotlin",
    },
    # Web Frameworks & Libraries
    "web": {
        "react",
        "vue",
        "angular",
        "node",
        "express",
        "django",
        "flask",
        "fastapi",
        "next",
        "nextjs",
        "nuxt",
        "svelte",
        "astro",
    },
    # Cloud & Infrastructure
    "infrastructure": {
        "aws",
        "gcp",
        "azure",
        "docker",
        "kubernetes",
        "k8s",
        "terraform",
        "helm",
        "ansible",
        "consul",
        "vault",
        "prometheus",
        "docker-compose",
        "podman",
        "buildah",
        "argocd",
        "flux",
        "gitops",
        "harbor",
        "quay",
    },
    # Databases & Data
    "databases": {
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "cassandra",
        "elasticsearch",
        "kafka",
        "dynamodb",
        "firestore",
        "snowflake",
        "bigquery",
        "duckdb",
        "cockroachdb",
        "timescaledb",
        "clickhouse",
        "dvc",
    },
    # Hardware/FPGA/Embedded & Engineering Tools - CRITICAL for ATS domain
    "hardware": {
        "verilog",
        "systemverilog",
        "asic",
        "fpga",
        "arm",
        "rtl",
        "dft",
        "lint",
        "ddr",
        "spi",
        "i2c",
        "uart",
        "can",
        "esd",
        "lef",
        "def",
        "gds",
        "matlab",
        "ansys",
        "nastran",
        "optistruct",
        "creo",
        "solidworks",
        "catia",
        "windchill",
        "simulink",
        "comsol",
        "fft",
        "ifft",
        "cordic",
        "mac",
    },
    # ML/AI Frameworks
    "ml_ai": {
        "tensorflow",
        "pytorch",
        "sklearn",
        "jax",
        "huggingface",
        "transformers",
        "onnx",
        "keras",
        "xgboost",
        "lightgbm",
        "catboost",
        "mlflow",
        "wandb",
        "opencv",
        "yolo",
        "spacy",
        "bert",
        "gpt",
        "llm",
        "timm",
    },
    # DevOps, Tools & Protocols
    "tools": {
        "jira",
        "confluence",
        "git",
        "gitlab",
        "github",
        "bitbucket",
        "circleci",
        "travis",
        "jenkins",
        "airflow",
        "prefect",
        "rest",
        "grpc",
        "graphql",
        "sql",
        "pydantic",
        "sqlalchemy",
        "celery",
        "mqtt",
        "amqp",
        "websocket",
        "coap",
        "cam",
        "cnc",
        "plm",
        "erp",
        "mrp",
    },
    # Methodologies & Practices
    "methodologies": {
        "agile",
        "scrum",
        "kanban",
        "tdd",
        "bdd",
        "ddd",
        "lean",
        "xp",
    },
    # Robotics & Emerging
    "robotics": {
        "ros",
        "ros2",
        "gazebo",
        "moveit",
        "webots",
    },
    # Other Critical Tools
    "other": {
        "protobuf",
        "json",
        "xml",
        "yaml",
        "kubeflow",
        "ray",
        "cadence",
        "synopsys",
    },
}


def get_all_keywords() -> set[str]:
    """Get flattened set of all keywords across categories.

    Returns:
        Set of all technology keywords (86 total)
    """
    all_kw = set()
    for category_keywords in TECH_KEYWORDS.values():
        all_kw.update(category_keywords)
    return all_kw


def get_keywords_by_category(category: str) -> set[str]:
    """Get keywords for specific category.

    Args:
        category: One of languages, web, infrastructure, databases,
                 hardware, ml_ai, tools, methodologies, robotics, other

    Returns:
        Set of keywords in that category, or empty set if not found
    """
    return TECH_KEYWORDS.get(category, set())


def get_categories() -> list[str]:
    """Get list of keyword categories.

    Returns:
        List of category names
    """
    return list(TECH_KEYWORDS.keys())
