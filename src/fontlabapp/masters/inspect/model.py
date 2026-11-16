# this_file: src/fontlabapp/masters/inspect/model.py
# SPDX-License-Identifier: Apache-2.0
"""Shared read-only native master reads and original twelve-step area calculations.

Imports remain host-free. Native access is lazy; no glyph FontGate getter,
font/history notification or stored-data write is used by these reports.
"""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from fontlabapp import _native
from fontlabapp.core.scripting import names_font_glyphs, names_selected_names

STEPS = 12
METRICS = [
    ("Ascender", "ascender"),
    ("Cap height", "capsHeight"),
    ("x-height", "xHeight"),
    ("Descender", "descender"),
]
selected_names = names_selected_names


def muted(widget: Any, alpha: int = 150) -> str:
    """Copy the original active theme color before changing its alpha."""
    QtGui = _native("PythonQt").QtGui
    color = QtGui.QColor(
        widget.palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText)
    )
    color.setAlpha(alpha)
    return color.name(QtGui.QColor.HexArgb)


def all_names() -> list[str]:
    """Read font order from the already available FontGate font, never flGlyph.fgGlyph."""
    return [name for (name, _) in names_font_glyphs()]


def location_text(package: Any, master: str) -> str:
    """Format axes in font order, displaying ? for unavailable location coordinates."""
    location = package.location(master)
    parts = []
    for axis in package.axes:
        try:
            parts.append(f"{axis.tag} {location[axis.shortName]:g}")
        except Exception:  # noqa: BLE001 - original unavailable-axis fallback
            parts.append(f"{axis.tag} ?")
    return ", ".join(parts) or "–"


def italic_angles(package: Any, masters: list[str]) -> dict[str, float]:
    """{master: italic angle}; switches the current master briefly and always restores it."""
    (current, angles) = (package.master, {})
    try:
        for master in masters:
            if package.master != master:
                package.setMaster(master)
            angles[master] = float(package.italicAngle_value)
    finally:
        if package.master != current:
            package.setMaster(current)
    return angles


def overview(package: Any) -> list[tuple[str, str, float, float, float, float, float]]:
    """[(master, location, ascender, cap height, x-height, descender, italic angle)]."""
    masters = list(package.masters)
    angles = italic_angles(package, masters)
    rows = []
    for master in masters:
        metrics = _native("fontlab").FontMetrics(package, master)
        rows.append(
            (
                master,
                location_text(package, master),
                *tuple(float(getattr(metrics, attr)) for (_, attr) in METRICS),
                angles[master],
            )
        )
    return rows


def master_layers(glyph: Any, masters: list[str]) -> dict[str, Any]:
    """{master: flLayer} for the masters present in this glyph."""
    found = {}
    for master in masters:
        layer = glyph.findLayer(master)
        if layer is not None and (not layer.isNull):
            found[master] = layer
    return found


def associated_master(name: str, masters: Sequence[str]) -> str | None:
    """Return the master that a layer name belongs to, or None.

    What: drop a leading ``|temp|``, cut at the first ``@`` (else the first
    ``#``) and return the rest when it is one of ``masters``. So
    ``"Regular@ 2026-10-21"`` and ``"Regular#bracket"`` belong to
    ``"Regular"``; ``"mask.Regular"`` and ``"Light Copy"`` belong to none.

    Why: this is FontLab's own rule (``flLayer::isMasterLayerName``,
    fllayer.cpp:10346-10375, which then calls ``package.hasMaster``). Scripts
    that step through, copy or promote layers use it to find the master of a
    backup or a bracket layer. Pure string work; it reads no font.
    """
    base = name.removeprefix("|temp|")
    cut = base.find("@")
    if cut < 0:
        cut = base.find("#")
    head = base if cut < 0 else base[:cut]
    return head if head and head in masters else None


def widths(glyph: Any, masters: list[str]) -> list[tuple[str, float | None]]:
    """[(master, advance width or None)] in the given master order."""
    found = master_layers(glyph, masters)
    return [(m, float(found[m].advanceWidth) if m in found else None) for m in masters]


def master_order(package: Any) -> list[str]:
    """Masters sorted by their location on the first axis (font order when there is no axis)."""
    masters = list(package.masters)
    axes = list(package.axes)
    if not axes:
        return masters
    key = axes[0].shortName

    def position(master: str) -> float:
        """Keep original zero-position fallback for an unavailable axis coordinate."""
        try:
            return float(package.location(master)[key])
        except Exception:  # noqa: BLE001 - original unavailable-axis fallback
            return 0.0

    return sorted(masters, key=position)


def nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """Cover both endpoints with nice ticks, retaining a nonzero constant-range axis."""
    import math

    if not all(math.isfinite(v) for v in (low, high)) or count <= 0 or high < low:
        raise ValueError(
            "Chart ranges must be finite, ordered and use positive tick counts."
        )
    span = max(high - low, 1e-09, math.ulp(max(abs(low), abs(high))) * count)
    if not math.isfinite(span):
        raise ValueError("Chart range is too large for finite ticks.")
    raw = span / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = min(
        (m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw), default=raw
    )
    start = math.floor(low / step) * step
    if start > low:
        start -= step
    (ticks, value) = ([], start)
    for _ in range(count + 3):
        ticks.append(value)
        if value >= high and len(ticks) > 1:
            break
        value += step
    return ticks


def label_tops(ys: list[float], height: float) -> list[float]:
    """Tops of value labels for points sorted top to bottom: above the point, or below it when the
    label above would collide with the previous one, pushed further down if still crowded.
    """
    (tops, last_point) = ([], None)
    for y in ys:
        top = y - height - 4
        if tops and (top < tops[-1] + height or y - last_point < height + 14):
            top = max(y + 6, tops[-1] + height)
        tops.append(top)
        last_point = y
    return tops


def spread(ys: list[float], gap: float) -> list[float]:
    """Sorted label positions pushed apart so neighbours are at least gap apart."""
    out = []
    for y in ys:
        out.append(y if not out else max(y, out[-1] + gap))
    return out


def node_points(contour: Any) -> list[tuple[float, float, bool]]:
    """Read contour coordinates and on/handle flags in original node order."""
    return [(node.x, node.y, bool(node.isOn())) for node in contour.nodes()]


def polygon(points: list[tuple[float, float, bool]]) -> list[tuple[float, float]]:
    """Flatten [(x, y, on)] of a closed contour: cubic for two handles, polyline otherwise."""
    if not points:
        return []
    start = next((i for (i, p) in enumerate(points) if p[2]), 0)
    pts = points[start:] + points[:start]
    (poly, handles, current) = ([pts[0][:2]], [], pts[0][:2])
    for x, y, on in pts[1:] + pts[:1]:
        if not on:
            handles.append((x, y))
            continue
        if len(handles) == 2:
            ((ax, ay), (bx, by), (cx, cy), (dx, dy)) = (
                current,
                handles[0],
                handles[1],
                (x, y),
            )
            for i in range(1, STEPS + 1):
                t = i / STEPS
                u = 1 - t
                poly.append(
                    (
                        u**3 * ax + 3 * u * u * t * bx + 3 * u * t * t * cx + t**3 * dx,
                        u**3 * ay + 3 * u * u * t * by + 3 * u * t * t * cy + t**3 * dy,
                    )
                )
        else:
            poly.extend(handles)
            poly.append((x, y))
        (current, handles) = ((x, y), [])
    poly.extend(handles)
    return poly


def inside(point: tuple[float, float], poly: list[tuple[float, float]]) -> bool:
    """Use ray crossings to determine counter nesting independently of winding."""
    (x, y) = point
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=False):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def ink_area(contours: list[list[tuple[float, float, bool]]]) -> float:
    """Filled area of contours [(x, y, on)]: + for even nesting depth, - for odd (counters)."""
    polys = [polygon(points) for points in contours]
    total = 0.0
    for i, poly in enumerate(polys):
        if len(poly) < 3:
            continue
        area = (
            abs(
                sum(
                    a[0] * b[1] - b[0] * a[1]
                    for (a, b) in zip(poly, poly[1:] + poly[:1], strict=False)
                )
            )
            / 2.0
        )
        depth = sum(
            1
            for (j, other) in enumerate(polys)
            if j != i and len(other) > 2 and inside(poly[0], other)
        )
        total += area if depth % 2 == 0 else -area
    return total


def layer_contours(layer: Any) -> list[list[tuple[float, float, bool]]]:
    """Own and component contours, components placed by their transforms."""
    QtCore = _native("PythonQt").QtCore
    result = []
    for shape in layer.shapes:
        transform = shape.transform
        for contour in shape.contours:
            points = node_points(contour)
            if not transform.isIdentity():
                points = [
                    (p.x(), p.y(), on)
                    for (x, y, on) in points
                    for p in [transform.map(QtCore.QPointF(x, y))]
                ]
            result.append(points)
    return result


def own_contours(layer: Any) -> list[Any]:
    """Contours drawn in this layer; layer.getContours() also lists the contours of components."""
    return [
        contour
        for shape in layer.shapes
        if not shape.isComponent
        for contour in shape.contours
    ]


def signature(layer: Any) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Comparable structure of a layer: contour node patterns, anchor names, component bases."""
    contours = tuple(
        "".join("o" if on else "h" for (_, _, on) in node_points(c))
        for c in own_contours(layer)
    )
    anchors = tuple(sorted(a.name for a in layer.anchors))
    components = tuple(
        shape.shapeData.componentGlyph
        if hasattr(shape.shapeData, "componentGlyph")
        else shape.name
        for shape in layer.shapes
        if shape.isComponent
    )
    return (contours, anchors, components)


def summary(sig: Any) -> tuple[int, int, int, int]:
    """Return displayed contour, node, anchor and component counts for a signature."""
    (contours, anchors, components) = sig
    return (len(contours), sum(len(c) for c in contours), len(anchors), len(components))


def check_glyph(
    glyph: Any, masters: list[str]
) -> tuple[dict[str, Any], bool, list[str]]:
    """({master: signature or None for auto layers}, ok, [differing aspects])."""
    sigs = {
        m: None if l.autoLayer else signature(l)
        for (m, l) in master_layers(glyph, masters).items()
    }
    real = [s for s in sigs.values() if s is not None]
    problems = []
    for index, aspect in enumerate(("contours", "anchors", "components")):
        if len({s[index] for s in real}) > 1:
            problems.append(aspect)
    if len(sigs) < len(masters):
        problems.append("missing layer")
    return (sigs, not problems, problems)



#: Timestamp used in the backup suffix field. Pass a local datetime to default_suffix.
STAMP_FORMAT = "%H:%M:%S, %d/%m/%y"


def default_suffix(now: datetime) -> str:
    """Format ``now`` for the backup suffix field, with seconds and a short date.

    Pass the local time, for example ``default_suffix(datetime.now().astimezone())``.
    Read no clock here so callers can use the same time for a whole batch.
    """
    return now.strftime(STAMP_FORMAT)


def backup_master(name: str, masters: Sequence[str]) -> str | None:
    """Return the master of a plain or legacy backup layer, or None.

    Refuse names equal to any master (casefold), and names with # or |temp|
    anywhere. For legacy @ names, match the part before @. Otherwise use the
    longest master plus a space prefix. Prefix matches use exact case, as the
    layer tools always did: ``regular sketch`` is not a backup of Regular,
    and with masters Bold and BOLD, ``BOLD backup x`` belongs to BOLD. With
    Bold and Bold Italic, ``Bold Italic backup x`` belongs to Bold Italic;
    Bold Italic itself is never a backup. Use this rule for display, cleanup
    and restore tools.
    """
    if "#" in name or "|temp|" in name or name.casefold() in {m.casefold() for m in masters}:
        return None
    if "@" in name:
        prefix = name.split("@", 1)[0]
        return prefix if prefix in masters else None
    return next(
        (m for m in sorted(masters, key=len, reverse=True) if name.startswith(m + " ")),
        None,
    )


def is_backup_layer(name: str, master: str, masters: Sequence[str]) -> bool:
    """Return True if ``backup_master(name, masters)`` is exactly ``master``.

    Pass all font masters to exclude master layers and resolve overlapping
    names. Example: ``is_backup_layer("Bold backup x", "Bold", ["Bold"])`` is True.
    """
    return backup_master(name, masters) == master


def backup_layer_name(base: str, taken: Iterable[str], suffix: str, masters: Sequence[str]) -> str:
    """Return a unique ``<base> backup <suffix>`` name, or raise ValueError.

    Strip the suffix and refuse an empty value. Append (2), (3) and so on
    for case-insensitive collisions in ``taken``. Refuse @, # or |temp|
    anywhere in the candidate, a master name (casefold), or a name that does
    not resolve exactly to ``base``. These checks keep
    the backup out of special layer roles and prevent a restore to the wrong
    master. Example: ``backup_layer_name("Bold", names, "trial", masters)``.
    """
    if not suffix.strip():
        raise ValueError("Enter a backup suffix.")
    candidate = f"{base} backup {suffix.strip()}"
    if "@" in candidate or "#" in candidate or "|temp|" in candidate.casefold():
        raise ValueError("Backup names must not contain @, # or |temp|.")
    used = {name.casefold() for name in taken}
    name, number = candidate, 2
    while name.casefold() in used:
        name = f"{candidate} ({number})"
        number += 1
    if name.casefold() in {master.casefold() for master in masters}:
        raise ValueError(f"Backup '{name}' is a font master name; choose another suffix.")
    resolved = backup_master(name, masters)
    if resolved != base:
        raise ValueError(f"Backup '{name}' would read as master {resolved!r}, not {base!r}; choose another suffix.")
    return name
