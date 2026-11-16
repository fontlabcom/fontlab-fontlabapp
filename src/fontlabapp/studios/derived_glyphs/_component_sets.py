# this_file: src/fontlabapp/studios/derived_glyphs/_component_sets.py
# SPDX-License-Identifier: Apache-2.0
"""One component-set writer for Default figures and Unicase (Scriptmix TODO:84).

``Scripts/Components/Set Default Figures.py`` and ``Make Lower Unicase.py``
carried identical copies of ``group_plan``, ``validate_pairs``, ``prepare``
and ``component_rows``, and the same writer body (``write_components`` in
Set Default Figures, ``apply_pairs`` in Make Lower Unicase, which differs
only in its ``replace_contours=True`` default). This module holds them once,
verbatim from Set Default Figures (the tests compare every function with
both originals by AST).

The writer validates every pair before any change (plain base layer per
master, unlocked target layers, no auto target or base of an auto glyph,
no circular component), creates missing targets with FontLab's Add Glyph
(each its own step, through ``glyph_creation.create_glyphs``), then
replaces the targets' components (and, only when asked, contours and
anchors), copies advances and kerning-class memberships in ONE
``history.commit`` step titled ``title``, and reads every layer back.
With ``replace_contours=False`` the target's own contours stay (the
figures-default repair, Scriptmix TODO:16).
"""

from __future__ import annotations

from typing import Any

import fontlabapp.core.edit_guards as edit_guards
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from . import _shared

#: The module names the verbatim originals import.
component_creation = _shared.Modules("component_creation")
writer = _shared.Modules("components")
glyph_copies = _shared.Modules("copies")
glyph_creation = _shared.Modules("creation")
TITLE = "Set Default Figures"

Pair = tuple[str, str]  # target, base


def group_plan(package: Any, pairs: list[Pair]) -> dict[str, dict[str, Any]]:
    """Give targets the same per-side class memberships as their bases."""
    desired = {}
    for master in package.masters:
        groups = {}
        for name, (members, mode) in package.kerning(master).groups.items():
            original = list(members)
            if mode not in {"KernLeft", "KernRight", "KernBothSide"}:
                continue
            new = [member for member in original if member not in {t for t, _ in pairs}]
            new.extend(
                target
                for target, base in pairs
                if base in original and target not in new
            )
            if new != original:
                groups[str(name)] = (new, mode)
        desired[str(master)] = groups
    return desired


def validate_pairs(
    package: Any,
    pairs: list[Pair],
    *,
    facts: history.AutoFacts | None = None,
    allow_rebuild: bool = False,
) -> None:
    """Check masters, layer locks, automatic owners and component cycles."""
    if not package.masters:
        raise ValueError("The font needs at least one master.")
    if not pairs:
        raise ValueError("No matching glyphs. Check the font and figure names.")
    facts = history.scan_auto_facts(package) if facts is None else facts
    for target, base in pairs:
        why = history.refusal(facts, target, "geometry", allow_bases=allow_rebuild)
        if why:
            raise ValueError(f"{target}: {why}.")
        for master in package.masters:
            source = package.findName(base)
            layer = source.findLayer(master) if source is not None else None
            if layer is None or layer.isNull or layer.autoLayer:
                raise ValueError(f"{base}: needs a plain layer for {master}.")
            glyph = package.findName(target)
            old = glyph.findLayer(master) if glyph is not None else None
            if old is not None and not old.isNull and old.isLocked:
                raise ValueError(f"{target} · {master}: layer is locked.")
        # A new base must not reach the target through existing components.
        todo, seen = [base], set()
        while todo:
            name = todo.pop()
            if name == target:
                raise ValueError(f"{target}: the new component would be circular.")
            if name in seen:
                continue
            seen.add(name)
            glyph = package.findName(name)
            if glyph is not None:
                todo.extend(
                    writer.base_of(s)
                    for layer in glyph.layers
                    for s in writer.components(layer)
                )


def prepare(
    package: Any, pairs: list[Pair], *, allow_rebuild: bool = False
) -> list[tuple[str, str, Any, float]]:
    """Build detached components through the App before the outline commit."""
    facts = history.scan_auto_facts(package)
    validate_pairs(package, pairs, facts=facts, allow_rebuild=allow_rebuild)
    result = []
    for target, base in pairs:
        wanted = [
            component_creation.NewComponent(base, str(m)) for m in package.masters
        ]
        components = component_creation.build_components(package, target, wanted, facts)
        for master, component in zip(package.masters, components, strict=True):
            layer = package.findName(base).findLayer(master)
            result.append((target, str(master), component, float(layer.advanceWidth)))
    return result


def component_rows(
    package: Any, rows: list[glyph_copies.Row], *, allow_rebuild: bool = False
) -> list[glyph_copies.Row]:
    """List per-target refusals without discarding other eligible targets."""
    facts = history.scan_auto_facts(package)
    candidates = glyph_creation.auto_candidates(
        package,
        facts,
        [r.target for r in rows if r.target and package.findName(r.target) is None],
    )
    existing = any(not r.note and package.findName(r.target) is not None for r in rows)
    safe = component_creation.prototype(package, facts) if existing else None
    result = []
    for row in rows:
        note = row.note
        rebuild = candidates.get(row.target, ())
        if not note:
            try:
                validate_pairs(
                    package,
                    [(row.target, row.source)],
                    facts=facts,
                    allow_rebuild=allow_rebuild,
                )
                if package.findName(row.target) is not None:
                    if safe is None:
                        note = f"{row.target}: kept; {component_creation.NO_PROTOTYPE}."
                elif rebuild and not allow_rebuild:
                    note = f"{row.target}: kept; {glyph_creation.rebuild_note(rebuild)}"
            except ValueError as error:
                note = f"{row.target}: kept; {error}"
        result.append(
            glyph_copies.Row(row.source, row.target, note=note, rebuild=rebuild)
        )
    return result


def write_components(
    package: Any,
    pairs: list[Pair],
    *,
    title: str = TITLE,
    replace_contours: bool = False,
    clear_anchors: bool = True,
    allow_rebuild: bool = False,
    unicodes: dict[str, tuple[int, ...]] | None = None,
    kept: list[str] | None = None,
    report: list[str] | None = None,
    disclosure: dict[str, Any] | None = None,
) -> int:
    """Replace target components, widths and class memberships in one history batch."""
    ids = edit_guards.pending_updates()
    captured = {"pending_updates": ids, "pending_note": edit_guards.pending_note(ids)}
    edit_guards.disclose(captured, disclosure if disclosure is not None else {})
    if report is not None and ids and disclosure is None:
        report.append(captured["pending_note"])
    elif disclosure is None and report is None:
        edit_guards.disclose(captured)
    facts = history.scan_auto_facts(package)
    rows = component_rows(
        package,
        [glyph_copies.Row(base, target) for target, base in pairs],
        allow_rebuild=allow_rebuild,
    )
    if kept is not None:
        kept.extend(row.note for row in rows if row.note)
    pairs = [(r.target, r.source) for r in rows if not r.note]
    existing = [(t, b) for t, b in pairs if package.findName(t) is not None]
    steps = prepare(package, existing, allow_rebuild=allow_rebuild) if existing else []
    specs = [
        glyph_creation.NewGlyph(
            target,
            tuple(
                (str(m), float(package.findName(base).findLayer(m).advanceWidth))
                for m in package.masters
            ),
            (unicodes or {}).get(target, ()),
            components=tuple(
                glyph_creation.Part(str(m), base) for m in package.masters
            ),
        )
        for target, base in pairs
        if package.findName(target) is None
    ]
    groups = group_plan(package, pairs)
    created = glyph_creation.create_glyphs(
        package, specs, title, facts, allow_rebuild=allow_rebuild
    )
    names = [str(glyph.name) for glyph in created.glyphs]
    created_text = "new glyphs that exist now: " + ", ".join(names) if names else ""
    diagnostics = list(created.mismatches)
    if report is not None:
        report.extend(([created_text] if created_text else []) + diagnostics)
    if diagnostics and not allow_rebuild:
        raise RuntimeError("; ".join([*diagnostics, created_text, history.UNDO_HINT]))
    if not steps and not any(groups.values()):
        return len(specs) * len(package.masters)
    if steps:
        edited = list(dict.fromkeys(target for target, _, _, _ in steps))
        glyphs = [package.findName(target) for target in edited]
        layers = [
            package.findName(target).findLayer(master) for target, master, _, _ in steps
        ]
        layers = [layer for layer in layers if layer is not None and not layer.isNull]
    else:
        memberships = [
            (target, master)
            for target, _ in pairs
            for master, changes in groups.items()
            if any(
                (target in package.kerning(master).groups[name][0])
                != (target in value[0])
                for name, value in changes.items()
            )
        ]
        edited = list(dict.fromkeys(target for target, _ in memberships))
        glyphs = [package.findName(target) for target in edited]
        layers = [
            package.findName(target).findLayer(master) for target, master in memberships
        ]
        layers = [layer for layer in layers if layer is not None and not layer.isNull]
    retain = [
        item
        for layer in layers
        for shape in writer.components(layer)
        for item in history.component_history(shape)
    ]
    container = package.kerningContainer()
    retain.extend([package, package.mastersContainer(), container])
    made, written = [], []

    def mutate() -> list[Any]:
        package.checkInitHistoryState(0)
        container.checkInitHistoryState(0)
        for target, master, component, width in steps:
            glyph = package.findName(target)
            if glyph is None:
                raise ValueError(f"{target}: target changed; Preview again.")
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                layer = glyph.findLayerCreate(master)
                made.append(layer)
            if replace_contours:
                for shape in list(layer.shapes):
                    if shape.isComponent or bool(shape.contours):
                        layer.removeShape(shape)
                if clear_anchors:
                    layer.clearAnchors()
            else:
                for shape in list(writer.components(layer)):
                    layer.removeShape(shape)
            component = component_creation.add_component(layer, component)
            writer.refreshed(component)
            layer.advanceWidth = width
            layer.changed()
            if layer.update() is False:
                raise RuntimeError(f"FontLab could not update {target} · {master}.")
            written.append((layer, component, width))
        for master, changes in groups.items():
            for name, value in changes.items():
                package.kerning(master).groups[name] = value
        return made

    def read_back() -> list[str]:
        missed = [
            str(layer.name)
            for layer, component, width in written
            if component not in layer.shapes or layer.advanceWidth != width
        ]
        for master, changes in groups.items():
            now = dict(package.kerning(master).groups.items())
            missed.extend(
                f"{master}: class {name}"
                for name, value in changes.items()
                if name not in now or (list(now[name][0]), now[name][1]) != value
            )
        return missed

    try:
        result = history.commit(
            title,
            layers,
            glyphs,
            mutate,
            operation="geometry" if steps else "metadata",
            facts=history.scan_auto_facts(package),
            allow_bases=allow_rebuild,
            retain=retain,
            read_back=read_back,
        )
    except (ValueError, RuntimeError, TimeoutError) as error:
        if names:
            raise history.PartialWriteError(
                title,
                [
                    error,
                    RuntimeError(created_text),
                    *(RuntimeError(text) for text in diagnostics),
                ],
            ) from error
        raise
    if result.mismatches:
        raise RuntimeError(
            "; ".join(
                [*diagnostics, *result.mismatches, created_text, history.UNDO_HINT]
            )
        )
    return len(steps) + len(specs) * len(package.masters)


__all__ = [
    "Pair",
    "component_rows",
    "group_plan",
    "prepare",
    "validate_pairs",
    "write_components",
]
