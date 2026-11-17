# this_file: tests/test_qt_compact.py
"""Compact layout helpers, checked against real Qt widgets (PySide6)."""

from types import SimpleNamespace

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from fontlabapp.qt import compact as mod


@pytest.fixture(autouse=True)
def qt(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(mod, "_qt", lambda: SimpleNamespace(QtGui=QtWidgets))
    return app


def margins(layout):
    m = layout.contentsMargins()
    return (m.left(), m.top(), m.right(), m.bottom())


def test_compact_layout_when_called_then_native_metrics():
    layout = mod.compact_layout(QtWidgets.QVBoxLayout())
    assert margins(layout) == (mod.MARGIN,) * 4
    assert layout.spacing() == mod.SPACING


def test_compact_when_window_has_nested_and_boxed_layouts_then_all_tightened():
    window = QtWidgets.QWidget()
    outer = QtWidgets.QVBoxLayout(window)
    outer.setContentsMargins(20, 20, 20, 20)
    row = QtWidgets.QHBoxLayout()
    outer.addLayout(row)
    box = QtWidgets.QGroupBox("Group", window)
    inner = QtWidgets.QVBoxLayout(box)
    inner.setContentsMargins(2, 30, 2, 30)
    outer.addWidget(box)
    assert mod.compact(window) is window
    assert margins(outer) == (mod.MARGIN,) * 4
    assert row.spacing() == inner.spacing() == mod.SPACING
    assert margins(row) == (0, 0, 0, 0), "nested layouts keep zero margins"
    assert margins(inner) == (2, mod.MARGIN, 2, mod.MARGIN), "only large sides are capped"


def test_compact_when_widget_has_no_layout_then_returns_widget():
    widget = QtWidgets.QLabel("x")
    assert mod.compact(widget) is widget


@pytest.mark.parametrize("side", ["top", "right"])
def test_split_view_when_side_given_then_view_frameless_and_stretched(side):
    window = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(window)
    view = QtWidgets.QScrollArea(window)
    controls, column = mod.controls_box(window)
    column.addWidget(QtWidgets.QPushButton("Apply"))
    assert mod.split_view(layout, view, controls, side) is layout
    assert view.frameShape() == QtWidgets.QFrame.NoFrame
    assert margins(layout) == (0, 0, 0, 0)
    assert margins(column) == (mod.MARGIN,) * 4
    if side == "top":
        assert layout.itemAt(0).widget() is view
        assert layout.stretch(0) == 1
        assert layout.itemAt(1).widget() is controls
    else:
        row = layout.itemAt(0).layout()
        assert row.itemAt(0).widget() is controls
        assert row.itemAt(1).widget() is view
        assert row.stretch(1) == 1


def test_split_view_when_side_unknown_then_value_error():
    layout = QtWidgets.QVBoxLayout()
    with pytest.raises(ValueError, match="side must be one of"):
        mod.split_view(layout, QtWidgets.QWidget(), QtWidgets.QWidget(), "left")


def test_frameless_when_widget_has_no_frame_then_unchanged():
    widget = QtWidgets.QWidget()
    assert mod.frameless(widget) is widget


def test_compact_dialog_when_main_window_exists_then_parented_and_compact():
    main = QtWidgets.QMainWindow()
    dialog, layout = mod.compact_dialog("Tool")
    assert dialog.windowTitle() == "Tool"
    assert not dialog.isModal()
    assert dialog.parent() is main
    assert margins(layout) == (mod.MARGIN,) * 4
    own = QtWidgets.QWidget()
    dialog2, _ = mod.compact_dialog(parent=own)
    assert dialog2.parent() is own
    main.deleteLater()


def test_main_window_when_no_application_then_none(monkeypatch):
    fake = SimpleNamespace(QApplication=SimpleNamespace(instance=lambda: None))
    monkeypatch.setattr(mod, "_qt", lambda: SimpleNamespace(QtGui=fake))
    assert mod._main_window() is None


def test_ui_facade_when_compact_dialog_requested_then_exported():
    from fontlabapp import ui

    assert ui.compact_dialog is mod.compact_dialog
    assert "split_view" in dir(ui)


def test_compact_layout_when_object_lacks_setters_then_returned_unchanged(caplog):
    from fontlabapp.qt.compact import compact_layout

    class Bare:
        pass

    bare = Bare()
    assert compact_layout(bare) is bare, "objects without Qt setters pass through"
    assert "lacks setContentsMargins/setSpacing" in caplog.text, "the missing setter is logged"
