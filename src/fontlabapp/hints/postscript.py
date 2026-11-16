# this_file: src/fontlabapp/hints/postscript.py
# SPDX-License-Identifier: Apache-2.0
"""PostScript hint counts of a layer, by FontLab's hint role.

What: ``hint_counts(layer)`` returns the (horizontal, vertical) counts of the
PostScript stem hints of a layer. Contours > Autohint Selected Layers and
Remove PostScript Hints show these counts before and after a write.

How: a hint is a guide object with ``isHint``. Its direction is its role,
read with the callable ``isHorizontal()`` and ``isVertical()`` of
``flGuideLine`` (the same calls as ``fontlabapp.metrics.zones.capture``).

Why the role and not the angle: ``flLayer.removeHints(horizontal,
vertical)`` selects hints by the role flag (source: ``fllayer.cpp:6293-6312``,
``flsnapline.cpp:4377-4389``), not by the angle that ``isVerticalQuarter``
tests. So these counts agree with what FontLab removes. A hint with neither
role is in neither count; FontLab's ``removeHints`` removes such a hint in
every direction. Plain guidelines are not counted.

This module imports nothing at load time beyond typing. Offline tests do not
prove native FontLab behaviour.

How to use (a script)::

    import fly.ap.hints.postscript as hints

    horizontal, vertical = hints.hint_counts(layer)
"""

from typing import Any


def hint_counts(layer: Any) -> tuple[int, int]:
    """Return (horizontal, vertical) PostScript hint counts of ``layer``, by role.

    A hint with neither role is in neither count. Plain guidelines are not
    counted.
    """
    found = [guide for guide in layer.guidelines if guide.isHint]
    horizontal = sum(1 for guide in found if guide.isHorizontal())
    vertical = sum(1 for guide in found if guide.isVertical())
    return horizontal, vertical


__all__ = ["hint_counts"]
