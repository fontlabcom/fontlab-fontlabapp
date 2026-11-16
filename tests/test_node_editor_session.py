# this_file: tests/test_node_editor_session.py
"""Accepted Node Editor plans cannot silently retarget or bypass preview."""
from types import SimpleNamespace as NS

import pytest

from fontlabapp.fontui.node_editor import session


def test_native_preview_requires_acceptance_and_passes_exact_capture(monkeypatch):
    package = NS(id=7, master="Regular")
    monkeypatch.setattr(session.scripting, "current_package", lambda *a: package)
    capture = NS(context=(7, "Regular"), source="source")
    monkeypatch.setattr(session.native, "capture", lambda *a: capture)
    monkeypatch.setattr(session.native, "plan", lambda *a: NS(inserted=2))
    seen = []
    monkeypatch.setattr(session.native, "execute", lambda *a, **k: seen.append(k) or {"inserted": 2})
    work = session.NativePlan(package, "current")
    with pytest.raises(ValueError, match="Preview"):
        work.apply()
    assert work.preview().inserted == 2
    assert work.apply() == {"inserted": 2}
    assert seen[0]["expected"] is capture and not work.dirty


def test_native_preview_switch_and_stale_target_refuse(monkeypatch):
    package = NS(id=7, master="Regular")
    monkeypatch.setattr(session.scripting, "current_package", lambda *a: package)
    work = session.NativePlan(package, "all")
    monkeypatch.setattr(session.native, "capture", lambda *a: NS(context=(8, "Regular")))
    with pytest.raises(ValueError, match="font"):
        work.preview()
    package.master = "Bold"
    with pytest.raises(ValueError, match="layer"):
        work.preview()
    monkeypatch.setattr(session.scripting, "current_package", lambda *a: None)
    with pytest.raises(ValueError, match="font"):
        work.preview()


def test_per_glyph_preview_retains_plan_and_refuses_changed_geometry(monkeypatch):
    package = NS(id=7, master="Regular")
    layer = NS(name="Regular", isNull=False)
    glyph = NS(name="a", layers=[layer], findLayer=lambda name: layer)
    panel = NS(live_glyphs=lambda: (package, [glyph]), chosen_masters=lambda: ["Regular"],
               options=lambda: {"allow_bases": False}, planner=lambda: "planner",
               _selection_snapshot="selection", _selected_occurrences=(), fill=lambda p: None,
               editor=lambda: "editor", refresh=lambda: None)
    row = NS(name="c", old="1", new="2", problem="", key=1)
    plan = NS(work=[(glyph, layer, [])], problems=[], rows=[("a", row)], refused=[], skipped=[])
    monkeypatch.setattr(session.scripting, "current_package", lambda *a: package)
    monkeypatch.setattr(session.history, "scan_auto_facts", lambda p: "facts")
    monkeypatch.setattr(session.writer, "collect", lambda *a, **k: plan)
    monkeypatch.setattr(session.native, "read_layer", lambda *a: ("geometry", "flags", {}))
    monkeypatch.setattr(session.writer, "apply_work", lambda *a, **k: {"edits": 1})
    work = session.PerGlyphPlan(package, panel)
    with pytest.raises(ValueError, match="Preview"):
        work.apply()
    assert work.preview() is plan
    row.old = "3"
    with pytest.raises(ValueError, match="preview changed"):
        work.apply()
    assert not work.dirty
    work.preview()
    assert work.apply() == {"edits": 1, "skipped": 0}
    plan.problems = ["locked"]
    with pytest.raises(ValueError, match="locked"):
        work.preview()
    plan.problems, plan.work = [], []
    with pytest.raises(ValueError, match="Nothing"):
        work.preview()


def test_native_boundary_rejects_changed_accepted_capture_before_history():
    from dataclasses import replace
    from time import monotonic
    from test_node_duplicator_native import host

    owned, native, qt, notifications, contour, provider, selected = host()
    before = session.native.capture("current", monotonic() + 3, native, provider)
    stale = replace(before, context=(999, "Regular", "font", 1))
    with pytest.raises(ValueError, match="preview changed"):
        session.native.execute("current", native=native, qt=qt, provider=provider, expected=stale)
    assert not notifications and len(contour.nodes()) == 1
    result = session.native.execute("current", native=native, qt=qt, provider=provider, expected=before)
    assert result["inserted"] == 1 and len(notifications) == 1


def test_per_glyph_snapshot_excludes_unrelated_auxiliary_but_rechecks_reference(monkeypatch):
    package = NS(id=7, master="Regular")
    target, reference, unrelated = [NS(name=name, isNull=False) for name in ("Regular", "Reference", "Generated")]
    glyph = NS(name="a", layers=[target, reference, unrelated], findLayer=lambda name: target if name == "Regular" else None)
    panel = NS(live_glyphs=lambda: (package, [glyph]), chosen_masters=lambda: ["Regular", "missing"],
               options=lambda: {"allow_bases": False, "compatible": True, "all_masters": ["Regular"]},
               planner=lambda: "planner", _selection_snapshot="selection",
               _selected_occurrences=(NS(glyph=glyph, layer=reference), NS(glyph=NS(name="untouched"), layer=unrelated)),
               fill=lambda p: None)
    plan = NS(work=[(glyph, target, [])], problems=[], rows=[])
    monkeypatch.setattr(session.scripting, "current_package", lambda *a: package)
    monkeypatch.setattr(session.history, "scan_auto_facts", lambda p: "facts")
    monkeypatch.setattr(session.writer, "collect", lambda *a, **k: plan)
    state, reads = [0], []
    def read(layer, glyph, deadline):
        assert layer is not unrelated, "Unsupported unrelated auxiliary must not block a master edit"
        reads.append(layer)
        return layer.name, state[0] if layer is reference else 0, {}
    monkeypatch.setattr(session.native, "read_layer", read)
    work = session.PerGlyphPlan(package, panel)
    work.preview()
    assert reads == [target, reference]
    state[0] = 1
    with pytest.raises(ValueError, match="preview changed"):
        work.apply()


def test_studio_entrypoints_use_public_fontui_services(monkeypatch):
    import fontlabapp.fontui as fontui
    from fontlabapp.studios import node_editor

    calls = []
    monkeypatch.setattr(fontui, "show_node_editor", lambda **kwargs: calls.append(kwargs) or "window")
    monkeypatch.setattr(fontui, "duplicate_nodes", lambda mode: calls.append(mode) or "result")
    assert node_editor.show(parent="parent") == "window"
    assert node_editor.duplicate_selected_nodes("handles") == "result"
    assert calls == [{"parent": "parent"}, "handles"]
