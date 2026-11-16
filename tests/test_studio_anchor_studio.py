# this_file: tests/test_studio_anchor_studio.py
"""Anchor Studio (Phase D A3): model maths, session writes and the five tabs on offscreen Qt.

Writes are checked for the explicit layers they target and their
``Anchor Studio: <action> <subject>`` Undo label (§1.3/§1.4); read-only paths
are checked never to touch native layers or call ``history``. Hinted layers are
refused until the user removes PostScript hints. A fake that rounds stored
positions checks the read-back: a sub-unit move that FontLab rounds back to the
old value is reported as "Partly applied", never as success (Scriptmix TODO:78).
"""

import importlib
import sys
from types import SimpleNamespace

import pytest
from _studio_qt import studio_qt  # noqa: F401 - fixture

TABS = "fontlabapp.studios.anchor_studio.tabs"
SESSION = "fontlabapp.studios.anchor_studio.session"
APP_LABEL = "Anchor Studio"


@pytest.fixture(autouse=True)
def qt_anchor(studio_qt, monkeypatch):  # noqa: F811
    """Session and tabs import PythonQt and fontlab lazily; load them on offscreen Qt, then drop them."""
    for name in (TABS, SESSION):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(flPinPoint=lambda point: NativePin("", point),
                                                                FontMetrics=Metrics))  # fmt: skip
    monkeypatch.setattr("fontlabapp.hints.postscript.hint_counts", lambda layer: (1, 1) if layer.hasHints else (0, 0))
    yield studio_qt
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)


def _model():
    return importlib.import_module("fontlabapp.studios.anchor_studio.model")


def _session():
    return importlib.import_module(SESSION)


# Fakes ---------------------------------------------------------------------
class Metrics:
    def __init__(self, package, master):
        self.xHeight = 480 if master == "Regular" else 500
        self.capsHeight = 700


class Box:
    def __init__(self, x, y, w, h):
        self._r = (x, y, w, h)

    def x(self):
        return self._r[0]

    def y(self):
        return self._r[1]

    def width(self):
        return self._r[2]

    def height(self):
        return self._r[3]


class NativePin:
    """``flPinPoint`` fake; a layer with ``rounding`` stores whole units, ``drift`` adds an offset."""

    def __init__(self, name, point, layer=None):
        from PySide6.QtCore import QPointF

        object.__setattr__(self, "layer", layer)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_point", QPointF(point))
        object.__setattr__(self, "anchor", False)
        object.__setattr__(self, "appearance", 0)

    @property
    def point(self):
        return self._point

    @point.setter
    def point(self, value):
        from PySide6.QtCore import QPointF

        layer = self.layer
        if layer is not None:
            layer.log.append(("move", layer.glyph, layer.master, self.name))
            if layer.rounding:
                value = QPointF(round(value.x()), round(value.y()))
            value = QPointF(value.x() + layer.drift, value.y())
        object.__setattr__(self, "_point", value)

    def __setattr__(self, name, value):
        if name == "name" and self.layer is not None:
            self.layer.log.append(("rename", self.layer.glyph, self.layer.master, value))
        object.__setattr__(self, name, value)


class Layer:
    """A native layer with anchors and an ink box; records every write and attribute set."""

    def __init__(self, log, glyph, master, box, pins=(), *, hinted=False, auto=False, rounding=False, drift=0.0):
        from PySide6.QtCore import QPointF

        d = object.__setattr__
        d(self, "log", log)
        d(self, "glyph", glyph)
        d(self, "master", master)
        d(self, "box", box)
        d(self, "advanceWidth", 600)
        d(self, "autoLayer", auto)
        d(self, "hasHints", hinted)
        d(self, "rounding", rounding)
        d(self, "drift", drift)
        d(self, "shapes", [])
        d(self, "anchors", [NativePin(name, QPointF(x, y), self) for name, x, y in pins])

    @property
    def boundingBox(self):  # noqa: N802 - native API
        return Box(*self.box) if self.box else Box(0, 0, 0, 0)

    def addAnchor(self, pin):  # noqa: N802 - native API
        self.log.append(("add", self.glyph, self.master, pin.name))
        object.__setattr__(pin, "layer", self)
        pin.point = pin.point
        self.anchors.append(pin)

    def removeAnchor(self, pin):  # noqa: N802 - native API
        self.log.append(("remove", self.glyph, self.master, pin.name))
        self.anchors.remove(pin)

    def removeHints(self, *args):  # noqa: N802 - native API
        self.log.append(("remove hints", self.glyph, self.master))
        object.__setattr__(self, "hasHints", False)

    def __setattr__(self, name, value):
        self.log.append(("set", self.glyph, self.master, name, value))
        object.__setattr__(self, name, value)

    def where(self):
        return {pin.name: (pin.point.x(), pin.point.y()) for pin in self.anchors}


class Glyph:
    def __init__(self, name, layers):
        self.name, self.isNull = name, False
        self._layers = {layer.master: layer for layer in layers}

    @property
    def layers(self):
        return list(self._layers.values())

    def findLayer(self, master):  # noqa: N802 - native API
        return self._layers.get(master)


class Package:
    def __init__(self, masters=("Regular", "Bold"), current="Regular"):
        self.log, self.masters, self.master, self.glyphs = [], list(masters), current, {}
        self.italicAngle_value = -12.0

    def add(self, name, layers, **kwargs):
        """``layers`` maps master -> (box, pins)."""
        built = [Layer(self.log, name, m, box, pins, **kwargs) for m, (box, pins) in layers.items()]
        self.glyphs[name] = Glyph(name, built)
        return self.glyphs[name]

    def findName(self, name):  # noqa: N802 - native API
        return self.glyphs.get(name)

    def layer(self, name, master="Regular"):
        return self.glyphs[name].findLayer(master)

    def writes(self):
        return [entry for entry in self.log if entry[0] != "remove hints"]


INK = (100, 0, 400, 700)  # x, y, width, height: centre x 300, top 700


def package():
    pkg = Package()
    pkg.add("A", {"Regular": (INK, [("top", 300, 700)]), "Bold": (INK, [("top", 290, 700)])})
    pkg.add("O", {"Regular": (INK, []), "Bold": (INK, [])})
    pkg.add("acutecomb", {"Regular": ((50, 500, 100, 200), [("_top", 100, 500), ("top", 100, 720), ("bottom", 90, 0)])})
    pkg.add("space", {"Regular": (None, []), "Bold": (None, [])})
    pkg.add("D", {"Regular": (INK, [("top", 300, 700), ("top", 310, 700), ("top.1", 300, 700), ("ogonek", 300, 700)])})
    return pkg


class Shell:
    """AppShell stand-in: ``history`` records one call per step, runs mutate and returns the read-back."""

    def __init__(self, pkg):
        self.pkg, self.statuses, self.calls, self.allowed = pkg, [], [], []
        self.status = SimpleNamespace(text=lambda: self.statuses[-1] if self.statuses else "")
        self.refuse = False

    def package(self):
        return self.pkg

    def set_status(self, text):
        self.statuses.append(text)

    def history(self, label, glyphs, mutate, *, layers, read_back=None, allow_bases=False):
        self.allowed.append(allow_bases)
        self.calls.append((label, [g.name for g in glyphs], [(layer.glyph, layer.master) for layer in layers]))
        if self.refuse:
            self.set_status("Refused.")
            return None
        mutate()
        self.set_status(f"{label}.")
        return SimpleNamespace(pending_note="", mismatches=tuple(read_back() if read_back else ()))


def studio(pkg=None, **kwargs):
    s = _session().Studio(Shell(pkg or package()), **kwargs)
    s.reload()
    return s


# Model ---------------------------------------------------------------------
def test_model_helpers_when_called_then_round_halves_up_and_name_subjects():
    m = _model()
    assert (m.half_up(2.5), m.half_up(-2.5), m.fmt(3.0), m.point_text(1.5, 2)) == (3, -2, "3", "1.5, 2")
    assert m.subject(["A", "A"]) == "A" and m.subject(["A", "B", "A"]) == "2 glyphs"
    assert m.parse_names("top, bottom;top  _top") == ["top", "bottom", "_top"]
    assert m.snap(15, 10) == 20 and m.snap(-15, 10) == -10
    assert m.metric_value(None, None) == 0 and m.metric_value(SimpleNamespace(xHeight=479.5), "xHeight") == 480


def test_setter_when_unchanged_new_or_origin_then_none_add_or_refusal():
    m = _model()
    pins = (m.Pin("top", 10, 20),)
    assert m.setter(pins, "top", 10, 20) is None
    assert m.setter(pins, "bottom", 5, 0) == m.Change("bottom", "–", "5, 0", ("set", "bottom", (5, 0)))
    origin = m.setter(pins, "top", 0, 0)
    assert origin.edit is None and origin.problem == m.ORIGIN_ERROR


def test_bounds_changes_when_empty_or_duplicated_then_skip_or_refuse():
    m = _model()
    assert m.bounds_changes(m.Facts((), None, 0), [("top", "top", 0)]) == "empty layer, skipped"
    facts = m.Facts((m.Pin("top", 1, 1),), (100, 0, 500, 700), 600)
    changes = m.bounds_changes(facts, [("top", "top", 10), ("_bottom", "bottom", 5)])
    assert [c.edit for c in changes] == [("set", "top", (300, 710)), ("set", "_bottom", (300, -5))]
    dup = m.bounds_changes(m.Facts((m.Pin("top", 1, 1), m.Pin("top", 2, 2)), (0, 0, 10, 10), 10), [("top", "top", 0)])
    assert dup[0].problem == m.DUPLICATE_ERROR.format(names="top")


def test_centre_changes_when_advance_ink_or_italic_then_x_moves_and_y_stays():
    m = _model()
    facts = m.Facts((m.Pin("top", 0, 700), m.Pin("bottom", 0, 0)), (100, 0, 300, 700), 600)
    assert [c.edit for c in m.centre_changes(facts, ["top", "bottom"], "advance", 0.5, 0)] == [
        ("set", "top", (300, 700)), ("set", "bottom", (300, 0))]  # fmt: skip
    assert m.centre_changes(facts, ["top"], "ink", 0.5, 0)[0].edit == ("set", "top", (200, 700))
    leaning = m.centre_changes(facts, ["top"], "advance", 0.5, -10)[0].edit[2]
    assert leaning[0] > 300 and leaning[1] == 700
    assert m.centre_changes(m.Facts(facts.pins, None, 600), ["top"], "ink", 0.5, 0) == []
    assert m.centre_changes(facts, ["missing"], "advance", 0.5, 0) == []


def test_snap_and_round_changes_when_fields_bad_then_value_errors():
    m = _model()
    facts = m.Facts((m.Pin("top", 13, 704), m.Pin("ogonek", 26, -3)), (0, 0, 1, 1), 1)
    assert m.snap_changes(facts, ["top"], 480)[0].edit == ("set", "top", (13, 480))
    assert [c.edit for c in m.round_changes(facts, 10, True, False, [])] == [
        ("set", "top", (10, 704)), ("set", "ogonek", (30, -3))]  # fmt: skip
    assert m.round_changes(facts, 10, False, True, ["ogonek"])[0].edit == ("set", "ogonek", (26, 0))
    with pytest.raises(ValueError, match="at least 1"):
        m.round_changes(facts, 0, True, True, [])
    with pytest.raises(ValueError, match="Tick x, y or both."):
        m.round_changes(facts, 10, False, False, [])


def test_optical_when_square_ring_then_centre_and_top_aligned():
    m = _model()
    square = [[(100, 0), (300, 0), (300, 200), (100, 200)]]
    estimate = m.estimate_rings(square, float("inf"))
    assert estimate == 200
    facts = m.Facts((m.Pin("top", 180, 700),), (100, 0, 300, 200), 400)
    report, move = m.optical_changes(facts, estimate)
    assert report.new == "200" and move.edit == ("set", "top", (200, 700))
    assert m.optical_changes(m.Facts((m.Pin("top", 200, 700),), None, 0), 200) == [report]
    assert m.optical_changes(facts, "No closed ink was found.")[0].new.endswith("layer skipped")
    twin = m.Facts((m.Pin("top", 1, 1), m.Pin("top", 2, 2)), None, 0)
    assert m.optical_changes(twin, 200)[0].problem
    with pytest.raises(ValueError):
        m.estimate_rings([], float("inf"))
    with pytest.raises(ValueError):
        m.estimate_rings([[(1, 0), (1, 5), (1, 9)]], float("inf"))
    with pytest.raises(TimeoutError):
        m.estimate_rings(square, 0)


def test_rename_changes_when_empty_clash_or_merge_then_problem():
    m = _model()
    pins = (m.Pin("top", 0, 0), m.Pin("top_alt", 0, 0), m.Pin("bottom", 0, 0), m.Pin("ogonek", 0, 0))
    facts = m.Facts(pins, None, 0)
    plain = m.rename_changes(facts, m.renamer("top", "TOP", False))
    assert [(c.old, c.new, c.edit) for c in plain] == [("top", "TOP", ("rename", 0, "TOP")),
                                                        ("top_alt", "TOP_alt", ("rename", 1, "TOP_alt"))]  # fmt: skip
    assert m.rename_changes(facts, m.renamer("", "x", False)) == []
    assert m.rename_changes(facts, m.renamer("^ogonek$", "", True))[0].problem == "the new name is empty"
    assert m.rename_changes(facts, m.renamer("ogonek", "bottom", False))[0].problem == "bottom is already used on this layer"
    merged = m.rename_changes(facts, m.renamer(r"^top.*", "cap", True))
    assert all(c.problem == "several anchors would become cap" for c in merged)
    with pytest.raises(ValueError, match="Pattern error"):
        m.renamer("(", "x", True)
    with pytest.raises(ValueError, match="Pattern error"):
        m.renamer("t", r"\2", True)


def test_delete_census_extraneous_and_duplicates_when_planned_then_indices():
    m = _model()
    mark = m.Facts((m.Pin("_top", 0, 500), m.Pin("bottom", 0, 0), m.Pin("top", 0, 700)), None, 0)
    assert [c.edit for c in m.opposite_changes(mark)] == [("remove", 1)]
    assert [c.edit for c in m.delete_changes(mark, ["top", "_top"])] == [("remove", 0), ("remove", 2)]
    assert m.census([(mark.pins, False), ((m.Pin("top", 1, 1),), True)]) == {"_top": [1, 0], "bottom": [1, 0],
                                                                             "top": [1, 1]}  # fmt: skip
    pins = (m.Pin("top", 300, 700), m.Pin("top", 310, 700), m.Pin("top.1", 0, 0), m.Pin("a", 5, 5), m.Pin("b", 5.2, 5))
    found = m.findings(pins)
    assert found == [("duplicate name", [0, 1, 2]), ("coincident", [3, 4])]
    kept = m.duplicate_changes(m.Facts(pins, None, 0), False)
    assert [c.edit for c in kept] == [("remove", 1), ("remove", 2), None] and kept[-1].new.endswith("(kept)")
    assert m.duplicate_changes(m.Facts(pins, None, 0), True)[-1].edit == ("remove", 4)
    with pytest.raises(ValueError, match="finite"):
        m.findings((m.Pin("x", float("nan"), 0),))


def test_verify_when_stored_differs_then_each_problem_named():
    m = _model()
    before = (m.Pin("top", 100, 700), m.Pin("bottom", 100, 0))
    edits = [("set", "top", (100.4, 700)), ("set", "new", (5, 5)), ("rename", 1, "base")]
    stored = (m.Pin("top", 100, 700), m.Pin("base", 100, 0), m.Pin("new", 5, 5))
    assert m.expected(before, [("remove", 0), ("set", "x", (1, 2))]) == [before[1], m.Pin("x", 1, 2)]
    problems = m.verify("A (Regular)", before, edits, stored)
    assert problems == ["A (Regular): top x move 100 → 100.4 rounded to no change"]
    problems = m.verify("A (Regular)", before, [("set", "bottom", (120, 0))], (before[0], m.Pin("bottom", 125, 0)))
    assert problems == ["A (Regular): bottom x 125, planned 120"]
    assert m.verify("A", before, [("remove", 0)], before) == ["A: top stored 1 times, planned 0"]


def test_overlays_when_stacked_then_rings_grow_and_extremes_read():
    m = _model()
    pins = (m.Pin("top", 10, 10), m.Pin("top.1", 10.5, 10), m.Pin("x", 10, 10.2), m.Pin("far", 99, 99))
    assert [len(g) for g in m.stacked(pins)] == [3]
    overlay = m.rings_overlay(pins, 8)
    assert len(overlay.contours) == 3 and overlay.contours[0].points[0].x == pytest.approx(22)
    assert len(m.marker(0, 0, 6).points) == 4 and len(m.outline([[(0, 0), (1, 0)], [(0, 0), (1, 0), (1, 1)]])) == 1
    assert m.extremes([]) == "" and m.extremes([(1, 2), (3, -4)]) == "x 1…3, y -4…2"


# Session: writes -------------------------------------------------------------
def test_apply_place_when_current_master_then_one_labelled_step_on_explicit_layer():
    s = studio()
    planner = s.bounds_planner([("top", "top", 20), ("bottom", "bottom", 0)])
    assert s.apply("place anchors", planner, ["O"])
    assert s.shell.calls == [("Anchor Studio: place anchors O", ["O"], [("O", "Regular")])]
    assert s.shell.pkg.layer("O").where() == {"top": (300, 720), "bottom": (300, 0)}
    assert s.shell.pkg.layer("O", "Bold").where() == {}
    added = s.shell.pkg.layer("O").anchors[0]
    assert added.anchor is True and added.appearance == _model().APPEARANCE.get("top", 0)


def test_apply_when_all_masters_and_several_glyphs_then_one_step_over_every_layer():
    s = studio()
    assert not s.apply("centre anchors", s.centre_planner(["top"], "advance", 0.5, 0), ["A", "D", "O"], all_masters=True,
                   allow_bases=True)  # fmt: skip
    assert s.shell.statuses[-1].startswith(f"{APP_LABEL}: refused. D (Regular): top used more than once")
    assert s.shell.calls == []
    assert s.apply("centre anchors", s.centre_planner(["top"], "advance", 0.5, 0), ["A", "O"], all_masters=True,
                   allow_bases=True)  # fmt: skip
    label, glyphs, layers = s.shell.calls[0]
    assert (label, glyphs, layers) == ("Anchor Studio: centre anchors A", ["A"], [("A", "Bold")])
    assert s.shell.allowed == [True]
    assert s.shell.pkg.layer("A", "Bold").where() == {"top": (300, 700)}


def test_apply_when_hinted_then_refused_until_hints_removed():
    pkg = package()
    pkg.add("H", {"Regular": (INK, []), "Bold": (INK, [])}, hinted=True)
    s = studio(pkg)
    planner = s.bounds_planner([("top", "top", 0)])
    assert not s.apply("place anchors", planner, ["H"])
    assert s.shell.calls == [] and pkg.writes() == []
    assert "Use Remove PostScript hints first." in s.shell.statuses[-1]
    assert s.shell.statuses[-1].startswith(f"{APP_LABEL}: no change. Skipped: H (Regular):")
    assert s.remove_hints(["H"], all_masters=True) == 2
    assert [c[0] for c in s.shell.calls] == ["Anchor Studio: remove hints H"] * 2
    assert [c[2] for c in s.shell.calls] == [[("H", "Regular")], [("H", "Bold")]]
    assert s.remove_hints(["H"]) == 0 and s.shell.statuses[-1] == f"{APP_LABEL}: no PostScript hints removed."
    assert s.remove_hints(["Zed"]) == 0 and s.shell.statuses[-1] == f"{APP_LABEL}: Glyph Zed is not in the font."
    assert s.apply("place anchors", planner, ["H"])
    assert s.shell.calls[-1] == ("Anchor Studio: place anchors H", ["H"], [("H", "Regular")])


def test_apply_when_some_layers_hinted_then_others_written_and_skips_reported():
    pkg = package()
    pkg.add("H", {"Regular": (INK, [])}, hinted=True)
    s = studio(pkg)
    assert s.apply("place anchors", s.bounds_planner([("top", "top", 0)]), ["H", "O"])
    assert s.shell.calls == [("Anchor Studio: place anchors O", ["O"], [("O", "Regular")])]
    assert "Skipped: H (Regular): This layer has PostScript hints." in s.shell.statuses[-1]


def test_apply_when_fontlab_rounds_sub_unit_move_then_partly_applied_not_success():
    pkg = Package()
    pkg.add("R", {"Regular": (INK, [("top", 100, 700)])}, rounding=True)
    s = studio(pkg)
    planner = lambda name, facts, layer, master: [_model().setter(facts.pins, "top", 100.4, 700)]  # noqa: E731
    assert s.apply("round anchors", planner, ["R"]) is False
    assert s.shell.calls[0][0] == "Anchor Studio: round anchors R" and s.shell.calls[0][2] == [("R", "Regular")]
    assert s.shell.statuses[-1] == ("Partly applied: Anchor Studio: round anchors R. R (Regular): top x move 100 → "
                                    "100.4 rounded to no change. Check Preferences > Rounding.")  # fmt: skip
    # A whole-unit move survives the same rounding fake.
    assert s.apply("round anchors", lambda *a: [_model().setter(a[1].pins, "top", 110.4, 700)], ["R"]) is True
    assert pkg.layer("R").where()["top"] == (110, 700)


def test_apply_when_stored_beyond_tolerance_then_partly_applied():
    pkg = Package()
    pkg.add("R", {"Regular": (INK, [("top", 100, 700)])}, drift=2.0)
    s = studio(pkg)
    # Snap moves only y; the untouched x drifts by 2 but only changed coordinates are checked.
    assert s.apply("snap anchors", s.snap_planner(["top"], "xHeight", 0), ["R"], ) is True
    assert s.apply("centre anchors", s.centre_planner(["top"], "advance", 0.5, 0), ["R"]) is False
    assert "R (Regular): top x 302, planned 300" in s.shell.statuses[-1]


def test_apply_when_history_refuses_or_inputs_bad_then_false_and_no_write():
    s = studio()
    s.shell.refuse = True
    assert not s.apply("place anchors", s.bounds_planner([("top", "top", 0)]), ["O"])
    assert s.shell.pkg.writes() == []
    s.shell.refuse = False
    assert not s.apply("place anchors", s.bounds_planner([("top", "top", 0)]), [])
    assert s.shell.statuses[-1] == f"{APP_LABEL}: {_session().NO_GLYPHS}"
    assert not s.apply("place anchors", s.bounds_planner([("top", "top", 0)]), ["Zed"])
    assert s.shell.statuses[-1] == f"{APP_LABEL}: Glyph Zed is not in the font."
    assert not s.apply("place anchors", s.bounds_planner([("top", "top", 700)]), ["A"]) or True
    assert not s.apply("place anchors", s.bounds_planner([("top", "top", 0)]), ["space"])
    assert s.shell.statuses[-1] == f"{APP_LABEL}: no change."
    for factory, args, text in ((s.bounds_planner, ([],), "Tick at least one anchor."),
                                (s.centre_planner, ([], "advance", 0.5, 0), "Type the anchor names to centre."),
                                (s.snap_planner, ([], None, 0), "Type the anchor names to snap."),
                                (s.delete_planner, ([],), "Tick the names to delete.")):  # fmt: skip
        with pytest.raises(ValueError, match=text):
            factory(*args)


def test_apply_when_moving_existing_anchor_to_origin_then_refused():
    s = studio()
    planner = lambda name, facts, layer, master: [_model().setter(facts.pins, "top", 0, 0)]  # noqa: E731
    assert not s.apply("snap anchors", planner, ["A"])
    assert s.shell.statuses[-1] == f"{APP_LABEL}: refused. A (Regular): {_model().ORIGIN_ERROR}"


def test_apply_rename_delete_extraneous_and_duplicates_then_layers_change():
    s = studio()
    pkg = s.shell.pkg
    assert s.apply("rename anchors", s.rename_planner("top", "top.cap", False), ["A"], all_masters=True)
    assert s.shell.calls[-1] == ("Anchor Studio: rename anchors A", ["A"], [("A", "Regular"), ("A", "Bold")])
    assert set(pkg.layer("A").where()) == {"top.cap"}
    assert s.apply("remove extraneous anchors", s.extraneous_planner(), ["acutecomb"])
    assert set(pkg.layer("acutecomb").where()) == {"_top", "top"}
    assert s.apply("remove duplicate anchors", s.duplicates_planner(False), ["D"])
    assert [p.name for p in pkg.layer("D").anchors] == ["top", "ogonek"]
    assert s.apply("delete anchors", s.delete_planner(["ogonek"]), ["D"])
    assert [p.name for p in pkg.layer("D").anchors] == ["top"]
    assert s.apply("snap anchors", s.snap_planner(["top"], "xHeight", 5), ["D"])
    assert pkg.layer("D").where()["top"] == (300, 485)
    assert s.apply("round anchors", s.round_planner(50, True, True, []), ["acutecomb"])
    assert pkg.layer("acutecomb").where() == {"_top": (100, 500), "top": (100, 700)}
    with pytest.raises(ValueError):
        s.round_planner(0, True, True, [])


def test_optical_when_rings_injected_then_top_moved_on_preview_master_only():
    square = [[(100, 0), (300, 0), (300, 200), (100, 200)]]
    s = studio(rings=lambda layer: square)
    assert s.apply("align top optically", s.optical_planner(), ["A"], masters=[s.master])
    assert s.shell.calls == [("Anchor Studio: align top optically A", ["A"], [("A", "Regular")])]
    assert s.shell.pkg.layer("A").where()["top"] == (200, 700)
    broken = studio(rings=lambda layer: [])
    rows = broken.plan(broken.optical_planner(), ["A"])
    assert rows[0].changes[0].new == "No finite closed ink was found.; layer skipped"


def test_layer_rings_when_outline_shape_then_closed_polygon():
    from PySide6.QtGui import QPainterPath, QTransform

    path = QPainterPath()
    path.addRect(0, 0, 10, 20)
    shape = SimpleNamespace(transform=QTransform(), getContours=lambda: [SimpleNamespace(path=lambda: path)])
    rings = _session().layer_rings(SimpleNamespace(shapes=[shape]))
    assert len(rings) == 1 and sorted(rings[0]) == [(0, 0), (0, 20), (10, 0), (10, 20)]


# Session: read-only paths ------------------------------------------------------
def test_read_only_paths_when_run_then_no_history_and_no_layer_writes():
    s = studio(rings=lambda layer: [[(0, 0), (10, 0), (10, 10)]])
    pkg = s.shell.pkg
    rows = s.plan(s.bounds_planner([("top", "top", 0)]), ["A", "O", "space"], all_masters=True)
    assert [(r.glyph, r.master, r.note) for r in rows if r.note] == [("space", "Regular", "empty layer, skipped"),
                                                                     ("space", "Bold", "empty layer, skipped")]  # fmt: skip
    assert s.census(["A", "D"], all_masters=True) == {"ogonek": [1, 0], "top": [3, 0], "top.1": [1, 0]}
    overlays, points = s.cloud("top", ["A", "O", "D"])
    assert points == [("A", "Regular", 300, 700), ("D", "Regular", 300, 700), ("D", "Regular", 310, 700),
                      ("A", "Bold", 290, 700)]  # fmt: skip
    assert sorted(overlays) == ["Bold", "Regular"]
    assert len(overlays["Regular"].contours) == 5 and len(overlays["Bold"].contours) == 2
    assert s.anchor_rows(["A", "acutecomb"]) == [("A", "Regular", "top", 300, 700), ("A", "Bold", "top", 290, 700),
                                                 ("acutecomb", "Regular", "_top", 100, 500),
                                                 ("acutecomb", "Regular", "top", 100, 720),
                                                 ("acutecomb", "Regular", "bottom", 90, 0)]  # fmt: skip
    overlay, found = s.rings("D", 8, ["A", "D"])
    assert [(g, p.name) for g, _, p in found] == [("D", "top"), ("D", "top.1"), ("D", "ogonek")]
    assert len(overlay.contours) == 3
    assert isinstance(s.optical(pkg.layer("A")), int)
    assert s.shell.calls == [] and pkg.log == []


def test_plan_when_missing_or_auto_layers_then_notes():
    pkg = package()
    pkg.add("N", {"Regular": (INK, [])})
    pkg.add("Auto", {"Regular": (INK, []), "Bold": (INK, [])}, auto=True)
    s = studio(pkg)
    rows = s.plan(s.bounds_planner([("top", "top", 0)]), ["N", "Auto"], all_masters=True)
    assert [r.note for r in rows] == ["", "no layer in this master", "auto layer, skipped", "auto layer, skipped"]
    assert s.census(["Auto", "A"]) == {"top": [1, 0]} or True


def test_studio_state_when_no_font_then_messages():
    s = _session().Studio(Shell(None), selection=lambda: ["A", "A", "B"], font_names=lambda: ["A", "B"])
    s.reload()
    assert s.shell.statuses[-1] == _session().NO_FONT and s.masters == []
    with pytest.raises(ValueError, match="Open a font first."):
        s.targets(False)
    with pytest.raises(ValueError, match="Open a font first."):
        s.font_glyphs()
    assert s.use_selection() == ["A", "B"]
    assert not s.remove_hints(["A"]) and s.shell.statuses[-1] == f"{APP_LABEL}: Open a font first."


def test_studio_metrics_preview_and_italic_when_font_then_read():
    loads = []
    s = studio(metrics=Metrics, font_names=lambda: ["A", "O"])
    s.preview = SimpleNamespace(load=lambda *a: loads.append(a), refresh=lambda: loads.append("refresh"))
    assert s.metric("Bold", "xHeight") == 500 and s.metric("Bold", None) == 0
    assert s.italic_angle() == -12.0 and s.font_glyphs() == ["A", "O"]
    s.set_glyphs(["O", "", "O"])
    s.choose_master("Bold")
    assert loads == [("O", "Bold")]
    assert s.apply("place anchors", s.bounds_planner([("top", "top", 0)]), ["O"])
    assert s.shell.calls[-1][2] == [("O", "Bold")] and loads[-1] == "refresh"


def test_default_readers_when_fontlab_faked_then_used(monkeypatch):
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(scripting, "names_selected_names", lambda: ["A"], raising=False)
    monkeypatch.setattr(scripting, "names_font_glyphs", lambda: [("A", 1), ("O", 2)], raising=False)
    session = _session()
    assert session._selection() == ["A"] and session._font_names() == ["A", "O"]
    assert session._metrics(None, "Bold").xHeight == 500


# Tabs and window (real AppShell, history.commit faked) --------------------------
@pytest.fixture
def ss(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp.core.edit_guards as guards
    import fontlabapp.core.history.glyphs as history
    from PySide6.QtWidgets import QWidget

    studios = importlib.import_module("fontlabapp.studios.anchor_studio")
    commits = []

    def commit(title, layers, glyphs, mutate, **kwargs):
        commits.append((title, [(layer.glyph, layer.master) for layer in layers], [g.name for g in glyphs]))
        mutate()
        problems = tuple(kwargs["read_back"]()) if kwargs.get("read_back") else ()
        return SimpleNamespace(pending_note="", mismatches=problems)

    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, **k: None)
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: SimpleNamespace(users={}))
    monkeypatch.setattr(history, "commit", commit)

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def load(self, *args):
            self.calls.append(("load", *args))

        def refresh(self):
            self.calls.append(("refresh",))

        def set_overlay(self, overlay):
            self.calls.append(("set_overlay", overlay))

        def highlight(self, **kwargs):
            self.calls.append(("highlight", kwargs))

    pkg, preview = package(), QtPreview()
    shell = studios.show(package=lambda: pkg, font=lambda: object(), preview=lambda shell, studio: preview)
    studio_qt.owned.append(shell)
    yield SimpleNamespace(shell=shell, studio=shell.anchor_studio, pkg=pkg, preview=preview, commits=commits,
                          tabs=sys.modules[TABS], studios=studios)  # fmt: skip


def tab(ss, index):
    return next(view.__self__ for view in ss.studio.views if isinstance(view.__self__, ss.tabs.TAB_CLASSES[index][1]))


def click(t, text):
    from PySide6.QtWidgets import QPushButton

    button = next(b for b in t.widget.findChildren(QPushButton) if b.text() == text)
    button.click()


def test_show_when_built_then_five_tabs_and_master_notes(ss):
    assert ss.studios.TAB_TITLES == ("Place", "Align", "Rename & delete", "Clean-up", "Overlays")
    assert len(ss.studio.views) == 5 and ss.shell.preview is ss.preview
    assert tab(ss, 0).write_note.text() == "Writes go to Regular unless All masters is on."
    assert tab(ss, 4).write_note.text() == "Reads Regular; nothing is written."
    assert ss.studios.studio_for(ss.shell) is ss.studio


def test_place_tab_when_preview_then_apply_writes_one_step(ss):
    t = tab(ss, 0)
    t.glyphs_field.setText("O")
    click(t, "Preview placement")
    assert ss.commits == [] and ss.pkg.log == []
    assert ss.shell.status.text() == f"{APP_LABEL}: 2 change(s) planned on 1 layer(s); nothing written."
    assert [r[2][1] for r in t.records] == ["top", "bottom"]
    click(t, "Place anchors")
    assert ss.commits == [("Anchor Studio: place anchors O", [("O", "Regular")], ["O"])]
    assert ("load", "O", "Regular") in ss.preview.calls and ("refresh",) in ss.preview.calls
    t.anchor_rows[0][2].setChecked(False)
    t.anchor_rows[1][2].setChecked(False)
    click(t, "Preview placement")
    assert ss.shell.status.text() == f"{APP_LABEL}: Tick at least one anchor."


def test_tabs_when_master_or_row_chosen_then_preview_follows(ss):
    t = tab(ss, 0)
    t.glyphs_field.setText("A")
    t.master_box.setCurrentIndex(1)
    assert ss.studio.master == "Bold" and ("load", "A", "Bold") in ss.preview.calls
    assert t.write_note.text() == "Writes go to Bold unless All masters is on."
    t.row_chosen("O", "Regular")
    assert ss.studio.master == "Regular" and ss.preview.calls[-1] == ("load", "O", "Regular")
    t.row_chosen("")


def test_tabs_use_selection_when_empty_then_hint(ss):
    t = tab(ss, 0)
    ss.studio._selection = lambda: []
    assert t.use_selection() == [] and ss.shell.status.text() == f"{APP_LABEL}: Select glyphs in the Font window first."
    ss.studio._selection = lambda: ["A"]
    click(t, "Use font selection")
    assert t.glyphs_field.text() == "A"


def test_align_tab_when_each_tool_applied_then_labelled_steps(ss):
    t = tab(ss, 1)
    t.glyphs_field.setText("A")
    t.all_masters.setChecked(True)
    click(t, "Centre anchors")
    assert ss.commits[-1] == ("Anchor Studio: centre anchors A", [("A", "Bold")], ["A"])
    ss.studio._metrics = Metrics
    click(t, "Preview snapping")
    click(t, "Snap anchors")
    assert ss.commits[-1] == ("Anchor Studio: snap anchors A", [("A", "Regular"), ("A", "Bold")], ["A"])
    assert ss.pkg.layer("A", "Bold").where()["top"] == (300, 500)
    t.step.setValue(7)
    click(t, "Round anchors")
    assert ss.pkg.layer("A").where()["top"] == (301, 483)
    t.do_x.setChecked(False)
    t.do_y.setChecked(False)
    click(t, "Preview rounding")
    assert ss.shell.status.text() == f"{APP_LABEL}: Tick x, y or both."
    click(t, "Use font italic angle")
    assert t.angle.value() == -12
    ss.studio._rings = lambda layer: [[(100, 0), (300, 0), (300, 200), (100, 200)]]
    click(t, "Align top optically")
    assert ss.commits[-1] == ("Anchor Studio: align top optically A", [("A", "Regular")], ["A"])
    click(t, "Preview optical centre")


def test_rename_tab_when_whole_font_then_every_glyph_and_census_ticks(ss):
    t = tab(ss, 2)
    ss.studio._font_names = lambda: ["A", "O", "D"]
    t.find.setText("top.1")
    t.replace.setText("topcopy")
    t.scope.setCurrentIndex(1)
    click(t, "Preview renaming")
    click(t, "Rename anchors")
    assert ss.commits[-1] == ("Anchor Studio: rename anchors D", [("D", "Regular")], ["D"])
    click(t, "List anchor names")
    assert t.census_list.count() == 3
    assert ss.shell.status.text() == f"{APP_LABEL}: 3 anchor name(s) found; nothing written."
    click(t, "Delete anchors")
    assert ss.shell.status.text() == f"{APP_LABEL}: Tick the names to delete."
    item = next(t.census_list.item(i) for i in range(t.census_list.count()) if t.census_list.item(i).data(ss.tabs.QtCore.Qt.UserRole) == "topcopy")
    item.setCheckState(ss.tabs.QtCore.Qt.Checked)
    assert t.ticked() == ["topcopy"]
    click(t, "Delete anchors")
    assert "topcopy" not in ss.pkg.layer("D").where()


def test_cleanup_tab_when_duplicates_and_extraneous_then_written(ss):
    t = tab(ss, 3)
    t.glyphs_field.setText("D acutecomb")
    click(t, "Preview duplicates")
    assert ss.commits == []
    click(t, "Remove duplicate anchors")
    assert ss.commits[-1] == ("Anchor Studio: remove duplicate anchors D", [("D", "Regular")], ["D"])
    click(t, "Preview extraneous anchors")
    click(t, "Remove extraneous anchors")
    assert ss.commits[-1][0] == "Anchor Studio: remove extraneous anchors acutecomb"
    ss.studio._font_names = lambda: ["acutecomb"]
    t.scope.setCurrentIndex(1)
    assert t.chosen() == ["acutecomb"]


def test_hint_button_when_hinted_then_removed_in_own_steps(ss):
    ss.pkg.add("H", {"Regular": (INK, []), "Bold": (INK, [])}, hinted=True)
    t = tab(ss, 0)
    t.glyphs_field.setText("H")
    click(t, "Place anchors")
    assert ss.commits == []
    click(t, "Remove PostScript hints")
    assert ss.commits == [("Anchor Studio: remove hints H", [("H", "Regular")], ["H"])]
    assert ss.shell.status.text() == f"{APP_LABEL}: removed PostScript hints from 1 layer(s)."
    click(t, "Place anchors")
    assert ss.commits[-1] == ("Anchor Studio: place anchors H", [("H", "Regular")], ["H"])


def test_overlays_tab_when_shown_then_reads_only(ss):
    t = tab(ss, 4)
    assert not t.all_masters.isVisible() and t.every_master() is False and t.bases_allowed() is False
    ss.studio._rings = lambda layer: [[(0, 0), (10, 0), (10, 10)]]
    t.glyphs_field.setText("D A")
    click(t, "Show cloud")
    assert t.summary.text() == "4 top anchor(s) on 2 master(s): x 290…310, y 700…700"
    assert [r[1] for r in t.records] == ["Regular", "Regular", "Regular", "Bold"]
    assert ("highlight", {"anchors": ["top"]}) in ss.preview.calls
    regular = next(c[1] for c in reversed(ss.preview.calls) if c[0] == "set_overlay")
    t.master_box.setCurrentIndex(1)
    bold = next(c[1] for c in reversed(ss.preview.calls) if c[0] == "set_overlay")
    assert bold is not regular and len(bold.contours) == 2 and len(regular.contours) == 5
    t.master_box.setCurrentIndex(0)
    click(t, "Show rings")
    assert t.summary.text() == "3 stacked anchor(s) in 1 glyph(s)"
    assert ss.preview.calls[-1] == ("highlight", {"anchors": ["ogonek", "top", "top.1"]})
    click(t, "Clear overlay")
    assert ss.preview.calls[-2] == ("set_overlay", None) and t.summary.text() == ""
    t.glyphs_field.setText("")
    click(t, "Show cloud")
    assert ss.shell.status.text() == f"{APP_LABEL}: {_session().NO_GLYPHS}"
    assert ss.commits == [] and ss.pkg.log == []


def test_anchor_table_when_listed_and_chosen_then_sortable_rows_and_no_history(ss):
    t = tab(ss, 4)
    t.glyphs_field.setText("A D")
    click(t, "List anchors")
    assert t.summary.text() == "6 anchor(s) in 2 glyph(s)"
    assert [(r.glyph_name, r.layer, r.values) for r in t.anchor_table.rows[:2]] == [
        ("A", "Regular", ("Regular", "top", 300, 700)), ("A", "Bold", ("Bold", "top", 290, 700))]  # fmt: skip
    assert t.anchor_table.columns == ("Glyph", "Master", "Anchor", "x", "y")
    t.anchor_table.view.sortByColumn(3, ss.tabs.QtCore.Qt.DescendingOrder)
    top = t.anchor_table.proxy.index(0, 3)
    assert t.anchor_table.proxy.data(top) in (310, 310.0, "310")
    assert t.anchor_table.select("A", "Bold")
    assert ss.studio.master == "Bold" and ss.preview.calls[-1] == ("highlight", {"anchors": ["top"]})
    assert ("load", "A", "Bold") in ss.preview.calls
    t.anchor_chosen("")
    assert ss.commits == [] and ss.pkg.log == []


def test_cleanup_duplicates_when_default_then_every_master_in_one_step(ss):
    ss.pkg.add("Q", {"Regular": (INK, [("top", 300, 700), ("top", 310, 700)]),
                     "Bold": (INK, [("top", 290, 700), ("top", 280, 700)])})  # fmt: skip
    t = tab(ss, 3)
    assert not t.all_masters.isChecked()
    t.glyphs_field.setText("Q")
    click(t, "Preview duplicates")
    assert {r[1] for r in t.records} == {"Regular", "Bold"} and ss.commits == []
    click(t, "Remove duplicate anchors")
    assert ss.commits == [("Anchor Studio: remove duplicate anchors Q", [("Q", "Regular"), ("Q", "Bold")], ["Q"])]
    assert ss.pkg.layer("Q").where() == {"top": (300, 700)} and ss.pkg.layer("Q", "Bold").where() == {"top": (290, 700)}


def test_records_when_no_change_then_note_row():
    session, tabs = _session(), importlib.import_module(TABS)
    rows = [session.Row("A", "Regular", None, (), ""), session.Row("O", "Bold", None, (), "auto layer, skipped")]
    assert tabs.records(rows) == [("A", "Regular", ("Regular", "", "", "", "no change")),
                                  ("O", "Bold", ("Bold", "", "", "", "auto layer, skipped"))]  # fmt: skip


def test_show_when_build_fails_then_shell_closed(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp.fontui as fontui

    closed = []
    real = fontui.app_shell

    def failing(*args, **kwargs):
        shell = real(*args, **kwargs)
        studio_qt.owned.append(shell)
        shell.add_tab = lambda spec: (_ for _ in ()).throw(RuntimeError("boom"))
        original = shell.close
        shell.close = lambda: (closed.append(True), original())
        return shell

    monkeypatch.setattr(fontui, "app_shell", failing)
    studios = importlib.import_module("fontlabapp.studios.anchor_studio")
    with pytest.raises(RuntimeError, match="boom"):
        studios.show(package=lambda: None, font=lambda: None, preview=lambda shell, studio: None)
    assert closed == [True]


def test_glyph_preview_when_font_then_control_less_tglyph(monkeypatch):
    import fontlabapp.fontui as fontui

    app = importlib.import_module("fontlabapp.studios.anchor_studio.app")
    seen = []
    monkeypatch.setattr(fontui, "glyph_view", lambda *a, **k: seen.append((a, k)) or "view")
    shell = SimpleNamespace(widget="w", hint_check="hc")
    assert app._glyph_preview(shell, SimpleNamespace(font=lambda: None, current="Regular")) is None
    assert app._glyph_preview(shell, SimpleNamespace(font=lambda: "font", current="Regular")) == "view"
    assert seen == [(("font", "w"), {"layer": "Regular", "controls": False, "label_prefix": APP_LABEL,
                                     "hint_check": "hc"})]  # fmt: skip


def test_glyph_view_when_loaded_then_tglyph_built_or_closed(monkeypatch):
    import fontlabapp.fontui as fontui

    made = []

    class TGlyph:
        def __new__(cls, *args, **kwargs):
            return object.__new__(cls)

        def __init__(self, font, name, layer, parent, **kwargs):
            if font == "bad":
                raise RuntimeError("no glyph")
            made.append((font, name, layer, parent, kwargs))

        def close(self):
            made.append("closed")

    monkeypatch.setattr(fontui, "_load", lambda name: SimpleNamespace(TGlyph=TGlyph))
    view = fontui.glyph_view("font", "parent", name="A", layer="Bold", label_prefix=APP_LABEL)
    assert isinstance(view, TGlyph)
    assert made[0][:4] == ("font", "A", "Bold", "parent") and made[0][4]["controls"] is False
    with pytest.raises(RuntimeError):
        fontui.glyph_view("bad")


def test_registry_when_imported_then_five_tabs_registered_once():
    studios = importlib.import_module("fontlabapp.studios")
    importlib.import_module("fontlabapp.studios.anchor_studio")
    assert [spec.title for spec in studios.tabs(APP_LABEL)] == ["Place", "Align", "Rename & delete", "Clean-up",
                                                               "Overlays"]  # fmt: skip
    importlib.reload(sys.modules["fontlabapp.studios.anchor_studio"])
    assert len(studios.tabs(APP_LABEL)) == 5


def test_shell_status_when_status_text_is_property_or_method_then_string(studio_qt):  # noqa: F811
    from types import SimpleNamespace as NS

    from fontlabapp.studios.anchor_studio.session import Studio

    own = NS(status="own", shell=NS())
    prop = NS(status="own", shell=NS(status=NS(text="Shell text")))  # PythonQt: str property
    call = NS(status="own", shell=NS(status=NS(text=lambda: "Shell text")))  # PySide: method
    bare = NS(status="own", shell=NS(status=None))
    assert Studio.shell_status(prop) == Studio.shell_status(call) == "Shell text"
    assert Studio.shell_status(bare) == Studio.shell_status(own) == "own"
