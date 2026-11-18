# this_file: tests/test_demo_scripts_font_editors.py
"""Offline runs of the Scripts/Font Editors demos (Issue 208, Task 8).

What is real: the demo scripts, ``fontlabapp.core.signals.scope``,
``fontlabapp.qt.widgets.create_dialog``, every ``fontlabapp.fontui`` module the
demos open, Fontport (``fontlab_fontport``, which the App gate installs), ufoLib2
and fontTools. The tests therefore check what the editors really do to the
demos' detached sample fonts. What is fake: ``PythonQt`` and ``fontlab``, which
exist only inside FontLab. The fake widgets model what the editors rely on:
signals fire only when a value changes, a spin box or slider clamps to its range
and rounds to its decimals, a dialog's ``close`` emits ``finished`` once while it
is shown, and a message box records what it showed when ``exec`` runs.
The fakes carry no class-level state: each test builds its own classes.
A missing Fontport or ufoLib2 is simulated by putting ``None`` into
``sys.modules``, which makes Python's import machinery raise
``ModuleNotFoundError`` for them, as it does when the package is absent.
Offline results are not native FontLab acceptance.
"""

import importlib
import json
import subprocess
import sys
from types import SimpleNamespace

import _cov_qt as fq
import pytest
from _light_canvas import light_canvas
from _demo_support import Recorder, run_script, script_path, stub_module

KERNING = script_path("Font Editors", "FontParts Kerning Editor Demo")
GROUPS = script_path("Font Editors", "Groups Editor Demo")
INFO = script_path("Font Editors", "Font Info Editor Demo")
FEATURES = script_path("Font Editors", "FontParts Features Editor Demo")
TRANSFORM = script_path("Font Editors", "Transform Editor Demo")
SEQUENCE = script_path("Font Editors", "Glyph Sequence Demo")
FONTS = script_path("Font Editors", "Font Browser Demo")
GLYPHS = script_path("Font Editors", "Glyph Browser Demo")
DESIGNSPACE = script_path("Font Editors", "Designspace Panel Demo")
BATCH = script_path("Font Editors", "Batch Panel Demo")
HELPERS = script_path("Font Editors", "Fontui Helpers Demo")

CHANGE_SIGNALS = ("historyChanged", "historyIndexChanged", "glyphUpdated", "glyphsUpdated", "signalPackageClosed")
REFUSED = "Qt refused part of the release; the window is kept open."


# --- A behavioural fake of the parts of PythonQt the editors use --------------------


class Permissive(fq.FakeWidget):
    """A widget that accepts any lower-case Qt method call and records it.

    Painters, pixmaps, colours and layouts take whatever the editors call; their
    output is not asserted. State the editors read (text, checked, value, current
    row...) is modelled by ``fq.FakeWidget`` and the classes below.
    """

    def __getattr__(self, name):
        try:
            return super().__getattr__(name)
        except AttributeError:
            if name.startswith("__") or not name[:1].islower():
                raise

            def method(*args, **kwargs):
                self.calls.append((name, args))

            return method


class ListItem:
    """A list widget item: text, icon and a selected flag."""

    def __init__(self, text):
        self._text, self.icon, self.selected = str(text), None, False

    def text(self):
        return self._text

    def setIcon(self, icon):
        self.icon = icon

    def setSelected(self, state):
        self.selected = bool(state)

    def isSelected(self):
        return self.selected


class ListWidget(Permissive):
    """QListWidget: rows from ``addItems`` or ``addItem``, a current row, a selection."""

    def __init__(self, *args):
        super().__init__(*args)
        self.itemDoubleClicked = fq.Signal()

    def addItem(self, item):
        self.items.append(ListItem(item) if isinstance(item, str) else item)

    def item(self, row):
        return self.items[row]

    def currentItem(self):
        return self.items[self.currentRow] if 0 <= self.currentRow < len(self.items) else None

    def selectedItems(self):
        marked = [item for item in self.items if getattr(item, "selected", False)]
        return marked or list(self.selected)


class PlainText(Permissive):
    """QPlainTextEdit: ``setPlainText`` emits ``textChanged`` when the text changes."""

    def setPlainText(self, text):
        changed = text != self.plain_text
        self.plain_text = text
        if changed:
            self._emit("textChanged")


class Ranged(Permissive):
    """QSpinBox, QDoubleSpinBox and QSlider: a value kept inside its range and decimals."""

    def __init__(self, *args):
        super().__init__(*args)
        self.low, self.high, self.decimals = 0, 99, None

    def setRange(self, low, high):
        self.low, self.high = low, high
        self.setValue(self.value)

    def setDecimals(self, decimals):
        self.decimals = decimals

    def setValue(self, value):
        value = min(self.high, max(self.low, value))
        if self.decimals is not None:
            value = round(value, self.decimals)
        super().setValue(value)


class Gui:
    """A module-like namespace: a Permissive class for every Qt name asked for."""

    def __init__(self, **special):
        self.__dict__.update(special)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        cls = type(name, (Permissive,), {})
        self.__dict__[name] = cls
        return cls


class Host:
    """The fake PythonQt and fontlab of one test; every list is this test's own."""

    def __init__(self, monkeypatch, handle):
        self.boxes, self.shots, self.dialogs, self.layouts, self.picks = [], [], [], [], []
        host = self

        class Dialog(Permissive):
            def __init__(self, *args):
                super().__init__(*args)
                self.title, self.modal, self.finished, self.closes = None, None, fq.Signal(), 0
                self.shown = False
                host.dialogs.append(self)

            def setWindowTitle(self, title):
                self.title = title

            def setModal(self, state):
                self.modal = state

            def show(self):
                self.shown = True

            def close(self):
                self.closes += 1
                if self.shown:
                    self.shown = False
                    self.finished.emit(0)
                return True

        class MessageBox(Permissive):
            def __init__(self, *args):
                super().__init__(*args)
                self.parts = {}

            def setText(self, text):
                self.parts["text"] = text

            def setInformativeText(self, text):
                self.parts["informative"] = text

            def setWindowTitle(self, title):
                self.parts["title"] = title

            def setDetailedText(self, text):
                self.parts["details"] = text

            def exec(self):
                host.boxes.append(self.parts)
                return 1

        class Layout(Permissive):
            def __init__(self, *args):
                super().__init__(*args)
                host.layouts.append(self)

            def added(self):
                return [args[0] for name, args in self.calls if name == "addWidget"]

        class Timer(fq.FakeTimer):
            @staticmethod
            def singleShot(delay, call):
                host.shots.append((delay, call))

        class FileDialog(Permissive):
            @staticmethod
            def getSaveFileName(*args):
                return host.picks.pop(0)

            getOpenFileName = getSaveFileName

        handle.qt.QtGui = Gui(
            QDialog=Dialog,
            QMessageBox=MessageBox,
            QFileDialog=FileDialog,
            QListWidget=ListWidget,
            QListWidgetItem=ListItem,
            QPlainTextEdit=PlainText,
            QSpinBox=Ranged,
            QDoubleSpinBox=Ranged,
            QSlider=Ranged,
            QVBoxLayout=Layout,
            QHBoxLayout=Layout,
            QFormLayout=Layout,
        )
        handle.qt.QtCore = Gui(QTimer=Timer, QEvent=fq.FakeEvent, Qt=fq.FakeWidget)
        self.items = SimpleNamespace(**{name: fq.Signal() for name in CHANGE_SIGNALS})
        self.actions = {name: SimpleNamespace(triggered=fq.Signal()) for name in ("actionUndo", "actionRedo")}
        self.window = SimpleNamespace(findChild=lambda cls, name: self.actions.get(name))
        stub_module(
            monkeypatch,
            "fontlab",
            MainWindow=lambda: self.window,
            flItems=SimpleNamespace(instance=lambda: SimpleNamespace(qobject=self.items)),
        )

    def drain(self):
        """Run the queued ``QTimer.singleShot`` callbacks, as the event loop would."""
        queued, self.shots[:] = list(self.shots), []
        for _, call in queued:
            call()

    def listeners(self):
        """How many FontLab signal connections the editors currently hold."""
        signals = [*vars(self.items).values(), *(action.triggered for action in self.actions.values())]
        return sum(len(signal.slots) for signal in signals)

    def layout_of(self, dialog):
        """The layout the demo made for ``dialog``."""
        (layout,) = [layout for layout in self.layouts if layout.args == (dialog,)]
        return layout


def forget_fontui(monkeypatch=None):
    """Drop every ``fontlabapp.fontui`` submodule so the next import meets the fake Qt."""
    for name in [name for name in sys.modules if name.startswith("fontlabapp.fontui.")]:
        if monkeypatch is not None:
            monkeypatch.delitem(sys.modules, name)
        else:
            sys.modules.pop(name)
        fq._forget_on_parent(name, monkeypatch)


@pytest.fixture
def host(monkeypatch):
    from contextlib import ExitStack
    from _feature_source_qt import owned_application, qt_namespace

    forget_fontui(monkeypatch)
    handle = fq.install(monkeypatch)
    source = importlib.import_module("fontlabapp.fontui.feature_source")
    original_factory = source.create_source_input
    owned = SimpleNamespace(app=None, parent=None, widgets=[], documents=[])
    try:
        with ExitStack() as stack:
            def dispose():
                import shiboken6
                from PySide6 import QtCore, QtWidgets

                assert QtWidgets.QApplication.instance() is owned.app
                # Include partially constructed children if the factory raised.
                if shiboken6.isValid(owned.parent):
                    for widget in owned.parent.findChildren(QtWidgets.QPlainTextEdit):
                        if widget not in owned.widgets:
                            owned.widgets.append(widget)
                        owned.documents.append(widget.document())
                    for widget in owned.widgets:
                        if shiboken6.isValid(widget):
                            widget.closed = True
                            widget.close()
                            widget.deleteLater()
                    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
                    owned.parent.close()
                    owned.parent.deleteLater()
                    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
                assert not shiboken6.isValid(owned.parent)
                assert all(not shiboken6.isValid(item) for item in owned.widgets + owned.documents)
                assert QtWidgets.QApplication.instance() is owned.app

            def create_source_input(qt, parent=None, **callbacks):
                if owned.app is None:
                    owned.app = stack.enter_context(owned_application())
                    owned.qt = qt_namespace()
                    owned.parent = owned.qt.QtGui.QWidget()
                    stack.callback(dispose)
                widget = original_factory(owned.qt, owned.parent, **callbacks)
                owned.widgets.append(widget)
                owned.documents.append(widget.document())
                return widget

            monkeypatch.setattr(source, "create_source_input", create_source_input)
            instance = Host(monkeypatch, handle)
            instance.real_source = owned
            yield instance
    finally:
        forget_fontui()
        fq.release()


def block(monkeypatch, root):
    """Make ``import <root>`` raise ModuleNotFoundError, as when the package is absent."""
    for name in [name for name in sys.modules if name.partition(".")[0] == root]:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, root, None)


def open_demo(host, path):
    """Run a window demo's ``main`` and return (module globals, the one open demo)."""
    names = run_script(path, "imported")
    names["main"]()
    assert len(names["_HANDLES"]) == 1, f"expected one open demo, got {names['_HANDLES']}"
    return names, names["_HANDLES"][0]


def shown(host):
    """The single message box a demo showed."""
    assert len(host.boxes) == 1, f"expected one message box, got {host.boxes}"
    return host.boxes[0]


def texts(widget):
    """The row texts of a list widget."""
    return [item.text() for item in widget.items]


# --- Window lifecycle shared by the eight window demos ------------------------------

# script, title, package whose absence the demo reports, factory it calls, follows FontLab
WINDOWS = [
    (KERNING, "FontParts Kerning Editor Demo", "fontlab_fontport", "kerning_editor", True),
    (GROUPS, "Groups Editor Demo", "fontlab_fontport", "groups_editor", True),
    (INFO, "Font Info Editor Demo", "fontlab_fontport", "font_info_editor", True),
    (FEATURES, "FontParts Features Editor Demo", None, "features_editor", True),
    (TRANSFORM, "Transform Editor Demo", "fontlab_fontport", "transform_editor", False),
    (SEQUENCE, "Glyph Sequence Demo", "fontlab_fontport", "glyph_sequence", True),
    (FONTS, "Font Browser Demo", "ufoLib2", "font_browser", True),
    (GLYPHS, "Glyph Browser Demo", "ufoLib2", "glyph_browser", True),
    (DESIGNSPACE, "Designspace Panel Demo", None, "designspace_panel", False),
]
IDS = [row[0].stem for row in WINDOWS]
NEEDING = [row for row in WINDOWS if row[2] is not None]
NEEDING_IDS = [row[0].stem for row in NEEDING]


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_main_then_one_nonmodal_dialog_holds_caption_editor_and_status(host, path, title, needs, factory, follows) -> None:
    names, demo = open_demo(host, path)
    (dialog,) = host.dialogs
    assert dialog.title == title and dialog.modal is False and dialog.shown, "a visible nonmodal dialog"
    assert dialog.args == (host.window,), "the dialog belongs to FontLab's main window"
    caption, widget, status = host.layout_of(dialog).added()
    assert caption.text == names["CAPTION"] and status is demo.status
    assert widget is demo.editor.widget and widget.args == (dialog,), "the editor is parented to the dialog"
    assert demo.problems == [] and not demo.editor.closed
    assert (host.listeners() > 0) is follows, "the editor connects to FontLab's signals exactly when it follows them"
    for module in names["MODULES"]:
        assert module in caption.text, f"the caption names {module}"
        assert importlib.import_module(module).__name__ == module.replace("fly.ap.", "fontlabapp.", 1)


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_the_dialog_finishes_then_release_waits_for_dispatch_then_frees_everything(host, path, title, needs, factory, follows) -> None:
    names, demo = open_demo(host, path)
    (dialog,) = host.dialogs
    dialog.close()
    assert [delay for delay, _ in host.shots] == [0] and names["_HANDLES"] == [demo], "release waits for Qt's dispatch"
    host.drain()
    assert names["_HANDLES"] == [] and demo.editor.closed and demo.owned.closed and dialog.deleted
    assert dialog.finished.slots == [] and demo.scope.records == [] and demo.problems == []
    assert host.listeners() == 0, "every FontLab connection is gone"
    assert host.boxes == [], "a clean release says nothing"
    demo.release()  # a second release is harmless
    assert names["_HANDLES"] == [] and host.boxes == []


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_qt_refuses_a_disconnect_then_the_demo_is_kept_until_it_succeeds(host, path, title, needs, factory, follows) -> None:
    names, demo = open_demo(host, path)
    (dialog,) = host.dialogs
    dialog.finished.disconnect = Recorder(False)
    dialog.finished.emit(0)
    host.drain()
    assert names["_HANDLES"] == [demo] and not demo.editor.closed and not dialog.deleted
    box = shown(host)
    assert box["informative"] == REFUSED and "Qt refused the owned signal disconnection." in box["details"]
    del dialog.finished.disconnect
    demo.release()
    assert names["_HANDLES"] == [] and demo.editor.closed and dialog.deleted


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_the_editor_cannot_disconnect_then_the_dialog_is_kept_and_the_message_names_why(host, path, title, needs, factory, follows) -> None:
    names, demo = open_demo(host, path)
    (dialog,) = host.dialogs

    def deleted(callback):
        raise RuntimeError("Internal C++ object already deleted.")

    demo.editor.widget.destroyed.disconnect = deleted  # every editor connects destroyed
    dialog.finished.emit(0)
    host.drain()
    assert names["_HANDLES"] == [demo] and not demo.owned.closed and not dialog.deleted
    box = shown(host)
    assert box["informative"] == REFUSED and box["details"] == "Internal C++ object already deleted."


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_the_dialog_will_not_close_then_the_demo_is_kept(host, path, title, needs, factory, follows) -> None:
    names, demo = open_demo(host, path)
    (dialog,) = host.dialogs
    dialog.close = lambda: False  # QWidget.close returns False when closeEvent ignores it
    dialog.finished.emit(0)
    host.drain()
    assert names["_HANDLES"] == [demo] and demo.editor.closed and not demo.owned.closed and not dialog.deleted
    assert shown(host)["informative"] == REFUSED


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_the_dialog_is_already_deleted_then_the_demo_is_kept_with_that_message(host, path, title, needs, factory, follows) -> None:
    names, demo = open_demo(host, path)
    (dialog,) = host.dialogs

    def deleted():
        raise RuntimeError("Internal C++ object already deleted.")

    dialog.deleteLater = deleted
    dialog.finished.emit(0)
    host.drain()
    assert names["_HANDLES"] == [demo] and demo.editor.closed and not demo.owned.closed
    assert shown(host)["details"] == "Internal C++ object already deleted."


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_the_editor_fails_to_build_then_the_dialog_closes_and_the_handle_is_dropped(host, monkeypatch, path, title, needs, factory, follows) -> None:
    def refuse(*args):
        raise RuntimeError("Qt refused the widget")

    monkeypatch.setattr(importlib.import_module("fontlabapp.fontui"), factory, refuse)
    names = run_script(path, "imported")
    with pytest.raises(RuntimeError, match="Qt refused the widget"):
        names["main"]()
    (dialog,) = host.dialogs
    assert names["_HANDLES"] == [] and dialog.deleted and not dialog.shown
    assert host.boxes == []


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), NEEDING, ids=NEEDING_IDS)
def test_window_when_a_package_is_missing_then_a_message_names_it_and_no_window_opens(host, monkeypatch, path, title, needs, factory, follows) -> None:
    block(monkeypatch, needs)
    names = run_script(path, "imported")
    names["main"]()
    box = shown(host)
    assert box["title"] == title and box["informative"] == names["MISSING"]
    assert host.dialogs == [] and names["_HANDLES"] == []
    if needs == "fontlab_fontport":
        assert "fontlab-fontlabapp[fontport]" in box["details"], "the message names the extra"
        assert "needs fontlab-fontport" in box["details"]
    else:
        assert "ufoLib2" in box["details"] and "fontport" in names["MISSING"], "the message names the package and the extra"


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_imported_then_nothing_runs(host, path, title, needs, factory, follows) -> None:
    names = run_script(path, "imported")
    assert callable(names["main"]) and names["_HANDLES"] == []
    assert host.dialogs == [] and host.boxes == [] and host.layouts == []


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), WINDOWS, ids=IDS)
def test_window_when_run_as_a_script_then_one_dialog_opens(host, path, title, needs, factory, follows) -> None:
    run_script(path)
    (dialog,) = host.dialogs
    assert dialog.shown and dialog.title == title


# --- FontParts Kerning Editor Demo -----------------------------------------------------


def kerning_parts(host):
    names, demo = open_demo(host, KERNING)
    return names, demo, demo.editor


def test_kerning_when_opened_then_explicit_pairs_of_the_sample_font_are_listed(host) -> None:
    names, demo, editor = kerning_parts(host)
    assert texts(editor.pair_list) == ["T | O | -30", "public.kern1.A | public.kern2.V | -80"]
    assert editor.apply_button.enabled, "the sample kerning has the batch hook, so the editor can edit"
    assert demo.status.text == names["IDLE"]


def test_kerning_when_a_pair_is_applied_then_only_the_sample_kerning_changes_and_the_status_counts_pairs(host) -> None:
    names, demo, editor = kerning_parts(host)
    for control, text in ((editor.left_control, "A"), (editor.right_control, "V"), (editor.value_control, "-50")):
        control.setText(text)
    editor.apply_button.clicked.emit()
    assert dict(demo.font.kerning) == {("T", "O"): -30, ("public.kern1.A", "public.kern2.V"): -80, ("A", "V"): -50}
    assert demo.status.text == "Applied to the sample font in memory: 3 explicit pairs."
    assert dict(demo.font.ufo.kerning) == {("T", "O"): -30, ("public.kern1.A", "public.kern2.V"): -80}, "the ufoLib2 font is untouched"
    assert "T | O | -30" in texts(editor.pair_list) and "A | V | -50" in texts(editor.pair_list)


def test_kerning_when_an_explicit_pair_is_deleted_then_it_leaves_the_sample_kerning(host) -> None:
    names, demo, editor = kerning_parts(host)
    editor.pair_list.setCurrentRow(0)  # T | O
    assert editor.delete_button.enabled, "an explicit pair can be deleted"
    editor.delete_button.clicked.emit()
    assert dict(demo.font.kerning) == {("public.kern1.A", "public.kern2.V"): -80}
    assert demo.status.text == "Applied to the sample font in memory: 1 explicit pairs."


def test_kerning_when_the_value_is_not_a_number_then_the_editor_refuses_and_nothing_changes(host) -> None:
    names, demo, editor = kerning_parts(host)
    for control, text in ((editor.left_control, "A"), (editor.right_control, "V"), (editor.value_control, "wide")):
        control.setText(text)
    editor.apply_button.clicked.emit()
    assert editor.diagnostic.text == "could not convert string to float: 'wide'"
    assert len(demo.font.kerning) == 2 and demo.status.text == names["IDLE"]


def test_kerning_when_a_glyph_is_unknown_then_fontport_refuses_the_pair(host) -> None:
    names, demo, editor = kerning_parts(host)
    for control, text in ((editor.left_control, "Q"), (editor.right_control, "V"), (editor.value_control, "-10")):
        control.setText(text)
    editor.apply_button.clicked.emit()
    assert editor.diagnostic.text == "Unknown kerning key: Q" and len(demo.font.kerning) == 2


def test_kerning_when_fontlab_runs_undo_then_the_list_reloads_from_the_sample_font(host) -> None:
    names, demo, editor = kerning_parts(host)
    demo.font.kerning[("V", "A")] = -20  # a change made behind the editor's back
    assert "V | A | -20" not in texts(editor.pair_list)
    host.actions["actionUndo"].triggered.emit()
    assert "V | A | -20" in texts(editor.pair_list), "the editor listens to Undo and reloads"


# --- Groups Editor Demo -----------------------------------------------------------------


def groups_parts(host):
    names, demo = open_demo(host, GROUPS)
    return names, demo, demo.editor


def test_groups_when_opened_then_the_three_sample_groups_are_listed(host) -> None:
    names, demo, editor = groups_parts(host)
    assert texts(editor.group_list) == ["Capitals", "public.kern1.A", "public.kern2.V"]
    assert all(button.enabled for key, button in editor.buttons.items() if key == "add")
    assert not editor.buttons["delete"].enabled, "Delete needs a selected group"


def test_groups_when_a_group_is_selected_then_its_members_list_and_the_first_is_previewed(host) -> None:
    names, demo, editor = groups_parts(host)
    editor.group_list.setCurrentRow(0)
    assert texts(editor.member_list) == ["A", "V", "T", "O"] and editor.preview.name == "A"
    assert editor.name_control.text == "Capitals"


def test_groups_when_a_group_is_added_then_the_sample_groups_gain_it_and_the_status_counts(host) -> None:
    names, demo, editor = groups_parts(host)
    editor.name_control.setText("Round")
    editor.buttons["add"].clicked.emit()
    assert demo.font.groups["Round"] == () and len(demo.font.groups) == 4
    assert demo.status.text == "Applied to the sample font in memory: 4 groups."
    assert "Round" not in names["GROUPS"], "the module's sample literal is never edited"


def test_groups_when_members_are_added_then_they_are_stored_as_a_tuple_without_duplicates(host) -> None:
    names, demo, editor = groups_parts(host)
    editor.group_list.setCurrentRow(1)  # public.kern1.A
    editor.members_control.setText("A T")
    editor.buttons["add_members"].clicked.emit()
    assert demo.font.groups["public.kern1.A"] == ("A", "T")


def test_groups_when_a_member_is_removed_then_the_group_keeps_the_others(host) -> None:
    names, demo, editor = groups_parts(host)
    editor.group_list.setCurrentRow(0)  # Capitals; its first member is selected
    editor.buttons["remove_members"].clicked.emit()
    assert demo.font.groups["Capitals"] == ("V", "T", "O")


def test_groups_when_a_group_is_renamed_then_the_old_name_is_gone(host) -> None:
    names, demo, editor = groups_parts(host)
    editor.group_list.setCurrentRow(0)
    editor.name_control.setText("Upper")
    editor.buttons["rename"].clicked.emit()
    assert "Capitals" not in demo.font.groups and demo.font.groups["Upper"] == ("A", "V", "T", "O")


def test_groups_when_a_group_is_deleted_then_the_sample_groups_shrink(host) -> None:
    names, demo, editor = groups_parts(host)
    editor.group_list.setCurrentRow(0)
    editor.buttons["delete"].clicked.emit()
    assert sorted(demo.font.groups) == ["public.kern1.A", "public.kern2.V"]
    assert demo.status.text == "Applied to the sample font in memory: 2 groups."


def test_groups_when_an_unknown_glyph_is_added_then_fontport_refuses_and_nothing_changes(host) -> None:
    names, demo, editor = groups_parts(host)
    editor.group_list.setCurrentRow(0)
    editor.members_control.setText("Q")
    editor.buttons["add_members"].clicked.emit()
    assert editor.diagnostic.text == "Unknown group members: ['Q']"
    assert demo.font.groups["Capitals"] == ("A", "V", "T", "O") and demo.status.text == names["IDLE"]


# --- Font Info Editor Demo --------------------------------------------------------------


def info_parts(host):
    names, demo = open_demo(host, INFO)
    return names, demo, demo.editor


def test_info_when_opened_then_the_form_shows_the_sample_information(host) -> None:
    names, demo, editor = info_parts(host)
    assert editor.fields["familyName"].text == "Demo Sans" and editor.fields["unitsPerEm"].text == "1000"
    assert editor.fields["openTypeOS2WeightClass"].text == "400" and editor.fields["italicAngle"].text == "0"
    assert editor.apply_button.enabled, "the sample information has the batch hook"


def test_info_when_a_field_is_applied_then_the_sample_information_changes_and_the_status_names_it(host) -> None:
    names, demo, editor = info_parts(host)
    editor.fields["familyName"].setText("Renamed Sans")
    editor.fields["ascender"].setText("820")
    editor.apply_button.clicked.emit()
    assert demo.font.info.familyName == "Renamed Sans" and demo.font.info.ascender == 820
    assert demo.status.text == "Applied to the sample font in memory: ascender, familyName."
    assert demo.font.info.info.familyName == "Renamed Sans", "the info object of the detached ufoLib2 font is the one that changed"
    assert editor.diagnostic.text == "Applied font information."


def test_info_when_ufolib2_refuses_one_value_then_no_field_changes(host) -> None:
    names, demo, editor = info_parts(host)
    editor.fields["familyName"].setText("Half Applied")
    editor.fields["openTypeOS2WeightClass"].setText("5000")  # Fontport accepts it; ufoLib2 wants 1..1000
    editor.apply_button.clicked.emit()
    assert editor.diagnostic.text == "'openTypeOS2WeightClass' must be between 1 and 1000"
    assert demo.font.info.familyName == "Demo Sans" and demo.font.info.openTypeOS2WeightClass == 400
    assert demo.status.text == names["IDLE"]


def test_info_when_an_integer_field_holds_text_then_the_form_names_the_field(host) -> None:
    names, demo, editor = info_parts(host)
    editor.fields["unitsPerEm"].setText("many")
    editor.apply_button.clicked.emit()
    assert editor.diagnostic.text == "unitsPerEm: 'many' is not an integer" and demo.font.info.unitsPerEm == 1000


def test_info_when_reverted_then_the_staged_text_is_dropped(host) -> None:
    names, demo, editor = info_parts(host)
    editor.fields["familyName"].setText("Draft")
    editor.revert_button.clicked.emit()
    assert editor.fields["familyName"].text == "Demo Sans" and demo.font.info.familyName == "Demo Sans"


# --- FontParts Features Editor Demo -------------------------------------------------------


def features_parts(host):
    names, demo = open_demo(host, FEATURES)
    return names, demo, demo.editor


def test_features_when_opened_then_the_prefix_and_two_blocks_are_offered(host) -> None:
    names, demo, editor = features_parts(host)
    assert texts(editor.block_control) == ["Prefix", "kern", "liga"]
    assert editor.text_control.source_text() == names["PREFIX"] and editor.status.text == "Unmodified"
    assert editor.apply_button.enabled is False, "nothing is staged yet"


def test_features_when_a_block_is_edited_and_applied_then_the_sample_blocks_change_and_nothing_is_compiled(host) -> None:
    names, demo, editor = features_parts(host)
    editor.block_control.setCurrentIndex(1)  # kern
    edited = "feature kern {\n    pos A V -90;\n} kern;\n"
    editor.text_control.setPlainText(edited)
    assert editor.status.text == "Modified, not applied" and editor.apply_button.enabled
    editor.apply_button.clicked.emit()
    assert demo.font.features.blocks["features"][0] == ("kern", edited)
    assert demo.status.text == "Stored in the sample font in memory: 6 lines, not compiled."
    assert editor.diagnostic.text == "Applied feature code (not compiled)."
    assert demo.font.features.text == names["PREFIX"] + edited + "feature liga {\n} liga;\n"


def test_features_when_a_feature_is_added_and_removed_then_the_staged_blocks_follow(host) -> None:
    names, demo, editor = features_parts(host)
    editor.tag_control.setText("ss01")
    editor.add_button.clicked.emit()
    assert texts(editor.block_control) == ["Prefix", "kern", "liga", "ss01"] and editor.key == "ss01"
    editor.apply_button.clicked.emit()
    assert [tag for tag, _ in demo.font.features.blocks["features"]] == ["kern", "liga", "ss01"]
    editor.remove_button.clicked.emit()
    editor.apply_button.clicked.emit()
    assert [tag for tag, _ in demo.font.features.blocks["features"]] == ["kern", "liga"]


def test_features_when_a_tag_repeats_then_the_editor_refuses_it(host) -> None:
    names, demo, editor = features_parts(host)
    editor.tag_control.setText("kern")
    editor.add_button.clicked.emit()
    assert editor.diagnostic.text == "Feature block already exists: kern"
    assert [tag for tag, _ in demo.font.features.blocks["features"]] == ["kern", "liga"]


def test_features_when_fontlab_runs_redo_then_unstaged_editor_reloads_from_the_sample_font(host) -> None:
    names, demo, editor = features_parts(host)
    demo.font.features.set_blocks({"prefix": "languagesystem latn dflt;\n", "features": []})  # changed behind the editor
    host.actions["actionRedo"].triggered.emit()
    assert editor.text_control.source_text() == "languagesystem latn dflt;\n" and texts(editor.block_control) == ["Prefix"]


def test_features_when_source_control_is_created_then_original_qt_document_and_methods_are_used(host):
    from pathlib import Path
    from PySide6 import QtGui, QtWidgets
    import fontlabapp.fontui.feature_source as source

    names, demo, editor = features_parts(host)
    widget = editor.text_control
    assert isinstance(widget, QtWidgets.QPlainTextEdit)
    assert isinstance(widget.document(), QtGui.QTextDocument)
    assert widget.document() is widget.observed_document
    assert widget.parent() is host.real_source.parent
    assert not host.real_source.parent.isVisible()
    assert QtWidgets.QApplication.instance() is host.real_source.app
    assert Path(widget.source_text.__func__.__code__.co_filename).resolve() == Path(source.__file__).resolve()
    assert type(widget).__module__ == "fontlabapp.fontui.feature_source"
    assert widget.source_text() == names["PREFIX"]
    assert vars(demo.font) == {"features": demo.font.features}


def test_features_when_unsupported_selected_input_arrives_then_source_selection_and_font_survive(host):
    from copy import deepcopy
    from PySide6.QtGui import QTextCursor
    from _feature_source_qt import snapshot

    names, demo, editor = features_parts(host)
    widget = editor.text_control
    cursor = widget.textCursor()
    cursor.setPosition(1)
    cursor.setPosition(8, QTextCursor.KeepAnchor)
    widget.setTextCursor(cursor)
    before, font = snapshot(widget), deepcopy(vars(demo.font.features))
    assert widget.insertPlainText("bad\u2029source") is False
    assert snapshot(widget) == before and widget.source_text() == names["PREFIX"]
    assert vars(demo.font) == {"features": demo.font.features}
    assert vars(demo.font.features) == font
    assert editor.status.text == "Unmodified" and not editor.apply_button.enabled
    assert editor.diagnostic.text == "Unsupported or untrusted source input refused."


def test_features_when_actual_owner_closes_then_source_ingress_is_fenced(host):
    from copy import deepcopy
    from _feature_source_qt import snapshot

    names, demo, editor = features_parts(host)
    widget = editor.text_control
    before, font = snapshot(widget), deepcopy(vars(demo.font.features))
    editor.close()
    assert editor.closed and editor._close_complete and widget.owner_closed()
    assert widget.insertPlainText("after close") is False
    assert snapshot(widget) == before
    assert vars(demo.font) == {"features": demo.font.features}
    assert vars(demo.font.features) == font
    with pytest.raises(ValueError, match="Unsupported or untrusted"):
        widget.source_text()


def test_features_when_source_factory_raises_then_owned_partial_document_is_retained_for_cleanup(host):
    import fontlabapp.fontui.feature_source as source
    from PySide6 import QtWidgets

    with pytest.raises(ValueError, match="closed owner"):
        source.create_source_input(None, is_closed=lambda: True,
                                   on_change=lambda: None, on_diagnostic=lambda text: None)
    assert QtWidgets.QApplication.instance() is host.real_source.app
    assert len(host.real_source.parent.findChildren(QtWidgets.QPlainTextEdit)) == 1


# --- Transform Editor Demo ----------------------------------------------------------------


def transform_parts(host):
    names, demo = open_demo(host, TRANSFORM)
    return names, demo, demo.editor


def test_transform_when_opened_then_the_identity_preview_of_glyph_a_is_reported(host) -> None:
    names, demo, editor = transform_parts(host)
    assert texts(editor.glyph_control) == ["A", "O", "T"] and editor.glyph_control.currentText == "A"
    assert demo.status.text == "Preview of A: matrix (1, 0, 0, 1, 0, 0) at 100%. The sample is unchanged."
    assert editor.original.bounds == editor.result.bounds == (0, 0, 600, 700)


def test_transform_when_the_matrix_changes_then_the_copy_moves_and_the_source_does_not(host) -> None:
    names, demo, editor = transform_parts(host)
    editor.matrix["xy"].setText("0.5")
    assert demo.status.text == "Preview of A: matrix (1, 0.5, 0, 1, 0, 0) at 100%. The sample is unchanged."
    assert editor.result.bounds == (0, 0, 600, 850), "xy lifts y by half of x, so the apex moves from 700 to 850"
    assert editor.original.bounds == (0, 0, 600, 700)
    assert [(point.x, point.y) for point in demo.font["A"].contours[0].points] == [(0, 0), (300, 700), (600, 0)]


def test_transform_when_the_matrix_is_singular_then_fontport_refuses_the_recipe(host) -> None:
    names, demo, editor = transform_parts(host)
    editor.matrix["xx"].setText("0")
    editor.matrix["xy"].setText("0")
    assert editor.result is None and editor.diagnostic.text == "Affine matrix must have a finite nonzero determinant"


def test_transform_when_a_field_is_not_a_number_then_the_editor_names_the_field(host) -> None:
    names, demo, editor = transform_parts(host)
    editor.matrix["dx"].setText("far")
    assert editor.result is None and editor.diagnostic.text == "dx: not a number: 'far'"


def test_transform_when_the_glyph_changes_then_the_status_follows_it(host) -> None:
    names, demo, editor = transform_parts(host)
    editor.glyph_control.setCurrentIndex(2)  # T
    assert demo.status.text.startswith("Preview of T:")


def test_transform_when_settings_are_saved_then_a_json_recipe_is_written_where_the_user_chose(host, tmp_path) -> None:
    names, demo, editor = transform_parts(host)
    editor.matrix["xy"].setText("0.25")
    target = tmp_path / "recipe.json"
    host.picks.append(str(target))
    editor.buttons["save"].clicked.emit()
    assert json.loads(target.read_text())["matrix"] == [1, 0.25, 0, 1, 0, 0]
    assert editor.diagnostic.text == f"Saved settings to {target}"
    host.picks.append(str(target))
    editor.buttons["save"].clicked.emit()
    assert "File exists" in editor.diagnostic.text, "Fontport never replaces a recipe file"


def test_transform_when_the_file_dialog_is_cancelled_then_nothing_is_written(host, tmp_path) -> None:
    names, demo, editor = transform_parts(host)
    host.picks.append("")
    editor.buttons["save"].clicked.emit()
    assert list(tmp_path.iterdir()) == [] and "Saved" not in editor.diagnostic.text


def test_transform_when_settings_are_loaded_then_the_fields_take_the_saved_recipe(host, tmp_path) -> None:
    names, demo, editor = transform_parts(host)
    target = tmp_path / "recipe.json"
    target.write_text(json.dumps({"matrix": [1.5, 0, 0, 1, 10, 0], "intensity": 50, "enabled": True, "method": "affine"}))
    host.picks.append(str(target))
    editor.buttons["load"].clicked.emit()
    assert editor.matrix["xx"].text == "1.5" and editor.matrix["dx"].text == "10" and editor.intensity_field.text == "50"
    assert demo.status.text == "Preview of A: matrix (1.5, 0, 0, 1, 10, 0) at 50%. The sample is unchanged."


def test_transform_when_the_view_buttons_are_used_then_only_the_view_changes(host, monkeypatch) -> None:
    names, demo, editor = transform_parts(host)
    light_canvas(monkeypatch, sys.modules["fontlabapp.fontui.transform_view"])
    editor.buttons["zoom"].clicked.emit()
    assert editor.zoom == 1.25
    editor.buttons["view"].clicked.emit()
    assert editor.zoom == 1.0
    editor.buttons["script"].clicked.emit()
    assert "recipe = Recipe(" in editor.script_view.plain_text
    editor.matrix["xy"].setText("0.5")
    editor.buttons["reset"].clicked.emit()
    assert editor.matrix["xy"].text == "0"
    editor.canvas.paintEvent(None)  # the canvas paints with no error
    assert editor.diagnostic.text == "A: affine preview at 100%; the source font is unchanged.", "painting raised nothing"


# --- Glyph Sequence Demo -------------------------------------------------------------------


def sequence_parts(host):
    names, demo = open_demo(host, SEQUENCE)
    return names, demo, demo.editor


def test_sequence_when_opened_then_the_start_text_is_placed_with_the_sample_kerning(host) -> None:
    names, demo, editor = sequence_parts(host)
    assert editor.text_control.text == names["START_TEXT"]
    glyphs = editor.run.glyphs
    assert [g.name for g in glyphs] == ["A", "V", "A", "space", "T", "O", "A", "V"]
    assert [g.x for g in glyphs] == [0, 520, 1120, 1720, 1970, 2500, 3140, 3660], "A V and T O are kerned by -80 and -30"


def test_sequence_when_kerning_is_turned_off_then_the_pair_returns_to_its_plain_advance(host) -> None:
    names, demo, editor = sequence_parts(host)
    editor.kerning_control.setChecked(False)
    assert [g.x for g in editor.run.glyphs][:2] == [0, 600]


def test_sequence_when_a_glyph_is_selected_by_key_then_the_status_names_it(host) -> None:
    names, demo, editor = sequence_parts(host)
    key = host_key(host, "Key_Right")
    assert editor.select_key(key) and demo.status.text == "Selected glyph A at position 1."
    assert editor.select_key(key) and demo.status.text == "Selected glyph V at position 2."
    assert editor.select_key(host_key(host, "Key_End")) and demo.status.text == "Selected glyph V at position 8."
    assert editor.select_key(host_key(host, "Key_Home")) and demo.status.text == "Selected glyph A at position 1."
    assert not editor.select_key("Key_Q"), "other keys are not handled"


def host_key(host, name):
    """The fake Qt's key constant ``name`` (the fake returns the name itself)."""
    return getattr(sys.modules["PythonQt"].QtCore.Qt, name)


def test_sequence_when_a_pixel_is_clicked_then_the_glyph_under_it_is_selected(host) -> None:
    names, demo, editor = sequence_parts(host)
    first = editor.run.glyphs[1]  # V
    x = editor.origin_x + (first.x + first.advance / 2) * editor.scale
    editor.select_at(x, 10)
    assert demo.status.text == "Selected glyph V at position 2."


def test_sequence_when_a_character_has_no_glyph_then_the_diagnostic_and_status_say_so(host) -> None:
    names, demo, editor = sequence_parts(host)
    editor.text_control.setText("AZ")
    assert editor.diagnostic.text == "Missing glyph for 'Z'"
    assert editor.select_key(host_key(host, "Key_End")) and demo.status.text == "Selected a missing glyph at position 2."


def test_sequence_when_glyph_names_are_typed_then_they_are_placed(host) -> None:
    names, demo, editor = sequence_parts(host)
    editor.mode_control.setCurrentIndex(1)
    editor.text_control.setText("/T /O")
    assert [g.name for g in editor.run.glyphs] == ["T", "O"] and editor.run.glyphs[1].x == 560 - 30


def test_sequence_when_wrapping_is_on_then_a_long_run_continues_on_further_lines(host, monkeypatch) -> None:
    names, demo, editor = sequence_parts(host)
    light_canvas(monkeypatch, sys.modules["fontlabapp.fontui.sequence_canvas"])
    editor.wrap_control.setChecked(True)
    lines = {line for _, line in editor.positions}
    assert len(lines) > 1, "the narrow canvas wraps the eight glyphs onto several lines"
    editor.canvas.paintEvent(None)
    assert editor.diagnostic.text == "Unicode lookup; no shaping", "painting raised nothing"


# --- Font Browser Demo ---------------------------------------------------------------------


def fonts_parts(host):
    names, demo = open_demo(host, FONTS)
    return names, demo, demo.editor


def test_fonts_when_opened_then_the_three_sample_fonts_are_listed_by_their_labels(host) -> None:
    names, demo, editor = fonts_parts(host)
    assert texts(editor.font_list) == ["Demo Serif Regular — Untitled", "Demo Sans Bold — Untitled", "Demo Sans Light — Untitled"]
    assert editor.count_label.text == "3 fonts"


def test_fonts_when_another_import_fails_then_the_message_does_not_blame_ufolib2(host, monkeypatch) -> None:
    real = importlib.import_module

    def broken(name, *args):
        if name in {"fontlabapp.fontui.fonts", "fly.ap.fontui.fonts"}:
            raise ImportError("cannot import name 'x'", name="fontlabapp.fontui.model")
        return real(name, *args)

    names = run_script(FONTS, "imported")
    monkeypatch.setattr(importlib, "import_module", broken)
    names["main"]()
    box = shown(host)
    assert box["informative"] == "An App module could not be imported." and "cannot import name 'x'" in box["details"]
    assert host.dialogs == [] and names["_HANDLES"] == []


@pytest.mark.parametrize(("path", "title", "needs", "factory", "follows"), NEEDING, ids=NEEDING_IDS)
def test_window_when_another_import_fails_then_the_message_does_not_blame_the_extra(host, monkeypatch, path, title, needs, factory, follows) -> None:
    real = importlib.import_module
    names = run_script(path, "imported")
    first = names["MODULES"][0]

    def broken(name, *args):
        if name == first:
            raise ImportError("cannot import name 'x'", name="fontlabapp.fontui.model")
        return real(name, *args)

    monkeypatch.setattr(importlib, "import_module", broken)
    names["main"]()
    box = shown(host)
    assert box["informative"] == "An App module could not be imported." and "cannot import name 'x'" in box["details"]
    assert host.dialogs == [] and names["_HANDLES"] == []


def test_batch_when_another_import_fails_then_the_message_does_not_blame_the_extra(host) -> None:
    names = run_script(BATCH, "imported")

    def broken():
        raise ImportError("cannot import name 'x'", name="fontlabapp.fontui.batch")

    names["main"].__globals__["lines"] = broken
    names["main"]()
    box = shown(host)
    assert box["informative"] == "An App module could not be imported." and "cannot import name 'x'" in box["details"]


def test_fonts_when_a_font_is_chosen_then_the_glyph_browser_lists_its_glyphs(host) -> None:
    names, demo, editor = fonts_parts(host)
    editor.font_list.setCurrentRow(1)
    assert texts(editor.browser.glyph_list) == ["A", "V"] and editor.browser.count_label.text == "2 glyphs"
    editor.font_list.setCurrentRow(2)
    assert texts(editor.browser.glyph_list) == ["T", "O"]


def test_fonts_when_sorted_then_the_browser_reorders_its_copy_and_the_sample_list_stays(host) -> None:
    names, demo, editor = fonts_parts(host)
    editor.sort()
    assert texts(editor.font_list) == ["Demo Sans Bold — Untitled", "Demo Sans Light — Untitled", "Demo Serif Regular — Untitled"]
    assert [font.info.styleName for font in demo.fonts] == ["Regular", "Bold", "Light"]


def test_fonts_when_a_glyph_is_double_clicked_then_the_status_names_it(host) -> None:
    names, demo, editor = fonts_parts(host)
    editor.font_list.setCurrentRow(1)
    editor.browser.glyph_list.itemDoubleClicked.emit(editor.browser.glyph_list.item(1))
    assert demo.status.text == "Activated glyph V of a sample font. Nothing was changed."


# --- Glyph Browser Demo --------------------------------------------------------------------


def glyphs_parts(host):
    names, demo = open_demo(host, GLYPHS)
    return names, demo, demo.editor


def test_glyphs_when_opened_then_every_glyph_is_listed_and_several_may_be_selected(host, monkeypatch) -> None:
    names, demo, editor = glyphs_parts(host)
    light_canvas(monkeypatch, sys.modules["fontlabapp.fontui.native"])
    assert texts(editor.glyph_list) == ["A", "V", "T", "O", "space"] and editor.count_label.text == "5 glyphs"
    assert ("setSelectionMode", ("ExtendedSelection",)) in editor.glyph_list.calls, "multiple selection was requested"
    editor.icon_timer.timeout.emit()  # thumbnails paint on the next idle turn
    assert all(item.icon is not None for item in editor.glyph_list.items), "each row has a thumbnail"


def test_glyphs_when_a_name_is_filtered_then_the_list_and_the_count_follow(host) -> None:
    names, demo, editor = glyphs_parts(host)
    editor.filter_control.setText("o")
    assert texts(editor.glyph_list) == ["O"] and editor.count_label.text == "1 glyphs"


def test_glyphs_when_a_glyph_is_selected_then_the_preview_shows_it_and_its_overlays_toggle(host, monkeypatch) -> None:
    names, demo, editor = glyphs_parts(host)
    light_canvas(monkeypatch, sys.modules["fontlabapp.fontui.preview"])
    editor.glyph_list.item(0).setSelected(True)  # A
    editor.glyph_list.itemSelectionChanged.emit()
    assert editor.preview.diagnostic.text == "A" and editor.state.selected == ("A",)
    editor.preview.option_controls["anchors"].setChecked(True)
    assert editor.preview.options["anchors"] is True
    editor.preview.canvas.paintEvent(None)
    assert editor.preview.diagnostic.text == "A", "painting the glyph, its metrics and its anchor raises nothing"


def test_glyphs_when_the_zoom_buttons_are_used_then_the_zoom_follows_inside_its_range(host) -> None:
    names, demo, editor = glyphs_parts(host)
    editor.preview.zoom_buttons["+"].clicked.emit()
    assert editor.preview.zoom == 1.25
    editor.preview.zoom_buttons["Fit"].clicked.emit()
    assert editor.preview.zoom == 1.0
    editor.preview.zoom_control.setValue(500)
    assert editor.preview.zoom == 20.0, "the spin box clamps to its range"


def test_glyphs_when_a_glyph_is_double_clicked_then_the_status_names_it(host) -> None:
    names, demo, editor = glyphs_parts(host)
    editor.glyph_list.itemDoubleClicked.emit(editor.glyph_list.item(3))
    assert demo.status.text == "Activated glyph O of the sample font. Nothing was changed."


def test_glyphs_when_the_mode_is_grid_then_the_list_switches_view(host) -> None:
    names, demo, editor = glyphs_parts(host)
    editor.mode_control.setCurrentIndex(1)
    assert editor.state.mode == "grid" and ("setViewMode", ("IconMode",)) in editor.glyph_list.calls


# --- Designspace Panel Demo ----------------------------------------------------------------


def designspace_parts(host):
    names, demo = open_demo(host, DESIGNSPACE)
    return names, demo, demo.editor


def test_designspace_when_opened_then_the_axes_start_at_their_defaults_on_a_source_master(host) -> None:
    names, demo, editor = designspace_parts(host)
    assert editor.values() == {"Weight": 400, "Width": 100}
    assert editor.status.text == "Source master: Regular" and demo.status.text == "Location Weight=400, Width=100."
    assert texts(editor.location_list) == [
        "Source: Light", "Source: Regular", "Source: Black Condensed", "Instance: Semibold",
        "Instance: Wide Light (unavailable: No font is made for it)",
    ]  # fmt: skip


def test_designspace_when_a_slider_moves_then_the_number_follows_inside_the_axis_range(host) -> None:
    names, demo, editor = designspace_parts(host)
    slider, number = editor.axes["Weight"]
    slider.setValue(60000)
    assert number.value == 600 and editor.status.text == "Instance location (not a source master): Weight=600, Width=100"
    assert demo.status.text == "Location Weight=600, Width=100."
    slider.setValue(10**6)
    assert slider.value == 90000 and number.value == 900, "the slider clamps to the axis maximum"


def test_designspace_when_a_number_is_typed_then_the_slider_follows(host) -> None:
    names, demo, editor = designspace_parts(host)
    slider, number = editor.axes["Width"]
    number.setValue(80.456)
    assert number.value == 80.46 and slider.value == 8046, "the number box rounds to two decimals"


def test_designspace_when_a_source_is_picked_then_the_axes_jump_to_it(host) -> None:
    names, demo, editor = designspace_parts(host)
    editor.location_list.setCurrentRow(2)
    assert editor.values() == {"Weight": 900, "Width": 75}
    assert editor.status.text == "Source master: Black Condensed" and demo.status.text == "Location Weight=900, Width=75."


def test_designspace_when_an_unavailable_instance_is_picked_then_the_axes_stay_and_the_reason_shows(host) -> None:
    names, demo, editor = designspace_parts(host)
    editor.location_list.setCurrentRow(4)
    assert editor.status.text == "Wide Light is unavailable: No font is made for it"
    assert editor.values() == {"Weight": 400, "Width": 100} and demo.status.text == "Location Weight=400, Width=100."


def test_designspace_when_reset_then_the_defaults_return(host) -> None:
    names, demo, editor = designspace_parts(host)
    editor.location_list.setCurrentRow(2)
    editor.reset_button.clicked.emit()
    assert editor.values() == {"Weight": 400, "Width": 100} and editor.status.text == "Source master: Regular"


def test_designspace_when_compared_with_fontports_designspace_then_the_stand_in_answers_alike() -> None:
    from fontTools.designspaceLib import DesignSpaceDocument
    from fontlab_fontport.designspace import Designspace

    sample = run_script(DESIGNSPACE, "imported")["SampleDesignspace"]()
    document = DesignSpaceDocument()
    for axis in sample.axes:
        document.addAxisDescriptor(name=axis.name, tag=axis.tag, minimum=axis.minimum, default=axis.default, maximum=axis.maximum)
    for entry in sample.sources:
        document.addSourceDescriptor(name=entry.name, designLocation=dict(entry.coordinates), font=object())
    real = Designspace(document)
    assert sample.defaults() == real.defaults()
    assert [(e.kind, e.name, dict(e.coordinates)) for e in sample.sources] == [(e.kind, e.name, dict(e.coordinates)) for e in real.sources]
    for values in ({}, {"Weight": 600}, {"Width": 80, "Weight": 100}):
        assert sample.location(values) == real.location(values)
        assert dict(sample.instance(values, "X").coordinates) == dict(real.instance(values, "X").coordinates)
    for bad in ({"Slant": 1}, {"Weight": 1000}, {"Width": 50}):
        with pytest.raises(ValueError) as stand_in:
            sample.location(bad)
        with pytest.raises(ValueError) as real_one:
            real.location(bad)
        assert str(stand_in.value) == str(real_one.value)


# --- Batch Panel Demo ----------------------------------------------------------------------


def test_batch_when_run_then_one_box_explains_the_panel_and_nothing_starts(host, monkeypatch) -> None:
    monkeypatch.delenv("FONTLABAPP_BATCH_PYTHON", raising=False)
    started = Recorder()
    monkeypatch.setattr(subprocess, "Popen", started)
    names = run_script(BATCH)
    box = shown(host)
    details = box["details"]
    assert box["title"] == "Batch Panel Demo" and box["informative"] == "Batch panel reference. Nothing was started, read or written."
    assert "Child Python: the python= argument, else $FONTLABAPP_BATCH_PYTHON (here: not set)." in details
    assert "Every 50 ms the panel reads at most 65536 bytes and 64 result rows from the child." in details
    assert "terminates the child after 10 s and kills it 5 s later." in details
    assert "never replace a file" in details and "PATH, HOME, TMPDIR, USER, LOGNAME, LANG, LC_ALL, LC_CTYPE" in details
    assert "does not open the panel" in details
    assert started.calls == [] and host.dialogs == [], "no process starts and no panel opens"
    assert callable(names["lines"])


def test_batch_when_the_python_variable_is_set_then_only_its_state_is_shown(host, monkeypatch) -> None:
    monkeypatch.setenv("FONTLABAPP_BATCH_PYTHON", "/private/location/python3.11")
    run_script(BATCH)
    details = shown(host)["details"]
    assert "(here: set)." in details and "/private/location" not in details


def test_batch_when_fontport_is_missing_then_a_message_names_the_extra(host, monkeypatch) -> None:
    block(monkeypatch, "fontlab_fontport")
    names = run_script(BATCH)
    box = shown(host)
    assert box["informative"] == names["MISSING"] and "fontlab-fontlabapp[fontport]" in box["details"]


def test_batch_when_imported_then_nothing_runs(host) -> None:
    run_script(BATCH, "imported")
    assert host.boxes == [] and host.dialogs == []


# --- Fontui Helpers Demo -------------------------------------------------------------------


def test_helpers_when_run_then_one_box_reports_every_section(host) -> None:
    run_script(HELPERS)
    box = shown(host)
    assert box["title"] == "Fontui Helpers Demo" and box["informative"] == "Sample fontui helper results. Nothing was read or written."
    details = box["details"]
    for section in ("fontui.model", "fontui.wrap", "fontui.features_state", "fontui.feature_blocks", "fontui.lifecycle"):
        assert f"== {section} ==" in details
    assert not details.endswith("\n"), "the report has no trailing blank line"


def test_helpers_when_run_then_the_model_lines_show_labels_filtering_the_viewport_and_open_paths(host) -> None:
    run_script(HELPERS)
    details = shown(host)["details"]
    assert "FontListState labels: ['Untitled — Untitled', 'Demo Sans Bold — Demo-Bold.ufo *']" in details
    assert "  after sort(): ['Demo Sans Bold — Demo-Bold.ufo *', 'Untitled — Untitled']" in details
    assert "names ['A', 'Aacute', 'B'], filter('a') -> ['A', 'Aacute'], select(['Aacute', 'missing']) -> ['Aacute']" in details
    assert "view 400 x 300): scale 0.26, x 122, y 228" in details
    assert "partition_paths: 3 commands in closed paths, 3 in open paths" in details


def test_helpers_when_run_then_wrapping_breaks_the_run_where_it_would_overflow(host) -> None:
    run_script(HELPERS)
    details = shown(host)["details"]
    assert "wrap(5 glyphs of advance 400, width 1000, 'ltr') -> [(0, 0), (400, 0), (0, 1), (400, 1), (0, 2)]" in details
    assert "wrap(..., width None) -> [(0, 0), (400, 0), (800, 0), (1200, 0), (1600, 0)]" in details


def test_helpers_when_run_then_staging_keeps_each_blocks_line_ending_and_refuses_mixed_ones(host) -> None:
    run_script(HELPERS)
    details = shown(host)["details"]
    assert "'a\\r\\nb' -> '\\r\\n', 'a\\nb' -> '\\n', 'a\\r\\nb\\n' -> None" in details
    assert "keys ['Prefix', 'kern', 'liga'], dirty True" in details
    assert "kern stays CRLF after the edit: 'feature kern {\\r\\n    pos A V -80;\\r\\n} kern;\\r\\n'" in details
    assert "Mixed line endings are refused: Prefix: Mixed line endings cannot be preserved; this block cannot be rewritten." in details


def test_helpers_when_run_then_the_host_modules_are_named_not_called(host) -> None:
    run_script(HELPERS)
    details = shown(host)["details"]
    assert "fontlabapp.fontui.feature_blocks exports read_feature_blocks, write_feature_blocks." in details
    assert "fontlabapp.fontui.lifecycle follows " + ", ".join(CHANGE_SIGNALS) + " and the actions actionUndo, actionRedo." in details
    assert "A first change arms one 100 ms timer" in details
    assert host.listeners() == 0 and host.dialogs == [], "nothing is connected and no window opens"


def test_helpers_when_imported_then_nothing_runs(host) -> None:
    run_script(HELPERS, "imported")
    assert host.boxes == []
