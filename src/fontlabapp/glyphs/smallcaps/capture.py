# this_file: src/fontlabapp/glyphs/smallcaps/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Capture only named read APIs; never inspect flGlyph.fgGlyph or change state.

FontGate name/unicodes and fgNametable.unc supply detached character facts.
packageLib's public.skipExportGlyphs is a compatibility policy, not a promise
about FontLab's binary exporter. Kerning classes come from one fontpr read for
the captured master; all memberships are retained, including ambiguity.
"""

from collections.abc import Callable
from time import monotonic

from fontlabapp import _native
import fontlabapp.core.scripting as scripting
from fontlabapp.glyphs.smallcaps.model import (
    GlyphFact,
    SC_SUFFIXES,
    analyze,
    check_deadline,
)

EXPORT_SCOPE = (
    "public.skipExportGlyphs compatibility policy (absent list means all); "
    "not a FontLab binary-export guarantee"
)
CASE_SCOPE = (
    "Exact .sc/.smcp/.c2sc particles identify smallcaps; Unicode/name-table "
    "text identifies upper/lower case; unmapped names are unclassified"
)


def _character(code: int) -> str | None:
    """Reject FontGate's unknown sentinel and Unicode surrogate code points."""
    return chr(code) if 0 <= code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else None


def _text(root: str, encoded: dict, table: object) -> str | None:
    """Resolve whole-name Unicode first, then all named ligature components."""
    if root in encoded:
        return encoded[root]
    direct = _character(int(table.unc(root)))
    if direct is not None:
        return direct
    if "_" not in root or root.startswith("_"):
        return None
    parts = [_text(part, encoded, table) for part in root.split("_")]
    return "".join(parts) if all(parts) else None


def _groups(classes: list, deadline: float, clock: Callable) -> dict:
    """Index native pair sides once; flip to Glyphs' glyph-side terminology."""
    groups = {"left": {}, "right": {}}
    for group in classes:
        check_deadline(deadline, clock)
        for member in group["glyph_names"]:
            check_deadline(deadline, clock)
            for source, side in (("left", "right"), ("right", "left")):
                if group[source]:
                    values = groups[side].setdefault(member, [])
                    if group["name"] not in values:
                        values.append(group["name"])
    return groups


def current_report(*, clock: Callable[[], float] = monotonic) -> dict:
    """Return a complete current-font snapshot within a shared three-second budget.

    Check before/after native reads and inside glyph/member/analysis loops. A
    synchronous native getter cannot be interrupted here; an over-budget getter
    is refused on return. Recheck package/master before returning detached data.
    """
    deadline = clock() + 3.0
    package = scripting.current_package()
    if package is None:
        raise ValueError("Open a font before running Smallcap Consistency.")
    check_deadline(deadline, clock)
    package_id, master = package.id, str(package.master)
    font = _native("fontlab").CurrentFont()
    if font is None:
        raise ValueError("No current FontGate font is available.")
    skip = package.packageLib.get("public.skipExportGlyphs", ())
    if not isinstance(skip, (tuple, list)) or any(not isinstance(n, str) for n in skip):
        raise ValueError("public.skipExportGlyphs must be a list of glyph names.")
    skip = set(skip)
    raw, encoded = [], {}
    for glyph in font.glyphs:
        check_deadline(deadline, clock)
        name = str(glyph.name)
        codes = glyph.unicodes
        text = _character(int(codes[0])) if codes else None
        raw.append(name)
        if "." not in name and text is not None:
            encoded[name] = text
    check_deadline(deadline, clock)
    reply = _native("fontpr").call(
        "list_kerning_classes", font_id=scripting.font_id(package), master_name=master
    )
    check_deadline(deadline, clock)
    groups = _groups(reply["classes"], deadline, clock)
    table = _native("fontgate").fgNametable()
    facts = []
    for name in raw:
        check_deadline(deadline, clock)
        root, *suffixes = name.split(".")
        text = _text(root, encoded, table)
        if any(s in SC_SUFFIXES for s in suffixes):
            case = "smallcap"
        elif text is None:
            case = "unknown"
        elif text.isupper():
            case = "upper"
        elif text.islower():
            case = "lower"
        else:
            case = "uncased"
        facts.append(
            GlyphFact(
                name,
                name not in skip,
                case,
                text,
                tuple(groups["left"].get(name, ())),
                tuple(groups["right"].get(name, ())),
            )
        )
    report = analyze(facts, deadline=deadline, clock=clock)
    current = scripting.current_package(package_id)
    if current is None or str(current.master) != master:
        raise ValueError("The current font or master changed; run the report again.")
    report.update(
        family=str(font.info.familyName),
        master=master,
        export_scope=EXPORT_SCOPE,
        case_scope=CASE_SCOPE,
    )
    check_deadline(deadline, clock)
    return report
