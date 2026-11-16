# this_file: src/fontlabapp/masters/switcher/model.py
# SPDX-License-Identifier: Apache-2.0
"""Original compact font-master labels and switching.

The menu uses these helpers. Master order follows the first axis, then font order
when no axis exists. Set the package master without editing outlines or widths,
and without a global refresh (``switch``).
"""

import contextlib
from typing import Any

from fontlabapp.masters.inspect.model import master_order


def location_label(package: Any, master: str) -> str:
    """Keep original numeric axis locations and omit unavailable coordinates."""
    location = package.location(master)
    parts = []
    for axis in package.axes:
        with contextlib.suppress(Exception):
            parts.append(f"{location[axis.shortName]:g}")
    return " · ".join(parts)


def button_values(package: Any | None) -> tuple[tuple[str, str], ...]:
    """Read every ordered master/label before creating actionable buttons."""
    if package is None:
        return ()
    masters = master_order(package)
    if len(masters) != len(set(masters)):
        raise ValueError("Master names must be unique before switching.")
    return tuple((master, location_label(package, master)) for master in masters)


def switch(package: Any, master: str) -> None:
    """Set a known font master with ``setMaster(master, True)``. Call no refresh.

    FontLab 9.0.9790 (issue 122 M1): ``UpdateAll()`` queued glyph ids in
    ``flGlyph.updatedFgGlyphs()`` (FontLab issue 8537) and changed no pixel in
    the Font window. ``setMaster`` alone gave the same state with an empty
    queue. Do not add ``notifyPackageContentUpdated``: it reverted the master.
    """
    if master not in package.masters:
        raise ValueError(f"Unknown master: {master!r}")
    package.setMaster(master, True)
