# this_file: tests/test_twindow_host.py
"""Exact native text targeting and owned subscriptions using host doubles."""

import sys
from types import SimpleNamespace as NS

import pytest
from fontlabapp.fontui.twindow_host import FontLabHost


class Symbols:
    def __init__(self, items):
        self.items = items

    def symbols(self):
        return self.items


class Block:
    id = 2
    # Live FontLab: flPackage.id is address-like; Fontport font_id is fgId.
    package = NS(id=523586929536, fgId=7)

    def __init__(self, text="AV"):
        self.value = Symbols([NS(name="", layerName="", unicode=ord(c)) for c in text])

    def symbolList(self):
        return self.value

    def getAllGlyphs(self):
        return []


def bridge():
    block = Block()
    workspace = NS(activeFontPanel=None, getActiveTextBlock=lambda: block)
    writes, updates = [], []

    def write(symbols, index):
        writes.append((symbols, index))
        block.value = symbols

    native = NS(
        flTextBlock=Block,
        flWorkspace=NS(instance=lambda: workspace),
        fgSymbol=lambda code: NS(name="", layerName="", unicode=code),
        fgSymbolList=Symbols,
        flItems=lambda: NS(requestContent=write),
        UpdateActiveCanvas=lambda: updates.append(True),
    )
    host = FontLabHost(NS(_backend=NS(font_id=7)), native)
    return host, block, workspace, writes, updates


def test_literal_text_when_host_and_window_edit_then_roundtrip():
    host, block, _, writes, updates = bridge()
    assert host.read_text() == "AV"
    block.value.items.append(NS(name="", layerName="", unicode=32))
    assert host.read_text() == "AV "
    assert host.write_text("😀\nA ")
    assert host.read_text() == "😀\nA "
    assert len(writes) == len(updates) == 1
    assert host.write_text("")
    assert host.read_text() == ""


@pytest.mark.parametrize("field,value", [("name", "A"), ("layerName", "Bold")])
def test_named_or_layered_text_when_unrepresentable_then_no_write(field, value):
    host, block, _, writes, _ = bridge()
    setattr(block.value.items[0], field, value)
    assert host.read_text() is None
    assert host.write_text("A") is False
    assert not writes


@pytest.mark.parametrize("value", [-1, 0x110000, 0xD800, 0xDFFF])
def test_bad_native_scalar_when_read_then_error(value):
    host, block, *_ = bridge()
    block.value.items[0].unicode = value
    with pytest.raises(ValueError, match="scalar"):
        host.read_text()


def test_bad_outbound_text_when_invalid_then_no_write():
    host, _, _, writes, _ = bridge()
    with pytest.raises(TypeError, match="string"):
        host.write_text(None)
    with pytest.raises(ValueError, match="surrogate"):
        host.write_text("\ud800")
    assert host.write_text("/A") is False
    assert not writes


@pytest.mark.parametrize("case", ["font", "panel", "block", "another", "backend"])
def test_changed_target_when_read_then_no_text_or_write(case):
    host, block, workspace, writes, _ = bridge()
    assert host.read_text() == "AV"
    if case == "font":
        block.package = NS(id=7, fgId=8)
    elif case == "panel":
        workspace.activeFontPanel = object()
    elif case == "block":
        workspace.getActiveTextBlock = lambda: None
        workspace.getActiveCanvas = lambda: None
    elif case == "another":
        block.id = 3
    else:
        host.font = object()
    assert host.read_text() is None
    assert host.write_text("A") is False
    assert not writes


def test_missing_native_when_read_then_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "fontlab", None)
    assert FontLabHost(object()).read_text() is None


def test_lazy_native_when_available_then_import_and_read(monkeypatch):
    host, *_ = bridge()
    monkeypatch.setitem(sys.modules, "fontlab", host.native)
    host.native = None
    assert host.read_text() == "AV"


def test_native_write_when_noop_then_readback_error():
    host, *_ = bridge()
    host.native.flItems = lambda: NS(requestContent=lambda *args: None)
    with pytest.raises(RuntimeError, match="did not retain"):
        host.write_text("B")


def test_target_disappears_during_write_preflight_then_no_write(monkeypatch):
    host, _, _, writes, _ = bridge()
    monkeypatch.setattr(host, "read_text", lambda: "AV")
    monkeypatch.setattr(host, "_block", lambda: None)
    assert host.write_text("B") is False
    assert not writes


def test_subscribe_when_text_changes_then_callback_and_closed_timer_stops(monkeypatch):
    import _cov_qt as qt

    qt.install(monkeypatch)
    from fontlabapp.fontui import lifecycle

    hooked, callbacks, diagnostics, timers = [], [], [], []
    monkeypatch.setattr(lifecycle, "follow_changes", lambda *args: hooked.append("changes"))
    monkeypatch.setattr(lifecycle, "follow_history", lambda *args: hooked.append("history"))

    class Timer:
        def __init__(self, parent):
            self.timeout = object()
            self.running = False
            timers.append(self)

        def setInterval(self, interval):
            assert interval == 250

        def start(self):
            self.running = True

        def stop(self):
            self.running = False

    monkeypatch.setattr(sys.modules["PythonQt"].QtCore, "QTimer", Timer)
    owner = NS(
        widget=object(), closed=False,
        connect=lambda signal, callback: callbacks.append(callback),
        diagnostic=NS(setText=diagnostics.append),
    )
    host, block, *_ = bridge()
    calls = []
    host.subscribe(owner, lambda: calls.append(host.read_text()), lambda: [host.font])
    assert hooked == ["changes", "history"]
    callbacks[0]()
    callbacks[0]()
    assert calls == ["AV"]
    block.value.items = []
    callbacks[0]()
    assert calls == ["AV", ""]
    block.value.items = [NS(name="", layerName="", unicode=-1)]
    callbacks[0]()
    assert "invalid Unicode" in diagnostics[-1]
    owner.closed = True
    callbacks[0]()
    assert not timers[0].running


def test_target_changes_while_symbols_stage_then_no_write():
    host, _block, workspace, writes, _ = bridge()

    def symbol(code):
        workspace.activeFontPanel = object()
        return NS(name="", layerName="", unicode=code)

    host.native.fgSymbol = symbol
    assert host.write_text("B") is False
    assert not writes
