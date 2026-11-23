import importlib.util
import json
from dataclasses import asdict
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "comment_stats", Path(__file__).parents[2] / "scripts" / "comment_stats.py"
)
assert _SPEC and _SPEC.loader
cs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cs)

SRC_A = "# plain note about setup\nimport os  # noqa: F401\n# WHY: ordering matters here\nx = 1  # units are meters\n"
TESTS_B = "# set up the fixture\ny = 2  # noqa: E501\n# pragma: no cover\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "a.py").write_text(SRC_A, encoding="utf-8")
    (tmp_path / "tests" / "b.py").write_text(TESTS_B, encoding="utf-8")
    return tmp_path


def test_compute_stats_hand_counted(repo: Path) -> None:
    stats = cs.compute_stats([repo / "src", repo / "tests"])
    assert stats.full_line_comments == 4  # a: 2 full, b: 2 full
    assert stats.inline_comments == 3  # a: 2 inline, b: 1 inline
    assert stats.full_plus_inline_by_base == {"src": 4, "tests": 3}
    assert stats.files_with_comment == 2
    assert stats.files_total == 2
    assert stats.comment_text_bytes == 132  # 24+12+28+18 + 20+12+18
    assert stats.comment_tokens_proxy == 33
    assert stats.total_bytes == len(SRC_A.encode()) + len(TESTS_B.encode()) == 164
    assert stats.comment_share_pct == pytest.approx(132 / 164 * 100)
    assert stats.directive_comments == 3  # a: noqa, b: noqa + pragma


def test_directive_only_counts_directives(repo: Path) -> None:
    stats = cs.compute_stats([repo / "src"])
    assert stats.directive_comments == 1
    assert stats.full_plus_inline_by_base == {"src": 4}
    assert stats.files_total == 1


def test_empty_root_guards_division(tmp_path: Path) -> None:
    stats = cs.compute_stats([tmp_path])
    assert stats.files_total == 0
    assert stats.total_bytes == 0
    assert stats.comment_share_pct == 0.0


def test_format_table_mentions_counts(repo: Path) -> None:
    table = cs.format_table(cs.compute_stats([repo / "src", repo / "tests"]))
    assert "132" in table
    assert "164" in table


def test_json_round_trip_and_exit_zero(repo: Path, tmp_path: Path) -> None:
    out = tmp_path / "stats.json"
    rc = cs.main([str(repo / "src"), str(repo / "tests"), "--json", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == asdict(cs.compute_stats([repo / "src", repo / "tests"]))


def test_default_paths_and_exit_zero(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    assert cs.main([]) == 0
    assert "132" in capsys.readouterr().out


PROBE_VALUE = 1  # sets PROBE_VALUE to 1
