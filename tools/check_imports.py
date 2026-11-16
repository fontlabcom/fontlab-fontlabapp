#!/usr/bin/env python3
# this_file: tools/check_imports.py
"""Snapshot Python sources, then verify an import-only formatting change.

Use --snapshot DIR src tests before formatting and --verify DIR afterwards.
Snapshots stay outside the repository. Verification permits adjacent ImportFrom
merges, but preserves every imported name, alias, scope and statement order.
"""

import argparse
import ast
from collections import Counter
import io
from pathlib import Path
import tokenize


class SplitFrom(ast.NodeTransformer):
    """Expand from-imports so permitted merges compare equal in the full AST."""

    def visit_ImportFrom(self, node: ast.ImportFrom) -> list[ast.ImportFrom]:
        return [
            ast.ImportFrom(module=node.module, names=[name], level=node.level)
            for name in node.names
        ]


def imported(tree: ast.AST) -> Counter:
    """Retain duplicate imports as well as module/name/asname triples."""
    result = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            result.update(
                ("." * node.level + (node.module or ""), n.name, n.asname)
                for n in node.names
            )
        elif isinstance(node, ast.Import):
            result.update((n.name, None, n.asname) for n in node.names)
    return result


def comment_text(source: str | bytes) -> list[str]:
    """Retain comment text and order, including existing noqa annotations."""
    if isinstance(source, bytes):
        encoding, _ = tokenize.detect_encoding(io.BytesIO(source).readline)
        source = source.decode(encoding)
    return [
        t.string
        for t in tokenize.generate_tokens(io.StringIO(source).readline)
        if t.type == tokenize.COMMENT
    ]


def non_import_tokens(source: str | bytes) -> list[tuple[int, str]]:
    """Check exact non-import spelling, ignoring only whitespace and separators."""
    if isinstance(source, bytes):
        encoding, _ = tokenize.detect_encoding(io.BytesIO(source).readline)
        source = source.decode(encoding)
    lines = source.split("\n")
    spans = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            begin = len(lines[node.lineno - 1].encode()[: node.col_offset].decode())
            end = len(
                lines[node.end_lineno - 1].encode()[: node.end_col_offset].decode()
            )
            spans.append(((node.lineno, begin), (node.end_lineno, end)))
    ignored = {
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
    }
    return [
        (t.type, t.string)
        for t in tokenize.generate_tokens(io.StringIO(source).readline)
        if t.type not in ignored
        and not (t.type == tokenize.OP and t.string == ";")
        and not any(start <= t.start < end for start, end in spans)
        and t.type != tokenize.COMMENT
    ]


def assert_equivalent(before: str | bytes, after: str | bytes) -> None:
    """Check import triples and the entire ordered, scope-preserving AST."""
    old, new = ast.parse(before), ast.parse(after)
    assert imported(old) == imported(new), "Imported module/name/asname triples changed"
    assert ast.dump(SplitFrom().visit(old)) == ast.dump(SplitFrom().visit(new)), (
        "Non-import AST, scope, name order or module order changed"
    )
    assert comment_text(before) == comment_text(after), (
        "Comments or noqa markers changed"
    )
    assert non_import_tokens(before) == non_import_tokens(after), (
        "Non-import statement text changed"
    )


def check(snapshot: Path, roots: list[Path], write: bool = False) -> int:
    """Save source bytes or verify all files against an external snapshot."""
    changed = 0
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            saved = snapshot / path.resolve().relative_to(Path.cwd().resolve())
            if write:
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(path.read_bytes())
            elif saved.read_bytes() != path.read_bytes():
                try:
                    assert_equivalent(saved.read_bytes(), path.read_bytes())
                except AssertionError as error:
                    raise AssertionError(f"{path}: {error}") from error
                changed += 1
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--snapshot", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args()
    count = check(args.snapshot or args.verify, args.roots, bool(args.snapshot))
    print("Snapshot saved" if args.snapshot else f"AST PASS: {count} changed files")
