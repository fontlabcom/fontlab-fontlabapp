# this_file: src/fontlabapp/plugins/filters/apply.py
"""Commit contour deletions or positional coordinate edits through App history."""

from dataclasses import dataclass, replace
from importlib import import_module
from math import isfinite
from typing import Any

from fontlabapp import _native
from fontlabapp.contours import writer as outline_writer
from fontlabapp.plugins import snapshot
from fontlabapp.plugins.filter import Filter, LayerEdit

# FontLab round-trips QPointF through float math; read-back x/y may drift by an ULP.
_COORDINATE_TOLERANCE = 1e-6


def _removed(before: snapshot.GlyphSnapshot, edit: LayerEdit) -> tuple[int, ...]:
    """Resolve retained snapshot contour identities; reject unsupported writes."""
    if edit.advance is not None or edit.anchors is not None:
        raise ValueError("This Filter host currently supports contour deletion only")
    if edit.contours is None:
        return ()
    original = {id(contour) for contour in before.contours}
    kept = [id(contour) for contour in edit.contours]
    if len(set(kept)) != len(kept) or not set(kept) <= original:
        raise ValueError("Filter returned new or repeated contours")
    keep_set = set(kept)
    if kept != [id(contour) for contour in before.contours if id(contour) in keep_set]:
        raise ValueError("This Filter host cannot reorder contours")
    return tuple(
        index
        for index, contour in enumerate(before.contours)
        if id(contour) not in kept
    )


def _drift_free(actual: tuple, expected: tuple, split: Any) -> bool:
    """Equal except x/y within _COORDINATE_TOLERANCE; ``split`` -> (rest, coords)."""
    (rest_a, xy_a), (rest_e, xy_e) = split(actual), split(expected)
    return (
        rest_a == rest_e
        and len(xy_a) == len(xy_e)
        and all(abs(a - e) <= _COORDINATE_TOLERANCE for a, e in zip(xy_a, xy_e))
    )


def _split_contours(contours: tuple) -> tuple:
    """Snapshot contours with node x/y zeroed, plus the flat x/y list."""
    rest = tuple(
        replace(c, nodes=tuple(replace(n, x=0.0, y=0.0) for n in c.nodes))
        for c in contours
    )
    return rest, [v for c in contours for n in c.nodes for v in (n.x, n.y)]


def _split_state(state: tuple) -> tuple:
    """Native state with node x/y zeroed, plus the flat x/y list."""
    rest = tuple(
        (*row[:3], tuple((n[0], 0.0, 0.0, *n[3:]) for n in row[3]), *row[4:])
        for row in state
    )
    return rest, [v for row in state for n in row[3] for v in n[1:3]]


@dataclass(frozen=True)
class _Coordinates:
    """Positional correspondence; native identities and raw flags fence the plan."""

    before: tuple
    after: tuple
    local: tuple
    state: tuple


@dataclass(frozen=True)
class _Deletion:
    """Bind removal ordinals to the original native contours and geometry."""

    removed: tuple[int, ...]
    before: tuple
    state: tuple
    targets: tuple = ()


def _native_state(layer: Any) -> tuple:
    """Read actual node kinds without reducing quadratic controls to on/off."""
    return tuple(
        (
            int(shape.id),
            int(contour.id),
            bool(contour.closed),
            tuple(
                (
                    int(n.id),
                    float(n.position.x()),
                    float(n.position.y()),
                    int(n.nodeState),
                    bool(n.selected),
                    bool(n.smooth),
                )
                for n in contour.nodes()
            ),
            tuple(
                float(getattr(shape.transform, key)())
                for key in ("m11", "m12", "m21", "m22", "dx", "dy")
            ),
        )
        for shape in layer.shapes
        if not shape.isComponent
        for contour in shape.contours
    )


def _coordinates(before: snapshot.GlyphSnapshot, edit: LayerEdit) -> tuple | None:
    """Accept only finite coordinates at the same contour/node positions."""
    if edit.anchors is not None or edit.advance is not None:
        raise ValueError("Filter supports contour deletion only or coordinate edits")
    after = edit.contours
    if after is None or all(any(c is old for old in before.contours) for c in after):
        return None
    if len(after) != len(before.contours):
        raise ValueError("Filter cannot mix deletion and replacement")
    for index, (old, new) in enumerate(zip(before.contours, after)):
        if new is not old and any(
            new is c for c in before.contours[:index] + before.contours[index + 1 :]
        ):
            raise ValueError("Filter cannot reorder contours")
        if len(new.nodes) != len(old.nodes) or new.closed != old.closed:
            raise ValueError("Filter cannot change contour topology")
        for a, b in zip(old.nodes, new.nodes):
            if replace(b, x=a.x, y=a.y) != a:
                raise ValueError("Filter cannot change node metadata")
            if not all(isfinite(v) for v in (a.x, a.y, b.x, b.y)):
                raise ValueError("Filter coordinates must be finite")
    return after


def _coordinate_safe(layer: Any, outlines: Any) -> bool:
    """Coordinate edits require owned shapes with exact translation-only transforms."""
    return all(
        shape in outlines.outline_shapes(layer)[0]
        and tuple(
            getattr(shape.transform, key)()
            for key in ("m11", "m12", "m21", "m22")
        )
        == (1, 0, 0, 1)
        and all(isfinite(getattr(shape.transform, key)()) for key in ("dx", "dy"))
        for shape in layer.shapes
        if not shape.isComponent and shape.contours
    )


def _local_coordinates(after: tuple, state: tuple) -> tuple:
    """Resolve finite stored coordinates before history opens; keep offsets intact."""
    local = []
    for contour, (_, _, _, _, transform) in zip(after, state):
        dx, dy = transform[4:]
        nodes = []
        for node in contour.nodes:
            x, y = node.x - dx, node.y - dy
            if (
                not all(isfinite(v) for v in (x, y))
                or (x + dx, y + dy) != (node.x, node.y)
            ):
                raise ValueError("Filter coordinates cannot be represented in this shape")
            nodes.append(replace(node, x=x, y=y))
        local.append(replace(contour, nodes=tuple(nodes)))
    return tuple(local)


def _targets_safe(layer: Any, removed: tuple[int, ...], outlines: Any) -> bool:
    """Allow deletion only from owned, unshared and untransformed shapes."""
    allowed = {int(shape.id) for shape in outlines.outline_shapes(layer)[0]}
    owners = [
        shape
        for shape in layer.shapes
        if not shape.isComponent
        for _contour in shape.contours
    ]
    return all(
        index < len(owners) and int(owners[index].id) in allowed for index in removed
    )


def _unsafe_rows(layer: Any, outlines: Any) -> list[Any]:
    """Say why coordinate edits were refused, so the status is never a bare name."""
    notes = outlines.outline_shapes(layer)[1]
    reasons = dict.fromkeys(
        note.removesuffix(", kept") for note in notes
    ) or {"shared or transformed outline": None}
    return [outlines.Change("coordinates", "", f"{why}, skipped") for why in reasons]


def _selected_layers(selected: Any) -> tuple:
    """Fence every retained native owner before computing any selected layer."""
    rows = {}
    for row in selected.occurrences:
        package, glyph, layer = row.package, row.glyph, row.layer
        try:
            valid = (
                not package.isNull
                and not glyph.isNull
                and layer is not None
                and not layer.isNull
                and layer.isValid
                and int(package.id) == row.package_id == selected.context[0]
                and str(package.master) == selected.context[1]
                and int(glyph.package.id) == row.package_id
                and int(glyph.id) == row.glyph_id
                and str(glyph.name) == row.glyph_name
                and int(layer.id) == row.layer_id
                and str(layer.name) == row.layer_name
                and int(layer.glyph.id) == row.glyph_id
                and int(layer.glyph.package.id) == row.package_id
                and (current := package.findName(row.glyph_name)) is not None
                and not current.isNull
                and int(current.id) == row.glyph_id
                and any(
                    not item.isNull and int(item.id) == row.layer_id
                    for item in glyph.layers
                )
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                "A selected font, glyph or layer is missing or changed."
            ) from error
        if not valid:
            raise ValueError("A selected font, glyph or layer is missing or changed.")
        rows.setdefault((row.package_id, row.glyph_id, row.layer_id), row)
    return tuple(rows.values())


@outline_writer.sharing_operation()
def plan_filter(
    plugin: Filter, values: dict[str, Any], selected: Any, outlines: Any, history: Any
) -> tuple[Any, Any]:
    """Plan exact selected layers under outline_writer's whole-glyph policy."""
    if not selected.occurrences:
        return outlines.Plan(), None
    selected_rows = _selected_layers(selected)
    package = selected_rows[0].package
    facts = history.scan_auto_facts(package)
    unsafe: list[str] = []

    def planner(glyph: Any, master_name: str, layer: Any) -> list[Any]:
        before = snapshot.capture(snapshot.NativeSource(package, layer))
        original_state = _native_state(layer)
        identities = tuple((s, c) for s, c, _, _, _ in original_state)
        edit = plugin.compute(before, values)
        coordinates = _coordinates(before, edit)
        if coordinates is not None:
            if coordinates == before.contours:
                return []
            if not _coordinate_safe(layer, outlines):
                unsafe.append(str(glyph.name))
                return _unsafe_rows(layer, outlines)
            state = _native_state(layer)
            if tuple((s, c) for s, c, _, _, _ in state) != identities:
                raise ValueError("Filter native contour identities changed")
            return [
                outlines.Change(
                    "coordinates",
                    "",
                    "updated",
                    edit=_Coordinates(
                        before.contours,
                        coordinates,
                        _local_coordinates(coordinates, state),
                        state,
                    ),
                )
            ]
        if _native_state(layer) != original_state:
            raise ValueError("Filter native contour state changed during compute")
        removed = _removed(before, edit)
        if not removed:
            return []
        if not _targets_safe(layer, removed, outlines):
            unsafe.append(str(glyph.name))
            return [
                outlines.Change(
                    "contours",
                    str(len(before.contours)),
                    "shared or transformed outline, skipped",
                )
            ]
        return [
            outlines.Change(
                "contours",
                str(len(before.contours)),
                str(len(before.contours) - len(removed)),
                edit=_Deletion(removed, before.contours, original_state),
                key=removed,
            )
        ]

    plan = outlines.Plan()
    for row in selected_rows:
        glyph, layer = row.glyph, row.layer
        why = history.refusal(facts, row.glyph_name, "geometry")
        if why:
            if row.glyph_name not in plan.refused:
                plan.refused.append(row.glyph_name)
                plan.rows.append(
                    (row.glyph_name, outlines.Change("glyph", "", f"skipped: {why}"))
                )
            continue
        label = f"{row.glyph_name} · {row.layer_name}"
        if layer.autoLayer:
            plan.skipped.append(f"{row.glyph_name}/{row.layer_name}")
            plan.rows.append(
                (label, outlines.Change("layer", "", "auto layer, skipped"))
            )
            continue
        changes = planner(glyph, row.layer_name, layer)
        plan.rows.extend((label, change) for change in changes)
        blocked = [change.problem for change in changes if change.problem]
        plan.problems.extend(f"{label}: {text}" for text in blocked)
        edits = [change.edit for change in changes if change.edit is not None]
        if edits and not blocked:
            plan.work.append((glyph, layer, edits))
    plan.refused.extend(unsafe)
    return plan, facts


class LayerEditEditor:
    """Apply guarded contour edits in one existing geometry history step."""

    def __init__(self, outlines: Any) -> None:
        self.outlines = outlines

    def prepare(self, layer: Any, edits: list[Any]) -> Any:
        """Resolve all targets and validate source state before opening history."""
        if len(edits) == 1 and isinstance(edits[0], _Coordinates):
            change = edits[0]
            if (
                not _coordinate_safe(layer, self.outlines)
                or _native_state(layer) != change.state
            ):
                raise ValueError("Filter coordinate plan is stale or unsafe")
            actual = snapshot._contours(layer, lambda read: list(read()))
            if actual != change.before:
                raise ValueError("Filter source coordinates changed")
            return change
        if len(edits) != 1 or not isinstance(edits[0], _Deletion):
            raise ValueError("Filter deletion requires an original contour identity fence")
        change = edits[0]
        if _native_state(layer) != change.state:
            raise ValueError("Filter deletion plan is stale")
        if snapshot._contours(layer, lambda read: list(read())) != change.before:
            raise ValueError("Filter source contours changed")
        allowed = {int(shape.id) for shape in self.outlines.outline_shapes(layer)[0]}
        rows = [
            (shape, contour)
            for shape in layer.shapes
            if not shape.isComponent
            for contour in shape.contours
        ]
        indices = set(change.removed)
        if any(
            index < 0 or index >= len(rows) or int(rows[index][0].id) not in allowed
            for index in indices
        ):
            raise ValueError("Filter cannot edit a shared or transformed outline")
        return replace(change, targets=tuple(
            (*rows[index], int(rows[index][1].id))
            for index in sorted(indices, reverse=True)
        ))

    def write(self, layer: Any, steps: Any) -> None:
        """Write coordinates in place or remove contours from their owning shapes."""
        if isinstance(steps, _Coordinates):
            qt = _native("PythonQt")
            contours = [
                c for s in layer.shapes if not s.isComponent for c in s.contours
            ]
            for contour, target in zip(contours, steps.local):
                for node, point in zip(contour.nodes(), target.nodes):
                    flags = int(node.nodeState)
                    node.position = qt.QtCore.QPointF(point.x, point.y)
                    node.nodeState = flags
            return
        # History initialization can reenter FontLab after prepare resolved targets.
        steps = self.prepare(layer, [steps])
        for shape, contour, _identifier in steps.targets:
            shape.removeContour(contour)

    def check(self, prepared: list[tuple[Any, Any]]) -> list[str]:
        """Detect a native writer that retained a supposedly deleted contour."""
        errors = []
        for layer, steps in prepared:
            if isinstance(steps, _Coordinates):
                actual = snapshot._contours(layer, lambda read: list(read()))
                state = _native_state(layer)
                expected = tuple(
                    (
                        s,
                        c,
                        closed,
                        tuple(
                            (n[0], p.x, p.y, *n[3:])
                            for n, p in zip(nodes, target.nodes)
                        ),
                        transform,
                    )
                    for (s, c, closed, nodes, transform), target in zip(
                        steps.state, steps.local
                    )
                )
                if not _drift_free(actual, steps.after, _split_contours) or not _drift_free(
                    state, expected, _split_state
                ):
                    errors.append(
                        "coordinates or native node state changed after Filter write"
                    )
        return errors + [
            "contour remained after Filter write"
            for _, steps in prepared
            if not isinstance(steps, _Coordinates)
            for shape, _contour, identifier in steps.targets
            if any(int(item.id) == identifier for item in shape.contours)
        ]

    def retain(self, steps: Any) -> list[Any]:
        """Pin removed native contours for FontLab's deep history notification."""
        return (
            []
            if isinstance(steps, _Coordinates)
            else [contour for _, contour, _identifier in steps.targets]
        )


@outline_writer.sharing_operation()
def apply_filter(
    plugin: Filter,
    values: dict[str, Any],
    *,
    selected: Any = None,
    outlines: Any = None,
    writer: Any = None,
    history: Any = None,
) -> tuple[Any, Any]:
    """Apply one selected-layer plan with exactly one geometry history commit."""
    values = type(plugin).validate(values)
    selected = selected if selected is not None else snapshot.selected_layers()
    outlines = outlines or import_module("fontlabapp.contours.writer")
    writer = writer or import_module("fontlabapp.masters.layers.writer")
    history = history or import_module("fontlabapp.core.history.glyphs")
    plan, facts = plan_filter(plugin, values, selected, outlines, history)
    if not plan.work:
        return plan, None
    result = writer.apply_work(
        plan.work, plugin.title, facts, LayerEditEditor(outlines)
    )
    return plan, result
