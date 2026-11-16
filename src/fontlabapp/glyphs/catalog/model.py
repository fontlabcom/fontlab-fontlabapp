# this_file: src/fontlabapp/glyphs/catalog/model.py
# SPDX-License-Identifier: Apache-2.0
"""Practical current-font versions of both archived part2 sort/filter lessons.

Source/proxy views share immutable glyph names, complete Unicode assignments
and local modification timestamps. Basic retains native Qt QRegExp filtering;
Custom retains the original Python matcher, OR fields, dates and sort keys.
Neither view edits the font or changes selection. Native acceptance is pending.
"""

from typing import Any


def capture(*, deadline: float | None = None) -> Any:
    """Read the glyph names, Unicode values and dates of the current font.

    What: return an immutable ``fontlabapp.qt.tables.filter.model.Table`` with the
    columns "Glyph name", "Unicode" and "Modified" in font order. ``rows``
    holds ``(name, "U+0041 U+00C1", "yyyy-MM-dd HH:mm:ss")`` tuples and
    ``epochs`` holds the modification instants (``None`` when unset).

    How: the private ``_glyph_catalog_native.capture`` reads the whole font
    twice from FontGate records mapped by ``package.findFgId``. It never reads
    ``flGlyph.fgGlyph``. A change between the reads rejects the whole result.

    Use: call it on the main UI thread. ``deadline`` is a ``time.monotonic()``
    instant; the default budget is two seconds. It raises ``ValueError`` with no
    open font or a changed font, ``TimeoutError`` after the deadline and
    ``RuntimeError`` off the main thread. It writes nothing. Native
    preservation is not proved by offline tests.
    """
    from fontlabapp.glyphs.catalog.native import capture as implementation

    return implementation(deadline=deadline)


def _show(custom: bool) -> Any:
    from fontlabapp.glyphs.catalog.native import capture
    from fontlabapp.qt.tables.filter.model import show

    return show(
        capture,
        title="Glyph Sorting and Filtering" + (" — Custom" if custom else " — Basic"),
        key="glyph_sort_filter_custom" if custom else "glyph_sort_filter_basic",
        custom=custom,
        description="Captured current-font glyph names, Unicode assignments and local modification dates. Filter and sort the snapshot; Refresh reads the font again. Cells are read-only.",
    )


def show_basic() -> Any:
    """Open the complete basic native Qt source/proxy filtering lesson."""
    return _show(False)


def show_custom() -> Any:
    """Open the complete custom matching, inclusive dates and ordering lesson."""
    return _show(True)


def _show_official(custom: bool) -> Any:
    from fontlabapp.glyphs.catalog.native import capture
    from fontlabapp.qt.tables.filter.model import show

    return show(
        capture,
        title="Glyph Filter Model — " + ("Date Range" if custom else "Local Dates"),
        key="glyph_filter_official_custom" if custom else "glyph_filter_official_basic",
        custom=custom,
        official=True,
        description="Read-only captured glyph metadata with typed dates. Match displayed local dates or apply inclusive calendar-day limits. Refresh reads the current font again.",
    )


def show_official_basic() -> Any:
    """Open complete part3 basic matching over real names, Unicode and Qt dates."""
    return _show_official(False)


def show_official_custom() -> Any:
    """Open complete part3 native-regexp, date-range and comparator workflow."""
    return _show_official(True)


__all__ = [
    "capture",
    "show_basic",
    "show_custom",
    "show_official_basic",
    "show_official_custom",
]
