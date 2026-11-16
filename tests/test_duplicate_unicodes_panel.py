# this_file: tests/test_duplicate_unicodes_panel.py
"""Actual owned Qt tree actions; never call a host or global clipboard."""

import os
import sys
from types import SimpleNamespace as NS

import pytest

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
else:
    from PySide6 import QtCore as C, QtGui as G, QtWidgets as W
import fontlabapp
import fontlabapp.glyphs.unicode.duplicates.ui as ui
import fontlabapp.core.scripting as scripts
from fontlabapp.glyphs.unicode.duplicates.model import Glyph, Snapshot


class Gui:
    QCloseEvent = G.QCloseEvent
    QColor = G.QColor
    QPalette = G.QPalette
    QBrush = G.QBrush

    def __getattr__(self, name):
        return getattr(W, name)


class Backend:
    def __init__(self):
        self.facts = Snapshot(
            (7,),
            tuple(
                Glyph(i, i + 10, n, c, (), ())
                for i, (n, c) in enumerate(
                    [("secondary", (66, 65)), ("primary", (65, 66)), ("other", (65,))]
                )
            ),
            (),
        )
        self.calls = []
        self.fail = False

    def capture(self):
        return self.facts

    def apply(self, facts, removals):
        self.calls.append((facts, removals))
        if self.fail:
            raise ValueError("owned stale source")
        assert removals
        self.facts = Snapshot((7,), (), ())
        return {"changed": ["secondary"], "removals": 1}


@pytest.fixture
def panel(monkeypatch):
    app = W.QApplication.instance() or W.QApplication([])
    qt = NS(QtCore=C, QtGui=Gui())
    monkeypatch.setattr(fontlabapp, "_native", lambda n: qt)
    monkeypatch.setattr(scripts, "_native", lambda n: qt)
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    backend = Backend()
    p = ui.dialog_type(qt)(backend=backend)
    p.show()
    app.processEvents()
    dead = []
    p.destroyed.connect(lambda *args: dead.append(True))
    yield app, qt, p, backend
    if not dead:
        p.close()
    app.sendPostedEvents(None, C.QEvent.DeferredDelete)


def test_all_original_controls_defaults_labels_unticking_apply_refresh(panel):
    _app, _qt, p, b = panel
    assert p.tree.topLevelItemCount() == 2 and p.tree.topLevelItem(0).isExpanded()
    assert p.items["primary", 65].checkState(0) == C.Qt.Unchecked
    assert p.items["secondary", 65].checkState(0) == C.Qt.Checked
    assert p.items["primary", 66].checkState(0) == C.Qt.Checked
    assert p.status.text() == "3 removals ticked"
    p.items["secondary", 65].setCheckState(0, C.Qt.Unchecked)
    assert (
        p.items["secondary", 65].text(1) == "keeps it"
        and p.status.text() == "2 removals ticked"
    )
    p.apply_button.click()
    assert b.calls[0][1] == [("other", 65), ("primary", 66)]
    assert p.tree.topLevelItemCount() == 0 and p.status.text() == "Updated 1 glyph"
    assert not p.apply_button.isEnabled()


def test_rescan_new_font_no_font_and_error_invalidates(panel):
    _app, _qt, p, b = panel
    b.facts = None
    p.reload_button.click()
    assert p.subtitle.text() == "Open a font first." and not p.apply_button.isEnabled()
    b.facts = Snapshot((8,), (), ())
    p.reload_button.click()
    assert "0 glyphs" in p.subtitle.text()
    b.facts = Backend().facts
    p.reload_button.click()
    b.fail = True
    p.apply_button.click()
    assert "owned stale source" in p.status.text() and not p.apply_button.isEnabled()
    assert p.tree.topLevelItemCount() == 0
    b.fail = False
    p.reload_button.click()
    assert p.apply_button.isEnabled()


def test_all_unticked_has_noop_and_close_destroys_owned_window(panel):
    app, _qt, p, b = panel
    for item in p.items.values():
        item.setCheckState(0, C.Qt.Unchecked)
    assert p.status.text() == "0 removals ticked" and not p.apply_button.isEnabled()
    p.apply()
    assert not b.calls
    dead = []
    p.destroyed.connect(lambda *a: dead.append(True))
    p.close_button.click()
    app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert dead == [True]


@pytest.mark.parametrize("terminal", ["accept", "reject", "done", "close"])
def test_every_visible_terminal_destroys_and_late_callbacks_are_inert(panel, terminal):
    app, _qt, p, backend = panel
    callbacks = [slot for _, slot, _ in p.signals.records]
    dead = []
    p.destroyed.connect(lambda *args: dead.append(True))
    getattr(p, terminal)(42) if terminal == "done" else getattr(p, terminal)()
    app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert dead == [True] and p.signals.dead
    for callback in callbacks:
        callback()
    assert backend.calls == []
    p.reload()
    p.update_actions()
    p.apply()


def test_failed_close_retains_retry_button_and_cannot_write(panel):
    app, _qt, p, backend = panel
    original, slot, retry = p.signals.records[0]

    class Once:
        fail = True

        def disconnect(self, callback):
            if self.fail:
                self.fail = False
                raise RuntimeError("owned disconnect failure")
            return original.disconnect(callback)

    p.signals.records[0] = (Once(), slot, retry)
    assert p.close() is False
    assert p.signals.closed and not p.signals.dead and not backend.calls
    p.close_button.click()
    app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert p.signals.dead and not backend.calls


def test_parent_destruction_and_constructor_failure_release_owned_state(panel):
    app, qt, _p, _backend = panel
    parent = W.QWidget()
    child = ui.dialog_type(qt)(parent, backend=Backend())
    sys._fontlab_samples["names_duplicate_unicodes"] = child
    dead = []
    child.destroyed.connect(lambda *args: dead.append(True))
    parent.deleteLater()
    app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert dead == [True] and child.signals.dead and not sys._fontlab_samples

    class Broken(Backend):
        def capture(self):
            raise ValueError("owned capture failure")

    with pytest.raises(ValueError, match="owned capture failure"):
        ui.dialog_type(qt)(backend=Broken())
    app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert not sys._fontlab_samples


def test_reentrant_apply_rescan_and_close_do_not_split_one_transaction(panel):
    _app, _qt, p, backend = panel
    original = backend.apply

    def apply(facts, removals):
        p.apply()
        p.reload()
        p.update_actions()
        assert p.close() is False
        return original(facts, removals)

    backend.apply = apply
    p.apply_button.click()
    assert len(backend.calls) == 1 and p.status.text() == "Updated 1 glyph"
    assert not p._busy


def test_external_parent_destruction_during_apply_never_dereferences_dead_widgets(
    panel,
):
    app, _qt, p, backend = panel
    original = backend.apply

    def apply(facts, removals):
        result = original(facts, removals)
        p.deleteLater()
        app.sendPostedEvents(None, C.QEvent.DeferredDelete)
        return result

    backend.apply = apply
    p.apply()
    assert p._dead and p.signals.dead and len(backend.calls) == 1
