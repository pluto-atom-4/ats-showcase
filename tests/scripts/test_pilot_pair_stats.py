import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).parents[2] / "scripts"


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The pilot script imports its siblings by bare name, so they must be registered first.
_load("loop_token_stats")
trend = _load("loop_token_trend")
pps = _load("pilot_pair_stats")

COMPONENTS = pps.COMPONENTS
PRE_USAGE = {
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_read_input_tokens": 1000,
    "cache_creation_input_tokens": 200,
}
POST_USAGE = {
    "input_tokens": 50,
    "output_tokens": 20,
    "cache_read_input_tokens": 800,
    "cache_creation_input_tokens": 100,
}
ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
PRE_COST = trend.cost({"input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 1000, "cache_write_tokens": 200})
POST_COST = trend.cost({"input_tokens": 50, "output_tokens": 20, "cache_read_tokens": 800, "cache_write_tokens": 100})
PRE_POST_REDUCTION = (PRE_COST - POST_COST) / PRE_COST * 100
FIVE_REDUCTIONS = [10.0, 20.0, 30.0, 40.0, 50.0]
TIGHT_REDUCTIONS = [30.0, 30.5, 29.5, 30.2, 29.8]


def _pair(pr: int, reduction: float) -> dict[str, Any]:
    return {
        "pr": pr,
        "cost_pre": 100.0,
        "cost_post": 100.0 - reduction,
        "reduction_pct": reduction,
        "components_pre": dict.fromkeys(COMPONENTS, 10),
        "components_post": dict.fromkeys(COMPONENTS, 4),
    }


def _entry(pr: int, variant: str, transcript: object) -> dict[str, Any]:
    return {"pr": pr, "variant": variant, "transcript": transcript}


def _line(msg_id: str, usage: dict[str, int]) -> str:
    message = {"id": msg_id, "role": "assistant", "content": [], "usage": usage}
    return json.dumps({"type": "assistant", "timestamp": "2026-11-10T10:00:00Z", "message": message})


def _transcript(path: Path, usage: dict[str, int]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_line("msg-1", usage) + "\n", encoding="utf-8")
    return str(path)


def _write_manifest(path: Path, entries: Any) -> Path:
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


@pytest.fixture
def pair_manifest(tmp_path: Path) -> Path:
    pre = _transcript(tmp_path / "t" / "pre-940.jsonl", PRE_USAGE)
    post = _transcript(tmp_path / "t" / "post-940.jsonl", POST_USAGE)
    return _write_manifest(tmp_path / "manifest.json", [_entry(940, "pre", pre), _entry(940, "post", post)])


def test_t_quantile_known_values() -> None:
    assert pps.t_quantile(4, 0.975) == 2.776
    assert pps.t_quantile(9, 0.975) == 2.262
    assert pps.t_quantile(19, 0.80) == 0.861


def test_t_quantile_missing_df_raises() -> None:
    with pytest.raises(KeyError):
        pps.t_quantile(3, 0.975)


def test_load_manifest_happy_path(tmp_path: Path) -> None:
    entries = [_entry(940, "pre", "/abs/pre.jsonl"), _entry(940, "post", "/abs/post.jsonl")]
    assert pps.load_manifest(_write_manifest(tmp_path / "m.json", entries)) == entries


def test_load_manifest_rejects_non_list(tmp_path: Path) -> None:
    with pytest.raises(pps.PilotError, match="JSON list"):
        pps.load_manifest(_write_manifest(tmp_path / "m.json", {"pr": 940}))


def test_load_manifest_rejects_bad_variant(tmp_path: Path) -> None:
    with pytest.raises(pps.PilotError, match="variant"):
        pps.load_manifest(_write_manifest(tmp_path / "m.json", [_entry(940, "mid", "/abs/x.jsonl")]))


@pytest.mark.parametrize("bad_pr", ["940", True, None])
def test_load_manifest_rejects_non_int_pr(tmp_path: Path, bad_pr: object) -> None:
    with pytest.raises(pps.PilotError, match="integer pr"):
        pps.load_manifest(_write_manifest(tmp_path / "m.json", [_entry(bad_pr, "pre", "/abs/x.jsonl")]))  # type: ignore[arg-type]


def test_load_manifest_rejects_empty_transcript(tmp_path: Path) -> None:
    with pytest.raises(pps.PilotError, match="transcript"):
        pps.load_manifest(_write_manifest(tmp_path / "m.json", [_entry(940, "pre", "")]))


def test_pair_entries_groups_by_pr() -> None:
    entries = [
        _entry(941, "post", "/p/post-941"),
        _entry(940, "pre", "/p/pre-940"),
        _entry(940, "post", "/p/post-940"),
        _entry(941, "pre", "/p/pre-941"),
    ]
    pairs, skipped = pps.pair_entries(entries)
    assert pairs == {
        940: {"pre": "/p/pre-940", "post": "/p/post-940"},
        941: {"pre": "/p/pre-941", "post": "/p/post-941"},
    }
    assert skipped == []


def test_pair_entries_skips_missing_variant() -> None:
    entries = [_entry(940, "pre", "/p/pre"), _entry(940, "post", "/p/post"), _entry(951, "pre", "/p/pre-951")]
    pairs, skipped = pps.pair_entries(entries)
    assert list(pairs) == [940]
    assert skipped == [{"pr": 951, "reason": "missing post variant"}]


def test_pair_entries_raises_on_duplicate() -> None:
    with pytest.raises(pps.PilotError, match="duplicate pre"):
        pps.pair_entries([_entry(940, "pre", "/p/a"), _entry(940, "pre", "/p/b")])


def test_pair_cost_computes_reduction(tmp_path: Path) -> None:
    pre = _transcript(tmp_path / "pre.jsonl", PRE_USAGE)
    post = _transcript(tmp_path / "post.jsonl", POST_USAGE)
    result = pps.pair_cost(940, Path(pre), Path(post))
    assert result is not None
    assert result["pr"] == 940
    assert result["cost_pre"] == PRE_COST
    assert result["cost_post"] == POST_COST
    assert result["reduction_pct"] == pytest.approx(PRE_POST_REDUCTION)
    assert result["components_pre"]["input_tokens"] == 100
    assert result["components_post"]["cache_read_tokens"] == 800


def test_pair_cost_returns_none_when_pre_cost_zero(tmp_path: Path) -> None:
    pre = _transcript(tmp_path / "pre.jsonl", ZERO_USAGE)
    post = _transcript(tmp_path / "post.jsonl", POST_USAGE)
    assert pps.pair_cost(940, Path(pre), Path(post)) is None


def test_bootstrap_mean_range_is_seeded_and_reproducible() -> None:
    first = pps.bootstrap_mean_range(FIVE_REDUCTIONS)
    assert first == pps.bootstrap_mean_range(FIVE_REDUCTIONS)
    assert min(FIVE_REDUCTIONS) <= first[0] <= first[1] <= max(FIVE_REDUCTIONS)


def test_mde_decreases_with_larger_n() -> None:
    values = [pps.mde(10.0, n) for n in pps.MDE_SAMPLE_SIZES]
    assert values == sorted(values, reverse=True)
    assert len(set(values)) == len(values)


def test_build_report_fewer_than_two_pairs_is_all_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_bootstrap(_: list[float]) -> tuple[float, float]:
        raise AssertionError("bootstrap must not run below two pairs")

    monkeypatch.setattr(pps, "bootstrap_mean_range", _no_bootstrap)
    for pairs in ([], [_pair(940, 30.0)]):
        report = pps.build_report(pairs, [{"pr": 951, "reason": "pre cost is 0"}])
        assert report["n_pairs"] == len(pairs)
        for key in ("mean_reduction_pct", "median_reduction_pct", "sd_reduction_pct", "ci_low", "ci_high"):
            assert report[key] is None
        assert report["mde"] == {"5": None, "10": None, "15": None, "20": None}
        assert report["stop_rule"] is None
        assert report["components"] == {"pre": dict.fromkeys(COMPONENTS), "post": dict.fromkeys(COMPONENTS)}


def test_build_report_five_pairs_happy_path() -> None:
    report = pps.build_report([_pair(pr, r) for pr, r in enumerate(FIVE_REDUCTIONS, start=940)], [])
    assert report["n_pairs"] == 5
    assert report["mean_reduction_pct"] == pytest.approx(30.0)
    assert report["median_reduction_pct"] == pytest.approx(30.0)
    assert report["sd_reduction_pct"] == pytest.approx(15.811388300841896)
    assert (report["ci_low"], report["ci_high"]) == pytest.approx((18.0, 42.0))
    assert set(report["mde"]) == {"5", "10", "15", "20"}
    assert report["mde"]["5"] == pytest.approx(26.28315905670397)
    assert report["mde"]["20"] == pytest.approx(10.443967158125306)
    assert report["components"]["pre"]["input_tokens"] == pytest.approx(10.0)
    assert report["components"]["post"]["cache_write_tokens"] == pytest.approx(4.0)
    assert [row["pr"] for row in report["pairs"]] == [940, 941, 942, 943, 944]


def test_build_report_sets_stop_rule_when_mde20_over_threshold() -> None:
    report = pps.build_report([_pair(pr, r) for pr, r in enumerate(FIVE_REDUCTIONS, start=940)], [])
    assert report["mde"]["20"] > pps.STOP_RULE_PCT
    assert report["stop_rule"] == pps.STOP_RULE_MESSAGE


def test_build_report_stop_rule_none_when_mde20_under_threshold() -> None:
    report = pps.build_report([_pair(pr, r) for pr, r in enumerate(TIGHT_REDUCTIONS, start=940)], [])
    assert report["mde"]["20"] == pytest.approx(0.25152403662473277)
    assert report["stop_rule"] is None
    assert pps.STOP_RULE_MESSAGE not in pps.render_table(report)


def test_render_table_prints_stop_rule() -> None:
    report = pps.build_report([_pair(pr, r) for pr, r in enumerate(FIVE_REDUCTIONS, start=940)], [])
    assert pps.render_table(report).splitlines()[-1] == pps.STOP_RULE_MESSAGE


def test_main_bad_manifest_path_exit_2_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert pps.main([str(tmp_path / "missing.json")]) == 2
    assert capsys.readouterr().err.startswith("pilot_pair_stats: ")


def test_main_duplicate_entry_exit_2_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = _write_manifest(tmp_path / "m.json", [_entry(940, "pre", "/a"), _entry(940, "pre", "/b")])
    assert pps.main([str(manifest)]) == 2
    assert "duplicate pre entry for pr 940" in capsys.readouterr().err


@pytest.mark.parametrize("kind", ["undecodable", "missing"])
def test_main_unreadable_transcript_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str) -> None:
    pre = tmp_path / "pre.jsonl"
    if kind == "undecodable":
        pre.write_bytes(b"\xff\xfe\xfa")
    post = _transcript(tmp_path / "post.jsonl", POST_USAGE)
    manifest = _write_manifest(
        tmp_path / "m.json",
        [_entry(940, "pre", str(pre)), _entry(940, "post", post)],
    )
    assert pps.main([str(manifest)]) == 2
    assert capsys.readouterr().err.startswith("pilot_pair_stats: cannot read transcript")


def test_main_end_to_end_with_real_transcript_fixtures(pair_manifest: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert pps.main([str(pair_manifest), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["n_pairs"] == 1
    assert report["pairs"][0]["pr"] == 940
    assert report["pairs"][0]["reduction_pct"] == pytest.approx(PRE_POST_REDUCTION)
    assert report["mean_reduction_pct"] is None
    assert report["stop_rule"] is None


def test_main_json_flag_prints_valid_json(pair_manifest: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert pps.main([str(pair_manifest), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report) == set(pps.build_report([], []))
    assert report["resampling_unit"] == "pair"


def test_main_table_mode_prints_table(pair_manifest: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert pps.main([str(pair_manifest)]) == 0
    out = capsys.readouterr().out
    assert "940" in out
    assert "N pairs" in out
    assert "{" not in out
