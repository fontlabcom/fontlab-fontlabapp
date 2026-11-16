# this_file: tests/test_layer_selection.py
"""Owned native-shaped selection records: no native host or reference code."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.masters.layers.selection as api
from fontlabapp.core import scripting


class Widget:
    def __init__(self, kind, parent=None):
        self.kind, self.parent = kind, parent

    def inherits(self, kind):
        return kind == self.kind

    def parentWidget(self):
        return self.parent


@pytest.fixture
def source(monkeypatch):
    regular, bold = (
        NS(id=11, name="Regular", isNull=False),
        NS(id=12, name="Bold", isNull=False),
    )
    package = NS(id=1, fgId=100, isNull=False, master="Regular", path="/f/a.vfj")
    glyph = NS(id=2, name="A", package=NS(id=1), isNull=False, activeLayer=regular)
    glyph.findLayer = lambda name: {"Regular": regular, "Bold": bold}.get(name)
    package.findName = lambda name: glyph if name == "A" else None
    workspace = NS(
        currentPackage=package,
        activeFontPanel=Widget("FontWindow", Widget("YFrameWindow")),
    )
    legacy = NS(
        font=type(
            "Font",
            (),
            {
                "file_name": "/f/a.vfj",  # FontLab 9 legacy Font: no id
                "__len__": lambda self: 1,
                "__getitem__": lambda self, n: NS(name="A"),
            },
        )(),
        Selected=lambda index: True,
    )

    def info(layer="", selected=True, active=False):
        return NS(
            isSelected=selected,
            isActive=active,
            glyph=glyph,
            symbol=NS(layerName=layer),
        )

    records = [info("Bold"), info("Regular"), info("Bold"), info("Regular", False)]
    block = NS(id=21, glyphsCount=lambda: len(records), getGlyphAt=lambda i: records[i])
    canvas = NS(
        id=20,
        isNull=False,
        viewPort=Widget("QWidget", Widget("GlyphWindow")),
        textBlocks=lambda: [block],
    )
    workspace.getActiveCanvas = lambda: canvas
    native = NS(flWorkspace=NS(instance=lambda: workspace))
    lookup = lambda name: native if name == "fontlab" else NS(fl=legacy)
    monkeypatch.setattr(api, "_native", lookup)
    monkeypatch.setattr(scripting, "_native", lookup)
    return NS(
        workspace=workspace,
        package=package,
        glyph=glyph,
        records=records,
        canvas=canvas,
        block=block,
        info=info,
        regular=regular,
        bold=bold,
        legacy=legacy,
    )


def capture():
    return api.capture(api.monotonic() + 2)


def test_font_window_reads_actual_selection_and_matching_master_without_writes(source):
    result = capture()
    (row,) = result.occurrences
    assert row.package is source.package and row.glyph is source.glyph
    assert row.layer is source.regular and row.block_id == 0 and row.index == 0
    assert row.layer_id == 11 and row.glyph_id == 2 and row.package_id == 1
    assert result.context[2] == "font" and result.carriers


def test_editor_occurrences_keep_duplicates_order_and_explicit_mixed_layers(source):
    source.workspace.activeFontPanel = None
    result = capture()
    assert [row.layer_id for row in result.occurrences] == [12, 11, 12]
    assert [row.index for row in result.occurrences] == [0, 1, 2]
    assert result.context == (1, "Regular", "editor", 20, (21,))
    source.records[:] = [None, source.info("", False, True)]
    (row,) = capture().occurrences
    assert row.layer is source.regular and row.index == 1


@pytest.mark.parametrize("problem", ["glyph", "layer", "foreign", "master"])
def test_invalid_selected_records_never_return_a_partial_prefix(source, problem):
    source.workspace.activeFontPanel = None
    if problem == "glyph":
        source.records[1].glyph = None
    if problem == "layer":
        source.records[1].symbol.layerName = "Missing"
    if problem == "foreign":
        source.glyph.package.id = 8
    if problem == "master":
        source.glyph.activeLayer = None
        source.records[1].symbol.layerName = ""
    with pytest.raises(ValueError):
        capture()


def test_missing_font_or_wrong_document_has_a_clear_refusal(source):
    source.workspace.currentPackage = None
    with pytest.raises(ValueError, match="font"):
        capture()
    source.workspace.currentPackage = source.package
    source.workspace.activeFontPanel = None
    source.canvas.viewPort = Widget("Preview")
    with pytest.raises(ValueError, match="Glyph window"):
        capture()
    source.workspace.getActiveCanvas = lambda: None
    with pytest.raises(ValueError, match="Glyph window"):
        capture()


def test_empty_selection_is_empty_without_current_glyph_fallback(source):
    source.legacy.Selected = lambda index: False
    assert capture().occurrences == ()
    source.workspace.activeFontPanel = None
    source.records[:] = [source.info("", False)]
    assert capture().occurrences == ()


def test_changed_occurrences_or_document_between_two_reads_refuse(source):
    source.workspace.activeFontPanel = None
    count = [0]

    def blocks():
        count[0] += 1
        if count[0] == 2:
            source.records[0].symbol.layerName = "Regular"
        return [source.block]

    source.canvas.textBlocks = blocks
    with pytest.raises(ValueError, match="changed"):
        capture()


def test_deadline_expires_during_bounded_editor_scan_without_returning_prefix(
    source, monkeypatch
):
    source.workspace.activeFontPanel = None
    clock = [0.0]
    monkeypatch.setattr(api, "monotonic", lambda: clock[0])

    def read(index):
        clock[0] = 3.0
        return source.records[index]

    source.block.getGlyphAt = read
    with pytest.raises(TimeoutError):
        api.capture(2.0)
