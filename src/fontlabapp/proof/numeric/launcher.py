# this_file: src/fontlabapp/proof/numeric/launcher.py
# SPDX-License-Identifier: Apache-2.0
"""Launch both original numeric profiles around captured FontLab font facts.

Use the registered current package, selected-layer reader and whole-font revision
reader. Compare complete captures before publication. No selected glyph, metric,
font, history, preference, file, clipboard or Output writer is used. Native
getter/cache preservation and actual PythonQt lifetime remain unqualified.
"""

from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp.proof.numeric.model import Facts


def _once(deadline: float) -> tuple:
    """Capture typed scalar facts while fencing package/master/UPM identity."""
    from fontlabapp.glyphs.catalog.native import capture as revisions
    from fontlabapp.metrics.worksheet.capture import capture as advances
    from fontlabapp.core.scripting import current_package

    if monotonic() >= deadline:
        raise TimeoutError("Font measurement capture expired.")
    package = current_package()
    if package is None:
        raise ValueError("Open a font and select glyph layers before refreshing.")
    context = (int(package.id), package.master, package.upm)
    selected = advances()
    table = revisions(deadline=deadline)
    current = current_package(context[0])
    if (
        current is None
        or (int(current.id), current.master, current.upm) != context
        or tuple(selected.context[:2]) != context[:2]
    ):
        raise ValueError("Font, master or UPM changed; refresh the worksheet.")
    if len(table.rows) != len(table.epochs):
        raise ValueError("The revision table is incomplete.")
    return (
        context,
        Facts(
            context[2],
            tuple((r.glyph_name, r.layer_name, r.width) for r in selected.rows),
            tuple(
                (row[0], epoch)
                for row, epoch in zip(table.rows, table.epochs, strict=True)
            ),
        ),
        selected,
    )


def capture() -> Facts:
    """Publish only equal complete passes within one two-second outer budget.

    Existing readers fence each selected occurrence and revision. The outer
    comparison also keeps their combined observations stable. Native blocking
    getters cannot be preempted. This is an observation fence, not proof that
    host getters preserve internal caches; native qualification is separate.
    """
    if current_thread() is not main_thread():
        raise RuntimeError("Capture numeric font facts on the main UI thread.")
    deadline = monotonic() + 2.0
    first, second = _once(deadline), _once(deadline)
    if monotonic() >= deadline:
        raise TimeoutError("Font measurement capture expired; no partial result.")
    if first != second:
        raise ValueError("Font measurements or revisions changed; refresh all facts.")
    return first[1]


def _show(part: int) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open the numeric worksheet on the main UI thread.")
    from fontlabapp import _native
    from fontlabapp.core.scripting import show_script_dialog
    from fontlabapp.proof.numeric.ui import panel_type

    qt = _native("PythonQt")
    kind = panel_type(qt.QtCore, qt.QtGui)
    return show_script_dialog(
        lambda parent: kind(parent, capture, part), f"glyph_numeric_{part}"
    )


def show() -> Any:
    """Open the complete part2 glyph metrics/revision worksheet."""
    return _show(2)


def show_detailed() -> Any:
    """Open part3 with special values and historical revision ranges."""
    return _show(3)
