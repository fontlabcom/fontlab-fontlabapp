# this_file: tests/test_fontui_hinting.py
"""``fontui.hinting``: the hint guard matches Fontport's outline guard; removal re-checks."""

import itertools
import sys
from types import SimpleNamespace

import pytest

from fontlabapp.fontui import hinting

FLAGS = list(itertools.product((False, True), repeat=3))


def layer(ps=False, tt=False, tth=False, hints=()):
    return SimpleNamespace(hasHints=ps, hasTTData=tt, hasTTH=tth, guidelines=list(hints))


def hint(horizontal=True):
    return SimpleNamespace(isHint=True, isHorizontal=lambda: horizontal, isVertical=lambda: not horizontal)


def fontport_refuses(target, monkeypatch) -> bool:
    """True when Fontport's own ``_stage_shapes`` guard refuses ``target`` as hinted."""
    from fontlab_fontport.errors import UnsupportedCapability
    from fontlab_fontport.host import NativeFontBackend

    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=SimpleNamespace()))
    target.shapes = []
    try:
        NativeFontBackend._stage_shapes(None, target, None, None, True)
    except UnsupportedCapability as error:
        return "hinted" in str(error)
    except Exception:  # noqa: BLE001 - an unhinted target fails later, not in the guard
        return False
    return False


@pytest.mark.parametrize("flags", FLAGS)
def test_layer_is_hinted_when_flags_vary_then_matches_fontport_guard(flags, monkeypatch):
    target = layer(*flags)
    state = hinting.layer_is_hinted(target)
    assert tuple(state) == flags
    assert bool(state) == fontport_refuses(target, monkeypatch), f"parity broken for {flags}"


def test_layer_is_hinted_when_none_then_not_hinted():
    assert not hinting.layer_is_hinted(None)
    assert hinting.layer_is_hinted(None).text() == ""


def test_hint_state_text_when_ps_or_tt_then_names_the_protection():
    assert hinting.HintState(True, True).text() == hinting.PS_TEXT
    assert hinting.HintState(False, False, True).text() == hinting.TT_TEXT
    assert "Advance width and kerning still work." in hinting.PS_TEXT


def test_recheck_text_when_states_vary_then_reports_what_remains():
    assert hinting.recheck_text(hinting.HintState()) == hinting.REMOVED_TEXT
    assert hinting.recheck_text(hinting.HintState(False, True)) == hinting.TT_REMAINS_TEXT
    assert hinting.recheck_text(hinting.HintState(True)) == hinting.PS_TEXT


def test_remove_hints_when_ps_hinted_then_one_named_step_and_recheck():
    target = layer(ps=True, tt=True, hints=[hint(True), hint(False)])
    calls = []

    def remove(horizontal, vertical):
        calls.append(("removeHints", horizontal, vertical))
        target.guidelines.clear()
        target.hasHints = False

    target.removeHints = remove
    glyph = SimpleNamespace(name="A")

    def commit(label, layers, glyphs, mutate, read_back):
        calls.append((label, layers, glyphs))
        mutate()
        assert read_back() == []

    state = hinting.remove_hints_with_recheck(
        target, "Kerning Studio: remove hints A/Regular", glyph=glyph, commit=commit
    )
    assert calls == [
        ("Kerning Studio: remove hints A/Regular", [target], [glyph]),
        ("removeHints", True, True),
    ]
    assert state == hinting.HintState(False, True, False)
    assert hinting.recheck_text(state) == hinting.TT_REMAINS_TEXT


def test_remove_hints_when_hints_remain_then_read_back_reports_them():
    target = layer(ps=True, hints=[hint(True)])
    target.removeHints = lambda h, v: None
    found = []
    hinting.remove_hints_with_recheck(
        target, "X", glyph=SimpleNamespace(name="A"),
        commit=lambda label, layers, glyphs, mutate, read_back: (mutate(), found.extend(read_back())),
    )  # fmt: skip
    assert found == ["A: 1 horizontal and 0 vertical hints remain"]


def test_remove_hints_when_no_ps_hints_then_no_history_call():
    target = layer(tt=True)
    state = hinting.remove_hints_with_recheck(
        target, "X", glyph=SimpleNamespace(name="A"), commit=lambda *a: pytest.fail("history called")
    )
    assert state.tt and not state.ps_hints


def test_remove_hints_when_default_commit_then_uses_core_history(monkeypatch):
    import fontlabapp.core.history.glyphs as history

    target = layer(ps=True, hints=[hint()])

    def remove(h, v):
        target.hasHints = False
        target.guidelines.clear()

    target.removeHints = remove
    seen = {}
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: ("facts", package))

    def commit(title, layers, glyphs, mutate, **kwargs):
        seen.update(title=title, kwargs=kwargs)
        mutate()

    monkeypatch.setattr(history, "commit", commit)
    hinting.remove_hints_with_recheck(target, "T", glyph=SimpleNamespace(name="A"), package="pkg")
    assert seen["title"] == "T"
    assert seen["kwargs"]["operation"] == "geometry"
    assert seen["kwargs"]["facts"] == ("facts", "pkg")


class Native(SimpleNamespace):
    """A fake live object with ``isNull``."""

    isNull = False


def package(layers, master="Regular"):
    """A fake flPackage: glyph ``A`` with the given ``{layer: flLayer}`` (live layers get ``isNull``)."""
    for target in layers.values():
        if not hasattr(target, "isNull"):
            target.isNull = False
    glyph = Native(findLayer=lambda name: layers.get(name))
    return Native(defaultMaster=master, findName=lambda name: glyph if name == "A" else None)


def test_native_layer_when_present_or_absent_then_layer_or_none():
    bold = layer(ps=True)
    pkg = package({"Regular": layer(), "Bold": bold, "Null": Native(isNull=True)})
    assert hinting.native_layer(pkg, "A", "Bold") is bold
    assert hinting.native_layer(pkg, "A") is pkg.findName("A").findLayer("Regular")
    assert hinting.native_layer(pkg, "A", "Null") is None
    assert hinting.native_layer(pkg, "A", "Light") is None
    assert hinting.native_layer(pkg, "Z") is None
    assert hinting.native_layer(None, "A") is None
    null_glyph = Native(defaultMaster="Regular", findName=lambda name: Native(isNull=True))
    assert hinting.native_layer(null_glyph, "A") is None


def test_hint_state_of_when_layer_hinted_then_state_else_none():
    pkg = package({"Regular": layer(), "Bold": layer(tt=True)})
    assert hinting.hint_state_of(pkg, "A", "Bold") == hinting.HintState(False, True, False)
    assert not hinting.hint_state_of(pkg, "A")
    assert hinting.hint_state_of(pkg, "A", "Light") is None


def test_package_of_when_backend_id_then_workspace_lookup(monkeypatch):
    pkg, found = package({}), []
    workspace = SimpleNamespace(findPackageId=lambda i: found.append(i) or (pkg if i == 7 else Native(isNull=True)))
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(flWorkspace=SimpleNamespace(instance=lambda: workspace)))
    assert hinting.package_of(SimpleNamespace(_backend=SimpleNamespace(font_id=7))) is pkg
    assert hinting.package_of(SimpleNamespace(_backend=SimpleNamespace(font_id=8))) is None
    assert hinting.package_of(SimpleNamespace()) is None
    assert found == [7, 8]
    monkeypatch.setitem(sys.modules, "fontlab", None)
    assert hinting.package_of(SimpleNamespace(_backend=SimpleNamespace(font_id=7))) is None


def test_font_hint_check_when_called_then_resolves_package_each_time(monkeypatch):
    calls, pkg = [], package({"Regular": layer(ps=True)})
    monkeypatch.setattr(hinting, "package_of", lambda font: calls.append(font) or pkg)
    check = hinting.font_hint_check("font")
    assert check("A", None).ps_hints and check("A", "Regular").ps_hints
    assert calls == ["font", "font"]
