"""Archive per-run token usage and full-file-read sizes from Claude Code JSONL transcripts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

GAP_START = dt.date(2026, 10, 27)
GAP_END = dt.date(2026, 11, 10)
SUMMARY_NAME = "token_stats_summary.json"
NOTE_NAME = "token_stats_gap_note.txt"
_PULL_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")


@dataclass
class RunRecord:
    agent_type: str
    date: str | None
    branch: str | None
    pr_number: int | None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    full_read_sizes: list[int] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    records: list[RunRecord]
    skipped: list[Path]


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _add_usage(record: RunRecord, usage: dict[str, Any]) -> None:
    # Keys follow the Anthropic API usage fields so sums match billing exports.
    record.input_tokens += _as_int(usage.get("input_tokens"))
    record.output_tokens += _as_int(usage.get("output_tokens"))
    record.cache_read_tokens += _as_int(usage.get("cache_read_input_tokens"))
    record.cache_write_tokens += _as_int(usage.get("cache_creation_input_tokens"))


def _result_size(content: Any) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            text = block.get("text") if isinstance(block, dict) else None
            if isinstance(text, str):
                total += len(text)
        return total
    return 0


def _assistant_texts(obj: dict[str, Any], message: dict[str, Any]) -> list[str]:
    # Only assistant-authored text counts: tool results quote PRs from unrelated work.
    if obj.get("type") != "assistant" and message.get("role") != "assistant":
        return []
    content = message.get("content")
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [
        b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)
    ]


def _pr_from_obj(obj: dict[str, Any]) -> int | None:
    explicit = obj.get("prNumber", obj.get("pr_number"))
    if isinstance(explicit, int) and not isinstance(explicit, bool):
        return explicit
    message = obj.get("message")
    if not isinstance(message, dict):
        return None
    for text in _assistant_texts(obj, message):
        match = _PULL_URL.search(text)
        if match:
            return int(match.group(1))
    return None


def _apply_metadata(record: RunRecord, obj: dict[str, Any]) -> None:
    timestamp = obj.get("timestamp")
    if record.date is None and isinstance(timestamp, str):
        record.date = timestamp[:10]
    branch = obj.get("gitBranch")
    if record.branch is None and isinstance(branch, str) and branch:
        record.branch = branch
    if record.agent_type == "main" and isinstance(obj.get("agentType"), str):
        record.agent_type = obj["agentType"]
    if record.pr_number is None:
        record.pr_number = _pr_from_obj(obj)


def _apply_tool_blocks(record: RunRecord, content: list[Any], full_read_ids: set[str]) -> None:
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use" and block.get("name") == "Read":
            tool_input = block.get("input")
            if isinstance(tool_input, dict) and tool_input.get("offset") is None and tool_input.get("limit") is None:
                full_read_ids.add(str(block.get("id")))
        elif block.get("type") == "tool_result":
            tool_id = str(block.get("tool_use_id"))
            if tool_id in full_read_ids:
                full_read_ids.discard(tool_id)
                record.full_read_sizes.append(_result_size(block.get("content")))


def _apply_message(record: RunRecord, message: dict[str, Any], seen: set[str], full_read_ids: set[str]) -> None:
    # Streamed assistant chunks repeat the same message id and usage block.
    message_id = message.get("id")
    usage = message.get("usage")
    if isinstance(usage, dict) and (not isinstance(message_id, str) or message_id not in seen):
        if isinstance(message_id, str):
            seen.add(message_id)
        _add_usage(record, usage)

    content = message.get("content")
    if isinstance(content, list):
        _apply_tool_blocks(record, content, full_read_ids)


def parse_transcript(path: Path) -> RunRecord:
    """Summarise one JSONL transcript; raises OSError or UnicodeDecodeError if unreadable."""
    record = RunRecord(agent_type="main", date=None, branch=None, pr_number=None)
    seen_message_ids: set[str] = set()
    full_read_ids: set[str] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        _apply_metadata(record, obj)
        message = obj.get("message")
        if isinstance(message, dict):
            _apply_message(record, message, seen_message_ids, full_read_ids)

    return record


def discover_records(input_dir: Path) -> DiscoveryResult:
    """Parse every JSONL transcript under a folder, recursively; unreadable files are skipped with a stderr line."""
    result = DiscoveryResult(records=[], skipped=[])
    for path in sorted(input_dir.rglob("*.jsonl")):
        try:
            result.records.append(parse_transcript(path))
        except (OSError, UnicodeDecodeError) as exc:
            result.skipped.append(path)
            print(f"skipped {path}: {exc}", file=sys.stderr)
    return result


def find_gap(dates: Iterable[str | None], start: dt.date = GAP_START, end: dt.date = GAP_END) -> list[str]:
    """Return ISO dates in the inclusive range that have no transcript."""
    present = {d for d in dates if d}
    days = ((start + dt.timedelta(days=i)).isoformat() for i in range((end - start).days + 1))
    return [day for day in days if day not in present]


def _gap_note(missing: list[str], start: dt.date, end: dt.date) -> str:
    label = f"{start.isoformat()} to {end.isoformat()}"
    if not missing:
        return f"No gap found in {label}: every date has at least one transcript file.\n"
    lines = [f"Gap {label}: no transcript files for {len(missing)} date(s):"]
    lines.extend(f"  - {day}" for day in missing)
    return "\n".join(lines) + "\n"


def write_archive(records: list[RunRecord], out_dir: Path) -> tuple[Path, Path]:
    """Write the per-run summary JSON and the transcript gap note into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / SUMMARY_NAME
    summary_path.write_text(json.dumps([asdict(r) for r in records], indent=2) + "\n", encoding="utf-8")

    missing = find_gap(r.date for r in records)
    note_path = out_dir / NOTE_NAME
    note_path.write_text(_gap_note(missing, GAP_START, GAP_END), encoding="utf-8")
    return summary_path, note_path


def main(argv: list[str] | None = None) -> int:
    """Run the transcript token-stats CLI; returns a process exit code."""
    parser = argparse.ArgumentParser(description="Summarise Claude Code JSONL transcripts.")
    parser.add_argument("input_dir", type=Path, help="Folder searched recursively for *.jsonl transcripts.")
    parser.add_argument("--archive", type=Path, default=None, help="Output folder for the summary and gap note.")
    args = parser.parse_args(argv)

    if not args.input_dir.is_dir():
        print(f"not a directory: {args.input_dir}", file=sys.stderr)
        return 2
    if args.archive is not None and args.archive.exists() and not args.archive.is_dir():
        print(f"--archive must be a directory, not a file: {args.archive}", file=sys.stderr)
        return 2

    result = discover_records(args.input_dir)
    if args.archive is None:
        print(json.dumps([asdict(r) for r in result.records], indent=2))
        return 0

    summary_path, note_path = write_archive(result.records, args.archive)
    print(f"{len(result.records)} run(s) -> {summary_path}")
    print(f"gap note -> {note_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
