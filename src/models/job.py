"""Pydantic models for job postings and related data."""

from datetime import UTC, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class JobPosting(BaseModel):
    """Schema for a job posting."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Senior Python Developer",
                "company": "Tech Corp",
                "location": "San Francisco, CA",
                "description": "We are looking for...",
                "requirements": ["Python 3.11+", "FastAPI", "PostgreSQL"],
            }
        }
    )

    id: Optional[str] = Field(None, description="Unique job ID")
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    location: Optional[str] = Field(None, description="Job location")
    url: Optional[HttpUrl] = Field(None, description="Job posting URL")
    description: str = Field(..., description="Full job description")
    requirements: Optional[List[str]] = Field(None, description="Key requirements")
    salary_min: Optional[float] = Field(None, description="Minimum salary")
    salary_max: Optional[float] = Field(None, description="Maximum salary")
    posted_date: Optional[datetime] = Field(None, description="When posted")
    crawled_date: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When crawled"
    )
    status: str = Field(
        default="pending_review", description="Status: pending_review, confirmed, rejected"
    )


class PreprocessedJob(BaseModel):
    """Schema for preprocessed job posting."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job_12345",
                "clean_text": "Senior Python Developer...",
                "token_count": 687,
                "estimated_cost": 0.00206,
            }
        }
    )

    job_id: str = Field(..., description="Reference to original job")
    clean_text: str = Field(..., description="Cleaned HTML -> text")
    sentences: List[str] = Field(..., description="Sentence-segmented text")
    chunks: List[str] = Field(..., description="Semantic chunks")
    token_count: int = Field(..., description="Total tokens")
    estimated_cost: float = Field(..., description="Estimated LLM cost in USD")
    processed_date: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Assessment(BaseModel):
    """Schema for CV-to-job assessment."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job_12345",
                "overall_score": 82.5,
                "tech_score": 85,
                "seniority_score": 80,
                "recommendations": ["Learn Kubernetes", "Strengthen AWS knowledge"],
                "summary": "Good fit for mid-level role, strong Python background",
            }
        }
    )

    job_id: str = Field(..., description="Job posting ID")
    overall_score: float = Field(..., ge=0, le=100, description="Overall match score (0-100)")
    tech_score: float = Field(..., ge=0, le=100, description="Technical skills match")
    seniority_score: float = Field(..., ge=0, le=100, description="Seniority level match")
    location_score: float = Field(..., ge=0, le=100, description="Location preference match")
    recommendations: List[str] = Field(..., description="Recommendations and gaps")
    summary: str = Field(..., description="Brief assessment summary")
    tokens_used: int = Field(..., description="Actual tokens used for assessment")
    actual_cost: float = Field(..., description="Actual cost in USD")
    assessed_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
