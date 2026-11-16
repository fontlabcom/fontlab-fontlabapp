# this_file: src/fontlabapp/metrics/zones/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Capture native all-master zones with complete native guide-buffer fences.

Use the model producer's in-memory binary serializer, not font-info JSON or the
system clipboard. The corrected binding must declare three arguments; the legacy
two-argument docstring/macro profile is refused before any master switch. No buffer is parsed or decoded here. Every guide, including nonzones,
is serialized. Native serialization coverage and read preservation still require
dedicated owned FontLab qualification. setMaster(name, False) is restored in
finally; this is not a claim that native reads have no side effects.
"""

from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.metrics.zones.model import Editor
from fontlabapp.core.scripting import current_package
from fontlabapp.metrics.zones.capture_codec import encode, serializer
from fontlabapp.metrics.zones.capture_data import Capture, GuideBuffer
from fontlabapp.metrics.zones.data import Master, Origin, Snapshot, Zone, Zones
from fontlabapp.metrics.zones.native_rules import is_top as _top
from fontlabapp.metrics.zones.rows import number, text


def _check(deadline: float) -> None:
    """Bound Python checkpoints; a native C++ call itself cannot be preempted."""
    if monotonic() >= deadline:
        raise TimeoutError("Zone capture exceeded its deadline; no partial capture.")


def _domain(package: Any) -> tuple:
    """Parse identity, master order and UPM before the first master switch."""
    identifier, current, names, upm = (
        package.id,
        package.master,
        package.masters,
        package.upm,
    )
    if (
        type(identifier) is not int
        or identifier <= 0
        or not isinstance(names, (tuple, list))
        or not names
        or any(not isinstance(name, str) for name in names)
    ):
        raise ValueError("Unreadable font identity or master domain.")
    names = tuple(text(name) for name in names)
    if len(set(names)) != len(names) or current not in names or number(upm) <= 0:
        raise ValueError("Unreadable font current master, master order or UPM.")
    return identifier, current, names, number(upm)


def _scan(
    package: Any, native: Any, domain: tuple, deadline: float, method: Any
) -> Capture:
    """Read all masters, every guide and each raw editable zone, with restoration."""
    identifier, original, names, upm = domain
    masters, buffers = [], []
    try:
        for name in names:
            _check(deadline)
            package.setMaster(name, False)
            if package.master != name:
                raise ValueError("Native font master switch did not select its target.")
            guides = tuple(package.guidelines)
            ids = tuple(g.id for g in guides)
            if any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(
                ids
            ):
                raise ValueError("Unreadable or duplicate native guide identity.")
            buffers.append(
                GuideBuffer(name, ids, encode(method, identifier, upm, guides))
            )
            top, bottom = [], []
            for guide in guides:
                _check(deadline)
                if type(guide.isZone) is not bool:
                    raise ValueError("Unreadable native zone flag.")
                if not guide.isZone or not guide.isHorizontal():
                    continue
                position, width, label = (
                    number(guide.centerPoint.y()),
                    number(guide.extPosition),
                    text(guide.name),
                )
                origin = Origin(
                    str(guide.id), encode(method, identifier, upm, (guide,))
                )
                zone = Zone(position, abs(width), label, origin)
                (top if _top(width, label, position) else bottom).append(zone)
            # A named FontMetrics lookup strips :/#/@ suffixes. Use the exact
            # current master just selected above, via its empty-name fallback.
            metrics = native.FontMetrics(package, "")
            masters.append(
                Master(
                    name,
                    number(metrics.xHeight),
                    number(metrics.capsHeight),
                    Zones(tuple(top), tuple(bottom)),
                )
            )
    finally:
        package.setMaster(original, False)
        if package.master != original:
            raise RuntimeError(
                "Native zone capture could not restore the starting master."
            )
    _check(deadline)
    result = Capture(Snapshot(identifier, original, tuple(masters)), tuple(buffers))
    Editor(result.snapshot)
    return result


def capture(expected_id: int | None = None) -> Capture:
    """Double-read a complete bound domain in two seconds; return no prefix.

    No glyph, history, cache-refresh, update, file, preference or clipboard writer
    is called. Master switches and native serialization still need their own
    preservation proof. This read adapter does not implement Apply or a menu.
    """
    deadline = monotonic() + 2.0
    if expected_id is not None and (type(expected_id) is not int or expected_id <= 0):
        raise ValueError("The expected font identity must be a positive integer.")
    package = current_package(expected_id)
    if package is None:
        raise ValueError("Open the original font before capturing zones.")
    domain = _domain(package)
    native = _native("fontlab")
    method = serializer(native)
    first = _scan(package, native, domain, deadline, method)
    if current_package(domain[0]) is None or _domain(package) != domain:
        raise ValueError(
            "The source font or master domain changed during zone capture."
        )
    second = _scan(package, native, domain, deadline, method)
    _check(deadline)
    if (
        current_package(domain[0]) is None
        or _domain(package) != domain
        or first != second
    ):
        raise ValueError(
            "The source font, master domain or complete guide data changed."
        )
    return second
