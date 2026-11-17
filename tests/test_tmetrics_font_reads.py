# this_file: tests/test_tmetrics_font_reads.py
"""TMetrics reuses whole-font reads while typing and re-reads them on refresh/follow.

Runs on the unshaped fallback: the shared ``tm_mod`` fixture module skips
without ``uharfbuzz``, so this file loads TMetrics over the same Qt fakes itself.
"""

import importlib.util
import sys
from collections import Counter
from types import SimpleNamespace as NS

import _cov_qt as fq
import pytest
from _tmetrics_fakes import TwoLayerFont
from test_twindow_host import bridge

from fontlabapp.fontui._font_reads import FontReads

# HarfBuzz shapes from the snapshot of the last read; the unshaped fallback
# (fontport glyphrun) looks kerning and glyphs up on the font each time.
_HAS_HARFBUZZ = importlib.util.find_spec("uharfbuzz") is not None


class Counted(dict):
    """Kerning/groups mapping that counts whole-mapping reads."""

    def __init__(self, data, counts, key):
        super().__init__(data)
        self._counts, self._key = counts, key

    def items(self):
        self._counts[self._key] = self._counts.get(self._key, 0) + 1
        return super().items()


class CountingFont(TwoLayerFont):
    """``TwoLayerFont`` that counts keys(), kerning, groups, getLayer and summaries."""

    def __init__(self, summaries=True):
        self.counts = {}
        super().__init__()
        self.layerOrder = ["public.default", "Bold"]
        if summaries:
            self.glyph_summaries = self._summaries

    def _bump(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1

    @property
    def kerning(self):
        return self._kerning

    @kerning.setter
    def kerning(self, value):
        self._kerning = Counted(value, self.counts, "kerning")

    @property
    def groups(self):
        return self._groups

    @groups.setter
    def groups(self, value):
        self._groups = Counted(value, self.counts, "groups")

    def keys(self):
        self._bump("keys")
        return super().keys()

    def __contains__(self, name):
        self._bump(f"in:{name}")
        return super().__contains__(name)

    def getLayer(self, name):  # noqa: N802 - FontParts method name
        self._bump(f"layer:{name}")
        return super().getLayer(name)

    def _summaries(self):
        self._bump("glyph_summaries")
        return [(g.name, tuple(g.unicodes), g.width) for g in self.ufo]


def test_reads_when_repeated_then_font_asked_once_until_reset():
    font = CountingFont()
    reads = FontReads(font)
    assert reads.keys() == reads.keys() == ("A", "V")
    assert "A" in reads and "Q" not in reads
    assert len(reads) == 2
    assert reads.kerning == reads.kerning == {("public.kern1.A", "public.kern2.V"): -80}
    assert reads.groups["public.kern1.A"] == ("A",)
    reads.groups
    assert reads.getLayer("Bold") is reads.getLayer("Bold")
    assert reads.features.text == "" and reads.info.unitsPerEm == 1000
    assert reads.defaultLayerName == "public.default"
    assert font.counts == {"keys": 1, "kerning": 1, "groups": 1, "layer:Bold": 1}

    font.kerning[("A", "V")] = -10
    font.ufo.newGlyph("Q")
    assert ("A", "V") not in reads.kerning, "Memo holds until reset"
    reads.reset()
    assert ("A", "V") in reads.kerning and "Q" in reads and reads.keys()[-1] == "Q"
    reads.getLayer("Bold")
    assert font.counts == {"keys": 2, "kerning": 2, "groups": 1, "layer:Bold": 2}



def test_reset_when_font_has_refresh_then_cached_handles_dropped():
    """A live Fontport font snapshots glyph handles; reset() must refresh it."""

    class Snapshotting:
        def __init__(self):
            self.width, self.refreshed, self.handle = 500, 0, None

        def __getitem__(self, name):
            if self.handle is None:
                self.handle = NS(name=name, width=self.width)
            return self.handle

        def refresh(self):
            self.refreshed += 1
            self.handle = None

    font = Snapshotting()
    reads = FontReads(font)
    assert reads["A"].width == 500
    font.width = 510  # an edit made in FontLab, invisible to the old handle
    assert reads["A"].width == 500, "Memo holds until reset"
    reads.reset()
    assert font.refreshed == 1 and reads["A"].width == 510
    FontReads(NS(refresh=None)).reset()  # a font without a callable refresh is fine

def test_reads_when_glyph_requested_then_live_glyph_object_kept():
    font = CountingFont()
    reads = FontReads(font)
    assert reads["A"] is font["A"]
    font["A"].width = 640
    assert reads["A"].width == 640, "The kept glyph object is the live glyph"
    assert reads.edit_glyph == font.edit_glyph, "Other attributes pass through"


def test_reads_when_glyph_asked_twice_then_font_asked_once_until_reset():
    font = OldFont(5)
    reads = FontReads(font)
    assert reads["A"] is reads["A"]
    assert [g.name for g in reads] == list(font.ufo.keys())
    assert font.scans == {"getitem": 5, "keys": 1}, font.scans
    with pytest.raises(KeyError):
        reads["Q"]
    font.ufo.newGlyph("Q")
    assert reads["Q"].name == "Q", "A missing name is asked again"
    reads.reset()
    font.scans.clear()
    reads["A"]
    assert font.scans == {"getitem": 1}


def test_reads_when_snapshot_returned_then_font_not_mutated_through_it():
    font = CountingFont()
    reads = FontReads(font)
    reads.kerning[("A", "V")] = 5
    assert ("A", "V") not in font.kerning


def test_glyph_summaries_when_font_has_them_then_memoized():
    font = CountingFont()
    reads = FontReads(font)
    assert reads.glyph_summaries() == reads.glyph_summaries()
    assert reads.glyph_summaries() == (("A", (65,), 600), ("V", (86,), 600))
    assert font.counts == {"glyph_summaries": 1}
    reads.reset()
    reads.glyph_summaries()
    assert font.counts == {"glyph_summaries": 2}


def test_glyph_summaries_when_font_lacks_them_then_absent():
    reads = FontReads(CountingFont(summaries=False))
    assert not callable(getattr(reads, "glyph_summaries", None))
    with pytest.raises(AttributeError):
        reads._memo_missing  # noqa: B018 - private names never pass through


OWN_MODULES = (
    "fontlabapp.fontui.tmetrics",
    "fontlabapp.fontui.tmetrics_model",
    "fontlabapp.fontui.livesync",
    "fontlabapp.fontui.tglyph",
    "fontlabapp.fontui.tglyph_model",
    "fontlabapp.fontui.tglyph_edit",
)


class _Bar:
    value = 0

    def setValue(self, value):
        self.value = value


@pytest.fixture
def tm_mod(monkeypatch):
    handle = fq.install(monkeypatch)
    for name in OWN_MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
        fq._forget_on_parent(name, monkeypatch)
    handle.qt.QtGui.QPainter = fq.FakeWidget
    monkeypatch.setattr(fq, "SIGNALS", fq.SIGNALS | {"returnPressed"})
    for flag in ("ShiftModifier", "ControlModifier", "AltModifier", "MetaModifier"):
        monkeypatch.setattr(fq.FakeWidget, flag, 0, raising=False)
    for name in ("setWindowTitle", "save", "restore", "drawLine", "drawRect", "drawText"):
        monkeypatch.setattr(fq.FakeWidget, name, lambda self, *args: None, raising=False)
    for name in ("horizontalScrollBar", "verticalScrollBar"):
        monkeypatch.setattr(fq.FakeWidget, name, lambda self: _Bar(), raising=False)
    module = handle.load("fontlabapp.fontui.tmetrics")
    monkeypatch.setattr(module, "_canvas_colors", lambda canvas, colors: {
        **colors, "selection_background": colors["selected"], "selection_foreground": "#303030",
    })
    monkeypatch.setattr(fq, "RECORDED_METHODS", fq.RECORDED_METHODS | {
        "setContentsMargins", "setSpacing", "setFrameShape",
    })
    yield module
    for name in OWN_MODULES:
        sys.modules.pop(name, None)


class Host:
    """Glyph-window text host that keeps the font and text callbacks it is given."""

    def __init__(self):
        self.text = "AV"

    def read_text(self):
        return self.text

    def write_text(self, text):
        self.text = text
        return True

    def subscribe(self, owner, callback, fonts, text_callback=None):
        self.callback, self.text_callback = callback, text_callback


def make(module):
    font = CountingFont()
    host = Host()
    window = module.TMetrics(font, host=host)
    return window, host, font


def test_typing_when_text_changes_then_whole_font_not_reread(tm_mod):
    window, _, font = make(tm_mod)
    window.set_text("AV")
    font.counts.clear()
    window.set_text("VAVA")
    window.text_control.setText("AVAV")
    window.set_view(size=72)
    assert [cell.name for cell in window.model.cells] == ["A", "V", "A", "V"]
    assert font.counts.get("keys", 0) == 0, font.counts
    assert font.counts.get("kerning", 0) == 0, font.counts
    assert font.counts.get("glyph_summaries", 0) == 0, font.counts


def test_refresh_when_font_edited_then_rereads_and_shows_edit(tm_mod):
    window, _, font = make(tm_mod)
    window.set_text("AV")
    kern = window.model.cells[0].kern
    font.kerning[("public.kern1.A", "public.kern2.V")] = -200
    font.ufo["V"].width = 650
    window.set_text("AV ")
    window.set_text("AV")
    if _HAS_HARFBUZZ:
        assert window.model.cells[0].kern == kern, "Typing reuses the last font reads"
    font.counts.clear()
    window.refresh()
    assert font.counts.get("kerning", 0) >= 1
    assert window.model.cells[0].kern != kern
    assert window.model.cells[0].kern == -200
    assert window.model.cells[1].width == 650


def test_refresh_when_glyph_added_then_cell_appears(tm_mod):
    window, _, font = make(tm_mod)
    window.set_text("AQ")
    assert not window.model.cells[1].present
    glyph = font.ufo.newGlyph("Q")
    glyph.width = 500
    glyph.unicodes = [ord("Q")]
    window.refresh()
    assert window.model.cells[1].present and window.model.cells[1].name == "Q"


def test_follow_when_font_edited_then_rereads_and_shows_edit(tm_mod):
    window, host, font = make(tm_mod)
    host.callback()
    font.kerning[("public.kern1.A", "public.kern2.V")] = -150
    font.counts.clear()
    host.callback()
    assert font.counts.get("kerning", 0) >= 1
    assert window.model.cells[0].kern == -150
    assert window.drawn == window.model.fingerprint()


def test_follow_when_font_edited_then_whole_font_read_once(tm_mod):
    window, host, font = make(tm_mod)
    host.callback()
    font.kerning[("public.kern1.A", "public.kern2.V")] = -150
    font.counts.clear()
    host.callback()
    assert window.model.cells[0].kern == -150
    assert font.counts.get("kerning", 0) == 1, font.counts
    assert font.counts.get("keys", 0) <= 1, font.counts
    assert font.counts.get("groups", 0) <= 1, font.counts


def test_follow_text_when_host_text_changes_then_reshapes_without_rereading(tm_mod):
    window, host, font = make(tm_mod)
    host.callback()
    font.counts.clear()
    host.text = "VVA"
    assert host.text_callback == window.follow_text
    host.text_callback()
    assert [cell.name for cell in window.model.cells] == ["V", "V", "A"]
    assert font.counts.get("kerning", 0) == 0 and font.counts.get("keys", 0) == 0, font.counts


def test_use_font_when_font_replaced_then_new_reads(tm_mod):
    window, _, _ = make(tm_mod)
    other = CountingFont()
    other.ufo["A"].width = 777
    window.font = other
    window.set_text("AV")
    window.refresh()
    assert window.model.font.font is other
    assert window.model.cells[0].width == 777


def test_subscribe_when_text_callback_given_then_poll_uses_it(monkeypatch):
    import _cov_qt as qt

    qt.install(monkeypatch)
    from fontlabapp.fontui import lifecycle

    hooked, callbacks = [], []
    monkeypatch.setattr(lifecycle, "follow_changes", lambda *args: hooked.append(args))
    monkeypatch.setattr(lifecycle, "follow_history", lambda *args: hooked.append(args))

    class Timer:
        def __init__(self, parent):
            self.timeout = object()

        def setInterval(self, interval):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(sys.modules["PythonQt"].QtCore, "QTimer", Timer)
    owner = NS(
        widget=object(), closed=False,
        connect=lambda signal, callback: callbacks.append(callback),
        diagnostic=NS(setText=lambda text: None),
    )
    host, block, *_ = bridge()
    fonts, texts = [], []

    def font_changed():
        fonts.append(host.read_text())

    host.subscribe(owner, font_changed, lambda: [host.font], text_callback=lambda: texts.append(host.read_text()))
    assert all(font_changed in args for args in hooked), "Font hooks keep the font callback"
    callbacks[0]()
    callbacks[0]()
    block.value.items = []
    callbacks[0]()
    assert texts == ["AV", ""]
    assert fonts == []


def test_reshape_when_current_master_switched_then_reads_forgotten(tm_mod):
    window, _, font = make(tm_mod)
    window.set_layer("Bold")
    window.set_text("AV")
    assert not window._current_master()
    font.counts.clear()
    font.defaultLayerName = "Bold"
    window.set_text("VA")
    assert window._current_master(), "A master switch without a notification is seen on the next keystroke"
    assert font.counts.get("keys", 0) >= 1, font.counts


def test_reshape_when_master_unchanged_then_reads_kept(tm_mod):
    window, _, font = make(tm_mod)
    window.set_text("AV")
    font.counts.clear()
    window.set_text("VA")
    assert font.counts.get("keys", 0) == 0, font.counts


def test_outline_when_read_fails_then_failure_not_remembered(tm_mod):
    model_mod = sys.modules["fontlabapp.fontui.tmetrics_model"]
    calls = []

    def flaky(font, name):
        calls.append(name)
        if len(calls) == 1:
            raise RuntimeError("transient")
        return "shape"

    model = NS(_outlines=None)
    kept = {}
    original = model_mod.outline
    model_mod.outline = flaky
    try:
        scope = model_mod.TMetricsModel.outline_scope
        outline_of = model_mod.TMetricsModel.outline_of
        font = object()
        with scope(model, kept):
            with pytest.raises(RuntimeError):
                outline_of(model, font, "A")
        with scope(model, kept):
            assert outline_of(model, font, "A") == "shape"
            assert outline_of(model, font, "A") == "shape"
    finally:
        model_mod.outline = original
    assert calls == ["A", "A"]


def test_typing_when_unknown_name_repeated_then_font_asked_once_per_name(tm_mod):
    window, _, font = make(tm_mod)
    window.set_text("AV")
    font.counts.clear()
    for text in ("/foo", "/foo ", "/foo A", "/foo AV", "/foo /bar", "/foo /bar V"):
        window.text_control.setText(text)
    assert font.counts.get("in:foo", 0) == 1, font.counts
    assert font.counts.get("in:bar", 0) == 1, font.counts
    assert font.counts.get("keys", 0) == 0, font.counts


def test_typing_when_glyph_added_after_unknown_name_then_seen(tm_mod):
    pytest.importorskip(
        "uharfbuzz", reason="the fallback keeps unknown /names as empty cells"
    )
    window, _, font = make(tm_mod)

    def names():
        return [cell.name for cell in window.model.cells]

    window.set_text("/A /foo")
    assert names() == ["A"]
    font.ufo.newGlyph("foo").width = 300
    window.set_text("/A /foo ")
    assert names() == ["A"], "/foo is asked once per read generation"
    font.ufo.newGlyph("Q").width = 500
    window.set_text("/A /foo /Q")
    assert names() == ["A", "foo", "Q"], "an already-probed /foo does not hide a new /Q, whose re-read shows both"
    window.set_text("/A /bar")
    font.ufo.newGlyph("bar").width = 400
    window.set_text("/A /bar ")
    assert names() == ["A"]
    window._forget_font_reads()
    window.set_text("/A /bar")
    assert names() == ["A", "bar"], "after forgetting, the new glyph is seen"


class OldLayer:
    """Old Fontport ``RLayer``: keys, ``in`` and ``layer[name]`` each list every glyph."""

    def __init__(self, font, layer):
        self._font, self._layer = font, layer

    def keys(self):
        self._font.scans["keys"] += 1
        return tuple(self._layer.keys())

    def __contains__(self, name):
        self._font.scans["in"] += 1
        return name in tuple(self._layer.keys())

    def __getitem__(self, name):
        self._font.scans["getitem"] += 1
        if name not in tuple(self._layer.keys()):
            raise KeyError(name)
        return self._layer[name]

    def __iter__(self):
        return (self[name] for name in self.keys())

    def __len__(self):
        return len(self.keys())


class OldFont:
    """Font shaped like Fontport before ``glyph_summaries``: every lookup is one whole-font scan."""

    def __init__(self, count):
        from ufoLib2 import Font

        self.ufo = Font()
        self.ufo.info.unitsPerEm = 1000
        self.ufo.info.ascender, self.ufo.info.descender = 800, -200
        for i in range(count):
            name = "A" if i == 0 else "V" if i == 1 else f"g{i:05d}"
            glyph = self.ufo.newGlyph(name)
            glyph.width = 600
            glyph.unicodes = (
                [65] if name == "A" else [86] if name == "V" else [0xE000 + i]
            )
            pen = glyph.getPen()
            pen.moveTo((0, 0))
            pen.lineTo((300, 700))
            pen.lineTo((600, 0))
            pen.closePath()
        self.ufo.newLayer("Bold")
        self.scans = Counter()
        self.info = self.ufo.info
        self.kerning = {("A", "V"): -80}
        self.groups = {}
        self.features = NS(text="")
        self.defaultLayerName = "public.default"
        self.layerOrder = ["public.default", "Bold"]
        self._default = OldLayer(self, self.ufo.layers.defaultLayer)

    def keys(self):
        return self._default.keys()

    def __contains__(self, name):
        return name in self._default

    def __getitem__(self, name):
        return self._default[name]

    def __iter__(self):
        return iter(self._default)

    def __len__(self):
        return len(self._default)

    @property
    def glyphOrder(self):
        return self._default.keys()

    @property
    def defaultLayer(self):
        return self._default

    def getLayer(self, name):
        self.scans["layer"] += 1
        return (
            self._default
            if name == "public.default"
            else OldLayer(self, self.ufo.layers[name])
        )


@pytest.mark.parametrize("count", [300, 1200])
def test_typing_when_font_lacks_summaries_then_no_whole_font_scans(tm_mod, count):
    font = OldFont(count)
    window = tm_mod.TMetrics(font, host=Host())
    window.set_text("AV")
    for text in ("/A/V /A", "AVAV", "AVAVAVAV", "AVA"):
        font.scans.clear()
        window.text_control.setText(text)
        assert sum(font.scans.values()) <= 1, (text, font.scans)
    assert [cell.name for cell in window.model.cells] == ["A", "V", "A"]
    assert window.model.cells[0].kern == -80


def test_refresh_when_font_lacks_summaries_then_edits_and_new_glyphs_seen(tm_mod):
    font = OldFont(20)
    window = tm_mod.TMetrics(font, host=Host())
    window.set_text("AV")
    font.ufo["V"].width = 650
    font.kerning = {("A", "V"): -200}
    window.refresh()
    assert window.model.cells[1].width == 650 and window.model.cells[0].kern == -200
    glyph = font.ufo.newGlyph("Q")
    glyph.width, glyph.unicodes = 500, [ord("Q")]
    window.set_text("AQ")
    if _HAS_HARFBUZZ:
        assert not window.model.cells[1].present, "Typing reuses the last font reads"
    window.refresh()
    assert window.model.cells[1].present and window.model.cells[1].width == 500


def test_typing_when_font_has_summaries_then_summaries_used_not_glyphs(
    tm_mod, monkeypatch
):
    pytest.importorskip(
        "uharfbuzz", reason="only the HarfBuzz snapshot reads glyph_summaries"
    )
    window, _, font = make(tm_mod)
    asked = []
    original = type(window._reads).__getitem__
    monkeypatch.setattr(
        type(window._reads),
        "__getitem__",
        lambda self, name: asked.append(name) or original(self, name),
    )
    font.counts.clear()
    window.refresh()
    window.text_control.setText("AVA")
    assert font.counts.get("glyph_summaries", 0) == 1, font.counts
    assert set(asked) <= {"A", "V"}, "Only the typed glyphs are read one by one"
