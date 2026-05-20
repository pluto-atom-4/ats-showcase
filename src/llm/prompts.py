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
    base_prompt = """You are an expert ATS (Applicant Tracking System) evaluator. Analyze the CV against the job posting.

Provide a structured assessment with:
1. Overall match score (0-100)
2. Technical skills match score (0-100)
3. Seniority level match score (0-100)
4. Location/logistics match score (0-100)
5. Key gaps or missing skills
6. Recommendations for improving fit
7. Brief summary (2-3 sentences)

Be objective and specific. If skills don't match, explain why."""
    
    if cv_summary:
        return f"{base_prompt}\n\nCandidate Summary:\n{cv_summary}"
    return base_prompt


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
