# this_file: tests/test_bracket_snapshot.py
"""Full-font SDK-boundary capture: no geometry, source mutation or partial scans."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.masters.layers.brackets import _snapshot as api


class Glyph(NS):
    @property
    def fgGlyph(self):
        raise AssertionError("Native fgGlyph getter must not run")


@pytest.fixture
def native(monkeypatch):
    package = NS(id=7, fgId=70, master="Regular", isNull=False)
    foreground = []
    objects = {}
    for i, name in enumerate(["A", "B", "C"], 1):
        glyph = Glyph(
            id=100 + i,
            fgGlyphId=i,
            name=name,
            package=package,
            isNull=False,
            isValid=True,
        )
        shapes = (
            [
                NS(
                    id=i * 100,
                    isComponent=True,
                    isComposite=True,
                    shapeData=NS(componentGlyph="A" if name == "B" else "B"),
                )
            ]
            if name != "A"
            else []
        )
        layer = NS(
            id=i * 10,
            name="[100]" if name == "A" else "Regular",
            glyph=glyph,
            isNull=False,
            isValid=True,
            isMaskLayer=False,
            isService=False,
            shapes=shapes,
        )
        glyph.layers = [layer]
        objects[i] = glyph
        foreground.append(NS(id=i, name=name))
    font = NS(id=70, glyphs=foreground)
    package.findFgId = Mock(side_effect=lambda identifier: objects[identifier])
    workspace = NS(currentPackage=package)
    module = NS(
        flWorkspace=NS(instance=lambda: workspace), CurrentFont=Mock(return_value=font)
    )
    monkeypatch.setattr(api, "_native", Mock(return_value=module))
    return NS(
        module=module, workspace=workspace, package=package, font=font, objects=objects
    )


def test_capture_when_complete_then_all_glyphs_layers_and_nested_edges_are_immutable(
    native,
):
    result = api.capture()
    assert result.context == (7, 70, "Regular")
    assert [g.name for g in result.glyphs] == ["A", "B", "C"]
    assert result.glyphs[0].layer_names == ("[100]",)
    assert result.glyphs[1].components == frozenset({"A"})
    assert result.glyphs[2].components == frozenset({"B"})
    assert native.package.findFgId.call_count == 6
    api.validate(result, api.monotonic() + 2)
    assert native.package.findFgId.call_count == 9


@pytest.mark.parametrize("role", ["isMaskLayer", "isService"])
def test_capture_when_background_or_service_then_excluded_but_identity_retained(
    native, role
):
    layer = native.objects[1].layers[0]
    setattr(layer, role, True)
    result = api.capture()
    assert (
        result.glyphs[0].layer_names == ()
        and result.glyphs[0].components == frozenset()
    )
    layer.name = "changed hidden name"
    with pytest.raises(ValueError, match="changed"):
        api.validate(result, api.monotonic() + 2)


def test_empty_font_and_repeated_layer_names_are_supported(native):
    layer = deepcopy(native.objects[1].layers[0])
    layer.glyph = native.objects[1]
    layer.id = 99
    native.objects[1].layers.append(layer)
    assert api.capture().glyphs[0].layer_names == ("[100]", "[100]")
    native.font.glyphs = []
    assert api.capture().glyphs == ()


@pytest.mark.parametrize(
    "problem",
    [
        "no-package",
        "null-package",
        "no-font",
        "wrong-font",
        "master-type",
        "fg-duplicate",
        "name-duplicate",
        "missing-native",
        "null-native",
        "invalid-native",
        "wrong-fg-id",
        "wrong-owner",
        "wrong-name",
        "null-layer",
        "invalid-layer",
        "foreign-layer",
        "duplicate-layer",
        "bad-layer-name",
        "bad-role",
        "bad-shape-role",
        "generated-shape",
        "duplicate-shape",
        "bad-component",
    ],
)
def test_capture_when_source_unreadable_then_no_snapshot(native, problem):
    g = native.objects[1]
    layer = g.layers[0]
    if problem == "no-package":
        native.workspace.currentPackage = None
    elif problem == "null-package":
        native.package.isNull = True
    elif problem == "no-font":
        native.module.CurrentFont.return_value = None
    elif problem == "wrong-font":
        native.font.id = 71
    elif problem == "master-type":
        native.package.master = None
    elif problem == "fg-duplicate":
        native.font.glyphs.append(native.font.glyphs[0])
    elif problem == "name-duplicate":
        native.font.glyphs[1].name = "A"
        native.objects[2].name = "A"
    elif problem == "missing-native":
        native.objects[1] = None
    elif problem == "null-native":
        g.isNull = True
    elif problem == "invalid-native":
        g.isValid = False
    elif problem == "wrong-fg-id":
        g.fgGlyphId = 99
    elif problem == "wrong-owner":
        g.package = NS(id=999)
    elif problem == "wrong-name":
        g.name = "mismatch"
    elif problem == "null-layer":
        layer.isNull = True
    elif problem == "invalid-layer":
        layer.isValid = False
    elif problem == "foreign-layer":
        layer.glyph = NS(id=999)
    elif problem == "duplicate-layer":
        g.layers.append(layer)
    elif problem == "bad-layer-name":
        layer.name = None
    elif problem == "bad-role":
        layer.isService = 1
    else:
        shape = NS(
            id=20, isComponent=True, isComposite=True, shapeData=NS(componentGlyph="A")
        )
        layer.shapes = [shape]
        if problem == "bad-shape-role":
            shape.isComponent = None
        elif problem == "generated-shape":
            shape.isComponent = False
        elif problem == "duplicate-shape":
            layer.shapes.append(shape)
        elif problem == "bad-component":
            shape.shapeData.componentGlyph = None
    with pytest.raises((ValueError, TypeError)):
        api.capture()


def test_capture_when_component_or_context_changes_between_passes_then_no_prefix(
    native,
):
    calls = 0

    def current():
        nonlocal calls
        calls += 1
        if calls == 2:
            native.objects[2].layers[0].shapes[0].shapeData.componentGlyph = "C"
        return native.font

    native.module.CurrentFont.side_effect = current
    with pytest.raises(ValueError, match="changed"):
        api.capture()
    native.module.CurrentFont.side_effect = None
    result = api.capture()
    native.package.master = "Bold"
    with pytest.raises(ValueError, match="changed"):
        api.validate(result, api.monotonic() + 2)


def test_capture_when_expired_or_wrong_thread_then_no_sdk_access(native, monkeypatch):
    with pytest.raises(TimeoutError):
        api.capture(deadline=api.monotonic() - 1)
    api._native.assert_not_called()
    with ThreadPoolExecutor(max_workers=1) as pool, pytest.raises(RuntimeError, match="thread"):
        pool.submit(api.capture).result()
    api._native.assert_not_called()


def test_capture_when_final_context_changes_then_no_stale_result(native):
    calls = 0

    def current():
        nonlocal calls
        calls += 1
        if calls == 3:
            native.package.master = "Other"
        return native.font

    native.module.CurrentFont.side_effect = current
    with pytest.raises(ValueError, match="changed"):
        api.capture()


def test_capture_when_plain_shape_then_geometry_and_shape_data_never_read(native):
    native.objects[1].layers[0].shapes = [
        NS(id=999, isComponent=False, isComposite=False)
    ]
    assert api.capture().glyphs[0].components == frozenset()


def test_capture_when_iterator_expires_mid_font_then_no_partial_snapshot(
    native, monkeypatch
):
    def glyphs():
        yield NS(id=1, name="A")
        monkeypatch.setattr(api, "monotonic", lambda: 11.0)
        yield NS(id=2, name="B")

    monkeypatch.setattr(api, "monotonic", lambda: 0.0)
    native.font.glyphs = glyphs()
    with pytest.raises(TimeoutError, match="no partial"):
        api.capture(deadline=10.0)
    assert native.package.findFgId.call_count == 1


def test_validate_when_context_changes_during_last_read_then_refused(native):
    result = api.capture()
    calls = 0

    def current():
        nonlocal calls
        calls += 1
        if calls == 2:
            native.package.master = "Other"
        return native.font

    native.module.CurrentFont.side_effect = current
    with pytest.raises(ValueError, match="changed"):
        api.validate(result, api.monotonic() + 2)
