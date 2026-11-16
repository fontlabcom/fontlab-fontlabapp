# this_file: src/fontlabapp/masters/node_report/model.py
# SPDX-License-Identifier: Apache-2.0
"""Reset Type Studio's complete per-master node report; see NOTICE.

Compare every ordered master with the first. Repair the original equal-count
node-type omission and missing trailing reference-path omission explicitly.
This structural report is not a font export compatibility certificate.
"""

from itertools import zip_longest
from typing import Any

from fontlabapp.masters.layers.compatibility.model import GlyphLayers


def compare_path_nodes(reference: tuple, tested: tuple) -> tuple | None:
    """Return the first differing zero-based index and original type names."""
    for index, (left, right) in enumerate(zip_longest(reference, tested)):
        if left != right:
            return index, left, right
    return None


def _counts(path: tuple) -> tuple[int, int]:
    """Count on-curves and handles, including quadratic endpoints as curves."""
    handles = path.count("offcurve")
    return len(path) - handles, handles


def _master(name: str, paths: tuple) -> list[str]:
    """Retain all original per-path counters for this master, in path order."""
    lines = [f"\n    ⭕️ Master: {name}", f"     • Paths: {len(paths)}"]
    for path in paths:
        on, off = _counts(path)
        curves = path.count("curve") + path.count("qcurve")
        lines.extend(
            (
                f"     • Nodes: {on} (Lines: {path.count('line')} · Curves: {curves})",
                f"     • Handles: {off}",
                f"     • Total Points: {len(path)}",
            )
        )
    return lines


def _differences(reference: tuple, paths: tuple, master: str) -> list[str]:
    """Check path presence both ways and types even when counts are equal."""
    result = []
    for i, (left, right) in enumerate(zip_longest(reference, paths), 1):
        prefix = f"  ⚠️ Incompatibility in master '{master}':"
        if left is None or right is None:
            where = "reference" if left is None else "tested"
            result.append(f"{prefix} Path #{i} → Path missing in {where} master.")
            continue
        mismatch = compare_path_nodes(left, right)
        if mismatch is None:
            continue
        index, expected, found = mismatch
        result.extend(
            (
                prefix,
                f"     • Path #{i} mismatch → Expected {_counts(left)}, Found {_counts(right)}",
                f"     • First difference at node #{index + 1}: Expected {expected.upper() if expected else '—'}, Found {found.upper() if found else '—'}",
            )
        )
    return result


def render(groups: tuple[GlyphLayers, ...]) -> str:
    """Render all counters and reference comparisons without partial results."""
    if not groups:
        raise ValueError("No glyph selected.")
    lines = []
    for group in groups:
        if not group.layers:
            raise ValueError("A glyph has no master layers.")
        lines.append(f"🔠 Glyph: {group.name}")
        for layer in group.layers:
            lines.extend(_master(layer.name, layer.paths))
        differences = []
        for layer in group.layers[1:]:
            differences.extend(
                _differences(group.layers[0].paths, layer.paths, layer.name)
            )
        lines.extend(differences)
        lines.extend(
            (
                "",
                "-" * 100,
                "  ⚠️ Masters are not compatible with the reference master."
                if differences
                else "  ✅ All masters are fully compatible with the reference master.",
            )
        )
    return "\n".join(lines)


def show() -> Any:
    """Open the shared owned Refresh/Close report through Fly/App dispatch."""
    from fontlabapp.proof.reports.specialized_ui import MasterNodeReportDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(MasterNodeReportDialog, MasterNodeReportDialog.KEY)
