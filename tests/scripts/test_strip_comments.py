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


def test_ast_equal_ignores_docstrings():
    a = 'def f():\n    """doc one"""\n    return 1\n'
    b = 'def f():\n    """doc one"""\n    return 1\n'
    assert sc.ast_equal(a, b)
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
    assert report["files"][0]["ast_ok"] is False
    assert f.read_text() == "# note\nx = 1\n"
    assert not list(tmp_path.glob(".*strip-tmp"))
