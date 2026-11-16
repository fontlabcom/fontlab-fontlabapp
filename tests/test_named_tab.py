# this_file: tests/test_named_tab.py
"""Own native-symbol construction and fresh-tab writer fences; no FontLab runs."""

from types import SimpleNamespace as NS

import pytest
import test_text_tab

import fontlabapp.proof.tabs.named as api

host = test_text_tab.host


class Symbols:
    def __init__(self, value):
        self.values = list(value)

    def append(self, other):
        self.values.extend(other.values)


@pytest.fixture
def named(host, monkeypatch):
    host.old_block.id = 11
    host.package.master = "Regular"
    host.native.fgSymbol = lambda name: NS(name=name)
    host.native.fgSymbolList = Symbols
    host.state.mode = "new"
    host.state.populations = []
    host.state.populate_error = False
    original = host.gui.QLineEdit

    class Sender:
        def __init__(self):
            self.inner = original()

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def setText(self, text):
            self.inner.setText(text)
            if self.inner.connected:
                if host.state.mode == "new":
                    host.state.block = NS(id=99, package=host.package)
                if host.state.mode == "wrong_font":
                    host.state.block = NS(id=99, package=NS(id=8))
                if host.state.mode == "none":
                    host.state.block = None
                if host.state.mode == "canvas":  # native: a fresh tab is only the canvas's block
                    host.state.block = None
                    host.state.canvas = NS(
                        textBlocks=lambda: [NS(id=99, package=host.package)]
                    )

    host.gui.QLineEdit = Sender

    def populate(symbols, cursor):
        host.state.populations.append((symbols, cursor))
        if host.state.populate_error:
            raise RuntimeError("owned populate failure")

    host.native.flItems = lambda: NS(requestContent=populate)
    monkeypatch.setattr(api, "_native", lambda name: host.native)
    monkeypatch.setattr(api, "monotonic", lambda: host.state.seconds)
    return host


def test_named_tab_when_fresh_tab_is_only_canvas_block_then_populates(named):
    named.state.mode = "canvas"
    api.open_named_tab((("A",),), expected_id=7, master="Regular")
    assert len(named.state.populations) == 1, "FontLab gives a fresh tab no active block"


def test_named_symbols_preserve_unencoded_repeats_and_final_blank_rows(named):
    api.open_named_tab(
        (("A.alt", "zero.osf", "A.alt"), (), ()), expected_id=7, master="Regular"
    )
    values = named.state.populations[0][0].values
    assert [v if isinstance(v, str) else v.name for v in values] == [
        "A.alt",
        "zero.osf",
        "A.alt",
        "\n",
        "\n",
    ]
    assert all(v.layerName == "Regular" for v in values if not isinstance(v, str))
    assert named.state.populations[0][1] == 0 and named.state.tabs == [""]
    assert named.shape.active is False and named.old_shape.active is True
    assert named.state.calls[-2:] == ["disconnect", "delete"]


@pytest.mark.parametrize("lines", [(), ((),), ((), (), ())])
def test_empty_rows_and_domain_preserve_every_line_break(named, lines):
    api.open_named_tab(lines, expected_id=7, master="Regular")
    assert named.state.populations[0][0].values == ["\n"] * max(0, len(lines) - 1)


@pytest.mark.parametrize("mode", ["unchanged", "none", "wrong_font"])
def test_failed_creation_fence_never_writes_any_existing_or_foreign_tab(named, mode):
    named.state.mode = mode
    with pytest.raises(ValueError, match="tab"):
        api.open_named_tab((("A",),), expected_id=7, master="Regular")
    assert not named.state.populations
    assert named.shape.active is False and named.old_shape.active is True
    assert named.state.calls[-2:] == ["disconnect", "delete"]


@pytest.mark.parametrize("lines", [("A",), (("",),), ((None,),)])
def test_invalid_symbol_rows_fail_before_any_tab_opens(named, lines):
    with pytest.raises((TypeError, ValueError)):
        api.open_named_tab(lines, expected_id=7, master="Regular")
    assert not named.state.calls and not named.state.populations


def test_late_native_population_failure_restores_flags_and_cleans_sender(named):
    named.state.populate_error = True
    with pytest.raises(RuntimeError, match="owned populate"):
        api.open_named_tab((("A",),), expected_id=7, master="Regular")
    assert named.state.tabs == [""] and len(named.state.populations) == 1
    assert named.shape.active is False and named.old_shape.active is True
    assert named.state.calls[-2:] == ["disconnect", "delete"]


def test_symbol_build_failure_and_deadline_never_open_a_tab(named):
    named.native.fgSymbol = lambda name: (_ for _ in ()).throw(
        RuntimeError("owned symbol failure")
    )
    with pytest.raises(RuntimeError, match="owned symbol"):
        api.open_named_tab((("A",),), expected_id=7, master="Regular")
    assert not named.state.calls
    with pytest.raises(TimeoutError):
        api.open_named_tab((("A",),), expected_id=7, master="Regular", deadline=-1.0)
    assert not named.state.calls


@pytest.mark.parametrize("phase", ["created", "populated"])
def test_post_creation_deadline_reports_that_a_new_tab_may_remain(
    named, monkeypatch, phase
):
    ticks = iter((0.0, 3.0) if phase == "populated" else (3.0,))
    # Keep all preflight checkpoints at zero; only the population phase clock expires.
    monkeypatch.setattr(api, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError, match="new tab may remain"):
        api.open_named_tab((("A",),), expected_id=7, master="Regular", deadline=2.0)
    assert len(named.state.populations) == (phase == "populated")


def test_source_master_change_and_invalid_master_refuse_before_tab_creation(named):
    named.package.master = "Bold"
    with pytest.raises(ValueError, match="source master changed"):
        api.open_named_tab((("A",),), expected_id=7, master="Regular")
    assert named.state.calls == [] and named.state.populations == []
    with pytest.raises(TypeError, match="master name"):
        api.open_named_tab((("A",),), expected_id=7, master=None)
    assert named.state.calls == []
