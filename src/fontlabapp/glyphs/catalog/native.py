# this_file: src/fontlabapp/glyphs/catalog/native.py
# SPDX-License-Identifier: Apache-2.0
"""Capture all current-font glyph scalar metadata without geometry/cache getters.

FontGate identities and Unicode values come from CurrentFont().glyphs. Map IDs
through the registered package.findFgId, never through native flGlyph.fgGlyph.
Double reads fence observed values, not arbitrary getter/cache side effects.
"""

from datetime import datetime
from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.qt.tables.filter.model import Table


def _check(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("Glyph metadata scan expired; no partial table.")


def _context(deadline: float) -> tuple:
    _check(deadline)
    native = _native("fontlab")
    package = native.flWorkspace.instance().currentPackage
    if package is None or package.isNull:
        raise ValueError("Open a font, then refresh the glyph table.")
    font = native.CurrentFont()
    if font is None or int(font.id) != int(package.fgId):
        raise ValueError("The current font identity is unreadable or changed.")
    if not isinstance(package.master, str):
        raise TypeError("The source master name is unreadable.")
    return (int(package.id), int(package.fgId), package.master), package, font


def _stamp(glyph: Any) -> tuple[bool, str, int | None]:
    stamp = glyph.lastModified
    valid = stamp.isValid
    valid = valid() if callable(valid) else valid
    if type(valid) is not bool:
        raise TypeError("Unreadable glyph modification date.")
    if not valid:
        return False, "", None
    epoch = stamp.toMSecsSinceEpoch()
    if type(epoch) is not int:
        raise TypeError("Unreadable glyph modification instant.")
    text = stamp.toLocalTime().toString("yyyy-MM-dd HH:mm:ss")
    if (
        not isinstance(text, str)
        or len(text) != 19
        or datetime.fromisoformat(text).isoformat(sep=" ", timespec="seconds") != text
    ):
        raise ValueError("Unreadable glyph modification date.")
    return True, text, epoch


def _rows(package: Any, font: Any, deadline: float) -> tuple:
    rows, facts, fg_ids, native_ids, names = [], [], set(), set(), set()
    for source in font.glyphs:
        _check(deadline)
        identity, name = int(source.id), source.name
        if not isinstance(name, str) or not name or identity in fg_ids or name in names:
            raise ValueError("Duplicate or unreadable glyph identity/name.")
        fg_ids.add(identity)
        names.add(name)
        codes = tuple(source.unicodes)
        if any(type(code) is not int or not 0 <= code <= 0x10FFFF for code in codes):
            raise ValueError("Unreadable glyph Unicode assignment.")
        glyph = package.findFgId(identity)
        if glyph is None or glyph.isNull or not glyph.isValid:
            raise ValueError("A mapped native glyph is missing or invalid.")
        native_id = int(glyph.id)
        if (
            native_id in native_ids
            or int(glyph.fgGlyphId) != identity
            or int(glyph.package.id) != int(package.id)
            or glyph.name != name
        ):
            raise ValueError("Native glyph identity/owner/name changed.")
        native_ids.add(native_id)
        valid, stamp, epoch = _stamp(glyph)
        rows.append((name, " ".join(f"U+{code:04X}" for code in codes), stamp))
        facts.append((identity, native_id, name, codes, valid, stamp, epoch))
    _check(deadline)
    return tuple(rows), tuple(facts)


def capture(*, deadline: float | None = None) -> Table:
    """Read the complete source twice under one two-second main-thread budget.

    Font/order/master/name/Unicode/date changes reject the entire observation.
    No font, selection, preferences, history or Output writer is called. Blocking
    native getters cannot be preempted; actual native preservation is unqualified.
    """
    if current_thread() is not main_thread():
        raise RuntimeError("Refresh the glyph table on the main UI thread.")
    limit = monotonic() + 2.0 if deadline is None else deadline
    context, package, font = _context(limit)
    first = _rows(package, font, limit)
    other, package, font = _context(limit)
    second = _rows(package, font, limit)
    final, _, _ = _context(limit)
    _check(limit)
    if context != other or other != final or first != second:
        raise ValueError("Font metadata or context changed; refresh the whole table.")
    return Table(
        ("Glyph name", "Unicode", "Modified"),
        first[0],
        epochs=tuple(row[-1] for row in first[1]),
    )
