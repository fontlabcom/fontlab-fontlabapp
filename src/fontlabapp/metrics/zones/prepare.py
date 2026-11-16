# this_file: src/fontlabapp/metrics/zones/prepare.py
# SPDX-License-Identifier: Apache-2.0
"""Prepare a complete zone batch without attaching it or notifying history.

Current-host ABI, decoder isolation and full native preservation remain gated.
Use only the dedicated owned qualification protocol until those gates pass.
The opaque restoration witness checks reversibility of serialized data; it does
not prove every metadata field or linked object's independence in the host.
"""

from collections.abc import Callable
from time import monotonic
from typing import Any

import fontlabapp.metrics.zones.guide_prepare as guide_ops
from fontlabapp import _native
from fontlabapp.core.scripting import current_package
from fontlabapp.metrics.zones.capture import capture
from fontlabapp.metrics.zones.capture_codec import encode, serializer
from fontlabapp.metrics.zones.capture_data import Capture
from fontlabapp.metrics.zones.data import Change
from fontlabapp.metrics.zones.prepared import PreparedBatch, PreparedMaster
from fontlabapp.metrics.zones.rows import number
from fontlabapp.metrics.zones.write_plan import WriteRow, build, require_current


def _check(deadline: float) -> None:
    """Respect one total Python deadline; native C++ calls cannot be preempted."""
    if monotonic() >= deadline:
        raise TimeoutError("Zone preparation exceeded its deadline; no partial batch.")


def _bounded(method: Callable, deadline: float) -> Callable:
    """Stop between native buffer operations when one consumes the total budget."""

    def call(*args: Any) -> Any:
        _check(deadline)
        result = method(*args)
        _check(deadline)
        return result

    return call


def _row(
    row: WriteRow, native: Any, qt: Any, codec: tuple, context: tuple, scratch: list
) -> tuple:
    """Prepare one root and retain a restoration witness until the batch ends."""
    method, decode = codec
    identifier, upm, protected, seen = context
    if row.zone.origin is None:
        guide = guide_ops.new(native, qt, row, protected, seen)
        original = None
    else:
        original = row.zone.origin.metadata
        guide = guide_ops.unpack(native, qt, decode, original, protected, seen)
        if encode(method, identifier, upm, (guide,)) != original:
            raise ValueError("Native zone payload did not round-trip before editing.")
    raw = guide_ops.visible(guide)
    guide.isZone = True
    signed = row.zone.width if row.kind == "Top" else -row.zone.width
    guide_ops.set_visible(guide, qt, (raw[0], row.zone.position, signed, row.zone.name))
    if not guide_ops.matches(guide, row) or guide_ops.visible(guide)[0] != raw[0]:
        raise ValueError("Prepared native zone differs from the requested row.")
    payload = encode(method, identifier, upm, (guide,))
    if original is not None:
        witness = guide_ops.unpack(native, qt, decode, payload, protected, seen)
        scratch.append(witness)
        guide_ops.set_visible(witness, qt, raw)
        if encode(method, identifier, upm, (witness,)) != original:
            raise ValueError(
                "Native zone restoration witness lost serialized source data."
            )
        if encode(method, identifier, upm, (guide,)) != payload:
            raise ValueError(
                "Native zone restoration witness aliases the prepared row."
            )
    return guide, payload


def _protected(package: Any, before: Capture, deadline: float) -> tuple:
    """Protect known source graph IDs and restore the exact starting master."""
    original = before.snapshot.current_master
    if package.master != original:
        raise ValueError("The source current master changed before graph capture.")
    graph = []
    try:
        for frame in before.guides:
            _check(deadline)
            package.setMaster(frame.master, False)
            if package.master != frame.master:
                raise ValueError("The source graph master switch failed.")
            guides = tuple(package.guidelines)
            if tuple(g.id for g in guides) != frame.ids:
                raise ValueError("The source guide identities changed.")
            graph.append((frame.master, tuple(guide_ops.identities(g) for g in guides)))
    finally:
        package.setMaster(original, False)
        if package.master != original:
            raise RuntimeError("Could not restore the source graph master.")
    return tuple(graph)


def prepare(before: Capture, changes: tuple[Change, ...]) -> PreparedBatch:
    """Preflight all rows, then return every prepared master or no batch.

    No system clipboard, guide-host attachment/removal, package/history notifier
    or UpdateAll is invoked. Source capture still switches/restores masters.
    New-guide defaults and actual native graph/payload safety require acceptance.
    """
    if type(changes) is not tuple:
        raise ValueError("Native zone preparation requires an immutable change tuple.")
    plan = build(before, changes)
    if not plan.masters:
        return PreparedBatch(plan, ())
    deadline = monotonic() + 2.0
    native = _native("fontlab")
    codec = (
        _bounded(serializer(native), deadline),
        _bounded(guide_ops.decoder(native), deadline),
    )
    require_current(plan, capture(before.snapshot.package_id))
    _check(deadline)
    package = current_package(before.snapshot.package_id)
    if package is None:
        raise ValueError("The source font closed before native zone preparation.")
    qt = _native("PythonQt").QtCore
    graph = _protected(package, before, deadline)
    protected = {i for _, guides in graph for ids in guides for i in ids}
    context = before.snapshot.package_id, number(package.upm), protected, set()
    masters, scratch = [], []
    for master in plan.masters:
        guides, payloads = [], []
        for row in master.rows:
            _check(deadline)
            guide, payload = _row(row, native, qt, codec, context, scratch)
            guides.append(guide)
            payloads.append(payload)
        masters.append(PreparedMaster(master.master, tuple(guides), tuple(payloads)))
    _check(deadline)
    for master, source in zip(masters, plan.masters, strict=True):
        for guide, payload, row in zip(
            master.guides, master.payloads, source.rows, strict=True
        ):
            _check(deadline)
            if (
                not guide_ops.matches(guide, row)
                or encode(codec[0], context[0], context[1], (guide,)) != payload
            ):
                raise ValueError(
                    "Prepared native rows changed while preparing the batch."
                )
    if _protected(package, before, deadline) != graph:
        raise ValueError("The source guide identity graph changed during preparation.")
    require_current(plan, capture(before.snapshot.package_id))
    _check(deadline)
    return PreparedBatch(plan, tuple(masters))
