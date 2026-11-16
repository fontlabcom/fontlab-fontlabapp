# this_file: src/fontlabapp/proof/tabs/text.py
# SPDX-License-Identifier: MIT
"""Open a native literal-text Glyph tab without an application-wide event loop.

Use FontLab's native doCreateTextBlock(QString), not a Glyphs text parser that
rejects missing characters. Preserve pre-existing shape activation flags around
creation, including the previously rendered block. Native content, font/history
preservation and missing-character behavior still require owned qualification.
Activation preservation follows Glyport model/navigation.py; see NOTICE.
"""

from collections.abc import Callable
from time import monotonic
from typing import Any

import fontlabapp.core.native_tabs as _tabs
from fontlabapp import _native
from fontlabapp.core.scripting import current_package


def _check(deadline: float) -> None:
    """Stop a slow preflight before tab creation; native calls are not preemptible."""
    if monotonic() >= deadline:
        raise TimeoutError("Text-tab preflight exceeded its deadline; no tab opened.")


def _remember(package: Any, names: Any, states: dict, deadline: float) -> None:
    """Retain original native shape active flags without reading fgGlyph/fgPackage."""
    seen = set()
    for name in names:
        _check(deadline)
        if name in seen:
            continue
        seen.add(name)
        glyph = package.findName(name)
        if glyph is None:
            continue
        for layer in glyph.layers:
            _check(deadline)
            for shape in layer.shapes:
                _check(deadline)
                if hasattr(shape, "active") and shape.id not in states:
                    states[shape.id] = shape, bool(shape.active)


def _snapshot(native: Any, workspace: Any, package: Any, deadline: float) -> dict:
    """Include the target font and an old rendered block of another font."""
    states: dict = {}
    font = native.CurrentFont()
    if font is None:
        raise ValueError("The current font disappeared before text-tab creation.")
    _remember(package, (glyph.name for glyph in font.glyphs), states, deadline)
    block = _tabs.rendered_block(workspace)
    if block is not None:
        _remember(
            block.package,
            (info.glyph.name for info in block.getAllGlyphs() or ()),
            states,
            deadline,
        )
    return states


def _restore(states: dict) -> None:
    """Attempt every saved flag restoration before reporting native failures."""
    errors = []
    for shape, active in states.values():
        try:
            if shape.active != active:
                shape.active = active
        except Exception as error:  # noqa: BLE001 - finish all native restoration attempts
            errors.append(error)
    if errors:
        raise ExceptionGroup("Text-tab activation restoration failed.", errors)


def open_text_tab(text: str, *, expected_id: int) -> None:
    """Open exactly one new native text tab bound to the captured current font.

    Build text before calling. Refuse a switched/closed font or slow preflight
    before connecting an owned hidden QLineEdit to the native private slot.
    Disconnect before deleting that sender on every path. No event pumping,
    current-font switch, Output/history/preference writer or user-tab reuse.
    Native failure can leave a new tab: no atomic UI rollback is claimed.
    """
    if not isinstance(text, str):
        raise TypeError("Text for a Glyph tab must be a string.")
    _open_tab(text, expected_id=expected_id, deadline=monotonic() + 2.0)


def _open_tab(
    text: str,
    *,
    expected_id: int,
    deadline: float,
    populate: Callable[[], None] | None = None,
    expected_master: str | None = None,
) -> None:
    """Share creation; populate only a verified new tab for named-symbol callers."""
    package = current_package(expected_id)
    if package is None:
        raise ValueError("The source font changed or closed; run the proof again.")
    native = _native("fontlab")
    workspace = native.flWorkspace.instance()
    main = native.MainWindow()
    if main is None:
        raise RuntimeError("FontLab main window is unavailable.")
    states = _snapshot(native, workspace, package, deadline)
    _check(deadline)
    if current_package(expected_id) is None:
        raise ValueError("The source font changed during preflight; run again.")
    previous = _tabs.rendered_block(workspace) if populate is not None else None
    previous_id = int(previous.id) if previous is not None else None
    if expected_master is not None and package.master != expected_master:
        raise ValueError("The source master changed; run the proof again.")
    gui = _native("PythonQt").QtGui
    with _tabs.text_tab_sender(
        gui,
        main,
        bootstrap_text=(
            "fontlabapp-before-connect" if text != "fontlabapp-before-connect" else ""
        ),
        connection_error=RuntimeError(
            "FontLab text-tab slot connection is unavailable."
        ),
        disconnection_error=RuntimeError("FontLab text-tab slot disconnect failed."),
        before_disconnect=lambda: _restore(states),
    ) as emitter:
        _check(deadline)
        emitter.setText(text)
        if populate is not None:
            # Native fact (scriptsweep probe 2026-11-03): a fresh tab has no active
            # text block; it is the active canvas's first block, with a new id.
            block = _tabs.rendered_block(workspace)
            if block is None or int(block.id) == previous_id:
                raise ValueError(
                    "No new Glyph tab became active; existing tabs were not populated."
                )
            if int(block.package.id) != expected_id:
                raise ValueError(
                    "The new Glyph tab belongs to another font; it was not populated."
                )
            populate()
