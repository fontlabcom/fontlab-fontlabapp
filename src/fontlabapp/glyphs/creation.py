# this_file: src/fontlabapp/glyphs/creation.py
# SPDX-License-Identifier: Apache-2.0
"""Create new glyphs through FontLab's own Add Glyph command, then fill them in one step.

What: the Contours creator scripts (Placeholder Glyphs, Small Caps From
Capitals, Superior & Inferior Figures, Tabular Figure Copies) make new
glyphs. ``create_glyphs`` does it in this order:

1. Refuse before any change (``ValueError``): a name listed twice, a name
   that exists now, a name that can make FontLab rebuild an automatic glyph
   (``auto_candidates``) without the user's consent, a Glyph window as the
   active canvas (``edit_guards.require_history_scope``, FontLab issue 8573:
   measured on 9790, Undo stays disabled for the new glyphs and their
   outlines there). Read queued native glyph updates for disclosure
   (FontLab issue 8537); never clear them.
2. Read the signature of every automatic layer (``auto_signatures``).
3. For each new glyph, call the fontpr tool ``set_glyph(create=True)`` with
   the name, one layer per master with its advance width, the code
   points and optional components (``NewGlyph.components``, ``Part``;
   ``glyph_data``). The components are checked after the call. FontLab runs its undoable Add Glyph command
   (``commAddGlyph``) for it.
4. Optionally ``fill`` the new layers in ONE
   ``history.commit(..., operation="geometry")`` that declares the new
   layers and glyphs.
5. Read back: the caller's ``read_back`` texts, then one text per automatic
   layer whose signature changed (``auto_changes``).

User text for the Undo shape: ``UNDO_TEXT`` ("Each new glyph is recorded as
its own Undo step, and the outlines as one more Undo step."). This module
makes no claim about what Undo restores.

Why: ``flPackage.addGlyph`` is a raw insert. It runs no command and records
no history (source: ``flpackage.cpp:18526-18532``), and it skips
``ensureComplete``. ``set_glyph`` creates the glyph the way FontLab's own
tools do (source: ``mcptools_source.cpp:144-172``); the command runs
synchronously and clears the queued glyph updates
(``flhistorycontroller.cpp:1818-1914``). Glyport creates glyphs the same
way. This module never calls ``addGlyph`` and never writes a FontGate
record.

The Add Glyph command re-resolves the default-recipe automatic composites
of the font (``commAddGlyph::updateAutoGlyphs``, fl#8512). FontLab gives no
Python call that predicts a default recipe, so ``auto_candidates`` is a
conservative guess: automatic layers without an own recipe whose glyph name
shares a dotted suffix segment with the new name (a new ``e.sc`` can change
``eacute.sc``). The script lists them ("may rebuild auto eacute.sc") and
creates such a glyph only after the user ticks ``REBUILD_LABEL``. The
after-write check (``auto_changes``) stays. Automatic layers are never
notified.

This module imports only the standard library and stdlib-only App modules
at load time; ``fontpr`` loads when ``create_glyphs`` runs. Offline tests
prove the call order, not native Undo/Redo.

How to use (a script)::

    import fly.ap.glyphs.creation as glyph_creation

    specs = [glyph_creation.NewGlyph("h.sc", (("Regular", 450),))]
    done = glyph_creation.create_glyphs(package, specs, "Small Caps", facts, fill=fill)
"""

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NamedTuple

import fontlabapp.core.edit_guards as edit_guards  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native

#: Label of the consent tick for names that can make FontLab rebuild automatic glyphs.
REBUILD_LABEL = "Create even if FontLab may rebuild these auto glyphs"
#: The Undo sentence for scripts that create glyphs and then fill their outlines.
UNDO_TEXT = "Each new glyph is recorded as its own Undo step, and the outlines as one more Undo step."
#: The Undo sentence when no outlines are filled (``fill=None``; components only).
CREATE_UNDO_TEXT = "Each new glyph is recorded as its own Undo step."
#: Automatic glyph names shown in one preview note before "…".
SHOWN_CANDIDATES = 2
#: One automatic layer: (glyph name, layer name).
LayerKey = tuple[str, str]


@dataclass(frozen=True)
class Part:
    """One component of a new glyph: master (layer) name, base glyph name, offset x and y.

    The base glyph must exist before ``create_glyphs`` runs and have a
    layer of that name. The component is a plain translation.
    """

    master: str
    base: str
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class NewGlyph:
    """One glyph to create: name, (master, advance width) per master, code points, components.

    ``components`` go into the same ``set_glyph(create=True)`` data, so the
    glyph and its components are ONE Add Glyph Undo step. No component
    constructor is measured on this FontLab build (fl#8505); this is the
    native path for the first component of a NEW glyph, also in a font
    without components.
    """

    name: str
    layers: tuple[tuple[str, int], ...]
    unicodes: tuple[int, ...] = ()
    components: tuple[Part, ...] = ()


class Created(NamedTuple):
    """New glyphs, read-back texts, and ids/note captured before the first creation.

    The outer result never attributes ids queued by its own creation to the
    earlier state. The fill commit independently captures its own pre-write queue.
    """

    glyphs: tuple[Any, ...]
    mismatches: tuple[str, ...]
    pending_updates: tuple[int, ...] = ()
    pending_note: str = ""

    def __getitem__(self, key: int | slice | str) -> Any:
        """Allow named disclosure fields and legacy tuple indexing."""
        return getattr(self, key) if isinstance(key, str) else tuple.__getitem__(self, key)


def glyph_data(spec: NewGlyph) -> dict[str, Any]:
    """Return the fontpr ``glyph_data`` JSON for ``spec``: name, layers, code points.

    Each layer is ``{"name": master, "advanceWidth": width}``. A layer with
    components also has ``"elements"``: one ``{"component": {"glyphName":
    base}, "transform": {"xOffset": x, "yOffset": y}}`` per ``Part``, in
    order (the VFJ tags ``glyphName``, ``xOffset``, ``yOffset`` of
    ``bin_types.cpp:543,570-571``; the form Glyport measured). ``unicodes``
    is present only when the glyph gets code points.
    """
    layers = []
    for master, width in spec.layers:
        layer: dict[str, Any] = {"name": master, "advanceWidth": width}
        elements = [
            {
                "component": {"glyphName": part.base},
                "transform": {"xOffset": float(part.x), "yOffset": float(part.y)},
            }
            for part in spec.components
            if part.master == master
        ]
        if elements:
            layer["elements"] = elements
        layers.append(layer)
    data: dict[str, Any] = {"name": spec.name, "layers": layers}
    if spec.unicodes:
        data["unicodes"] = list(spec.unicodes)
    return data


def undo_text(filled: bool) -> str:
    """Return ``UNDO_TEXT`` when the script fills outlines, else ``CREATE_UNDO_TEXT``."""
    return UNDO_TEXT if filled else CREATE_UNDO_TEXT


def segments(name: str) -> frozenset[str]:
    """Return the dotted suffix segments of a glyph name: h.sc.ss01 -> {sc, ss01}."""
    return frozenset(part for part in name.split(".")[1:] if part)


def auto_candidates(
    package: Any, facts: history.AutoFacts, names: Iterable[str]
) -> dict[str, tuple[str, ...]]:
    """Map each new name to the automatic glyphs that FontLab may rebuild when it appears.

    A candidate owns a layer with ``autoLayer`` and no own ``recipe`` (a
    default-recipe automatic layer), and its name shares a whole dotted
    suffix segment with the new name (``e.sc`` and ``eacute.sc``; not
    ``x.scale``). A new name without a dot gets no candidates. Names without
    candidates are left out. Only the owners in ``facts.autos`` are read.

    Scope: this is a pre-write HEURISTIC for
    the consent tick, not a prediction. Adding ANY glyph re-resolves every
    automatic layer of the font: Add Glyph passes every glyph id to
    ``_process_update_auto_layers`` (``flhistorycontroller.cpp:1910-1921``)
    and ``UpdatePackageData::updateAutoLayers`` walks every auto layer
    (``update_components.cpp:716-790``). So any new name, dotted or not
    (``acute`` and ``Aacute``), can change any default-recipe automatic
    glyph. The guard is the after-write ``auto_changes`` check. This is a
    reading of the source, not a measurement.
    """
    owners = []
    for owner in sorted(facts.autos):
        glyph = package.findName(owner)
        if glyph is not None and any(
            x.autoLayer and not x.recipe for x in glyph.layers
        ):
            owners.append(owner)
    found = {}
    for name in names:
        wanted = segments(name)
        hits = tuple(
            owner for owner in owners if owner != name and wanted & segments(owner)
        )
        if hits:
            found[name] = hits
    return found


def rebuild_note(candidates: Sequence[str]) -> str:
    """Return the preview note: "may rebuild auto eacute.sc, aacute.sc…"."""
    shown = ", ".join(candidates[:SHOWN_CANDIDATES])
    return f"may rebuild auto {shown}" + (
        "…" if len(candidates) > SHOWN_CANDIDATES else ""
    )


def layer_signature(layer: Any) -> tuple[Any, ...]:
    """Return the component bases and transforms, anchors and width of ``layer``."""
    parts = []
    for shape in layer.shapes:
        if shape.isComponent:
            t = shape.transform
            parts.append(
                (
                    str(shape.shapeData.componentGlyph),
                    t.m11(),
                    t.m12(),
                    t.m21(),
                    t.m22(),
                    t.dx(),
                    t.dy(),
                )
            )
    anchors = tuple((str(a.name), a.point.x(), a.point.y()) for a in layer.anchors)
    return tuple(parts), anchors, float(layer.advanceWidth)


def auto_signatures(
    package: Any, facts: history.AutoFacts
) -> dict[LayerKey, tuple[Any, ...]]:
    """Return the signature of every automatic layer of the font, before the write.

    FontLab resolves automatic composites by name; a new glyph name can
    change how one resolves. ``auto_changes`` compares these signatures.
    """
    found = {}
    for name in sorted(facts.autos):
        glyph = package.findName(name)
        for layer in glyph.layers if glyph is not None else ():
            if layer.autoLayer:
                found[name, str(layer.name)] = layer_signature(layer)
    return found


def auto_changes(package: Any, before: Mapping[LayerKey, tuple[Any, ...]]) -> list[str]:
    """Return one text per automatic layer whose signature changed or that is gone."""
    changed = []
    for (name, layer_name), signature in before.items():
        glyph = package.findName(name)
        layer = glyph.findLayer(layer_name) if glyph is not None else None
        if layer is None or layer.isNull or layer_signature(layer) != signature:
            changed.append(
                f"Auto glyph {name} · {layer_name} changed after the write; "
                "FontLab rebuilt it. Check it."
            )
    return changed


def _refuse_parts(package: Any, spec: NewGlyph) -> None:
    """Raise ``ValueError`` for a component of ``spec`` that FontLab cannot resolve now."""
    masters = {master for master, _ in spec.layers}
    for part in spec.components:
        where = f"{spec.name} · {part.master}"
        if part.master not in masters:
            raise ValueError(f"Refused: {where}: no such new layer.")
        if not all(
            isinstance(v, (int, float)) and math.isfinite(v) for v in (part.x, part.y)
        ):
            raise ValueError(
                f"Refused: {where}: the component offset must be finite numbers."
            )
        base = (
            package.findName(part.base)
            if part.base and part.base != spec.name
            else None
        )
        layer = None if base is None or base.isNull else base.findLayer(part.master)
        if layer is None or layer.isNull:
            raise ValueError(
                f"Refused: {where}: no base glyph {part.base} with that layer."
            )


def _check_parts(glyph: Any, spec: NewGlyph) -> None:
    """Raise ``RuntimeError`` unless every new layer holds the planned component bases, in order."""
    for master, _ in spec.layers:
        wanted = [part.base for part in spec.components if part.master == master]
        if not wanted:
            continue
        layer = glyph.findLayer(master)
        found = [
            str(s.shapeData.componentGlyph)
            for s in (layer.shapes if layer is not None else ())
            if s.isComponent
        ]
        if found != wanted:
            raise RuntimeError(
                f"FontLab did not add the components of {spec.name} · {master}."
            )


def _refuse(
    package: Any,
    specs: Sequence[NewGlyph],
    facts: history.AutoFacts,
    allow_rebuild: bool,
) -> None:
    """Raise ``ValueError`` for a repeated or existing name or an unconsented candidate."""
    seen: set[str] = set()
    for spec in specs:
        if spec.name in seen:
            raise ValueError(f"Refused: {spec.name} is listed twice.")
        seen.add(spec.name)
        if package.findName(spec.name) is not None:
            raise ValueError(f"Refused: {spec.name} exists now. Check the list again.")
        _refuse_parts(package, spec)
    found = (
        {}
        if allow_rebuild
        else auto_candidates(package, facts, [spec.name for spec in specs])
    )
    if found:
        name, owners = next(iter(found.items()))
        raise ValueError(
            f'Refused: {name} {rebuild_note(owners)}. Tick "{REBUILD_LABEL}" to create it.'
        )


def _partial(
    title: str, error: Exception, made: Sequence[Any]
) -> history.PartialWriteError:
    """Return the error for a failure after the first glyph exists; it names the new glyphs.

    A ``PartialWriteError`` from ``history.commit`` gives its own errors,
    so the text is not nested.
    """
    errors: list[Exception] = (
        list(error.errors) if isinstance(error, history.PartialWriteError) else [error]
    )
    if made:
        errors.append(
            RuntimeError(
                "new glyphs that exist now: " + ", ".join(str(g.name) for g in made)
            )
        )
    return history.PartialWriteError(title, errors)


class _NotRun(RuntimeError):
    """FontLab refused one ``set_glyph`` before its Add Glyph command ran."""


def _add(package: Any, spec: NewGlyph) -> Any:
    """Create one glyph with fontpr ``set_glyph(create=True)`` and return the NEW package glyph.

    For an existing name ``set_glyph(create=True)`` does not refuse: it
    replaces that glyph's layers (``mcptools_source.cpp:89-90,144-163``).
    So the name is checked again just before the call, and the result must
    say ``"created": true``. A refusal before the command ran (the name
    exists, a ``fontpr.Error``, an error status) raises ``_NotRun``.
    """
    if package.findName(spec.name) is not None:
        raise _NotRun(f"{spec.name} exists now; FontLab would replace its layers.")
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - lazy: cold import stays stdlib-only

    fontpr = _native("fontpr")
    refused = getattr(fontpr, "Error", None)
    try:
        result = fontpr.call(
            "set_glyph",
            font_id=scripting.font_id(package),
            glyph_name=spec.name,
            create=True,
            glyph_data=glyph_data(spec),
        )
    except Exception as error:
        if isinstance(refused, type) and isinstance(error, refused):
            raise _NotRun(str(error) or type(error).__name__) from error
        raise
    if isinstance(result, dict) and result.get("status", "ok") != "ok":
        raise _NotRun(str(result.get("error") or result))
    if not isinstance(result, dict) or result.get("created") is not True:
        raise RuntimeError(f"FontLab did not report a new glyph {spec.name}.")
    glyph = package.findName(spec.name)
    if glyph is None or glyph.isNull:
        raise RuntimeError(f"FontLab did not add the glyph {spec.name}.")
    return glyph


def create_glyphs(
    package: Any,
    specs: Sequence[NewGlyph],
    title: str,
    facts: history.AutoFacts,
    *,
    fill: Callable[[dict[str, Any]], None] | None = None,
    read_back: Callable[[], Iterable[str]] | None = None,
    allow_rebuild: bool = False,
) -> Created:
    """Create every glyph of ``specs``, then optionally fill them in ONE Undo step.

    ``facts``: a fresh ``history.scan_auto_facts(package)``. ``fill(glyphs)``
    gets ``{name: new package glyph}`` and edits the new master layers (find
    them with ``glyph.findLayer(master)``); it runs inside one
    ``history.commit(title, layers, glyphs, ..., operation="geometry")`` that
    declares every new layer and glyph. ``read_back()`` returns one text per
    mismatch with the plan. ``allow_rebuild``: the user ticked
    ``REBUILD_LABEL``; it also goes to the commit as ``allow_bases``.

    Raise ``ValueError`` before any change for a refusal (module text, step
    1). When FontLab refuses the FIRST glyph before its command runs, raise
    ``RuntimeError`` ("... did not start ... No glyph was added.") without
    the Undo hint. Every other failure raises ``history.PartialWriteError``
    (with ``history.UNDO_HINT``); after the first glyph exists its text
    names the new glyphs. Nothing
    to create returns ``Created((), ())`` with no native call.
    """
    if not specs:
        return Created((), ())
    _refuse(package, specs, facts, allow_rebuild)
    edit_guards.require_history_scope((), creates=True)
    ids = edit_guards.pending_updates()
    before = auto_signatures(package, facts)
    made: list[Any] = []
    for spec in specs:
        try:
            glyph = _add(package, spec)
        except _NotRun as error:
            if made:
                raise _partial(title, error, made) from error
            raise RuntimeError(
                f"{title} did not start: {error} No glyph was added."
            ) from error
        except Exception as error:
            raise _partial(title, error, made) from error
        made.append(glyph)  # it exists now: every later failure names it
        try:
            _check_parts(glyph, spec)
        except Exception as error:
            raise _partial(title, error, made) from error
    layers = []
    for spec, glyph in zip(specs, made, strict=True):
        for master, _ in spec.layers:
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                raise _partial(
                    title, RuntimeError(f"{spec.name} has no layer {master}"), made
                )
            layers.append(layer)

    def check() -> list[str]:
        return [
            *(read_back() if read_back is not None else ()),
            *auto_changes(package, before),
        ]

    if fill is None:
        try:
            return Created(tuple(made), tuple(check()), ids, edit_guards.pending_note(ids))
        except Exception as error:
            raise _partial(title, error, made) from error
    named = {spec.name: glyph for spec, glyph in zip(specs, made, strict=True)}
    try:
        done = history.commit(
            title, layers, made, lambda: fill(named),
            operation="geometry", facts=facts, allow_bases=allow_rebuild, read_back=check,
        )  # fmt: skip
    except history.PartialWriteError as error:  # add the names of the new glyphs
        raise _partial(title, error, made) from error
    except Exception as error:  # the glyphs exist; the outlines may be missing
        raise _partial(title, error, made) from error
    return Created(tuple(made), done.mismatches, ids, edit_guards.pending_note(ids))


__all__ = [
    "CREATE_UNDO_TEXT",
    "REBUILD_LABEL",
    "SHOWN_CANDIDATES",
    "UNDO_TEXT",
    "Created",
    "LayerKey",
    "NewGlyph",
    "Part",
    "auto_candidates",
    "auto_changes",
    "auto_signatures",
    "create_glyphs",
    "glyph_data",
    "layer_signature",
    "rebuild_note",
    "segments",
    "undo_text",
]
