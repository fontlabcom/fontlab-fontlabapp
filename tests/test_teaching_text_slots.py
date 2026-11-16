# this_file: tests/test_teaching_text_slots.py
"""Qt Slot Reference: target capture, report building and panel lifecycle, on real offscreen Qt."""

import gc
import json
import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401

KINDS = NS(Signal="sig", Slot="slot")


def method(kind, signature):
    return NS(methodType=lambda: kind, methodSignature=lambda: NS(data=lambda: signature))


def owner_with(methods, name="QThing"):
    meta = NS(className=lambda: name, methodCount=lambda: len(methods), method=lambda i: methods[i])
    return NS(metaObject=lambda: meta)


@pytest.fixture
def slots(lab):  # noqa: F811
    module, shown = lab("slots")
    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    child = qt.QtGui.QPushButton("child", parent)
    yield module, qt, parent, child
    module._PANELS.clear()


def test_object_choices_when_no_owner_then_refused(slots):
    module, qt, parent, child = slots
    with pytest.raises(ValueError, match="main window"):
        module.object_choices(qt.QtGui, None)


def test_object_choices_when_children_then_labelled_and_gc_restored(slots):
    module, qt, parent, child = slots
    labels = [label for label, _ in module.object_choices(qt.QtGui, parent)]
    assert labels[:2] == ["Main window", "Focused widget at panel open"]
    assert any(label.endswith("QPushButton") for label in labels[2:]) and gc.isenabled()
    gc.disable()
    try:
        module.object_choices(qt.QtGui, parent)
        assert not gc.isenabled()  # not switched on if it was off
    finally:
        gc.enable()


def test_slot_report_when_methods_read_then_sorted_and_deduplicated():
    from fontlabapp.fontui.teaching_text import slots as mod

    owner = owner_with([method("sig", b"b()"), method("slot", "a(int)"), method("sig", b"a()"),
                        method("sig", b"a()"), method("other", b"x()")])
    report = json.loads(mod.slot_report(owner, KINDS))
    assert report["class"] == "QThing" and report["signals"] == ["a()", "b()"] and report["slots"] == ["a(int)"]
    assert report["availability"] == "available" and report["invoked"] is False


def test_slot_report_when_binding_lacks_metadata_then_fallback_with_rules():
    from fontlabapp.fontui.teaching_text import slots as mod

    report = json.loads(mod.slot_report(NS(), KINDS))
    assert report["availability"] == "not available on this build" and "AttributeError" in report["detail"]
    assert report["PythonQt rules"][0].startswith("Widgets live in")
    with pytest.raises(ValueError, match="absent or destroyed"):
        mod.slot_report(None, KINDS)


def test_panel_when_read_then_report_shown_and_bad_choice_refused(slots):
    module, qt, parent, child = slots
    panel = module.show(qt, parent, embedded=True)
    assert panel in module._PANELS and len(panel.targets) >= 3
    assert "PythonQt rules" in panel.output_box.toPlainText()
    panel.target_picker.setCurrentIndex(0)
    panel.read_slots()
    assert json.loads(panel.output_box.toPlainText())["class"] and panel.status_line.text() in {
        "available", "not available on this build"}
    panel.forget_target(1)
    assert panel.targets[1] is None
    panel.target_picker.setCurrentIndex(1)
    with pytest.raises(ValueError, match="absent or destroyed"):
        panel.read_slots()
    panel.targets = []
    with pytest.raises(ValueError, match="Choose an available"):
        panel.read_slots()


def test_panel_when_read_button_clicked_then_wrapped_action_runs(slots):
    module, qt, parent, child = slots
    panel = module.show(qt, parent, embedded=True)
    panel.target_picker.setCurrentIndex(0)
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == "Read Reference"][0].click()
    assert json.loads(panel.output_box.toPlainText())["class"]


def test_panel_when_closed_then_scopes_finished_or_retained(slots):
    module, qt, parent, child = slots
    panel = module.show(qt, parent, embedded=True)
    event = NS(ignored=False, accepted=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: setattr(event, "accepted", True))
    panel.scope.finish = lambda destroyed=False: False
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    del panel.scope.finish
    panel.closeEvent(event)
    assert event.accepted and panel not in module._PANELS
    panel.release_owner()  # idempotent after close


def test_show_when_window_show_fails_then_panel_released_or_kept(slots, monkeypatch):
    module, qt, parent, child = slots
    monkeypatch.setattr(qt.QtGui.QWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("no screen")))
    with pytest.raises(RuntimeError, match="no screen"):
        module.show(qt, parent)
    assert module._PANELS == []
    import fontlabapp.core.signals.scope as signals

    monkeypatch.setattr(signals.Scope, "finish", lambda self, destroyed=False: False)
    with pytest.raises(RuntimeError, match="no screen"):
        module.show(qt, parent)
    assert len(module._PANELS) == 1  # cleanup failed: retained for a retry


def test_main_and_build_when_run_then_use_main_window(slots, monkeypatch, capsys):
    module, qt, parent, child = slots
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    panel = module.build(None)
    assert panel in module._PANELS and panel.targets[0] is parent
    seen = []
    monkeypatch.setattr(module, "show", lambda q, p: seen.append(p))
    module.main()
    assert seen == [parent]
    monkeypatch.setattr(module, "show", lambda q, p: (_ for _ in ()).throw(ValueError("nope")))
    module.main()
    assert capsys.readouterr().out == f"{module.TITLE}: nope\n"
