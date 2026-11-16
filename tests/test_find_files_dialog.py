# this_file: tests/test_find_files_dialog.py
"""Real Qt actions over owned font/script files, with desktop activation injected."""

import os
import sys
import json
import subprocess
from types import SimpleNamespace as NS
import pytest

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
else:
    from PySide6 import QtCore as C, QtGui as G, QtWidgets as W
import fontlabapp
import fontlabapp.core.scripting as scripts
import fontlabapp.qt.find_files.ui as ui


class Gui:
    QCloseEvent = G.QCloseEvent

    def __getattr__(self, name):
        return getattr(W, name)


@pytest.fixture
def panel(monkeypatch, tmp_path):
    app = W.QApplication.instance() or W.QApplication([])
    opened = []
    gui = Gui()
    gui.QDesktopServices = NS(
        openUrl=lambda url: opened.append(url.toLocalFile()) or True
    )
    qt = NS(QtCore=C, QtGui=gui)
    monkeypatch.setattr(fontlabapp, "_native", lambda n: qt)
    monkeypatch.setattr(
        scripts,
        "_native",
        lambda n: qt if n == "PythonQt" else NS(MainWindow=lambda: None),
    )
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    made = []

    def create(profile):
        w = ui.dialog_type(profile, qt)()
        made.append(w)
        w.directory.setEditText(str(tmp_path))
        w.show()
        return w

    yield app, create, opened, tmp_path
    for w in made:
        if not w._closed:
            w.close()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)


def drain(w):
    for _ in range(10000):
        if not w._timer.isActive():
            return
        w.tick()
    raise AssertionError("Owned search did not finish")


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_actual_Find_Browse_activation_and_repeat_history(panel, profile):
    app, create, opened, root = panel
    (root / "fønt.glyphs").write_text('{familyName="Orchard";}', encoding="utf8")
    (root / "tool.py").write_text("# Orchard script; never executed")
    w = create(profile)
    w.pattern.setEditText("*.glyphs")
    w.containing.setEditText("Orchard")
    w.find_button.click()
    drain(w)
    assert w.table.rowCount() == 1 and w.table.item(0, 0).text() == "fønt.glyphs"
    assert w.table.item(0, 1).text() == ("1" if profile == "text" else "1 KB")
    w.table.cellActivated.emit(0, 0)
    assert opened == [str(root / "fønt.glyphs")]
    w.browse_button.click()
    browser = w._browser
    assert browser.isVisible() and browser.testOption(W.QFileDialog.DontUseNativeDialog)
    browser.setDirectory(str(root))
    browser.selectFile(str(root))
    browser.accept()
    assert w.directory.currentText() == str(root)
    w.find_button.click()
    drain(w)
    assert w.table.rowCount() == 1
    if profile == "bytes":
        assert (
            w.pattern.findText("*.glyphs") >= 0
            and w.containing.findText("Orchard") >= 0
        )
        assert [w.containing.itemText(i) for i in range(w.containing.count())].count(
            "Orchard"
        ) == 1


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_actual_cancel_button_closes_stream_and_close_stops_everything(panel, profile):
    app, create, opened, root = panel
    (root / "large.vfj").write_bytes(b"x" * 200000)
    w = create(profile)
    w.pattern.setEditText("*")
    w.containing.setEditText("missing")
    w.find_button.click()
    while w._search.stream is None:
        w.tick()
    stream = w._search.stream
    w.cancel_button.click()
    assert stream.closed and not w._timer.isActive() and w._search.stream is None
    assert not w.progress.isVisible() and not opened
    w.find_button.click()
    while w._search.stream is None:
        w.tick()
    stream = w._search.stream
    assert w.close() is True
    assert stream.closed and not w._timer.isActive()


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_profile_window_size_table_editing_and_all_terminals(panel, profile):
    app, create, opened, root = panel
    (root / "a.py").write_text("owned")
    for terminal in ("close", "reject", "accept", "done", "escape", "parent"):
        w = create(profile)
        w.pattern.setEditText("*")
        w.find_button.click()
        drain(w)
        assert (w.width(), w.height()) == (
            (640, 460) if profile == "text" else (700, 300)
        )
        assert bool(w.table.item(0, 0).flags() & C.Qt.ItemIsEditable) == (
            profile == "text"
        )
        dead = []
        w.destroyed.connect(lambda *args: dead.append(True))
        if terminal == "parent":
            parent = W.QWidget()
            w.setParent(parent)
            parent.deleteLater()
        elif terminal == "escape":
            app.sendEvent(
                w, G.QKeyEvent(C.QEvent.KeyPress, C.Qt.Key_Escape, C.Qt.NoModifier)
            )
        elif terminal == "done":
            w.done(9)
        else:
            getattr(w, terminal)()
        C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
        assert dead == [True] and w._closed and w._completion_lifetime.closed
        assert w._search.stream is None and w._search.entries is None


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_owned_parent_destruction_releases_active_read_and_late_callbacks(
    panel, profile
):
    app, create, opened, root = panel
    (root / "a.py").write_bytes(b"x" * 200000)
    w = create(profile)
    w.pattern.setEditText("*")
    w.containing.setEditText("missing")
    w.find_button.click()
    while w._search.stream is None:
        w.tick()
    stream = w._search.stream
    callbacks = [slot for signal, slot in w._connections]
    parent = W.QWidget()
    w.setParent(parent)
    parent.deleteLater()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert stream.closed and w._closed and w._search.entries is None
    for callback in callbacks:
        callback(0, 0)
    assert not opened


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_edited_labels_do_not_redirect_activation_and_fault_closes_stream(
    panel, profile, monkeypatch
):
    app, create, opened, root = panel
    (root / "a.py").write_text("owned")
    w = create(profile)
    w.pattern.setEditText("*")
    w.find_button.click()
    drain(w)
    w.table.item(0, 0).setText("unrelated.py")
    w.table.cellActivated.emit(0, 0)
    assert opened == [str(root / "a.py")]
    import fontlabapp.qt.find_files.actions as actions

    def broken(owner):
        owner._search = Search(root, "*", "missing", profile)
        while owner._search.stream is None and owner._search.active:
            owner._search.step()
        raise ValueError("owned injected callback fault")

    from fontlabapp.qt.find_files.model import Search

    monkeypatch.setattr(actions, "begin", broken)
    w.find_button.click()
    assert (
        not w._search.active and w._search.stream is None and w._search.entries is None
    )
    assert "injected callback fault" in w.status.text()


def test_property_bound_combo_reads_and_snapshot_histories(panel):
    app, create, opened, root = panel
    (root / "a.py").write_text("needle")
    w = create("bytes")
    w.pattern.setEditText("*.py")
    w.containing.setEditText("needle")
    w.find_button.click()
    w.pattern.setEditText("*.txt")
    w.containing.setEditText("different")
    drain(w)
    assert w.table.rowCount() == 1 and w.pattern.findText("*.py") >= 0
    assert (
        w.containing.findText("needle") >= 0 and w.containing.findText("different") < 0
    )
    import fontlabapp.qt.find_files.actions as actions

    original = w.pattern
    w.pattern = NS(
        currentText="*", findText=original.findText, addItem=original.addItem
    )
    w._action(actions.begin)
    drain(w)
    assert w._search.pattern == "*"


def test_actual_public_facades_lazily_launch_both_owned_profiles(panel):
    app, create, opened, root = panel
    import fontlabapp.qt.find_files.model as api

    for launch, profile in ((api.show, "text"), (api.show_bytes, "bytes")):
        w = launch()
        assert w._profile == profile and w.isVisible()
        assert sys._fontlab_samples["find-font-files-" + profile] is w
        w.close()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)


def test_constructor_fault_destroys_partial_dialog_and_invalid_profile_refuses(
    panel, monkeypatch
):
    app, create, opened, root = panel
    with pytest.raises(ValueError):
        ui.dialog_type("unknown", NS())
    factory = ui.dialog_type("text", NS(QtCore=C, QtGui=Gui()))

    def broken(self):
        raise ValueError("owned constructor fault")

    monkeypatch.setattr(factory, "_build", broken)
    with pytest.raises(ValueError, match="constructor fault"):
        factory()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert not sys._fontlab_samples


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_missing_directory_and_tick_fault_show_owned_diagnosis(
    panel, profile, monkeypatch
):
    app, create, opened, root = panel
    w = create(profile)
    w.directory.setEditText(str(root / "missing"))
    w.find_button.click()
    drain(w)
    assert w._search.error and not w._timer.isActive()
    import fontlabapp.qt.find_files.actions as actions

    monkeypatch.setattr(
        actions,
        "tick",
        lambda owner: (_ for _ in ()).throw(ValueError("owned tick fault")),
    )
    w.tick()
    assert w.status.text() == "owned tick fault"


@pytest.mark.parametrize("profile", ["text", "bytes"])
@pytest.mark.parametrize("documents", [False, True])
def test_physical_long_home_preserves_geometry_and_complete_directory(
    tmp_path, profile, documents
):
    home = tmp_path / ("long home ž " + "a" * 70) / ("owned Unicode " + "b" * 70)
    home.mkdir(parents=True)
    if documents:
        (home / "Documents").mkdir()
    assert home.resolve() == home
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    code = r'''
import json, os, sys
from pathlib import Path
from types import SimpleNamespace as NS
if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W, QtTest as T
else:
    from PySide6 import QtCore as C, QtGui as G, QtWidgets as W, QtTest as T
import fontlabapp.core.scripting as scripts
from fontlabapp.qt.find_files.ui import dialog_type
class Gui:
    QCloseEvent = G.QCloseEvent
    def __getattr__(self, name):
        return getattr(W, name)
app = W.QApplication([])
qt = NS(QtCore=C, QtGui=Gui())
scripts._native = lambda name: qt if name == "PythonQt" else NS(MainWindow=lambda: None)
sys._fontlab_samples = {}
home = Path.home()
assert str(home) == os.environ["HOME"] == os.environ["USERPROFILE"]
initial = str(home / "Documents" if (home / "Documents").is_dir() else home)
window = dialog_type(sys.argv[1], qt)()
window.show()
app.processEvents()
combo = window.directory
editor = combo.lineEdit()
assert combo.itemText(0) == combo.currentText() == initial
assert editor.maxLength() == 32767
editor.selectAll()
assert editor.selectedText() == initial
editor.setCursorPosition(len(initial))
assert editor.cursorPosition() == len(initial)
before = [window.width(), window.height()]
other = home / ("another history ł " + "c" * 70)
other.mkdir()
combo.addItem(str(other))
combo.setCurrentIndex(1)
assert combo.currentText() == str(other)
combo.showPopup()
app.processEvents()
view = combo.view()
index = combo.model().index(0, combo.modelColumn(), combo.rootModelIndex())
view.scrollTo(index)
app.processEvents()
rect = view.visualRect(index).intersected(view.viewport().rect())
assert view.isVisible() and rect.isValid() and not rect.isEmpty()
T.QTest.mouseClick(view.viewport(), C.Qt.LeftButton, C.Qt.NoModifier, rect.center())
app.processEvents()
assert not view.isVisible()
assert combo.currentIndex() == 0 and combo.currentText() == initial
assert [combo.itemText(i) for i in range(combo.count())] == [initial, str(other)]
editor.selectAll()
assert editor.selectedText() == initial
after = [window.width(), window.height()]
def size(value):
    return [value.width(), value.height()]
record = {
    "profile": sys.argv[1], "home": str(home), "initial": initial,
    "documents": (home / "Documents").is_dir(), "fidelity_controls": True,
    "initial_geometry": before, "after_history_geometry": after,
    "qpa": app.platformName(), "style": app.style().objectName(),
    "font": app.font().toString(), "dialog_minimum": size(window.minimumSize()),
    "layout_minimum": size(window.layout().minimumSize()),
    "control_minimum_hints": {name: size(getattr(window, name).minimumSizeHint())
        for name in ["pattern", "containing", "directory", "table", "status",
                     "browse_button", "find_button"]},
}
print(json.dumps(record), flush=True)
window.close()
C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
assert before == after == ([640, 460] if sys.argv[1] == "text" else [700, 300]), record
'''
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, profile],
        env=env, capture_output=True, text=True, timeout=60,
    )
    (tmp_path / "long-home-child.stdout").write_text(result.stdout, encoding="utf8")
    (tmp_path / "long-home-child.stderr").write_text(result.stderr, encoding="utf8")
    assert result.stdout.strip(), (result.returncode, result.stderr)
    observation = json.loads(result.stdout.strip().splitlines()[-1])
    (tmp_path / "long-home-observation.json").write_text(
        json.dumps(observation, indent=2), encoding="utf8"
    )
    assert observation["fidelity_controls"] is True
    assert result.returncode == 0, (result.stdout, result.stderr)
