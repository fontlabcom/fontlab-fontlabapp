# this_file: tests/test_show_all_layers_native.py
"""Exact layer-aware tab payload, mixed masters/repeats and whole-call refusals."""

from types import SimpleNamespace as NS

import fontlabapp.masters.layers.show_all.native as api
import pytest
from fontlabapp.masters.layers.show_all.model import run


class Symbols:
    def __init__(self, values):
        self.rows = (
            []
            if values == ""
            else ["\n"]
            if values == "\n"
            else [(s.name, s.layerName) for s in values]
        )

    def append(self, other):
        self.rows.extend(other.rows)


@pytest.fixture
def owned(monkeypatch):
    glyph = NS(id=10, name="A/😀", package=NS(id=7), isNull=False, layers=[])
    for i, name in enumerate(["Bold", "Mask", "Alt", "Regular", "Service"]):
        glyph.layers.append(
            NS(
                id=i + 20,
                name=name,
                isNull=False,
                isValid=True,
                glyph=glyph,
                isMasterLayer=name in ("Bold", "Regular"),
                isMaskLayer=name == "Mask",
                isService=name == "Service",
            )
        )
    glyph.findLayer = lambda name: next(l for l in glyph.layers if l.name == name)
    occurrence = NS(
        glyph=glyph,
        layer=glyph.layers[0],
        glyph_id=10,
        layer_id=20,
        glyph_name=glyph.name,
        layer_name="Bold",
    )
    selected = NS(
        context=(7, "Regular", "editor", 88), occurrences=(occurrence, occurrence)
    )
    monkeypatch.setattr(api.selection, "capture", lambda deadline: selected)
    monkeypatch.setattr(
        api.selection, "document_context", lambda deadline: selected.context
    )
    native = NS(fgSymbolList=Symbols, fgSymbol=lambda name: NS(name=name, layerName=""))
    monkeypatch.setattr(api, "_native", lambda name: native)
    events = []
    monkeypatch.setattr(
        api.tabs,
        "_open_symbols",
        lambda native, symbols, package, master, deadline: events.append(
            (symbols.rows, package, master)
        ),
    )
    return glyph, selected, events


def test_actual_full_original_proof_preserves_order_mixed_layers_repeats_newlines(
    owned,
):
    glyph, _selected, events = owned
    assert run() == {"groups": 2, "layers": 6}
    assert events == [
        (
            [(glyph.name, "Bold"), (glyph.name, "Alt"), (glyph.name, "Regular"), "\n"]
            * 2,
            7,
            "Regular",
        )
    ]


def test_empty_selection_opens_no_tab_and_empty_parent_still_emits_newline(owned):
    glyph, selected, events = owned
    selected.occurrences = ()
    assert api.run() == {"groups": 0, "layers": 0} and not events
    selected.occurrences = (
        NS(
            glyph=glyph,
            layer=NS(id=77, name="chosen", isNull=False),
            glyph_id=10,
            layer_id=77,
            glyph_name=glyph.name,
            layer_name="chosen",
        ),
    )
    glyph.layers = []
    assert api.run() == {"groups": 1, "layers": 0}
    assert events[0][0] == ["\n"]


@pytest.mark.parametrize(
    "change",
    [
        lambda g, s: setattr(g, "isNull", True),
        lambda g, s: setattr(g.layers[0], "isValid", False),
        lambda g, s: setattr(g.layers[0], "isService", 1),
        lambda g, s: g.layers.append(g.layers[0]),
        lambda g, s: setattr(g.layers[2], "name", "Bold"),
        lambda g, s: setattr(g.layers[0], "name", ""),
    ],
)
def test_invalid_stale_or_unaddressable_sources_refuse_before_tab(owned, change):
    glyph, selected, events = owned
    change(glyph, selected)
    with pytest.raises(ValueError):
        api.run()
    assert events == []


def test_capture_and_final_source_drift_refuse_without_tab(owned, monkeypatch):
    _glyph, _selected, events = owned
    real = api.capture
    count = 0

    def capture(deadline):
        nonlocal count
        count += 1
        result = real(deadline)
        return (
            api.Snapshot((8, "Other"), result.groups, result.states)
            if count == 2
            else result
        )

    monkeypatch.setattr(api, "capture", capture)
    with pytest.raises(ValueError, match="source changed"):
        api.run()
    assert not events


def test_absolute_deadline_and_context_drift_refuse(owned, monkeypatch):
    with pytest.raises(TimeoutError):
        api.capture(0)
    monkeypatch.setattr(
        api.selection, "document_context", lambda deadline: ("changed",)
    )
    with pytest.raises(ValueError, match="changed"):
        api.run()


def test_symbol_allocation_failure_never_opens_tab(owned, monkeypatch):
    monkeypatch.setattr(
        api,
        "_native",
        lambda name: NS(
            fgSymbolList=Symbols,
            fgSymbol=lambda name: (_ for _ in ()).throw(RuntimeError("symbol")),
        ),
    )
    with pytest.raises(RuntimeError, match="symbol"):
        api.run()
    assert not owned[2]
