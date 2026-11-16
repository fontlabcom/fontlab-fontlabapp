# this_file: tests/test_background_selection.py
"""Actual scoped first-layer reader; unrelated selected layers are poisonous."""

from time import monotonic

import fontlabapp.masters.background.selection as api
import pytest
import test_layer_selection as common


@pytest.fixture
def source(monkeypatch):
    h = common.source.__wrapped__(monkeypatch)
    monkeypatch.setattr(api, "_native", api.layers._native)
    return h


def test_font_reader_resolves_only_first_selected_layer(source, monkeypatch):
    reads = []
    original = source.package.findName

    def find(name):
        reads.append(name)
        assert name == "A"
        return original(name)

    source.package.findName = find
    monkeypatch.setattr(
        api.layers, "names_font_window_selection", lambda **kw: ["A", "broken.later"]
    )
    captured = api.capture(monotonic() + 2)
    assert captured.occurrences[0].layer is source.regular and reads == ["A", "A"]


def test_editor_reads_first_explicit_layer_without_later_blocks_or_slots(source):
    source.workspace.activeFontPanel = None

    class Later:
        @property
        def id(self):
            raise AssertionError("unvisited block ID")

    source.canvas.textBlocks = lambda: [source.block, Later()]
    result = api.capture(monotonic() + 2)
    assert (
        result.context == (1, "Regular", "editor", 20) and len(result.occurrences) == 1
    )
    assert result.occurrences[0].layer is source.bold
    source.records[:] = [None, source.info("", False, True)]
    assert api.capture(monotonic() + 2).occurrences[0].layer is source.regular


def test_empty_font_and_editor_selections_have_no_fallback(source):
    source.legacy.Selected = lambda index: False
    assert not api.capture(monotonic() + 2).occurrences
    source.workspace.activeFontPanel = None
    source.records[:] = [None, source.info("Regular", False)]
    assert not api.capture(monotonic() + 2).occurrences


@pytest.mark.parametrize(
    "problem",
    [
        "package",
        "null",
        "canvas",
        "wrong-window",
        "glyph",
        "layer",
        "foreign",
        "expired",
    ],
)
def test_first_layer_failures_refuse_before_background_capture(source, problem):
    source.workspace.activeFontPanel = None
    if problem == "package":
        source.workspace.currentPackage = None
    elif problem == "null":
        source.package.isNull = True
    elif problem == "canvas":
        source.workspace.getActiveCanvas = lambda: None
    elif problem == "wrong-window":
        source.canvas.viewPort = common.Widget("Preview")
    elif problem == "glyph":
        source.records[0].glyph = None
    elif problem == "layer":
        source.records[0].symbol.layerName = "Missing"
    elif problem == "foreign":
        source.glyph.package.id = 99
    with pytest.raises((ValueError, TimeoutError)):
        api.capture(-1 if problem == "expired" else monotonic() + 2)


def test_first_context_staleness_is_rejected(source, monkeypatch):
    original = api.read
    count = []

    def read(deadline):
        result = original(deadline)
        count.append(True)
        if len(count) == 1:
            source.package.master = "Other"
        return result

    monkeypatch.setattr(api, "read", read)
    with pytest.raises(ValueError):
        api.capture(monotonic() + 2)
