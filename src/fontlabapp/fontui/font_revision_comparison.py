# this_file: src/fontlabapp/fontui/font_revision_comparison.py
# SPDX-License-Identifier: Apache-2.0
"""S62 Font Revision Comparison: cross-font difference reports.

Routes reuse the capture/render pair of Report Composite Differences and Report
Glyph Set Differences (current font against the other open fonts). Read-only.
Compare Open Font Revisions keeps its own Scriptmix dialog (no snapshot model)
and is not routed here.
"""

from typing import Any

from .snapshot_audit import show_snapshots

ABOUT = (
    "Font Revision Comparison: composite and glyph-set differences between open fonts, read-only.\n"
    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
    "Menus: https://github.com/fontlabcom/fontlab-python-scriptmix\n"
    "Credits: Jens Kutilek (MIT, Copyright (c) 2017) composite and glyph-set workflows; FontLab App contributors (Apache-2.0)."
)


def routes() -> tuple:
    """Build the route table lazily so importing stays free of native modules."""
    from time import monotonic

    from fontlabapp.proof.crossfont import model, native

    state: dict = {}

    def capture(composites: bool):
        # One absolute 3.5 s deadline bounds the capture and the following render (as the old dialog did).
        state["deadline"] = monotonic() + 3.5
        return native.capture(composites=composites, deadline=state["deadline"])

    def render(function):
        return lambda snapshot: function(snapshot, deadline=state.get("deadline"))

    return (
        ("Report Composite Differences",
         "Current font against the first other open font: composite base differences on the selected master.",
         lambda: capture(True), render(model.composite_text),
         lambda snapshot: "Current font \u2192 first other open font."),
        ("Report Glyph Set Differences",
         "Current font against every other open font: glyphs present in one but not the other.",
         lambda: capture(False), render(model.glyph_sets_text),
         lambda snapshot: "Current font \u2192 every other open font."),
    )


def show(*, only: str | None = None, parent: Any = None) -> Any:
    """Open Font Revision Comparison, or only the named report's tab."""
    return show_snapshots("Font Revision Comparison", routes(), ABOUT, parent=parent, only=only)
