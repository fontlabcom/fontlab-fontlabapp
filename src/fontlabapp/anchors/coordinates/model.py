# this_file: src/fontlabapp/anchors/coordinates/model.py
# SPDX-License-Identifier: Apache-2.0
"""Original Center, Round and Snap arithmetic with source-candidate point writes."""

import math
from typing import Any

from fontlabapp import _native
from fontlabapp.anchors.copy.model import layer_of
from fontlabapp.anchors.edit import (
    apply_point_moves,
    finite,
    prepare_point_moves,
    raw_point,
)

METRICS = [
    ("Baseline", None),
    ("x-height", "xHeight"),
    ("Cap height", "capsHeight"),
    ("Ascender", "ascender"),
    ("Descender", "descender"),
]
REFERENCES = [("Advance width", "advance"), ("Ink box", "ink")]


def parse_names(text: str) -> list[str]:
    return [name.strip() for name in text.replace(";", ",").split(",") if name.strip()]


def target_x(
    layer: Any, reference: str, fraction: float, angle: float, y: float
) -> float | None:
    """Original slanted advance/ink reference; FontLab's negative angle leans right."""
    fraction, angle, y = finite(fraction), finite(angle), finite(y)
    if reference not in {"advance", "ink"}:
        raise ValueError("Choose Advance width or Ink box.")
    slope = -math.tan(math.radians(angle))
    if reference == "advance":
        return finite(finite(layer.advanceWidth) * fraction + slope * y)
    box = layer.boundingBox
    x, bottom, width, height = [
        finite(v()) for v in (box.x, box.y, box.width, box.height)
    ]
    if width <= 0 and height <= 0:
        return None
    return finite(x + width * fraction + slope * (y - bottom - height / 2))


def center_plan(
    layer: Any, names: list[str], reference: str, fraction: float, angle: float
) -> list:
    rows = []
    for pin in layer.anchors:
        if pin.name in names:
            x, y = map(round, raw_point(pin))
            new = target_x(layer, reference, fraction, angle, y)
            rows.append((pin.name, (x, y), None if new is None else round(new)))
    return rows


def snap(value: float, step: float) -> int:
    """Original half-up grid operation, including negative half ties."""
    value, step = finite(value), finite(step)
    if step <= 0:
        raise ValueError("Grid step must be positive.")
    return int(step * math.floor(value / step + 0.5))


def round_plan(
    layer: Any, step: float, do_x: bool, do_y: bool, names: list[str]
) -> list:
    snap(0, step)
    rows = []
    for pin in layer.anchors:
        if names and pin.name not in names:
            continue
        x, y = map(round, raw_point(pin))
        new = (snap(x, step) if do_x else x, snap(y, step) if do_y else y)
        if new != (x, y):
            rows.append((pin.name, (x, y), new))
    return rows


def metric_value(package: Any, master: str, attribute: str | None) -> int:
    if master not in package.masters or attribute not in {
        value for _, value in METRICS
    }:
        raise ValueError("Metric or masters changed; reopen this tool.")
    if attribute is None:
        return 0
    return round(
        finite(getattr(_native("fontlab").FontMetrics(package, master), attribute))
    )


def metric_plan(layer: Any, names: list[str], y: float) -> list:
    finite(y)
    return [
        (pin.name, tuple(map(round, raw_point(pin))), y)
        for pin in layer.anchors
        if pin.name in names
    ]


def _run(
    package: Any,
    glyphs: list,
    masters: list[str],
    planner: Any,
    axes: tuple[bool, bool],
    title: str,
) -> dict:
    if len(set(masters)) != len(masters) or set(masters) - set(package.masters):
        raise ValueError("Masters changed; reopen this tool.")
    jobs, skipped = [], []
    for glyph in glyphs:
        for master in masters:
            layer = layer_of(glyph, master)
            if layer is None:
                continue
            rows = planner(layer, master)
            if layer.autoLayer:
                if rows:
                    skipped.append(f"{glyph.name}/{master}")
                continue
            moves = []
            for pin in layer.anchors:
                matches = [row for row in rows if row[0] == pin.name]
                if matches and sum(p.name == pin.name for p in layer.anchors) > 1:
                    raise ValueError(
                        "Duplicate anchor names; resolve duplicates before moving."
                    )
                if not matches:
                    continue
                _, old, new = matches[0]
                if new is None:
                    continue
                new = (
                    new
                    if isinstance(new, tuple)
                    else (new, old[1])
                    if axes[0]
                    else (old[0], new)
                )
                if new != old:
                    raw = raw_point(pin)
                    moves.append(
                        (
                            pin,
                            tuple(
                                new[i] if axes[i] and new[i] != old[i] else raw[i]
                                for i in (0, 1)
                            ),
                        )
                    )
            if moves:
                jobs.append((glyph, master, moves))
    result = apply_point_moves(prepare_point_moves(package, jobs), title)
    return dict(result, skipped=skipped)


def run_center(
    glyphs: list,
    masters: list[str],
    names: list[str],
    reference: str,
    fraction: float,
    angle: float,
    *,
    package: Any,
) -> dict:
    return _run(
        package,
        glyphs,
        masters,
        lambda layer, _: center_plan(layer, names, reference, fraction, angle),
        (True, False),
        "Center Anchors Horizontally",
    )


def run_round(
    glyphs: list,
    masters: list[str],
    step: float,
    do_x: bool,
    do_y: bool,
    names: list[str],
    *,
    package: Any,
) -> dict:
    snap(0, step)
    return _run(
        package,
        glyphs,
        masters,
        lambda layer, _: round_plan(layer, step, do_x, do_y, names),
        (do_x, do_y),
        "Round Anchors to Grid",
    )


def run_metrics(
    package: Any,
    glyphs: list,
    masters: list[str],
    names: list[str],
    attribute: str | None,
    offset: float,
) -> dict:
    finite(offset)
    heights = {
        master: metric_value(package, master, attribute) + offset for master in masters
    }
    return _run(
        package,
        glyphs,
        masters,
        lambda layer, master: metric_plan(layer, names, heights[master]),
        (False, True),
        "Snap Anchors to Metrics",
    )
