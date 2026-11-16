# this_file: tests/test_node_duplicator_guards.py
"""Current writer safety rules over the actual literal Node Duplicator boundary."""

from types import SimpleNamespace as NS

import pytest

from test_node_duplicator_native import host
from fontlabapp.contours.nodes.duplicator.native import execute
from fontlabapp.contours.nodes.duplicator._write import WriteError


@pytest.mark.parametrize("mode", ["current", "all", "handles"])
def test_execute_when_updates_pending_then_discloses_once_without_refusal_or_clear(
    mode,
):
    owned, native, qt, notifications, contour, provider, selected = host(mode)
    reads = []
    native.flGlyph.updatedFgGlyphs = lambda: reads.append(True) or [919, 920]
    result = execute(mode, native=native, qt=qt, provider=provider, report=False)
    assert result["pending_updates"] == (919, 920)
    assert "8537" in result["pending_note"]
    assert len(reads) == 1, (
        "Read the native queue once, without clearing or draining it"
    )
    assert result["inserted"] == (3 if mode == "handles" else 1)
    assert len(notifications) == 1


def canvas_host():
    owned, native, qt, notifications, contour, provider, selected = host("all")
    other, *_ = host("all")
    first, layer = owned.bound[30]
    second, other_layer = other.bound[30]
    second.id, second.name, other_layer.id = 41, "b", 31
    first.isNull = second.isNull = False
    other_layer.shapes[0].id = 72
    other_layer.shapes[0].shapeData.id = 73
    other_layer.shapes[0].contours[0].id = 21
    package = first.package
    second.package = package
    package.findName = lambda name: {"a": first, "b": second}[name]
    native.CurrentFont = lambda: NS(id=60, glyphs=[NS(name="a"), NS(name="b")])
    canvas = NS(
        isNull=False,
        selectedNodes=lambda: [NS(node=contour.nodes()[0])],
        selection=lambda: [],
        textBlocks=lambda: [
            NS(glyphsCount=lambda: 1, getGlyphAt=lambda index: NS(glyph=first))
        ],
    )
    native.flWorkspace.instance().getActiveCanvas = lambda: canvas
    selected.context, selected.carriers = (50, "Regular", "editor", 1), (canvas,)
    selected.occurrences += (
        NS(
            package=package,
            glyph=second,
            layer=other_layer,
            package_id=50,
            glyph_id=41,
            layer_id=31,
            block_id=0,
            index=1,
        ),
    )
    return owned, native, qt, notifications, contour, provider, first, second


def test_execute_when_canvas_omits_one_owner_then_refuses_before_cloning_or_history(
    monkeypatch,
):
    owned, native, qt, notifications, contour, provider, first, second = canvas_host()
    contour.nodes()[0].clone = lambda: pytest.fail(
        "Unsafe scope must be refused before staging"
    )
    with pytest.raises(ValueError, match="Font window"):
        execute("all", native=native, qt=qt, provider=provider, report=False)
    assert not notifications and first.events == second.events == []
    assert len(contour.nodes()) == 1


def test_execute_when_all_owners_in_canvas_then_complete_original_scope_is_allowed():
    owned, native, qt, notifications, contour, provider, first, second = canvas_host()
    canvas = native.flWorkspace.instance().getActiveCanvas()
    canvas.textBlocks = lambda: [
        NS(
            glyphsCount=lambda: 2,
            getGlyphAt=lambda index: NS(glyph=[first, second][index]),
        )
    ]
    result = execute("all", native=native, qt=qt, provider=provider, report=False)
    assert result["inserted"] == 2 and len(notifications) == 1


@pytest.mark.parametrize("field", ["layer_note", "shape_name", "shape_note"])
def test_execute_when_captured_metadata_changes_during_insert_then_never_returns_success(
    field,
):
    owned, native, qt, notifications, contour, provider, selected = host()
    layer = owned.bound[30][1]
    original = contour.insert

    def corrupt(index, node):
        original(index, node)
        if field == "layer_note":
            layer.note = "unexpected owned change"
        else:
            setattr(
                layer.shapes[0].shapeData,
                "name" if field == "shape_name" else "note",
                "unexpected",
            )

    contour.insert = corrupt
    with pytest.raises(WriteError, match="metadata"):
        execute("current", native=native, qt=qt, provider=provider, report=False)
    assert len(notifications) == 1, (
        "A late failure retains the completed Undo notification"
    )


def test_execute_when_invalid_profile_then_refuses_before_any_native_access():
    class Forbidden:
        def __getattr__(self, name):
            pytest.fail("Invalid profile must not read native state")

    with pytest.raises(ValueError, match="profile"):
        execute("invalid", native=Forbidden(), qt=Forbidden(), report=False)
