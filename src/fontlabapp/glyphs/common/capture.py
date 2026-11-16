# this_file: src/fontlabapp/glyphs/common/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Bounded registered-font double reads, without current-font or canvas access.

Read canonical font-owned FontGate records, never flGlyph.fgGlyph. Every family,
name, scalar and registration participates in stale detection. Reads preserve
the order supplied by AllFonts; no font/master/selection activation is needed.
"""

from collections.abc import Callable
from threading import current_thread, main_thread
from time import monotonic
from fontlabapp import _native
from fontlabapp.glyphs.common.model import Font, Glyph, analyze, checkpoint, validate


def read(check: Callable) -> tuple[Font, ...]:
    """Read all registered carriers, refusing invalid/missing/repeated identities."""
    check()
    if current_thread() is not main_thread():
        raise ValueError("Common Glyphs capture requires the FontLab GUI thread.")
    native = _native("fontlab")
    registered, identities = {}, set()
    items = native.flWorkspace.instance().packages()
    check()
    for item in items:
        check()
        package = native.flPackage(item)
        check()
        if package is None or package.isNull:
            raise ValueError("Open font registration changed; run again.")
        fg_id, identity = int(package.fgId), int(package.id)
        if fg_id <= 0 or identity <= 0 or fg_id in registered or identity in identities:
            raise ValueError("Open fonts have invalid or duplicate registrations.")
        registered[fg_id] = identity
        identities.add(identity)
    raw_fonts = native.AllFonts()
    check()
    rows, seen = [], set()
    for font in raw_fonts:
        check()
        fg_id = int(font.id)
        if fg_id not in registered or fg_id in seen:
            raise ValueError(
                "An open font is not uniquely registered in the workspace."
            )
        seen.add(fg_id)
        family, glyphs = str(font.info.familyName), []
        raw_glyphs = font.glyphs
        check()
        for glyph in raw_glyphs:
            check()
            name, codes = str(glyph.name), []
            raw_codes = glyph.unicodes
            check()
            for code in raw_codes:
                check()
                codes.append(code)
            glyphs.append(Glyph(name, tuple(codes)))
        rows.append(Font(registered[fg_id], fg_id, family, tuple(glyphs)))
    if seen != set(registered):
        raise ValueError("A registered font is absent from AllFonts; run again.")
    result = tuple(rows)
    validate(result, check)
    return result


def capture(
    metadata: Callable,
    *,
    deadline: float | None = None,
    clock: Callable = monotonic,
    cancelled: Callable = lambda: False,
) -> dict:
    """Publish only a complete report stable across metadata work and two reads.

    Native calls cannot be preempted; check immediately after they return. The
    caller's shared deadline/cancellation flows into metadata and all loops.
    """
    limit = clock() + 2.5 if deadline is None else deadline
    check = lambda: checkpoint(limit, clock, cancelled)
    opening = read(check)
    report = analyze(opening, metadata, check=check)
    if opening != read(check):
        raise ValueError("Open fonts changed during the scan; refresh the report.")
    check()
    return report
