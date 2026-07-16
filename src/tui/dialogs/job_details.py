"""Expandable job details view for assessment results."""

from typing import Any, Dict

from textual.widgets import Static

from src.tui.utils.formatters import truncate


class JobDetailsPanel(Static):
    """Expandable panel showing full job assessment details.

    Displays:
    - Overall score (0-100)
    - Category scores (tech, seniority, location)
    - Claude reasoning from assessment
    - Recommendations
    """

    DEFAULT_CSS = """
    JobDetailsPanel {
        width: 1fr;
        height: auto;
        border: solid $accent;
        padding: 1;
        background: $boost;
    }

    JobDetailsPanel > .score-row {
        width: 1fr;
        height: auto;
    }

    JobDetailsPanel > .reasoning {
        width: 1fr;
        height: auto;
        border-top: solid $accent;
        padding: 1 0 0 0;
        margin: 1 0 0 0;
    }

    JobDetailsPanel > .recommendations {
        width: 1fr;
        height: auto;
        border-top: solid $accent;
        padding: 1 0 0 0;
        margin: 1 0 0 0;
    }
    """

    def __init__(self, job_id: str, job_data: Dict[str, Any]):
        super().__init__()
        self.job_id = job_id
        self.job_data = job_data

    def render(self) -> str:
        """Render job assessment details."""
        lines = [f"[b]Job Assessment: {self.job_data.get('title', 'Unknown')}[/b]"]

        # Overall score
        overall = self.job_data.get("overall_score", 0)
        lines.append(f"\n[b]Overall Match Score:[/b] {overall:.0f}/100")

        # Category scores
        lines.append("\n[b]Category Breakdown:[/b]")
        tech_score = self.job_data.get("tech_score", 0)
        lines.append(f"  • Technical Skills: {tech_score:.0f}/100")

        seniority_score = self.job_data.get("seniority_score", 0)
        lines.append(f"  • Seniority Level: {seniority_score:.0f}/100")

        location_score = self.job_data.get("location_score", 0)
        lines.append(f"  • Location Match: {location_score:.0f}/100")

        # Assessment summary from Claude
        summary = self.job_data.get("assessment_summary", "")
        if summary:
            lines.append("\n[b]Assessment Summary:[/b]")
            summary_text = truncate(summary, max_len=500)
            lines.append(f"  {summary_text}")

        # Recommendations
        recommendations = self.job_data.get("recommendations", [])
        if recommendations:
            lines.append("\n[b]Recommendations:[/b]")
            for rec in recommendations[:5]:  # Show top 5
                lines.append(f"  • {rec}")

        return "\n".join(lines)

    def get_score_bar(self, score: float, width: int = 20) -> str:
        """Generate visual score bar."""
        filled = int((score / 100) * width)
        return "█" * filled + "░" * (width - filled)
