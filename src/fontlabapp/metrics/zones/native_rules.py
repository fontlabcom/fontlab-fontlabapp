# this_file: src/fontlabapp/metrics/zones/native_rules.py
# SPDX-License-Identifier: Apache-2.0
"""Source-derived native alignment-zone kind rule; no host imports or writes."""

DIRECTION_EPSILON = 0.00001


def is_top(width: float, name: str, position: float) -> bool:
    """Keep updateZonesFromGuidelines/flZone::isTop's near-zero classification.

    Empty names are guaranteed a B prefix before native classification. Do not
    silently turn a nameless zero-width zone at positive y into a Top zone.
    """
    if width > DIRECTION_EPSILON:
        return True
    if width < -DIRECTION_EPSILON:
        return False
    lower = name.lower()
    if lower in ("asc", "caps", "xhgt", "fig") or lower.startswith("t"):
        return True
    if (
        not lower
        or lower in ("dsc", "base", "comma", "parenleft")
        or lower.startswith("b")
    ):
        return False
    return position > 0
