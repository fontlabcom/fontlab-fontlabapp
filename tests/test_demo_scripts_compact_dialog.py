# this_file: tests/test_demo_scripts_compact_dialog.py
"""Offline run of Scripts/Widgets/Compact Dialog Demo.py (Issue 253).

The demo runs through runpy as ``__main__`` (one modeless dialog is built, filled and
shown) and as an imported name (nothing may run). ``PythonQt`` and ``fontlab`` natives
and ``compact_dialog`` are replaced; offline results are not native FontLab acceptance.
"""

from unittest.mock import MagicMock

from _demo_support import Recorder, qt_namespace, run_script, script_path, stub_module

import fontlabapp.qt.compact as compact

DEMO = script_path("Widgets", "Compact Dialog Demo")


def install(monkeypatch):
    """Stub the natives and ``compact_dialog``; return (QtGui namespace, dialog, layout, recorder)."""
    qt = qt_namespace()
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(monkeypatch, "fontlab", MainWindow=lambda: "main-window")
    dialog, layout = MagicMock(), MagicMock()
    recorder = Recorder((dialog, layout))
    monkeypatch.setattr(compact, "compact_dialog", recorder)
    return qt, dialog, layout, recorder


def test_compact_dialog_when_main_then_fills_and_shows_one_dialog(monkeypatch) -> None:
    qt, dialog, layout, recorder = install(monkeypatch)
    names = run_script(DEMO)
    assert recorder.calls == [(("Compact Dialog Demo",), {})]
    assert layout.addWidget.call_count == 2
    dialog.show.assert_called_once_with()
    assert names["_KEEP"] == [dialog], "the modeless dialog must stay referenced"
    qt.QtGui.QPushButton.return_value.clicked.connect.assert_called_once_with(dialog.close)


def test_compact_dialog_when_imported_then_nothing_runs(monkeypatch) -> None:
    _, dialog, _, recorder = install(monkeypatch)
    names = run_script(DEMO, run_name="imported")
    assert recorder.calls == [] and names["_KEEP"] == [] and callable(names["main"])
    dialog.show.assert_not_called()
