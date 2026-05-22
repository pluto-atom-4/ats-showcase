"""SQL queries for job storage and retrieval."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class JobQueries:
    """Common SQL queries for job data."""

    @staticmethod
    def get_all_jobs(
        status: Optional[str] = None, company: Optional[str] = None, limit: int = 100
    ) -> str:
        """
        Get jobs with optional filtering.

        Args:
            status: Filter by status (pending_review, confirmed, rejected)
            company: Filter by company name
            limit: Limit results

        Returns:
            SQL query string
        """
        query = "SELECT * FROM jobs WHERE 1=1"
        if status:
            query += f" AND status = '{status}'"
        if company:
            query += f" AND company = '{company}'"
        query += f" ORDER BY crawled_date DESC LIMIT {limit}"
        return query

    @staticmethod
    def search_jobs(keyword: str, min_score: Optional[float] = None) -> str:
        """
        Full-text search jobs by keyword using FTS5.

        Args:
            keyword: Search keyword
            min_score: Minimum assessment score (if available)

        Returns:
            SQL query string
        """
        query = f"""
            SELECT j.*, a.overall_score
            FROM jobs j
            LEFT JOIN assessments a ON j.id = a.job_id
            WHERE j.title LIKE '%{keyword}%'
                OR j.description LIKE '%{keyword}%'
                OR j.company LIKE '%{keyword}%'
        """
        if min_score:
            query += f" AND a.overall_score >= {min_score}"
        query += " ORDER BY a.overall_score DESC NULLS LAST"
        return query

    @staticmethod
    def get_stats() -> str:
        """Get database statistics."""
        return """
            SELECT
                'Total Jobs' as metric, COUNT(*) as value FROM jobs
            UNION ALL
            SELECT 'Pending Review' as metric, COUNT(*) FROM jobs WHERE status='pending_review'
            UNION ALL
            SELECT 'Confirmed' as metric, COUNT(*) FROM jobs WHERE status='confirmed'
            UNION ALL
            SELECT 'Assessed' as metric, COUNT(*) FROM assessments
            UNION ALL
            SELECT 'Avg Score' as metric, ROUND(AVG(overall_score), 1) FROM assessments
        """


class CostQueries:
    """SQL queries for cost tracking."""

    @staticmethod
    def get_total_cost() -> str:
        """Get total cost across all jobs."""
        return "SELECT SUM(cost) as total_cost FROM cost_tracking"

    @staticmethod
    def get_cost_by_phase() -> str:
        """Get cost breakdown by phase."""
        return """
            SELECT
                phase,
                COUNT(*) as num_jobs,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(cost) as total_cost
            FROM cost_tracking
            GROUP BY phase
            ORDER BY total_cost DESC
        """


class AssessmentQueries:
    """SQL queries for assessment results."""

    @staticmethod
    def get_top_matches(limit: int = 10) -> str:
        """Get top matching jobs."""
        return f"""
            SELECT
                j.title,
                j.company,
                j.location,
                a.overall_score,
                a.summary
            FROM assessments a
            JOIN jobs j ON a.job_id = j.id
            ORDER BY a.overall_score DESC
            LIMIT {limit}
        """

    @staticmethod
    def get_below_threshold(threshold: float = 50) -> str:
        """Get jobs below score threshold."""
        return f"""
            SELECT
                j.title,
                j.company,
                a.overall_score,
                a.recommendations
            FROM assessments a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.overall_score < {threshold}
            ORDER BY a.overall_score DESC
        """
