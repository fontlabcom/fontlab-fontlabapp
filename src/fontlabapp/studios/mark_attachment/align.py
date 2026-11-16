# this_file: src/fontlabapp/studios/mark_attachment/align.py
# SPDX-License-Identifier: Apache-2.0
"""Align by anchor tab (Scriptmix Components · Align By Anchor): move mark components onto their base anchors.

The original's rules are kept unchanged (``anchor_points``, ``base_layer``,
``pairs``, ``align_changes``, ``families``): the first component is the
base; each later component moves so that its ``_X`` anchor sits on the
base's ``X`` (rounded half up); "no matching anchors", "scaled or slanted,
kept" and "in place" rows are listed and not written. Anchor pair:
"Automatic (first matching pair)" or one named pair; masters: current
(default) or all. Apply writes the listed offsets as one
``Mark Attachment: align components <subject>`` Undo step.
"""

from collections.abc import Iterable
from typing import Any

from .._kerning_ui import combo, get, row
from . import _shared

#: The verbatim functions read the original's module name.
component_writer = _shared.Modules("components")

AUTOMATIC = "Automatic (first matching pair)"


def anchor_points(layer: Any | None) -> dict[str, tuple[float, float]]:
    """{name: (x, y)} of the layer. Duplicate names: the first one wins."""
    found: dict[str, tuple[float, float]] = {}
    for pin in layer.anchors if layer is not None else ():
        found.setdefault(pin.name, (float(pin.point.x()), float(pin.point.y())))
    return found


def base_layer(package: Any, shape: Any, master: str) -> Any | None:
    """The layer that a component shows: its base glyph on this master."""
    glyph = package.findName(component_writer.base_of(shape))
    if glyph is None:
        return None
    return component_writer.layer_of(glyph, shape.shapeData.componentLayer or master)


def pairs(base: dict[str, tuple[float, float]], mark: dict) -> list[str]:
    """Anchor names X with X on the base and _X on the mark, in base order."""
    return [n for n in base if not n.startswith("_") and "_" + n in mark]


def align_changes(
    package: Any, layer: Any, master: str, wanted: str | None
) -> list[component_writer.Change]:
    """One row per mark component: anchor pair, current and new offset.

    `wanted` None takes the first shared pair. A row without `edit` is shown
    only: no pair, a scaled component, or a mark that already sits right.
    """
    shapes = component_writer.components(layer)
    if len(shapes) < 2:
        return []
    first = shapes[0]
    base = anchor_points(base_layer(package, first, master))
    bx, by = component_writer.offset(first)
    rows: list[component_writer.Change] = []
    for shape in shapes[1:]:
        name, old = component_writer.base_of(shape), component_writer.offset(shape)
        mark = anchor_points(base_layer(package, shape, master))
        found = pairs(base, mark)
        family = (found[0] if found else None) if wanted is None else wanted
        if family not in found:
            rows.append(
                component_writer.Change(
                    name, component_writer.offset_text(old), "no matching anchors"
                )
            )
            continue
        if not component_writer.plain_move(shape) or not component_writer.plain_move(
            first
        ):
            rows.append(
                component_writer.Change(
                    name, component_writer.offset_text(old), "scaled or slanted, kept"
                )
            )
            continue
        (ax, ay), (mx, my) = base[family], mark["_" + family]
        new = (
            float(component_writer.half_up(bx + ax - mx)),
            float(component_writer.half_up(by + ay - my)),
        )
        label = f"{name} @ {family}"
        if all(
            abs(new[axis] - old[axis]) < component_writer.EPSILON for axis in (0, 1)
        ):
            rows.append(
                component_writer.Change(
                    label, component_writer.offset_text(old), "in place"
                )
            )
        else:
            rows.append(
                component_writer.Change(
                    label,
                    component_writer.offset_text(old),
                    component_writer.offset_text(new),
                    (shape.id, new),
                )
            )
    return rows


def families(package: Any, glyphs: Iterable[Any], master: str) -> list[str]:
    """Anchor pairs any selected composite could use on `master`, in order."""
    found: list[str] = []
    for glyph in glyphs:
        layer = component_writer.layer_of(glyph, master)
        shapes = component_writer.components(layer) if layer is not None else []
        if len(shapes) < 2:
            continue
        base = anchor_points(base_layer(package, shapes[0], master))
        for shape in shapes[1:]:
            mark = anchor_points(base_layer(package, shape, master))
            found.extend(n for n in pairs(base, mark) if n not in found)
    return found


class AlignPanel(_shared.PlanPanel):
    """Align By Anchor."""

    ACTION = "Align"
    UNDO = "align components"
    WRITER = "components"

    def build_controls(self, form: Any) -> None:
        self.family = row(
            self.widget,
            form,
            "Anchor pair",
            combo(self.widget, [AUTOMATIC], self.changed),
        )
        self.scope = self.scope_box(form)
        self.choice = ""

    def changed(self) -> None:
        if self.ready:
            self.choice = get(self.family.currentText)
            self.run(self.refresh)

    def masters(self) -> list[str]:
        return self.tool.scope(get(self.scope.currentIndex) == 1)

    def wanted(self) -> str | None:
        return (
            None if get(self.family.currentIndex) <= 0 else get(self.family.currentText)
        )

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        package = self.tool.package
        found = families(package, glyphs, self.tool.current)
        self.family.blockSignals(True)
        self.family.clear()
        for item in [AUTOMATIC, *found]:
            self.family.addItem(item)
        self.family.setCurrentIndex(
            found.index(self.choice) + 1 if self.choice in found else 0
        )
        self.family.blockSignals(False)
        wanted = self.wanted()
        return lambda glyph, master, layer: align_changes(
            package, layer, master, wanted
        )

    def refresh(self) -> None:
        if self.ready:
            self.fill_scope(self.scope)
        super().refresh()

    def summary(self) -> str:
        dry = self.dry
        return f"{_shared.plural(dry.edits, 'component change')} on {_shared.plural(len(dry.work), 'layer')}"

    def sync(self, *args: Any) -> None:
        super().sync()
        if not self.dry.work and self.dry.rows and not self.dry.problem:
            self.count.setText("All marks already sit on their anchors")

    def editor(self) -> Any:
        return _shared.MoveEdit()


__all__ = [
    "AUTOMATIC", "AlignPanel", "align_changes", "anchor_points", "base_layer", "families", "pairs",
]  # fmt: skip
