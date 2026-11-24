import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_NAME = "loop_token_trend"
_SPEC = importlib.util.spec_from_file_location(_NAME, Path(__file__).parents[2] / "scripts" / "loop_token_trend.py")
assert _SPEC and _SPEC.loader
ltt = importlib.util.module_from_spec(_SPEC)
sys.modules[_NAME] = ltt
_SPEC.loader.exec_module(ltt)

BEFORE_END = "2026-10-26"
AFTER_START = "2026-11-21"


def _run(
    agent_type: str | None,
    date: str | None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> dict[str, Any]:
    return {
        "agent_type": agent_type,
        "date": date,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
    }


def _write(tmp_path: Path, payload: Any) -> Path:
    path = tmp_path / "token_stats_summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _table_row(out: str, agent_type: str) -> list[str]:
    rows = [line.split() for line in out.splitlines()]
    matches = [row for row in rows if row and row[0] == agent_type]
    assert len(matches) == 2, f"expected one row per window for {agent_type}"
    return matches[0]


def test_median_and_quartiles_match_hand_computation():
    runs = [_run("builder", "2026-10-20", input_tokens=v) for v in (10, 20, 30, 40, 50)]
    builder = ltt.build_report(runs, BEFORE_END, AFTER_START)["windows"]["before"]["builder"]
    assert builder["n"] == 5
    assert builder["cost"] == {"median": 30, "q1": 15, "q3": 45}


def test_iqr_column_is_q3_minus_q1_in_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    runs = [_run("builder", "2026-10-20", input_tokens=v) for v in (10, 20, 30, 40, 50)]
    assert ltt.main([str(_write(tmp_path, runs))]) == 0
    row = _table_row(capsys.readouterr().out, "builder")
    assert row[:4] == ["builder", "5", "30.0", "30.0"]


def test_single_run_has_median_but_no_iqr():
    runs = [_run("reviewer", "2026-10-20", input_tokens=7)]
    cell = ltt.build_report(runs, BEFORE_END, AFTER_START)["windows"]["before"]["reviewer"]
    assert cell["n"] == 1
    assert cell["cost"] == {"median": 7, "q1": None, "q3": None}


def test_cost_weights_and_component_medians():
    runs = [
        _run("architect", "2026-10-20", input_tokens=2, output_tokens=1, cache_read_tokens=10, cache_write_tokens=4),
        _run("architect", "2026-10-21", input_tokens=4, output_tokens=3, cache_read_tokens=20, cache_write_tokens=8),
    ]
    cell = ltt.build_report(runs, BEFORE_END, AFTER_START)["windows"]["before"]["architect"]
    assert cell["cost"]["median"] == pytest.approx((13 + 31) / 2)
    assert cell["components"] == {
        "input_tokens": {"median": 3},
        "output_tokens": {"median": 2},
        "cache_read_tokens": {"median": 15},
        "cache_write_tokens": {"median": 6},
    }


def test_gap_dates_and_undated_runs_are_excluded_from_both_windows(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    runs = [
        _run("builder", "2026-10-20", input_tokens=10),
        _run("builder", "2026-10-27", input_tokens=1000),
        _run("builder", "2026-11-10", input_tokens=1000),
        _run("builder", "2026-11-15", input_tokens=1000),
        _run("builder", None, input_tokens=1000),
        _run("builder", "2026-11-25", input_tokens=20),
    ]
    assert ltt.main([str(_write(tmp_path, runs)), "--json"]) == 0
    captured = capsys.readouterr()
    assert "dropped 1 undated" in captured.err
    windows = json.loads(captured.out)["windows"]
    assert windows["before"]["builder"]["n"] == 1
    assert windows["before"]["builder"]["cost"]["median"] == 10
    assert windows["after"]["builder"]["n"] == 1
    assert windows["after"]["builder"]["cost"]["median"] == 20


def test_type_with_no_runs_in_window_prints_zero_row(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    runs = [_run("reviewer", "2026-10-20", input_tokens=5)]
    assert ltt.main([str(_write(tmp_path, runs))]) == 0
    out = capsys.readouterr().out
    assert _table_row(out, "reviewer")[:2] == ["reviewer", "1"]
    assert _table_row(out, "slop-hunter") == ["slop-hunter", "0"] + ["-"] * 6
    report = ltt.build_report(runs, BEFORE_END, AFTER_START)
    assert report["windows"]["after"]["reviewer"] == {
        "n": 0,
        "cost": {"median": None, "q1": None, "q3": None},
        "components": {name: {"median": None} for name in ltt.COMPONENTS},
    }


def test_ignored_types_are_absent_and_undated_ignored_runs_not_counted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    runs = [
        _run("main", "2026-10-20", input_tokens=99),
        _run("gate-enforcer", "2026-10-20", input_tokens=99),
        _run("general-purpose", None, input_tokens=99),
        _run("caveman:cavecrew-investigator", "2026-10-20", input_tokens=99),
        _run("builder", "2026-10-20", input_tokens=1),
    ]
    assert ltt.main([str(_write(tmp_path, runs)), "--json"]) == 0
    captured = capsys.readouterr()
    assert "dropped 0 undated" in captured.err
    windows = json.loads(captured.out)["windows"]
    assert list(windows["before"]) == list(ltt.AGENT_TYPES)
    assert "main" not in captured.out
    assert "general-purpose" not in captured.out
    assert "investigator" not in captured.out


def test_caveman_prefix_is_folded_into_unprefixed_type():
    runs = [
        _run("caveman:cavecrew-builder", "2026-10-20", input_tokens=4),
        _run("cavecrew-builder", "2026-10-21", input_tokens=8),
        _run("caveman:cavecrew-reviewer", "2026-11-22", input_tokens=2),
    ]
    windows = ltt.build_report(runs, BEFORE_END, AFTER_START)["windows"]
    assert windows["before"]["cavecrew-builder"]["n"] == 2
    assert windows["before"]["cavecrew-builder"]["cost"]["median"] == 6
    assert windows["after"]["cavecrew-reviewer"]["n"] == 1
    assert windows["after"]["cavecrew-builder"]["n"] == 0
    assert "caveman:cavecrew-builder" not in windows["before"]


def test_json_output_round_trips_with_default_params(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    runs = [_run("builder", "2026-10-20", input_tokens=10), _run("builder", "2026-11-22", input_tokens=20)]
    assert ltt.main([str(_write(tmp_path, runs)), "--json"]) == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert set(parsed) == {"params", "windows"}
    assert parsed["params"] == {"before_end": BEFORE_END, "after_start": AFTER_START}
    assert set(parsed["windows"]) == {"before", "after"}
    assert parsed["windows"]["after"]["builder"]["components"]["input_tokens"] == {"median": 20}
    assert "PR size" not in out


def test_json_params_follow_flags(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    runs = [_run("builder", "2026-10-31", input_tokens=10), _run("builder", "2026-11-01", input_tokens=20)]
    args = [str(_write(tmp_path, runs)), "--json", "--before-end", "2026-10-31", "--after-start", "2026-11-01"]
    assert ltt.main(args) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["params"] == {"before_end": "2026-10-31", "after_start": "2026-11-01"}
    assert parsed["windows"]["before"]["builder"]["n"] == 1
    assert parsed["windows"]["after"]["builder"]["n"] == 1


def test_table_has_confounder_block_after_both_windows(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    runs = [_run("builder", "2026-10-20", input_tokens=10)]
    assert ltt.main([str(_write(tmp_path, runs))]) == 0
    out = capsys.readouterr().out
    assert out.index("window before") < out.index("window after") < out.index("PR size")
    for needle in ("review rounds", "#835", "2026-10-27", "2026-11-10", "assumption"):
        assert needle in out, needle


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        '{"agent_type": "builder"}',
        "[1, 2]",
        '[{"agent_type": "builder", "date": "2026-10-20"}]',
        '[{"agent_type": 3, "date": "2026-10-20", "input_tokens": 1, "output_tokens": 1, '
        '"cache_read_tokens": 1, "cache_write_tokens": 1}]',
        '[{"agent_type": "builder", "date": "2026/10/20", "input_tokens": 1, "output_tokens": 1, '
        '"cache_read_tokens": 1, "cache_write_tokens": 1}]',
        '[{"agent_type": "builder", "date": "2026-10-20", "input_tokens": true, "output_tokens": 1, '
        '"cache_read_tokens": 1, "cache_write_tokens": 1}]',
        "[" * 100000,
    ],
)
def test_malformed_summary_exits_2(tmp_path: Path, content: str, capsys: pytest.CaptureFixture[str]):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    assert ltt.main([str(path)]) == 2
    assert "loop_token_trend" in capsys.readouterr().err


def test_missing_summary_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert ltt.main([str(tmp_path / "absent.json")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_non_utf8_summary_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe\x80 not utf-8")
    assert ltt.main([str(path)]) == 2
    assert "cannot read" in capsys.readouterr().err


@pytest.mark.parametrize(("before", "after"), [("2026-11-21", "2026-10-26"), ("2026-10-26", "2026-10-26")])
def test_after_start_not_later_than_before_end_exits_2(
    tmp_path: Path, before: str, after: str, capsys: pytest.CaptureFixture[str]
):
    args = [str(_write(tmp_path, [])), "--before-end", before, "--after-start", after]
    assert ltt.main(args) == 2
    assert "--after-start" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--before-end", "--after-start"])
def test_invalid_day_flag_exits_2(tmp_path: Path, flag: str, capsys: pytest.CaptureFixture[str]):
    assert ltt.main([str(_write(tmp_path, [])), flag, "2026-1-5"]) == 2
    assert flag in capsys.readouterr().err
