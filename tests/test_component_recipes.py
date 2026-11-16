# this_file: tests/test_component_recipes.py
"""Owned records and native-shaped fakes for the adapted recipe report."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace as NS

import pytest

import fontlabapp.components.recipes.model as api


def test_original_line_order_duplicates_mixed_layers_and_unicode_are_exact():
    records = (
        api.RecipeLayer("Aacute", ("A", "acute")),
        api.RecipeLayer("empty", ()),
        api.RecipeLayer("Aacute", ("A", "A")),
        api.RecipeLayer("é", ("e", "acute")),
    )
    assert api.recipes(records) == "A+acute=Aacute\nA+A=Aacute\ne+acute=é\n"
    assert api.recipes(()) == ""
    assert api.recipes((api.RecipeLayer(".notdef", ()),)) == ""
    with pytest.raises(FrozenInstanceError):
        records[0].glyph = "changed"


@pytest.fixture
def source(monkeypatch):
    shapes = [
        NS(id=30, isComponent=False),
        NS(id=31, isComponent=True, shapeData=NS(componentGlyph="A")),
        NS(id=32, isComponent=True, shapeData=NS(componentGlyph="acute")),
    ]
    layer = NS(id=20, name="Regular", isNull=False, shapes=shapes)
    package = NS(id=1, fgId=100, master="Regular")
    glyph = NS(
        id=10,
        name="Aacute",
        isNull=False,
        package=package,
        findLayer=lambda master: layer,
    )
    package.findName = lambda name: glyph
    state = NS(
        package=package,
        selection=["Aacute"],
        glyph=glyph,
        layer=layer,
        shapes=shapes,
        calls=[],
    )

    def selected(deadline):
        state.calls.append(deadline)
        if state.package is None:
            raise ValueError("Open a font")
        rows = []
        for index, name in enumerate(state.selection):
            item = state.package.findName(name)
            current = None if item is None else item.findLayer(state.package.master)
            if item is None or current is None:
                raise ValueError("Selected glyph/layer is missing")
            rows.append(
                api.selection.LayerOccurrence(state.package, item, current, 0, index)
            )
        return api.selection.LayerSelection(context(deadline), tuple(rows))

    def context(deadline):
        return (state.package.id, state.package.master, "font", 1)

    monkeypatch.setattr(api.selection, "capture", selected)
    monkeypatch.setattr(api.selection, "document_context", context)
    return state


def test_capture_reads_components_without_decomposing_paths_or_names(source):
    result = api.capture()
    assert result.master == "Regular" and result.package_id == 1
    assert api.recipes(result.layers) == "A+acute=Aacute\n"
    source.shapes[2].shapeData.componentGlyph = "missing.base"
    assert api.recipes(api.capture().layers) == "A+missing.base=Aacute\n"


@pytest.mark.parametrize("kind", ["font", "selection", "glyph", "layer"])
def test_no_font_no_selection_or_missing_native_record_is_diagnosed(source, kind):
    if kind == "font":
        source.package = None
    if kind == "selection":
        source.selection = []
    if kind == "glyph":
        source.package.findName = lambda name: None
    if kind == "layer":
        source.glyph.findLayer = lambda master: None
    with pytest.raises(ValueError):
        api.capture()


@pytest.mark.parametrize(
    "kind", ["component", "shape", "layer", "glyph", "master", "font", "selection"]
)
def test_complete_snapshot_refuses_observed_source_changes(source, kind):
    calls = 0

    def find(name):
        nonlocal calls
        calls += 1
        if calls == 2:
            if kind == "component":
                source.shapes[1].shapeData.componentGlyph = "B"
            if kind == "shape":
                source.shapes.reverse()
            if kind == "layer":
                source.layer.id += 1
            if kind == "glyph":
                source.glyph.id += 1
            if kind == "master":
                source.package.master = "Bold"
            if kind == "font":
                source.package.id += 1
            if kind == "selection":
                source.selection = []
        return source.glyph

    source.package.findName = find
    with pytest.raises(ValueError):
        api.capture()


def test_no_partial_publication_after_native_failure(source):
    source.shapes.append(NS(id=33, isComponent=True, shapeData=NS(componentGlyph=None)))
    with pytest.raises(ValueError, match="component"):
        api.capture()


def test_one_deadline_is_forwarded_to_all_shared_provider_reads(source):
    api.capture()
    assert len(source.calls) == 3 and len(set(source.calls)) == 1


def test_deadline_inside_shape_scan_discards_every_partial_recipe(source, monkeypatch):
    ticks = [0.0]
    monkeypatch.setattr(api, "monotonic", lambda: ticks[0])

    class SlowShape:
        id = 40

        @property
        def isComponent(self):
            ticks[0] = 3.0
            return False

    source.shapes.insert(0, SlowShape())
    with pytest.raises(TimeoutError):
        api.capture()


def test_every_selected_layer_is_read_in_order_without_a_silent_limit(
    source, monkeypatch
):
    names = [f"composite{i}" for i in range(200)]
    source.selection = names
    monkeypatch.setattr(api, "monotonic", lambda: 0.0)
    source.package.findName = lambda name: NS(
        id=10 + names.index(name),
        name=name,
        isNull=False,
        package=source.package,
        findLayer=lambda master: NS(
            id=1000 + names.index(name), name=master, isNull=False, shapes=source.shapes
        ),
    )
    result = api.capture()
    assert [layer.glyph for layer in result.layers] == names
    assert api.recipes(result.layers).splitlines() == [
        "A+acute=" + name for name in names
    ]


@pytest.mark.parametrize("fail_at", [1, 2])
def test_unsupported_or_changed_document_never_publishes_a_recipe(
    source, monkeypatch, fail_at
):
    original = api.selection.capture
    calls = []

    def selected(deadline):
        calls.append(deadline)
        if len(calls) == fail_at:
            raise ValueError("Activate a supported document window")
        return original(deadline)

    monkeypatch.setattr(api.selection, "capture", selected)
    with pytest.raises(ValueError, match="document window"):
        api.capture()
    assert len(calls) == fail_at


def test_final_document_context_call_cannot_publish_after_deadline(source, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(api, "monotonic", lambda: clock[0])
    original = api.selection.document_context

    def context(deadline):
        result = original(deadline)
        clock[0] = 3.0
        return result

    monkeypatch.setattr(api.selection, "document_context", context)
    with pytest.raises(TimeoutError):
        api.capture()
