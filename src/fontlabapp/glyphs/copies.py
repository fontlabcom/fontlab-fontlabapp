# this_file: src/fontlabapp/glyphs/copies.py
# SPDX-License-Identifier: Apache-2.0
"""Shared kernel of the scripts that make new glyphs from copies of existing ones.

What: Small Caps From Capitals, Superior & Inferior Figures and Tabular
Figure Copies plan one new glyph per selected source glyph and copy its
contours, transformed, into every master. This module holds the parts that
were byte-identical in the three scripts:

- ``survey_with`` plans one ``Row`` per selected name with the script's
  ``naming`` rule. It lists and skips a repeated target, a missing source, a
  target that exists, a source layer that cannot be copied
  (``source_problem``) and, without the user's consent, a target that can
  make FontLab rebuild automatic glyphs (``Row.rebuild``).
- ``create`` makes the planned glyphs through
  ``fontlabapp.glyphs.creation.create_glyphs``: each glyph with its master
  widths, then all contours in one Undo step, then a read-back.
- ``panel_type()`` returns ``CopiesPanel``, the shared panel of the three
  scripts (a ``fontlabapp.contours.selection.panel.model`` panel with a source table and
  the rebuild consent tick).

How: a job is ``(new name, [(master, contours, advance)])``; the script's
``prepare`` builds it with ``fontlabapp.contours.copy.copy_contours``.
Undo: ``glyph_creation.UNDO_TEXT``.

This module imports only the standard library and stdlib-only App modules
at load time; PythonQt loads in ``panel_type()`` and ``fontlab`` in
``create``. Offline tests do not prove native Undo/Redo.

How to use (a script)::

    import fly.ap.glyphs.copies as glyph_copies

    rows = glyph_copies.survey_with(package, names, naming, facts, allow_rebuild)
    result = glyph_copies.create(package, jobs, "Small Caps", facts, allow_rebuild=True)
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import fontlabapp.contours.copy as contour_copy  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.glyphs.creation as glyph_creation  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native

#: One new glyph: (new name, [(master, contours, advance width)]).
Job = tuple[str, list[tuple[str, list[Any], int]]]
#: ``naming(source name) -> (new name, problem)``; a problem skips the row.
Naming = Callable[[str], tuple[str, str]]


@dataclass(frozen=True)
class Row:
    """One selected glyph and its planned copy.

    ``layers``: (master, source layer) per master. ``note`` set: skipped.
    ``rebuild``: automatic glyphs that FontLab may rebuild when ``target``
    appears (``glyph_creation.auto_candidates``).
    """

    source: str
    target: str
    layers: tuple[tuple[str, Any], ...] = ()
    note: str = ""
    rebuild: tuple[str, ...] = ()


def half_up(value: float) -> int:
    """Round half up (250.5 -> 251), as the other metrics scripts do."""
    return math.floor(value + 0.5)


def _valid(layer: Any) -> bool:
    """True for a real native layer object."""
    return layer is not None and not layer.isNull


def source_problem(layer: Any) -> str:
    """Return why a source master layer cannot be copied, or ""."""
    if not _valid(layer):
        return "no layer"
    if layer.autoLayer:
        return "auto layer"
    if any(shape.isComponent for shape in layer.shapes):
        return "built from components"
    if not contour_copy.contour_shapes(layer):
        return "no outline"
    return ""


def survey_with(
    package: Any,
    names: Sequence[str],
    naming: Naming,
    facts: history.AutoFacts,
    allow_rebuild: bool = False,
) -> list[Row]:
    """Plan one new glyph per selected name. Change nothing.

    A target that can make FontLab rebuild automatic glyphs gets
    ``rebuild``; without ``allow_rebuild`` its note is
    ``glyph_creation.rebuild_note(...)`` and the row is skipped.
    """
    rows: list[Row] = []
    seen: set[str] = set()
    for name in names:
        target, problem = naming(name)
        if problem:
            rows.append(Row(name, "", note=problem))
            continue
        if target in seen:
            rows.append(Row(name, target, note="repeated"))
            continue
        seen.add(target)
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            rows.append(Row(name, target, note="not in font"))
            continue
        if package.findName(target) is not None:
            rows.append(Row(name, target, note=f"{target} exists"))
            continue
        layers = tuple((m, glyph.findLayer(m)) for m in package.masters)
        bad = next(
            ((m, source_problem(x)) for m, x in layers if source_problem(x)), None
        )
        rows.append(
            Row(name, target, note=f"{bad[0]}: {bad[1]}")
            if bad
            else Row(name, target, layers)
        )
    ready = [row.target for row in rows if not row.note]
    found = glyph_creation.auto_candidates(package, facts, ready)
    for index, row in enumerate(rows):
        owners = found.get(row.target, ()) if not row.note else ()
        if owners:
            note = "" if allow_rebuild else glyph_creation.rebuild_note(owners)
            rows[index] = Row(row.source, row.target, row.layers, note, owners)
    return rows


def create(
    package: Any,
    jobs: Sequence[Job],
    title: str,
    facts: history.AutoFacts,
    *,
    allow_rebuild: bool = False,
) -> dict[str, Any]:
    """Create every planned glyph, then add all contours as ONE Undo step.

    Return ``{"glyphs", "layers", "mismatches"}``. Nothing to do returns
    zeros and makes no native call. A target that exists now, an
    unconsented rebuild candidate raises
    ``ValueError`` before any change; a failure after the first glyph exists
    raises ``history.PartialWriteError``. See ``glyph_creation.create_glyphs``.
    """
    if not jobs:
        return {"pending_updates": (), "pending_note": "", "glyphs": 0, "layers": 0, "mismatches": []}
    specs = [
        glyph_creation.NewGlyph(target, tuple((m, advance) for m, _, advance in layers))
        for target, layers in jobs
    ]

    def fill(glyphs: dict[str, Any]) -> None:
        fontlab = _native("fontlab")
        for target, layers in jobs:
            for master, contours, _ in layers:
                shape = fontlab.flShape()
                shape.addContours(list(contours), True)
                glyphs[target].findLayer(master).addShape(shape)

    def read_back() -> list[str]:
        found = []
        for target, layers in jobs:
            glyph = package.findName(target)
            for master, contours, advance in layers:
                layer = glyph.findLayer(master) if glyph is not None else None
                ok = _valid(layer)
                count = (
                    sum(len(s.contours) for s in contour_copy.contour_shapes(layer))
                    if ok
                    else 0
                )
                width = half_up(layer.advanceWidth) if ok else 0
                if (count, width) != (len(contours), advance):
                    found.append(
                        f"{target} · {master}: {count} contours, width {width}; planned {len(contours)}, {advance}"
                    )
        return found

    done = glyph_creation.create_glyphs(
        package,
        specs,
        title,
        facts,
        fill=fill,
        read_back=read_back,
        allow_rebuild=allow_rebuild,
    )
    return {"pending_note": done.pending_note, 
        "glyphs": len(jobs),
        "layers": sum(len(layers) for _, layers in jobs),
        "mismatches": list(done.mismatches),
        "pending_updates": done.pending_updates,
    }


def panel_type() -> type:
    """Return the ``CopiesPanel`` base class (a PythonQt ``QDialog``).

    Call it inside FontLab only. Subclass it, set ``TITLE``, ``KEY`` and
    ``NOUN`` ("capitals", "figures"), and fill in ``build_controls``,
    ``survey(package, facts, allow_rebuild)`` and ``jobs(rows)``. See
    ``fontlabapp.contours.selection.panel.ui.CopiesPanel``.
    """
    from fontlabapp.contours.selection.panel.ui import CopiesPanel

    return CopiesPanel


__all__ = [
    "Job",
    "Naming",
    "Row",
    "create",
    "half_up",
    "panel_type",
    "source_problem",
    "survey_with",
]
