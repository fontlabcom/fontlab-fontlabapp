# this_file: tests/test_component_recipes_dialog.py
"""Exercise actual adapted widgets offscreen; never run reference bodies."""

import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch):
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
    for name in ("fontlabapp.glyphs.names.ui", "fontlabapp.components.recipes.ui"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    mod = importlib.import_module("fontlabapp.components.recipes.ui")
    report = mod.api.RecipeSnapshot(
        1,
        "Regular",
        (
            mod.api.RecipeLayer("Aacute", ("A", "acute")),
            mod.api.RecipeLayer("empty", ()),
        ),
    )
    monkeypatch.setattr(mod.api, "capture", lambda: report)
    widget = mod.ComponentRecipesDialog()
    yield widget, mod
    if isValid(widget):
        widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_complete_original_recipe_text_readonly_and_modeless(panel):
    widget, _mod = panel
    assert widget.output.toPlainText() == "A+acute=Aacute\n"
    assert widget.output.isReadOnly() and not widget.isModal()
    assert "Recipes: 1 · Layers: 2" in widget.status.text()
    assert "repeated editor occurrences" in widget.subtitle.text()


@pytest.mark.parametrize(
    "error", [ValueError("missing layer"), TimeoutError("deadline")]
)
def test_refresh_clears_old_snapshot_on_failure_then_recovers(
    panel, monkeypatch, error
):
    widget, mod = panel
    original = mod.api.capture

    def fail():
        raise error

    monkeypatch.setattr(mod.api, "capture", fail)
    widget.refresh_button.click()
    assert widget.report is None and widget.output.toPlainText() == ""
    assert str(error) in widget.status.text() and widget.close_button.isEnabled()
    monkeypatch.setattr(mod.api, "capture", original)
    widget.refresh()
    assert widget.output.toPlainText() == "A+acute=Aacute\n"


def test_opening_failure_remains_diagnosed_and_closable(panel, monkeypatch):
    _, mod = panel
    monkeypatch.setattr(
        mod.api, "capture", lambda: (_ for _ in ()).throw(ValueError("No font"))
    )
    widget = mod.ComponentRecipesDialog()
    assert widget.report is None and "No font" in widget.status.text()
    widget.close_button.click()
    widget.refresh()
    assert widget._closed and not widget._connections


@pytest.mark.parametrize("owner", ["close", "direct", "parent"])
def test_saved_callbacks_are_inert_after_every_destruction_route(
    panel, monkeypatch, owner
):
    _, mod = panel
    parent = QtWidgets.QWidget()
    widget = mod.ComponentRecipesDialog(parent)
    callbacks = tuple(slot for _, slot in widget._connections[:2])
    if owner == "close":
        widget.close()
    else:
        (parent if owner == "parent" else widget).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)

    def forbidden(self):
        pytest.fail("Closed callback touched a native widget method")

    with monkeypatch.context() as patch:
        patch.setattr(mod.ComponentRecipesDialog, "close", forbidden)
        patch.setattr(mod.ComponentRecipesDialog, "invalidate", forbidden)
        for callback in callbacks:
            callback()
    assert widget._closed and not widget._connections and not widget._disconnect_errors
    if isValid(parent):
        parent.deleteLater()


def test_factory_and_repeat_launch_replace_only_owned_panel(panel, monkeypatch):
    _, mod = panel
    from fontlabapp.core import scripting

    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: None))
    assert scripting.component_recipes_dialog_type() is mod.ComponentRecipesDialog
    first = scripting.show_script_dialog(
        mod.ComponentRecipesDialog, mod.ComponentRecipesDialog.KEY
    )
    second = scripting.show_script_dialog(
        mod.ComponentRecipesDialog, mod.ComponentRecipesDialog.KEY
    )
    assert first._closed and not first._connections
    second.close()


def test_registry_cleanup_and_disconnect_failure_are_contained(panel):
    widget, _ = panel
    sys.__dict__.setdefault("_fontlab_samples", {})[widget.KEY] = widget

    class Failed:
        def disconnect(self, slot):
            raise RuntimeError("disconnect")

    widget._connections.append((Failed(), lambda: None))
    widget._destroyed()
    assert widget._disconnect_errors == ["RuntimeError('disconnect')"]
    assert widget.KEY not in sys._fontlab_samples
    widget.close()


def test_refresh_checks_native_document_view_separately_from_report_focus(
    panel, monkeypatch
):
    widget, mod = panel
    from fontlabapp.core import scripting

    package = NS(id=1, isNull=False)
    frame = NS(inherits=lambda name: name == "YFrameWindow")
    font_panel = NS(
        inherits=lambda name: name == "FontWindow", parentWidget=lambda: frame
    )
    workspace = NS(currentPackage=package, activeFontPanel=font_panel)
    original_native = scripting._native
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: (
            NS(flWorkspace=NS(instance=lambda: workspace))
            if name == "fontlab"
            else original_native(name)
        ),
    )
    snapshot = widget.report

    def capture():
        mod.api.selection._require_selection_window(1)
        return snapshot

    monkeypatch.setattr(mod.api, "capture", capture)
    widget.show()
    widget.activateWindow()
    APP.processEvents()
    assert APP.activeWindow() is widget, (
        "The modeless report really holds Qt focus in this owned test"
    )
    widget.refresh_button.click()
    assert widget.report is snapshot
    # Official MainWindow source clears this field on Glyph-window activation.
    workspace.activeFontPanel = None
    widget.refresh_button.click()
    assert widget.report is None and widget.output.toPlainText() == ""
    assert "Font window" in widget.status.text()
