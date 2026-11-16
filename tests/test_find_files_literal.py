# this_file: tests/test_find_files_literal.py
"""Exact query/history text, including a PythonQt-shaped lossy combo boundary."""

import os
import sys
from types import SimpleNamespace as NS

import pytest

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
else:
    from PySide6 import QtCore as C, QtGui as G, QtWidgets as W

import fontlabapp
import fontlabapp.core.scripting as scripts
from fontlabapp.qt.find_files.ui import dialog_type


class NativeCombo(W.QComboBox):
    """Emulate only the measured no-length inbound QString conversion."""

    def setEditText(self, text):
        super().setEditText(text.split("\0", 1)[0])

    def addItem(self, text):
        super().addItem(text.split("\0", 1)[0])

    def findText(self, text):
        return super().findText(text.split("\0", 1)[0])


@pytest.fixture
def panel(monkeypatch, tmp_path):
    app = W.QApplication.instance() or W.QApplication([])
    app.setQuitOnLastWindowClosed(False)

    class Gui:
        QComboBox = NativeCombo

        def __getattr__(self, name):
            return getattr(W, name) if hasattr(W, name) else getattr(G, name)

    qt = NS(QtGui=Gui(), QtCore=C)
    monkeypatch.setattr(fontlabapp, "_native", lambda _: qt)
    monkeypatch.setattr(
        scripts,
        "_native",
        lambda name: qt if name == "PythonQt" else NS(MainWindow=lambda: None),
    )
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    made = []

    def create(profile):
        w = dialog_type(profile, qt)()
        made.append(w)
        w.directory.setEditText(str(tmp_path))
        w.pattern.setEditText("*.py")
        return w

    yield create, tmp_path, qt
    for w in made:
        if not w._closed:
            w.close()
        C.QCoreApplication.sendPostedEvents(w, C.QEvent.DeferredDelete)


def finish(w):
    for _ in range(1000):
        if not w._timer.isActive():
            return
        w.tick()
    raise AssertionError("Owned literal query exceeded its bounded turns")


def history(combo):
    return [combo.itemText(i) for i in range(combo.count())]


@pytest.mark.parametrize("profile", ["text", "bytes"])
@pytest.mark.parametrize(
    "needle", ["\0", "\0A", "A\0", "A\0B", "中😀\0\u2028\u2029\0é"]
)
def test_literal_query_and_ordered_history_roundtrip(panel, profile, needle):
    create, root, _ = panel
    (root / "exact.py").write_bytes(needle.encode("utf8"))
    (root / "prefix.py").write_bytes(needle.split("\0", 1)[0].encode("utf8"))
    w = create(profile)
    prior = history(w.containing)
    for _ in range(2):
        w.containing.setEditText(needle)
        assert w.containing.currentText() == needle
        assert w.containing.lineEdit().text() == needle
        assert w.containing.lineEdit().maxLength() == 32767
        w.find_button.click()
        finish(w)
        assert w._query == ("*.py", needle, str(root))
        assert [p.name for p in w._paths] == ["exact.py"]
        assert history(w.containing) == prior + ([needle] if profile == "bytes" else [])
    if profile == "bytes":
        w.containing.setCurrentIndex(w.containing.count() - 1)
        assert w.containing.currentText() == needle
        w.find_button.click()
        finish(w)
        assert w._query[1] == needle
        assert history(w.containing) == prior + [needle]


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_all_query_fields_retain_nul_without_searching_a_prefix(panel, profile):
    create, root, _ = panel
    (root / "a.py").write_text("owned")
    w = create(profile)
    w.pattern.setEditText("*.py\0suffix")
    w.find_button.click()
    finish(w)
    assert w._query[0] == "*.py\0suffix" and not w._paths
    w.pattern.setEditText("*.py")
    w.directory.setEditText(str(root) + "\0suffix")
    w.find_button.click()
    finish(w)
    assert w._query[2] == str(root) + "\0suffix"
    assert not w._timer.isActive() and not w._paths and w.status.text()


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_original_utf16_maximum_is_unchanged(panel, profile):
    create, root, _ = panel
    requested = "A\0" + "😀" * 16382 + "Ztail"
    oracle = W.QLineEdit()
    oracle.setText(requested)
    expected = oracle.text()
    try:
        w = create(profile)
        w.containing.setEditText(requested)
        assert w.containing.currentText() == expected
        assert w.containing.lineEdit().maxLength() == 32767
        (root / "a.py").write_bytes(expected.encode("utf8"))
        w.find_button.click()
        finish(w)
        assert w._query[1] == expected and [p.name for p in w._paths] == ["a.py"]
    finally:
        oracle.deleteLater()
        C.QCoreApplication.sendPostedEvents(oracle, C.QEvent.DeferredDelete)
