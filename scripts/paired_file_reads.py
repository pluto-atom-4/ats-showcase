"""Paired per-file read size reduction between a before and an after date window."""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from pathlib import Path
from typing import Any

AGENT_TYPES = ("architect", "builder", "reviewer", "slop-hunter", "cavecrew-builder", "cavecrew-reviewer")
CAVEMAN_PREFIX = "caveman:"
DEFAULT_BEFORE_END = "2026-10-26"
DEFAULT_AFTER_START = "2026-11-21"
DAY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
PATH_ROOTS = ("src/", "tests/")
BOOTSTRAP_SEED = 0
BOOTSTRAP_RESAMPLES = 10_000


class SummaryError(ValueError):
    """Input or argument error reported to stderr with exit code 2."""


def _validate_read(item: object, record: int, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SummaryError(f"record {record} full_reads[{index}] is not an object")
    if not isinstance(item.get("path"), str):
        raise SummaryError(f"record {record} full_reads[{index}] has no string path")
    size = item.get("size")
    if not isinstance(size, int) or isinstance(size, bool):
        raise SummaryError(f"record {record} full_reads[{index}] size is not an integer")
    return item


def _validate_run(item: object, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SummaryError(f"record {index} is not an object")
    if not isinstance(item.get("agent_type"), str):
        raise SummaryError(f"record {index} has no string agent_type")
    date = item.get("date")
    if date is not None and not (isinstance(date, str) and DAY_RE.fullmatch(date)):
        raise SummaryError(f"record {index} has a bad date: {date!r}")
    reads = item.get("full_reads", [])
    if not isinstance(reads, list):
        raise SummaryError(f"record {index} full_reads is not a list")
    for position, read in enumerate(reads):
        _validate_read(read, index, position)
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


def _keep_path(path: str) -> bool:
    return bool(path) and path.endswith(".py") and path.startswith(PATH_ROOTS)


def _pool_sizes(
    runs: list[dict[str, Any]], before_end: str, after_start: str
) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    before: dict[str, list[int]] = {}
    after: dict[str, list[int]] = {}
    for run in runs:
        date = run.get("date")
        if _fold(run["agent_type"]) is None or date is None:
            continue
        if date <= before_end:
            target = before
        elif date >= after_start:
            target = after
        else:
            continue
        for read in run.get("full_reads", []):
            if _keep_path(read["path"]):
                target.setdefault(read["path"], []).append(read["size"])
    return before, after


def paired_files(runs: list[dict[str, Any]], before_end: str, after_start: str) -> list[dict[str, Any]]:
    before, after = _pool_sizes(runs, before_end, after_start)
    rows: list[dict[str, Any]] = []
    for path in sorted(before.keys() & after.keys()):
        mean_before = statistics.fmean(before[path])
        if mean_before == 0:
            continue
        mean_after = statistics.fmean(after[path])
        rows.append(
            {
                "path": path,
                "mean_before": mean_before,
                "mean_after": mean_after,
                "reduction_pct": (mean_before - mean_after) / mean_before * 100,
            }
        )
    return rows


def bootstrap_median_range(reductions: list[float]) -> tuple[float, float]:
    rng = random.Random(BOOTSTRAP_SEED)
    size = len(reductions)
    medians = sorted(statistics.median(rng.choices(reductions, k=size)) for _ in range(BOOTSTRAP_RESAMPLES))
    last = BOOTSTRAP_RESAMPLES - 1
    return medians[round(0.025 * last)], medians[round(0.975 * last)]


def build_report(
    runs: list[dict[str, Any]], before_end: str, after_start: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = paired_files(runs, before_end, after_start)
    summary: dict[str, Any] = {
        "n_files": len(rows),
        "median_reduction_pct": None,
        "ci_low": None,
        "ci_high": None,
        "total_reduction_pct": None,
        "before_end": before_end,
        "after_start": after_start,
        "seed": BOOTSTRAP_SEED,
        "resampling_unit": "file",
    }
    if not rows:
        return rows, summary
    reductions = [row["reduction_pct"] for row in rows]
    summary["median_reduction_pct"] = statistics.median(reductions)
    summary["ci_low"], summary["ci_high"] = bootstrap_median_range(reductions)
    sum_before = sum(row["mean_before"] for row in rows)
    if sum_before != 0:
        sum_after = sum(row["mean_after"] for row in rows)
        summary["total_reduction_pct"] = (sum_before - sum_after) / sum_before * 100
    return rows, summary


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def render_table(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    width = max([len(row["path"]) for row in rows], default=4)
    header = f"{'path':<{width}}{'before':>12}{'after':>12}{'reduction':>12}"
    lines = [header]
    for row in rows:
        lines.append(
            f"{row['path']:<{width}}{row['mean_before']:>12.1f}{row['mean_after']:>12.1f}"
            f"{_pct(row['reduction_pct']):>12}"
        )
    low, high = summary["ci_low"], summary["ci_high"]
    band = "-" if low is None or high is None else f"{low:.1f}% to {high:.1f}%"
    lines += [
        "",
        f"{'N files':<24}{summary['n_files']}",
        f"{'median reduction':<24}{_pct(summary['median_reduction_pct'])}",
        f"{'95% range of median':<24}{band}",
        f"{'total reduction':<24}{_pct(summary['total_reduction_pct'])}",
        f"{'resampling':<24}{summary['resampling_unit']}, {BOOTSTRAP_RESAMPLES} draws, seed {summary['seed']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paired per-file read size reduction across two date windows.")
    parser.add_argument("summary", type=Path, help="token_stats_summary.json")
    parser.add_argument("--before-end", default=DEFAULT_BEFORE_END)
    parser.add_argument("--after-start", default=DEFAULT_AFTER_START)
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    parser.add_argument("--gap-note", type=Path, default=None, help="transcript gap note path, printed only")
    args = parser.parse_args(argv)
    try:
        before_end = _parse_day(args.before_end, "--before-end")
        after_start = _parse_day(args.after_start, "--after-start")
        if after_start <= before_end:
            raise SummaryError("--after-start must be later than --before-end")
        runs = load_runs(args.summary)
    except SummaryError as exc:
        print(f"paired_file_reads: {exc}", file=sys.stderr)
        return 2
    rows, summary = build_report(runs, before_end, after_start)
    if args.json:
        if args.gap_note is not None:
            print(f"gap note: {args.gap_note}", file=sys.stderr)
        print(json.dumps(summary, indent=2))
        return 0
    if args.gap_note is not None:
        print(f"gap note: {args.gap_note}")
    print(render_table(rows, summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
