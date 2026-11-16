# this_file: tests/test_studio_contours.py
"""``fontlabapp.studios._contours`` (Scriptmix TODO:46–47) and ``fontlabapp.core.outline``.

The five copied ``spans`` helpers, the four contour-selection scaffolds and
the three selection planners now live once in ``_contours``; these tests pin
their behaviour (errors included) without FontLab.
"""

import importlib
import math
import sys
from types import SimpleNamespace

import pytest
from _contour_fakes import NContour, NLayer, NNode, NShape, square

from fontlabapp.core import outline


class _Lazy:
    """``c.name`` imports ``fontlabapp.studios._contours`` on use, so collection loads no studio child."""

    def __getattr__(self, name):
        return getattr(importlib.import_module("fontlabapp.studios._contours"), name)


c = _Lazy()


@pytest.fixture(autouse=True)
def _unload_studios():
    yield
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


def layer_of(*shapes, locked=False):
    lay = NLayer("A", "Regular", list(shapes), log=[])
    object.__setattr__(lay, "isLocked", locked)
    object.__setattr__(lay, "name", "Regular")
    return lay


def rotate(angle):
    r = math.radians(angle)
    return (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0.0, 0.0)


# TODO:47 spans -------------------------------------------------------------------
def test_node_spans_when_lines_and_cubic_then_split_and_wraps():
    nodes = [(0, True), (1, False), (2, False), (3, True), (4, True)]
    got = c.node_spans(nodes, lambda n: n[1])
    assert [[n[0] for n in s] for s in got] == [[0, 1, 2, 3], [3, 4], [4, 0]]


def test_node_spans_when_quadratic_segment_then_value_error():
    with pytest.raises(ValueError, match="unsupported segment"):
        c.node_spans([(0, True), (1, False), (2, True)], lambda n: n[1])


def test_spans_when_open_or_tt_then_refused_else_native_segments():
    log = []
    assert len(c.spans(square(log))) == 4
    with pytest.raises(ValueError, match="closed PostScript"):
        c.spans(NContour(square(log).nodes(), closed=False))
    with pytest.raises(ValueError, match="closed PostScript"):
        c.spans(NContour(square(log).nodes(), tt=True))


# TODO:46 scaffolds -------------------------------------------------------------
def test_selected_contours_when_selection_then_only_selected_own_contours():
    log = []
    picked, other = square(log, selected=(0,)), square(log)
    shape = NShape([picked, other], log=log)
    found = c.selected_contours(layer_of(shape, NShape(component=True, log=log)))
    assert [(s, k) for s, k, _ in found] == [(shape, picked)]


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda log: (NShape([square(log, selected=(0,))], locked=True, log=log), False), "Unlock"),
        (lambda log: (NShape([square(log, selected=(0,))], log=log), True), "Unlock"),
        (lambda log: (NShape([square(log, selected=(0,))], refs=2, log=log), False), "shared"),
    ],
)
def test_selected_contours_when_locked_or_shared_then_refused(make, message):
    shape, locked = make([])
    with pytest.raises(ValueError, match=message):
        c.selected_contours(layer_of(shape, locked=locked))


def test_selected_contours_when_transform_or_nan_then_refused():
    log = []
    contour = square(log, selected=(0,))
    contour.transform = SimpleNamespace(m11=lambda: 2.0, m12=lambda: 0.0, m21=lambda: 0.0, m22=lambda: 1.0,
                                        dx=lambda: 0.0, dy=lambda: 0.0)  # fmt: skip
    with pytest.raises(ValueError, match="Bake"):
        c.selected_contours(layer_of(NShape([contour], log=log)))
    bad = NContour([NNode(math.nan, 0, True, selected=True, log=log)])
    with pytest.raises(ValueError, match="non-finite"):
        c.selected_contours(layer_of(NShape([bad], log=log)))


def test_write_and_check_moves_when_written_then_pass_else_runtime_error():
    log = []
    node = NNode(0, 0, True, log=log)
    c.write_moves([(node, 10, 20, True), (node, 10, 20, None)])
    assert (node.x, node.y, node.smooth) == (10, 20, True)
    lay = layer_of()
    c.check_moves(lay, [(node, 10.4, 20, True)])
    with pytest.raises(RuntimeError, match="Regular: a node differs"):
        c.check_moves(lay, [(node, 11, 20, None)])
    with pytest.raises(RuntimeError):
        c.check_moves(lay, [(node, 10, 20, False)])


def test_chosen_masters_when_all_or_selection_then_names_and_pairs():
    assert c.chosen_masters(["R", "B"], True) == (["R", "B"], None)
    names, pairs = c.chosen_masters(["R", "B"], False, [(1, "A", "B"), (1, "C", "R"), (1, "A", "R")], 1)
    assert names == ["B", "R"] and pairs == {("A", "B"), ("C", "R"), ("A", "R")}
    with pytest.raises(ValueError, match="another font"):
        c.chosen_masters(["R"], False, [(2, "A", "R")], 1)


# TODO:46 planners ----------------------------------------------------------------
def test_selection_matrix_when_finite_then_about_centre_else_error():
    m = c.selection_matrix(180, (50, 50), rotate)
    x, y = m[0] * 0 + m[2] * 0 + m[4], m[1] * 0 + m[3] * 0 + m[5]
    assert (round(x, 6), round(y, 6)) == (100, 100)
    with pytest.raises(ValueError, match="finite"):
        c.selection_matrix(math.inf, (0, 0), rotate)


def test_selection_changes_when_nodes_and_component_then_one_change_and_writes(monkeypatch):
    log = []
    contour = square(log, selected=(0, 1, 2, 3))
    comp = NShape(component=True, selected=True, box=(0, 0, 100, 100), log=log)
    lay = layer_of(NShape([contour], log=log), comp)
    changes = c.selection_changes(lay, 180, rotate)
    assert len(changes) == 1 and changes[0].old == "4 nodes, 1 components"
    moves, placed = changes[0].edit
    assert len(moves) == 4 and placed[0][0] is comp
    made = []
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=SimpleNamespace(
        QTransform=lambda *m: made.append(m) or SimpleNamespace(**dict(zip(
            ("m11", "m12", "m21", "m22", "dx", "dy"), [lambda v=v: v for v in m], strict=True))))))  # fmt: skip
    c.write_selection([changes[0].edit])
    assert made and ("changed",) in [e[:1] for e in log] or made
    c.check_selection(lay, [changes[0].edit])
    comp.transform = None
    with pytest.raises(RuntimeError, match="Component placement"):
        c.check_selection(lay, [changes[0].edit])


def test_selection_changes_when_nothing_or_identity_then_empty():
    log = []
    assert c.selection_changes(layer_of(NShape([square(log)], log=log)), 90, rotate) == []
    lay = layer_of(NShape([square(log, selected=(0,))], log=log))
    assert c.selection_changes(lay, 0, rotate) == []
    locked = NShape(component=True, selected=True, locked=True, box=(0, 0, 1, 1), log=log)
    with pytest.raises(ValueError, match="component"):
        c.selection_changes(layer_of(locked), 90, rotate)


# core.outline --------------------------------------------------------------------
def test_merged_copy_when_fontgate_injected_then_converted_and_merged():
    calls = []

    class Copy:
        contours = [SimpleNamespace(countNodes=lambda: 8), SimpleNamespace(countNodes=lambda: 4)]

        def removeOverlap(self):
            calls.append("merge")

    shape = SimpleNamespace(convertToFgShape=lambda result: calls.append("convert"))
    copy = outline.merged_copy(shape, fontgate=SimpleNamespace(fgShape=Copy))
    assert calls == ["convert", "merge"] and outline.node_counts(copy) == (4, 8)


def test_font_info_when_dict_then_returned_else_error(monkeypatch):
    monkeypatch.setattr(outline.scripting, "font_id", lambda package: 7)
    seen = []
    fontpr = SimpleNamespace(call=lambda name, **kw: seen.append((name, kw)) or {"masters": []})
    assert outline.font_info(object(), fontpr=fontpr) == {"masters": []}
    assert seen == [("get_font_info", {"font_id": 7})]
    with pytest.raises(ValueError, match="font info"):
        outline.font_info(object(), fontpr=SimpleNamespace(call=lambda name, **kw: "nope"))


def test_master_measures_when_record_then_metrics_and_stems_else_errors():
    record = {"name": "Bold", "ascender": 750, "capsHeight": 700, "xHeight": 500, "descender": -250,
              "fontStemsH": [{"value": 80}], "fontStemsV": [{"value": 120}, {"value": 110}]}  # fmt: skip
    data = {"masters": [{"fontMaster": record}, {"fontMaster": {"name": "Light"}}]}
    assert outline.master_measures(data, "Bold#2") == ((750, 700, 500, -250), (80,), (120, 110))
    assert outline.master_measures(data, "Light") == ((0, 0, 0, 0), (), ())
    with pytest.raises(ValueError, match="domain"):
        outline.master_measures({}, "Bold")
    with pytest.raises(ValueError, match="no unique"):
        outline.master_measures(data, "Black")
    broken = {"masters": [{"fontMaster": {"name": "Bold", "fontStemsH": [3]}}]}
    with pytest.raises(ValueError, match="stem list"):
        outline.master_measures(broken, "Bold")
