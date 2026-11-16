# this_file: src/fontlabapp/proof/reports/specialized_ui.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Shared owned read-only reports: Refresh, selectable text and safe Close."""

from typing import Any

from fontlabapp.masters.node_report import (
    model as master_node_report,
    native as master_node_report_native,
)
from fontlabapp.contours.svg_path import (
    model as svg_path_commands,
    native as svg_path_commands_native,
)
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


class MasterNodeReportDialog(SnapshotTextDialog):
    """Keep Reset's complete first-master report in the shared lifecycle."""

    KEY = "master_node_report"

    def __init__(self, parent: Any = None) -> None:
        super().__init__(
            parent,
            "Master Node Compatibility Report",
            self.KEY,
            "Selected glyphs, every master against the first: paths, nodes, lines, curves, handles, total points and first differing node. Repairs equal-count type mismatches and missing trailing paths. Structural checks only.",
            master_node_report_native.capture,
            master_node_report.render,
            lambda rows: f"{len(rows)} unique selected glyphs. No font changes.",
        )


class SvgPathCommandsDialog(SnapshotTextDialog):
    """Preserve Simon's own-path-only and unconditional Z command contract."""

    KEY = "svg_path_commands"

    def __init__(self, parent: Any = None) -> None:
        super().__init__(
            parent,
            "Dump to SVG Path Commands",
            self.KEY,
            "First selected layer, own paths only. M/L/C commands; Z and a blank line after every contour, including open and empty contours, as in the original. Components are omitted. Own affine shape transforms are applied. Quadratic/unsupported segments and projective transforms refuse the whole report. This is not a complete SVG document.",
            svg_path_commands_native.capture,
            svg_path_commands.render,
            lambda rows: f"{len(rows)} own paths. No font or file changes.",
        )
