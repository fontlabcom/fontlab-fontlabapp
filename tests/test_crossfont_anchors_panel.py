# this_file: tests/test_crossfont_anchors_panel.py
"""Actual standalone Qt5/Qt6 controls; no native host/fonts/clipboard access."""

import os
import sys
from types import SimpleNamespace as NS

import pytest

if os.environ.get("CROSSFONT_TEST_QT") == "qt5":
    from PyQt5 import QtCore as core, QtGui as paint, QtWidgets as widgets
else:
    from PySide6 import QtCore as core, QtGui as paint, QtWidgets as widgets
from fontlabapp.anchors.crossfont.ui import KEY, panel_type
from fontlabapp.qt.properties import value

GUI = NS(
    **{
        name: getattr(widgets, name)
        for name in (
            "QDialog",
            "QVBoxLayout",
            "QGridLayout",
            "QLabel",
            "QPushButton",
            "QLineEdit",
            "QComboBox",
            "QRadioButton",
            "QButtonGroup",
            "QSpinBox",
            "QCheckBox",
            "QGroupBox",
            "QPlainTextEdit",
        )
    },
    QCloseEvent=paint.QCloseEvent,
)


class Backend:
    def __init__(self):
        self.rows = (
            NS(identity=1, label="same.vfj", masters=("Light", "Bold")),
            NS(identity=2, label="same.vfj", masters=("Other",)),
        )
        self.calls = []
        self.fail = False

    def fonts(self):
        return self.rows

    def copy(self, *args):
        self.calls.append(args)
        if self.fail:
            raise ValueError("Activate the chosen source Font window")
        return {
            "anchors": 2,
            "layers": 1,
            "skipped": ("Missing layer: b/Light → Other",),
            "zero_advance": (("a", "top"),),
        }


@pytest.fixture
def panel():
    app = widgets.QApplication.instance() or widgets.QApplication([])
    parent = widgets.QWidget()
    parent_destroyed = []
    parent.destroyed.connect(lambda *args: parent_destroyed.append(True))
    backend = Backend()
    dialog = panel_type(core, GUI)(parent, backend)
    registry = sys.__dict__.setdefault("_fontlab_samples", {})
    assert KEY not in registry
    registry[KEY] = dialog
    dialog.show()
    app.processEvents()
    yield dialog, backend, app, parent
    if not dialog.dead:
        dialog.close()
        core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    if not parent_destroyed:
        parent.deleteLater()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert KEY not in registry


def test_all_original_controls_defaults_font_identity_and_independent_refresh(panel):
    d, _b, _app, _parent = panel
    assert (
        d.all_glyphs.isChecked()
        and d.all_anchors.isChecked()
        and d.absolute.isChecked()
    )
    assert (
        d.rename.isChecked()
        and d.rename_destination.isChecked()
        and not d.italic.isChecked()
    )
    assert (
        value(d.suffix, "text") == ".bak"
        and value(d.angle, "minimum") == 0
        and value(d.angle, "maximum") == 20
        and value(d.angle, "value") == 10
    )
    assert (
        d.source_font.itemText(0) == "same.vfj [#1]"
        and d.source_font.itemText(1) == "same.vfj [#2]"
    )
    assert (
        value(d.source_layer, "count") == 1 and value(d.destination_layer, "count") == 1
    )
    d.source_layer_refresh.click()
    assert [
        d.source_layer.itemText(i) for i in range(value(d.source_layer, "count"))
    ] == ["*All masters*", "Light", "Bold"]
    assert value(d.destination_layer, "count") == 1
    d.destination_font.setCurrentIndex(1)
    d.destination_layer_refresh.click()
    assert d.destination_layer.itemText(1) == "Other"
    d.source_font_refresh.click()
    assert (
        value(d.destination_font, "currentIndex") == 0
        and value(d.source_layer, "count") == value(d.destination_layer, "count") == 1
    )
    d.destination_font_refresh.click()
    assert value(d.source_font, "currentIndex") == 0
    assert d.windowFlags() & core.Qt.WindowStaysOnTopHint and not d.isModal()
    assert d.isWindow() and d.isVisible()


def test_actual_copy_button_dispatches_every_original_alternative_and_retains_diagnoses(
    panel,
):
    d, b, _app, _parent = panel
    d.source_font.setCurrentIndex(1)
    d.destination_font.setCurrentIndex(0)
    d.source_layer_refresh.click()
    d.source_layer.setCurrentIndex(1)
    d.destination_layer_refresh.click()
    d.destination_layer.setCurrentIndex(2)
    d.selected_glyphs.click()
    d.specific_anchors.click()
    d.anchor_names.setText(" top, bottom ")
    d.relative.click()
    d.overwrite.click()
    d.incoming.click()
    d.suffix.setText(" .new ")
    d.italic.click()
    d.angle.setValue(20)
    d.copy_button.click()
    args = b.calls[-1]
    assert args[:5] == (2, 1, "Other", "Bold", True)
    o = args[-1]
    assert (
        o.relative
        and o.italic
        and o.angle == 20
        and not o.rename
        and not o.rename_destination
    )
    assert o.specific == " top, bottom " and o.suffix == " .new "
    assert (
        d.last_result["anchors"] == 2
        and "Missing layer" in d.details.toPlainText()
        and "Zero source advance" in d.details.toPlainText()
    )
    b.fail = True
    d.copy_button.click()
    assert d.last_result is None and "Activate the chosen source" in d.details.toPlainText()


def test_no_open_fonts_disable_copy_but_refresh_recovers_and_closed_id_is_not_retargeted(
    panel,
):
    d, b, _app, _parent = panel
    b.rows = ()
    d.source_font_refresh.click()
    assert not d.copy_button.isEnabled() and "No open font" in value(d.status, "text")
    b.rows = (NS(identity=99, label="same.vfj", masters=("New",)),)
    d.destination_font_refresh.click()
    assert d.copy_button.isEnabled() and value(d.source_font, "currentIndex") == 0
    b.rows = ()
    d.source_layer_refresh.click()
    assert "closed" in d.details.toPlainText()


@pytest.mark.parametrize(
    "terminal", ["close", "reject", "accept", "done", "escape", "button", "parent"]
)
def test_all_owned_terminal_paths_destroy_disconnect_and_fence_late_actions(
    panel, terminal
):
    d, b, _app, parent = panel
    seen = []
    d.destroyed.connect(lambda *args: seen.append(True))
    if terminal == "parent":
        parent.deleteLater()
    elif terminal == "escape":
        widgets.QApplication.sendEvent(
            d,
            paint.QKeyEvent(
                core.QEvent.KeyPress, core.Qt.Key_Escape, core.Qt.NoModifier
            ),
        )
    elif terminal == "button":
        d.close_button.click()
    elif terminal == "done":
        d.done(0)
    else:
        getattr(d, terminal)()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert (
        seen == [True] and d.dead and not d.signals.records and not d.terminal.records
    )
    assert getattr(sys, "_fontlab_samples", {}).get(KEY) is not d
    d.copy()
    d.refresh_fonts()
    d.refresh_layers("source")
    assert not b.calls


def test_close_disconnect_failure_retains_owner_then_retry_drains_exact_signal(panel):
    d, b, _app, _parent = panel
    signal, slot, retry = d.signals.records[0]

    class Fault:
        failed = False

        def disconnect(self, callback):
            if not self.failed:
                self.failed = True
                raise RuntimeError("owned disconnect refused")
            return signal.disconnect(callback)

    d.signals.records[0] = (Fault(), slot, retry)
    assert d.close() is False and d.closed and not d.dead
    assert sys._fontlab_samples[KEY] is d and d.signals.records
    d.copy()
    assert not b.calls
    d.close_button.click()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert d.dead and KEY not in sys._fontlab_samples


def test_empty_copy_result_and_busy_reentrancy_never_dispatch_twice(panel):
    d, b, _app, _parent = panel
    d.busy = True
    d.copy()
    d.refresh_fonts()
    d.refresh_layers("source")
    assert not b.calls
    d.busy = False
    b.copy = lambda *args: {
        "anchors": 0,
        "layers": 0,
        "skipped": (),
        "zero_advance": (),
    }
    d.copy_button.click()
    assert "Nothing to process!" in value(d.status, "text")


def test_constructor_failure_destroys_owned_dialog_and_does_not_publish_registry(panel):
    d, _b, _app, parent = panel

    class Fault(Backend):
        def fonts(self):
            raise RuntimeError("font scan failed")

    seen = []

    class Kind(panel_type(core, GUI)):
        def __init__(self, *args):
            try:
                super().__init__(*args)
            finally:
                self.destroyed.connect(lambda *args: seen.append(True))

    with pytest.raises(RuntimeError, match="font scan failed"):
        Kind(parent, Fault())
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert seen == [True] and sys._fontlab_samples[KEY] is d


def test_constructor_cleanup_refusal_retains_exact_owner_for_explicit_retry(
    panel, monkeypatch
):
    _d, _b, _app, parent = panel
    import fontlabapp.anchors.crossfont.ui as module

    original = module.Scope.finish
    failed = []

    def refuse_once(self, *, destroyed=False):
        if not destroyed and not failed:
            failed.append(True)
            return False
        return original(self, destroyed=destroyed)

    monkeypatch.setattr(module.Scope, "finish", refuse_once)

    class Fault(Backend):
        def fonts(self):
            raise RuntimeError("font scan failed")

    old = sys._fontlab_samples.pop(KEY)
    with pytest.raises(RuntimeError, match="font scan failed"):
        panel_type(core, GUI)(parent, Fault())
    retained = sys._fontlab_samples[KEY]
    assert retained is not old and retained.closed and not retained.dead
    retained.close()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert retained.dead and KEY not in sys._fontlab_samples
    sys._fontlab_samples[KEY] = old


def test_non_escape_key_uses_native_base_and_invalid_empty_choice_is_not_aliased(panel):
    d, b, _app, _parent = panel
    widgets.QApplication.sendEvent(
        d, paint.QKeyEvent(core.QEvent.KeyPress, core.Qt.Key_X, core.Qt.NoModifier, "x")
    )
    assert not b.calls
    d.source_font.clear()
    with pytest.raises(ValueError, match="Refresh"):
        d.copy()
    assert not d.busy and not b.calls


def test_full_many_glyph_diagnostics_remain_complete_and_controls_reachable(panel):
    d, b, app, _parent = panel
    before = d.height()
    skipped = tuple("Missing destination glyph " + str(i) for i in range(500))
    b.copy = lambda *args: {
        "anchors": 0,
        "layers": 0,
        "skipped": skipped,
        "zero_advance": (),
    }
    d.copy_button.click()
    app.processEvents()
    assert d.height() <= before + 200
    assert d.details.isReadOnly() and d.details.toPlainText().splitlines() == list(
        skipped
    )
    assert d.copy_button.isVisible() and d.close_button.isVisible()
    d.failure(ValueError("long failure " + ("example " * 3000)))
    app.processEvents()
    assert d.height() <= before + 200 and d.details.toPlainText() == d.last_error
