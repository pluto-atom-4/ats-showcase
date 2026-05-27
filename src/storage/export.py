"""Markdown report generation for job assessments."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.storage.assessment_store import AssessmentStore

logger = logging.getLogger(__name__)


@dataclass
class ExportConfig:
    """Configuration for export operations."""

    min_score: int = 0
    max_score: int = 100
    sort_by: str = "score"  # score, company, location
    template_style: str = "detailed"  # detailed, summary
    include_recommendations: bool = True
    include_stats: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if not 0 <= self.min_score <= 100:
            raise ValueError("min_score must be 0-100")
        if not 0 <= self.max_score <= 100:
            raise ValueError("max_score must be 0-100")
        if self.min_score > self.max_score:
            raise ValueError("min_score must be <= max_score")
        if self.sort_by not in ("score", "company", "location"):
            raise ValueError("sort_by must be 'score', 'company', or 'location'")
        if self.template_style not in ("detailed", "summary"):
            raise ValueError("template_style must be 'detailed' or 'summary'")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "min_score": self.min_score,
            "max_score": self.max_score,
            "sort_by": self.sort_by,
            "template_style": self.template_style,
            "include_recommendations": self.include_recommendations,
            "include_stats": self.include_stats,
        }


class MarkdownExporter:
    """Generate markdown reports from assessments."""

    def __init__(self, store: AssessmentStore, config: Optional[ExportConfig] = None):
        """
        Initialize exporter.

        Args:
            store: AssessmentStore instance
            config: Export configuration (defaults to ExportConfig())
        """
        self.store = store
        self.config = config or ExportConfig()
        self.generated_at = datetime.now(timezone.utc)

    def generate_report(self) -> str:
        """
        Generate complete markdown report.

        Returns:
            Markdown-formatted report string
        """
        assessments = self._get_filtered_assessments()

        if not assessments:
            return self._render_empty_report()

        sections = [
            self._render_header(assessments),
            self._render_top_matches(assessments),
            self._render_details(assessments),
        ]

        if self.config.include_stats:
            sections.append(self._render_statistics(assessments))

        sections.append(self._render_footer())

        return "\n".join(sections)

    def generate_summary(self) -> str:
        """
        Generate executive summary (top 10 matches only).

        Returns:
            Markdown-formatted summary
        """
        assessments = self._get_filtered_assessments()
        top_10 = assessments[:10]

        sections = [
            self._render_header(top_10),
            self._render_top_matches(top_10),
        ]

        if self.config.include_stats:
            sections.append(self._render_statistics(top_10))

        sections.append(self._render_footer())

        return "\n".join(sections)

    def _get_filtered_assessments(self) -> List[Dict[str, Any]]:
        """
        Get assessments filtered and sorted per config.

        Returns:
            List of assessment dictionaries
        """
        assessments = self.store.get_assessments_by_score(
            min_score=self.config.min_score, max_score=self.config.max_score
        )

        # Sort by configured field
        if self.config.sort_by == "score":
            assessments.sort(key=lambda x: x["overall_score"], reverse=True)
        elif self.config.sort_by == "company":
            assessments.sort(key=lambda x: x.get("company", "").lower())
        elif self.config.sort_by == "location":
            assessments.sort(key=lambda x: x.get("location", "").lower())

        return assessments

    def _render_header(self, assessments: List[Dict[str, Any]]) -> str:
        """Render report header."""
        timestamp = self.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        total = self.store.count_assessments()
        filtered = len(assessments)

        lines = [
            "# Job Assessment Report",
            "",
            f"**Generated:** {timestamp}",
            f"**Total Assessed:** {total} | **Filtered:** {filtered}",
            "",
        ]

        if self.config.min_score > 0 or self.config.max_score < 100:
            lines.append(f"**Score Range:** {self.config.min_score}-{self.config.max_score}")
            lines.append("")

        # Cost summary
        stats = self.store.get_stats()
        if stats and "total_cost" in stats:
            lines.append(
                f"**Cost Summary:** ${stats['total_cost']:.4f} total "
                f"({stats['total_input_tokens']} input + "
                f"{stats['total_output_tokens']} output tokens)"
            )
            lines.append("")

        return "\n".join(lines)

    def _render_top_matches(self, assessments: List[Dict[str, Any]]) -> str:
        """Render top matches section."""
        if not assessments:
            return ""

        top_count = 5 if self.config.template_style == "detailed" else 10
        top = assessments[:top_count]

        lines = [f"## Top {top_count} Matches", ""]

        for idx, job in enumerate(top, 1):
            company = job.get("company", "N/A")
            title = job.get("title", "N/A")
            score = job.get("overall_score", 0)
            lines.append(f"{idx}. **{title}** @ {company} (Score: {score})")

        lines.append("")

        return "\n".join(lines)

    def _render_details(self, assessments: List[Dict[str, Any]]) -> str:
        """Render job details section."""
        lines = ["## Job Details", ""]

        for idx, job in enumerate(assessments, 1):
            job_card = self._render_job_card(job, idx)
            lines.append(job_card)

        return "\n".join(lines)

    def _render_job_card(self, job: Dict[str, Any], index: int) -> str:
        """
        Render single job card.

        Args:
            job: Assessment dictionary
            index: Display index (1-based)

        Returns:
            Markdown-formatted job card
        """
        lines = []

        # Header
        company = job.get("company", "N/A")
        title = job.get("title", "N/A")
        lines.append(f"### [{index}] {title} @ {company}")
        lines.append("")

        # Scores
        overall = job.get("overall_score", 0)
        tech = job.get("tech_score", 0)
        seniority = job.get("seniority_score", 0)
        location = job.get("location_score", 0)
        lines.append(
            f"- **Overall Score:** {overall} | "
            f"Tech: {tech} | Seniority: {seniority} | Location: {location}"
        )
        lines.append("")

        # Location
        location_str = job.get("location", "")
        if location_str:
            lines.append(f"- **Location:** {location_str}")
            lines.append("")

        # Recommendations
        if self.config.include_recommendations:
            recommendations = job.get("recommendations", [])
            if recommendations:
                lines.append("- **Recommendations:**")
                for rec in recommendations:
                    lines.append(f"  - {rec}")
                lines.append("")

        return "\n".join(lines)

    def _render_statistics(self, assessments: List[Dict[str, Any]]) -> str:
        """Render analytics section."""
        if not assessments:
            return ""

        lines = ["## Analytics", ""]

        # Score statistics
        scores = [a.get("overall_score", 0) for a in assessments]
        if scores:
            avg_score = sum(scores) / len(scores)
            min_score = min(scores)
            max_score = max(scores)
            lines.append("- **Score Statistics**")
            lines.append(f"  - Average: {avg_score:.1f}")
            lines.append(f"  - Min: {min_score}")
            lines.append(f"  - Max: {max_score}")
            lines.append("")

        # Score distribution
        ranges = self.store.get_score_ranges()
        if ranges:
            lines.append("- **Score Distribution**")
            for range_key in ["0-25", "25-50", "50-75", "75-100"]:
                count = ranges.get(range_key, 0)
                bar = "█" * (count // max(len(ranges.values()), 1))
                lines.append(f"  - {range_key}: {count:3d} {bar}")
            lines.append("")

        # Cost breakdown
        stats = self.store.get_stats()
        if stats and stats.get("total_cost", 0) > 0:
            input_tokens = stats.get("total_input_tokens", 0)
            output_tokens = stats.get("total_output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            input_pct = (input_tokens / total_tokens * 100) if total_tokens > 0 else 0
            lines.append("- **Cost Breakdown**")
            lines.append(f"  - Input: {input_pct:.0f}%")
            lines.append(f"  - Output: {100 - input_pct:.0f}%")
            lines.append("")

        return "\n".join(lines)

    def _render_empty_report(self) -> str:
        """Render report when no jobs match filters."""
        lines = [
            "# Job Assessment Report",
            "",
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "⚠️ **No jobs found** matching filters "
            f"(score: {self.config.min_score}-{self.config.max_score})",
            "",
            "Try adjusting score range or running without filters.",
        ]

        return "\n".join(lines)

    def _render_footer(self) -> str:
        """Render report footer."""
        lines = [
            "---",
            "",
            "## Search Tips",
            "",
            "Use the `query` command to search jobs by keyword:",
            "",
            "```bash",
            'uv run python -m src.cli query --keyword "python" --min-score 75',
            "```",
            "",
            "Filter by score range, sort by company, and export at any time.",
        ]

        return "\n".join(lines)
