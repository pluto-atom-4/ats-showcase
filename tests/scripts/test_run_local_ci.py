import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = Path(".claude/scripts/run-local-ci.sh")
USAGE = "Usage: bash .claude/scripts/run-local-ci.sh [--tests] [--tests-workers=N|auto] [--strict]"
PYTEST_PREFIX = ["run", "pytest", "tests/", "-v", "--tb=short"]
PARALLEL_ARGS = [*PYTEST_PREFIX, "-m", "not perf", "-n", "2"]
PERF_ARGS = [*PYTEST_PREFIX, "-m", "perf", "-n", "0"]
TIMEOUT_S = 60
VCS_BIN = "git"

UV_STUB = """#!__PYTHON__
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["UV_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
needle = os.environ.get("UV_STUB_FAIL_IF", "")
if needle and needle in " ".join(args):
    print("STUB-FAIL " + json.dumps(args))
    sys.exit(1)
print("STUB-OUT " + json.dumps(args))
"""

STUB_GIT = """#!/bin/bash
case "$1" in
    rev*)
        if [ "$2" = "HEAD" ]; then echo 0000000000000000000000000000000000000000; fi
        ;;
    merg*)
        echo 1111111111111111111111111111111111111111
        ;;
esac
exit 0
"""


@dataclass
class CiRun:
    returncode: int
    stdout: str
    calls: list[list[str]]

    def pytest_calls(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] == ["run", "pytest"]]


def _write_exec(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def run_ci(tmp_path: Path) -> Callable[..., CiRun]:
    script_dir = tmp_path / "repo" / ".claude" / "scripts"
    script_dir.mkdir(parents=True)
    script = script_dir / "run-local-ci.sh"
    script.write_bytes((REPO_ROOT / SCRIPT_REL).read_bytes())

    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    _write_exec(stub_dir / "uv", UV_STUB.replace("__PYTHON__", sys.executable))
    _write_exec(stub_dir / VCS_BIN, STUB_GIT)

    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    log = tmp_path / "uv_calls.jsonl"
    bash = shutil.which("bash")
    assert bash is not None

    def _run(*args: str, fail_if: str = "") -> CiRun:
        env = {
            "PATH": str(stub_dir) + ":/usr/bin:/bin",
            "HOME": str(tmp_path),
            "TMPDIR": str(tmp_dir),
            "UV_STUB_LOG": str(log),
            "UV_STUB_FAIL_IF": fail_if,
        }
        proc = subprocess.run(
            [bash, str(script), *args],
            cwd=script.parents[2],
            env=env,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=TIMEOUT_S,
            check=False,
        )
        calls: list[list[str]] = []
        if log.exists():
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        return CiRun(proc.returncode, proc.stdout, calls)

    return _run


@pytest.mark.parametrize("flag", ["--tests-workers=0", "--tests-workers=abc", "--tests-workers="])
def test_invalid_workers_value_exits_1_without_uv(run_ci: Callable[..., CiRun], flag: str) -> None:
    result = run_ci(flag)
    assert result.returncode == 1
    assert USAGE in result.stdout
    assert result.calls == []


def test_unknown_option_exits_1_with_usage(run_ci: Callable[..., CiRun]) -> None:
    result = run_ci("--bogus")
    assert result.returncode == 1
    assert USAGE in result.stdout
    assert result.calls == []


def test_no_flag_does_not_call_pytest(run_ci: Callable[..., CiRun]) -> None:
    result = run_ci()
    assert result.returncode == 0
    assert result.pytest_calls() == []


def test_tests_flag_runs_single_serial_pytest_phase(run_ci: Callable[..., CiRun]) -> None:
    result = run_ci("--tests")
    assert result.returncode == 0
    assert result.pytest_calls() == [PYTEST_PREFIX]


@pytest.mark.parametrize("flag, workers", [("--tests-workers=2", "2"), ("--tests-workers=auto", "auto")])
def test_workers_flag_runs_parallel_then_perf_phase(run_ci: Callable[..., CiRun], flag: str, workers: str) -> None:
    result = run_ci(flag)
    assert result.returncode == 0
    assert result.pytest_calls() == [
        [*PYTEST_PREFIX, "-m", "not perf", "-n", workers],
        PERF_ARGS,
    ]


def test_parallel_phase_failure_skips_perf_phase(run_ci: Callable[..., CiRun]) -> None:
    result = run_ci("--tests-workers=2", fail_if="not perf")
    assert result.returncode == 1
    assert "Tests failed (parallel phase)" in result.stdout
    assert result.pytest_calls() == [PARALLEL_ARGS]


def test_perf_phase_failure_log_holds_both_phases(run_ci: Callable[..., CiRun]) -> None:
    result = run_ci("--tests-workers=2", fail_if="perf -n 0")
    assert result.returncode == 1
    assert "Tests failed (perf phase)" in result.stdout
    assert "STUB-OUT " + json.dumps(PARALLEL_ARGS) in result.stdout
    assert "STUB-FAIL " + json.dumps(PERF_ARGS) in result.stdout
