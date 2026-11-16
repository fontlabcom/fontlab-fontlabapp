# this_file: src/fontlabapp/glyphs/character_map/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Read full current-font Unicode metadata without glyph cache/geometry reads."""

from threading import current_thread, main_thread
from time import monotonic

from fontlabapp.glyphs.catalog.native import _context
from fontlabapp.glyphs.character_map.model import Glyph, Snapshot


def check(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("Font coverage capture expired; refresh the whole font.")


def read(font: object, deadline: float) -> tuple[Glyph, ...]:
    """Detach all glyphs, retaining empty, multiple and duplicate assignments."""
    rows, ids, names = [], set(), set()
    for source in font.glyphs:
        check(deadline)
        ident, name, codes = source.id, source.name, tuple(source.unicodes)
        if type(ident) is not int or not isinstance(name, str) or not name:
            raise ValueError("A glyph has invalid identity or name.")
        if ident in ids or name in names:
            raise ValueError("Font glyph identities or names are duplicated.")
        if any(type(code) is not int or not 0 <= code <= 0x10FFFF for code in codes):
            raise ValueError("A glyph has invalid Unicode metadata.")
        ids.add(ident)
        names.add(name)
        rows.append(Glyph(ident, name, codes))
        check(deadline)
    check(deadline)
    return tuple(rows)


def capture() -> Snapshot:
    """Publish only equal complete passes under one two-second UI deadline."""
    if current_thread() is not main_thread():
        raise RuntimeError("Capture font coverage on the main UI thread.")
    deadline = monotonic() + 2.0
    first, _, font = _context(deadline)
    a = read(font, deadline)
    second, _, font = _context(deadline)
    b = read(font, deadline)
    final, _, _ = _context(deadline)
    check(deadline)
    if first != second or second != final or a != b:
        raise ValueError("The font, master or Unicode assignments changed; refresh.")
    return Snapshot(tuple(final), b)
