"""Observational cost trend per loop agent type across a before and an after date window."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

AGENT_TYPES = ("architect", "builder", "reviewer", "slop-hunter", "cavecrew-builder", "cavecrew-reviewer")
COMPONENTS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
CAVEMAN_PREFIX = "caveman:"
DEFAULT_BEFORE_END = "2026-10-26"
DEFAULT_AFTER_START = "2026-11-21"
DAY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
CONFOUNDERS = (
    "Confounders (not controlled here):",
    "- PR size per run (diff volume) varies between windows",
    "- review rounds per PR differ between windows",
    "- loop changes in between, e.g. #835",
    "- transcript gap 2026-10-27 to 2026-11-10: no runs recorded",
    "- cost weights (1.25 cache write, 0.1 cache read, 5 output) are an assumption",
)


class SummaryError(ValueError):
    """Input or argument error reported to stderr with exit code 2."""


def cost(run: dict[str, Any]) -> float:
    return float(
        run["input_tokens"]
        + 1.25 * run["cache_write_tokens"]
        + 0.1 * run["cache_read_tokens"]
        + 5 * run["output_tokens"]
    )


def _validate_run(item: object, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SummaryError(f"record {index} is not an object")
    if not isinstance(item.get("agent_type"), str):
        raise SummaryError(f"record {index} has no string agent_type")
    date = item.get("date")
    if date is not None and not (isinstance(date, str) and DAY_RE.fullmatch(date)):
        raise SummaryError(f"record {index} has a bad date: {date!r}")
    for name in COMPONENTS:
        value = item.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise SummaryError(f"record {index} field {name} is not an integer")
    return item


def load_runs(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise SummaryError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise SummaryError(f"{path} must contain a JSON list")
    return [_validate_run(item, i) for i, item in enumerate(payload)]


def _parse_day(text: str, flag: str) -> str:
    if not DAY_RE.fullmatch(text):
        raise SummaryError(f"{flag} must be YYYY-MM-DD, got {text!r}")
    return text


def _fold(agent_type: str) -> str | None:
    name = agent_type.removeprefix(CAVEMAN_PREFIX)
    return name if name in AGENT_TYPES else None


def _summarise(runs: list[dict[str, Any]]) -> dict[str, Any]:
    cell: dict[str, Any] = {
        "n": len(runs),
        "cost": {"median": None, "q1": None, "q3": None},
        "components": {name: {"median": None} for name in COMPONENTS},
    }
    if not runs:
        return cell
    costs = [cost(run) for run in runs]
    cell["cost"]["median"] = statistics.median(costs)
    if len(costs) >= 2:
        q1, _, q3 = statistics.quantiles(costs, n=4, method="exclusive")
        cell["cost"]["q1"] = q1
        cell["cost"]["q3"] = q3
    for name in COMPONENTS:
        cell["components"][name]["median"] = statistics.median([run[name] for run in runs])
    return cell


def build_report(runs: list[dict[str, Any]], before_end: str, after_start: str) -> dict[str, Any]:
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = {
        "before": {t: [] for t in AGENT_TYPES},
        "after": {t: [] for t in AGENT_TYPES},
    }
    for run in runs:
        agent = _fold(run["agent_type"])
        date = run["date"]
        if agent is None or date is None:
            continue
        if date <= before_end:
            buckets["before"][agent].append(run)
        elif date >= after_start:
            buckets["after"][agent].append(run)
    return {
        "params": {"before_end": before_end, "after_start": after_start},
        "windows": {
            window: {t: _summarise(group) for t, group in by_type.items()} for window, by_type in buckets.items()
        },
    }


def _undated_count(runs: list[dict[str, Any]]) -> int:
    return sum(1 for run in runs if run["date"] is None and _fold(run["agent_type"]) is not None)


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def render_table(label: str, window: dict[str, Any]) -> str:
    header = f"{'agent_type':<18}{'N':>4}{'cost_med':>11}{'cost_iqr':>11}"
    header += "".join(f"{name:>20}" for name in COMPONENTS)
    lines = [f"window {label}", header]
    for agent in AGENT_TYPES:
        cell = window[agent]
        q1, q3 = cell["cost"]["q1"], cell["cost"]["q3"]
        iqr = None if q1 is None or q3 is None else q3 - q1
        row = f"{agent:<18}{cell['n']:>4}{_fmt(cell['cost']['median']):>11}{_fmt(iqr):>11}"
        row += "".join(f"{_fmt(cell['components'][name]['median']):>20}" for name in COMPONENTS)
        lines.append(row)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cost trend per loop agent type across two date windows.")
    parser.add_argument("summary", type=Path, help="token_stats_summary.json")
    parser.add_argument("--before-end", default=DEFAULT_BEFORE_END)
    parser.add_argument("--after-start", default=DEFAULT_AFTER_START)
    parser.add_argument("--json", action="store_true", help="print JSON instead of tables")
    args = parser.parse_args(argv)
    try:
        before_end = _parse_day(args.before_end, "--before-end")
        after_start = _parse_day(args.after_start, "--after-start")
        if after_start <= before_end:
            raise SummaryError("--after-start must be later than --before-end")
        runs = load_runs(args.summary)
    except SummaryError as exc:
        print(f"loop_token_trend: {exc}", file=sys.stderr)
        return 2
    print(f"loop_token_trend: dropped {_undated_count(runs)} undated run(s)", file=sys.stderr)
    report = build_report(runs, before_end, after_start)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(render_table(f"before (date <= {before_end})", report["windows"]["before"]))
    print()
    print(render_table(f"after (date >= {after_start})", report["windows"]["after"]))
    print()
    print("\n".join(CONFOUNDERS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
