"""Build assessment prompts for Claude API with preprocessed data."""

import json
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# System prompt for job assessment
SYSTEM_PROMPT = """You are an expert recruiter and technical interviewer.

Your task: Assess how well a candidate's CV matches a job posting.

Guidelines:
1. Be objective - focus on skill/experience match, not subjective fit
2. Look for both required and nice-to-have skills
3. Consider seniority level alignment (junior/mid/senior)
4. Factor in transferable skills (e.g., language-agnostic concepts)
5. Be balanced - acknowledge both strengths and gaps

Return JSON format (no markdown, just raw JSON):
{
    "overall_score": <0-100 int>,
    "tech_match": <0-100 int>,
    "seniority_match": <0-100 int>,
    "location_match": "<yes/no/unknown>",
    "top_strengths": ["strength1", "strength2"],
    "gaps": ["gap1", "gap2"],
    "reasoning": "Brief explanation of scoring"
}"""


class PromptBuilder:
    """Build assessment prompts for Claude API."""

    @staticmethod
    def build_simple_prompt(
        cv_text: str,
        job_description: str,
        extracted_entities: Optional[Tuple[List[str], List[str], List[str]]] = None,
        chunks: Optional[List[str]] = None,
    ) -> str:
        """Build assessment prompt without examples.

        Args:
            cv_text: CV text
            job_description: Job description
            extracted_entities: Tuple of (skills, tech, requirements)
            chunks: Semantic chunks of job description

        Returns:
            Prompt string ready for API call
        """
        if extracted_entities is None:
            extracted_entities = ([], [], [])

        if chunks is None:
            chunks = []

        skills, tech, requirements = extracted_entities

        # Format entities
        entity_section = ""
        if skills or tech or requirements:
            entity_section = "\n## Job Requirements (Extracted)\n"
            if skills:
                entity_section += f"\n**Skills Needed:** {', '.join(skills)}"
            if tech:
                entity_section += f"\n**Tech Stack:** {', '.join(tech)}"
            if requirements:
                entity_section += f"\n**Other Requirements:** {', '.join(requirements)}"

        # Format chunks
        chunks_section = ""
        if chunks:
            chunks_section = "\n### Job Description (Semantic Chunks)\n\n"
            chunks_section += "\n".join(f"- {chunk}" for chunk in chunks)

        prompt = f"""{SYSTEM_PROMPT}

---

## Candidate Profile

{cv_text}{entity_section}{chunks_section}

## Assessment

Evaluate CV fit (0-100) across:
1. **Technical Skills Match** - Do CV skills align with job tech stack?
2. **Seniority Alignment** - Does CV experience level match job level?
3. **Location & Availability** - Are CV location/availability compatible?
4. **Overall Match Score** - Weighted average of above

JSON:"""

        logger.debug(f"Simple prompt built: {len(prompt)} chars")
        return prompt

    @staticmethod
    def build_prompt_with_examples(
        cv_text: str,
        job_description: str,
        extracted_entities: Optional[Tuple[List[str], List[str], List[str]]] = None,
        chunks: Optional[List[str]] = None,
    ) -> str:
        """Build assessment prompt with few-shot examples.

        Includes one example to guide response format and quality.
        Costs ~200 additional tokens but improves accuracy.

        Args:
            cv_text: CV text
            job_description: Job description
            extracted_entities: Tuple of (skills, tech, requirements)
            chunks: Semantic chunks of job description

        Returns:
            Prompt string with examples
        """
        if extracted_entities is None:
            extracted_entities = ([], [], [])

        if chunks is None:
            chunks = []

        example_assessment = {
            "overall_score": 75,
            "tech_match": 85,
            "seniority_match": 70,
            "location_match": "yes",
            "top_strengths": [
                "5 years Python and Django experience",
                "Strong PostgreSQL background",
                "Familiarity with REST APIs",
            ],
            "gaps": [
                "No Redis experience",
                "Limited async/background job knowledge",
            ],
            "reasoning": "Strong backend foundation with most required tech stack. "
            "Missing specialized async experience but skills are transferable.",
        }

        skills, tech, requirements = extracted_entities

        entity_section = ""
        if skills or tech or requirements:
            entity_section = "\n## Job Requirements (Extracted)\n"
            if skills:
                entity_section += f"\n**Skills Needed:** {', '.join(skills[:10])}"
            if tech:
                entity_section += f"\n**Tech Stack:** {', '.join(tech[:10])}"
            if requirements:
                entity_section += f"\n**Other Requirements:** {', '.join(requirements[:10])}"

        chunks_section = ""
        if chunks:
            chunks_section = "\n### Job Description\n\n"
            chunks_section += "\n".join(f"- {chunk}" for chunk in chunks[:3])

        prompt = f"""{SYSTEM_PROMPT}

---

## Example Assessment

**Example CV:**
5 years Python, Django, PostgreSQL. React basics. Previous startup role managing 2 engineers.

**Example Job:**
Senior Python developer. Needs Django, PostgreSQL, Redis. Lead technical initiatives.

**Example Assessment:**
{json.dumps(example_assessment, indent=2)}

---

## Actual Assessment

### Candidate Profile

{cv_text}{entity_section}{chunks_section}

### Your Assessment

JSON:"""

        logger.debug(f"Prompt with examples built: {len(prompt)} chars")
        return prompt
