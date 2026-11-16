# this_file: src/fontlabapp/glyphs/case_coverage/controller.py
# SPDX-License-Identifier: Apache-2.0
"""Run complete detached case reports and explicitly requested proof UI actions."""

from collections.abc import Callable
from time import monotonic
from typing import Any
from fontlabapp import _native
from fontlabapp.glyphs.case_coverage.model import Options, checkpoint
from fontlabapp.glyphs.case_coverage.capture import Snapshot, read, validate
from fontlabapp.glyphs.case_coverage.ui import panel_type
from fontlabapp.proof.reports.model import show_report
from fontlabapp.glyphs.case_coverage.targets import TargetChoiceRequired, ProofFailure
from fontlabapp.core.scripting import current_package, show_script_dialog


def run(
    options: Options,
    metadata: Callable,
    preferred: Callable,
    *,
    cancelled: Callable = lambda: False,
    clock: Callable = monotonic,
    proof: Callable | None = None,
    choices: dict | None = None,
) -> Snapshot:
    """Stage every font before proofs; no issue creates no proof view.

    One shared deadline covers capture, analysis, preflight and proof cleanup.
    Native getters/senders cannot be preempted, so check immediately on return.
    """
    deadline = clock() + 3.0
    check = lambda: checkpoint(deadline, clock, cancelled)
    check()
    snapshot = read(
        options,
        metadata,
        preferred,
        clock=clock,
        cancelled=cancelled,
        deadline=deadline - 0.5,
    )
    validate(
        snapshot,
        deadline - 0.5,
        check=lambda: checkpoint(deadline - 0.5, clock, cancelled),
    )
    has_proof = False
    for font in snapshot.fonts:
        check()
        has_proof = has_proof or bool(font.report["proof"])
    if has_proof:
        if proof is None:
            from fontlabapp.glyphs.case_coverage.proof import open_proofs

            proof = open_proofs
        try:
            proof(
                snapshot,
                options,
                deadline=deadline,
                cancelled=cancelled,
                choices=choices or {},
            )
        except TargetChoiceRequired as error:
            error.snapshot = snapshot
            raise
        except Exception as error:
            raise ProofFailure(snapshot, error) from error
    check()
    return snapshot


def details(
    snapshot: Snapshot,
    *,
    clock: Callable = monotonic,
    cancelled: Callable = lambda: False,
) -> Any:
    """Stage every complete detached report under a deadline before owned UI.

    Copy only the small outer record shell; bounded shared serialization walks
    the complete existing report data without recursive asdict or truncation.
    """
    deadline = clock() + 3.0
    check = lambda: checkpoint(deadline, clock, cancelled)
    check()
    fonts = []
    for font in snapshot.fonts:
        check()
        fonts.append(
            dict(
                identity=font.identity,
                fg_id=font.fg_id,
                label=font.label,
                master=font.master,
                report=font.report,
            )
        )
    check()
    return show_report(
        dict(current_id=snapshot.current_id, fonts=fonts),
        title="Case Coverage — detailed report",
        key="case_coverage_details",
        deadline=deadline,
        clock=clock,
        cancelled=cancelled,
    )


def show(metadata: Callable, preferred: Callable, *, settings: Any = None) -> Any:
    """Open native theme controls; settings injection isolates native test probes."""
    qt = _native("PythonQt")
    kind = panel_type(qt.QtCore, qt.QtGui)
    return show_script_dialog(
        lambda parent: kind(
            parent,
            lambda options, cancelled, choices: run(
                options, metadata, preferred, cancelled=cancelled, choices=choices
            ),
            lambda: current_package() is not None,
            details,
            settings=settings,
        ),
        "case_coverage",
    )
