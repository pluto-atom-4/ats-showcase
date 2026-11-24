"""Paired cost reduction stats for the controlled strip-comments replay pilot."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Sibling scripts are imported by bare name: run this file directly or keep scripts/ on sys.path.
from loop_token_stats import parse_transcript
from loop_token_trend import COMPONENTS, cost

BOOTSTRAP_SEED = 0
BOOTSTRAP_RESAMPLES = 10_000
MDE_SAMPLE_SIZES: tuple[int, ...] = (5, 10, 15, 20)
STOP_RULE_PCT = 10.0
STOP_RULE_MESSAGE = "not detectable at this sample size"
VARIANTS = ("pre", "post")
SIDES = ("pre", "post")

# Hardcoded so the pilot needs no scipy; only df 4/9/14/19 (n = 5/10/15/20) are reachable.
_T_TABLE: dict[tuple[int, float], float] = {
    (4, 0.80): 0.941,
    (9, 0.80): 0.883,
    (14, 0.80): 0.868,
    (19, 0.80): 0.861,
    (4, 0.975): 2.776,
    (9, 0.975): 2.262,
    (14, 0.975): 2.145,
    (19, 0.975): 2.093,
}


class PilotError(ValueError):
    """Input or argument error reported to stderr with exit code 2."""


def t_quantile(df: int, prob: float) -> float:
    """Return the hardcoded t critical value for df and prob; raises KeyError if absent."""
    return _T_TABLE[(df, prob)]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_entry(item: object, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise PilotError(f"entry {index} is not an object")
    if not _is_int(item.get("pr")):
        raise PilotError(f"entry {index} has no integer pr")
    if item.get("variant") not in VARIANTS:
        raise PilotError(f"entry {index} variant must be 'pre' or 'post', got {item.get('variant')!r}")
    transcript = item.get("transcript")
    if not isinstance(transcript, str) or not transcript:
        raise PilotError(f"entry {index} has no transcript path")
    return item


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Read and validate the pair manifest; raises PilotError on malformed JSON or entries."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise PilotError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise PilotError(f"{path} must contain a JSON list")
    return [_validate_entry(item, i) for i, item in enumerate(payload)]


def pair_entries(entries: list[dict[str, Any]]) -> tuple[dict[int, dict[str, str]], list[dict[str, Any]]]:
    """Group manifest entries by PR into complete pre/post pairs; returns (pairs, skipped)."""
    grouped: dict[int, dict[str, str]] = {}
    for entry in entries:
        variants = grouped.setdefault(entry["pr"], {})
        if entry["variant"] in variants:
            raise PilotError(f"duplicate {entry['variant']} entry for pr {entry['pr']}")
        variants[entry["variant"]] = entry["transcript"]
    pairs: dict[int, dict[str, str]] = {}
    skipped: list[dict[str, Any]] = []
    for pr in sorted(grouped):
        missing = [variant for variant in VARIANTS if variant not in grouped[pr]]
        if missing:
            skipped.append({"pr": pr, "reason": f"missing {missing[0]} variant"})
        else:
            pairs[pr] = grouped[pr]
    return pairs, skipped


def _parse(path: Path) -> dict[str, Any]:
    try:
        return asdict(parse_transcript(path))
    except (OSError, UnicodeDecodeError) as exc:
        raise PilotError(f"cannot read transcript {path}: {exc}") from exc


def pair_cost(pr: int, pre_path: Path, post_path: Path) -> dict[str, Any] | None:
    """Return pre/post cost and component values for one PR, or None when pre cost is 0."""
    pre = _parse(pre_path)
    post = _parse(post_path)
    cost_pre = cost(pre)
    if cost_pre == 0:
        return None
    cost_post = cost(post)
    return {
        "pr": pr,
        "cost_pre": cost_pre,
        "cost_post": cost_post,
        "reduction_pct": (cost_pre - cost_post) / cost_pre * 100,
        "components_pre": {name: pre[name] for name in COMPONENTS},
        "components_post": {name: post[name] for name in COMPONENTS},
    }


def bootstrap_mean_range(reductions: list[float]) -> tuple[float, float]:
    """Bootstrap a 95% range for the mean of reduction_pct using seeded resampling."""
    rng = random.Random(BOOTSTRAP_SEED)
    size = len(reductions)
    means = sorted(statistics.fmean(rng.choices(reductions, k=size)) for _ in range(BOOTSTRAP_RESAMPLES))
    last = BOOTSTRAP_RESAMPLES - 1
    return means[round(0.025 * last)], means[round(0.975 * last)]


def mde(sd: float, n: int) -> float:
    """Minimum detectable effect in percentage points for a paired design of n pairs."""
    df = n - 1
    return sd * (t_quantile(df, 0.975) + t_quantile(df, 0.80)) / math.sqrt(n)


def _component_means(pairs: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {
        side: {name: statistics.fmean(pair[f"components_{side}"][name] for pair in pairs) for name in COMPONENTS}
        for side in SIDES
    }


def build_report(pairs: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the full report dict from pair_cost results and skip records."""
    report: dict[str, Any] = {
        "n_pairs": len(pairs),
        "mean_reduction_pct": None,
        "median_reduction_pct": None,
        "sd_reduction_pct": None,
        "ci_low": None,
        "ci_high": None,
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "resampling_unit": "pair",
        "mde": dict.fromkeys(str(n) for n in MDE_SAMPLE_SIZES),
        "stop_rule": None,
        # Keys stay present with null values so the JSON shape is stable across outcomes.
        "components": {side: dict.fromkeys(COMPONENTS) for side in SIDES},
        "pairs": [{key: pair[key] for key in ("pr", "cost_pre", "cost_post", "reduction_pct")} for pair in pairs],
        "skipped": sorted(skipped, key=lambda item: item["pr"]),
    }
    if len(pairs) < 2:
        return report
    reductions = [pair["reduction_pct"] for pair in pairs]
    sd = statistics.stdev(reductions)
    report["mean_reduction_pct"] = statistics.fmean(reductions)
    report["median_reduction_pct"] = statistics.median(reductions)
    report["sd_reduction_pct"] = sd
    report["ci_low"], report["ci_high"] = bootstrap_mean_range(reductions)
    report["mde"] = {str(n): mde(sd, n) for n in MDE_SAMPLE_SIZES}
    report["components"] = _component_means(pairs)
    if report["mde"]["20"] > STOP_RULE_PCT:
        report["stop_rule"] = STOP_RULE_MESSAGE
    return report


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def _num(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def render_table(report: dict[str, Any]) -> str:
    """Render the report as a plain-text table with pair rows and summary lines."""
    lines = [f"{'pr':>6}{'cost_pre':>14}{'cost_post':>14}{'reduction':>12}"]
    for pair in report["pairs"]:
        lines.append(
            f"{pair['pr']:>6}{pair['cost_pre']:>14.1f}{pair['cost_post']:>14.1f}{_pct(pair['reduction_pct']):>12}"
        )
    low, high = report["ci_low"], report["ci_high"]
    band = "-" if low is None or high is None else f"{low:.1f}% to {high:.1f}%"
    lines += [
        "",
        f"{'N pairs':<24}{report['n_pairs']}",
        f"{'mean reduction':<24}{_pct(report['mean_reduction_pct'])}",
        f"{'median reduction':<24}{_pct(report['median_reduction_pct'])}",
        f"{'sd reduction':<24}{_num(report['sd_reduction_pct'])}",
        f"{'95% range of mean':<24}{band}",
        f"{'resampling':<24}{report['resampling_unit']}, {BOOTSTRAP_RESAMPLES} draws, seed {BOOTSTRAP_SEED}",
    ]
    for n in MDE_SAMPLE_SIZES:
        lines.append(f"{'MDE n=' + str(n):<24}{_pct(report['mde'][str(n)])}")
    for side in SIDES:
        for name in COMPONENTS:
            lines.append(f"{side + ' ' + name:<24}{_num(report['components'][side][name])}")
    for item in report["skipped"]:
        lines.append(f"{'skipped pr ' + str(item['pr']):<24}{item['reason']}")
    if report["stop_rule"] is not None:
        lines.append(report["stop_rule"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the pilot pair-stats CLI; returns a process exit code."""
    parser = argparse.ArgumentParser(description="Paired cost reduction stats for the strip-comments replay pilot.")
    parser.add_argument("manifest", type=Path, help="JSON list of {pr, variant, transcript} entries")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)
    try:
        entries = load_manifest(args.manifest)
        pairs_by_pr, skipped = pair_entries(entries)
        usable: list[dict[str, Any]] = []
        for pr, variants in pairs_by_pr.items():
            result = pair_cost(pr, Path(variants["pre"]), Path(variants["post"]))
            if result is None:
                skipped.append({"pr": pr, "reason": "pre cost is 0"})
            else:
                usable.append(result)
    except PilotError as exc:
        print(f"pilot_pair_stats: {exc}", file=sys.stderr)
        return 2
    report = build_report(usable, skipped)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_table(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
