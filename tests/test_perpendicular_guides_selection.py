# this_file: tests/test_perpendicular_guides_selection.py
"""First-layer scope must never resolve an irrelevant later glyph/layer slot."""

from time import monotonic
from types import SimpleNamespace as NS

import fontlabapp.guides.perpendicular.selection as m
import pytest


@pytest.fixture
def source(monkeypatch):
    package = NS(id=10, fgId=99)
    layer = NS(id=30, name="Regular", isNull=False)
    glyph = NS(
        id=20,
        name="A",
        package=package,
        isNull=False,
        findLayer=lambda name: layer,
        activeLayer=layer,
    )
    calls = []

    def find(name):
        calls.append(name)
        if name != "A":
            raise AssertionError("Later glyph must never resolve")
        return glyph

    package.findName = find
    doc = NS(
        package=package, context=(10, "Regular", "font", 100), carriers=(), blocks=()
    )
    monkeypatch.setattr(m.reader, "_document", lambda deadline: doc)

    class Font:  # live FontLab 9 legacy Font: no id, identified by its saved path
        file_name = "/f/a.vfj"

        def __len__(self):
            return 2

        def __getitem__(self, index):
            assert index == 0, "Later glyph name must never read"
            return NS(name="A")

    fl = NS(
        font=Font(),
        Selected=lambda index: (
            True
            if index == 0
            else (_ for _ in ()).throw(
                AssertionError("Later selection must never read")
            )
        ),
    )
    monkeypatch.setattr(m, "_native", lambda name: NS(fl=fl))
    from fontlabapp.core import scripting

    current = NS(isNull=False, path="/f/a.vfj", fgId=99)
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: NS(flWorkspace=NS(instance=lambda: NS(currentPackage=current))),
    )
    return NS(
        doc=doc, package=package, glyph=glyph, layer=layer, fl=fl, calls=calls, current=current
    )


@pytest.mark.parametrize(("path", "ok"), [("/f/a.vfj", True), ("/f/other.vfj", False)])
def test_font_when_legacy_font_has_no_id_then_saved_path_fences_carrier(
    source, monkeypatch, path, ok
):
    from fontlabapp.core import scripting

    class Font:  # FontLab 9 legacy Font: no id, only its saved path
        file_name = path

        def __len__(self):
            return 1

        def __getitem__(self, index):
            return NS(name="A")

    source.fl.font = Font()
    current = NS(isNull=False, path="/f/a.vfj", fgId=99)
    monkeypatch.setattr(scripting, "_native", lambda name: NS(
        flWorkspace=NS(instance=lambda: NS(currentPackage=current))))
    if ok:
        assert len(m.capture(monotonic() + 2).occurrences) == 1
    else:
        with pytest.raises(ValueError, match="path differs"):
            m.capture(monotonic() + 2)


def test_font_first_occurrence_stops_before_later_selected_glyph(source):
    result = m.capture(monotonic() + 2)
    assert len(result.occurrences) == 1
    assert result.occurrences[0].layer is source.layer
    assert source.calls == ["A", "A"]


def test_editor_first_occurrence_stops_before_selected_control(source):
    def get(index):
        if index:
            raise AssertionError("Later selected control must not resolve")
        return NS(
            isSelected=True,
            isActive=False,
            glyph=source.glyph,
            symbol=NS(layerName="Regular"),
        )

    block = NS(id=7, glyphsCount=lambda: 2, getGlyphAt=get)
    source.doc.context = (10, "Regular", "editor", 100, (7, 8))
    source.doc.blocks = (block,)
    result = m.capture(monotonic() + 2)
    assert result.occurrences[0].block_id == 7 and result.occurrences[0].index == 0
    assert result.context == (10, "Regular", "editor", 100)


def test_editor_skips_unselected_earlier_slots_and_retains_active_layer(source):
    def get(index):
        return (
            None
            if index == 0
            else NS(
                isSelected=False,
                isActive=True,
                glyph=source.glyph,
                symbol=NS(layerName=""),
            )
        )

    source.doc.context = (10, "Regular", "editor", 100, (7,))
    source.doc.blocks = (NS(id=7, glyphsCount=lambda: 2, getGlyphAt=get),)
    assert m.capture(monotonic() + 2).occurrences[0].index == 1


@pytest.mark.parametrize(
    "failure", ["carrier", "first-layer", "first-glyph", "no-selection", "expired"]
)
def test_only_actual_first_target_or_carrier_failure_blocks(source, failure):
    if failure == "carrier":
        source.current.path = "/f/other.vfj"
    elif failure == "first-layer":
        source.glyph.findLayer = lambda name: None
    elif failure == "first-glyph":
        source.glyph.isNull = True
    elif failure == "no-selection":
        source.fl.Selected = lambda index: False
    if failure == "no-selection":
        assert not m.capture(monotonic() + 2).occurrences
    else:
        with pytest.raises((ValueError, TimeoutError)):
            m.capture(monotonic() - 1 if failure == "expired" else monotonic() + 2)


def test_first_target_changes_between_passes_refused(source, monkeypatch):
    original = m.read
    count = [0]

    def read(deadline):
        value = original(deadline)
        count[0] += 1
        if count[0] == 1:
            source.layer.id = 31
        return value

    monkeypatch.setattr(m, "read", read)
    with pytest.raises(ValueError, match="changed"):
        m.capture(monotonic() + 2)


def test_editor_first_missing_glyph_is_diagnosed_without_ordinal_guess(source):
    source.doc.context = (10, "Regular", "editor", 100, (7,))
    source.doc.blocks = (
        NS(
            id=7,
            glyphsCount=lambda: 1,
            getGlyphAt=lambda i: NS(isSelected=True, isActive=False, glyph=None),
        ),
    )
    with pytest.raises(ValueError, match="no glyph"):
        m.capture(monotonic() + 2)


def test_first_auxiliary_layer_name_never_falls_back_to_master(source):
    source.layer.name = "Aux"

    def layer(name):
        assert name == "Aux"
        return source.layer

    source.glyph.findLayer = layer
    source.doc.context = (10, "Regular", "editor", 100, (7,))
    source.doc.blocks = (
        NS(
            id=7,
            glyphsCount=lambda: 2,
            getGlyphAt=lambda i: (
                NS(
                    isSelected=True,
                    isActive=False,
                    glyph=source.glyph,
                    symbol=NS(layerName="Aux"),
                )
                if i == 0
                else (_ for _ in ()).throw(AssertionError("Later slot"))
            ),
        ),
    )
    assert m.capture(monotonic() + 2).occurrences[0].layer_name == "Aux"


def test_empty_editor_selection_is_not_replaced_by_active_glyph_guess(source):
    source.doc.context = (10, "Regular", "editor", 100, (7,))
    source.doc.blocks = (
        NS(
            id=7,
            glyphsCount=lambda: 2,
            getGlyphAt=lambda i: (
                None if i == 0 else NS(isSelected=False, isActive=False)
            ),
        ),
    )
    assert not m.capture(monotonic() + 2).occurrences


def test_font_carrier_change_during_target_resolution_refused(source):
    def find(name):
        source.current.path = "/f/other.vfj"
        return source.layer

    source.glyph.findLayer = find
    with pytest.raises(ValueError, match="path differs"):
        m.capture(monotonic() + 2)


def test_font_when_same_path_but_other_fgid_then_refused_before_capture(source):
    source.current.fgId = source.package.fgId + 1
    with pytest.raises(ValueError, match="differs from the active package"):
        m.capture(monotonic() + 2)


def test_font_when_fgid_changes_during_capture_then_carrier_changed(source):
    def find(name):
        source.current.fgId = source.package.fgId + 1
        return source.layer

    source.glyph.findLayer = find
    with pytest.raises(ValueError, match="carrier changed"):
        m.capture(monotonic() + 2)
