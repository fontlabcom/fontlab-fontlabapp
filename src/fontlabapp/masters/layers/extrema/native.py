# this_file: src/fontlabapp/masters/layers/extrema/native.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Capture complete ordered native layer bounds without creating missing layers.

Current mode keeps the selected master only. All mode follows the existing
Glyport foreground mapping: master order, then ordinary auxiliaries in stored
order; masks/service records are background/cache. Actual order/role/bounds and
read preservation still require owned native qualification. Layer getters can
complete lazy imports/cache state. No direct fgGlyph getter,
master switch, UpdateAll, selection/font/history/preference/Output writer occurs.
"""

from dataclasses import dataclass
from math import isfinite
from time import monotonic
from typing import Any, Literal

from fontlabapp.masters.layers.extrema.model import LayerExtent
from fontlabapp.core.scripting import current_package

Mode = Literal["current", "all"]


@dataclass(frozen=True)
class Snapshot:
    """Complete plain source domain and immutable raw-bound fences; no handles."""

    package_id: int
    master: str
    masters: tuple[str, ...]
    mode: Mode
    rows: tuple[LayerExtent, ...]
    domain: tuple


def check(deadline: float) -> None:
    """Bound Python checkpoints; a blocking native call cannot be preempted."""
    if monotonic() >= deadline:
        raise TimeoutError(
            "Layer extrema capture exceeded its deadline; no partial proof."
        )


def _identity(value: Any) -> tuple:
    """Parse known object identity/name properties without reflecting getters."""
    identifier, name = value.id, value.name
    if (
        type(identifier) is not int
        or identifier <= 0
        or not isinstance(name, str)
        or not name
    ):
        raise ValueError("Unreadable native glyph/layer identity.")
    return identifier, name


def _domain(package: Any) -> tuple:
    """Fence current font/master and every ordered real master name."""
    identifier, master, names = package.id, package.master, tuple(package.masters)
    if (
        type(identifier) is not int
        or identifier <= 0
        or not names
        or any(not isinstance(name, str) or not name for name in names)
        or len(set(names)) != len(names)
        or master not in names
    ):
        raise ValueError("Unreadable native font/master domain.")
    return identifier, master, names


def _layers(
    glyph: Any, masters: tuple[str, ...], master: str, mode: Mode, deadline: float
) -> tuple:
    """Require exact addressable layers; never create or silently choose fallback."""
    layers = (glyph.findLayer(master),) if mode == "current" else glyph.layers
    states, foreground, ids = [], {}, set()
    for layer in layers:
        check(deadline)
        if layer is None or layer.isNull or not layer.isValid:
            raise ValueError("A source glyph has an invalid or missing layer.")
        if layer.glyph.id != glyph.id:
            raise ValueError("A source layer belongs to another glyph.")
        identifier, name = _identity(layer)
        roles = (layer.isMasterLayer, layer.isMaskLayer, layer.isService)
        if identifier in ids or any(type(v) is not bool for v in roles):
            raise ValueError(
                "Duplicate layer identity or unreadable native layer role."
            )
        ids.add(identifier)
        is_master, mask, service = roles
        if mask or service:
            if mode == "current":
                raise ValueError("The selected master is not a foreground layer.")
            states.append((identifier, name, roles, None))
            continue
        if (
            name in foreground
            or (is_master and name not in masters)
            or (name in masters and not is_master)
        ):
            raise ValueError("Ambiguous or unmapped foreground master/layer name.")
        box = layer.boundingBox
        bounds = (box.x(), box.y(), box.width(), box.height())
        if (
            any(type(v) not in (int, float) or not isfinite(v) for v in bounds)
            or bounds[2] < 0
            or bounds[3] < 0
            or not isfinite(bounds[1] + bounds[3])
        ):
            raise ValueError("A source layer has invalid raw bounds.")
        foreground[name] = bounds
        states.append((identifier, name, roles, bounds))
    chosen = (
        (master,)
        if mode == "current"
        else masters + tuple(name for name in foreground if name not in masters)
    )
    if any(name not in foreground for name in chosen):
        raise ValueError(
            "Every source glyph must have its exact selected/master layers."
        )
    return tuple((name, foreground[name]) for name in chosen), tuple(states)


def _read(package: Any, context: tuple, mode: Mode, deadline: float) -> Snapshot:
    """Keep font glyph order, complete layer domains and every unrounded box."""
    identifier, master, masters = context
    rows, domain, ids, names = [], [], set(), set()
    # flPackage has no glyph list (native probe 2026-11-03): fgPackage gives font
    # order and findName the matching flGlyph.
    for source in package.fgPackage.glyphs:
        check(deadline)
        glyph = package.findName(str(source.name))
        if glyph is None or glyph.isNull or glyph.package.id != identifier:
            raise ValueError("A source glyph is missing or belongs to another font.")
        gid, name = _identity(glyph)
        if gid in ids or name in names:
            raise ValueError("Duplicate source glyph identity/name.")
        ids.add(gid)
        names.add(name)
        layers, states = _layers(glyph, masters, master, mode, deadline)
        rows.extend(
            LayerExtent(name, layer, bounds[1], bounds[1] + bounds[3])
            for layer, bounds in layers
        )
        domain.append((gid, name, states))
    check(deadline)
    return Snapshot(identifier, master, masters, mode, tuple(rows), tuple(domain))


def capture(mode: Mode, deadline: float | None = None) -> Snapshot:
    """Double-read all required bounds or return no snapshot on stale sources."""
    if mode not in ("current", "all"):
        raise ValueError("Choose current or all foreground layers.")
    limit = monotonic() + 2.0 if deadline is None else deadline
    check(limit)
    package = current_package()
    if package is None:
        raise ValueError("Open a font before finding its layer extrema.")
    context = _domain(package)
    first = _read(package, context, mode, limit)
    if current_package(context[0]) is None or _domain(package) != context:
        raise ValueError("Source font or master changed during bounds capture.")
    second = _read(package, context, mode, limit)
    check(limit)
    if (
        current_package(context[0]) is None
        or _domain(package) != context
        or first != second
    ):
        raise ValueError("Source font, layers or bounds changed; run the proof again.")
    return second
