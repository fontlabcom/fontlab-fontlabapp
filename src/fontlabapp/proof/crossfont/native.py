# this_file: src/fontlabapp/proof/crossfont/native.py
# SPDX-License-Identifier: Apache-2.0
"""Checked registered-font reads, without activation or the mutating fgGlyph getter.

AllFonts supplies original open-font order. Canonical FontGate glyph names/path
are read directly; flPackage.master is the stored key-layer getter (flpackage.cpp
18416). Only the two composite participants resolve selected-master own shapes.
Native complete-font note/lib/date/history preservation still needs qualification.
"""
from time import monotonic
from math import isfinite
from typing import Any
from fontlabapp import _native
from fontlabapp.anchors.duplicates.capture import check, require_main_thread
from fontlabapp.proof.crossfont.model import Font, Glyph, Snapshot

def _read(composites: bool, deadline: float) -> Snapshot:
    check(deadline)
    native = _native("fontlab")
    current = native.CurrentFont()
    if current is None:
        raise ValueError("Open a current reference font and at least one other font.")
    current_id = int(current.id)
    opened = []
    for font in native.AllFonts():
        check(deadline)
        opened.append(font)
    ids = tuple(int(font.id) for font in opened)
    if current_id not in ids or (composites and len(ids) < 2) or len(set(ids)) != len(ids):
        raise ValueError("Open font identities changed or no other font is open.")
    participants = {current_id, next(i for i in ids if i != current_id)} if composites else set()
    packages = {}
    if composites:
        for item in native.flWorkspace.instance().packages():
            check(deadline)
            package = native.flPackage(item)
            identifier = int(package.fgId)
            if identifier in packages:
                raise ValueError("Duplicate open font registration.")
            packages[identifier] = package
    rows = []
    for font, identifier in zip(opened, ids, strict=True):
        check(deadline)
        if composites and identifier not in participants:
            rows.append(Font(identifier, None, "", ()))
            continue
        package, master = None, ""
        if composites:
            package = packages.get(identifier)
            if package is None or package.isNull:
                raise ValueError("A comparison font is not registered in the workspace.")
            master = str(package.master)
            if master not in tuple(str(m) for m in package.masters):
                raise ValueError("The selected master cannot be resolved without changing the font.")
        glyphs = []
        for canonical in font.glyphs:
            check(deadline)
            name = str(canonical.name)
            bases = []
            if composites:
                glyph = package.findName(name)
                if glyph is None or glyph.isNull:
                    raise ValueError("A comparison glyph disappeared.")
                layer = glyph.findLayer(master)
                if layer is None or layer.isNull:
                    raise ValueError("A comparison glyph has no selected-master layer.")
                for shape in layer.shapes:
                    check(deadline)
                    if shape.isComponent:
                        bases.append(str(shape.shapeData.componentGlyph))
            glyphs.append(Glyph(name, tuple(bases)))
        rows.append(Font(identifier, None if composites else (str(font.path) or None), master, tuple(glyphs)))
    check(deadline)
    return Snapshot(current_id, tuple(rows))

def capture(*, composites: bool = False, deadline: float | None = None) -> Snapshot:
    """Publish only two identical complete reads within one absolute deadline."""
    require_main_thread()
    deadline = monotonic() + 3.5 if deadline is None else deadline
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not isfinite(deadline):
        raise ValueError("A finite absolute report deadline is required.")
    before = _read(composites, deadline)
    if _read(composites, deadline) != before:
        raise ValueError("Comparison source changed during capture; refresh.")
    check(deadline)
    return before
