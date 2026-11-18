import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_NAME = "loop_token_stats"
_SPEC = importlib.util.spec_from_file_location(_NAME, Path(__file__).parents[2] / "scripts" / "loop_token_stats.py")
assert _SPEC and _SPEC.loader
lts = importlib.util.module_from_spec(_SPEC)
sys.modules[_NAME] = lts
_SPEC.loader.exec_module(lts)

RECORD_FIELDS = {
    "agent_type",
    "date",
    "branch",
    "pr_number",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "full_read_sizes",
}


def _entry(**fields: Any) -> str:
    return json.dumps(fields)


def _assistant(
    ts: str,
    msg_id: str,
    usage: dict[str, Any] | None = None,
    content: list[Any] | None = None,
    branch: str | None = None,
) -> str:
    message: dict[str, Any] = {"id": msg_id, "role": "assistant", "content": content or []}
    if usage is not None:
        message["usage"] = usage
    return _entry(type="assistant", timestamp=ts, gitBranch=branch, message=message)


def _text(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def _read_call(tool_id: str, offset: bool = False) -> dict[str, Any]:
    tool_input: dict[str, Any] = {"file_path": "/synthetic/module.py"}
    if offset:
        tool_input["offset"] = 10
    return {"type": "tool_use", "id": tool_id, "name": "Read", "input": tool_input}


def _read_result(tool_id: str, content: Any) -> dict[str, Any]:
    return {"type": "tool_result", "tool_use_id": tool_id, "content": content}


def _write_session(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


USAGE_A = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20}
USAGE_B = {"input_tokens": 3, "output_tokens": 7, "cache_read_input_tokens": 50, "cache_creation_input_tokens": 0}


@pytest.fixture
def synthetic_transcripts(tmp_path: Path) -> Path:
    root = tmp_path / "transcripts" / "synthetic-project"
    session_a = [
        _assistant(
            "2026-10-20T09:00:00Z",
            "m0",
            content=[_text("opened https://github.com/o/r/pull/901")],
            branch="feat/issue-863-synth",
        ),
        _assistant("2026-10-20T09:01:00Z", "m1", USAGE_A, [_read_call("r1")]),
        _entry(type="user", timestamp="2026-10-20T09:01:05Z", message={"content": [_read_result("r1", "x" * 1234)]}),
        _assistant("2026-10-20T09:02:00Z", "m2", USAGE_B, [_read_call("r2", offset=True)]),
        _entry(type="user", timestamp="2026-10-20T09:02:05Z", message={"content": [_read_result("r2", "y" * 99)]}),
    ]
    session_b = [
        _entry(
            type="user",
            timestamp="2026-10-26T12:00:00Z",
            agentType="builder",
            gitBranch="feat/issue-863-other",
            message={"content": "hi"},
        ),
        _assistant("2026-10-26T12:01:00Z", "m3", USAGE_B, [_read_call("r3")]),
        _entry(
            type="user",
            timestamp="2026-10-26T12:01:05Z",
            message={"content": [_read_result("r3", [{"type": "text", "text": "z" * 500}])]},
        ),
    ]
    session_c = [
        _assistant("2026-11-11T08:00:00Z", "m4", USAGE_A, branch="feat/issue-863-late"),
    ]
    _write_session(root / "session-a.jsonl", session_a)
    _write_session(root / "session-b.jsonl", session_b)
    _write_session(root / "session-c.jsonl", session_c)
    return tmp_path / "transcripts"


def _records_by_branch(summary: list[dict[str, Any]], branch: str) -> dict[str, Any]:
    matches = [r for r in summary if r["branch"] == branch]
    assert len(matches) == 1
    return matches[0]


def test_discovers_records_from_synthetic_files(synthetic_transcripts: Path):
    result = lts.discover_records(synthetic_transcripts)
    assert len(result.records) == 3
    assert result.skipped == []
    assert sorted(r.date for r in result.records if r.date) == ["2026-10-20", "2026-10-26", "2026-11-11"]


def test_archive_file_has_expected_per_run_fields(synthetic_transcripts: Path, tmp_path: Path):
    out_dir = tmp_path / "archive"
    summary_path, _ = lts.write_archive(lts.discover_records(synthetic_transcripts).records, out_dir)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(summary) == 3
    assert all(set(r) == RECORD_FIELDS for r in summary)

    run_a = _records_by_branch(summary, "feat/issue-863-synth")
    assert run_a["date"] == "2026-10-20"
    assert run_a["agent_type"] == "main"
    assert run_a["pr_number"] == 901
    assert run_a["input_tokens"] == 13
    assert run_a["output_tokens"] == 12
    assert run_a["cache_read_tokens"] == 150
    assert run_a["cache_write_tokens"] == 20
    assert run_a["full_read_sizes"] == [1234]

    run_b = _records_by_branch(summary, "feat/issue-863-other")
    assert run_b["agent_type"] == "builder"
    assert run_b["pr_number"] is None
    assert run_b["full_read_sizes"] == [500]


def test_gap_note_lists_missing_dates(synthetic_transcripts: Path, tmp_path: Path):
    out_dir = tmp_path / "archive"
    _, note_path = lts.write_archive(lts.discover_records(synthetic_transcripts).records, out_dir)
    note = note_path.read_text(encoding="utf-8")
    assert "2026-10-27" in note
    assert "2026-11-10" in note
    assert "2026-10-26" not in note
    assert "2026-11-11" not in note
    assert "No gap found" not in note


def test_cli_archive_writes_to_given_out_dir(
    synthetic_transcripts: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    out_dir = tmp_path / "cli-out"
    assert lts.main([str(synthetic_transcripts), "--archive", str(out_dir)]) == 0
    assert (out_dir / lts.SUMMARY_NAME).is_file()
    assert (out_dir / lts.NOTE_NAME).is_file()
    assert str(out_dir / lts.SUMMARY_NAME) in capsys.readouterr().out


def test_no_gap_note_when_every_date_present(tmp_path: Path):
    root = tmp_path / "full"
    days = [lts.GAP_START + lts.dt.timedelta(days=i) for i in range((lts.GAP_END - lts.GAP_START).days + 1)]
    for day in days:
        line = _assistant(f"{day.isoformat()}T10:00:00Z", f"m-{day.isoformat()}", USAGE_B)
        _write_session(root / f"{day.isoformat()}.jsonl", [line])
    _, note_path = lts.write_archive(lts.discover_records(root).records, tmp_path / "out")
    assert "No gap found" in note_path.read_text(encoding="utf-8")


def test_corrupt_lines_and_repeated_message_ids_are_handled(tmp_path: Path):
    path = _write_session(
        tmp_path / "t" / "noisy.jsonl",
        [
            "{not json",
            _assistant("2026-10-30T10:00:00Z", "dup", USAGE_A),
            _assistant("2026-10-30T10:00:01Z", "dup", USAGE_A),
        ],
    )
    record = lts.parse_transcript(path)
    assert record.input_tokens == USAGE_A["input_tokens"]
    assert record.cache_read_tokens == USAGE_A["cache_read_input_tokens"]


def test_empty_folder_gives_no_records_and_full_gap(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    records = lts.discover_records(empty).records
    assert records == []
    missing = lts.find_gap(r.date for r in records)
    assert missing[0] == "2026-10-27"
    assert missing[-1] == "2026-11-10"
    assert len(missing) == 15


def test_cli_without_archive_prints_json(synthetic_transcripts: Path, capsys: pytest.CaptureFixture[str]):
    assert lts.main([str(synthetic_transcripts)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert len(printed) == 3


def test_cli_rejects_missing_input_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert lts.main([str(tmp_path / "does-not-exist")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_non_utf8_file_is_skipped_and_reported(synthetic_transcripts: Path, capsys: pytest.CaptureFixture[str]):
    bad = synthetic_transcripts / "synthetic-project" / "binary.jsonl"
    bad.write_bytes(b"\xff\xfe\x00not utf-8 \x80\x81\n")
    result = lts.discover_records(synthetic_transcripts)
    assert len(result.records) == 3
    assert result.skipped == [bad]
    assert f"skipped {bad}" in capsys.readouterr().err


def test_non_numeric_usage_counts_as_zero(tmp_path: Path):
    usage = {
        "input_tokens": "abc",
        "output_tokens": 4,
        "cache_read_input_tokens": [1],
        "cache_creation_input_tokens": None,
    }
    path = _write_session(tmp_path / "t" / "odd.jsonl", [_assistant("2026-10-30T10:00:00Z", "odd", usage)])
    record = lts.parse_transcript(path)
    assert record.input_tokens == 0
    assert record.output_tokens == 4
    assert record.cache_read_tokens == 0
    assert record.cache_write_tokens == 0


def test_pr_quoted_in_tool_result_is_not_captured(tmp_path: Path):
    path = _write_session(
        tmp_path / "t" / "quoted.jsonl",
        [
            _assistant("2026-10-30T10:00:00Z", "q1", USAGE_B, [_read_call("q")]),
            _entry(
                type="user",
                timestamp="2026-10-30T10:00:01Z",
                message={"content": [_read_result("q", "see https://github.com/o/other/pull/777")]},
            ),
            _assistant("2026-10-30T10:00:02Z", "q2", USAGE_B, content=[_text("done")]),
        ],
    )
    assert lts.parse_transcript(path).pr_number is None


def test_structured_pr_number_field_is_captured(tmp_path: Path):
    line = _entry(
        type="assistant",
        timestamp="2026-10-30T10:00:00Z",
        prNumber=55,
        message={"id": "s1", "role": "assistant", "content": [_text("ok")]},
    )
    assert lts.parse_transcript(_write_session(tmp_path / "t" / "pr.jsonl", [line])).pr_number == 55


def test_null_offset_and_limit_count_as_full_read(tmp_path: Path):
    call = {
        "type": "tool_use",
        "id": "n1",
        "name": "Read",
        "input": {"file_path": "/s.py", "offset": None, "limit": None},
    }
    path = _write_session(
        tmp_path / "t" / "nulls.jsonl",
        [
            _assistant("2026-10-30T10:00:00Z", "n1", USAGE_B, [call]),
            _entry(type="user", timestamp="2026-10-30T10:00:01Z", message={"content": [_read_result("n1", "abcdefg")]}),
        ],
    )
    assert lts.parse_transcript(path).full_read_sizes == [7]


def test_cli_rejects_archive_path_that_is_a_file(
    synthetic_transcripts: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    target = tmp_path / "not-a-dir"
    target.write_text("occupied", encoding="utf-8")
    assert lts.main([str(synthetic_transcripts), "--archive", str(target)]) == 2
    assert "must be a directory" in capsys.readouterr().err
    assert target.read_text(encoding="utf-8") == "occupied"


def _write_meta(transcript: Path, content: str | bytes) -> None:
    meta = transcript.with_suffix(".meta.json")
    if isinstance(content, bytes):
        meta.write_bytes(content)
    else:
        meta.write_text(content, encoding="utf-8")


def _subagent_session(tmp_path: Path, name: str = "agent-abc") -> Path:
    return _write_session(
        tmp_path / "sub" / f"{name}.jsonl",
        [_assistant("2026-10-30T10:00:00Z", f"{name}-m", USAGE_A)],
    )


def test_subagent_meta_json_sets_agent_type(tmp_path: Path):
    path = _subagent_session(tmp_path)
    _write_meta(path, '{"agentType":"reviewer","isBuiltIn":false}')
    assert lts.parse_transcript(path).agent_type == "reviewer"


def test_meta_json_wins_over_inline_agent_type(tmp_path: Path):
    path = _write_session(
        tmp_path / "sub" / "agent-inline.jsonl",
        [
            _entry(type="user", timestamp="2026-10-30T10:00:00Z", agentType="builder", message={"content": "hi"}),
            _assistant("2026-10-30T10:00:01Z", "i1", USAGE_B),
        ],
    )
    _write_meta(path, '{"agentType":"reviewer"}')
    assert lts.parse_transcript(path).agent_type == "reviewer"


def test_inline_agent_type_used_when_meta_json_absent(tmp_path: Path):
    path = _write_session(
        tmp_path / "sub" / "agent-inline.jsonl",
        [_entry(type="user", timestamp="2026-10-30T10:00:00Z", agentType="builder", message={"content": "hi"})],
    )
    assert lts.parse_transcript(path).agent_type == "builder"


def test_missing_meta_json_keeps_main(tmp_path: Path):
    assert lts.parse_transcript(_subagent_session(tmp_path)).agent_type == "main"


def test_malformed_meta_json_keeps_main_and_parses_transcript(tmp_path: Path):
    path = _subagent_session(tmp_path)
    _write_meta(path, "{not json")
    record = lts.parse_transcript(path)
    assert record.agent_type == "main"
    assert record.input_tokens == USAGE_A["input_tokens"]


def test_unreadable_meta_json_keeps_main_and_parses_transcript(tmp_path: Path):
    path = _subagent_session(tmp_path)
    _write_meta(path, b"\xff\xfe\x80 not utf-8")
    record = lts.parse_transcript(path)
    assert record.agent_type == "main"
    assert record.input_tokens == USAGE_A["input_tokens"]


@pytest.mark.parametrize(
    "meta_text",
    ['["reviewer"]', '"reviewer"', '{"agentType": 7}', '{"agentType": ""}', '{"agentType": null}', "{}"],
)
def test_non_string_or_empty_meta_agent_type_keeps_main(tmp_path: Path, meta_text: str):
    path = _subagent_session(tmp_path)
    _write_meta(path, meta_text)
    assert lts.parse_transcript(path).agent_type == "main"
