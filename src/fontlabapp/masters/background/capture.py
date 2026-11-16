# this_file: src/fontlabapp/masters/background/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Immutable background domain facts, retaining actual native owners separately."""

from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from fontlabapp.masters.background.records import check, layer_record, selection_record


@dataclass
class Target:
    glyph: Any
    foreground: Any
    mask: Any
    record: tuple | None
    repeat: int = 1
    visible: bool = field(init=False)
    active: Any = field(init=False)

    def __post_init__(self):
        self.visible = bool(self.foreground.isVisible)
        self.active = self.glyph.activeLayer


@dataclass
class Capture:
    mode: str
    selection: Any
    targets: tuple
    fingerprint: tuple
    source: Any


def read(backend: Any, mode: str) -> Capture:
    if backend.poisoned:
        raise RuntimeError(
            "Background adapter retains a failed edit; review its native history first."
        )
    if mode not in ("scale", "shift", "replace"):
        raise ValueError("Unknown background operation.")
    deadline = monotonic() + 4
    selection = backend._selection(mode, deadline)
    if not selection.occurrences:
        if mode == "replace":
            raise ValueError("Select a foreground glyph layer first.")
        return Capture(mode, selection, (), (mode, selection.context, "empty"), None)
    first = selection.occurrences[0]
    package = first.package
    native = backend.native("fontlab")
    current = native.flWorkspace.instance().currentPackage
    if (
        current is None
        or int(current.id) != int(package.id)
        or str(current.master) != str(selection.context[1])
    ):
        raise ValueError("The selected font is no longer current.")
    font = native.CurrentFont()
    if font is None or int(font.id) != int(package.fgId):
        raise ValueError("The current FontGate carrier changed.")
    requests = [
        (o.glyph, o.layer)
        for o in (
            selection.occurrences[:1] if mode == "replace" else selection.occurrences
        )
    ]
    domain = []
    if mode == "replace":
        for row in font.glyphs:
            check(deadline)
            glyph = package.findName(row.name)
            if glyph is None:
                raise ValueError("A font glyph disappeared during background capture.")
            foreground = glyph.findLayer(selection.context[1])
            if foreground is None or foreground.isNull:
                raise ValueError(
                    f"Glyph {row.name!r} has no selected-master foreground layer; restore that layer before replacing every background."
                )
            domain.append((str(row.name), int(glyph.id), int(foreground.id)))
            requests.append((glyph, foreground))
    targets = []
    keys = {}
    for glyph, foreground in requests:
        check(deadline)
        if foreground.isMaskLayer:
            raise ValueError("Select foreground layers, not native mask layers.")
        mask = foreground.getMaskLayer(False)
        if mask is not None and not mask.isValid:
            mask = None
        if mask is not None and (int(mask.glyph.id) != int(glyph.id) or mask.autoLayer):
            raise ValueError(
                "Background ownership is missing or automatic; use an owned manual background."
            )
        if (
            mask is not None
            and mode == "replace"
            and (
                mask.tthProgram
                or mask.ttData.hasHints()
                or any(g.isHint for g in mask.guidelines)
            )
        ):
            raise ValueError(
                "Replacing native hinted backgrounds needs a qualified hint-preservation route."
            )
        key = (
            int(glyph.id),
            int(mask.id) if mask is not None else int(foreground.id),
        )
        if key in keys:
            if mode != "replace":
                keys[key].repeat += 1
            continue
        target = Target(
            glyph,
            foreground,
            mask,
            layer_record(mask, deadline, components=mode != "scale"),
        )
        targets.append(target)
        keys[key] = target
    source = first.layer
    source_record = selection_record(source, deadline) if mode == "replace" else ()
    facts = tuple(
        (
            int(t.glyph.id),
            int(t.foreground.id),
            tuple(int(l.id) for l in t.glyph.layers),
            int(t.glyph.currentHistoryState()),
            t.visible,
            int(t.active.id),
            t.record,
            t.repeat,
        )
        for t in targets
    )
    occurrences = tuple(
        (int(o.glyph.id), int(o.layer.id), int(o.block_id), int(o.index))
        for o in (
            selection.occurrences[:1] if mode == "replace" else selection.occurrences
        )
    )
    check(deadline)
    return Capture(
        mode,
        selection,
        tuple(targets),
        (mode, selection.context, occurrences, tuple(domain), facts, source_record),
        source,
    )
