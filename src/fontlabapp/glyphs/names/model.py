# this_file: src/fontlabapp/glyphs/names/model.py
# SPDX-License-Identifier: Apache-2.0
"""Whole-font snapshot, refusals and one-Undo commit for the Names editors.

What: the Names editors (Batch Rename, Suffix Tool, Unicode From Names, Glyph
Notes, Batch Glyph Notes, Glyph Tags, Mark Color Palette) share one model:

- ``scan()`` reads every glyph of the current font into ``Facts``: one
  ``Entry`` per glyph (FontGate record plus FontLab glyph) and the auto-layer
  facts of the whole font (``history.AutoFacts``).
- ``refusal``/``editable`` say which glyphs an operation may edit.
- ``fresh_facts`` scans again just before a write, refuses a switched font
  and leaves pre-write disclosure to ``commit``.
- ``commit`` runs the edit as ONE Undo step through ``history.commit``.

How: ``scan`` maps each font-owned record through ``package.findFgId`` and
checks name and id both ways. It never reads ``flGlyph.fgGlyph``: on build
9784 that getter can clear a fresh note mirror. ``Facts`` is never patched; a
stale snapshot is scanned again.

Why the refusals (``history.refusal``): FontLab rebuilds every auto layer when
an auto layer or a base of an auto composite is notified, and Undo does not
restore the result (after ``e`` was renamed, ``ecircumflex`` became a lone
``ee``). Use ``operation="rename"`` or ``"unicode"`` for names and code
points, ``"metadata"`` for notes, tags and mark colours (these refuse only
glyphs that own an auto layer).

How to use::

    import fly.ap.glyphs.names.model as names_edit

    facts = names_edit.fresh_facts(package_id)
    ok, refused = names_edit.editable(facts, names, "rename")
    names_edit.commit("Batch Rename", [facts.entries[n] for n in ok],
                      lambda: rename(ok), operation="rename", facts=facts)

The module imports only the standard library at load time. Offline tests do
not prove native Undo/Redo/reopen behaviour.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from fontlabapp import _native
from fontlabapp.core.history.glyphs import (
    AutoFacts,
    Committed,
    Operation,
    auto_facts,
    commit as one_step,
    refusal as policy,
)


@dataclass(frozen=True)
class Entry:
    """One glyph: ``record`` is the FontGate glyph, ``glyph`` the FontLab glyph.

    Rename and Unicode writes go to ``record`` (the font-owned FontGate glyph);
    history calls go to ``glyph`` and its layers.
    """

    name: str
    record: Any
    glyph: Any


@dataclass(frozen=True)
class Facts:
    """Whole-font snapshot. Never patched: scan again when it is stale.

    ``entries``: glyph name -> ``Entry`` in font order. ``autos``: the
    auto-layer facts of every layer (``history.AutoFacts``).
    """

    package: Any
    package_id: int
    entries: dict[str, Entry]
    autos: AutoFacts


def scan(native: Any = None) -> Facts:
    """Read every glyph and every layer dependency of the current font.

    ``native`` is the ``fontlab`` module (default: the native one). Raise
    ``ValueError("Open a font first.")`` with no font and ``ValueError`` when
    a record and its FontLab glyph disagree on name or id.
    """
    module = _native("fontlab") if native is None else native
    package = module.flWorkspace.instance().currentPackage
    font = module.CurrentFont()
    if package is None or package.isNull or font is None:
        raise ValueError("Open a font first.")
    entries: dict[str, Entry] = {}
    records: list[tuple[str, bool, tuple[str, ...]]] = []
    for record in font.glyphs:
        name = str(record.name)
        glyph = package.findFgId(int(record.id))
        if (
            glyph is None
            or glyph.isNull
            or glyph.name != record.name
            or int(glyph.fgGlyphId) != int(record.id)
        ):
            raise ValueError("Native glyph mapping is inconsistent; reload the font.")
        entries[name] = Entry(name, record, glyph)
        for layer in glyph.layers:
            bases = tuple(
                str(shape.shapeData.componentGlyph)
                for shape in layer.shapes
                if shape.isComponent
            )
            records.append((name, bool(layer.autoLayer), bases))
    return Facts(package, int(package.id), entries, auto_facts(records))


def refusal(facts: Facts, name: str, operation: str) -> str:
    """Return why ``operation`` must not edit glyph ``name``, or ``""``.

    Texts, checked in this order: ``"not in font"``, ``"has no layers"``, then
    the ``history.refusal`` policy (``"has auto layers"``, ``"base of auto
    X, Y…"``). An unknown operation raises ``ValueError``.
    """
    entry = facts.entries.get(name)
    if entry is None:
        return "not in font"
    if not tuple(entry.glyph.layers):
        return "has no layers"
    return policy(facts.autos, name, operation)


def editable(
    facts: Facts, names: Iterable[str], operation: str
) -> tuple[list[str], dict[str, str]]:
    """Split ``names`` into (names that may be edited, {refused name: reason})."""
    allowed: list[str] = []
    refused: dict[str, str] = {}
    for name in names:
        reason = refusal(facts, name, operation)
        if reason:
            refused[name] = reason
        else:
            allowed.append(name)
    return allowed, refused


def fresh_facts(package_id: int, *, native: Any = None) -> Facts:
    """Scan again just before a write. Refuse a switched font; disclose queued updates.

    ``package_id`` is the id from the scan that the preview showed. Raise
    ``ValueError`` when the current font is another one. ``commit`` reads the
    queue immediately before writing and reports its ids and note.
    """
    module = _native("fontlab") if native is None else native
    facts = scan(module)
    if facts.package_id != package_id:
        raise ValueError("The scanned font is no longer current; reload.")
    return facts


def commit(
    title: str,
    entries: list[Entry],
    mutate: Callable[[], Iterable[Any] | None],
    *,
    operation: Operation,
    facts: Facts,
    read_back: Callable[[], Iterable[str]] | None = None,
    window: int | None = None,
    native: Any = None,
    stamp: Any = None,
) -> Committed:
    """Run ``mutate`` as ONE Undo step over ``entries`` (``history.commit``).

    Every layer of every entry glyph and the glyphs themselves get
    ``checkInitHistoryState(0)`` and go into the one notification (layers
    first, then glyphs). ``facts`` comes from ``fresh_facts``. For Unicode
    writes pass ``window=facts.package_id``: the Font-window and no-editor
    guards then run first. Refusals raise ``ValueError`` before any history
    call; later failures raise ``history.PartialWriteError``.
    """
    glyphs = [entry.glyph for entry in entries]
    layers = [layer for glyph in glyphs for layer in glyph.layers]
    return one_step(
        title,
        layers,
        glyphs,
        mutate,
        operation=operation,
        facts=facts.autos,
        read_back=read_back,
        window=window,
        native=native,
        stamp=stamp,
    )


__all__ = [
    "Entry",
    "Facts",
    "commit",
    "editable",
    "fresh_facts",
    "refusal",
    "scan",
]
