# this_file: src/fontlabapp/contours/near_miss/native.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Read all selected parents' first layers and explicit associated-master JSON.

Package stem getters use the active key master; FontMetrics silently falls back
for unknown names. Avoid both. The established get_font_info read serializes
named fontMaster records, fontStemsH/V and zero-omitted metrics. Never call a
master/selection/font writer. Native serialization/getter preservation is pending.
"""

import re
from time import monotonic
from typing import Any

import fontlabapp.masters.layers.selection as selection
import fontlabapp.contours.near_miss.model as report
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native


def _parents(deadline: float) -> tuple:
    """Capture every selected parent without resolving its selected layer."""
    selection._check(deadline)
    document = selection._document(deadline)
    package, glyphs = document.package, []
    if document.context[2] == "font":
        names = selection.names_font_window_selection(
            expected_fg_id=int(package.fgId), deadline=deadline
        )
        for name in names:
            selection._check(deadline)
            glyphs.append(package.findName(name))
    else:
        for block in document.blocks:
            selection._check(deadline)
            for index in range(int(block.glyphsCount())):
                selection._check(deadline)
                info = block.getGlyphAt(index)
                if info is not None and (info.isSelected or info.isActive):
                    glyphs.append(info.glyph)
    identities = []
    for glyph in glyphs:
        selection._check(deadline)
        if glyph is None or glyph.isNull or int(glyph.package.id) != int(package.id):
            raise ValueError("A selected glyph is missing or belongs to another font.")
        identities.append((int(glyph.id), int(glyph.fgGlyphId), str(glyph.name)))
    return (
        document.context,
        package,
        tuple(glyphs),
        tuple(identities),
        document.carriers,
    )


def _master(data: dict, layer: str) -> tuple:
    """Resolve native name association explicitly; never fall back to key master."""
    name = re.split(r"[:#@]", layer, maxsplit=1)[0]
    masters = data.get("masters")
    if not isinstance(masters, (list, tuple)):
        raise TypeError("Unreadable native master domain.")
    matches = [
        entry.get("fontMaster")
        for entry in masters
        if isinstance(entry, dict)
        and isinstance(entry.get("fontMaster"), dict)
        and entry["fontMaster"].get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError("The first layer has no unique associated named master.")
    master = matches[0]
    metrics = tuple(
        report.number(master.get(key, 0))
        for key in ("ascender", "capsHeight", "xHeight", "descender")
    )
    stems = []
    for key in ("fontStemsH", "fontStemsV"):
        values = master.get(key, [])
        if not isinstance(values, (list, tuple)) or any(not isinstance(v, dict) for v in values):
            raise ValueError("Unreadable associated-master stem list.")
        stems.append(tuple(report.number(v.get("value", 0)) for v in values))
    return name, metrics, *stems


def _paths(layer: Any, deadline: float) -> tuple:
    """Map own nodes to layer coordinates and preserve Glyphs closed-node order."""
    paths, states = [], []
    for shape in layer.shapes:
        selection._check(deadline)
        if type(shape.isComponent) is not bool:
            raise ValueError("Unreadable shape role.")
        if shape.isComponent:
            states.append((int(shape.id), "component"))
            continue
        if shape.isComposite:
            raise ValueError(
                "Generated shape geometry is unsupported; no partial report."
            )
        transform = shape.transform
        matrix = tuple(
            report.number(getattr(transform, f"m{i}{j}")())
            for i in (1, 2, 3)
            for j in (1, 2, 3)
        )
        if (matrix[2], matrix[5], matrix[8]) != (0, 0, 1):
            raise ValueError("Projective shape transform is unsupported.")
        states.append((int(shape.id), matrix))
        for contour in shape.contours:
            selection._check(deadline)
            if type(contour.closed) is not bool or type(contour.isTT) is not bool:
                raise ValueError("Unreadable native contour topology.")
            nodes, identities = [], []
            for node in contour.nodes():
                selection._check(deadline)
                if node.isNull:
                    raise ValueError("A contour contains a null node.")
                flags = (node.isOn(), node.isOff(), node.isCurve())
                if any(type(v) is not bool for v in flags) or sum(flags) != 1:
                    raise ValueError("Unreadable native node role.")
                point = transform.map(node.position)
                nodes.append(
                    report.Node(
                        (report.number(point.x()), report.number(point.y())),
                        not flags[0],
                    )
                )
                identities.append((int(node.id), flags))
            if contour.isTT and any(node.off for node in nodes):
                raise ValueError(
                    "Quadratic TrueType controls are unsupported; no partial report."
                )
            if contour.closed and nodes:
                nodes = nodes[1:] + nodes[:1]
            paths.append(tuple(nodes))
            states.append(
                (int(contour.id), contour.closed, contour.isTT, tuple(identities))
            )
    return tuple(paths), tuple(states)


def _read(selected: tuple, deadline: float) -> tuple:
    """Read literal layer zero for each occurrence, never later layer attributes."""
    _context, package, glyphs, identities, _ = selected
    data = _native("fontpr").call("get_font_info", font_id=scripting.font_id(package))
    if not isinstance(data, dict):
        raise TypeError("Unreadable native font info.")
    rows, states = [], []
    for glyph, identity in zip(glyphs, identities):
        selection._check(deadline)
        layers = glyph.layers
        if not layers:
            raise ValueError("A selected glyph has no first layer.")
        layer = layers[0]
        if (
            layer is None
            or layer.isNull
            or not layer.isValid
            or int(layer.glyph.id) != identity[0]
        ):
            raise ValueError("A selected glyph has no valid owned first layer.")
        master, metrics, horizontal, vertical = _master(data, str(layer.name))
        paths, path_ids = _paths(layer, deadline)
        rows.append(
            report.Glyph(
                identity[2],
                str(layer.name),
                master,
                metrics,
                horizontal,
                vertical,
                paths,
            )
        )
        states.append((identity, int(layer.id), path_ids))
    selection._check(deadline)
    result = tuple(rows)
    report.findings(result, deadline)
    return result, tuple(states)


def capture() -> tuple[report.Glyph, ...]:
    """Fence all selection, required first-layer geometry and master values twice.

    Python checkpoints bound two seconds; native calls are not preemptible.
    No partial result or active-master substitution is returned on any failure.
    """
    deadline = monotonic() + 2.0
    first = _parents(deadline)
    if not first[2]:
        raise ValueError("Select glyphs before running Close But No Cigar.")
    rows = _read(first, deadline)
    second = _parents(deadline)
    repeated = _read(second, deadline)
    final = _parents(deadline)
    context = selection.document_context(deadline)
    selection._check(deadline)
    if (
        (first[0], first[3]) != (second[0], second[3])
        or (second[0], second[3]) != (final[0], final[3])
        or rows != repeated
        or final[0] != context
    ):
        raise ValueError(
            "Font, selection, first layers, masters or geometry changed; refresh."
        )
    return rows[0]
