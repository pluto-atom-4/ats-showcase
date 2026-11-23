import importlib.util
import json
import subprocess
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_SPEC = importlib.util.spec_from_file_location("check_added_comments", _ROOT / "scripts" / "check_added_comments.py")
assert _SPEC and _SPEC.loader
cac = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cac)

_SRC = _ROOT / "src" / "x.py"
_DIFF = """\
diff --git a/src/a.py b/src/a.py
index 1111111..2222222 100644
--- a/src/a.py
+++ b/src/a.py
@@ -3 +3,2 @@
-# old note
+# sets x to 5
+y = 2
@@ -10,0 +12 @@
+# added later
@@ -20,2 +22,0 @@
-# gone one
-# gone two
diff --git a/src/b.py b/src/b.py
new file mode 100644
--- /dev/null
+++ b/src/b.py
@@ -0,0 +1,2 @@
+x = 1
+# hi
"""


def _check(source: str, added: set[int], removed: set[str] | None = None) -> list:
    return list(cac.find_violations(_SRC, source, added, removed or set()))


def _git(repo: Path, *args: str) -> None:
    identity = [
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.autocrlf=false",
    ]
    subprocess.run(["git", "-C", str(repo), *identity, *args], check=True, capture_output=True)


def _commit_file(repo: Path, name: str, content: str, msg: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", msg)


def test_restating_comment_added_fails():
    violations = _check("x = 5\n# sets x to 5\n", {2})
    assert len(violations) == 1
    assert violations[0].line == 2
    assert violations[0].text == "# sets x to 5"


def test_why_comment_added_passes():
    assert _check("x = 5\n# workaround for #881, see link\n", {2}) == []


def test_bare_directive_added_passes():
    assert _check("x = f()  # noqa: E501\n", {1}) == []


def test_embedded_noqa_does_not_bypass():
    assert len(_check("x = 5\n# obviously sets x to 5  # noqa\n", {2})) == 1


def test_reflow_exemption():
    src = "x = 5\n# sets x to 5\n"
    assert _check(src, {2}, {"# sets x to 5"}) == []
    assert len(_check(src, {2}, {"# something else"})) == 1


def test_why_keep_list_override(tmp_path, monkeypatch):
    keep = json.loads((_ROOT / "scripts" / "why_keep_list.json").read_text(encoding="utf-8"))
    keep.append(["src/x.py", "sets x to 5"])
    temp = tmp_path / "why_keep_list.json"
    temp.write_text(json.dumps(keep), encoding="utf-8")
    overrides = json.loads(temp.read_text(encoding="utf-8"))
    monkeypatch.setattr(cac.sc, "KEPT_OVERRIDES", frozenset((k, t) for k, t in overrides))
    assert _check("x = 5\n# sets x to 5\n", {2}) == []


def test_synthetic_marker_kept():
    assert _check("x = 5\n# SYNTHETIC: placeholder value\n", {2}) == []


def test_parse_added_and_removed_hunk_header():
    assert cac.parse_added_lines(_DIFF) == {"src/a.py": {3, 4, 12}, "src/b.py": {1, 2}}
    assert cac.parse_removed_texts(_DIFF) == {"src/a.py": {"# old note", "# gone one", "# gone two"}}


def test_base_ref_integration_fails_on_restating(tmp_path, monkeypatch, capsys):
    _git(tmp_path, "init", "-q")
    _commit_file(tmp_path, "m.py", "x = 5\n", "base")
    _commit_file(tmp_path, "m.py", "x = 5\n# sets x to 5\n", "head")
    monkeypatch.chdir(tmp_path)
    assert cac.main(["--base-ref", "HEAD~1", "m.py"]) == 1
    err = capsys.readouterr().err
    assert "m.py:2:" in err
    assert "added comment reads as a restated" in err


def test_base_ref_integration_passes_on_why(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    _commit_file(tmp_path, "m.py", "x = 5\n", "base")
    _commit_file(tmp_path, "m.py", "x = 5\n# workaround for #881, see link\n", "head")
    monkeypatch.chdir(tmp_path)
    assert cac.main(["--base-ref", "HEAD~1", "m.py"]) == 0


def test_staged_integration_fails_on_restating(tmp_path, monkeypatch, capsys):
    _git(tmp_path, "init", "-q")
    _commit_file(tmp_path, "m.py", "x = 5\n", "base")
    (tmp_path / "m.py").write_text("x = 5\n# sets x to 5\n", encoding="utf-8")
    _git(tmp_path, "add", "m.py")
    monkeypatch.chdir(tmp_path)
    assert cac.main(["--staged", "m.py"]) == 1
    assert "m.py:2:" in capsys.readouterr().err
