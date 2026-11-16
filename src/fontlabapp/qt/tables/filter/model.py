# this_file: src/fontlabapp/qt/tables/filter/model.py
# SPDX-License-Identifier: Apache-2.0
"""Immutable three-column tables and the archived custom filter semantics.

Basic Qt filtering remains native QRegExp; Custom preserves Python re.search,
whole-string fnmatchcase, substring matching, casefold and lexical day bounds.
Both original views share one source model, never editable native font objects.
"""

import fnmatch
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

Row = tuple[str, str, str]


@dataclass(frozen=True)
class Table:
    """Complete captured scalar table; no live native handles or partial rows."""

    headers: Row
    rows: tuple[Row, ...]
    epochs: tuple[int | None, ...] | None = None

    def __post_init__(self) -> None:
        if (
            type(self.headers) is not tuple
            or len(self.headers) != 3
            or any(not isinstance(v, str) for v in self.headers)
        ):
            raise TypeError("Provide exactly three text column headings.")
        if type(self.rows) is not tuple or any(
            type(row) is not tuple
            or len(row) != 3
            or any(not isinstance(v, str) for v in row)
            for row in self.rows
        ):
            raise TypeError(
                "Provide a complete immutable table of three text cells per row."
            )

        if self.epochs is not None:
            if type(self.epochs) is not tuple or len(self.epochs) != len(self.rows):
                raise TypeError(
                    "Epoch milliseconds must cover the complete row domain."
                )
            for row, epoch in zip(self.rows, self.epochs, strict=True):
                if epoch is not None and (
                    type(epoch) is not int or not -(2**63) <= epoch < 2**63
                ):
                    raise TypeError(
                        "Epoch milliseconds require a signed64-bit integer or None."
                    )
                if bool(row[2]) != (epoch is not None):
                    raise ValueError("A missing datetime and missing epoch must agree.")


@dataclass(frozen=True)
class Query:
    """Original custom matching rules and independent filter/sort case switches."""

    pattern: str = ""
    syntax: Literal["regular", "wildcard", "fixed"] = "regular"
    case_sensitive: bool = False
    sort_sensitive: bool = False
    lower: str | None = None
    upper: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pattern, str) or self.syntax not in (
            "regular",
            "wildcard",
            "fixed",
        ):
            raise ValueError("Use text and regular/wildcard/fixed syntax.")
        if (
            type(self.case_sensitive) is not bool
            or type(self.sort_sensitive) is not bool
        ):
            raise TypeError("Case switches must be boolean.")
        for bound in (self.lower, self.upper):
            if bound is not None and (
                not isinstance(bound, str)
                or date.fromisoformat(bound).isoformat() != bound
            ):
                raise ValueError("Date limits require exact ISO calendar days.")

    def matches(self, text: str) -> bool:
        """Apply original casefold before matching; invalid regex matches nothing."""
        needle = self.pattern
        if not self.case_sensitive:
            text, needle = text.casefold(), needle.casefold()
        if self.syntax == "wildcard":
            return fnmatch.fnmatchcase(text, needle)
        if self.syntax == "fixed":
            return needle in text
        try:
            return re.search(needle, text) is not None
        except re.error:
            return False

    def accepts(self, row: Row) -> bool:
        """Match either first column, then inclusive optional bounds on day text."""
        if not (self.matches(row[0]) or self.matches(row[1])):
            return False
        day = row[2][:10]
        return (self.lower is None or day >= self.lower) and (
            self.upper is None or day <= self.upper
        )


def sort_key(text: str, column: int, sensitive: bool) -> str:
    """Keep original last-angle-token ordering in the second column."""
    if column == 1:
        text = text.rsplit("<", maxsplit=1)[-1].rstrip(">")
    return text if sensitive else text.casefold()


def show(
    capture: Callable[[], Table],
    *,
    title: str,
    key: str,
    custom: bool = False,
    description: str = "",
    official: bool = False,
) -> Any:
    """Open an owned generic source/proxy panel, importing Qt only on request."""
    from fontlabapp.qt.tables.filter.ui import FilterTableDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(
        lambda parent: FilterTableDialog(
            parent, title, key, capture, custom, description, official=official
        ),
        key,
    )


def show_demo() -> Any:
    """Open the eight-row read-only demonstration without reading a font."""
    rows = (
        ("A", "Latin capital A <U+0041>", "2026-01-05 09:30"),
        ("B", "Latin capital B <U+0042>", "2026-01-12 14:05"),
        ("a", "Latin small a <U+0061>", "2026-02-02 11:00"),
        ("Aacute", "Latin capital A acute <U+00C1>", "2026-02-20 16:45"),
        ("alpha", "Greek small alpha <U+03B1>", "2026-03-08 08:10"),
        ("Alpha", "Greek capital alpha <U+0391>", "2026-03-09 10:20"),
        ("zero", "Digit zero <U+0030>", "2026-04-01 13:15"),
        ("space", "Space <U+0020>", "2026-04-15 17:55"),
    )
    table = Table(("Glyph", "Description", "Modified"), rows)
    return show(
        lambda: table,
        title="Table Filter Demo",
        key="widgets-demo-table-filter",
        custom=True,
        description="Sample rows only. Filter the top table into the bottom one.",
    )
