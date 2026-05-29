"""Assessment prompts for Claude API."""

from typing import Optional


def get_assessment_prompt(cv_summary: Optional[str] = None) -> str:
    """
    Get the main assessment prompt template.

    Args:
        cv_summary: Optional CV summary for personalization

    Returns:
        Prompt template string
    """
    base_prompt = """You are an expert recruiter evaluating job fit for candidates.

Analyze the CV against the job posting and score on these dimensions:

1. **Tech Skills Match (0-100)**: Do they have required technologies?
2. **Seniority Level Match (0-100)**: Years of experience vs. role expectations?
3. **Location Fit (0-100)**: Remote/on-site/hybrid alignment?
4. **Overall Score (0-100)**: Weighted fit (40% tech, 30% seniority, 30% location)

For each dimension, provide:
- Score (0-100)
- Reasoning
- Gaps or mismatches

Output format: ONLY valid JSON, no markdown, no extra text.

Example response:
{
  "tech_score": 85,
  "seniority_score": 78,
  "location_score": 60,
  "overall_score": 75,
  "recommendations": ["Learn Kubernetes", "Strengthen AWS knowledge"],
  "summary": "Strong Python/backend developer with solid experience. Junior on cloud infrastructure, which is a gap for this role."
}"""

    if cv_summary:
        return f"{base_prompt}\n\nCandidate Summary:\n{cv_summary}"
    return base_prompt


def build_cv_fit_prompt(cv_text: str, job_text: str) -> str:
    """
    Build a complete CV fit assessment prompt.

    Args:
        cv_text: User's CV as text
        job_text: Job description text

    Returns:
        Complete assessment prompt
    """
    return f"""You are an expert recruiter evaluating job fit.

CANDIDATE CV:
{cv_text}

JOB POSTING:
{job_text}

Score on these dimensions (0-100 scale):
1. Tech Skills Match: Do they have required technologies?
2. Seniority Level: Years of experience vs. role expectations?
3. Location Fit: Remote/on-site/hybrid alignment?
4. Overall Score: Weighted fit (40% tech, 30% seniority, 30% location)

Provide 2-3 gaps/recommendations for improvement.

Respond with ONLY this JSON (no markdown, no extra text):
{{
  "tech_score": <0-100>,
  "seniority_score": <0-100>,
  "location_score": <0-100>,
  "overall_score": <0-100>,
  "recommendations": ["gap1", "gap2"],
  "summary": "<2-3 sentence assessment>"
}}"""


def get_extraction_prompt() -> str:
    """
    Get prompt for extracting structured data from job postings.

    Returns:
        Prompt template string
    """
    return """Extract structured information from this job posting:
1. Key technical skills required (list)
2. Seniority level (junior/mid/senior/principal)
3. Experience requirements in years
4. Preferred technologies/tools (list)
5. Nice-to-have skills (list)
6. Job type (full-time/contract/part-time)
7. Remote options (on-site/hybrid/remote)

Provide as JSON-like structure for parsing."""


def get_summary_prompt() -> str:
    """
    Get prompt for generating executive summary.

    Returns:
        Prompt template string
    """
    return """Summarize the key aspects of this job posting in 2-3 sentences:
- Main role and responsibilities
- Key requirements
- Notable benefits or requirements

Be concise and informative for quick scanning."""


# Prompt templates registry
PROMPTS = {
    "assessment": get_assessment_prompt,
    "extraction": get_extraction_prompt,
    "summary": get_summary_prompt,
}


def get_prompt(prompt_type: str, **kwargs) -> str:
    """
    Get a prompt template by type.

    Args:
        prompt_type: Type of prompt (assessment, extraction, summary)
        **kwargs: Additional arguments for prompt customization

    Returns:
        Prompt template string
    """
    if prompt_type not in PROMPTS:
        raise ValueError(f"Unknown prompt type: {prompt_type}")
    return PROMPTS[prompt_type](**kwargs)
