# this_file: src/fontlabapp/glyphs/case_coverage/views.py
# SPDX-License-Identifier: Apache-2.0
"""Capability-checked exact native proof models and verified named content.

Source: pyflworkspace.cpp canvases/setActiveCanvas; pyflcanvas.cpp textBlocks;
pyfltextblock.cpp symbolList; pyfgsymbollist.cpp symbols; pyfgsymbol.cpp name
and layerName. Runtime model normalization and UI effects remain native-held.
"""

from collections.abc import Callable
from typing import Any
from fontlabapp.glyphs.case_coverage.targets import Target
from fontlabapp.core.native_tabs import canvases, rendered_block, text_tab_sender


def active_model(native: Any, workspace: Any) -> Any:
    """Accept only typed models or an actually bound official item.textBlock()."""
    # A fresh or freshly populated tab has no active text block in FontLab 9
    # (native probe 2026-11-03); its model is the active canvas's first block.
    item = rendered_block(workspace)
    if item is None:
        return None
    if isinstance(item, native.flTextBlock):
        return item
    getter = getattr(item, "textBlock", None)
    model = getter() if callable(getter) else None
    if not isinstance(model, native.flTextBlock):
        raise ValueError(
            "FontLab does not expose this active text block's model identity. Activate the intended text block, Refresh and retry; this binding needs native qualification."
        )
    return model


def targets(native: Any, workspace: Any, records: tuple, check: Callable) -> tuple:
    """Enumerate exact typed model identities; no creation-order MRU inference."""
    labels = {}
    for record in records:
        check()
        labels[record.identity] = record.label
    targets, handles = [], {}
    for canvas in canvases(native, workspace):
        check()
        for block in canvas.textBlocks():
            check()
            identity = int(block.package.id)
            if identity in labels:
                target = Target(
                    identity,
                    int(canvas.id),
                    int(block.id),
                    f"{labels[identity]} — view {canvas.id}, block {block.id}",
                )
                targets.append(target)
                handles[(target.canvas_id, target.block_id)] = (canvas, block)
    check()
    return tuple(targets), handles


def verify(
    native: Any,
    workspace: Any,
    expected_id: int,
    expected: tuple,
    check: Callable,
    *,
    block_id: int | None = None,
) -> Any:
    """Refuse silent no-op population and verify every symbol name/layer/repeat."""
    check()
    if workspace.activeFontPanel is not None:
        raise ValueError(
            "Activate the selected Glyph view before proofing; the Font window is active."
        )
    block = active_model(native, workspace)
    if (
        block is None
        or int(block.package.id) != expected_id
        or (block_id is not None and int(block.id) != block_id)
    ):
        raise ValueError(
            "The exact proof text block changed or closed; Refresh and retry."
        )
    actual = []
    for symbol in block.symbolList().symbols():
        check()
        actual.append((str(symbol.name), str(symbol.layerName)))
    check()
    if tuple(actual) != expected:
        raise ValueError(
            "FontLab did not deliver the exact proof content; inspect the selected view and retry."
        )
    check()
    return block


def fresh(
    native: Any,
    workspace: Any,
    package_id: int,
    symbols: Any,
    expected: tuple,
    previous_ids: set[int],
    check: Callable,
    gui: Any,
) -> None:
    """Create and populate only a verified NEW typed model; own one native sender."""
    main = native.MainWindow()
    if main is None:
        raise ValueError("FontLab main window is unavailable; no proof opened.")
    with text_tab_sender(
        gui,
        main,
        bootstrap_text="fontlabapp-case-coverage-bootstrap",
        connection_error=RuntimeError("Proof creation signal connection failed."),
        disconnection_error=RuntimeError("Proof creation signal disconnect failed."),
        before_disconnect=check,
    ) as emitter:
        check()
        emitter.setText("")
        check()
        block = active_model(native, workspace)
        if (
            block is None
            or int(block.id) in previous_ids
            or int(block.package.id) != package_id
        ):
            raise ValueError(
                "No new exact proof target became active; existing content was not replaced."
            )
        if workspace.activeFontPanel is not None:
            raise ValueError(
                "The new proof view is not active; no content was replaced."
            )
        check()
        native.flItems().requestContent(symbols, 0)
        verify(native, workspace, package_id, expected, check, block_id=int(block.id))
