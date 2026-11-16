# this_file: src/fontlabapp/masters/layers/compatibility/_records.py
# SPDX-License-Identifier: MIT
"""Read exact ordered native node types/name sets without geometry writers.

FontLab cubic controls are Curve, quadratic controls Off; Glyphs names both
OFFCURVE. An on-curve endpoint uses its predecessor and contour.isTT. Closed
paths rotate the native start to the final slot, matching the existing bridge.
Actual imported topology/read preservation remains a native acceptance gate.
"""

from time import monotonic
from typing import Any

from fontlabapp.masters.layers.compatibility.model import Layer


def check(deadline: float) -> None:
    """Bound Python steps; a native getter itself cannot be preempted."""
    if monotonic() >= deadline:
        raise TimeoutError("Layer compatibility scan expired; no partial report.")


def nodes(contour: Any, deadline: float) -> tuple:
    """Return Glyphs-ordered type names and raw identity/role fences."""
    closed, quadratic = contour.closed, contour.isTT
    if type(closed) is not bool or type(quadratic) is not bool:
        raise ValueError("Unreadable native contour topology.")
    raw = []
    for node in contour.nodes():
        check(deadline)
        if node.isNull:
            raise ValueError("A contour has a null node.")
        flags = (node.isOn(), node.isOff(), node.isCurve())
        if any(type(v) is not bool for v in flags) or sum(flags) != 1:
            raise ValueError("A contour has an unknown or ambiguous node type.")
        raw.append((int(node.id), flags))
    types = []
    for i, (_, flags) in enumerate(raw):
        check(deadline)
        previous = raw[i - 1][1] if i or closed else (False, False, False)
        kind = "line"
        if not flags[0]:
            kind = "offcurve"
        elif previous[1] or previous[2]:
            kind = "curve" if previous[2] and not quadratic else "qcurve"
        types.append(kind)
    if closed and types:
        types = types[1:] + types[:1]
    check(deadline)
    return tuple(types), (int(contour.id), closed, quadratic, tuple(raw))


def layer(value: Any, deadline: float) -> tuple:
    """Read own ordered paths plus component/anchor names; never decompose."""
    paths, shapes, bases = [], [], set()
    for shape in value.shapes:
        check(deadline)
        component = shape.isComponent
        if type(component) is not bool:
            raise ValueError("Unreadable native shape role.")
        if component:
            base = shape.shapeData.componentGlyph
            if not isinstance(base, str):
                raise ValueError("A component has no readable base name.")
            bases.add(base)
            state = base
        else:
            if shape.isComposite:
                raise ValueError("Generated shapes need native topology qualification.")
            contours = []
            for contour in shape.contours:
                check(deadline)
                kinds, state = nodes(contour, deadline)
                paths.append(kinds)
                contours.append(state)
            state = tuple(contours)
        shapes.append((int(shape.id), component, state))
    anchors, pins = set(), []
    for pin in value.anchors:
        check(deadline)
        name = pin.name
        if not isinstance(name, str):
            raise TypeError("An anchor has no readable name.")
        anchors.add(name)
        pins.append((int(pin.id), name))
    check(deadline)
    return Layer(str(value.name), tuple(paths), frozenset(anchors), frozenset(bases)), (
        tuple(shapes),
        tuple(pins),
    )
