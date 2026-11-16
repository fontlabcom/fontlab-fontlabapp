# this_file: src/fontlabapp/fontui/geometry_audit.py
# SPDX-License-Identifier: Apache-2.0
"""S60 Geometry Audit: contour reports over the existing snapshot owners.

Routes reuse the capture/render pair of each original report (Close But No
Cigar, Dangerous Offcurves, Dump to SVG Path Commands, both Point Counters).
All are read-only; Dangerous Offcurves opens its exact-layer proof tab as it
always did. Live Glyph Info, Nodes Near Zones and Open Contours stay Scriptmix
dialogs (no App model) and are not routed here.
"""

from typing import Any

from .snapshot_audit import show_snapshots

ABOUT = (
    "Geometry Audit: contour reports for the selected glyphs, read-only.\n"
    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
    "Menus: https://github.com/fontlabcom/fontlab-python-scriptmix\n"
    "Credits: Simon Cozens (MIT) Close But No Cigar and Dump to SVG; Alex Slobzheninov (Apache-2.0) Dangerous Offcurves and Point Counter; independent implementation inspired by Reza Bohloul's Point Counter (no licence declared; no code copied) for Point Counter (Master Layers); FontLab App contributors (Apache-2.0)."
)


def routes() -> tuple:
    """Build the route table lazily so importing stays free of native modules."""
    from fontlabapp.contours.dangerous_offcurves import model as offcurves_model, native as offcurves_native
    from fontlabapp.contours.near_miss import model as near_model, native as near_native
    from fontlabapp.contours.point_counts import native as counts
    from fontlabapp.contours.svg_path import model as svg_model, native as svg_native
    from fontlabapp.masters.point_counts import model as master_model, native as master_native

    return (
        ("Close But No Cigar",
         "All selected glyph occurrences, strict near-angle, stem-length and node-position checks.",
         near_native.capture, near_model.render,
         lambda rows: f"{len(rows)} selected glyph occurrences. No font changes."),
        ("Dangerous Offcurves",
         "Full-font scan; opens an exact-layer proof tab for the findings.",
         lambda: offcurves_native.run(), offcurves_model.render,
         lambda report: "Dangerous Offcurves refreshed."),
        ("Dump to Svg Path Commands",
         "First selected layer, own paths only. Not a complete SVG document.",
         svg_native.capture, svg_model.render,
         lambda rows: f"{len(rows)} own paths. No font or file changes."),
        ("Point Counter (Master Layers)",
         "Point counts of every master layer for the selected glyphs.",
         master_native.capture, master_model.render,
         lambda rows: f"Snapshot: {len(rows)} master layers. Refresh after changes."),
        ("Point Counter",
         "Own contour nodes in every foreground layer of each selected glyph occurrence.",
         counts.capture, counts.render,
         lambda rows: f"Snapshot: {len(rows)} selected occurrences. Refresh after changes."),
    )


def show(*, only: str | None = None, parent: Any = None) -> Any:
    """Open Geometry Audit, or only the named report's tab."""
    return show_snapshots("Geometry Audit", routes(), ABOUT, parent=parent, only=only)
