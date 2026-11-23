#!/usr/bin/env python3
"""Fail when a diff adds a comment that reads as restated or removed-class prose."""

import argparse
import importlib.util
import io
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("strip_comments", Path(__file__).with_name("strip_comments.py"))
assert _SPEC and _SPEC.loader
sc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sc)

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_FAILURE = (
    '{file}:{line}: added comment reads as a restated/removed-class comment: "{text}"\n'
    "  -> add a WHY reason (hidden constraint, ordering, units, workaround link,\n"
    '     "do not change X because Y"), or if this is a reviewed WHY the heuristic missed,\n'
    "     add the exact (file, text) pair to scripts/why_keep_list.json in this PR.\n"
    "     '# noqa' alone does not suppress this check."
)


class GitError(RuntimeError):
    """A git invocation failed; message carries its stderr."""


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    text: str


def _git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {args[0]} failed")
    return proc.stdout


def _parse_diff(diff_text: str) -> tuple[dict[str, set[int]], dict[str, set[str]]]:
    added: dict[str, set[int]] = {}
    removed: dict[str, set[str]] = {}
    path: str | None = None
    new_no = 0
    old_left = new_left = 0
    for line in diff_text.split("\n"):
        if line.startswith("\\"):
            continue
        if old_left or new_left:
            if line.startswith("-"):
                old_left -= 1
                if path is not None:
                    removed.setdefault(path, set()).add(line[1:].strip())
            elif line.startswith("+"):
                new_left -= 1
                if path is not None:
                    added.setdefault(path, set()).add(new_no)
                new_no += 1
            else:
                old_left -= 1
                new_left -= 1
                new_no += 1
            continue
        if line.startswith("+++ "):
            target = line[4:]
            path = None if target == "/dev/null" else target.removeprefix("b/")
        elif (m := _HUNK_RE.match(line)) is not None:
            old_left = int(m.group(2)) if m.group(2) is not None else 1
            new_left = int(m.group(4)) if m.group(4) is not None else 1
            new_no = int(m.group(3))
    return {k: v for k, v in added.items() if v}, removed


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Added (`+`) line numbers per file from a unified diff."""
    return _parse_diff(diff_text)[0]


def parse_removed_texts(diff_text: str) -> dict[str, set[str]]:
    """Removed (`-`) line texts per file, stripped, for the reflow exemption."""
    return _parse_diff(diff_text)[1]


def git_diff(pathspecs: list[str], *, staged: bool, base_ref: str | None) -> str:
    """Zero-context diff of the staged index, or of `base_ref...HEAD` when no staging is requested."""
    flags = ["--unified=0", "--no-color", "--no-ext-diff", "--no-textconv"]
    if staged:
        return _git(["diff", "--cached", *flags, "--", *pathspecs])
    return _git(["diff", *flags, f"{base_ref}...HEAD", "--", *pathspecs])


def find_violations(file_path: Path, source: str, added_lines: set[int], removed_texts: set[str]) -> list[Violation]:
    """Added comments that classify as "remove", skipping lines whose text also appears removed."""
    file_key = sc._repo_key(file_path)
    lines = source.split("\n")
    found: list[Violation] = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.COMMENT:
            continue
        line_no, col = tok.start
        if line_no not in added_lines:
            continue
        line = lines[line_no - 1]
        if line.strip() in removed_texts:
            continue
        full_line = line[:col].strip() == ""
        if sc._kind_for(tok.string, line_no, full_line, file_key) == "remove":
            found.append(Violation(file=file_key, line=line_no, text=tok.string))
    return found


def _staged_source(key: str) -> str:
    return _git(["show", f":0:{key}"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="check the staged index (pre-commit)")
    mode.add_argument("--base-ref", help="check base_ref...HEAD (CI)")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)

    violations: list[Violation] = []
    try:
        diff = git_diff(args.paths, staged=args.staged, base_ref=args.base_ref)
        added = parse_added_lines(diff)
        removed = parse_removed_texts(diff)
        top = Path(_git(["rev-parse", "--show-toplevel"]).strip())
        for key, lines in sorted(added.items()):
            if not key.endswith(".py"):
                continue
            source = _staged_source(key) if args.staged else (top / key).read_text(encoding="utf-8", errors="replace")
            violations.extend(find_violations(top / key, source, lines, removed.get(key, set())))
    except (GitError, OSError, tokenize.TokenError, SyntaxError) as exc:
        print(f"check_added_comments: {exc}", file=sys.stderr)
        return 1

    for v in violations:
        print(_FAILURE.format(file=v.file, line=v.line, text=v.text), file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
