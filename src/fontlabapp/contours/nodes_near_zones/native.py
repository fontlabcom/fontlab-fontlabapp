# this_file: src/fontlabapp/contours/nodes_near_zones/native.py
# SPDX-License-Identifier: Apache-2.0
"""Nodes Near Zones native boundary: font, selection and metrics reads, glyph selection."""

from fontlabapp import _native
from fontlabapp.core import scripting

from .model import NodesNearZonesReport, scan


def selected_names() -> list:
    """Names of the selected glyphs of the current font; empty when unreadable."""
    try:
        fl = _native("FL").fl
        font = fl.font
        return [font[i].name for i in range(len(font)) if fl.Selected(i)]
    except (AttributeError, RuntimeError, TypeError):
        return []


def capture(tolerance: int, whole_font: bool = False) -> NodesNearZonesReport:
    """Scan the selected glyphs (all glyphs when none, or when ``whole_font``)."""
    package = scripting.current_package()
    if package is None:
        raise ValueError("Open a font first.")
    fontlab = _native("fontlab")
    names = ([] if whole_font else selected_names()) or [glyph.name for glyph in fontlab.CurrentFont().glyphs]
    rows = scan(package, names, tolerance, lambda master: fontlab.FontMetrics(package, master),
                _native("PythonQt").QtCore.QPointF)
    return NodesNearZonesReport(package.id, len(names), len(package.masters), tolerance, rows)


def select(report: NodesNearZonesReport, names: list | None = None) -> list:
    """Select ``names`` (default every report glyph), once each, in the font it was scanned from."""
    names = list(dict.fromkeys(row[0] for row in report.rows if names is None or row[0] in names))
    return scripting.select_glyphs(names, package_id=report.package_id)
