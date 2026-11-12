#!/usr/bin/env python3
"""Strip redundant comments from Python files via tokenize; dry-run unless --apply."""

import argparse
import ast
import io
import json
import os
import re
import shutil
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_KEPT_BLOCK = 3

DIRECTIVE_RE = re.compile(
    r"(?:^|#)\s*(?:(?:(?:ruff|flake8)\s*:\s*)?(?i:noqa)(?=[:\s\[]|$)"
    r"|type:\s*ignore\b|type:\s*\(|pragma(?=[:\s\[]|$)|fmt:\s*(?:on|off|skip)"
    r"|isort:\s*(?:skip|split|on|off)|mypy:|pylint:|pyright:|pyre-ignore|pyre-fixme"
    r"|nosec\b|noinspection\b|codespell:\s*ignore)"
)
TYPE_ANNOTATION_RE = re.compile(r"^type:\s*\S")
HEADER_RE = re.compile(r"\b(?:spdx|copyright|license)\b", re.IGNORECASE)
ENCODING_RE = re.compile(r"coding[:=]\s*[-\w.]+")
WHY_RE = re.compile(
    r"\b(?:why|because|hazard|do not|don't|workaround|units?|ordering|order matters"
    r"|race|deadlock|thread-unsafe|timezone|utc|axis|sign convention|rad|deg)\b"
    r"|https?://|#\d+|\bSYNTHETIC\b",
    re.IGNORECASE,
)
TODO_RE = re.compile(r"\b(?:todo|fixme)\b", re.IGNORECASE)
TRACKED_REF_RE = re.compile(r"#\d+|https?://|issue\s+\d+", re.IGNORECASE)


@dataclass
class FileResult:
    new_source: str
    directive_count: int = 0
    removed_count: int = 0
    kept_why_count: int = 0
    manual_review: list[dict] = field(default_factory=list)


def _looks_like_code(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    if not tree.body:
        return False
    plain = (ast.Name, ast.Constant, ast.Attribute)
    return not all(isinstance(n, ast.Expr) and isinstance(n.value, plain) for n in tree.body)


def _classify(text: str, line_no: int, full_line: bool) -> str:
    if line_no == 1 and text.startswith("#!"):
        return "directive"
    body = text.lstrip("#").strip()
    if line_no <= 2 and ENCODING_RE.search(body):
        return "directive"
    if full_line and line_no <= 3 and HEADER_RE.search(body):
        return "directive"
    if DIRECTIVE_RE.search(body):
        return "directive"
    if not full_line and TYPE_ANNOTATION_RE.match(body):
        return "directive"
    if TODO_RE.search(body):
        return "why" if TRACKED_REF_RE.search(body) else "remove"
    if WHY_RE.search(body):
        return "why"
    return "remove"


def _cap_for(next_line: str | None, at_start: bool) -> int:
    if next_line is None or at_start:
        return 0
    return 2 if next_line[:1] not in (" ", "\t", "\r") else 1


def _collapse_blank_runs(items: list[tuple[str, bool]]) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(items)
    while i < n:
        text, removed = items[i]
        if not (removed or text.strip() == ""):
            out.append(text)
            i += 1
            continue
        j = i
        while j < n and (items[j][1] or items[j][0].strip() == ""):
            j += 1
        run = items[i:j]
        if any(r for _, r in run):
            blanks = [t for t, r in run if not r]
            next_line = items[j][0] if j < n else None
            out.extend(blanks[: _cap_for(next_line, not out)])
        else:
            out.extend(t for t, _ in run)
        i = j
    return out


def _trim_long_blocks(kept_full: list[int], lines: list[str], removed_full: set[int], result: FileResult) -> None:
    run = 0
    prev = -2
    for line_no in kept_full:
        run = run + 1 if line_no == prev + 1 else 1
        prev = line_no
        if run > MAX_KEPT_BLOCK:
            removed_full.add(line_no)
            result.kept_why_count -= 1
            result.removed_count += 1
            result.manual_review.append({"line": line_no, "text": lines[line_no - 1].strip(), "tag": "trimmed_why"})


def process_source(source: str) -> FileResult:
    lines = source.split("\n")
    result = FileResult(new_source=source)
    comments = [
        (tok.start[0], tok.start[1], tok.string)
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT
    ]

    removed_full: set[int] = set()
    inline_cuts: dict[int, int] = {}
    kept_full: list[int] = []

    for line_no, col, text in comments:
        full_line = lines[line_no - 1][:col].strip() == ""
        kind = _classify(text, line_no, full_line)
        if kind == "directive":
            result.directive_count += 1
            continue
        if kind == "why":
            result.kept_why_count += 1
            if full_line:
                kept_full.append(line_no)
            continue
        result.removed_count += 1
        if _looks_like_code(text.lstrip("#").strip()):
            result.manual_review.append({"line": line_no, "text": text, "tag": "commented_code"})
        if full_line:
            removed_full.add(line_no)
        else:
            inline_cuts[line_no] = col

    _trim_long_blocks(kept_full, lines, removed_full, result)

    items: list[tuple[str, bool]] = []
    for idx, line in enumerate(lines, start=1):
        if idx in inline_cuts:
            cr = "\r" if line.endswith("\r") else ""
            line = line[: inline_cuts[idx]].rstrip() + cr
        items.append((line, idx in removed_full))

    if removed_full:
        trailing_newline = lines[-1] == ""
        body = items[:-1] if trailing_newline else items
        collapsed = _collapse_blank_runs(body)
        result.new_source = "\n".join(collapsed) + ("\n" if trailing_newline and collapsed else "")
    else:
        result.new_source = "\n".join(t for t, _ in items)
    return result


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            del body[0]
    return tree


def _docstrings(tree: ast.AST) -> list[str | None]:
    return [
        ast.get_docstring(n, clean=False)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]


def ast_equal(original: str, transformed: str) -> bool:
    ta, tb = ast.parse(original), ast.parse(transformed)
    if _docstrings(ta) != _docstrings(tb):
        return False
    a, b = _strip_docstrings(ta), _strip_docstrings(tb)
    return ast.dump(a, include_attributes=False) == ast.dump(b, include_attributes=False)


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.strip-tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def collect_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        files.extend(sorted(p.rglob("*.py")) if p.is_dir() else [p])
    return files


def run(paths: list[Path], apply: bool = False, report: dict | None = None) -> dict:
    if report is None:
        report = {"files": [], "directive_total": 0, "removed_total": 0}
    for path in collect_files(paths):
        entry: dict[str, Any] = {
            "file": str(path),
            "directive_count": 0,
            "removed_count": 0,
            "kept_why_count": 0,
            "manual_review": [],
            "ast_ok": True,
            "write_failed": False,
        }
        report["files"].append(entry)
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                original = fh.read()
            res = process_source(original)
            entry["directive_count"] = res.directive_count
            entry["kept_why_count"] = res.kept_why_count
            entry["manual_review"] = res.manual_review
            report["directive_total"] += res.directive_count
            if not ast_equal(original, res.new_source):
                entry["ast_ok"] = False
                entry["manual_review"].append(
                    {"line": 0, "text": "AST mismatch, file left unchanged", "tag": "ast_mismatch"}
                )
                continue
        except (SyntaxError, tokenize.TokenError, ValueError, RecursionError, OSError) as exc:
            entry["ast_ok"] = False
            entry["manual_review"].append({"line": 0, "text": str(exc), "tag": "ast_mismatch"})
            continue
        entry["removed_count"] = res.removed_count
        report["removed_total"] += res.removed_count
        if apply and res.new_source != original:
            try:
                _write_atomic(path, res.new_source)
            except OSError as exc:
                entry["removed_count"] = 0
                report["removed_total"] -= res.removed_count
                entry["write_failed"] = True
                entry["manual_review"].append({"line": 0, "text": f"write failed: {exc}", "tag": "write_error"})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="explicit no-write mode (default)")
    parser.add_argument("--report", type=Path, help="write JSON report here")
    parser.add_argument("--strict-manual", action="store_true", help="exit 1 on manual_review")
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run are mutually exclusive")

    report: dict = {"files": [], "directive_total": 0, "removed_total": 0}
    try:
        run(args.paths, apply=args.apply, report=report)
    finally:
        if args.report:
            args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    mode = "applied" if args.apply else "dry-run"
    print(
        f"[{mode}] files={len(report['files'])} removed={report['removed_total']} "
        f"directive lines preserved={report['directive_total']}"
    )
    mismatches = [f["file"] for f in report["files"] if not f["ast_ok"]]
    for name in mismatches:
        print(f"ast_mismatch: {name}", file=sys.stderr)
    write_failures = [f["file"] for f in report["files"] if f["write_failed"]]
    for name in write_failures:
        print(f"write_failed: {name}", file=sys.stderr)
    if mismatches or write_failures:
        return 1
    if args.strict_manual and any(f["manual_review"] for f in report["files"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
