# this_file: src/fontlabapp/core/native_tabs.py
# SPDX-License-Identifier: MIT
"""Shared native tab mechanics with injected Qt objects and caller error policy.

No native module is imported here. Callers retain source-font selection, text
parsing, deadlines and restoration policy. Activation contexts preserve the
existing Glyport behavior; App's richer deadline/all-restoration policy stays
in text_tab. See NOTICE for original MIT attribution.
"""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import Any


def rendered_block(workspace: Any) -> Any:
    """Read the active block, then the first canvas block, or None."""
    block = workspace.getActiveTextBlock()
    if block is None:
        canvas = workspace.getActiveCanvas()
        blocks = [] if canvas is None else list(canvas.textBlocks())
        block = blocks[0] if blocks else None
    return block


def canvases(native: Any, workspace: Any) -> list:
    """Every glyph canvas, or only the active one where the binding is broken.

    FontLab 9.0.9804's flWorkspace.canvases() raises TypeError (native probe
    2026-11-03). The active canvas still holds every block a fresh tab could be
    confused with, so new-tab fences stay sound; only reuse choices shrink.
    """
    try:
        return [native.flCanvas(raw) for raw in workspace.canvases()]
    except TypeError:
        active = workspace.getActiveCanvas()
        return [] if active is None else [active]


@contextmanager
def preserve_shape_activation(package: Any, names: Iterable[str]) -> Iterator[None]:
    """Restore original active flags using Glyport's existing first-error policy.

    Keep first-name order, skip absent glyphs/layers and retain the last wrapper
    encountered per native shape id. Callers that need deadline checks or
    aggregate restoration failures use their own snapshot/restoration policy.
    """
    states = {}
    for name in dict.fromkeys(names):
        glyph = package.findName(name)
        if glyph is None:
            continue
        for layer in getattr(glyph, "layers", ()):
            for shape in layer.shapes:
                if hasattr(shape, "active"):
                    states[shape.id] = (shape, bool(shape.active))
    try:
        yield
    finally:
        for shape, active in states.values():
            if shape.active != active:
                shape.active = active


@contextmanager
def preserve_rendered_activation(workspace: Any) -> Iterator[None]:
    """Preserve the old renderer's shape activation while the caller opens a tab."""
    block = rendered_block(workspace)
    if block is None:
        yield
        return
    names = [info.glyph.name for info in block.getAllGlyphs() or ()]
    with preserve_shape_activation(block.package, names):
        yield


@contextmanager
def text_tab_sender(
    qtgui: Any,
    receiver: Any,
    *,
    bootstrap_text: str,
    connection_error: Exception,
    disconnection_error: Exception,
    before_disconnect: Callable[[], None] | None = None,
) -> Iterator[Any]:
    """Own one hidden sender for FontLab's native doCreateTextBlock(QString) slot.

    Set caller-supplied bootstrap before connecting. Yield the sender; the caller
    sets its final text. Run optional caller restoration before disconnecting,
    including bootstrap/connect failures. Delete the sender even if restoration
    or disconnect fails. No Python callback is connected to a native signal.
    Error instances keep caller-specific types/messages/capabilities unchanged.
    """
    emitter = qtgui.QLineEdit()
    connection = ("textChanged(QString)", receiver, "doCreateTextBlock(QString)")
    connected = False
    try:
        emitter.setText(bootstrap_text)
        connected = emitter.connect(*connection)
        if not connected:
            raise connection_error
        yield emitter
    finally:
        try:
            if before_disconnect is not None:
                before_disconnect()
        finally:
            try:
                if connected and not emitter.disconnect(*connection):
                    raise disconnection_error
            finally:
                emitter.deleteLater()
