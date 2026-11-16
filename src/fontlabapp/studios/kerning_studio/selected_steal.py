# this_file: src/fontlabapp/studios/kerning_studio/selected_steal.py
# SPDX-License-Identifier: Apache-2.0
"""Selected-slot Steal Kerning From Next Pair migrated from the Scriptmix independent Apache-2.0 rewrite.

Original inspiration: Alex Slobzheninov, https://github.com/slobzheninov/Glyphs-Scripts.
Preserves selected OR active slot capture and exact typed native writer semantics.
"""
import math
from fontlabapp.studios._kerning_ui import line_edit, get, row
from itertools import pairwise
from time import monotonic
from typing import Any
from fontlabapp.core import scripting
from fontlabapp.studios._kerning_ui import Panel, button

TITLE = 'Steal Kerning From Next Pair'
selection = scripting.layer_selection_api()
kerning = scripting.kerning_tool_backends().batch

Point = tuple[float, float, bool]
masters = scripting.masters_api()


def quadratic_cubics(points: list[Point]) -> list[Point]:
    """Elevate quadratic spans, including implied on-curves, before flattening."""
    if not points:
        return []
    start = next((i for i, point in enumerate(points) if point[2]), None)
    if start is None:
        first, last = points[0], points[-1]
        origin = ((first[0] + last[0]) / 2, (first[1] + last[1]) / 2, True)
        ordered = [origin, *points, origin]
    else:
        ordered = points[start:] + points[:start] + [points[start]]
    result, handles = [ordered[0]], []
    current = ordered[0]
    for point in ordered[1:]:
        if not point[2]:
            handles.append(point)
            continue
        for index, handle in enumerate(handles):
            end = (
                point
                if index == len(handles) - 1
                else (
                    (handle[0] + handles[index + 1][0]) / 2,
                    (handle[1] + handles[index + 1][1]) / 2,
                    True,
                )
            )
            result.extend(
                [
                    (
                        current[0] + (handle[0] - current[0]) * 2 / 3,
                        current[1] + (handle[1] - current[1]) * 2 / 3,
                        False,
                    ),
                    (
                        end[0] + (handle[0] - end[0]) * 2 / 3,
                        end[1] + (handle[1] - end[1]) * 2 / 3,
                        False,
                    ),
                    end,
                ]
            )
            current = end
        if not handles:
            result.append(point)
        current, handles = point, []
    return result


def extents(
    layer: Any, height: float, *, glyph_name: str = "", notices: list[str] | None = None
) -> tuple[float, float]:
    """Find the leftmost/rightmost scanline crossings of the decomposed outline."""

    contours = masters.layer_contours(layer)
    kinds = [
        (bool(c.isTT), bool(c.closed)) for shape in layer.shapes for c in shape.contours
    ]
    if len(contours) != len(kinds):
        raise ValueError("Outline structure changed during measurement; Preview again.")
    name = glyph_name or str(layer.name)
    skipped = sum(not closed for _, closed in kinds)
    note = f"{name}: skipped {skipped} open contour{'' if skipped == 1 else 's'}."
    if skipped and notices is not None:
        notices.append(note)
    crossings = []
    deadline = monotonic() + 2.0
    for points, (is_quadratic, closed) in zip(contours, kinds, strict=True):
        if monotonic() >= deadline:
            raise TimeoutError("Outline measurement exceeded its per-glyph time limit.")
        if not closed:
            continue
        polygon = masters.polygon(quadratic_cubics(points) if is_quadratic else points)
        if any(not math.isfinite(value) for point in polygon for value in point):
            raise ValueError("Outline coordinates must be finite.")
        for (x1, y1), (x2, y2) in pairwise(polygon + polygon[:1]):
            if min(y1, y2) <= height <= max(y1, y2):
                if y1 == y2:
                    crossings.extend((x1, x2))
                else:
                    crossings.append(x1 + (height - y1) * (x2 - x1) / (y2 - y1))
    if not crossings:
        detail = f" {note}" if skipped else ""
        raise ValueError(
            f"{name}: No closed outline crossing at height {height:g} in {layer.name}.{detail}"
        )
    return min(crossings), max(crossings)


def target_key(groups: dict, records: dict, left: str, right: str) -> tuple:
    """Keep the most specific existing exception; otherwise use native side groups."""
    sides = []
    for index, name in enumerate((left, right)):
        permitted = (
            ("KernLeft", "KernBothSide")
            if index == 0
            else ("KernRight", "KernBothSide")
        )
        matches = [
            key
            for key, (members, mode) in groups.items()
            if name in members and mode in permitted
        ]
        if len(matches) > 1:
            raise ValueError(f"Glyph {name} has multiple kerning groups on one side.")
        sides.append((matches[0], "groupMode") if matches else (name, "glyphMode"))
    glyphs = ((left, "glyphMode"), (right, "glyphMode"))
    candidates = (glyphs, (glyphs[0], sides[1]), (sides[0], glyphs[1]), tuple(sides))
    return next((pair for pair in candidates if pair in records), tuple(sides))


def plan(height: float, expected_id: int | None = None) -> dict:
    """Read four selected slots, their outline gaps and the complete kerning snapshot."""

    if not math.isfinite(height):
        raise ValueError("Height must be a finite number.")
    captured = selection.capture(monotonic() + 2.0)
    package = scripting.current_package()
    if (
        package is None
        or package.id != captured.context[0]
        or (expected_id is not None and package.id != expected_id)
    ):
        raise ValueError("Activate the original font and select four glyphs.")
    rows = captured.occurrences
    if captured.context[2] != "editor" or len(rows) != 4:
        raise ValueError("Select exactly four adjacent glyphs in a Glyph window.")
    if any(
        a.block_id != b.block_id or b.index != a.index + 1 for a, b in pairwise(rows)
    ):
        raise ValueError("Select four consecutive glyphs in one text block.")
    master = str(rows[0].layer.name)
    if master not in package.masters or any(
        not row.layer.isMasterLayer or str(row.layer.name) != master for row in rows
    ):
        raise ValueError("All four glyphs must show the same declared master.")
    widths = [float(row.layer.advanceWidth) for row in rows]
    if any(not math.isfinite(width) or width < 0 for width in widths):
        raise ValueError("Advance widths must be finite and nonnegative.")
    before = kerning.snapshot_kerning(package, typed=True)
    notices: list[str] = []
    bounds = [
        extents(row.layer, height, glyph_name=row.glyph_name, notices=notices)
        for row in rows
    ]
    notices = list(dict.fromkeys(notices))
    gaps = (
        widths[0] - bounds[0][1] + bounds[1][0],
        widths[2] - bounds[2][1] + bounds[3][0],
    )
    reference = float(
        scripting.kerning_pair_value(
            package.kerning(master), rows[2].glyph_name, rows[3].glyph_name
        )
    )
    if not math.isfinite(reference):
        raise ValueError("Reference kerning must be finite.")
    value = int(gaps[1] - gaps[0] + reference)
    pair = target_key(
        before.groups[master],
        before.pairs[master],
        rows[0].glyph_name,
        rows[1].glyph_name,
    )
    return {
        "package": package,
        "selection": captured,
        "before": before,
        "height": height,
        "edits": {master: {pair: None if value == 0 else value}},
        "value": value,
        "record": " · ".join(
            ("@" if mode == "groupMode" else "") + name for name, mode in pair
        ),
        "notices": notices,
        "fingerprint": (
            captured,
            before,
            tuple(widths),
            tuple(bounds),
            reference,
            pair,
            tuple(notices),
        ),
        "names": tuple(row.glyph_name for row in rows),
        "gaps": gaps,
    }


def write(preview: dict) -> dict:
    """Re-measure before writing; refuse stale selection, outlines or kerning."""

    current = plan(preview["height"], preview["package"].id)
    if current["fingerprint"] != preview["fingerprint"]:
        raise ValueError("Pair preview changed; press Preview again.")
    try:
        changed = kerning.write_kerning(
            current["package"], preview["edits"], TITLE, expected=preview["before"]
        )
    except RuntimeError as error:
        raise RuntimeError(
            f"{error} Native changes may remain; use Edit > Undo."
        ) from error
    return {
        "value": preview["value"],
        "changed": changed,
        "notices": preview["notices"],
    }


def run(height: float) -> dict:
    """Measure and apply a live four-slot pair action without opening a panel."""
    return write(plan(height))


def default_height(package: Any) -> float:
    """Use half the shown master's x-height, falling back to the current master."""

    if package is None:
        return 0.0
    captured = selection.capture(monotonic() + 2.0)
    if captured.context[0] != package.id:
        raise ValueError("The active font changed; reopen this tool.")
    rows = captured.occurrences
    master = str(rows[0].layer.name) if rows else str(package.master)
    if master not in package.masters:
        master = str(package.master)
    import fontlab

    return float(fontlab.FontMetrics(package, master).xHeight) / 2


class StealStage:
    """Apply only the displayed height and recaptured four-slot measurement."""
    def __init__(self, package: Any = scripting.current_package) -> None:
        self.package = package
        self.accepted: dict | None = None

    def ready(self) -> bool:
        return self.accepted is not None

    def preview(self, height: float) -> dict:
        self.accepted = None
        package = self.package()
        self.accepted = plan(height, package.id if package is not None else None)
        return self.accepted

    def apply(self, height: float) -> dict:
        data, self.accepted = self.accepted, None
        if data is None:
            raise ValueError('Preview Changes before applying the matched gap.')
        self.package()
        if height != data['height']:
            raise ValueError('Height changed; Preview Changes again.')
        return write(data)


class StealPanel(Panel):
    """Match the first selected pair to the second at the displayed Height."""
    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.stage = StealStage(tool.shell.package)
        self.height_edit = line_edit(self.widget, '0', slot=self.height_changed)
        row(self.widget, self.layout, 'Height', self.height_edit)
        button(self.widget, self.layout, 'Use half the shown x-height', self.use_default)
        self.grid = self.table(['Target', 'Master', 'Reference', 'Record', 'Height', 'Computed value'])
        self.subtitle.setText('Select four consecutive Glyph-window slots. Match the first pair to the second at Height. Open contours are skipped and reported.')
        tool.shell.set_actions(self.widget, refresh=self.refresh, preview=self.preview,
                               apply=self.apply, ready=self.stage.ready, dirty=self.stage.ready,
                               apply_label='Apply matched gap')
        self.default_pending = True

    def height_changed(self, *args: Any) -> None:
        self.default_pending = False
        self.refresh()

    def use_default(self) -> None:
        self.height_edit.setText(f'{default_height(self.tool.shell.package()):g}')
        self.default_pending = False

    def refresh(self) -> None:
        self.stage.accepted = None
        self.grid.set_rows([])
        self.tool.say('Preview Changes to measure the selected pairs at Height.')

    def preview(self) -> None:
        if self.default_pending:
            self.use_default()
        self.refresh()
        try:
            height = float(get(self.height_edit.text))
        except ValueError as error:
            raise ValueError('Height must be a finite number.') from error
        data = self.stage.preview(height)
        master = next(iter(data['edits']))
        self.grid.set_rows([(' '.join(data['names'][:2]), master,
                             (master, ' '.join(data['names'][2:]), data['record'], data['height'], data['value']))])
        self.tool.show_pair(*data['names'][:2], master)
        self.tool.say(f"Unkerned gaps: {data['gaps'][0]:g} and {data['gaps'][1]:g} units. " + ' '.join(data['notices']))

    def apply(self) -> None:
        result = self.stage.apply(float(get(self.height_edit.text)))
        if result['value'] == 0:
            message = 'Pair record removed.' if result['changed'] else 'Pair record already absent.'
        else:
            message = f"Kerning {'set to' if result['changed'] else 'unchanged at'} {result['value']} units."
        self.tool.say(message + ' ' + ' '.join(result['notices']))
        if self.tool.preview is not None:
            self.tool.preview.refresh()
