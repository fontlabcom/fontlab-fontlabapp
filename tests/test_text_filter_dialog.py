# this_file: tests/test_text_filter_dialog.py
"""Actual owned Qt6 widgets and temporary settings; no native FontLab or corpus."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

from fontlabapp.proof.text_filter.model import DEFAULT_CHARACTERS

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch, tmp_path):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

        def __setattr__(self, name, value):
            assert QtWidgets.QDialog.staticMetaObject.indexOfProperty(name) < 0
            assert not callable(getattr(QtWidgets.QDialog, name, None))
            super().__setattr__(name, value)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel = Dialog, Label
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in ("_names_dialog", "_text_filter_controls", "_text_filter_dialog"):
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    mod = importlib.import_module("fontlabapp.proof.text_filter.ui")
    monkeypatch.setattr(mod, "current_package", lambda: NS(id=31))
    calls = []
    monkeypatch.setattr(
        mod,
        "open_text_tab",
        lambda text, *, expected_id: calls.append((text, expected_id)),
    )
    settings = QtCore.QSettings(str(tmp_path / "owned.ini"), QtCore.QSettings.IniFormat)
    widget = mod.TextFilterDialog(settings=settings)
    yield widget, mod, settings, calls
    if isValid(widget):
        widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_complete_panel_filters_autosaves_and_reopens_with_geometry(panel):
    widget, mod, settings, calls = panel
    assert widget.output_edit.isReadOnly() and not widget.input_edit.isReadOnly()
    assert widget.new_tab.isChecked() is False
    widget.input_edit.setPlainText("a1Z 🙂\n")
    widget.characters_edit.setPlainText(r"a-z\s🙂")
    widget.simplify_button.click()
    assert widget.output_edit.toPlainText() == "a 🙂\n" and calls == []
    assert settings.value("input") == "a1Z 🙂\n"
    assert settings.value("output") == "a 🙂\n"
    widget.resize(700, 580)
    widget.close()
    reopened = mod.TextFilterDialog(settings=settings)
    try:
        assert reopened.input_edit.toPlainText() == "a1Z 🙂\n"
        assert reopened.output_edit.toPlainText() == "a 🙂\n"
        assert reopened.characters_edit.toPlainText() == r"a-z\s🙂"
        assert reopened.width() == 700
    finally:
        reopened.close()


def test_reset_removes_only_two_keys_and_retains_input_checkbox(panel):
    w, _, settings, _ = panel
    settings.setValue("other", "keep")
    w.input_edit.setPlainText("input")
    w.characters_edit.setPlainText("a-z")
    w.new_tab.setChecked(True)
    w.simplify_button.click()
    w.reset_button.click()
    assert w.input_edit.toPlainText() == "input" and w.output_edit.toPlainText() == ""
    assert w.characters_edit.toPlainText() == DEFAULT_CHARACTERS
    assert w.new_tab.isChecked() and not settings.contains("output")
    assert not settings.contains("characters") and settings.value("other") == "keep"


def test_regex_error_keeps_old_output_and_can_be_repaired(panel):
    w, _, _, _ = panel
    w.input_edit.setPlainText("a1")
    w.characters_edit.setPlainText("a-z")
    w.simplify_button.click()
    assert w.output_edit.toPlainText() == "a"
    w.characters_edit.setPlainText("")
    w.simplify_button.click()
    assert w.output_edit.toPlainText() == "a" and "unterminated" in w.status.text()
    w.characters_edit.setPlainText("0-9")
    w.simplify_button.click()
    assert w.output_edit.toPlainText() == "1"


def test_new_tab_uses_original_font_and_failed_tab_keeps_filtered_output(
    panel, monkeypatch
):
    w, _mod, _, calls = panel
    w.input_edit.setPlainText("a1")
    w.characters_edit.setPlainText("a-z")
    w.new_tab.setChecked(True)
    w.simplify_button.click()
    assert calls == [("a", 31)]
    w._open_tab = lambda text: (_ for _ in ()).throw(
        ValueError("Original font changed")
    )
    w.simplify_button.click()
    assert w.output_edit.toPlainText() == "a" and "font changed" in w.status.text()


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy"]
)
def test_every_completion_path_releases_io_callbacks_and_registry(panel, route):
    w, _, _, _ = panel
    sys.__dict__.setdefault("_fontlab_samples", {})["text_filter"] = w
    captured = [callback for _, callback in w._connections]
    w.show()
    if route == "close":
        w.close_button.click()
    elif route == "reject":
        w.reject()
    elif route == "accept":
        w.accept()
    elif route == "done":
        w.done(0)
    elif route == "destroy":
        w.deleteLater()
    else:
        from PySide6.QtTest import QTest

        QTest.keyClick(w, QtCore.Qt.Key_Escape)
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and w._settings is None and w._open_tab is None
    assert not w._connections and "text_filter" not in sys._fontlab_samples
    for callback in captured:
        callback()
