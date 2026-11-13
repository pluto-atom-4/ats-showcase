"""ESCO-aligned soft skills taxonomy for NLP skill extraction (Phase 1).

This module provides soft skills categorized according to ESCO standards:
- Communication & Presentation: Language skills, speaking, writing
- Leadership & Management: Team leadership, project management
- Teamwork & Collaboration: Interpersonal skills, cooperation
- Problem-Solving & Analysis: Critical thinking, analytical reasoning
- Organization & Planning: Time management, scheduling
- Emotional Intelligence: Empathy, interpersonal awareness
- Adaptability & Learning: Flexibility, continuous improvement
- Customer & Relationship: Client focus, negotiation
"""

SOFT_SKILLS_BY_CATEGORY = {
    # Communication & Presentation
    "communication": {
        "communication",
        "written communication",
        "oral communication",
        "presentation",
        "public speaking",
        "writing",
        "writing skills",
        "speaking",
        "verbal",
        "articulate",
    },
    # Leadership & Management
    "leadership": {
        "leadership",
        "project management",
        "team leadership",
        "management",
        "leading",
        "directing",
        "supervising",
        "mentoring",
        "coaching",
        "training",
    },
    # Teamwork & Collaboration
    "teamwork": {
        "teamwork",
        "collaboration",
        "team collaboration",
        "cooperative",
        "interpersonal",
        "interpersonal skills",
        "working with others",
        "cooperation",
        "collaborative",
    },
    # Problem-Solving & Analysis
    "problem_solving": {
        "problem-solving",
        "problem solving",
        "critical thinking",
        "analytical",
        "analytical skills",
        "analytical thinking",
        "analysis",
        "reasoning",
        "logical thinking",
        "troubleshooting",
    },
    # Organization & Planning
    "organization": {
        "organizational",
        "organizational skills",
        "time management",
        "planning",
        "organization",
        "scheduling",
        "multitasking",
        "prioritization",
    },
    # Emotional Intelligence
    "emotional_intelligence": {
        "emotional intelligence",
        "empathy",
        "self-awareness",
        "self-regulation",
        "relationship management",
        "motivation",
        "adaptability",
        "resilience",
    },
    # Adaptability & Learning
    "adaptability": {
        "adaptability",
        "flexibility",
        "learning ability",
        "quick learner",
        "continuous learning",
        "learning agility",
        "innovative",
        "creative",
    },
    # Customer & Relationship Management
    "customer_relations": {
        "customer service",
        "customer focus",
        "client relations",
        "negotiation",
        "persuasion",
        "conflict resolution",
        "listening",
    },
}

SOFT_SKILLS = set()
for category_skills in SOFT_SKILLS_BY_CATEGORY.values():
    SOFT_SKILLS.update(category_skills)


def get_all_soft_skills() -> set[str]:
    """Get all soft skills.

    Returns:
        Set of all soft skill terms across all categories
    """
    return SOFT_SKILLS.copy()


def get_soft_skills_by_category(category: str) -> set[str]:
    """Get soft skills for a specific ESCO category.

    Args:
        category: One of: communication, leadership, teamwork, problem_solving,
                  organization, emotional_intelligence, adaptability, customer_relations

    Returns:
        Set of soft skill terms in that category, or empty set if category not found
    """
    return SOFT_SKILLS_BY_CATEGORY.get(category, set()).copy()


def get_all_categories() -> list[str]:
    """Get all ESCO soft skills categories.

    Returns:
        List of category names
    """
    return list(SOFT_SKILLS_BY_CATEGORY.keys())
