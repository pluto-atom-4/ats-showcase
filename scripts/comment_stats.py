#!/usr/bin/env python3
"""Count comment volume and directive share across Python files via tokenize (point-in-time, read-only)."""

import argparse
import importlib.util
import io
import json
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path

_SC_SPEC = importlib.util.spec_from_file_location("strip_comments", Path(__file__).with_name("strip_comments.py"))
assert _SC_SPEC and _SC_SPEC.loader
_sc = importlib.util.module_from_spec(_SC_SPEC)
_SC_SPEC.loader.exec_module(_sc)

DEFAULT_PATHS = ["src", "tests"]


@dataclass(frozen=True)
class CommentStats:
    """Comment volume and directive share for a set of Python files."""

    full_line_comments: int
    inline_comments: int
    full_plus_inline_by_base: dict[str, int]
    files_with_comment: int
    files_total: int
    comment_text_bytes: int
    comment_tokens_proxy: int
    comment_share_pct: float
    total_bytes: int
    directive_comments: int


def _collect(paths: list[Path]) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    seen: set[Path] = set()
    for root in paths:
        if root.is_dir():
            candidates = sorted(root.rglob("*.py"))
        elif root.suffix == ".py" and root.is_file():
            candidates = [root]
        else:
            candidates = []
        for file in candidates:
            if file not in seen:
                seen.add(file)
                pairs.append((file, root))
    return pairs


def _base_key(file: Path, root: Path) -> str:
    anchor = root if root.name == "" else root.parent
    return file.relative_to(anchor).parts[0]


def _comments(source: str) -> list[tuple[str, bool, int]]:
    lines = source.split("\n")
    out: list[tuple[str, bool, int]] = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            line_no, col = tok.start
            out.append((tok.string, lines[line_no - 1][:col].strip() == "", line_no))
    return out


def compute_stats(paths: list[Path]) -> CommentStats:
    """Tokenize every .py under paths and tally comment volume and directive share."""
    full = inline = directive = files_with = files_total = text_bytes = total_bytes = 0
    by_base: dict[str, int] = {}
    for file, root in _collect(paths):
        raw = file.read_bytes()
        try:
            comments = _comments(raw.decode("utf-8"))
        except (ValueError, SyntaxError, tokenize.TokenError):
            continue
        files_total += 1
        total_bytes += len(raw)
        base = _base_key(file, root)
        by_base.setdefault(base, 0)
        if comments:
            files_with += 1
        for text, full_line, line_no in comments:
            if _sc._classify(text, line_no, full_line) == "directive":
                directive += 1
            if full_line:
                full += 1
            else:
                inline += 1
            text_bytes += len(text.encode("utf-8"))
            by_base[base] += 1
    return CommentStats(
        full_line_comments=full,
        inline_comments=inline,
        full_plus_inline_by_base=by_base,
        files_with_comment=files_with,
        files_total=files_total,
        comment_text_bytes=text_bytes,
        comment_tokens_proxy=text_bytes // 4,
        comment_share_pct=text_bytes / total_bytes * 100 if total_bytes else 0.0,
        total_bytes=total_bytes,
        directive_comments=directive,
    )


def format_table(stats: CommentStats) -> str:
    """Render stats as a markdown table."""
    rows: list[tuple[str, str]] = [
        ("full-line comments", str(stats.full_line_comments)),
        ("inline comments", str(stats.inline_comments)),
        ("directive comments", str(stats.directive_comments)),
    ]
    rows += [(f"full+inline in `{base}`", str(n)) for base, n in stats.full_plus_inline_by_base.items()]
    rows += [
        ("files with comment", f"{stats.files_with_comment}/{stats.files_total}"),
        ("comment text bytes", str(stats.comment_text_bytes)),
        ("comment tokens (bytes/4 proxy)", str(stats.comment_tokens_proxy)),
        ("total bytes", str(stats.total_bytes)),
        ("comment share of bytes", f"{stats.comment_share_pct:.2f}%"),
    ]
    body = "\n".join(f"| {name} | {value} |" for name, value in rows)
    return f"| metric | value |\n|---|---|\n{body}"


def main(argv: list[str] | None = None) -> int:
    """Print the comment table for PATHs; optionally write JSON; always returns 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path(p) for p in DEFAULT_PATHS])
    parser.add_argument("--json", dest="json_out", type=Path, metavar="OUT")
    args = parser.parse_args(argv)
    stats = compute_stats(args.paths)
    print(format_table(stats))
    if args.json_out:
        args.json_out.write_text(json.dumps(asdict(stats)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
