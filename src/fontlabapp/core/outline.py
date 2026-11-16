# this_file: src/fontlabapp/core/outline.py
# SPDX-License-Identifier: Apache-2.0
"""Native outline reads that studios may not reach directly.

What: ``merged_copy(shape)`` returns a detached FontGate copy of a native
``flShape`` with its overlaps removed (the Scriptmix Remove Overlap route:
``convertToFgShape`` then ``fgShape.removeOverlap``), and ``font_info``
returns fontpr's ``get_font_info`` JSON for a package, which carries every
master's metrics and stems without switching the current master.
Why: the studio boundary refuses ``fontgate`` and ``fontlabapp._native``;
the Outline Doctor (``fontlabapp.studios.outline_doctor``) calls these.
Neither function writes the font. Only ``convertToFgShape``, ``removeOverlap``
and the copy's ``contours``/``countNodes`` are touched: probing other
FontGate attributes has crashed the host (AGENTS.md, Issue 235).
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.core import scripting


def merged_copy(shape: Any, *, fontgate: Any = None) -> Any:
    """A detached ``fgShape`` copy of ``shape`` with overlaps removed (no write)."""
    module = fontgate if fontgate is not None else _native("fontgate")
    result = module.fgShape()
    shape.convertToFgShape(result)
    result.removeOverlap()
    return result


def node_counts(copy: Any) -> tuple[int, ...]:
    """Sorted node counts of every contour of a FontGate copy."""
    return tuple(sorted(int(contour.countNodes()) for contour in copy.contours))


def font_info(package: Any, *, fontpr: Any = None) -> dict[str, Any]:
    """fontpr ``get_font_info`` for ``package`` (read-only; ValueError when unreadable)."""
    module = fontpr if fontpr is not None else _native("fontpr")
    data = module.call("get_font_info", font_id=scripting.font_id(package))
    if not isinstance(data, dict):
        raise ValueError("Unreadable native font info.")
    return data


def master_measures(data: dict[str, Any], master: str) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """(ascender, cap height, x height, descender), horizontal and vertical stems of ``master``.

    Reads the ``fontMaster`` record whose name matches ``master`` (before any
    ``:``/``#``/``@`` suffix) in ``font_info`` data, as Close But No Cigar did.
    """
    import re

    name = re.split(r"[:#@]", master, maxsplit=1)[0]
    masters = data.get("masters")
    if not isinstance(masters, (list, tuple)):
        raise ValueError("Unreadable native master domain.")
    matches = [entry["fontMaster"] for entry in masters
               if isinstance(entry, dict) and isinstance(entry.get("fontMaster"), dict)
               and entry["fontMaster"].get("name") == name]  # fmt: skip
    if len(matches) != 1:
        raise ValueError(f"Master {name} has no unique native record.")
    record = matches[0]
    metrics = tuple(float(record.get(key, 0)) for key in ("ascender", "capsHeight", "xHeight", "descender"))
    stems = []
    for key in ("fontStemsH", "fontStemsV"):
        values = record.get(key, [])
        if not isinstance(values, (list, tuple)) or any(not isinstance(v, dict) for v in values):
            raise ValueError("Unreadable associated-master stem list.")
        stems.append(tuple(float(v.get("value", 0)) for v in values))
    return metrics, stems[0], stems[1]
