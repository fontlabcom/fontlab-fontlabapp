# this_file: tests/test_raise_ascender_backend.py
"""Whole adapter/model/writer sequential actions with source-shaped owned doubles."""

import os
from time import monotonic
from types import SimpleNamespace as NS

import pytest

import fontlabapp.contours.raise_ascender._capture as capture
import fontlabapp.contours.raise_ascender.native as api

if os.environ.get('FONTLABAPP_TEST_QT5') == '1':
    from PyQt5 import QtCore as C
else:
    from PySide6 import QtCore as C
from test_raise_ascender_geometry import fixture as geometry_layer


def setup(monkeypatch, repeated=True, auto=False, queue=()):
    events = []
    layer = geometry_layer()
    layer.id, layer.isNull, layer.isValid = 10, False, True
    layer.checkInitHistoryState = lambda value: events.append("layer:history")
    layer.removeShape = lambda old: layer.shapes.remove(old)
    layer.insertShape = lambda index, shape: layer.shapes.insert(index, shape)
    layer.changed = lambda: events.append("changed")
    layer.update = lambda: True
    glyph = NS(id=20, name="A", isNull=False)
    glyph.checkInitHistoryState = lambda value: events.append("glyph:history")
    layer.glyph = glyph
    package = NS(id=30, findName=lambda name: glyph)
    glyph.package = package
    document = NS(package=package, context=(30, "Regular", "font"), carriers=())
    monkeypatch.setattr(api, "current_package", lambda: package)
    monkeypatch.setattr(
        api,
        "selected",
        lambda all_layers, deadline: (
            document,
            ((glyph, layer),) * (2 if repeated else 1),
        ),
    )
    monkeypatch.setattr(api, "masters", lambda package, deadline: (("Regular", 500.0),))
    deps = ((20, "A", ((10, "Regular.aux", auto, ()),)),)
    monkeypatch.setattr(api, "dependencies", lambda package, deadline: deps)

    def notify(*args):
        events.append("notify")

    native = NS(
        flGlyph=NS(updatedFgGlyphs=lambda: queue),
        flItems=lambda: NS(notifyChangesApplied=notify),
    )
    monkeypatch.setattr(
        api, "_native", lambda name: native if name == "fontlab" else NS(QtCore=C)
    )
    return api.Backend(), layer, events, document


def test_complete_repeated_negative_action_single_changed_scope_then_noop(monkeypatch):
    backend, layer, events, _doc = setup(monkeypatch)
    result = backend.execute("-20", False)
    assert result == {"occurrences": 2, "undo_steps": 1, "nodes": 1, "pending_updates": (), "pending_note": ""}
    assert layer.shapes[0].contours[0].nodes()[1].position.y() == 500
    assert events.count("notify") == 1 and events.count("layer:history") == 1


def test_repeated_positive_action_keeps_two_distinct_history_notifications(monkeypatch):
    backend, layer, events, _doc = setup(monkeypatch)
    result = backend.execute("10", False)
    assert result == {"occurrences": 2, "undo_steps": 2, "nodes": 2, "pending_updates": (), "pending_note": ""}
    assert events.count("notify") == 2
    assert layer.shapes[0].contours[0].nodes()[1].position.y() == 540


def test_noop_ignores_pending_queue_and_automatic_writer_limits_without_history(
    monkeypatch,
):
    backend, layer, events, _doc = setup(monkeypatch, auto=True, queue=(99,))
    layer.autoLayer = True
    assert backend.execute("0", False)["undo_steps"] == 0
    assert not events


def test_automatic_dependants_refuse_before_any_history(monkeypatch):
    backend, layer, events, _doc = setup(monkeypatch, auto=True)
    with pytest.raises(ValueError):
        backend.execute("10", False)
    assert not events and layer.shapes[0].id == 31


def test_changed_font_or_geometry_read_refuses_before_history(monkeypatch):
    backend, layer, events, doc = setup(monkeypatch)
    doc.package.id = 31
    with pytest.raises(ValueError, match="original font"):
        backend.capture(False, monotonic() + 10)
    assert not events
    doc.package.id = 30
    original = api.read
    count = 0

    def moving(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            layer.note = "changed concurrently"
        return original(*args, **kwargs)

    monkeypatch.setattr(api, "read", moving)
    with pytest.raises(ValueError, match="changed during capture"):
        backend.capture(False, monotonic() + 10)
    assert not events


def test_checked_component_closure_transitive_cycles_and_deadline():
    deps = (
        (1, "A", ((1, "Regular", False, ()),)),
        (2, "B", ((2, "Regular", False, ("A",)),)),
        (3, "C", ((3, "aux", False, ("B", "C")),)),
    )
    assert api.closure(deps, {"A"}, monotonic() + 10) == {"A", "B", "C"}
    with pytest.raises(TimeoutError):
        api.closure(deps, {"A"}, 0)


def test_named_metric_serialization_does_not_fallback_to_current_master(monkeypatch):
    package = NS(id=1, fgId=9, masters=("Regular", "Bold"))
    data = {
        "masters": [
            {"fontMaster": {"name": "Bold", "xHeight": 600}},
            {"fontMaster": {"name": "Regular"}},
        ]
    }
    monkeypatch.setattr(capture, "_native", lambda name: NS(call=lambda *a, **kw: data))
    assert capture.masters(package, monotonic() + 10) == (("Regular", 0), ("Bold", 600))
    data["masters"].pop()
    with pytest.raises(ValueError, match="unique"):
        capture.masters(package, monotonic() + 10)


def test_owner_main_thread_and_late_source_validation_refuse(monkeypatch):
    backend, layer, events, _doc = setup(monkeypatch)
    monkeypatch.setattr(api, 'current_thread', lambda: object())
    with pytest.raises(RuntimeError, match='main UI'):
        backend.capture(False, monotonic() + 10)
    monkeypatch.setattr(api, 'current_thread', api.main_thread)
    layer.glyph = NS(id=-1)
    with pytest.raises(ValueError, match='owner'):
        backend.capture(False, monotonic() + 10)
    assert not events


def test_source_drift_after_detached_staging_prevents_first_history(monkeypatch):
    backend, layer, events, _doc = setup(monkeypatch)
    prepare = api.prepare
    def moving(*args):
        result = prepare(*args)
        layer.note = 'intervening authored edit'
        return result
    monkeypatch.setattr(api, 'prepare', moving)
    with pytest.raises(ValueError, match='before history'):
        backend.execute('10', False)
    assert not events and layer.shapes[0].id == 31


def test_transitive_dependant_identity_is_enrolled_and_changed_owner_refuses(monkeypatch):
    backend, layer, _events, _doc = setup(monkeypatch)
    facts = backend.capture(False, monotonic() + 10)
    dependent = NS(id=40)
    layer.glyph.package.findName = lambda name: dependent
    deps = (*facts.dependencies, (40, 'B', ((21, 'Regular', False, ('A',)),)))
    assert backend._dependants(facts.rows[0], deps, monotonic() + 10) == (dependent,)
    dependent.id = -1
    with pytest.raises(ValueError, match='dependant identity'):
        backend._dependants(facts.rows[0], deps, monotonic() + 10)


def test_post_notification_callback_drift_stops_second_occurrence(monkeypatch):
    backend, layer, events, _doc = setup(monkeypatch)
    native = api._native('fontlab')
    def notify(*args):
        events.append('notify')
        layer.note = 'plugin edit during notification'
    native.flItems = lambda: NS(notifyChangesApplied=notify)
    with pytest.raises(RuntimeError, match='1 completed'):
        backend.execute('10', False)
    assert events.count('notify') == 1


@pytest.mark.parametrize("all_layers", [False, True])
def test_pending_queue_is_read_once_and_disclosed_without_blocking(monkeypatch, all_layers):
    backend, layer, events, _ = setup(monkeypatch, queue=(99, 100))
    native = api._native("fontlab")
    calls = []
    def queue():
        calls.append("read")
        assert len(calls) == 1, "Do not reread or clear the native queue"
        return (99, 100)
    native.flGlyph.updatedFgGlyphs = queue
    disclosure = {}
    result = backend.execute("10", all_layers, disclosure=disclosure)
    assert result["nodes"] == 2 and events.count("notify") == 2
    assert result["pending_updates"] == (99, 100)
    assert disclosure == {"pending_updates": (99, 100), "pending_note": result["pending_note"]}
    assert "8537" in result["pending_note"] and calls == ["read"]


def test_queue_change_during_staging_is_disclosed_not_source_drift(monkeypatch):
    backend, layer, events, _ = setup(monkeypatch)
    native = api._native("fontlab")
    prepare = api.prepare
    def staging(*args):
        result = prepare(*args)
        native.flGlyph.updatedFgGlyphs = lambda: (123,)
        return result
    monkeypatch.setattr(api, "prepare", staging)
    assert backend.execute("10", False)["pending_updates"] == (123,)
    assert events.count("notify") == 2


def test_partial_failure_keeps_disclosure_and_next_noop_resets_it(monkeypatch, capsys):
    backend, layer, events, _ = setup(monkeypatch, queue=(99,))
    native = api._native("fontlab")
    def notify(*args):
        events.append("notify")
        layer.note = "callback mutation"
    native.flItems = lambda: NS(notifyChangesApplied=notify)
    disclosure = {}
    with pytest.raises(RuntimeError, match="1 completed"):
        backend.execute("10", False, disclosure=disclosure)
    assert disclosure["pending_updates"] == (99,) and "8537" in disclosure["pending_note"]
    assert backend.execute("0", False, disclosure=disclosure)["pending_note"] == ""
    assert disclosure == {"pending_updates": (), "pending_note": ""}
    backend, _, _, _ = setup(monkeypatch, queue=(99,))
    backend.execute("10", False)
    assert "8537" in capsys.readouterr().out, "CLI callers need the same caveat"


def test_early_failure_resets_disclosure_before_any_history(monkeypatch):
    backend, _, events, _ = setup(monkeypatch)
    disclosure = {"pending_updates": (99,), "pending_note": "old warning"}
    with pytest.raises(ValueError):
        backend.execute("invalid", False, disclosure=disclosure)
    assert disclosure == {"pending_updates": (), "pending_note": ""}
    assert not events


def test_cli_partial_failure_prints_queue_warning_before_undo_diagnosis(monkeypatch, capsys):
    backend, layer, events, _ = setup(monkeypatch, queue=(99,))
    native = api._native("fontlab")
    def notify(*args):
        events.append("notify")
        layer.note = "callback mutation"
    native.flItems = lambda: NS(notifyChangesApplied=notify)
    with pytest.raises(RuntimeError, match="1 completed"):
        backend.execute("10", False)
    assert capsys.readouterr().out.count("8537") == 1
    assert events.count("notify") == 1, "Do not continue after partial failure"
