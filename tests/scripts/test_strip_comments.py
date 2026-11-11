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
    b = 'def f():\n    """doc two"""\n    return 1\n'
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
    assert sc.collect_files([tmp_path]) != []
