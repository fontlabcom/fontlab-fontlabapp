# this_file: tests/test_demo_scripts_compact_dialog.py
"""Offline run of Scripts/Widgets/Compact Dialog Demo.py (Issue 253).

The demo runs through runpy as ``__main__`` and as an imported name (nothing may
run). ``PythonQt`` is replaced by real PySide6 widgets so the real ``compact``
helpers set real margins and spacing; ``fontlab`` is a stub. Offline results are
not native FontLab acceptance (see the native probe evidence for that).
"""

from types import SimpleNamespace

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from _demo_support import run_script, script_path, stub_module

import fontlabapp.qt.compact as compact

DEMO = script_path("Widgets", "Compact Dialog Demo")


@pytest.fixture
def app(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    stub_module(monkeypatch, "PythonQt", QtGui=QtWidgets, QtCore=SimpleNamespace())
    stub_module(monkeypatch, "fontlab", MainWindow=lambda: None)
    monkeypatch.setattr(compact, "_qt", lambda: SimpleNamespace(QtGui=QtWidgets))
    return app


def margins(layout):
    m = layout.contentsMargins()
    return (m.left(), m.top(), m.right(), m.bottom())


def test_compact_dialog_when_main_then_real_compact_metrics_and_view_above_controls(app) -> None:
    names = run_script(DEMO)
    (dialog,) = names["_KEEP"]
    outer = dialog.layout()
    assert margins(outer) == (0, 0, 0, 0), "split_view lets the view reach the window edges"
    view, controls = outer.itemAt(0).widget(), outer.itemAt(1).widget()
    assert isinstance(view, QtWidgets.QGraphicsView) and view.frameShape() == QtWidgets.QFrame.NoFrame
    assert outer.stretch(0) == 1, "the view takes all extra space"
    assert margins(controls.layout()) == (compact.MARGIN,) * 4
    assert controls.layout().spacing() == compact.SPACING
    assert dialog.windowTitle() == "Compact Dialog Demo" and not dialog.isModal()
    assert not dialog.isHidden(), "the dialog is shown"
    dialog.close()


def test_compact_dialog_when_close_clicked_then_dialog_closes(app) -> None:
    (dialog,) = run_script(DEMO)["_KEEP"]
    button = dialog.findChildren(QtWidgets.QPushButton)[0]
    button.click()
    assert not dialog.isVisible()


def test_compact_dialog_when_imported_then_nothing_runs(app) -> None:
    names = run_script(DEMO, run_name="imported")
    assert names["_KEEP"] == [] and callable(names["main"])


def test_demo_source_when_wiring_close_then_uses_lambda_not_bound_cpp_method() -> None:
    """FontLab 9.1.9813 PythonQt ignores a bound C++ method as a slot (native probe p17)."""
    source = DEMO.read_text(encoding="utf-8")
    assert "clicked.connect(dialog.close)" not in source and "clicked.connect(lambda" in source
