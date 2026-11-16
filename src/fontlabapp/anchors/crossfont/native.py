# this_file: src/fontlabapp/anchors/crossfont/native.py
# SPDX-License-Identifier: Apache-2.0
"""Two-font capture/staging fences and complete post-notification verification."""

from dataclasses import replace
from time import monotonic

from fontlabapp import _native
from fontlabapp.anchors.duplicates.capture import check, require_main_thread
from fontlabapp.anchors.crossfont.model import Options
from fontlabapp.anchors.crossfont.capture import fonts, read
from fontlabapp.anchors.crossfont.transaction import (
    PartialWriteError,
    pending,
    prepare,
    publish,
)


class Backend:
    """Read refreshed registered choices and execute immediate guarded batches."""

    def fonts(self) -> tuple:
        """Read refreshed registered font identities without activating a document."""
        return fonts(monotonic() + 3)

    def copy(
        self,
        source: int,
        destination: int,
        source_layer: str,
        destination_layer: str,
        only_selected: bool,
        options: Options,
        title: str | None = None,
    ) -> dict:
        """Dispatch every current original option once, retaining skips and failures.

        ``title`` names the destination's one Undo step; None keeps the
        Copy Anchors Between Fonts title.
        """
        require_main_thread()
        deadline = monotonic() + 3
        native, qt = _native("fontlab"), _native("PythonQt")
        pending(native)
        args = (
            source,
            destination,
            source_layer,
            destination_layer,
            only_selected,
            deadline,
        )
        before = read(*args)
        if read(*args) != before:
            raise ValueError(
                "Source or destination changed during capture; retry after refresh."
            )
        jobs = prepare(before, options, native, qt, deadline)
        pending(native)
        if read(*args) != before:
            raise ValueError(
                "Source or destination changed before history; retry after refresh."
            )
        if not jobs:
            return {
                "anchors": 0,
                "layers": 0,
                "skipped": before.skipped,
                "zero_advance": (),
            }
        result = (
            publish(before, jobs, native, qt, deadline)
            if title is None
            else publish(before, jobs, native, qt, deadline, title)
        )
        try:
            after = read(*args)
            if (
                after.fonts != before.fonts
                or after.names != before.names
                or after.pairs != before.pairs
                or after.dependencies != before.dependencies
            ):
                raise ValueError(
                    "Font, selection or dependency source changed during copying."
                )
            expected = {key: (result, clones) for _, key, result, clones in jobs}
            for old_row, new_row in zip(before.layers, after.layers, strict=True):
                if old_row[:3] != new_row[:3]:
                    raise ValueError("Captured layer mapping changed during copying.")
                for old, new in zip(old_row[3:], new_row[3:], strict=True):
                    if old is None or new is None:
                        if old != new:
                            raise ValueError("A missing layer changed during copying.")
                        continue
                    if (old.identity, old.width, old.automatic) != (
                        new.identity,
                        new.width,
                        new.automatic,
                    ):
                        raise ValueError(
                            "An anchor owner or its metrics changed during copying."
                        )
                    if old.identity in expected:
                        planned, clones = expected[old.identity]
                        wanted = tuple(
                            replace(pin, identity=int(clones[pin.identity].id))
                            if pin.identity in clones
                            else pin
                            for pin in planned.pins
                        )
                    else:
                        wanted = old.pins
                    if len(wanted) != len(new.pins):
                        raise ValueError(
                            "Post-copy anchor count differs from the complete plan."
                        )
                    for wanted_pin, actual in zip(wanted, new.pins, strict=True):
                        if (actual.identity, actual.name, actual.x, actual.y) != (
                            wanted_pin.identity,
                            wanted_pin.name,
                            wanted_pin.x,
                            wanted_pin.y,
                        ):
                            raise ValueError(
                                "Post-copy anchor identity/name/coordinates differ from the plan."
                            )
                        if any(
                            actual.metadata[i] != wanted_pin.metadata[i]
                            for i in range(7)
                        ):
                            raise ValueError(
                                "Post-copy retained anchor metadata changed."
                            )
            check(deadline)
        except BaseException as error:
            raise PartialWriteError(
                sum(len(r.edits) for _, _, r, _ in jobs), [error]
            ) from error
        return result
