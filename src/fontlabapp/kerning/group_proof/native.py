# this_file: src/fontlabapp/kerning/group_proof/native.py
# SPDX-License-Identifier: Apache-2.0
"""Capture complete peer membership and open explicit named proof symbols.

Native pair-side left maps to Glyphs visual right and vice versa, matching the
existing Glyport visual-side definitions. Multiple distinct classes on one side
cannot represent the original single-group field and receive a diagnosis. Use
CurrentFont.glyphs FG metadata, never a flGlyph.fgGlyph getter or an unrequested
mark/layer/Unicode scan. Existing App
layer selection and fresh named-tab safeguards retain their native gates.
"""

from dataclasses import dataclass
from time import monotonic
from typing import Any

import fontlabapp.proof.tabs.named as named
from fontlabapp import _native
from fontlabapp.kerning.group_proof.selection import read as first_selection
from fontlabapp.kerning.group_proof.model import GlyphGroups, Proof
from fontlabapp.core.scripting import current_package, kerning_class_lists


class AmbiguousGroups(ValueError):
    """Native multiple side memberships cannot represent one Glyphs group."""


class NoSelectedGlyph(ValueError):
    """An absent font/selection gets the original Script Error diagnosis."""


@dataclass(frozen=True)
class Snapshot:
    """Keep the immutable source selection and every ordered glyph/group row."""

    package_id: int
    master: str
    current_id: int
    rows: tuple[GlyphGroups, ...]
    selection: Any


def _check(deadline: float) -> None:
    """Refuse a whole operation rather than publish a partial peer proof."""
    if monotonic() >= deadline:
        raise TimeoutError(
            "Kerning-group proof exceeded its deadline; no partial proof."
        )


def _group(groups: list[str], name: str, side: str) -> str | None:
    """Never choose an arbitrary native class for the original singular field."""
    distinct = sorted(set(groups))
    if len(distinct) > 1:
        raise AmbiguousGroups(
            f"Glyph {name!r} belongs to multiple {side} groups: {', '.join(distinct)}. "
            "A same-group proof needs one group per side. No tab was opened."
        )
    return distinct[0] if distinct else None


def _read(selection: Any, deadline: float) -> tuple[GlyphGroups, ...]:
    """Read all native FG names/IDs and each uniquely defined side membership."""
    _check(deadline)
    package = selection.package
    font = _native("fontlab").CurrentFont()
    if font is None or int(font.id) != int(package.fgId):
        raise ValueError("The source font changed while reading kerning groups.")
    pair_left, pair_right, _ = kerning_class_lists(package, selection.context[1])
    current_left = _group(
        pair_right.get(selection.glyph_name, []), selection.glyph_name, "left"
    )
    current_right = _group(
        pair_left.get(selection.glyph_name, []), selection.glyph_name, "right"
    )
    if not (current_left or current_right):
        return (GlyphGroups(selection.glyph_id, selection.glyph_name, None, None),)
    rows = []
    for glyph in font.glyphs:
        _check(deadline)
        name = glyph.name
        if not isinstance(name, str) or not name:
            raise ValueError("A source glyph name is missing or invalid.")
        rows.append(
            GlyphGroups(
                int(glyph.id),
                name,
                _group(pair_right.get(name, []), name, "left")
                if current_left
                else None,
                _group(pair_left.get(name, []), name, "right")
                if current_right
                else None,
            )
        )
    _check(deadline)
    return tuple(rows)


def capture(deadline: float) -> Snapshot:
    """Fence first selected identity, complete font order and both group maps."""
    _check(deadline)
    if current_package() is None:
        raise NoSelectedGlyph("Open a font and select a glyph first.")
    first = first_selection(deadline)
    if first is None:
        raise NoSelectedGlyph("No glyph currently selected.")
    rows = _read(first, deadline)
    second = first_selection(deadline)
    if second is None or first != second or rows != _read(second, deadline):
        raise ValueError(
            "The selected glyph, font order or kerning groups changed; run again."
        )
    current_id = first.glyph_id
    if not any(g.ident == current_id and g.name == first.glyph_name for g in rows):
        raise ValueError("The selected glyph is missing or changed in the source font.")
    _check(deadline)
    return Snapshot(first.context[0], first.context[1], current_id, rows, first)


def open_proof(source: Snapshot, proof: Proof, deadline: float) -> None:
    """Build literal labels/separators and explicit peer names before tab creation."""
    _check(deadline)
    native = _native("fontlab")
    symbols = []

    def add(value: str | int) -> None:
        _check(deadline)
        symbol = native.fgSymbol(value)
        symbol.layerName = source.master
        symbols.append(symbol)

    for index, (prefix, names) in enumerate(proof.rows):
        if index:
            add(10)
        for char in prefix:
            add(ord(char))
        for position, name in enumerate(names):
            if position:
                add(32)
            add(name)
    _check(deadline)
    named._open_symbols(
        native, native.fgSymbolList(symbols), source.package_id, source.master, deadline
    )


def diagnose(title: str, message: str) -> None:
    """Use App's owned message-box cleanup for the original diagnosis branch."""
    from fontlabapp.qt.dialogs import create_message_box, run_owned_dialog

    qt = _native("PythonQt")
    gui = qt.QtGui
    box = create_message_box(
        gui, title, message, "Information", (_native("fontlab").MainWindow(),)
    )

    def configure(current: Any) -> None:
        current.setWindowFlags(current.windowFlags() | qt.QtCore.Qt.WindowStaysOnTopHint)
        current.setWindowTitle(title)
        current.setStandardButtons(gui.QMessageBox.Ok)

    run_owned_dialog(box, configure, lambda current, result: None)
