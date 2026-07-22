"""Main PoC app orchestrating review workflow.

Demonstrates:
- App-level async coordination
- Multiple screen pushes in sequence (@work decorator)
- State accumulation across dialogs
- Terminal cleanup (stty sane)
"""

import asyncio
import sys
from typing import List, Tuple

from poc_state import PoCStateManager
from review_dialog import ReviewDialog
from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class ReviewPoCApp(App):
    """Proof-of-concept review app with proper Textual patterns."""

    BINDINGS = [("q", "quit", "Quit")]
    CSS = """
    Screen {
        layout: vertical;
    }

    Header {
        height: 1;
    }

    Footer {
        height: 1;
    }

    #status {
        height: 3;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self, jobs: List[Tuple[str, str, str, str]]):
        super().__init__()
        self.jobs = jobs
        self.state = PoCStateManager()

        # Add jobs to state
        for job_id, title, company, _desc in jobs:
            self.state.add_job(job_id, title, company)

    def compose(self) -> ComposeResult:
        """Build app UI."""
        yield Header()
        yield Static("Job Review PoC | Use Tab/Enter to navigate, Escape to skip", id="status")
        yield Footer()

    def on_mount(self) -> None:
        """Start review workflow."""
        self.run_review()

    @work(exclusive=True)
    async def run_review(self) -> None:
        """Run interactive review for all jobs."""
        status = self.query_one("#status", Static)

        for i, (job_id, title, company, description) in enumerate(self.jobs, 1):
            # Update status
            status.update(
                f"[bold]Job {i}/{len(self.jobs)}: {title}[/bold]\n"
                f"Use Tab to navigate, Enter to select, Escape to skip"
            )

            # Show dialog and wait for decision
            decision = await self.app.push_screen_wait(
                ReviewDialog(job_id, title, company, description)
            )

            # Record decision
            self.state.record_decision(job_id, decision)

            # Small delay for readability
            await asyncio.sleep(0.2)

        # Show results
        status.update(f"[bold green]✓ Review Complete[/bold green]\n\n{self.state.summary()}")

        # Auto-exit after 2 seconds
        await asyncio.sleep(2)
        self.exit()


def main():
    """Run PoC app with mock jobs."""
    jobs = [
        (
            "job_1",
            "Senior Python Developer",
            "TechCorp",
            "5+ years Python, FastAPI, PostgreSQL. Work on microservices.",
        ),
        (
            "job_2",
            "Full-Stack Engineer",
            "StartupXYZ",
            "React + Node.js + MongoDB. Fast-paced, shipped fast.",
        ),
        (
            "job_3",
            "DevOps Engineer",
            "CloudSys",
            "Kubernetes, Docker, AWS. Build and maintain infrastructure.",
        ),
    ]

    app = ReviewPoCApp(jobs)

    print("🧪 Textual Review PoC")
    print("   Demonstrates proper Textual interaction patterns")
    print()

    try:
        app.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore terminal state (critical after TUI exit)
        import subprocess

        try:
            if sys.stdin.isatty():
                subprocess.run(["stty", "sane"], check=False)
        except Exception:
            pass

    # Print final results
    print("\n📊 Final Results:")
    print(app.state.summary())


if __name__ == "__main__":
    main()
