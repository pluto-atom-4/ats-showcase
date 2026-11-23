import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "strip_comments", Path(__file__).parents[2] / "scripts" / "strip_comments.py"
)
assert _SPEC and _SPEC.loader
sc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sc)


def strip(src: str) -> str:
    return str(sc.process_source(src).new_source)


def test_hash_inside_strings_untouched():
    src = 'x = "# not a comment"\ny = f"{1}# nope"\nz = """\n# inside\n"""\n'
    assert strip(src) == src


def test_directives_kept():
    src = (
        "import os  # noqa: F401\n"
        "x: int = foo()  # type: ignore[attr-defined]\n"
        "# pragma: no cover\n"
        "# fmt: off\n"
        "# isort: skip\n"
        "# mypy: ignore-errors\n"
        "# pylint: disable=x\n"
        "y = 1\n"
    )
    result = sc.process_source(src)
    assert result.new_source == src
    assert result.directive_count == 7


def test_shebang_and_encoding_kept():
    src = "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nx = 1\n"
    result = sc.process_source(src)
    assert result.new_source == src
    assert result.directive_count == 2


def test_why_comment_kept():
    src = "# keep because ordering matters here\nx = 1\n# set the value\ny = 2\n"
    assert strip(src) == "# keep because ordering matters here\nx = 1\ny = 2\n"


def test_issue_ref_and_synthetic_marker_kept():
    src = "# pinned in #523\na = 1\n# SYNTHETIC: placeholder\nb = 2\n# plain\nc = 3\n"
    assert strip(src) == "# pinned in #523\na = 1\n# SYNTHETIC: placeholder\nb = 2\nc = 3\n"


def test_ref_and_synthetic_matching_is_bounded():
    assert strip("# #1 priority\na = 1\n") == "a = 1\n"
    assert strip("# generate synthetic data\na = 1\n") == "a = 1\n"
    assert strip("# html &#39; entity\na = 1\n") == "a = 1\n"
    assert strip("# see #523\na = 1\n") == "# see #523\na = 1\n"
    assert strip("# SYNTHETIC: x\na = 1\n") == "# SYNTHETIC: x\na = 1\n"


def test_tracked_todo_kept_bare_todo_removed():
    src = "# TODO: fix (#12)\na = 1\n# TODO: fix later\nb = 2\n"
    assert strip(src) == "# TODO: fix (#12)\na = 1\nb = 2\n"


def test_inline_trailing_comment_removed():
    assert strip("x = 1  # set x\ny = 2\n") == "x = 1\ny = 2\n"


def test_inline_trailing_why_kept():
    src = "x = 1  # because units are rad\n"
    assert strip(src) == src


def test_banner_removed():
    assert strip("# -----\n# =====\nx = 1\n") == "x = 1\n"


def test_long_why_block_trimmed_and_flagged():
    src = "# why one\n# why two\n# why three\n# why four\nx = 1\n"
    result = sc.process_source(src)
    assert result.new_source == "# why one\n# why two\n# why three\nx = 1\n"
    assert any(m["tag"] == "trimmed_why" for m in result.manual_review)


def test_commented_code_removed_and_flagged():
    result = sc.process_source("# print(x)\nx = 1\n")
    assert result.new_source == "x = 1\n"
    assert any(m["tag"] == "commented_code" for m in result.manual_review)


def test_plain_word_not_flagged_as_commented_code():
    result = sc.process_source("# Returns\nx = 1\n")
    assert result.manual_review == []


def test_blank_line_cleanup_after_removed_block():
    src = "def f():\n    a = 1\n\n    # step\n\n    b = 2\n"
    assert strip(src) == "def f():\n    a = 1\n\n    b = 2\n"


def test_blank_cleanup_toplevel_keeps_two():
    src = "import os\n\n\n# helpers\n\n\ndef f():\n    pass\n"
    assert strip(src) == "import os\n\n\ndef f():\n    pass\n"


def test_comment_only_untouched_blank_lines_preserved():
    src = "a = 1\n\n\n\nb = 2\n"
    assert strip(src) == src


def test_ast_equal_detects_code_and_docstring_changes():
    doc = 'def f():\n    """doc one"""\n    return 1\n'
    assert sc.ast_equal(doc, doc)
    assert not sc.ast_equal(doc, doc.replace("doc one", "doc two"))
    assert not sc.ast_equal(doc, doc.replace("return 1", "return 2"))
    assert not sc.ast_equal("x = 1\n", "x = 2\n")


def test_ast_guard_aborts_file_on_mismatch(tmp_path, monkeypatch):
    f = tmp_path / "m.py"
    original = "# note\nx = 1\n"
    f.write_text(original)
    monkeypatch.setattr(sc, "ast_equal", lambda a, b: False)
    report = sc.run([f], apply=True)
    assert f.read_text() == original
    assert report["files"][0]["ast_ok"] is False


def test_apply_writes_and_dry_run_does_not(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("# note\nx = 1\n")
    sc.run([f], apply=False)
    assert f.read_text() == "# note\nx = 1\n"
    sc.run([f], apply=True)
    assert f.read_text() == "x = 1\n"


def test_cli_report_and_directive_total(tmp_path, capsys):
    f = tmp_path / "m.py"
    f.write_text("import os  # noqa\n# note\n")
    out = tmp_path / "r.json"
    assert sc.main([str(tmp_path), "--report", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["directive_total"] == 1
    assert "directive" in capsys.readouterr().out.lower()
    assert f.read_text() == "import os  # noqa\n# note\n"


def test_strict_manual_exit_code(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("# print(x)\nx = 1\n")
    assert sc.main([str(f), "--strict-manual"]) == 1


def test_syntax_error_file_reported_not_crashing(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def (:\n")
    report = sc.run([f], apply=True)
    assert report["files"][0]["ast_ok"] is False


@pytest.mark.parametrize("name", ["a.py", "sub/b.py"])
def test_directory_walk(tmp_path, name):
    f = tmp_path / name
    f.parent.mkdir(exist_ok=True)
    f.write_text("x = 1\n")
    assert sc.collect_files([tmp_path]) == [f]


def test_crlf_preserved(tmp_path):
    f = tmp_path / "m.py"
    f.write_bytes(b"# note\r\nx = 1  # set\r\n\r\n\r\ny = 2\r\n")
    sc.run([f], apply=True)
    assert f.read_bytes() == b"x = 1\r\n\r\n\r\ny = 2\r\n"


def test_no_trailing_newline():
    assert strip("# note\nx = 1") == "x = 1"
    assert strip("x = 1  # set") == "x = 1"


def test_comments_inside_brackets():
    src = "x = [\n    1,  # one\n    # between\n    2,\n]\n"
    assert strip(src) == "x = [\n    1,\n    2,\n]\n"


def test_backslash_continuation():
    src = "x = 1 + \\\n    2  # total\n"
    assert strip(src) == "x = 1 + \\\n    2\n"


@pytest.mark.parametrize(
    "line",
    [
        "x = []  # type: list[int]\n",
        "x = f()  # pyright: ignore\n",
        "# fmt: off\n",
        "x = f()  # nosec\n",
        "x = f()  # pyre-ignore\n",
        "# SPDX-License-Identifier: MIT\n",
        "# Copyright 2026\n",
    ],
)
def test_extra_directives_kept(line):
    assert strip(line) == line


def test_copyright_only_protected_in_header():
    src = "x = 1\ny = 2\nz = 3\n# copyright note\nw = 4\n"
    assert strip(src) == "x = 1\ny = 2\nz = 3\nw = 4\n"


def test_docstring_change_detected_by_ast_guard():
    assert not sc.ast_equal('"""a"""\nx = 1\n', '"""b"""\nx = 1\n')


def test_report_written_when_run_raises(tmp_path, monkeypatch):
    f = tmp_path / "m.py"
    f.write_text("x = 1\n")
    out = tmp_path / "r.json"

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(sc, "process_source", boom)
    with pytest.raises(RuntimeError):
        sc.main([str(f), "--report", str(out)])
    assert out.exists()


def test_write_error_recorded(tmp_path, monkeypatch):
    f = tmp_path / "m.py"
    f.write_text("# note\nx = 1\n")

    def fail(*a, **k):
        raise OSError("disk")

    monkeypatch.setattr(sc.os, "replace", fail)
    report = sc.run([f], apply=True)
    assert report["files"][0]["write_failed"] is True
    assert report["files"][0]["ast_ok"] is True
    assert f.read_text() == "# note\nx = 1\n"
    assert not list(tmp_path.glob(".*strip-tmp"))


def test_prose_not_mistaken_for_directive():
    assert strip("# pragmatic approach\nx = 1\n") == "x = 1\n"
    assert strip("# Type: job title\nx = 1\n") == "x = 1\n"
    assert strip("# see noqa docs\nx = 1\n") == "x = 1\n"


def test_header_word_boundary_and_full_line_only():
    assert strip("# licensed stuff\nx = 1\n") == "x = 1\n"
    assert strip("x = 1  # copyright\n") == "x = 1\n"


def test_write_failure_exit_code(tmp_path, monkeypatch, capsys):
    f = tmp_path / "m.py"
    f.write_text("# note\nx = 1\n")
    monkeypatch.setattr(sc.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    assert sc.main([str(f), "--apply"]) == 1
    assert "write_failed" in capsys.readouterr().err


def test_recursion_error_skips_file_and_continues(tmp_path, monkeypatch):
    bad, good = tmp_path / "a.py", tmp_path / "b.py"
    bad.write_text("x = 1\n")
    good.write_text("# note\ny = 1\n")
    real = sc.process_source

    def maybe(src):
        if src == "x = 1\n":
            raise RecursionError
        return real(src)

    monkeypatch.setattr(sc, "process_source", maybe)
    report = sc.run([bad, good], apply=True)
    assert good.read_text() == "y = 1\n"
    assert report["files"][0]["ast_ok"] is False


@pytest.mark.parametrize(
    "line",
    ["# ruff: noqa\n", "# ruff: noqa: E501\n", "# flake8: noqa\n", "x = 1  # NOQA\n"],
)
def test_file_level_linter_directives_kept(line):
    assert strip(line) == line


@pytest.mark.parametrize(
    "comment",
    [
        "# Pragma is used here",
        "# Mypy: is slow",
        "# nosecurity note",
        "# type: the job title",
        "# type: str of the value",
    ],
)
def test_prose_lookalikes_removed(comment):
    assert strip(f"{comment}\nx = 1\n") == "x = 1\n"


def test_trailing_type_annotation_kept_full_line_prose_removed():
    assert strip("x = []  # type: list[int]\n") == "x = []  # type: list[int]\n"
    assert strip("def f(a):\n    # type: (int) -> str\n    return a\n").count("type:") == 1


KEPT_TEXT = "Assumed ~30% token reduction from boilerplate removal, not measured."
KEPT_FILE = "src/cli.py"


def strip_for(src: str, file_key: str | None) -> str:
    with sc._file_scope(file_key):
        return str(sc.process_source(src).new_source)


def test_kept_override_hit_keeps_comment():
    src = f"# {KEPT_TEXT}\nx = 1\n"
    assert strip(src) == "x = 1\n"
    assert strip_for(src, KEPT_FILE) == src


@pytest.mark.parametrize("file_key", ["src/other.py", "tests/test_cli.py", None])
def test_kept_override_miss_removes_comment(file_key):
    src = f"# {KEPT_TEXT}\nx = 1\n"
    assert strip_for(src, file_key) == "x = 1\n"


def test_kept_override_miss_on_text_removes_comment():
    assert strip_for("# Assumed ~30% token reduction\nx = 1\n", KEPT_FILE) == "x = 1\n"


def test_kept_override_entries_are_unique_pairs():
    pairs = json.loads((Path(__file__).parents[2] / "scripts" / "why_keep_list.json").read_text(encoding="utf-8"))
    assert all(isinstance(p, list) and len(p) == 2 for p in pairs)
    assert len({tuple(p) for p in pairs}) == len(pairs)


MISLABELS = [
    ("src/integrity/models.py", "# One of 'error', 'warning', 'info'."),
    ("src/nlp/confidence.py", "# 0.0 to 1.0"),
    ("src/poc/extract_requirements_c.py", "# Start AFTER the section header"),
    ("src/poc/extract_requirements_d.py", "# Start AFTER the section header"),
    ("src/poc/tweak/markdown_section_classifier.py", "# Use first ~50 words as pseudo-title for matching"),
    ("src/tokenization/technical_compounds.py", "# Medium-confidence keyword patterns for detection"),
    ("tests/test_technical_compounds_phase1.py", "# Expected in Phase 3 output"),
]


@pytest.mark.parametrize(("file_key", "comment"), MISLABELS)
def test_mislabel_stays_removed(file_key, comment):
    assert strip_for(f"{comment}\nx = 1\n", file_key) == "x = 1\n"


def test_label_comment_stays_removed():
    src = "DATA = [\n    # Operations\n    1,\n]\n"
    assert strip_for(src, "src/example.py") == "DATA = [\n    1,\n]\n"


@pytest.mark.parametrize(
    "comment",
    [
        "# Importing registers the component via its decorator.",
        "# Registers the handler through the factory at import time.",
        "# Must run after requirement_filter, which populates doc._.requirements.",
        "# Runs before the tokenizer is loaded.",
        "# Deliberately broad: user-supplied config JSON can have any shape.",
        "# Intentional: the cache is never evicted.",
        '# Known limitation (accepted): generic triggers such as "is an equal opportunity"',
        "# The check compares after.lower_, so an uppercase entry would silently never match.",
        "# Re-export for backward compatibility",
        "# Kept for backward-compat with old configs.",
    ],
)
def test_structural_idiom_kept(comment):
    assert sc._classify(comment, 1, True) == "why"


@pytest.mark.parametrize(
    "comment",
    [
        "# Registers the handler for events.",
        "# The loop runs once per frame.",
        "# Runs the parser after cleanup finishes.",
        "# Delete the file.",
        "# Intent is unclear here.",
        "# known issues list",
        "# silence warnings from the logger",
        "# backward pass of the network",
        "# avoid this pattern",
        "# must be called once",
    ],
)
def test_structural_idiom_near_miss_removed(comment):
    assert sc._classify(comment, 1, True) == "remove"


def test_prose_before_noqa_is_not_directive():
    assert sc._classify("# obviously sets x to 5  # noqa", 5, True) == "remove"


@pytest.mark.parametrize(
    "comment",
    ["# noqa: E501", "# type: ignore[arg-type]"],
)
def test_bare_leading_directive_classified_directive(comment):
    assert sc._classify(comment, 5, True) == "directive"
