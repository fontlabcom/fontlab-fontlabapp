# this_file: src/fontlabapp/qt/compact.py
"""Compact, native-like layout metrics for script dialogs and palettes.

FontLab's own panels (Proteus ``.ui`` files) use 0-8 px margins and 0-4 px
spacing; Qt's style defaults (about 11-20 px on macOS) waste space. A
standalone script needs one line::

    from fontlabapp.ui import compact_dialog
    dialog, layout = compact_dialog("My tool")

An existing window can be tightened in place with ``compact(widget)``.
Glyph views go frameless into the top or right half with ``split_view``.
Colours are not set here: widgets keep the host QPalette, so the light and
dark FontLab themes both apply.
"""

from __future__ import annotations

from typing import Any

MARGIN = 6  # outer margin of a dialog or palette, px (Proteus panels: 4-8)
SPACING = 4  # gap between controls, px (Proteus panels: 0-4)
SIDES = ("top", "right")


def compact_layout(layout: Any, margin: int = MARGIN, spacing: int = SPACING) -> Any:
    """Set ``layout``'s margins to ``margin`` and its spacing to ``spacing``.

    Objects without the Qt layout setters (test doubles, partial wrappers)
    are returned unchanged: compaction is cosmetic and must not break a window.
    """
    margins = getattr(layout, "setContentsMargins", None)
    if margins is not None:
        margins(margin, margin, margin, margin)
    spacing_setter = getattr(layout, "setSpacing", None)
    if spacing_setter is not None:
        spacing_setter(spacing)
    return layout


def compact(widget: Any, margin: int = MARGIN, spacing: int = SPACING) -> Any:
    """Tighten every layout under ``widget``: its own layout gets ``margin``.

    Nested layouts keep zero margins and get ``spacing``. Layouts inside
    child widgets (group boxes, tabs) get ``spacing`` and their own margin
    only when it is larger than ``margin``. Returns ``widget``.
    """
    own = widget.layout()
    if own is not None:
        compact_layout(own, margin, spacing)
    qt = _qt()
    for layout in widget.findChildren(qt.QtGui.QLayout):
        if own is not None and _same(layout, own):
            continue
        layout.setSpacing(spacing)
        if _parent_is_layout(layout):
            continue
        _cap_margins(layout, margin)
    return widget


def _same(left: Any, right: Any) -> bool:
    try:
        return bool(left == right)
    except Exception:  # noqa: BLE001 - wrapper comparison is optional
        return left is right


def _parent_is_layout(layout: Any) -> bool:
    parent = layout.parent()
    return parent is not None and hasattr(parent, "addItem")


def _cap_margins(layout: Any, margin: int) -> None:
    margins = layout.contentsMargins()
    sides = [_side(margins, name) for name in ("left", "top", "right", "bottom")]
    if any(side > margin for side in sides):
        layout.setContentsMargins(*[min(side, margin) for side in sides])


def _side(margins: Any, name: str) -> int:
    found = getattr(margins, name)
    return int(found() if callable(found) else found)


def frameless(view: Any) -> Any:
    """Drop the frame of a scroll area or graphics view; other widgets pass."""
    if hasattr(view, "setFrameShape"):
        view.setFrameShape(_qt().QtGui.QFrame.NoFrame)
    return view


def split_view(layout: Any, view: Any, controls: Any, side: str = "top") -> Any:
    """Put ``view`` frameless in the top or right half of ``layout``.

    ``layout`` is the window's outer box layout; it gets zero margins so the
    view reaches the window edges. ``controls`` (a widget with a compact
    layout, see ``controls_box``) goes below or to the left. The view takes
    all extra space. Returns ``layout``.
    """
    if side not in SIDES:
        raise ValueError(f"side must be one of {SIDES}, not {side!r}")
    compact_layout(layout, 0, 0)
    frameless(view)
    if side == "top":
        layout.addWidget(view, 1)
        layout.addWidget(controls)
        return layout
    row = _qt().QtGui.QHBoxLayout()
    compact_layout(row, 0, 0)
    row.addWidget(controls)
    row.addWidget(view, 1)
    layout.addLayout(row, 1)
    return layout


def controls_box(parent: Any) -> tuple[Any, Any]:
    """Return ``(widget, layout)``: a child of ``parent`` with a compact column."""
    gui = _qt().QtGui
    widget = gui.QWidget(parent)
    return widget, compact_layout(gui.QVBoxLayout(widget))


def compact_dialog(title: str = "", parent: Any = None) -> tuple[Any, Any]:
    """Return ``(dialog, layout)``: a modeless QDialog with compact metrics.

    ``parent`` defaults to FontLab's main window when it can be found, so the
    dialog stays above it. Add widgets to ``layout`` and call ``dialog.show()``.
    """
    gui = _qt().QtGui
    dialog = gui.QDialog(_main_window() if parent is None else parent)
    dialog.setWindowTitle(title)
    dialog.setModal(False)
    return dialog, compact_layout(gui.QVBoxLayout(dialog))


def _main_window() -> Any:
    app = _qt().QtGui.QApplication.instance()
    if app is None:
        return None
    for widget in app.topLevelWidgets():
        if widget.inherits("QMainWindow"):
            return widget
    return None


def _qt() -> Any:
    from fontlabapp import _native

    return _native("PythonQt")
