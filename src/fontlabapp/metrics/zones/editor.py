# this_file: src/fontlabapp/metrics/zones/editor.py
# SPDX-License-Identifier: Apache-2.0
"""Launch the complete Alignment Zones UI with an explicit source/write adapter.

Importing this module stays host-free. The adapter owns native capture, complete
source/guideline identity and metadata checks, bounded reads, one-step history,
partial-failure reporting and persistence qualification. No default native writer
is implied by this UI: pass ``zone_native.backend()`` (route-A writer, native
acceptance pending) or another explicit adapter.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from fontlabapp.metrics.zones.model import Extent
from fontlabapp.metrics.zones.data import Change, Snapshot
from fontlabapp.metrics.zones.rows import result_matches

KEY = "metrics_zones_editor"


@dataclass(frozen=True)
class Backend:
    """Required callbacks; each owns its native deadline and preservation checks.

    capture raises on no font. check rejects changed/closed source/domain/metadata.
    bounds returns positive-height o/O extents (None for missing/flat layers).
    apply owns one complete history batch and returns a verified new baseline.
    No callback has a default or a placeholder implementation.
    """

    capture: Callable[[], Snapshot]
    check: Callable[[Snapshot], None]
    bounds: Callable[[Snapshot, str], tuple[Extent, Extent]]
    apply: Callable[[Snapshot, tuple[Change, ...]], Snapshot]


def check_result(
    before: Snapshot, changes: tuple[Change, ...], after: Snapshot
) -> None:
    """Refuse foreign, reordered or incomplete writer results before UI rebasing."""

    def domain(snapshot: Snapshot) -> tuple:
        """Include every master metric and its order in the post-write fence."""
        return (
            snapshot.package_id,
            snapshot.current_master,
            tuple(
                (master.name, master.x_height, master.caps_height)
                for master in snapshot.masters
            ),
        )

    values = {change.master: change.after for change in changes}
    if domain(before) != domain(after) or any(
        not result_matches(values[old.name], new.zones, old.zones)
        if old.name in values
        else old.zones != new.zones
        for old, new in zip(before.masters, after.masters, strict=True)
    ):
        raise ValueError(
            "Zone write result differs from the complete plan; inspect Undo and reopen."
        )


def show(backend: Backend) -> Any:
    """Replace only the previous owned modeless panel; require explicit native I/O."""
    from fontlabapp.metrics.zones.ui import AlignmentZonesDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(partial(AlignmentZonesDialog, backend=backend), KEY)
