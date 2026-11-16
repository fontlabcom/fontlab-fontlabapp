# this_file: src/fontlabapp/studios/font_audit/model.py
# SPDX-License-Identifier: Apache-2.0
"""Font Audit calculations over one ``_records.Catalogue``: the absorbed reports' rules.

What: the Font Overview cards, the Label Statistics groups, the Glyph Table
CSV rows and file format, the Unicode Coverage blocks, the Empty Glyphs scan
and the shared texts of each report, kept exactly as in the Scriptmix
originals (thresholds, defaults, order, formats). Overview "Empty" means no
contours and no components on the current master; Empty Glyphs counts
contours only, on every master (a missing layer is empty): the originals
differ and so do these helpers. Pure and Qt-free.
Used by ``fontlabapp.studios.font_audit`` (session and tabs).
"""

import csv
import io
import pathlib
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any

from .._records import Catalogue
from .blocks import BLOCKS

# Font Overview ----------------------------------------------------------------
OVERVIEW_STATUS = "Composites: a component on any master. Empty: no contours and no components."
METRIC_COLUMNS = ("Master", "Ascender", "Caps", "x-height", "Descender", "Kern pairs")


def overview_cards(cat: Catalogue) -> dict[str, int]:
    """The eight Font Overview cards, in their original order."""
    records = cat.records
    found = [r for r in records if r.found]
    codes = [code for r in records for code in r.unicodes]
    return {
        "Glyphs": len(records),
        "Encoded glyphs": sum(1 for r in records if r.unicodes),
        "Code points": len(set(codes)),
        "Masters": len(cat.masters),
        "Composites": sum(1 for r in found if r.composite),
        f"Empty on {cat.master}": sum(
            1 for r in found if r.current_contours is not None and not r.current_contours and not r.components
        ),
        "Marked": sum(1 for r in found if r.mark),
        "With notes": sum(1 for r in found if r.note.strip()),
    }


def subtitle(cat: Catalogue) -> str:
    return f"{cat.family} · {cat.upm} units per em · current master {cat.master}"


def metric_text(value: Any) -> str:
    """Overview metric cells: ``{value:g}``."""
    return f"{value:g}"


# Label Statistics -------------------------------------------------------------
HUES = [(15, "red"), (45, "orange"), (70, "yellow"), (160, "green"), (200, "teal"), (255, "blue"),
        (290, "purple"), (335, "pink"), (361, "red")]


def font_labels(cat: Catalogue) -> list[tuple[str, int]]:
    """``[(glyph name, mark)]`` in font order (every glyph, as ``CurrentFont().glyphs``)."""
    return [(r.name, r.mark) for r in cat.records]


def suffix_of(name: str) -> str:
    """'.ss01.sc' for 'a.ss01.sc'; '' for 'a' and '.notdef'."""
    _head, dot, tail = name[1:].partition(".")
    return "." + tail if dot else ""


def mark_label(mark: int) -> str:
    """Describe FontLab colour marks using the original hue buckets."""
    if mark <= 0:
        return "Unmarked"
    if 1000 <= mark <= 1255:
        return f"Grey {mark - 1000}"
    if mark > 360:
        return f"Mark {mark}"
    hue = mark - 1
    return next(name for limit, name in HUES if hue < limit).capitalize() + f" (hue {hue}°)"


def mark_rgb(mark: int, lightness: int = 150) -> tuple[str, int, int, int] | None:
    """The original swatch colour: ``("hsl", hue, 200, lightness)`` or ``("rgb", g, g, g)``."""
    if mark <= 0:
        return None
    if mark <= 360:
        return ("hsl", mark - 1, 200, lightness)
    grey = min(255, lightness // 2 + max(0, mark - 1000) // 2)
    return ("rgb", grey, grey, grey)


def statistics(labels: Iterable[tuple[str, int]]) -> tuple[list, list]:
    """``([(mark, [names])], [(suffix, [names])])`` sorted by count, largest first."""
    marks: dict[int, list[str]] = {}
    suffixes: dict[str, list[str]] = {}
    for name, mark in labels:
        marks.setdefault(mark, []).append(name)
        suffixes.setdefault(suffix_of(name), []).append(name)

    def order(item: Any) -> Any:
        return (-len(item[1]), str(item[0]))

    return sorted(marks.items(), key=order), sorted(suffixes.items(), key=order)


def label_subtitle(labels: Sequence[tuple[str, int]], marks: Sequence, suffixes: Sequence) -> str:
    if not labels:
        return "Open a font first."
    marked = sum(len(n) for m, n in marks if m)
    suffixed = sum(len(n) for s, n in suffixes if s)
    colours = sum(1 for m, _ in marks if m)
    sets = sum(1 for s, _ in suffixes if s)
    return (f"{len(labels)} glyphs: {marked} marked in {colours} colours, {suffixed} with a suffix in "
            f"{sets} sets. Click a row to select those glyphs.")


# Glyph Table CSV --------------------------------------------------------------
CSV_TITLE = "Export glyph table"
CSV_DEFAULT = "glyphs.csv"
CSV_FILTER = "CSV files (*.csv)"
CSV_HINT = "Choose a file to export, or copy the CSV."


def table(cat: Catalogue, names: Iterable[str]) -> tuple[list[str], list[list[Any]]]:
    """Header and rows of Glyph Table CSV for ``names``; unknown glyphs are skipped."""
    header = ["glyph", "unicode", *[f"width {m}" for m in cat.masters], "contours", "components"]
    known = cat.by_name()
    rows = []
    for name in names:
        record = known.get(name)
        if record is None or not record.found:
            continue
        widths = ["" if width is None else round(width, 2) for width in record.widths]
        rows.append([
            name,
            " ".join(f"{c:04X}" for c in record.unicodes),
            *widths,
            record.current_contours or 0,
            " ".join(record.components),
        ])
    return header, rows


def table_subtitle(cat: Catalogue, rows: Sequence) -> str:
    return (f"{len(rows)} glyphs · widths for {len(cat.masters)} masters · contours and components on "
            f"{cat.master}. Click a header to sort.")


def to_csv(header: Sequence, rows: Iterable[Sequence]) -> str:
    """Encode report rows with standard CSV quoting and LF line endings."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def write_csv(path: Any, header: Sequence, rows: Iterable[Sequence]) -> int:
    """Write the CSV (UTF-8 with BOM so spreadsheets detect it); return the byte size."""
    pathlib.Path(path).write_text(to_csv(header, rows), encoding="utf-8-sig", newline="")
    return pathlib.Path(path).stat().st_size


# Unicode Coverage -------------------------------------------------------------
def font_codes(cat: Catalogue) -> dict[int, str]:
    """{code point: glyph name} of the font (first glyph wins)."""
    out: dict[int, str] = {}
    for record in cat.records:
        for code in record.unicodes:
            out.setdefault(code, record.name)
    return out


def assigned(start: int, end: int) -> int:
    """Number of assigned characters (not Cn) in a range."""
    return sum(1 for code in range(start, end + 1) if unicodedata.category(chr(code)) != "Cn")


def coverage(codes: Iterable[int], show_all: bool = False) -> tuple[list[tuple], list[int]]:
    """``[(start, end, block, covered, assigned)]`` for touched (or all) blocks, and the codes outside."""
    codes = list(codes)
    rows, outside = [], set(codes)
    for start, end, name in BLOCKS:
        inside = [c for c in codes if start <= c <= end]
        outside.difference_update(inside)
        if inside or show_all:
            rows.append((start, end, name, len(inside), assigned(start, end)))
    return rows, sorted(outside)


def percent(covered: int, total: int) -> str:
    """The original progress-bar text."""
    return f"{100.0 * covered / total:.0f}%" if total else "–"


def coverage_subtitle(codes: dict, rows: Sequence[tuple]) -> str:
    if not codes:
        return "Open a font with encoded glyphs first."
    full = sum(1 for r in rows if r[3] and r[3] >= r[4])
    touched = sum(1 for r in rows if r[3])
    return (f"{len(codes)} code points in {touched} blocks; {full} complete. "
            "Click a block to preview it; use Select block glyphs in Font window to select its glyphs.")


def coverage_status(rows: Sequence, outside: Sequence) -> str:
    extra = f" · {len(outside)} code points outside planes 0–1" if outside else ""
    return f"{len(rows)} blocks listed{extra}"


def block_names(codes: dict[int, str], start: int, end: int) -> list[str]:
    """Glyphs of the block, in the first-glyph-wins code order the original uses."""
    return [glyph for code, glyph in codes.items() if start <= code <= end]


# Empty Glyphs -----------------------------------------------------------------
SPACE_NAMES = frozenset({".notdef", ".null", "nbspace", "space", "CR", "nonmarkingreturn"})
SPACE_CATEGORIES = frozenset({"Zs", "Zl", "Zp", "Cc", "Cf"})
HIDE_SPACES = "Hide space-like glyphs (empty on purpose)"


def is_whitespace(name: str, codes: Iterable[int]) -> bool:
    """Recognise intentional empty glyphs by Unicode category and conventional names."""
    if any(unicodedata.category(chr(c)) in SPACE_CATEGORIES for c in codes):
        return True
    return name in SPACE_NAMES or name.endswith("space")


def scan_empty(cat: Catalogue, skip_whitespace: bool) -> list[tuple[str, list[str]]]:
    """``[(glyph name, [master, ...] without contours)]`` in font order."""
    out = []
    for record in cat.records:
        if skip_whitespace and is_whitespace(record.name, record.unicodes):
            continue
        if not record.found:
            continue
        empty = [m for m, count in zip(cat.masters, record.contours) if not count]
        if empty:
            out.append((record.name, empty))
    return out


def empty_subtitle(rows: Sequence[tuple[str, list[str]]], masters: Sequence[str]) -> str:
    partial = sum(1 for _, empty in rows if len(empty) < len(masters))
    return (f"{len(rows)} glyph{'s' if len(rows) != 1 else ''} without outlines on at least one of "
            f"{len(masters)} masters; {partial} only on some (likely mistakes).")


# Shared -----------------------------------------------------------------------
def plural(count: int) -> str:
    return "s" if count != 1 else ""


def preview_text(names: Iterable[str]) -> str:
    """TMetrics text for ``names``: ``/a/b``; empty for none."""
    names = [n for n in names if n]
    return "/" + "/".join(names) if names else ""


__all__ = [
    "CSV_DEFAULT", "CSV_FILTER", "CSV_HINT", "CSV_TITLE", "HIDE_SPACES", "HUES", "METRIC_COLUMNS",
    "OVERVIEW_STATUS", "SPACE_CATEGORIES", "SPACE_NAMES", "assigned", "block_names", "coverage",
    "coverage_status", "coverage_subtitle", "empty_subtitle", "font_codes", "font_labels",
    "is_whitespace", "label_subtitle", "mark_label", "mark_rgb", "metric_text", "overview_cards",
    "percent", "plural", "preview_text", "scan_empty", "statistics", "subtitle", "suffix_of", "table",
    "table_subtitle", "to_csv", "write_csv",
]
