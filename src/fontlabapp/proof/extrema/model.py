# this_file: src/fontlabapp/proof/extrema/model.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Run complete current-master or all-foreground extrema proof workflows lazily.

No source body, Glyphs API, selection change, Output writer or async callback is
used. Coordinate/identity reads, symbol building and fresh tab creation share
one deadline. Actual native roles/bounds/tab/history preservation remain gated.
"""

from time import monotonic
from typing import Any

import fontlabapp.masters.layers.extrema.native as bounds
from fontlabapp.masters.layers.extrema.model import Extremes, choose


class ProofError(RuntimeError):
    """Keep valid computed coordinates when native tab creation/population fails."""

    def __init__(self, result: Extremes, error: Exception) -> None:
        self.result = result
        super().__init__(f"Proof tab failed; a new tab may remain: {error}")


def run(mode: bounds.Mode) -> Extremes:
    """Capture/recheck the complete source and open both exact winning layers."""
    from fontlabapp.proof.tabs.named import open_layer_tab

    deadline = monotonic() + 2.0
    before = bounds.capture(mode, deadline)
    result = choose(before.rows)
    if before != bounds.capture(mode, deadline):
        raise ValueError("The complete extrema source changed; run the proof again.")
    try:
        bounds.check(deadline)
        open_layer_tab(
            result.layers,
            expected_id=before.package_id,
            master=before.master,
            deadline=deadline,
        )
    except Exception as error:
        raise ProofError(result, error) from error
    return result


def show_all() -> Any:
    """Open the all-layer proof and retain numeric results in an owned panel.

    The source's highest/lowest coordinate messages stay available without
    overwriting Output. Run Again repeats the complete scan/new-tab workflow.
    """
    from fontlabapp.proof.extrema.ui import ExtremaDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(ExtremaDialog, "highest_lowest_layers")
