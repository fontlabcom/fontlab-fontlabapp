# this_file: src/fontlabapp/fontui/metric_reports.py
# SPDX-License-Identifier: Apache-2.0
"""S63 Metric Reports: vertical metrics over the existing snapshot owner.

The route reuses the capture/render pair of Vertical Metrics Reporter. Read-only.
Sidebearing Direction Marker is a live Glyph-window overlay, not a snapshot
report; it stays its own Scriptmix dialog and is not routed here.
"""

from typing import Any

from .snapshot_audit import show_snapshots

ABOUT = (
    "Metric Reports: vertical metrics of every master in every open font, read-only.\n"
    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
    "Menus: https://github.com/fontlabcom/fontlab-python-scriptmix\n"
    "Credits: Pedro Arilla (Apache-2.0) vertical metrics reporter; FontLab App contributors (Apache-2.0)."
)


def routes() -> tuple:
    """Build the route table lazily so importing stays free of native modules."""
    from fontlabapp.metrics.vertical import model, native

    return (
        ("Vertical Metrics Reporter",
         "Eight stored vertical metric values for every master in every open font.",
         native.capture, model.render,
         lambda report: f"Snapshot: {report.fonts} fonts, {len(report.rows)} masters. Refresh after changes."),
    )


def show(*, only: str | None = None, parent: Any = None) -> Any:
    """Open Metric Reports, or only the named report's tab."""
    return show_snapshots("Metric Reports", routes(), ABOUT, parent=parent, only=only)
