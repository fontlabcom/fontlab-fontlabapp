# this_file: tests/test_kerning_group_proof_read_domain.py
"""Original conditional sides and first selected parent, without layer reads."""

from time import monotonic
from types import SimpleNamespace as NS

import fontlabapp.kerning.group_proof.native as native
import fontlabapp.kerning.group_proof.selection as selection
import fontlabapp.kerning.group_proof.model as api
import pytest
import test_layer_selection as layer_tests
from test_kerning_group_proof_native import owned


@pytest.fixture
def source(monkeypatch):
    return layer_tests.source.__wrapped__(monkeypatch)


@pytest.mark.parametrize(
    "current_side,unused_mode", [("KernLeft", "KernRight"), ("KernRight", "KernLeft")]
)
def test_absent_current_side_never_resolves_ambiguous_peer_side(
    monkeypatch, current_side, unused_mode
):
    state = owned(
        monkeypatch,
        groups={
            "proof": (["current", "right.peer"], current_side),
            "unusedA": (["left.unencoded"], unused_mode),
            "unusedB": (["left.unencoded"], unused_mode),
        },
    )
    result = api.run()
    assert result is not None and result.has_peers and len(state.opened) == 1
    assert (result.right if current_side == "KernLeft" else result.left) == (
        "right.peer",
    )
    assert (result.left if current_side == "KernLeft" else result.right) == ()


def test_first_font_selected_identity_never_resolves_any_selected_layer(monkeypatch):
    package = NS(id=42, fgId=777)

    class Glyph:
        id = 111
        fgGlyphId = 11
        name = "current"
        isNull = False

        def findLayer(self, name):
            raise AssertionError("unrequested layer getter")

        @property
        def activeLayer(self):
            raise AssertionError("unrequested active layer")

    first = Glyph()
    first.package = package

    def find(name):
        assert name == "current", "Later selected glyph resolved"
        return first

    package.findName = find
    package.kerning = lambda master: NS(
        groups={"right": (["current", "peer"], "KernLeft")}
    )
    doc = NS(
        package=package, context=(42, "Regular", "font", 99), blocks=(), carriers=()
    )
    monkeypatch.setattr(native, "current_package", lambda: package)
    monkeypatch.setattr(selection, "_document", lambda deadline: doc)
    monkeypatch.setattr(
        selection.layers,
        "names_font_window_selection",
        lambda **kw: ["current", "broken.later"],
    )
    monkeypatch.setattr(
        native,
        "_native",
        lambda name: NS(
            CurrentFont=lambda: NS(
                id=777, glyphs=[NS(id=11, name="current"), NS(id=12, name="peer")]
            )
        ),
    )
    captured = native.capture(monotonic() + 2)
    assert captured.current_id == 11 and captured.rows[-1].name == "peer"


def test_no_current_groups_never_reads_the_font_glyph_inventory(monkeypatch):
    state = owned(monkeypatch, groups={})

    class Font:
        id = 777

        @property
        def glyphs(self):
            raise AssertionError("Original no-group branch does not scan peers")

    state.font = Font()
    assert api.run().has_peers is False and not state.opened


@pytest.mark.parametrize("problem", ["none", "null", "foreign"])
def test_first_parent_rejects_missing_or_foreign_identity_without_layers(
    monkeypatch, problem
):
    package = NS(id=42, fgId=777)
    glyph = (
        None
        if problem == "none"
        else NS(
            isNull=problem == "null", package=NS(id=999 if problem == "foreign" else 42)
        )
    )
    doc = NS(context=(42, "Regular", "font", 99), package=package, carriers=())
    package.findName = lambda name: glyph
    monkeypatch.setattr(selection, "_document", lambda deadline: doc)
    monkeypatch.setattr(
        selection.layers, "names_font_window_selection", lambda **kw: ["current"]
    )
    with pytest.raises(ValueError, match="first selected glyph"):
        selection.read(monotonic() + 2)


def test_empty_font_selection_has_no_parent_fallback(monkeypatch):
    package = NS(fgId=777)
    monkeypatch.setattr(
        selection,
        "_document",
        lambda deadline: NS(context=(42, "Regular", "font", 99), package=package),
    )
    monkeypatch.setattr(
        selection.layers, "names_font_window_selection", lambda **kw: []
    )
    assert selection.read(monotonic() + 2) is None


@pytest.mark.parametrize("active", [False, True])
def test_editor_stops_before_later_slots_blocks_and_symbol_layer_getters(
    monkeypatch, active
):
    package = NS(id=42, fgId=777)
    glyph = NS(id=111, fgGlyphId=11, name="current", isNull=False, package=package)

    class Info:
        isSelected = not active
        isActive = active

        @property
        def glyph(self):
            return glyph

        @property
        def symbol(self):
            raise AssertionError("No selected-layer property belongs to this original")

    reads = []

    def slot(index):
        reads.append(index)
        assert index < 3, "Later selected slot read"
        return [None, NS(isSelected=False, isActive=False), Info()][index]

    block = NS(id=9, glyphsCount=lambda: 4, getGlyphAt=slot)
    doc = NS(
        context=(42, "Regular", "editor", 88),
        package=package,
        blocks=(block, NS()),
        carriers=(object(),),
    )
    monkeypatch.setattr(selection, "_document", lambda deadline: doc)
    first = selection.read(monotonic() + 2)
    assert reads == [0, 1, 2] and first.glyph_id == 11 and first.glyph_name == "current"
    assert first.block_id == 9 and first.index == 2 and first.carriers == doc.carriers


def test_empty_editor_blocks_and_no_selected_slots_have_no_fallback(monkeypatch):
    doc = NS(context=(42, "Regular", "editor", 88), blocks=())
    monkeypatch.setattr(selection, "_document", lambda deadline: doc)
    assert selection.read(monotonic() + 2) is None
    doc.blocks = (
        NS(glyphsCount=lambda: 0),
        NS(
            glyphsCount=lambda: 1,
            getGlyphAt=lambda index: NS(isSelected=False, isActive=False),
        ),
    )
    assert selection.read(monotonic() + 2) is None


def test_selection_deadline_is_checked_after_native_calls(monkeypatch):
    doc = NS(context=(42, "Regular", "editor", 88), blocks=())
    monkeypatch.setattr(selection, "_document", lambda deadline: doc)
    with pytest.raises(TimeoutError):
        selection.read(-1)


def test_later_selected_parent_changes_do_not_invalidate_first_identity(monkeypatch):
    state = owned(monkeypatch)
    original = native._read

    def read(first, deadline):
        result = original(first, deadline)
        state.selection.occurrences = (state.selection.occurrences[0], NS())
        return result

    monkeypatch.setattr(native, "_read", read)
    assert api.run().left == ("left.unencoded",) and len(state.opened) == 1


def test_real_document_context_does_not_touch_later_editor_block_ids(
    source, monkeypatch
):
    monkeypatch.setattr(selection, "_native", selection.layers._native)
    font = selection._document(monotonic() + 2)
    assert font.context[:3] == (1, "Regular", "font") and font.carriers
    source.workspace.activeFontPanel = None

    class Later:
        @property
        def id(self):
            raise AssertionError("Unvisited block ID read")

    source.canvas.textBlocks = lambda: [source.block, Later()]
    editor = selection._document(monotonic() + 2)
    assert editor.context == (1, "Regular", "editor", 20) and len(editor.blocks) == 2


@pytest.mark.parametrize(
    "problem",
    [
        "none-package",
        "null-package",
        "none-canvas",
        "null-canvas",
        "wrong-window",
        "expired",
    ],
)
def test_real_document_refuses_invalid_source_without_parent_or_layer(
    source, monkeypatch, problem
):
    monkeypatch.setattr(selection, "_native", selection.layers._native)
    source.workspace.activeFontPanel = None
    if problem == "none-package":
        source.workspace.currentPackage = None
    elif problem == "null-package":
        source.package.isNull = True
    elif problem == "none-canvas":
        source.workspace.getActiveCanvas = lambda: None
    elif problem == "null-canvas":
        source.canvas.isNull = True
    elif problem == "wrong-window":
        source.canvas.viewPort = type(source.canvas.viewPort)("Preview")
    with pytest.raises((ValueError, TimeoutError)):
        selection._document(-1 if problem == "expired" else monotonic() + 2)
