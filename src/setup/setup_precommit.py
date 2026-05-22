#!/usr/bin/env python3
"""
Pre-commit setup utility for ATS Playground.

Automatically installs and configures pre-commit hooks to catch code quality
issues (formatting, linting, type checking, tests) before commits.

Usage:
    python -m src.setup.setup_precommit
    python -m src.setup.setup_precommit --skip-full-run
    python -m src.setup.setup_precommit --help

Features:
    - Validates .pre-commit-config.yaml syntax
    - Installs pre-commit hooks from config
    - Tests all hooks on entire codebase
    - Provides helpful error messages
    - Supports --skip-full-run for faster setup

Exit Codes:
    0: Setup successful
    1: Setup failed (see error message)

Skip Hooks During Commit:
    SKIP=black,ruff,mypy git commit -m "..."
    SKIP=pytest git commit -m "..."

Force Commit Without Hooks:
    git commit --no-verify -m "..."
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"


class PreCommitSetup:
    """Manages pre-commit hook installation and validation."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        """Initialize setup manager.

        Args:
            project_root: Path to project root (auto-detected if None)
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        self.config_file = self.project_root / ".pre-commit-config.yaml"

    def _run_command(
        self, cmd: list, check: bool = True, capture_output: bool = False
    ) -> tuple[int, str]:
        """Run a shell command safely.

        Args:
            cmd: Command and arguments as list
            check: Raise exception on non-zero exit
            capture_output: Capture stdout/stderr

        Returns:
            Tuple of (return_code, output)
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                check=False,
                capture_output=capture_output,
                text=True,
            )
            if check and result.returncode != 0:
                if capture_output:
                    raise RuntimeError(f"Command failed: {result.stderr or result.stdout}")
                else:
                    raise subprocess.CalledProcessError(result.returncode, cmd)
            return (result.returncode, result.stdout if capture_output else "")
        except FileNotFoundError as e:
            raise RuntimeError(f"Command not found: {cmd[0]}") from e

    def validate_config(self) -> bool:
        """Validate .pre-commit-config.yaml syntax.

        Returns:
            True if valid, False otherwise
        """
        if not self.config_file.exists():
            self._print_error(f"Config file not found: {self.config_file}")
            return False

        try:
            self._run_command(["pre-commit", "validate-config"])
            self._print_success("Config validated")
            return True
        except Exception as e:
            self._print_error(f"Config validation failed: {e}")
            return False

    def install_hooks(self) -> bool:
        """Install pre-commit hooks into .git/hooks.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._run_command(["pre-commit", "install"])
            self._print_success("Hooks installed to .git/hooks/pre-commit")
            return True
        except Exception as e:
            self._print_error(f"Hook installation failed: {e}")
            return False

    def run_all_hooks(self) -> bool:
        """Run all hooks on entire codebase.

        Returns:
            True if all hooks pass, False otherwise
        """
        try:
            self._print_info("\n🔄 Running hooks on all files (this may take ~60s)...\n")
            self._run_command(["pre-commit", "run", "--all-files"])
            self._print_success("All hooks passed!")
            return True
        except subprocess.CalledProcessError:
            self._print_warning(
                "⚠️  Some files need fixing (auto-fixes applied, please review and commit)"
            )
            return False
        except Exception as e:
            self._print_error(f"Hook execution failed: {e}")
            return False

    def check_git_installed(self) -> bool:
        """Check if git is installed and .git directory exists.

        Returns:
            True if git is available, False otherwise
        """
        if not (self.project_root / ".git").exists():
            self._print_error(".git directory not found. Are you in the project root?")
            return False
        try:
            self._run_command(["git", "--version"])
            return True
        except Exception as e:
            self._print_error(f"Git not available: {e}")
            return False

    def check_pre_commit_installed(self) -> bool:
        """Check if pre-commit is installed.

        Returns:
            True if pre-commit is available, False otherwise
        """
        try:
            self._run_command(["pre-commit", "--version"])
            return True
        except Exception as e:
            self._print_error(f"pre-commit not installed: {e}")
            self._print_info("\n💡 Install with: uv sync (or pip install pre-commit)")
            return False

    def setup(self, skip_full_run: bool = False) -> int:
        """Execute complete pre-commit setup process.

        Args:
            skip_full_run: Skip running hooks on all files

        Returns:
            0 if successful, 1 if failed
        """
        self._print_header("🚀 Pre-commit Setup for ATS Playground")

        # Step 1: Check prerequisites
        self._print_step("1", "Checking prerequisites")
        if not self.check_git_installed():
            return 1
        if not self.check_pre_commit_installed():
            return 1

        # Step 2: Validate config
        self._print_step("2", "Validating configuration")
        if not self.validate_config():
            return 1

        # Step 3: Install hooks
        self._print_step("3", "Installing hooks")
        if not self.install_hooks():
            return 1

        # Step 4: Run hooks (optional)
        if not skip_full_run:
            self._print_step("4", "Testing hooks on all files")
            if not self.run_all_hooks():
                self._print_warning("\n⚠️  Some formatting needed. Review changes and commit.")
                return 0  # Not a critical failure

        # Success
        self._print_footer(
            "✨ Pre-commit setup complete!\n"
            "\n📋 Next steps:"
            "\n  1. Review any auto-fixed files (git diff)"
            "\n  2. Stage and commit: git add . && git commit"
            "\n  3. Hooks will run automatically on future commits"
            "\n\n💡 Skip hooks if needed:"
            "\n  SKIP=black,ruff git commit -m '...'"
            "\n  git commit --no-verify -m '...' (emergency only)"
        )
        return 0

    # Helper methods for output formatting
    def _print_header(self, text: str) -> None:
        """Print section header."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")

    def _print_footer(self, text: str) -> None:
        """Print footer with summary."""
        print(f"\n{Colors.BOLD}{Colors.GREEN}{text}{Colors.RESET}\n")

    def _print_step(self, number: str, description: str) -> None:
        """Print step indicator."""
        print(f"{Colors.BOLD}{Colors.BLUE}Step {number}:{Colors.RESET} {description}")

    def _print_success(self, text: str) -> None:
        """Print success message."""
        print(f"  {Colors.GREEN}✓{Colors.RESET} {text}")

    def _print_warning(self, text: str) -> None:
        """Print warning message."""
        print(f"  {Colors.YELLOW}⚠{Colors.RESET}  {text}")

    def _print_error(self, text: str) -> None:
        """Print error message."""
        print(f"  {Colors.RED}✗{Colors.RESET} {text}")

    def _print_info(self, text: str) -> None:
        """Print info message."""
        print(f"  {Colors.BLUE}ℹ{Colors.RESET} {text}")


def main() -> int:
    """CLI entry point for pre-commit setup."""
    parser = argparse.ArgumentParser(
        description="Set up pre-commit hooks for ATS Playground",
        epilog="See docs/QUALITY-ASSURANCE.md for detailed documentation",
    )
    parser.add_argument(
        "--skip-full-run",
        action="store_true",
        help="Skip running hooks on all files (faster for CI/CD)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Path to project root (auto-detected if omitted)",
    )

    args = parser.parse_args()

    setup = PreCommitSetup(project_root=args.project_root)
    return setup.setup(skip_full_run=args.skip_full_run)


if __name__ == "__main__":
    sys.exit(main())
