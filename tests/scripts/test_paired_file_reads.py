import importlib.util
import json
import random
import sys
from pathlib import Path
from typing import Any

import pytest

_NAME = "paired_file_reads"
_SPEC = importlib.util.spec_from_file_location(_NAME, Path(__file__).parents[2] / "scripts" / "paired_file_reads.py")
assert _SPEC and _SPEC.loader
pfr = importlib.util.module_from_spec(_SPEC)
sys.modules[_NAME] = pfr
_SPEC.loader.exec_module(pfr)

BEFORE_END = "2026-10-26"
AFTER_START = "2026-11-21"
JSON_KEYS = {
    "n_files",
    "median_reduction_pct",
    "ci_low",
    "ci_high",
    "total_reduction_pct",
    "before_end",
    "after_start",
    "seed",
    "resampling_unit",
}


def _run(agent_type: str, date: str | None, reads: list[tuple[str, int]]) -> dict[str, Any]:
    return {
        "agent_type": agent_type,
        "date": date,
        "full_reads": [{"path": path, "size": size} for path, size in reads],
    }


def _before(reads: list[tuple[str, int]]) -> dict[str, Any]:
    return _run("builder", "2026-10-20", reads)


def _after(reads: list[tuple[str, int]]) -> dict[str, Any]:
    return _run("reviewer", "2026-11-22", reads)


def _write(tmp_path: Path, payload: Any) -> Path:
    path = tmp_path / "token_stats_summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = pfr.build_report(runs, BEFORE_END, AFTER_START)[1]
    return summary


def _paths(runs: list[dict[str, Any]]) -> list[str]:
    return [row["path"] for row in pfr.build_report(runs, BEFORE_END, AFTER_START)[0]]


def _three_file_runs() -> list[dict[str, Any]]:
    return [
        _before([("src/a.py", 100), ("src/b.py", 100), ("tests/c.py", 300)]),
        _after([("src/a.py", 50), ("src/b.py", 90), ("tests/c.py", 0)]),
    ]


def test_median_and_total_match_hand_computation():
    summary = _summary(_three_file_runs())
    assert summary["n_files"] == 3
    assert summary["median_reduction_pct"] == pytest.approx(50.0)
    assert summary["total_reduction_pct"] == pytest.approx(72.0)


def test_file_read_only_before_is_excluded():
    runs = [_before([("src/a.py", 100), ("src/only_before.py", 100)]), _after([("src/a.py", 50)])]
    assert _paths(runs) == ["src/a.py"]


def test_file_read_only_after_is_excluded():
    runs = [_before([("src/a.py", 100)]), _after([("src/a.py", 50), ("src/only_after.py", 10)])]
    assert _paths(runs) == ["src/a.py"]


def test_same_input_gives_identical_range():
    runs = _three_file_runs()
    first = _summary(runs)
    second = _summary(runs)
    assert (first["ci_low"], first["ci_high"]) == (second["ci_low"], second["ci_high"])
    assert first["ci_low"] <= first["median_reduction_pct"] <= first["ci_high"]


def test_bootstrap_range_is_seeded_not_dependent_on_global_random():
    reductions = [10.0, 20.0, 30.0, 40.0]
    first = pfr.bootstrap_median_range(reductions)
    random.seed(12345)
    assert pfr.bootstrap_median_range(reductions) == first


def test_single_file_range_collapses_to_its_reduction():
    summary = _summary([_before([("src/a.py", 200)]), _after([("src/a.py", 150)])])
    assert summary["n_files"] == 1
    assert summary["median_reduction_pct"] == pytest.approx(25.0)
    assert summary["ci_low"] == pytest.approx(25.0)
    assert summary["ci_high"] == pytest.approx(25.0)


def test_runs_outside_windows_and_undated_ignored():
    baseline = _summary(_three_file_runs())
    runs = _three_file_runs() + [
        _run("builder", "2026-11-10", [("src/a.py", 999), ("src/b.py", 999)]),
        _run("reviewer", "2026-10-27", [("src/c.py", 999)]),
        _run("builder", None, [("src/a.py", 1)]),
        _run("reviewer", None, [("src/a.py", 1)]),
        _run("general-purpose", "2026-10-20", [("src/a.py", 1)]),
        _run("main", "2026-11-22", [("src/a.py", 1)]),
    ]
    assert _summary(runs) == baseline


def test_record_without_date_key_is_ignored():
    runs = [
        {"agent_type": "builder", "full_reads": [{"path": "src/a.py", "size": 999}]},
        _before([("src/a.py", 100)]),
        _after([("src/a.py", 50)]),
    ]
    summary = _summary(runs)
    assert summary["n_files"] == 1
    assert summary["median_reduction_pct"] == pytest.approx(50.0)


def test_caveman_prefix_folds_and_pairs():
    runs = [
        _run("caveman:builder", "2026-10-20", [("src/a.py", 100)]),
        _run("reviewer", "2026-11-22", [("src/a.py", 25)]),
    ]
    assert _paths(runs) == ["src/a.py"]
    assert _summary(runs)["median_reduction_pct"] == pytest.approx(75.0)


def test_non_src_tests_non_py_and_empty_paths_excluded():
    paths = ["docs/x.py", "scripts/y.py", "src/z.md", "src/", "", "srcx/w.py", "tests/ok.py"]
    runs = [_before([(p, 100) for p in paths]), _after([(p, 50) for p in paths])]
    assert _paths(runs) == ["tests/ok.py"]


def test_zero_mean_before_is_excluded_without_crash():
    runs = [
        _before([("src/zero.py", 0), ("src/ok.py", 100)]),
        _after([("src/zero.py", 10), ("src/ok.py", 50)]),
    ]
    summary = _summary(runs)
    assert summary["n_files"] == 1
    assert summary["median_reduction_pct"] == pytest.approx(50.0)
    assert summary["total_reduction_pct"] == pytest.approx(50.0)


def test_all_zero_mean_before_gives_null_summary():
    runs = [_before([("src/zero.py", 0)]), _after([("src/zero.py", 10)])]
    summary = _summary(runs)
    assert summary["n_files"] == 0
    assert summary["median_reduction_pct"] is None
    assert summary["total_reduction_pct"] is None


def test_empty_pairing_reports_null_without_crash(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert pfr.main([str(_write(tmp_path, []))]) == 0
    assert "N files" in capsys.readouterr().out
    assert pfr.main([str(_write(tmp_path, [])), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["n_files"] == 0
    assert parsed["median_reduction_pct"] is None
    assert parsed["ci_low"] is None
    assert parsed["ci_high"] is None


def test_json_has_exact_keys_and_defaults(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert pfr.main([str(_write(tmp_path, _three_file_runs())), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert set(parsed) == JSON_KEYS
    assert parsed["before_end"] == BEFORE_END
    assert parsed["after_start"] == AFTER_START
    assert parsed["seed"] == 0
    assert parsed["resampling_unit"] == "file"


def test_json_numbers_match_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    path = _write(tmp_path, _three_file_runs())
    assert pfr.main([str(path)]) == 0
    table = capsys.readouterr().out
    assert pfr.main([str(path), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert f"{parsed['median_reduction_pct']:.1f}%" in table
    assert f"{parsed['total_reduction_pct']:.1f}%" in table
    assert f"{parsed['ci_low']:.1f}% to {parsed['ci_high']:.1f}%" in table
    assert f"{'N files':<24}{parsed['n_files']}" in table


def test_flags_change_windows(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    runs = [_run("builder", "2026-10-31", [("src/a.py", 100)]), _run("reviewer", "2026-11-01", [("src/a.py", 50)])]
    args = [str(_write(tmp_path, runs)), "--json", "--before-end", "2026-10-31", "--after-start", "2026-11-01"]
    assert pfr.main(args) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["n_files"] == 1
    assert parsed["median_reduction_pct"] == pytest.approx(50.0)
    assert parsed["before_end"] == "2026-10-31"


def test_gap_note_given_is_printed_in_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    gap = tmp_path / "gap.md"
    assert pfr.main([str(_write(tmp_path, _three_file_runs())), "--gap-note", str(gap)]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"gap note: {gap}\n")
    assert not gap.exists()


def test_gap_note_omitted_is_not_printed(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert pfr.main([str(_write(tmp_path, _three_file_runs()))]) == 0
    assert "gap note" not in capsys.readouterr().out


def test_gap_note_with_json_keeps_stdout_valid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    gap = tmp_path / "gap.md"
    assert pfr.main([str(_write(tmp_path, _three_file_runs())), "--json", "--gap-note", str(gap)]) == 0
    captured = capsys.readouterr()
    assert set(json.loads(captured.out)) == JSON_KEYS
    assert str(gap) in captured.err


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        '{"agent_type": "builder"}',
        "[1, 2]",
        '[{"date": "2026-10-20", "full_reads": []}]',
        '[{"agent_type": "builder", "date": "2026/10/20", "full_reads": []}]',
        '[{"agent_type": "builder", "date": "2026-10-20", "full_reads": {}}]',
        '[{"agent_type": "builder", "date": "2026-10-20", "full_reads": [1]}]',
        '[{"agent_type": "builder", "date": "2026-10-20", "full_reads": [{"path": 3, "size": 1}]}]',
        '[{"agent_type": "builder", "date": "2026-10-20", "full_reads": [{"path": "src/a.py"}]}]',
        '[{"agent_type": "builder", "date": "2026-10-20", "full_reads": [{"path": "src/a.py", "size": true}]}]',
        '[{"agent_type": "builder", "date": "2026-10-20", "full_reads": [{"path": "src/a.py", "size": "5"}]}]',
        "[" * 100000,
    ],
)
def test_malformed_summary_exits_2(tmp_path: Path, content: str, capsys: pytest.CaptureFixture[str]):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    assert pfr.main([str(path)]) == 2
    assert "paired_file_reads" in capsys.readouterr().err


def test_missing_summary_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert pfr.main([str(tmp_path / "absent.json")]) == 2
    assert "cannot read" in capsys.readouterr().err


@pytest.mark.parametrize(("before", "after"), [("2026-11-21", "2026-10-26"), ("2026-10-26", "2026-10-26")])
def test_after_start_not_later_than_before_end_exits_2(
    tmp_path: Path, before: str, after: str, capsys: pytest.CaptureFixture[str]
):
    args = [str(_write(tmp_path, [])), "--before-end", before, "--after-start", after]
    assert pfr.main(args) == 2
    assert "--after-start" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--before-end", "--after-start"])
def test_invalid_day_flag_exits_2(tmp_path: Path, flag: str, capsys: pytest.CaptureFixture[str]):
    assert pfr.main([str(_write(tmp_path, [])), flag, "2026-1-5"]) == 2
    assert flag in capsys.readouterr().err
