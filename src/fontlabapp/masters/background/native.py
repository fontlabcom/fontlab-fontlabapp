# this_file: src/fontlabapp/masters/background/native.py
# SPDX-License-Identifier: Apache-2.0
"""Complete bounded native adapter for Pedro's three background operations."""

from time import monotonic
from types import SimpleNamespace as NS
from typing import Any

import fontlabapp.masters.layers.selection as layers
from fontlabapp import _native
from fontlabapp.masters.background.capture import Capture
from fontlabapp.masters.background.records import check, clone, shape_record
from fontlabapp.masters.background.stage import selected_shapes, transform_shape
from fontlabapp.masters.background.model import Transform
from fontlabapp.masters.background.transaction import publish


def _values(shape: Any, deadline: float) -> tuple:
    row = shape_record(shape, deadline)
    contours = tuple(
        (closed, tt, tuple(node[1:] for node in nodes))
        for _id, closed, tt, nodes in row[-1]
    )
    return (*row[2:-1], contours)


class Backend:
    """Inject native-shaped providers for offline checks; native calls stay lazy."""

    def __init__(self, provider=None, first_provider=None, native=_native):
        self.provider = provider or layers.capture
        self.first_provider = first_provider
        self.native = native
        self.poisoned = False

    def _selection(self, mode: str, deadline: float) -> Any:
        if mode != "replace":
            return self.provider(deadline)
        if self.first_provider is not None:
            return self.first_provider(deadline)
        from fontlabapp.masters.background.selection import capture

        return capture(deadline)

    def capture(self, mode: str) -> Capture:
        """Capture exactly the original selected/all-font background domain."""
        from fontlabapp.masters.background.capture import read

        return read(self, mode)

    def apply(self, source: Capture, operation: Transform | None) -> dict:
        if self.poisoned:
            raise RuntimeError(
                "Background adapter retains a failed edit; review its native history first."
            )
        if (
            (operation is None) != (source.mode == "replace")
            or operation is not None
            and operation.mode != source.mode
        ):
            raise ValueError("Background operation does not match its captured source.")
        deadline = monotonic() + 4
        qt = self.native("PythonQt")
        jobs = []
        template = (
            selected_shapes(source.source, self.native("fontlab"), qt, deadline)
            if source.mode == "replace"
            else ()
        )
        for target in source.targets:
            check(deadline)
            old = () if target.mask is None else tuple(target.mask.shapes)
            if source.mode == "replace":
                desired = tuple(clone(shape, deadline) for shape in template)
                replacements = tuple(
                    (i, shape, None) for i, shape in reversed(tuple(enumerate(old)))
                ) + tuple((i, None, shape) for i, shape in enumerate(desired))
            else:
                if target.mask is None:
                    continue
                replacements = tuple(
                    (i, s, new)
                    for i, s in enumerate(old)
                    if (
                        new := transform_shape(
                            s, operation, target.repeat, qt, deadline
                        )
                    )
                    is not s
                    and _values(s, deadline) != _values(new, deadline)
                )
                desired = tuple(
                    new if new is not None else old[i] for i, _old, new in replacements
                )
            anchors = () if target.mask is None else tuple(target.mask.anchors)
            guides = () if target.mask is None else tuple(target.mask.guidelines)
            if (
                source.mode == "replace"
                and target.mask is not None
                and not (anchors or guides)
                and tuple(_values(s, deadline) for s in old)
                == tuple(_values(s, deadline) for s in desired)
            ):
                continue
            if not replacements and source.mode != "replace":
                continue
            jobs.append(
                NS(
                    target=target,
                    replacements=replacements,
                    replace=source.mode == "replace",
                    anchors=anchors,
                    guides=guides,
                    created=None,
                )
            )
        if self.capture(source.mode).fingerprint != source.fingerprint:
            raise ValueError(
                "Background source, selection, master or complete destination set changed; run again."
            )
        if not jobs:
            return {"changed": 0, "mode": source.mode}
        try:
            publish(
                tuple(jobs),
                self.native("fontlab"),
                qt,
                deadline,
                {
                    "scale": "Scale background",
                    "shift": "Shift background",
                    "replace": "Selection to all backgrounds",
                }[source.mode],
            )
        except BaseException:
            self.poisoned = True
            raise
        return {"changed": len(jobs), "mode": source.mode}
