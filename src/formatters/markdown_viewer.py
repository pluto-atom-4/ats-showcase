"""Rich-formatted markdown report viewer."""

import re
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown


class ScoreLevel(Enum):
    """Score severity levels for coloring."""

    EXCELLENT = (90, "bright_green")  # 90-100
    GOOD = (75, "green")              # 75-89
    FAIR = (50, "yellow")             # 50-74
    POOR = (0, "red")                 # 0-49


class MarkdownReportViewer:
    """Rich-formatted markdown report viewer."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def view_report(
        self,
        report_path: str,
        template: str = "full",
        topn: int = 5,
        min_score: float = 0.0,
        max_score: float = 100.0,
        highlight: bool = True,
        use_pager: bool = True,
    ) -> None:
        """Display report with rich formatting."""
        path = Path(report_path)

        if not path.exists():
            self.console.print(f"❌ Report not found: {report_path}", style="bold red")
            raise FileNotFoundError(f"Report not found: {report_path}")

        content = path.read_text(encoding="utf-8")

        if template == "summary":
            self._render_summary(content, highlight)
        elif template == "topn":
            self._render_topn(content, topn, highlight)
        else:
            self._render_full(content, min_score, max_score, highlight)

    def _render_summary(self, content: str, highlight: bool) -> None:
        """Render headers and summary statistics only."""
        lines = content.split("\n")
        summary_lines = []
        in_job_details = False

        for line in lines:
            if line.startswith("## Job Details"):
                in_job_details = True
                continue
            if in_job_details and line.startswith("### ["):
                break
            summary_lines.append(line)

        summary_content = "\n".join(summary_lines)
        self._print_markdown(summary_content, highlight)

    def _render_topn(self, content: str, topn: int, highlight: bool) -> None:
        """Render top N matches section."""
        match = re.search(
            r"## Top \d+ Matches\s*\n(.*?)\n##",
            content,
            re.DOTALL,
        )

        if match:
            header = "## Top Matches\n\n"
            top_matches = match.group(1)
            lines = top_matches.strip().split("\n")[:topn]
            top_content = header + "\n".join(lines)
            self._print_markdown(top_content, highlight)
        else:
            self.console.print("No matches found in report", style="bold yellow")

    def _render_full(
        self,
        content: str,
        min_score: float,
        max_score: float,
        highlight: bool,
    ) -> None:
        """Render full report with optional filtering."""
        filtered_content = self._filter_by_score(content, min_score, max_score)
        self._print_markdown(filtered_content, highlight)

    def _filter_by_score(
        self,
        content: str,
        min_score: float,
        max_score: float,
    ) -> str:
        """Filter job details by score range."""
        if min_score == 0.0 and max_score == 100.0:
            return content

        lines = content.split("\n")
        filtered_lines = []
        skip_job = False

        for line in lines:
            if line.startswith("### ["):
                match = re.search(r"Score: (\d+(?:\.\d+)?)\)", line)
                if match:
                    score = float(match.group(1))
                    skip_job = not (min_score <= score <= max_score)

            if not skip_job:
                filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _print_markdown(self, content: str, highlight: bool) -> None:
        """Print markdown with rich formatting."""
        if highlight:
            md = Markdown(content)
            self.console.print(md)
        else:
            self.console.print(content)
