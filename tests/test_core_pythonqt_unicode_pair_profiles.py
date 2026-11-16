# this_file: tests/test_core_pythonqt_unicode_pair_profiles.py
"""App-side coverage for the pure logic of the Apply Unicode Map and Pair Proof profiles."""

from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace as NS

import pytest
from legacy_panel_qt import font_host, legacy_qt  # noqa: F401

from fontlabapp.fontui.core_pythonqt_labs.profiles import apply_unicode_map as aum
from fontlabapp.fontui.core_pythonqt_labs.profiles import pair_proof_generator as ppg


def facts_for(**codes):
    entries = {
        n: NS(record=NS(unicodes=list(c)), glyph=NS(layers=["m1"])) for n, c in codes.items()
    }
    return NS(entries=entries, autos=(), package_id=7)


@pytest.fixture
def names_edit(monkeypatch):
    """Install a fake fly.ap.glyphs.names.model so no host is needed."""
    mod = ModuleType("fly.ap.glyphs.names.model")
    mod.refusals = {}
    mod.refusal = lambda facts, name, op: mod.refusals.get(name, "")
    mod.fresh = facts_for(A=[], B=[0x42])
    mod.fresh_facts = lambda package_id: mod.fresh
    mod.mismatch = False

    def commit(title, entries, mutate, **kw):
        mutate()
        bad = kw["read_back"]() if not mod.mismatch else ["A"]
        return NS(mismatches=bad, pending_note="n", pending_updates=(1,))

    mod.commit = commit
    for name in ("fly", "fly.ap", "fly.ap.glyphs", "fly.ap.glyphs.names"):
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name) or ModuleType(name))
    monkeypatch.setitem(sys.modules, "fly.ap.glyphs.names.model", mod)
    monkeypatch.setattr(sys.modules["fly.ap.glyphs.names"], "model", mod, raising=False)
    return mod


@pytest.mark.parametrize(
    ("text", "expect"),
    [
        ('{"A": 65, "B": ["U+0042", "0x43", 66]}', {"A": (65,), "B": (66, 67)}),
        ('{"A": "41"}', {"A": (0x41,)}),
    ],
)
def test_parse_map_when_valid_then_scalars(text, expect):
    assert aum.parse_map(text) == expect


@pytest.mark.parametrize(
    "text",
    [
        '{"A": 1, "A": 2}',
        "{}",
        "[1]",
        '{"": 1}',
        '{"A B": 1}',
        '{"A": []}',
        '{"A": 1.5}',
        '{"A": "zz"}',
        '{"A": 1114112}',
        '{"A": 55296}',
        '{"A": -1}',
        '{"\\ud800": 1}',
        "{\"A\": 1} ",
    ],
)
def test_parse_map_when_invalid_then_value_error(text):
    with pytest.raises(ValueError):
        aum.parse_map(text)


def test_snapshot_and_code_owners_when_detached_then_stable():
    facts = facts_for(A=[65], B=[66, 65])
    snap = aum.snapshot_facts(facts)
    facts.entries["A"].record.unicodes.append(1)
    assert snap.entries["A"].record.unicodes == (65,)
    assert snap.code_owners[65] == {"A", "B"}


def test_plan_map_when_mixed_then_notes(names_edit):
    facts = facts_for(A=[], B=[0x42], C=[0x43], D=[], F=[])
    names_edit.refusals["D"] = "refused"
    mapping = {"A": (0x41,), "B": (0x42,), "C": (0x42,), "D": (1,), "E": (2,), "F": (0x41,)}
    rows = {r["name"]: r for r in aum.plan_map(facts, ["A", "B", "C", "D", "F"], mapping)}
    assert rows["A"]["note"] == "Unicode claimed by another glyph or map row"
    assert rows["B"]["note"] == "Unicode claimed by another glyph or map row"
    assert rows["D"]["note"] == "refused"
    assert rows["E"]["note"] == "not selected"
    mapping = {"A": (0x41,), "B": (0x42,)}
    rows = {r["name"]: r for r in aum.plan_map(aum.snapshot_facts(facts), ["A", "B"], mapping)}
    assert rows["A"]["note"] == "" and rows["A"]["after"] == (0x41,)
    assert rows["B"]["note"] == "already present"


def test_write_map_when_fresh_then_commit_and_snapshot(names_edit):
    mapping = {"A": (0x41,)}
    preview = aum.plan_map(names_edit.fresh, ["A"], mapping)
    result = aum.write_map(7, ["A"], mapping, preview)
    assert result["changed"] == 1 and result["pending_updates"] == (1,)
    assert names_edit.fresh.entries["A"].record.unicodes == [0x41]


def test_write_map_when_stale_then_error_carries_fresh_facts(names_edit):
    with pytest.raises(aum.StalePreviewError) as caught:
        aum.write_map(7, ["A"], {"A": (0x41,)}, [])
    assert "A" in caught.value.facts.entries


def test_write_map_when_nothing_ready_then_zero(names_edit):
    mapping = {"B": (0x42,)}
    preview = aum.plan_map(names_edit.fresh, ["B"], mapping)
    assert aum.write_map(7, ["B"], mapping, preview)["changed"] == 0


def test_write_map_when_read_back_differs_then_runtime_error(names_edit):
    names_edit.mismatch = True
    mapping = {"A": (0x41,)}
    preview = aum.plan_map(names_edit.fresh, ["A"], mapping)
    with pytest.raises(RuntimeError, match="Undo"):
        aum.write_map(7, ["A"], mapping, preview)


@pytest.fixture
def catalog(monkeypatch):
    mod = ModuleType("fly.ap.glyphs.catalog.model")
    mod.capture = lambda: NS(rows=[("A",), ("V",), ("T",), ("o",), ("a b",)])
    for name in ("fly", "fly.ap", "fly.ap.glyphs", "fly.ap.glyphs.catalog"):
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name) or ModuleType(name))
    monkeypatch.setitem(sys.modules, "fly.ap.glyphs.catalog.model", mod)
    monkeypatch.setattr(sys.modules["fly.ap.glyphs.catalog"], "model", mod, raising=False)


def test_build_output_when_product_then_ordered_pairs(catalog):
    out = ppg.build_output(("A T", "V o", "", "", "Product", "A", "T"))
    assert out.splitlines()[0] == "/A/A/V/T"
    assert len(out.splitlines()) == 4


def test_build_output_when_zip_then_pairs_and_length_checked(catalog):
    assert ppg.build_output(("A T", "V o", "", "", "Zip", "", "")) == "/A/V\n/T/o"
    with pytest.raises(ValueError, match="equal"):
        ppg.build_output(("A T", "V", "", "", "Zip", "", ""))


@pytest.mark.parametrize(
    "fields",
    [
        ("", "V", "", "", "Product", "", ""),
        ("A", "V", "", "", "Other", "", ""),
        ("Q", "V", "", "", "Product", "", ""),
        ("a b", "V", "", "", "Product", "", ""),
    ],
)
def test_build_output_when_invalid_then_value_error(catalog, fields):
    with pytest.raises(ValueError):
        ppg.build_output(fields)


def test_checked_when_bad_text_then_refused():
    assert ppg.checked("ok") == "ok"
    for bad in ("a\0", "a\u00a0", "a\r", "\ud800"):
        with pytest.raises(ValueError):
            ppg.checked(bad)


def _panel(lq, monkeypatch, capture):
    from PySide6 import QtCore, QtWidgets

    qt = NS(QtCore=QtCore, QtGui=lq.gui)
    parent = QtWidgets.QWidget()
    lq.owned.append(parent)
    monkeypatch.setattr(ppg, "build_output", capture)
    panel = ppg.show(qt, parent, embedded=True)
    lq.owned.append(panel)
    return panel


def test_panel_when_refresh_copy_close_then_fresh_reads(legacy_qt, font_host, monkeypatch):  # noqa: F811
    calls = []
    panel = _panel(legacy_qt, monkeypatch, lambda fields: calls.append(fields) or "/A/V")
    assert panel.output_box.toPlainText() == "/A/V"
    panel.copy_output()
    assert panel.status_line.text() == "Fresh result copied."
    assert len(calls) == 2 and calls[0][4] == "Product"
    ppg._PANELS.clear()
    ppg._PANELS.append(panel)
    event = NS(accepted=None, ignore=lambda: setattr(event, "accepted", False), accept=lambda: setattr(event, "accepted", True))
    panel.closeEvent(event)
    assert event.accepted is True and panel not in ppg._PANELS


def test_panel_when_capture_refuses_then_output_cleared(legacy_qt, font_host, monkeypatch):  # noqa: F811
    def refuse(fields):
        raise ValueError("no font")

    panel = _panel(legacy_qt, monkeypatch, refuse)
    assert panel.status_line.text() == "no font" and panel.output_box.toPlainText() == ""
    panel.copy_output()
    assert panel.status_line.text() == "no font"
    panel._capture = lambda fields: ""
    panel.copy_output()
    assert panel.status_line.text() == "No matching output to copy."


def test_panel_when_scope_refuses_finish_then_close_ignored_and_release(legacy_qt, font_host, monkeypatch):  # noqa: F811
    panel = _panel(legacy_qt, monkeypatch, lambda fields: "x")
    real = panel.signal_scope.finish
    panel.signal_scope.finish = lambda **kw: False
    event = NS(ignored=False, ignore=lambda: setattr(event, "ignored", True), accept=lambda: None)
    panel.closeEvent(event)
    assert event.ignored
    panel.signal_scope.finish = real
    panel.release_owner()
    assert panel not in ppg._PANELS


def test_show_when_build_controls_fails_then_panel_released(legacy_qt, font_host, monkeypatch):  # noqa: F811
    from PySide6 import QtCore

    gui = legacy_qt.gui
    monkeypatch.setattr(gui, "QComboBox", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        ppg.show(NS(QtCore=QtCore, QtGui=gui), None, embedded=True)
    assert ppg._PANELS == []


def test_main_and_build_when_called_then_use_fly_qt(legacy_qt, font_host, monkeypatch, capsys):  # noqa: F811
    import fly
    from PySide6 import QtCore

    qt = NS(QtCore=QtCore, QtGui=legacy_qt.gui)
    monkeypatch.setitem(vars(fly), "qt", qt)
    monkeypatch.setitem(vars(fly), "fl", NS(MainWindow=lambda: None))
    monkeypatch.setattr(ppg, "show", lambda *a, **k: (_ for _ in ()).throw(ValueError("closed")))
    ppg.main()
    assert "closed" in capsys.readouterr().out
    monkeypatch.setattr(ppg, "show", lambda q, p, embedded=False: ("built", embedded))
    assert ppg.build(None) == ("built", True)
