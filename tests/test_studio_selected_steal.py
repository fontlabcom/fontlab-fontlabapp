# this_file: tests/test_studio_selected_steal.py
"""Retain selected-pair scanline numerical and failure oracles in the App gate."""
import importlib
import sys
from types import SimpleNamespace as NS
from typing import Any

import pytest
from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def four_slots(studio_qt, monkeypatch):  # noqa: F811
    module = importlib.import_module('fontlabapp.studios.kerning_studio.selected_steal')
    package = NS(id=7, master='Regular', masters=['Regular', 'Bold'], kerning=lambda master: NS(get=lambda pair: -25))
    rows = [NS(glyph_name=name, index=index, block_id=11,
               layer=NS(name='Regular', isMasterLayer=True, advanceWidth=500,
                        edges=(50, 450) if index < 2 else (75, 425),
                        shapes=[NS(contours=[NS(isTT=False, closed=True)])]))
            for index, name in enumerate(['A', 'V', 'V', 'A'])]
    selection = NS(context=(7, 'Regular', 'editor'), occurrences=tuple(rows))
    groups = {'AGroup': (('A',), 'KernLeft'), 'VGroup': (('V',), 'KernRight')}
    pair = (('AGroup', 'groupMode'), ('VGroup', 'groupMode'))
    snapshot = NS(groups={m: groups for m in package.masters}, pairs={m: {pair: -80} for m in package.masters})
    writes = []
    monkeypatch.setattr(module, 'selection', NS(capture=lambda deadline: selection))
    monkeypatch.setattr(module, 'scripting', NS(current_package=lambda: package,
                        kerning_pair_value=lambda kern, left, right: kern.get((left, right))))
    monkeypatch.setattr(module, 'kerning', NS(snapshot_kerning=lambda p, typed: snapshot,
                        write_kerning=lambda *args, **kw: writes.append((args, kw)) or True))
    monkeypatch.setattr(module, 'masters', NS(
        layer_contours=lambda layer: [[(layer.edges[0], 0, True), (layer.edges[1], 0, True),
                                       (layer.edges[1], 500, True), (layer.edges[0], 500, True)]],
        polygon=lambda points: [(x, y) for x, y, _ in points]))
    return NS(module=module, package=package, rows=rows, selection=selection, snapshot=snapshot, writes=writes, qt=studio_qt)


@pytest.mark.parametrize("group_record_exists", [False, True])
def test_steal_equalizes_measured_gaps(
    four_slots: Any, group_record_exists: bool
) -> None:
    key = (("AGroup", "groupMode"), ("VGroup", "groupMode"))
    if not group_record_exists:
        four_slots.snapshot.pairs["Regular"].pop(key)
    result = four_slots.module.run(250)
    assert result["value"] == 25, "Reference gap 150 - target gap 100 - 25 kerning"
    assert list(four_slots.writes[0][0][1]["Regular"].values()) == [25]
    assert next(iter(four_slots.writes[0][0][1]["Regular"])) == (
        ("AGroup", "groupMode"),
        ("VGroup", "groupMode"),
    )


@pytest.mark.parametrize("kind", ["group", "glyph", "mixed"])
def test_steal_computed_zero_removes_record(four_slots: Any, kind: str) -> None:
    four_slots.package.kerning = lambda master: NS(get=lambda pair: -50)
    key = (("AGroup", "groupMode"), ("VGroup", "groupMode"))
    if kind == "glyph":
        key = (("A", "glyphMode"), ("V", "glyphMode"))
    elif kind == "mixed":
        key = (("A", "glyphMode"), ("VGroup", "groupMode"))
    four_slots.snapshot.pairs["Regular"][key] = -70
    result = four_slots.module.run(250)
    assert result["value"] == 0
    assert four_slots.writes[0][0][1] == {"Regular": {key: None}}


def test_steal_open_contours_are_skipped_and_named(
    four_slots: Any, monkeypatch: Any
) -> None:
    four_slots.rows[0].layer.shapes[0].contours.append(NS(isTT=False, closed=False))
    masters = four_slots.module.masters
    original = masters.layer_contours
    monkeypatch.setattr(
        masters,
        "layer_contours",
        lambda layer: original(layer) * len(layer.shapes[0].contours),
    )
    result = four_slots.module.run(250)
    assert result["value"] == 25
    assert result["notices"] == ["A: skipped 1 open contour."]
    assert len(four_slots.writes) == 1


def test_steal_keeps_existing_target_exception(four_slots: Any) -> None:
    pair = (("A", "glyphMode"), ("V", "glyphMode"))
    four_slots.snapshot.pairs["Regular"][pair] = -40
    four_slots.module.run(250)
    assert next(iter(four_slots.writes[0][0][1]["Regular"])) == pair


@pytest.mark.parametrize("height", [-1, 501, float("nan"), float("inf")])
def test_steal_bad_height_or_no_crossing_refuses(
    four_slots: Any, height: float
) -> None:
    with pytest.raises(ValueError):
        four_slots.module.run(height)
    assert four_slots.writes == []


def test_steal_refuses_stale_geometry(four_slots: Any) -> None:
    tool = four_slots.module
    preview = tool.plan(250)
    four_slots.rows[0].layer.edges = (70, 440)
    with pytest.raises(ValueError, match="preview changed"):
        tool.write(preview)
    assert four_slots.writes == []


@pytest.mark.parametrize("failure", ["count", "gap", "block", "master"])
def test_steal_bad_selection_refuses(four_slots: Any, failure: str) -> None:
    if failure == "count":
        four_slots.selection.occurrences = tuple(four_slots.rows[:3])
    elif failure == "gap":
        four_slots.rows[3].index = 10
    elif failure == "block":
        four_slots.rows[3].block_id = 12
    else:
        four_slots.rows[3].layer.name = "Bold"
    with pytest.raises(ValueError):
        four_slots.module.run(250)
    assert four_slots.writes == []



def test_steal_transformed_components_and_quadratic_crossings(
    four_slots: Any, monkeypatch: Any
) -> None:
    class Point:
        def __init__(self, x: float, y: float) -> None:
            self.coords = (x, y)

        def x(self) -> float:
            return self.coords[0]

        def y(self) -> float:
            return self.coords[1]

    from fontlabapp.core.scripting import masters_api
    monkeypatch.setattr(four_slots.module, 'masters', masters_api())

    def layer(points: list, quadratic: bool, offset: float) -> Any:
        contour = NS(
            isTT=quadratic,
            closed=True,
            nodes=lambda: [NS(x=x, y=y, isOn=lambda on=on: on) for x, y, on in points],
        )
        transform = NS(
            isIdentity=lambda: False, map=lambda p: Point(p.x() + offset, p.y())
        )
        return NS(
            name="Regular",
            shapes=[NS(contours=[contour], transform=transform, isComponent=True)],
        )

    rectangle = layer(
        [(50, 0, True), (450, 0, True), (450, 500, True), (50, 500, True)], False, 100
    )
    tool = four_slots.module
    assert tool.extents(rectangle, 250) == (150, 550)
    assert tool.extents(rectangle, 500) == (150, 550), "Top flat edge must be included"
    assert tool.extents(rectangle, 0) == (150, 550), "Bottom flat edge must be included"
    arc = layer([(0, 0, True), (50, 100, False), (100, 0, True)], True, 0)
    left, right = tool.extents(arc, 25)
    assert 14 < left < 16 and 84 < right < 86
    assert tool.quadratic_cubics([]) == []
    implied = tool.quadratic_cubics([(0, 0, False), (100, 0, False)])
    assert implied[0] == (50, 0, True)
    arc.shapes[0].contours[0].closed = False
    notices = []
    rectangle.shapes.extend(arc.shapes)
    assert tool.extents(rectangle, 250, glyph_name="A", notices=notices) == (150, 550)
    assert notices == ["A: skipped 1 open contour."]
    with pytest.raises(ValueError, match="A.*No closed outline crossing"):
        tool.extents(arc, 25, glyph_name="A")



@pytest.mark.parametrize('problem', ['font', 'expected', 'context', 'width', 'reference', 'groups', 'structure', 'finite', 'deadline'])
def test_measurement_refuses_invalid_capture_before_any_write(four_slots, monkeypatch, problem):
    f = four_slots
    if problem == 'font':
        monkeypatch.setattr(f.module.scripting, 'current_package', lambda: None)
    elif problem == 'context':
        f.selection.context = (7, 'Regular', 'font')
    elif problem == 'width':
        f.rows[0].layer.advanceWidth = float('nan')
    elif problem == 'reference':
        f.package.kerning = lambda master: NS(get=lambda pair: float('inf'))
    elif problem == 'groups':
        f.snapshot.groups['Regular']['another'] = (('A',), 'KernLeft')
    elif problem == 'structure':
        monkeypatch.setattr(f.module.masters, 'layer_contours', lambda layer: [])
    elif problem == 'finite':
        monkeypatch.setattr(f.module.masters, 'polygon', lambda points: [(float('nan'), 0)])
    elif problem == 'deadline':
        times = iter([0, 0, 5])
        monkeypatch.setattr(f.module, 'monotonic', lambda: next(times))
    with pytest.raises((ValueError, TimeoutError)):
        f.module.plan(250, 99 if problem == 'expected' else 7)
    assert not f.writes


def test_write_partial_failure_preserves_undo_guidance(four_slots, monkeypatch):
    f = four_slots
    preview = f.module.plan(250)
    def fail(*args, **kw):
        raise RuntimeError('native write failed')
    monkeypatch.setattr(f.module.kerning, 'write_kerning', fail)
    with pytest.raises(RuntimeError, match='use Edit > Undo'):
        f.module.write(preview)


def test_default_height_uses_shown_master_or_current_fallback(four_slots, monkeypatch):
    f = four_slots
    calls = []
    monkeypatch.setitem(sys.modules, 'fontlab', NS(FontMetrics=lambda package, master: calls.append(master) or NS(xHeight=550)))
    assert f.module.default_height(None) == 0
    f.package.master = 'Bold'
    assert f.module.default_height(f.package) == 275 and calls == ['Regular']
    f.rows[0].layer.name = 'Auxiliary'
    assert f.module.default_height(f.package) == 275 and calls[-1] == 'Bold'
    f.selection.occurrences = ()
    assert f.module.default_height(f.package) == 275 and calls[-1] == 'Bold'
    f.selection.context = (99, 'Bold', 'editor')
    with pytest.raises(ValueError, match='changed'):
        f.module.default_height(f.package)
