# this_file: src/fontlabapp/proof/extrema/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Retain all-layer extrema coordinates beside the required exact-layer proof."""

from typing import Any

from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog
from fontlabapp.proof.extrema.model import ProofError, run
from fontlabapp.masters.layers.extrema.model import render


def _result() -> tuple:
    """Retain source coordinate messages even if the subsequent proof tab fails."""
    try:
        return run("all"), ""
    except ProofError as error:
        return error.result, str(error)


class ExtremaDialog(SnapshotTextDialog):
    """Reuse complete owned report/completion mechanics; Run Again opens a tab."""

    KEY = "highest_lowest_layers"

    def __init__(self, parent: Any = None) -> None:
        super().__init__(
            parent,
            "Highest & Lowest Glyphs",
            self.KEY,
            "Scan every foreground master and auxiliary layer. Show both exact winners in a new Glyph tab.",
            _result,
            lambda result: render(result[0]),
            lambda result: result[1] or "Two exact layers opened in a new tab.",
        )
        self.refresh_button.setText("Run Again")
        self.resize(620, 300)
