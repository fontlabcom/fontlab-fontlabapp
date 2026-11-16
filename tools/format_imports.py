#!/usr/bin/env python3
# this_file: tools/format_imports.py
"""Normalize imports without sorting modules or moving statements between scopes.

Uses the repository's default Ruff limit (88 columns). Comments and blank lines
are merge boundaries. --split-statements also splits pre-existing non-import
semicolon separators; statement text and the normalized AST remain unchanged.
"""

import argparse
import ast
from collections import Counter
import io
from pathlib import Path
import tokenize

LINE_LENGTH = 88


def positions(source: str) -> tuple[list[str], list[int]]:
    """Locate AST UTF-8 byte columns in the original Unicode source."""
    parts = source.split("\n")
    lines = [line + "\n" for line in parts[:-1]] + parts[-1:]
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return lines, offsets


def offset(lines: list[str], offsets: list[int], row: int, column: int) -> int:
    """Convert one AST byte offset to a character offset without losing Unicode."""
    return offsets[row - 1] + len(lines[row - 1].encode()[:column].decode())


def bodies(tree: ast.AST):
    """Visit statement lists, including handlers, TYPE_CHECKING and local imports."""
    for parent in ast.walk(tree):
        for _, value in ast.iter_fields(parent):
            if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                yield value


def indent_unit(source: str) -> str:
    """Follow the file's existing suite indentation, defaulting to four spaces."""
    stack, units = [""], []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.INDENT:
            units.append(token.string[len(stack[-1]) :])
            stack.append(token.string)
        elif token.type == tokenize.DEDENT:
            stack.pop()
    return Counter(units).most_common(1)[0][0] if units else "    "


def split_statements(source: str, all_statements: bool = False) -> str:
    """Split separators, expanding inline suites only when needed for valid syntax."""
    lines, offsets = positions(source)
    newline = "\r\n" if "\r\n" in source else "\n"
    unit, edits = indent_unit(source), []
    for body in bodies(ast.parse(source)):
        first = body[0]
        start = offset(lines, offsets, first.lineno, first.col_offset)
        prefix = source[offsets[first.lineno - 1] : start]
        indent = prefix[: len(prefix) - len(prefix.lstrip())]
        selected = [
            (a, b)
            for a, b in zip(body, body[1:])
            if a.end_lineno == b.lineno
            and (
                all_statements
                or isinstance(a, (ast.Import, ast.ImportFrom))
                or isinstance(b, (ast.Import, ast.ImportFrom))
            )
        ]
        inline = prefix.strip() and (
            selected or isinstance(first, (ast.Import, ast.ImportFrom))
        )
        if inline:
            colon = source.rfind(":", offsets[first.lineno - 1], start) + 1
            indent += unit
            edits.append((colon, start, newline + indent))
        for a, b in selected:
            end = offset(lines, offsets, a.end_lineno, a.end_col_offset)
            begin = offset(lines, offsets, b.lineno, b.col_offset)
            assert source[end:begin].strip() == ";", source[end:begin]
            edits.append((end, begin, newline + indent))
    for start, end, text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    return source


def format_imports(source: str, *, split_all: bool = False) -> str:
    """Merge only adjacent uncommented from-imports and wrap long name lists."""
    source = split_statements(source, split_all)
    lines, offsets = positions(source)
    newline = "\r\n" if "\r\n" in source else "\n"
    unit, edits = indent_unit(source), []
    comments = [
        t
        for t in tokenize.generate_tokens(io.StringIO(source).readline)
        if t.type == tokenize.COMMENT
    ]
    for body in bodies(ast.parse(source)):
        index = 0
        while index < len(body):
            node = body[index]
            index += 1
            if not isinstance(node, ast.ImportFrom) or any(
                n.name == "*" for n in node.names
            ):
                continue
            start = offset(lines, offsets, node.lineno, node.col_offset)
            end = offset(lines, offsets, node.end_lineno, node.end_col_offset)
            if any(node.lineno <= t.start[0] < node.end_lineno for t in comments):
                continue
            names, last = list(node.names), node
            while index < len(body):
                other = body[index]
                tail_start = offset(
                    lines, offsets, last.end_lineno, last.end_col_offset
                )
                tail = source[tail_start : offsets[last.end_lineno]]
                if (
                    not isinstance(other, ast.ImportFrom)
                    or (other.module, other.level) != (node.module, node.level)
                    or any(n.name == "*" for n in other.names)
                    or tail.strip()
                    or other.lineno != last.end_lineno + 1
                    or any(
                        other.lineno <= t.start[0] < other.end_lineno for t in comments
                    )
                ):
                    break
                names.extend(other.names)
                last = other
                index += 1
                end = offset(lines, offsets, last.end_lineno, last.end_col_offset)
            indent = lines[node.lineno - 1][: node.col_offset]
            head = "from " + "." * node.level + (node.module or "") + " import "
            aliases = [n.name + (" as " + n.asname if n.asname else "") for n in names]
            compact = head + ", ".join(aliases)
            if len(indent + compact) <= LINE_LENGTH:
                replacement = compact
            else:
                replacement = head + "(" + newline
                replacement += "".join(
                    indent + unit + name + "," + newline for name in aliases
                )
                replacement += indent + ")"
            edits.append((start, end, replacement))
    for start, end, text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    return source


if __name__ == "__main__":
    from check_imports import assert_equivalent

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots", nargs="*", type=Path, default=[Path("src"), Path("tests")]
    )
    parser.add_argument("--split-statements", action="store_true")
    args = parser.parse_args()
    changed = 0
    for root in args.roots:
        for path in sorted(root.rglob("*.py")):
            encoding, _ = tokenize.detect_encoding(
                io.BytesIO(path.read_bytes()).readline
            )
            before = path.read_bytes().decode(encoding)
            after = format_imports(before, split_all=args.split_statements)
            assert_equivalent(before, after)
            if before != after:
                path.write_bytes(after.encode(encoding))
                changed += 1
    print(f"Formatted {changed} files")
