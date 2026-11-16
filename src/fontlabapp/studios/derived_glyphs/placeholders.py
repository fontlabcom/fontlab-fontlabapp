# this_file: src/fontlabapp/studios/derived_glyphs/placeholders.py
# SPDX-License-Identifier: Apache-2.0
"""Placeholders tab: ``Scripts/Contours/Placeholder Glyphs.py`` in host mode.

Type glyph names or characters (separated by spaces, commas or new lines).
A single non-ASCII character becomes ``uniXXXX``/``uXXXXX`` with that code
point; a uni-form name gets its code point unless another glyph has it;
other ASCII tokens are names (``&`` or ``1`` are invalid). The live list
shows each name, its code point and the action; existing, repeated and
invalid entries are skipped. NUL, no-break space and the line/paragraph
separators are refused. Create re-checks the font and creates each empty
glyph (Advance width 600 by default, 0-4000) on every master with FontLab's
Add Glyph, each its own Undo step, then reads it back. A code-point write
needs an active Font window and no open Glyph window. Rows that may rebuild
auto glyphs are skipped unless the consent is ticked; a text change clears
the tick. The functions below are the original's, verbatim (only their
local ``fly`` imports are module names here). Adapted from
generate_placeholder_glyphs.py.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PythonQt import QtGui

import fontlabapp.core.edit_guards as edit_guards

from .._kerning_ui import get, row as form_row, spin
from . import _shared
from ._shared import PlanPanel, plural

glyph_copies = _shared.Modules("copies")
glyph_creation = _shared.Modules("creation")


class _Ap:
    """``fly.ap`` as ``font_codes`` reads it: ``ap.fontlab``."""

    @property
    def fontlab(self) -> Any:
        return _shared.backends().fontlab


ap = _Ap()
#: ``create`` reads this global: the Add Glyph error texts name the tab (no history commit runs).
TITLE = "Derived Glyphs: create placeholder glyphs"

NAME = re.compile(r"[A-Za-z_.][A-Za-z0-9_.-]*")


UNI = re.compile(r"uni([0-9A-F]{4})|u([0-9A-F]{5,6})")


UNSAFE = (
    ("\x00", "NUL"),
    ("\u00a0", "no-break space"),
    ("\u2028", "line separator"),
    ("\u2029", "paragraph separator"),
)  # characters that FontLab's text conversion can change


@dataclass(frozen=True)
class Entry:
    """One typed token, the glyph name it stands for, and a parse problem (or "")."""

    token: str
    name: str
    problem: str = ""


@dataclass(frozen=True)
class Row:
    """One planned glyph: code point to assign (or None), note, problem (set: skipped).

    ``rebuild``: automatic glyphs that FontLab may rebuild when the glyph
    appears (``glyph_creation.auto_candidates``).
    """

    name: str
    code: int | None
    note: str = ""
    problem: str = ""
    rebuild: tuple[str, ...] = ()


def check_text(text: str) -> None:
    """Raise ValueError when ``text`` holds a character that FontLab can change."""
    found = [label for char, label in UNSAFE if char in text]
    if found:
        raise ValueError(
            "Refused: the text holds "
            + ", ".join(found)
            + ". FontLab's text conversion can change it; "
            "remove it and type the names again."
        )


def char_name(char: str) -> str:
    """Return uniXXXX for a BMP character, uXXXXX above it."""
    code = ord(char)
    return f"uni{code:04X}" if code <= 0xFFFF else f"u{code:X}"


def code_of(name: str) -> int | None:
    """Return the code point that a uniXXXX / uXXXXX name stands for, else None.

    Surrogates and values above U+10FFFF are not characters: None.
    """
    match = UNI.fullmatch(name)
    if match is None:
        return None
    code = int(match.group(1) or match.group(2), 16)
    return None if 0xD800 <= code <= 0xDFFF or code > 0x10FFFF else code


def parse(text: str) -> list[Entry]:
    """Return one Entry per token. A single non-ASCII character becomes uniXXXX."""
    check_text(text)
    entries: list[Entry] = []
    seen: set[str] = set()
    for token in re.split(r"[\s,]+", text.strip()):
        if not token:
            continue
        name = char_name(token) if len(token) == 1 and not token.isascii() else token
        if not NAME.fullmatch(name):
            entries.append(Entry(token, name, "invalid name"))
        elif name in seen:
            entries.append(Entry(token, name, "repeated"))
        else:
            seen.add(name)
            entries.append(Entry(token, name))
    return entries


def font_codes() -> dict[int, str]:
    """Return {code point: glyph name} from the font-owned glyph records."""

    font = ap.fontlab.CurrentFont()
    if font is None:
        return {}
    return {
        int(code): str(record.name)
        for record in font.glyphs
        for code in record.unicodes
    }


def plan(
    entries: Sequence[Entry], exists: Callable[[str], bool], codes: dict[int, str]
) -> list[Row]:
    """Return one Row per entry: skip problems and existing glyphs, never reuse a code point."""
    rows: list[Row] = []
    for entry in entries:
        if entry.problem:
            rows.append(Row(entry.name, None, problem=entry.problem))
            continue
        if exists(entry.name):
            rows.append(Row(entry.name, None, problem="exists"))
            continue
        code = code_of(entry.name)
        if code is None:
            rows.append(Row(entry.name, None))
        elif code in codes:
            rows.append(
                Row(entry.name, None, f"U+{code:04X} is on {codes[code]}: not assigned")
            )
        else:
            rows.append(Row(entry.name, code, f"U+{code:04X}"))
    return rows


def gate(
    package: Any, rows: Sequence[Row], facts: Any, allow_rebuild: bool
) -> list[Row]:
    """Mark each ready row that can make FontLab rebuild automatic glyphs.

    The row gets ``rebuild``; without ``allow_rebuild`` its problem is the
    "may rebuild auto ..." note, so it is skipped.
    """

    found = glyph_creation.auto_candidates(
        package, facts, [r.name for r in rows if not r.problem]
    )
    gated = []
    for row in rows:
        owners = () if row.problem else found.get(row.name, ())
        problem = (
            glyph_creation.rebuild_note(owners)
            if owners and not allow_rebuild
            else row.problem
        )
        gated.append(Row(row.name, row.code, row.note, problem, owners))
    return gated


def create(
    package: Any,
    rows: Sequence[Row],
    advance: int,
    facts: Any,
    allow_rebuild: bool = False,
) -> dict[str, Any]:
    """Create every ready row as an empty glyph on all masters with FontLab's Add Glyph command.

    Return ``{"glyphs", "layers", "codes", "mismatches"}``. Nothing ready
    returns zeros and makes no native call. A name or code point that is
    taken now, an unconsented rebuild, a code point without an active Font
    window or with an open Glyph window, queued ids are disclosed with their possible date changes. A failure after the first glyph exists
    raises RuntimeError that names the new glyphs.
    """

    ready = [r for r in rows if not r.problem]
    coded = [r for r in ready if r.code is not None]
    masters = list(package.masters)
    if not ready:
        return {
            "pending_updates": (),
            "pending_note": "",
            "glyphs": 0,
            "layers": 0,
            "codes": 0,
            "mismatches": [],
        }
    if coded:
        edit_guards.require_selection_window(int(package.id))
        edit_guards.require_no_editors()
    taken = font_codes()
    for row in ready:
        if row.code is not None and row.code in taken:
            raise ValueError(
                f"Refused: U+{row.code:04X} is on {taken[row.code]} now. Check the list again."
            )
    specs = [
        glyph_creation.NewGlyph(
            row.name,
            tuple((m, advance) for m in masters),
            () if row.code is None else (row.code,),
        )
        for row in ready
    ]

    def read_back() -> list[str]:
        font = ap.fontlab.CurrentFont()
        found = (
            {int(record.id): record for record in font.glyphs}
            if coded and font is not None
            else {}
        )
        problems = []
        for row in ready:
            glyph = package.findName(row.name)
            if glyph is None:
                problems.append(f"{row.name}: missing after the write")
                continue
            for master in masters:
                layer = glyph.findLayer(master)
                width = (
                    glyph_copies.half_up(layer.advanceWidth)
                    if layer is not None and not layer.isNull
                    else None
                )
                if width != advance:
                    problems.append(
                        f"{row.name} · {master}: width {width}, planned {advance}"
                    )
            if row.code is not None:
                record = found.get(int(glyph.fgGlyphId))
                codes = list(record.unicodes) if record is not None else []
                if codes != [row.code]:
                    problems.append(
                        f"{row.name}: Unicode is {codes}, planned U+{row.code:04X}"
                    )
        return problems

    done = glyph_creation.create_glyphs(
        package, specs, TITLE, facts, read_back=read_back, allow_rebuild=allow_rebuild
    )
    return {
        "pending_note": done.pending_note,
        "pending_updates": done.pending_updates,
        "glyphs": len(ready),
        "layers": len(ready) * len(masters),
        "codes": len(coded),
        "mismatches": list(done.mismatches),
    }


class PlaceholdersPanel(PlanPanel):
    """Names, advance width, rebuild consent, live list, Create glyphs."""

    ACTION = "Create glyphs"
    HEADERS = ("Glyph", "Unicode", "Action")
    SELECTION = False

    def __init__(self, tool: Any) -> None:
        self.CONSENT = _shared.backends().creation.REBUILD_LABEL
        super().__init__(tool)

    def build_controls(self, form: Any) -> None:
        self.text = QtGui.QPlainTextEdit()
        self.text.setPlaceholderText("e.g.  A.alt  ampersand.ss01  Ω  ₿")
        self.text.setMaximumHeight(90)
        self.text.setAccessibleName("Glyph names or characters")
        form.addWidget(self.text)
        self.text.textChanged.connect(lambda *_: self.contain(self.text_changed)())
        self.advance = spin(self.widget, 0, 4000, 600, suffix=" units")
        form_row(self.widget, form, "Advance width", self.advance)

    def text_changed(self) -> None:
        """New text: clear the rebuild consent, then plan again."""
        if self.consent is not None:
            self.consent.blockSignals(True)
            self.consent.setChecked(False)
            self.consent.blockSignals(False)
        self.refresh()

    def plan(self, package: Any, facts: Any) -> list[Any]:
        entries = parse(self.text.toPlainText())
        rows = plan(
            entries, lambda name: package.findName(name) is not None, font_codes()
        )
        return gate(package, rows, facts, self.consented())

    def row_key(self, row: Any) -> Any:
        return (row.name, row.code, row.note, row.problem, tuple(row.rebuild))

    def is_ready(self, row: Any) -> bool:
        return not row.problem

    def row_name(self, row: Any) -> str:
        return row.name

    def preview_names(self, row: Any) -> list[str]:
        return []

    def cells(self, row: Any) -> tuple[str, str | None, tuple[Any, ...]]:
        action = (
            f"{row.problem}: skipped"
            if row.problem
            else f"create on {len(self.masters)} masters"
        )
        if row.rebuild and not row.problem:
            action += " · " + glyph_creation.rebuild_note(row.rebuild)
        return (row.name, None, (row.note, action))

    def intro(self) -> str:
        return f"Creates empty glyphs on all {len(self.masters)} masters. Existing glyphs are never overwritten."

    def pending(self, todo: list[Any]) -> str:
        return f"{plural(len(todo), 'glyph')} to create · {len(self.rows) - len(todo)} skipped"

    def write(self, package: Any, rows: list[Any], facts: Any) -> dict[str, Any]:
        return create(
            package, rows, int(get(self.advance.value)), facts, self.consented()
        )

    def result_text(self, result: dict[str, Any]) -> str:
        if not result["glyphs"]:
            return "Nothing to create"
        return (
            f"Created {plural(result['glyphs'], 'glyph')} ({plural(result['layers'], 'master layer')}, "
            f"{plural(result['codes'], 'code point')})"
        )


__all__ = [
    "Entry",
    "PlaceholdersPanel",
    "Row",
    "char_name",
    "check_text",
    "code_of",
    "create",
    "font_codes",
    "gate",
    "parse",
    "plan",
]
