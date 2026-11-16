# this_file: src/fontlabapp/fontui/master_structure_audit.py
# SPDX-License-Identifier: Apache-2.0
"""S61 Master Structure Audit: master and layer compatibility reports.

Routes reuse the capture/render pair of Master Node Compatibility Report and
Why You Not Compatible?. Structural source checks only; read-only; not an
export-compatibility certificate.
"""

from typing import Any

from .snapshot_audit import show_snapshots

ABOUT = (
    "Master Structure Audit: structural compatibility reports, read-only.\n"
    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
    "Menus: https://github.com/fontlabcom/fontlab-python-scriptmix\n"
    "Credits: Fernando D\u00edaz and Reset Type Studio (Apache-2.0, 2025) Master Node Compatibility Report; Simon Cozens (MIT) Why You Not Compatible; FontLab App contributors (Apache-2.0)."
)


def routes() -> tuple:
    """Build the route table lazily so importing stays free of native modules."""
    from fontlabapp.masters.layers.compatibility import model as layers_model, native as layers_native
    from fontlabapp.masters.node_report import model as node_model, native as node_native

    return (
        ("Master Node Compatibility Report",
         "Selected glyphs, every master against the first: paths, nodes, lines, curves, handles and first differing node.",
         node_native.capture, node_model.render,
         lambda rows: f"{len(rows)} unique selected glyphs. No font changes."),
        ("Why You Not Compatible",
         "Adjacent foreground layers: path and node counts and types, anchor and component name sets.",
         layers_native.capture, layers_model.render,
         lambda rows: f"Snapshot: {len(rows)} selected occurrences. Refresh after changes."),
    )


def show(*, only: str | None = None, parent: Any = None) -> Any:
    """Open Master Structure Audit, or only the named report's tab."""
    return show_snapshots("Master Structure Audit", routes(), ABOUT, parent=parent, only=only)
