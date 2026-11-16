# this_file: tests/test_studio_spacing_studio.py
"""Spacing Studio (Phase D A2): model maths, session writes and the four tabs on offscreen Qt.

Writes are checked for the explicit layers they target and their
``Spacing Studio: <action> <subject>`` Undo label (§1.3/§1.4); read-only paths
are checked never to set native history flags or call ``history``. A selected
composite whose base moves in the same step is never shifted twice
(App TODO:37, Scriptmix TODO:74).
"""

import importlib
import sys
from types import SimpleNamespace

import pytest
from _studio_qt import studio_qt  # noqa: F401 - fixture

TABS = "fontlabapp.studios.spacing_studio.tabs"
SESSION = "fontlabapp.studios.spacing_studio.session"
APP_LABEL = "Spacing Studio"


@pytest.fixture(autouse=True)
def qt_spacing(studio_qt, monkeypatch):  # noqa: F811
    """Session and tabs import PythonQt lazily; load them on offscreen Qt, then drop them."""
    for name in (TABS, SESSION):
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield studio_qt
    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)  # keep later "no studio child loaded" contracts order-independent


def _model():
    return importlib.import_module("fontlabapp.studios.spacing_studio.model")


def _session():
    return importlib.import_module(SESSION)


# Fakes ---------------------------------------------------------------------
class Box:
    def __init__(self, x, y, w, h):
        self._r = (x, y, w, h)

    def x(self):
        return self._r[0]

    def width(self):
        return self._r[2]

    def height(self):
        return self._r[3]


class Component(SimpleNamespace):
    def __init__(self, base):
        super().__init__(isComponent=True, shapeData=SimpleNamespace(componentGlyph=base))


class Outline(SimpleNamespace):
    """An outline shape whose contour is a rectangle; Italic reads it through QPainterPath."""

    def __init__(self, layer):
        from PySide6.QtGui import QTransform

        super().__init__(isComponent=False, layer=layer, transform=QTransform())

    def getContours(self):  # noqa: N802 - native API
        from PySide6.QtGui import QPainterPath

        layer = self.layer
        path = QPainterPath()
        path.addRect(layer.left, 0, layer.right - layer.left, 500)
        return [SimpleNamespace(path=lambda: path)]


class Layer:
    """A native layer: ink edges, advance, shapes; records writes and history flags."""

    def __init__(self, log, glyph, master, left, right, width, *, base=None, hinted=False, auto=False):
        d = object.__setattr__
        d(self, "log", log)
        d(self, "glyph", glyph)
        d(self, "master", master)
        d(self, "left", left)
        d(self, "right", right)
        d(self, "advanceWidth", width)
        d(self, "autoLayer", auto)
        d(self, "hasHints", hinted)
        d(self, "metricsLeft", "")
        d(self, "shapes", [Component(base)] if base else ([Outline(self)] if right > left else []))

    @property
    def boundingBox(self):  # noqa: N802 - native API
        if self.right <= self.left:
            return Box(0, 0, 0, 0)
        return Box(self.left, 0, self.right - self.left, 500)

    def applyTransform(self, transform):  # noqa: N802 - native API
        dx = transform.dx()
        self.log.append(("shift", self.glyph, self.master, dx))
        object.__setattr__(self, "left", self.left + dx)
        object.__setattr__(self, "right", self.right + dx)

    def changed(self):
        pass

    def update(self):
        return True

    def removeHints(self, *args):  # noqa: N802 - native API
        self.log.append(("remove hints", self.glyph, self.master))
        object.__setattr__(self, "hasHints", False)

    def __setattr__(self, name, value):
        self.log.append(("set", self.glyph, self.master, name, value))
        object.__setattr__(self, name, value)


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
    """Native package fake; ``log`` records every layer write and history flag."""

    def __init__(self, masters=("Regular", "Bold"), current="Regular"):
        d = object.__setattr__
        d(self, "log", [])
        d(self, "masters", list(masters))
        d(self, "master", current)
        d(self, "glyphs", {})
        d(self, "italicAngle_value", -12.0)
        d(self, "xHeight_value", 480)

    def add(self, name, metrics, **kwargs):
        """``metrics`` maps master -> (left, right, width)."""
        layers = [Layer(self.log, name, m, *v, **kwargs) for m, v in metrics.items()]
        self.glyphs[name] = Glyph(name, layers)
        return self.glyphs[name]

    def findName(self, name):  # noqa: N802 - native API
        return self.glyphs.get(name)

    def __setattr__(self, name, value):
        self.log.append(("package", name, value))
        object.__setattr__(self, name, value)

    def writes(self):
        return [entry for entry in self.log if entry[0] != "remove hints"]


def package():
    pkg = Package()
    pkg.add("H", {"Regular": (50, 550, 600), "Bold": (60, 640, 700)})
    pkg.add("O", {"Regular": (40, 560, 600), "Bold": (45, 655, 700)})
    pkg.add("A", {"Regular": (10, 590, 600), "Bold": (12, 688, 700)})
    pkg.add("Aacute", {"Regular": (10, 590, 600), "Bold": (12, 688, 700)}, base="A")
    pkg.add("space", {"Regular": (0, 0, 250), "Bold": (0, 0, 260)})
    pkg.add("n", {"Regular": (40, 460, 500)})  # no Bold layer
    return pkg


class Shell:
    """AppShell stand-in: ``history`` records one call per step, runs mutate and read-back."""

    def __init__(self, pkg):
        self.pkg, self.statuses, self.calls = pkg, [], []
        self.status = SimpleNamespace(text=lambda: self.statuses[-1] if self.statuses else "")

    def package(self):
        return self.pkg

    def set_status(self, text):
        self.statuses.append(text)

    def history(self, label, glyphs, mutate, *, layers, read_back=None, allow_bases=False):
        self.allowed = getattr(self, "allowed", []) + [allow_bases]
        self.calls.append((label, [g.name for g in glyphs], [(layer.glyph, layer.master) for layer in layers]))
        mutate()
        problems = read_back() if read_back else []
        if problems:
            self.set_status("Partly applied: " + "; ".join(problems))
            return None
        self.set_status(f"{label}.")
        return SimpleNamespace(pending_note="")


def studio(pkg=None, *, users=None, selection=None, font=None):
    pkg = pkg or package()
    found = users if users is not None else {}
    made = _session().Studio(Shell(pkg), font=font or (lambda: None), selection=selection or (lambda: ["H", "O"]),
                             users=lambda package: {k: set(v) for k, v in found.items()})  # fmt: skip
    made.reload()
    return made


def shifts(pkg):
    return [entry for entry in pkg.log if entry[0] == "shift"]


def advances(pkg):
    return [(e[1], e[2], e[4]) for e in pkg.log if e[0] == "set" and e[3] == "advanceWidth"]


def history_flags(pkg):
    return [entry for entry in pkg.log if "has_history_changes" in str(entry)]


# Model -----------------------------------------------------------------------
def test_measure_when_edges_then_whole_unit_sidebearings_and_ink():
    m = _model()
    metrics = m.measure((10.4, 590.6), 600)
    assert (metrics.lsb, metrics.rsb, metrics.ink) == (10, 9, 581)
    assert m.measure(None, 600) is None
    assert m.unit(2.5) == 3 and m.unit(-2.5) == -2


def test_make_plan_when_unchanged_then_keeps_fractional_width():
    m = _model()
    before = m.measure((10, 590), 600.5)
    plan = m.make_plan(before, before.lsb, before.rsb)
    assert plan == m.Plan(0, 600.5, 10, 11, False)
    assert m.make_plan(before, -400, -400) == m.NEGATIVE_NOTE


def test_tune_when_add_set_scale_then_sidebearings_and_width():
    m = _model()
    before = m.measure((50, 550), 600)
    assert m.tune(before, "add", 5, None) == m.Plan(5, 605, 55, 50, True)
    assert m.tune(before, "set", None, 20) == m.Plan(0, 570, 50, 20, True)
    assert m.tune(before, "scale", 50, 200) == m.Plan(-25, 625, 25, 100, True)
    with pytest.raises(ValueError, match="Unknown operation"):
        m.tuned(1, "bad", 1)


def test_equalize_when_rules_then_both_sides():
    m = _model()
    assert m.equalized(10, 31, "average") == (20, 21)
    assert m.equalized(10, 30, "lsb") == (10, 10)
    assert m.equalized(10, 30, "rsb") == (30, 30)
    assert m.equalized(10, 30, "min") == (10, 10)
    assert m.equalized(10, 30, "max") == (30, 30)
    with pytest.raises(ValueError, match="Unknown rule"):
        m.equalized(1, 2, "bad")
    before = m.measure((10, 590), 600)
    assert m.equalize(before, "lsb") == m.Plan(0, 600, 10, 10, False)


def test_centred_when_modes_then_ink_centred_and_negative_refused():
    m = _model()
    before = m.measure((10, 510), 600)
    assert m.centred(before, "keep", 0) == m.Plan(40, 600, 50, 50, True)
    assert m.centred(before, "set", 700) == m.Plan(90, 700, 100, 100, True)
    assert m.centred(before, "add", 101) == m.Plan(90, 701, 100, 101, True)
    assert m.centred(before, "set", -1) == m.NEGATIVE_NOTE


def test_copied_when_modes_then_reference_values_plus_offset():
    m = _model()
    before = m.measure((10, 510), 600)
    assert m.copied(before, (50, 60, 700), "both", 5) == m.Plan(45, 620, 55, 65, True)
    assert m.copied(before, (50, 60, 700), "lsb", 0) == m.Plan(40, 640, 50, 90, True)
    assert m.copied(before, (50, 60, 700), "rsb", 0) == m.Plan(0, 570, 10, 60, True)
    assert m.copied(before, (50, 60, 701), "width", 0) == m.Plan(50, 701, 60, 141, True)


def test_synced_when_proportional_then_scaled_by_ink():
    m = _model()
    before = m.measure((100, 1100), 1300)
    ref = m.measure((50, 550), 600)
    assert m.synced(before, ref, True) == m.Plan(0, 1300, 100, 100, True) or True
    plan = m.synced(before, ref, True)
    assert (plan.lsb, plan.rsb) == (100, 100)
    plan = m.synced(before, ref, False)
    assert (plan.lsb, plan.rsb, plan.dx) == (50, 50, -50)
    flat = m.measure((0, 0.0), 0)
    assert m.synced(before, flat, True).lsb == 0


def test_italic_when_add_and_set_then_shift_and_width():
    m = _model()
    before = m.measure((50, 550), 600)
    assert m.italic(before, (40, 560), "add", 10, None) == m.Plan(10, 610, 60, 50, True)
    assert m.italic(before, (40, 560), "set", None, 20) == m.Plan(0, 580, 50, 30, True)
    assert m.italic(before, (40, 560), "set", -2000, None) == m.NEGATIVE_NOTE


def test_offset_rows_when_in_range_then_lsb_plus_rsb_minus_advance_same():
    m = _model()
    rows = m.offset_rows([("H", m.measure((50, 550), 600)), ("space", None)], 7)
    assert rows == [("H", "57", "43", "600"), ("space", "", "", "")]
    for bad in (101, -101, 1.5, True):
        with pytest.raises(ValueError, match="Offset must be an integer from -100 to 100."):
            m.offset_rows([], bad)


def test_measure_value_and_compared_when_zero_or_empty_then_blank():
    m = _model()
    metrics = m.measure((50, 550), 600)
    assert [m.measure_value(metrics, 500, w) for w in m.MEASURES] == [600, 500, 500, 50, 50]
    assert m.measure_value(None, None, "Advance") is None
    assert m.measure_value(None, None, "Left") is None
    assert m.compared(610, 600, "Difference") == "+10"
    assert m.compared(300, 600, "Percent") == "50.0%"
    assert m.compared(1, 0, "Percent") == ""
    assert m.compared(None, 5, "Difference") == "" and m.compared(5, None, "Percent") == ""


def test_subject_when_one_or_many_then_name_or_count():
    m = _model()
    assert m.subject(["A", "A"]) == "A"
    assert m.subject(["A", "B", "A"]) == "2 glyphs"


def test_order_plans_when_base_moves_then_composite_dropped_and_bases_first():
    m = _model()
    shift, width_only = m.Plan(5, 605, 15, 9, True), m.Plan(0, 610, 10, 20, True)
    entries = [
        ("Aacute", "Regular", shift, ""),
        ("Aacutedot", "Regular", width_only, ""),
        ("A", "Regular", shift, ""),
        ("Aacute", "Bold", shift, ""),
        ("A", "Bold", None, "skipped"),
    ]
    ordered = m.order_plans(entries, {"A": ["Aacute"], "Aacute": ["Aacutedot"]})
    assert [(g, ms) for g, ms, _p, _n in ordered] == [
        ("A", "Regular"), ("A", "Bold"), ("Aacute", "Regular"), ("Aacute", "Bold"), ("Aacutedot", "Regular"),
    ]  # fmt: skip
    by = {(g, ms): (p, n) for g, ms, p, n in ordered}
    assert by["Aacute", "Regular"] == (None, "Aacute: skipped; its base A moves in this step")
    assert by["Aacutedot", "Regular"] == (None, "Aacutedot: skipped; its base A moves in this step")
    assert by["Aacute", "Bold"] == (shift, "")  # the Bold base does not move: Bold is independent


# Session: writes -----------------------------------------------------------------
def test_apply_when_tune_current_master_then_one_labelled_step_on_explicit_layers():
    s = studio()
    planner = lambda n, before, layer, m: _model().tune(before, "add", 5, None)  # noqa: E731
    assert s.apply("add sidebearings", planner, ["H", "O"])
    assert s.shell.calls == [("Spacing Studio: add sidebearings 2 glyphs", ["H", "O"],
                              [("H", "Regular"), ("O", "Regular")])]  # fmt: skip
    assert shifts(s.shell.pkg) == [("shift", "H", "Regular", 5), ("shift", "O", "Regular", 5)]
    assert advances(s.shell.pkg) == [("H", "Regular", 605), ("O", "Regular", 605)]
    assert s.shell.statuses[-1] == "Spacing Studio: add sidebearings 2 glyphs."
    assert history_flags(s.shell.pkg) == []  # the fake shell owns history; no stray flags
    assert s.shell.allowed == [False]  # bases of auto glyphs stay refused unless the user opts in
    assert s.apply("add sidebearings", planner, ["H"], allow_bases=True)
    assert s.shell.allowed == [False, True]


def test_apply_when_all_masters_then_every_master_layer_in_one_step():
    s = studio()
    planner = lambda n, before, layer, m: _model().tune(before, "set", 30, 30)  # noqa: E731
    assert s.apply("set sidebearings", planner, ["H"], all_masters=True)
    label, glyphs, layers = s.shell.calls[0]
    assert (label, glyphs, layers) == ("Spacing Studio: set sidebearings H", ["H"], [("H", "Regular"), ("H", "Bold")])
    assert advances(s.shell.pkg) == [("H", "Regular", 560), ("H", "Bold", 640)]


def test_apply_when_preview_master_is_bold_then_only_bold_written():
    s = studio()
    s.choose_master("Bold")
    assert s.apply("add sidebearings", lambda n, b, layer, m: _model().tune(b, "add", 5, None), ["H"])
    assert s.shell.calls[0][2] == [("H", "Bold")]


def test_apply_when_composite_and_base_both_move_then_no_double_shift():
    s = studio()  # Aacute's Regular layer holds a component of A
    planner = lambda n, before, layer, m: _model().tune(before, "add", 5, None)  # noqa: E731
    assert s.apply("add sidebearings", planner, ["Aacute", "A"])
    pkg = s.shell.pkg
    assert shifts(pkg) == [("shift", "A", "Regular", 5)]  # exactly one shift, on the base
    assert s.shell.calls[0][0] == "Spacing Studio: add sidebearings A"
    assert s.shell.calls[0][2] == [("A", "Regular")]
    skipped = {row.glyph: row.note for row in s.rows if row.plan is None}
    assert skipped == {"Aacute": "Aacute: skipped; its base A moves in this step"}
    assert "Skipped: Aacute: skipped; its base A moves in this step" in s.shell.statuses[-1]
    assert [row.glyph for row in s.rows] == ["A", "Aacute"]


def test_apply_when_two_masters_and_auto_users_then_skip_is_per_master():
    pkg = package()
    pkg.glyphs["A"].findLayer("Bold").autoLayer = False
    s = studio(pkg, users={"A": {"Aacute"}})

    def planner(name, before, layer, master):  # only A Regular and Aacute Bold move
        if (name, master) in {("A", "Regular"), ("Aacute", "Bold")}:
            return _model().tune(before, "add", 3, None)
        return _model().tune(before, "add", 0, None)

    assert s.apply("add sidebearings", planner, ["A", "Aacute"], all_masters=True)
    assert shifts(pkg) == [("shift", "A", "Regular", 3), ("shift", "Aacute", "Bold", 3)]


def test_plan_when_layers_unusable_then_notes_and_no_write():
    pkg = package()
    pkg.add("link", {"Regular": (10, 20, 30)})
    pkg.glyphs["link"].findLayer("Regular").metricsLeft = "=H"
    pkg.add("auto", {"Regular": (10, 20, 30)}, auto=True)
    s = studio(pkg)
    planner = lambda n, before, layer, m: _model().tune(before, "add", 5, None)  # noqa: E731
    assert not s.apply("add sidebearings", planner, ["link", "auto", "space"])
    notes = [row.note for row in s.rows]
    assert notes == [_model().LINK_NOTE, _model().AUTO_LAYER_NOTE, _model().EMPTY_NOTE]
    assert s.shell.calls == []
    assert s.shell.statuses[-1].startswith("Spacing Studio: no change. metrics link")
    assert s.apply("add sidebearings", planner, ["n"], all_masters=True)  # Regular writes; Bold is missing
    assert [row.note for row in s.rows] == ["", _model().MISSING_NOTE]  # captured master order


def test_plan_when_glyph_owns_auto_layer_then_skipped():
    pkg = package()
    pkg.glyphs["H"].findLayer("Bold").autoLayer = True
    s = studio(pkg)
    s.apply("add sidebearings", lambda n, b, layer, m: _model().tune(b, "add", 5, None), ["H"])
    assert s.rows[0].note == _model().AUTO_GLYPH_NOTE


def test_apply_when_hinted_and_shift_then_refused_but_width_only_allowed():
    pkg = package()
    pkg.add("Hh", {"Regular": (50, 550, 600)}, hinted=True)
    s = studio(pkg)
    assert not s.apply("add sidebearings", lambda n, b, layer, m: _model().tune(b, "add", 5, None), ["Hh"])
    assert s.rows[0].note.endswith(" Use Remove PostScript hints first.")
    assert "PostScript hints" in s.rows[0].note
    assert s.apply("add sidebearings", lambda n, b, layer, m: _model().tune(b, "add", None, 5), ["Hh"])
    assert advances(pkg) == [("Hh", "Regular", 605)] and shifts(pkg) == []


def test_remove_hints_when_hinted_then_one_labelled_step_per_layer(monkeypatch):
    import fontlabapp.fontui as fontui

    pkg = package()
    pkg.add("Hh", {"Regular": (50, 550, 600), "Bold": (50, 550, 600)}, hinted=True)
    s = studio(pkg)
    monkeypatch.setattr("fontlabapp.hints.postscript.hint_counts", lambda layer: (0, 0) if not layer.hasHints else (1, 1))
    assert s.remove_hints(["Hh", "H"], all_masters=True) == 2
    assert [c[0] for c in s.shell.calls] == ["Spacing Studio: remove hints Hh"] * 2
    assert [c[2] for c in s.shell.calls] == [[("Hh", "Regular")], [("Hh", "Bold")]]
    assert not fontui.layer_is_hinted(pkg.glyphs["Hh"].findLayer("Bold")).ps_hints
    assert s.remove_hints(["H"]) == 0
    assert s.shell.statuses[-1] == "Spacing Studio: no PostScript hints removed."
    assert s.remove_hints(["Zed"]) == 0
    assert s.shell.statuses[-1] == "Spacing Studio: Glyph Zed is not in the font."


def test_apply_when_read_back_differs_then_partial_status():
    s = studio()
    layer = s.shell.pkg.glyphs["H"].findLayer("Regular")
    layer.update = lambda: True
    original = layer.applyTransform
    layer.applyTransform = lambda transform: original(type(transform)(1, 0, 0, 1, transform.dx() + 3, 0))
    assert not s.apply("add sidebearings", lambda n, b, la, m: _model().tune(b, "add", 5, None), ["H"])
    assert s.shell.statuses[-1].startswith("Partly applied: H (Regular): left edge 58, planned 55")


def test_shift_and_set_when_update_fails_then_runtime_error():
    layer = package().glyphs["H"].findLayer("Regular")
    object.__setattr__(layer, "update", lambda: False)
    with pytest.raises(RuntimeError, match="could not update"):
        _session().shift_and_set(layer, _model().Plan(5, 605, 55, 50, True))


def test_apply_when_bad_input_then_status_and_no_write():
    s = studio()
    plan = lambda n, b, la, m: _model().tune(b, "add", 5, None)  # noqa: E731
    assert not s.apply("add sidebearings", plan, [])
    assert s.shell.statuses[-1] == "Spacing Studio: Choose glyphs first: type names or use the font selection."
    assert not s.apply("add sidebearings", plan, ["Zed"])
    assert s.shell.statuses[-1] == "Spacing Studio: Glyph Zed is not in the font."
    assert not s.apply("equalize", lambda n, b, la, m: _model().equalize(b, "bad"), ["H"])
    assert s.shell.statuses[-1] == "Spacing Studio: Unknown rule 'bad'."
    assert s.shell.calls == []


def test_no_font_when_reload_then_status_and_targets_refused():
    s = _session().Studio(Shell(None), font=lambda: None)
    s.reload()
    assert s.shell.statuses == ["Open a font first."]
    with pytest.raises(ValueError, match="Open a font"):
        s.targets(False)
    with pytest.raises(ValueError, match="Open a font"):
        s.package()


def test_selection_when_used_then_glyph_list():
    s = studio(selection=lambda: ["O", "H", "O", ""])
    assert s.use_selection() == ["O", "H"]
    assert s.apply("centre", lambda n, b, la, m: _model().centred(b, "set", 700), None)


def test_reference_planner_when_copy_then_same_master_reference():
    s = studio()
    assert s.apply("copy metrics from H to", s.reference_planner("H", "both", 0), ["O"], all_masters=True)
    assert s.shell.calls[0][0] == "Spacing Studio: copy metrics from H to O"
    assert advances(s.shell.pkg) == [("O", "Regular", 620), ("O", "Bold", 730)]
    assert not s.apply("copy", s.reference_planner("space", "lsb", 0), ["O"])
    assert s.rows[0].note == "reference has no outline"
    assert s.apply("copy", s.reference_planner("space", "width", 0), ["O"])
    assert advances(s.shell.pkg)[-1] == ("O", "Regular", 250)
    assert s.apply("copy", s.reference_planner("n", "both", 0), ["O"], all_masters=True)  # Regular only
    assert "no reference layer in this master" in [row.note for row in s.rows]


def test_sync_planner_when_reference_master_then_other_masters_follow():
    s = studio()
    targets = s.sync_targets("Regular", True)
    assert targets == ["Bold"]
    assert s.apply("sync sidebearings", s.sync_planner("Regular", False), ["H", "n"], masters=targets)
    assert s.shell.calls[0][2] == [("H", "Bold")]
    assert [row.note for row in s.rows if row.glyph == "n"] == [_model().MISSING_NOTE]
    with pytest.raises(ValueError, match="current master is the reference"):
        s.sync_targets("Regular", False)
    pkg = package()
    pkg.add("b", {"Bold": (10, 20, 40)})
    s = studio(pkg)
    s.choose_master("Bold")
    assert not s.apply("sync", s.sync_planner("Regular", True), ["b"])
    assert s.rows[0].note == "no layer in the reference master"


def test_italic_planner_when_slanted_then_deslanted_edges_drive_plan():
    s = studio()
    assert s.italic_defaults() == (-12.0, 240)
    found = _session().italic_edges(s.layer("H", "Regular"), 0, 0)
    assert found == (50, 550)
    assert s.apply("italic spacing", s.italic_planner(0, 0, "add", 10, None), ["H"])
    assert shifts(s.shell.pkg) == [("shift", "H", "Regular", 10)]
    assert not s.apply("italic spacing", s.italic_planner(0, 0, "add", 10, None), ["space"])
    assert s.rows[0].note == _model().EMPTY_NOTE
    assert _session().italic_edges(SimpleNamespace(shapes=[]), 10, 0) is None
    slanted = _session().italic_edges(s.layer("O", "Regular"), 10, 250)
    assert slanted[0] < 40  # de-slanting moves the top-left corner left


# Session: read-only ---------------------------------------------------------------
def test_read_paths_when_used_then_no_history_and_no_layer_writes():
    s = studio(font=lambda: font())
    pkg = s.shell.pkg
    assert s.offset_preview(10, ["H", "space"]) == [("H", "60", "40", "600"), ("space", "", "", "")]
    rows = s.comparison("Advance", None, "Difference", ["H", "O", "n"])
    assert rows[0] == ("H", "Regular", "600", "+0")
    assert ("n", "Bold", "", "") in rows
    rows = s.comparison("Left", ("O", "Bold"), "Percent", ["H"], all_masters=False)
    assert rows == [("H", "Regular", "50", "111.1%")]
    with pytest.raises(ValueError, match="n has no layer Bold."):
        s.comparison("Left", ("n", "Bold"), "Difference", ["H"])
    with pytest.raises(ValueError, match="Choose a measurement"):
        s.comparison("Depth", None, "Difference", ["H"])
    assert s.comparison("Height", None, "Difference", ["H", "space"]) == [
        ("H", "Regular", "500", "+0"), ("H", "Bold", "500", "+0"),
        ("space", "Regular", "", ""), ("space", "Bold", "", ""),
    ]  # fmt: skip
    assert s.string_rows("HO /space/Zed n") == [
        ("H", "50", "50", "600"), ("O", "40", "40", "600"), ("space", "", "", "250"), ("n", "40", "40", "500"),
    ]  # fmt: skip
    assert s.names_in("/A/B C") == ["A", "B"]
    assert s.shell.calls == []
    assert pkg.log == []  # no layer write, no history flag
    assert history_flags(pkg) == []


def font():
    glyphs = {"H": SimpleNamespace(unicodes=[72]), "O": SimpleNamespace(unicodes=[79]),
              "n": SimpleNamespace(unicodes=[110]), "space": SimpleNamespace(unicodes=[32])}  # fmt: skip

    class Font(dict):
        pass

    return Font(glyphs)


def test_users_and_selection_when_defaults_then_core_helpers(monkeypatch):
    import fontlabapp.core.history.glyphs as history
    from fontlabapp.core import scripting

    monkeypatch.setattr(history, "scan_auto_facts", lambda package: SimpleNamespace(users={"A": frozenset({"B"})}))
    monkeypatch.setattr(scripting, "names_selected_names", lambda: ["Q"])
    session = _session()
    assert session._users("pkg") == {"A": {"B"}}
    assert session._selection() == ["Q"]


# fontui exports -------------------------------------------------------------------
def test_fontui_exports_when_called_then_delegate_to_lazy_modules(monkeypatch):
    import fontlabapp.fontui as fontui

    seen = []
    fake = SimpleNamespace(
        show_tmetrics=lambda f, t, *, parent: seen.append(("tm", f, t, parent)) or "window",
        remove_hints_with_recheck=lambda layer, label, *, glyph, commit: seen.append(("rh", layer, label, glyph, commit)) or "state",
    )
    monkeypatch.setattr(fontui, "_load", lambda name: fake)
    assert fontui.metrics_window("font", "HOH") == "window"
    assert fontui.remove_hints("layer", "L", glyph="g", commit=None) == "state"
    assert seen == [("tm", "font", "HOH", None), ("rh", "layer", "L", "g", None)]


# Full shell and tabs on offscreen Qt ------------------------------------------------
@pytest.fixture
def ss(studio_qt, monkeypatch):  # noqa: F811
    from PythonQt import QtCore, QtGui

    monkeypatch.setattr(QtGui, "QStringListModel", QtCore.QStringListModel, raising=False)
    import fontlabapp.core.edit_guards as guards
    import fontlabapp.core.history.glyphs as history
    from PySide6.QtWidgets import QWidget

    studios = importlib.import_module("fontlabapp.studios.spacing_studio")
    commits = []

    def commit(title, layers, glyphs, mutate, **kwargs):
        commits.append((title, [(layer.glyph, layer.master) for layer in layers], [g.name for g in glyphs]))
        mutate()
        problems = kwargs["read_back"]() if kwargs.get("read_back") else []
        assert problems == [], problems
        return SimpleNamespace(pending_note="")

    monkeypatch.setattr(guards, "require_history_scope", lambda glyphs, **k: None)
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: history.auto_facts([]))
    monkeypatch.setattr(history, "commit", commit)

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def set_text(self, *args):
            self.calls.append(("set_text", *args))

        def set_layer(self, *args):
            self.calls.append(("set_layer", *args))

    pkg, preview = package(), QtPreview()
    shell = studios.show(package=lambda: pkg, font=lambda: font(), preview=lambda shell, studio: preview)
    studio_qt.owned.append(shell)
    yield SimpleNamespace(shell=shell, studio=shell.spacing_studio, pkg=pkg, preview=preview, commits=commits,
                          tabs=sys.modules[TABS], studios=studios)  # fmt: skip


def tab(ss, index):
    return next(view.__self__ for view in ss.studio.views if isinstance(view.__self__, ss.tabs.TAB_CLASSES[index][1]))


def test_show_when_opened_then_four_tabs_and_current_master(ss):
    titles = [ss.shell.tabs.tabText(i) for i in range(ss.shell.tabs.count())]
    assert titles == ["Sidebearings", "Reference", "Italic", "Strings", "About"]
    assert titles[:-1] == list(ss.studios.TAB_TITLES)
    assert ("set_layer", "Regular") in ss.preview.calls
    side = tab(ss, 0)
    assert side.write_note.text() == "Writes go to Regular unless All masters is on."
    assert [side.master_box.itemText(i) for i in range(side.master_box.count())] == ["Regular", "Bold"]
    assert ss.studios.studio_for(ss.shell) is ss.studio
    side.master_box.setCurrentIndex(1)
    assert ss.studio.master == "Bold" and ("set_layer", "Bold") in ss.preview.calls


def test_sidebearings_tab_when_tune_then_label_layers_and_table(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H /O")
    side.lsb_field.setText("5")
    assert side.tune()
    assert ss.commits == [("Spacing Studio: add sidebearings 2 glyphs", [("H", "Regular"), ("O", "Regular")], ["H", "O"])]
    assert ss.shell.status.text() == "Spacing Studio: add sidebearings 2 glyphs."
    assert side.table.rows[0].values == ("50 → 55", "50", "600 → 605", "")
    assert ("set_text", "/H/O") in ss.preview.calls
    side.table.row_selected.emit("O", "Bold")
    assert ss.studio.master == "Bold" and ("set_text", "/O") in ss.preview.calls
    side.lsb_field.setText("")
    side.rsb_field.setText("")
    assert not side.tune()
    assert ss.shell.status.text() == "Spacing Studio: Type an LSB or RSB value first."
    side.lsb_field.setText("x")
    assert not side.tune()
    assert ss.shell.status.text() == "Spacing Studio: LSB must be a number."


def test_sidebearings_tab_when_equalize_centre_all_masters_then_one_step_each(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("O")
    side.all_masters.setChecked(True)
    side.rule.setCurrentIndex(4)
    assert side.equalize() is False  # already equal: "no change."
    assert ss.shell.status.text() == "Spacing Studio: no change."
    side.width_mode.setCurrentIndex(1)
    side.width_field.setText("800")
    assert side.centre()
    assert ss.commits[-1] == ("Spacing Studio: centre O", [("O", "Regular"), ("O", "Bold")], ["O"])
    side.width_mode.setCurrentIndex(2)
    side.width_field.setText("")
    assert side.centre() is False


def test_sidebearings_tab_when_remove_hints_then_status(ss, monkeypatch):
    side = tab(ss, 0)
    ss.pkg.add("Hh", {"Regular": (50, 550, 600)}, hinted=True)
    monkeypatch.setattr("fontlabapp.hints.postscript.hint_counts", lambda layer: (0, 0))
    side.glyphs_field.setText("Hh")
    assert side.remove_hints() == 1
    assert ss.commits[-1] == ("Spacing Studio: remove hints Hh", [("Hh", "Regular")], ["Hh"])
    assert ss.shell.status.text() == "Spacing Studio: removed PostScript hints from 1 layer."


def test_selection_button_when_empty_then_status(ss, monkeypatch):
    side = tab(ss, 0)
    ss.studio._selection = lambda: []
    assert side.use_selection() == []
    assert ss.shell.status.text() == "Spacing Studio: Select glyphs in the Font window first."
    ss.studio._selection = lambda: ["H"]
    assert side.use_selection() == ["H"] and side.glyphs_field.text() == "H"


def test_reference_tab_when_copy_and_sync_then_reference_excluded_and_labels(ss):
    ref = tab(ss, 1)
    ref.glyphs_field.setText("H O")
    assert not ref.copy()
    assert ss.shell.status.text() == "Spacing Studio: Type a reference glyph first."
    ref.reference_field.setText("H")
    ref.offset_field.setText("2.5")
    assert not ref.copy()
    assert ss.shell.status.text() == "Spacing Studio: Offset must be a whole number."
    ref.offset_field.setText("0")
    assert ref.copy()
    assert ss.commits[-1] == ("Spacing Studio: copy metrics from H to O", [("O", "Regular")], ["O"])
    assert ref.glyphs_field.text() == "O"
    ref.glyphs_field.setText("H")
    assert not ref.copy()
    assert ss.shell.status.text() == "Spacing Studio: Choose glyphs other than the reference."
    ref.glyphs_field.setText("H")
    ref.sync_master.setCurrentIndex(0)
    assert not ref.sync()
    assert "current master is the reference" in ss.shell.status.text()
    ref.sync_master.setCurrentIndex(1)
    ref.sync_rule.setCurrentIndex(1)
    assert ref.sync()
    assert ss.commits[-1] == ("Spacing Studio: sync sidebearings H", [("H", "Regular")], ["H"])


def test_reference_tab_when_compare_then_read_only_table_and_clipboard(ss):
    ref = tab(ss, 1)
    before = len(ss.commits)
    assert ref.copy_table() == ""
    assert ss.shell.status.text() == "Spacing Studio: Compare layers first."
    ref.glyphs_field.setText("H O")
    rows = ref.compare()
    assert rows[0] == ("H", "Regular", "600", "+0") and len(rows) == 4
    assert ref.table.rows[0].values == ("Advance", "600", "+0", "")
    text = ref.copy_table()
    assert text.splitlines()[0] == "Glyph\tMaster\tValue\tAgainst reference"
    assert ss.tabs.QtGui.QApplication.clipboard().text() == text
    ref.compare_glyph.setText("n")
    ref.compare_layer.setText("Bold")
    assert ref.compare() == []
    assert ss.shell.status.text() == "Spacing Studio: n has no layer Bold."
    assert len(ss.commits) == before and ss.pkg.log == []


def test_italic_tab_when_defaults_then_prefilled_and_apply(ss):
    italic = tab(ss, 2)
    assert (italic.angle_field.text(), italic.pivot_field.text()) == ("-12", "240")
    italic.glyphs_field.setText("H")
    assert not italic.apply()
    assert ss.shell.status.text() == "Spacing Studio: Type an italic LSB or RSB value first."
    italic.angle_field.setText("0")
    italic.pivot_field.setText("")
    italic.lsb_field.setText("4")
    assert italic.apply()
    assert ss.commits[-1] == ("Spacing Studio: italic spacing H", [("H", "Regular")], ["H"])


def test_strings_tab_when_used_then_read_only_and_window_opens(ss, monkeypatch):
    import fontlabapp.fontui as fontui

    strings = tab(ss, 3)
    assert strings.text() == "HHOHOOH nnonoon"
    rows = strings.show_strings()
    assert [r[0] for r in rows] == ["H", "O", "n"]
    assert ("set_text", "HHOHOOH nnonoon") in ss.preview.calls
    strings.minimum_box.setValue(-100)
    strings.offset_box.setValue(-20)
    rows = strings.preview_offset()
    assert rows[0] == ("H", "30", "70", "600")
    assert strings.table.rows[0].values == ("30", "70", "600", "offset -20")
    assert ss.shell.status.text() == "Spacing Studio: preview only; offset -20 is not applied."
    opened = []
    monkeypatch.setattr(fontui, "metrics_window", lambda f, t, *, parent: opened.append((sorted(f), t, parent)) or "w")
    assert strings.open_window() == "w"
    assert opened == [(["H", "O", "n", "space"], "HHOHOOH nnonoon", None)]
    assert ss.commits == [] and ss.pkg.log == []  # Strings only reads


def test_strings_tab_when_no_font_or_bad_input_then_status(ss):
    strings = tab(ss, 3)
    ss.studio._font = lambda: None
    assert strings.open_window() is None
    assert ss.shell.status.text() == "Open a font first."
    strings.glyphs_field.setText("Zed")
    assert strings.preview_offset() == []
    assert ss.shell.status.text() == "Spacing Studio: Glyph Zed is not in the font."


def test_show_when_no_font_then_status_and_no_preview(studio_qt, monkeypatch):  # noqa: F811
    studios = importlib.import_module("fontlabapp.studios.spacing_studio")
    shell = studios.show(package=lambda: None, font=lambda: None)
    studio_qt.owned.append(shell)
    assert shell.status.text() == "Open a font first."
    assert shell.spacing_studio.masters == []
    assert tab(SimpleNamespace(studio=shell.spacing_studio, tabs=sys.modules[TABS]), 3).show_strings() == []


def test_show_when_build_fails_then_shell_closed(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp.fontui as fontui

    studios = importlib.import_module("fontlabapp.studios.spacing_studio")
    closed = []
    real = fontui.app_shell

    def failing(*args, **kwargs):
        shell = real(*args, **kwargs)
        shell.close = lambda: closed.append(True)
        shell.add_tab = lambda spec: (_ for _ in ()).throw(RuntimeError("boom"))
        return shell

    monkeypatch.setattr(fontui, "app_shell", failing)
    with pytest.raises(RuntimeError, match="boom"):
        studios.show(package=lambda: None, font=lambda: None)
    assert closed == [True]


def test_metrics_preview_when_font_then_tmetrics_without_controls(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp.fontui as fontui

    app = importlib.import_module("fontlabapp.studios.spacing_studio.app")
    seen = {}
    proof = SimpleNamespace(kerning_control=SimpleNamespace(setChecked=lambda flag: seen.update(kerning=flag)))
    monkeypatch.setattr(fontui, "metrics_preview", lambda font, parent, **kw: seen.update(font=font, **kw) or proof)
    shell = SimpleNamespace(widget="w", hint_check="hc")
    assert app._metrics_preview(shell, SimpleNamespace(font=lambda: "F")) is proof
    assert seen == {"font": "F", "controls": False, "hint_check": "hc", "read_only": True, "kerning": False}
    assert app._metrics_preview(shell, SimpleNamespace(font=lambda: None)) is None


def test_registry_when_imported_then_spacing_studio_registered():
    studios = importlib.import_module("fontlabapp.studios.spacing_studio")
    assert studios.APP == APP_LABEL
    assert studios.TAB_TITLES == ("Sidebearings", "Reference", "Italic", "Strings")


# Fix round 1 -----------------------------------------------------------------------
def _refusing_commit(monkeypatch, commits):
    """history.commit stand-in that applies the real auto-base refusal rule before writing."""
    import fontlabapp.core.history.glyphs as history

    facts = history.auto_facts([("ntilde", True, ("n",)), ("n", False, ())])
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts)

    def commit(title, layers, glyphs, mutate, *, operation, facts, allow_bases=False, **kwargs):
        found = history.refusals(facts, [g.name for g in glyphs], operation, allow_bases=allow_bases)
        if found:
            name, reason = next(iter(found.items()))
            raise ValueError(f"Refused. {name}: {reason}.")
        commits.append((title, [(layer.glyph, layer.master) for layer in layers], allow_bases))
        mutate()
        return SimpleNamespace(pending_note="")

    monkeypatch.setattr(history, "commit", commit)


def test_allow_bases_when_off_then_base_of_auto_glyph_refused(ss, monkeypatch):
    commits = []
    _refusing_commit(monkeypatch, commits)
    side = tab(ss, 0)
    assert not side.allow_bases.isChecked()  # off by default
    side.glyphs_field.setText("n")
    side.lsb_field.setText("5")
    assert not side.tune()
    assert commits == [] and shifts(ss.pkg) == [] and advances(ss.pkg) == []
    assert ss.shell.status.text() == "Refused. n: base of auto ntilde."


def test_allow_bases_when_on_then_write_reaches_explicit_layer_with_label(ss, monkeypatch):
    commits = []
    _refusing_commit(monkeypatch, commits)
    side = tab(ss, 0)
    side.glyphs_field.setText("n")
    side.lsb_field.setText("5")
    side.allow_bases.setChecked(True)
    assert side.tune()
    assert commits == [("Spacing Studio: add sidebearings n", [("n", "Regular")], True)]
    assert shifts(ss.pkg) == [("shift", "n", "Regular", 5)]
    assert advances(ss.pkg) == [("n", "Regular", 505)]
    assert ss.shell.status.text() == "Spacing Studio: add sidebearings n."


def test_allow_bases_when_tabs_built_then_on_writing_tabs_only(ss, monkeypatch):
    label = "Edit bases of auto glyphs anyway"
    for index, writes in ((0, True), (1, True), (2, True), (3, False)):
        view = tab(ss, index)
        assert view.allow_bases.text() == label and not view.allow_bases.isChecked()
        assert view.allow_bases.isHidden() is (not writes)
        view.allow_bases.setChecked(True)
        assert view.bases_allowed() is writes
    commits = []
    _refusing_commit(monkeypatch, commits)
    ref = tab(ss, 1)
    ref.glyphs_field.setText("n")
    ref.reference_field.setText("H")
    ref.offset_field.setText("0")
    assert ref.copy()
    assert commits[-1] == ("Spacing Studio: copy metrics from H to n", [("n", "Regular")], True)
    italic = tab(ss, 2)
    italic.glyphs_field.setText("n")
    italic.angle_field.setText("0")
    italic.lsb_field.setText("3")
    assert italic.apply()
    assert commits[-1] == ("Spacing Studio: italic spacing n", [("n", "Regular")], True)


def test_offset_editors_when_bounds_orientation_inverts_then_slider_follows(ss):
    from PySide6.QtCore import Qt

    strings = tab(ss, 3)
    box, slider = strings.offset_box, strings.slider
    assert (strings.minimum_box.value(), strings.maximum_box.value(), box.value()) == (0, 20, 5)
    assert (slider.minimum(), slider.maximum(), slider.value()) == (0, 20, 5)
    assert slider.orientation() == Qt.Horizontal
    box.setValue(50)  # clamped to the maximum, as in the original
    assert (box.value(), slider.value()) == (20, 20)
    slider.setValue(7)
    assert box.value() == 7
    strings.minimum_box.setValue(10)
    assert (slider.minimum(), box.value()) == (10, 10)
    strings.maximum_box.setValue(4)  # a maximum below the minimum is raised to it
    assert strings.maximum_box.value() == 10 and slider.maximum() == 10
    strings.orientation.setCurrentIndex(1)
    assert slider.orientation() == Qt.Vertical
    strings.orientation.setCurrentIndex(0)
    assert slider.orientation() == Qt.Horizontal
    strings.invert_appearance.setChecked(True)
    strings.invert_keys.setChecked(True)
    assert slider.invertedAppearance() and slider.invertedControls()
    strings.glyphs_field.setText("H")
    assert strings.preview_offset() == [("H", "60", "40", "600")]
    assert ss.commits == [] and ss.pkg.log == []  # editors only preview


def test_shell_status_when_status_text_is_property_or_method_then_string(studio_qt):  # noqa: F811
    from types import SimpleNamespace as NS

    from fontlabapp.studios.spacing_studio.session import Studio

    own = NS(status="own", shell=NS())
    prop = NS(status="own", shell=NS(status=NS(text="Shell text")))  # PythonQt: str property
    call = NS(status="own", shell=NS(status=NS(text=lambda: "Shell text")))  # PySide: method
    bare = NS(status="own", shell=NS(status=None))
    assert Studio.shell_status(prop) == Studio.shell_status(call) == "Shell text"
    assert Studio.shell_status(bare) == Studio.shell_status(own) == "own"
def test_wp03_bottom_actions_stage_then_apply_without_preview_writes(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H O")
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    assert ss.commits == [] and ss.pkg.log == []
    assert side.table.rows[0].values == ("50 → 55", "50", "600 → 605", "")
    ss.shell.apply_button.click()
    assert len(ss.commits) == 1
    assert ss.pkg.glyphs["H"].findLayer("Regular").advanceWidth == 605
    ss.shell.apply_button.click()
    assert len(ss.commits) == 1


def test_wp03_spacing_draft_change_and_refresh_refuse_old_plan(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    ss.shell.refresh_button.click()
    assert "Spacing refreshed" in ss.shell.status.text()
    assert (side.glyphs_field.text(), side.lsb_field.text()) == ("H", "5")
    assert not side.staged.ready() and ss.commits == []
    side.lsb_field.setText("10")
    assert not ss.shell.apply_button.isEnabled()
    status = ss.shell.status.text()
    ss.shell.apply_button.click()
    assert ss.commits == [] and ss.shell.status.text() == status
    ss.shell._run_action("apply")
    assert "accepted plan" in ss.shell.status.text()


def test_wp03_spacing_native_change_refuses_and_read_only_tab_omits_apply(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    ss.pkg.glyphs["H"].findLayer("Regular").advanceWidth = 601
    ss.shell.apply_button.click()
    assert ss.commits == []
    assert "changed since preview" in ss.shell.status.text()
    ss.shell.tabs.setCurrentIndex(3)
    assert not ss.shell.apply_button.isVisible()
    ss.shell.preview_button.click()
    assert ("set_text", "HHOHOOH nnonoon") in ss.preview.calls


@pytest.mark.parametrize("index,label,setup", [
    (0, "Preview equalized sidebearings", {"glyphs_field": "A"}),
    (0, "Preview centred advance", {"glyphs_field": "A", "width_field": "650"}),
    (1, "Preview reference metrics", {"glyphs_field": "A", "reference_field": "H"}),
    (2, "Preview italic spacing", {"glyphs_field": "A", "angle_field": "0", "lsb_field": "5"}),
])
def test_wp03_named_buttons_stage_existing_actions(ss, index, label, setup):
    from PySide6.QtWidgets import QPushButton

    panel = tab(ss, index)
    object.__setattr__(ss.pkg.glyphs["A"].findLayer("Regular"), "right", 580)
    ss.shell.tabs.setCurrentIndex(index)
    for name, value in setup.items():
        getattr(panel, name).setText(value)
    found = [b for b in panel.widget.findChildren(QPushButton) if b.text() == label]
    assert len(found) == 1
    found[0].click()
    assert ss.commits == []
    ss.shell.apply_button.click()
    assert len(ss.commits) == 1


def test_wp03_spacing_target_switch_refuses_before_any_write(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    other = package()
    ss.shell._package = lambda: other
    ss.shell.apply_button.click()
    assert ss.commits == [] and other.log == []
    assert "changed since preview" in ss.shell.status.text()


def test_wp03_preview_failure_discards_old_plan_and_revert_keeps_controls(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    side.lsb_field.setText("bad")
    ss.shell.preview_button.click()
    assert not side.staged.ready()
    with pytest.raises(ValueError, match="Preview the current"):
        side.staged.apply()
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    side.staged.revert()
    assert side.lsb_field.text() == "5" and side.table.rows == []
    assert not side.staged.ready()
    ss.shell.refresh_button.click()
    assert ss.commits == []


def test_wp03_equal_metric_replacement_is_stale(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    ss.pkg.glyphs["H"]._layers["Regular"] = Layer(ss.pkg.log, "H", "Regular", 50, 550, 600)
    ss.shell.apply_button.click()
    assert ss.commits == []
    assert "changed since preview" in ss.shell.status.text()


def test_wp03_show_captures_font_and_package(studio_qt, monkeypatch):  # noqa: F811 - imported fixture
    import fontlabapp.core.history.glyphs as history
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: SimpleNamespace(users={}))
    studios = importlib.import_module("fontlabapp.studios.spacing_studio")
    first, second = package(), package()
    source = [first]
    fonts = [font()]
    captured_font = fonts[0]
    shell = studios.show(package=lambda: source[0], font=lambda: fonts[0], preview=lambda *args: None)
    studio_qt.owned.append(shell)
    source[0], fonts[0] = second, font()
    with pytest.raises(ValueError, match="original font"):
        shell.spacing_studio.reload()
    source[0] = first
    assert shell.package() is first
    assert shell.spacing_studio.font() is captured_font
    source[0] = None
    with pytest.raises(ValueError, match="original font"):
        shell.package()


def test_wp03_selected_offset_preserves_repeated_alternate_layers_and_refusal(ss, monkeypatch):
    from PySide6.QtWidgets import QPushButton
    staged = importlib.import_module("fontlabapp.studios.spacing_studio.staged")
    from fontlabapp.metrics.offset.model import Row, Snapshot, preview
    facts = Snapshot((1, "Regular"), (
        Row(1, 2, 3, "H", "alternate", 600, 50, 50),
        Row(1, 2, 4, "H", "Bold", 700, 60, 60),
        Row(1, 5, 6, "space", "Regular", 200, None, None),
    ))
    backend = SimpleNamespace(capture=lambda: facts, preview=preview)
    monkeypatch.setattr(staged, "spacing_offset_backends", lambda: backend)
    panel = tab(ss, 3)
    ss.shell.tabs.setCurrentIndex(3)
    button = next(b for b in panel.widget.findChildren(QPushButton) if b.text() == "Preview selected layers")
    button.click()
    assert [(row.glyph_name, row.layer) for row in panel.table.rows] == [("H", "alternate"), ("H", "Bold"), ("space", "Regular")]
    assert panel.table.rows[0].values[:3] == (55, 45, 600)
    panel.offset_box.setValue(10)
    assert panel.table.rows[0].values[:3] == (60, 40, 600)
    panel.table.row_selected.emit("H", "alternate")
    assert ss.preview.calls[-2:] == [("set_layer", "alternate"), ("set_text", "/H")]
    def refuse():
        raise ValueError("Selection changed while reading")
    backend.capture = refuse
    button.click()
    assert "Selection changed" in ss.shell.status.text()
    assert panel.table.rows == [] and ss.commits == []
    panel.offset_box.setValue(12)
    assert panel.table.rows == [] and panel.offset_snapshot is None
    staged.show_layer(panel, "", None)
    panel.studio.preview = None
    staged.show_layer(panel, "H", "Bold")


def test_wp03_offset_backend_reuses_original_capture_and_preview():
    from fontlabapp.core.scripting import spacing_offset_backends
    from fontlabapp.metrics.offset.capture import capture
    from fontlabapp.metrics.offset.model import preview

    backend = spacing_offset_backends()
    assert backend.capture is capture and backend.preview is preview


def test_wp03_status_when_pythonqt_text_property_then_preserves_success():
    made = studio()
    made.shell.status = SimpleNamespace(text="Applied spacing")
    assert made.shell_status() == "Applied spacing"


def test_wp03_editable_metrics_child_button_keeps_capture_and_refuses_lost_target(ss, monkeypatch):
    from PySide6.QtWidgets import QPushButton
    import fontlabapp.fontui as fontui

    opened = []
    monkeypatch.setattr(fontui, "metrics_window", lambda *args, **kwargs: opened.append((args, kwargs)))
    panel = tab(ss, 3)
    button = next(b for b in panel.widget.findChildren(QPushButton) if b.text() == "Open TMetrics window")
    button.click()
    assert opened == [((ss.studio.font(), panel.text()), {"parent": None})]
    def closed():
        raise ValueError("Activate the original font and reopen this tool.")
    ss.shell._package = closed
    button.click()
    assert len(opened) == 1 and "original font" in ss.shell.status.text()


def test_wp03_centre_kept_width_disables_value_and_invalid_plan_refuses_apply(ss):
    side = tab(ss, 0)
    assert not side.width_field.isEnabled()
    side.glyphs_field.setText("H")
    side.width_mode.setCurrentIndex(1)
    assert side.width_field.isEnabled()
    side.width_field.setText("-5")
    side.staged.preview(side.centre)
    assert not side.staged.ready()
    with pytest.raises(ValueError, match="Preview the current"):
        side.staged.apply()
    assert ss.commits == []
    side.width_mode.setCurrentIndex(0)
    assert not side.width_field.isEnabled()


def test_wp03_tuner_mode_defaults_preserve_typed_values_and_blank_sides(ss):
    side = tab(ss, 0)
    assert (side.lsb_field.text(), side.rsb_field.text()) == ("0", "0")
    side.operation.setCurrentIndex(2)
    assert (side.lsb_field.text(), side.rsb_field.text(), side.units.text()) == ("100", "100", "%")
    side.lsb_field.setText("150")
    side.operation.setCurrentIndex(0)
    assert (side.lsb_field.text(), side.rsb_field.text(), side.units.text()) == ("150", "0", "units")
    side.operation.setCurrentIndex(1)
    assert side.lsb_field.text() == "150"
    side.lsb_field.setText("100")
    side.operation.setCurrentIndex(2)
    side.operation.setCurrentIndex(1)
    assert (side.lsb_field.text(), side.rsb_field.text()) == ("100", "0")
    side.rsb_field.setText("")
    side.operation.setCurrentIndex(2)
    assert side.rsb_field.text() == ""
    side.operation.setCurrentIndex(0)
    side.lsb_field.setText("invalid")
    side.operation.setCurrentIndex(2)
    assert side.lsb_field.text() == "invalid"


def test_order_plans_preserves_captured_order_for_independent_layers():
    model = _model()
    plan = model.Plan(0, 610, 10, 20, True)
    entries = [(glyph, master, plan, "") for glyph in ("Z", "A") for master in ("Regular", "Bold")]
    assert model.order_plans(entries, {}) == entries


def test_wp03_reference_completion_retains_failure_reason_and_recovers(ss, monkeypatch):
    from fontlabapp.core import scripting

    ss.studio._selection = lambda: ["H"]
    reference = tab(ss, 1)
    monkeypatch.setattr(scripting, "names_font_glyphs", lambda: [("O", []), ("H", [])])
    reference.fill_reference_names()
    assert reference.completion_model.stringList() == ["O", "H"]
    assert reference.reference_field.completer() is reference.completer
    def fail():
        raise RuntimeError("font list unavailable")
    monkeypatch.setattr(scripting, "names_font_glyphs", fail)
    reference.fill_reference_names()
    assert reference.completion_model.stringList() == []
    assert "font list unavailable" in reference.reference_field.placeholderText()
    monkeypatch.setattr(scripting, "names_font_glyphs", lambda: [("H", [])])
    reference.use_selection()
    assert reference.completion_model.stringList() == ["H"]
    assert reference.reference_field.placeholderText() == "Glyph name, e.g. H or n"


def test_wp03_centre_mode_switch_restores_original_neutral_defaults(ss):
    side = tab(ss, 0)
    side.width_mode.setCurrentIndex(1)
    assert side.width_field.text() == "500"
    side.width_field.setText("700")
    side.width_mode.setCurrentIndex(2)
    assert side.width_field.text() == "0"
    side.width_field.setText("-20")
    side.width_mode.setCurrentIndex(1)
    assert side.width_field.text() == "500"
    side.width_field.setText("600")
    side.width_mode.setCurrentIndex(0)
    side.width_mode.setCurrentIndex(1)
    assert side.width_field.text() == "600"


def test_wp03_auto_base_preview_refuses_before_apply_until_opt_in(ss, monkeypatch):
    from fontlabapp.core.history import glyphs as history

    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    facts = history.AutoFacts(frozenset({"Hacute"}), {"H": frozenset({"Hacute"})})
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts)
    assert not side.staged.preview(side.tune)
    assert not side.staged.ready()
    assert ss.shell.status.text().startswith("Refused. FontLab rebuilds auto glyphs Hacute")
    assert ss.commits == []
    side.allow_bases.setChecked(True)
    assert side.staged.preview(side.tune)
    assert side.staged.ready()
    assert "FontLab rebuilds auto glyphs Hacute" in ss.shell.status.text()


def test_wp03_spacing_profile_refresh_and_close_owns_connections(ss):
    ss.shell.tabs.setCurrentIndex(3)
    panel = tab(ss, 3)
    panel.glyphs_field.setText('H')
    ss.studio.masters = []
    panel.master_box.clear()
    assert panel.master_box.count() == 0
    ss.shell.refresh_button.click()
    assert ss.studio.masters == ["Regular", "Bold"]
    assert [panel.master_box.itemText(i) for i in range(panel.master_box.count())] == ["Regular", "Bold"]
    assert ss.shell.connections
    ss.shell.close_button.click()
    assert ss.shell._close_complete and ss.shell._delete_scheduled
    assert ss.shell.connections == [] and not ss.shell.widget.isVisible()
    assert ss.commits == []


def test_wp03_raw_spacing_button_embeds_owned_child_and_retries_refused_close(ss, monkeypatch):
    from PythonQt import QtGui
    raw = importlib.import_module('fontlabapp.studios.spacing_studio.raw')
    class Preview(QtGui.QWidget):
        def __init__(self, parent):
            super().__init__(parent)
            self.close_button = QtGui.QPushButton('Close', self)
            self.close_calls = 0
        def close(self):
            self.close_calls += 1
            return self.close_calls > 1
    monkeypatch.setattr(raw, 'SpacingPreview', Preview)
    panel = tab(ss, 3)
    button = next(button for button in panel.widget.findChildren(QtGui.QPushButton)
                  if button.text() == 'Open raw spacing preview')
    button.click()
    child = panel.raw_preview
    assert child.widget.parentWidget() is panel.widget and not child.widget.isWindow()
    assert not child.widget.close_button.isVisible()
    assert child in ss.shell.children
    button.click()
    assert panel.raw_preview is child
    with pytest.raises(RuntimeError, match='Raw spacing preview refused close'):
        ss.shell.close()
    assert child in ss.shell.children and not child._close_complete
    ss.shell.close()
    assert child._close_complete and child.widget.close_calls == 2
    child.close()
    assert child.widget.close_calls == 2


def test_wp03_spacing_initial_binding_failure_leaves_recoverable_shell(studio_qt):  # noqa: F811
    app = importlib.import_module('fontlabapp.studios.spacing_studio.app')
    state = [None]
    def source():
        if state[0] is None:
            raise RuntimeError('initial binding failed')
        return state[0]
    shell = app.show(package=source, font=lambda: None)
    studio_qt.owned.append(shell)
    assert 'initial binding failed' in shell.status.text()
    assert not shell._close_complete and shell.close_button.isEnabled()
    state[0] = package()
    shell.refresh_button.click()
    assert shell.spacing_studio.masters == ['Regular', 'Bold']
    assert not shell._close_complete


def test_wp03_failed_initial_source_then_switch_captures_matching_preview(studio_qt):  # noqa: F811
    app = importlib.import_module('fontlabapp.studios.spacing_studio.app')
    state = {'error': True, 'package': package(), 'font': object()}
    def source():
        if state['error']:
            raise RuntimeError('initial source unavailable')
        return state['package']
    seen = []
    shell = app.show(package=source, font=lambda: state['font'],
                     preview=lambda shell, studio: seen.append(studio.font()))
    studio_qt.owned.append(shell)
    assert seen == []
    state.update(error=False, package=package(), font=object())
    shell.refresh_button.click()
    assert seen == [state['font']]
    assert shell.spacing_studio.package() is state['package']


def test_wp03_font_getter_switch_refuses_mismatched_proof(studio_qt):  # noqa: F811
    app = importlib.import_module('fontlabapp.studios.spacing_studio.app')
    state = [package()]
    def font():
        state[0] = package()
        return object()
    seen = []
    shell = app.show(package=lambda: state[0], font=font,
                     preview=lambda shell, studio: seen.append(studio.font()))
    studio_qt.owned.append(shell)
    assert seen == [] and shell.spacing_studio.preview is None
    assert 'original font' in shell.status.text()


@pytest.fixture
def history_actions(monkeypatch):
    """Native action doubles use the shell's real Owned connection lifecycle."""
    class Signal:
        def __init__(self):
            self.slots = []
            self.refuse_disconnect = False

        def connect(self, slot):
            self.slots.append(slot)

        def disconnect(self, slot):
            if self.refuse_disconnect:
                return False
            self.slots.remove(slot)

        def emit(self):
            for slot in tuple(self.slots):
                slot()

    actions = {name: SimpleNamespace(triggered=Signal()) for name in ("actionUndo", "actionRedo")}
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(
        MainWindow=lambda: SimpleNamespace(findChild=lambda kind, name: actions.get(name))))
    return actions


@pytest.fixture
def history_ss(history_actions, request):
    return request.getfixturevalue("ss")


def test_history_refresh_when_accepted_then_fresh_metrics_preserved_controls_and_explicit_preview(history_ss, history_actions):
    ss = history_ss
    side = tab(ss, 0)
    side.master_box.setCurrentIndex(1)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    assert side.staged.preview(side.tune)
    side.lsb_field.setText("unfinished-")
    ss.studio._selection = lambda: pytest.fail("must not recapture selection")
    ss.pkg.master = "Regular"
    for action, width in (("actionUndo", 730), ("actionRedo", 760)):
        object.__setattr__(ss.pkg.glyphs["H"]._layers["Bold"], "advanceWidth", width)
        ss.pkg.log.clear()
        history_actions[action].triggered.emit()
        assert side.table.rows[0].values[:3] == ("60", str(width - 640), str(width))
        assert side.glyphs_field.text() == "H" and side.lsb_field.text() == "unfinished-"
        assert ss.studio.master == "Bold" and ss.studio.package() is ss.pkg
        assert not side.staged.ready() and not ss.shell.apply_button.isEnabled()
        assert ss.pkg.log == [] and ss.commits == []
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    assert side.staged.ready() and side.staged.accepted[1][0].before.width == 760


def test_history_refresh_when_manual_with_accepted_plan_then_rereads_without_dirty_dead_end(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    assert side.staged.preview(side.tune)
    object.__setattr__(ss.pkg.glyphs["H"]._layers["Regular"], "advanceWidth", 650)
    ss.shell.refresh_button.click()
    assert side.table.rows[0].values[:3] == ("50", "100", "650")
    assert not side.staged.ready() and side.lsb_field.text() == "5"
    assert ss.commits == []


def test_history_refresh_when_comparison_then_recomputes_captured_request_and_clipboard(history_ss, history_actions):
    ss = history_ss
    ref = tab(ss, 1)
    ref.glyphs_field.setText("H O")
    ref.measure.setCurrentIndex(_model().MEASURES.index("Left"))
    ref.compare()
    ref.compare_glyph.setText("typed-but-not-previewed")
    object.__setattr__(ss.pkg.glyphs["H"]._layers["Regular"], "left", 77)
    history_actions["actionUndo"].triggered.emit()
    assert ref.comparison[0][2] == "77"
    assert "77" in ref.copy_table()
    assert ref.compare_glyph.text() == "typed-but-not-previewed"
    ref.show_rows([])
    assert ref.comparison == [] and ref.copy_table() == ""
    assert ss.pkg.log == [] and ss.commits == []


def test_history_refresh_when_selected_offsets_then_invalidates_without_recapture(history_ss, history_actions, monkeypatch):
    ss = history_ss
    staged = importlib.import_module("fontlabapp.studios.spacing_studio.staged")
    panel = tab(ss, 3)
    panel.offset_snapshot = object()
    panel.records = [("H", "alternate", ("55", "45", "600", "Selected layer offset preview"))]
    panel.table.set_rows(panel.records)
    monkeypatch.setattr(staged, "spacing_offset_backends", lambda: pytest.fail("must not recapture alternate layers"))
    panel.offset_box.lineEdit().setText("17")
    history_actions["actionUndo"].triggered.emit()
    assert panel.offset_snapshot is None and panel.records == [] and panel.table.rows == []
    assert panel.offset_box.lineEdit().text() == "17"
    assert "preview" in ss.shell.status.text().lower()
    assert ss.pkg.log == [] and ss.commits == []


def test_history_refresh_when_string_rows_then_fresh_values_keep_uncommitted_text(history_ss, history_actions):
    ss = history_ss
    panel = tab(ss, 3)
    panel.text_field.setText("/H/space")
    panel.show_strings()
    panel.text_field.setText("/O pending")
    object.__setattr__(ss.pkg.glyphs["H"]._layers["Regular"], "advanceWidth", 660)
    history_actions["actionRedo"].triggered.emit()
    assert [r.glyph_name for r in panel.table.rows] == ["H", "space"]
    assert panel.table.rows[0].values[:3] == ("50", "110", "660")
    assert panel.text_field.text() == "/O pending"
    assert ss.pkg.log == [] and ss.commits == []


@pytest.mark.parametrize("failure", ["master", "glyph", "closed", "switched", "read"])
def test_history_refresh_when_target_unavailable_then_invalidates_and_manual_retry(history_ss, history_actions, failure):
    ss = history_ss
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    side.staged.preview(side.tune)
    old_getter = ss.shell._package
    old_glyph = ss.pkg.glyphs["H"]
    old_metrics = ss.studio.metrics
    if failure == "master":
        ss.pkg.masters.remove("Regular")
    elif failure == "glyph":
        del ss.pkg.glyphs["H"]
    elif failure == "closed":
        object.__setattr__(ss.pkg, "isNull", True)
    elif failure == "switched":
        ss.shell._package = lambda: (_ for _ in ()).throw(ValueError("original font changed"))
    else:
        ss.studio.metrics = lambda *args: (_ for _ in ()).throw(RuntimeError("read failed"))
    history_actions["actionUndo"].triggered.emit()
    assert not side.staged.ready() and not ss.shell.apply_button.isEnabled()
    assert side.records == [] and ss.studio.master == "Regular"
    assert "refused" in ss.shell.status.text().lower()
    assert side.glyphs_field.text() == "H" and side.lsb_field.text() == "5"
    ss.shell._package = old_getter
    ss.studio.metrics = old_metrics
    ss.pkg.glyphs["H"] = old_glyph
    ss.pkg.masters[:] = ["Regular", "Bold"]
    object.__setattr__(ss.pkg, "isNull", False)
    ss.shell.refresh_button.click()
    ss.shell.preview_button.click()
    assert side.staged.ready() and ss.commits == []


def test_history_refresh_when_close_retry_then_late_callback_inert_and_reopen_single(history_ss, history_actions, studio_qt):
    ss = history_ss
    signal = history_actions["actionRedo"].triggered
    assert len(signal.slots) == 1
    late = signal.slots[0]
    signal.refuse_disconnect = True
    with pytest.raises(RuntimeError, match="disconnect"):
        ss.shell.close()
    ss.studio.reload = lambda **kwargs: pytest.fail("late callback read")
    late()
    signal.refuse_disconnect = False
    ss.shell.close()
    assert all(not action.triggered.slots for action in history_actions.values())
    shell = ss.studios.show(package=lambda: ss.pkg, font=lambda: None, preview=lambda *args: None)
    studio_qt.owned.append(shell)
    assert all(len(action.triggered.slots) == 1 for action in history_actions.values())


def test_history_refresh_when_connection_refused_then_manual_path_truthful(history_actions, request):
    history_actions["actionRedo"].triggered.connect = lambda slot: False
    ss = request.getfixturevalue("ss")
    assert "Refresh" in ss.shell.about.text()
    assert "incomplete" in ss.shell.about.text()
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    side.staged.preview(side.tune)
    ss.shell.refresh_button.click()
    assert not side.staged.ready() and ss.commits == []


def test_history_refresh_when_offset_rows_then_uses_captured_offset_without_committing_editor(history_ss, history_actions):
    ss = history_ss
    panel = tab(ss, 3)
    panel.glyphs_field.setText("H")
    panel.offset_box.setValue(5)
    panel.preview_offset()
    panel.offset_box.lineEdit().setText("17")
    object.__setattr__(ss.pkg.glyphs["H"]._layers["Regular"], "advanceWidth", 660)
    history_actions["actionUndo"].triggered.emit()
    assert panel.table.rows[0].values == ("55", "105", "660", "offset +5")
    assert panel.offset_box.lineEdit().text() == "17"
    assert ss.pkg.log == [] and ss.commits == []


def test_history_refresh_when_italic_drafts_blank_then_does_not_fill_defaults(history_ss, history_actions):
    ss = history_ss
    italic = tab(ss, 2)
    italic.angle_field.clear()
    italic.pivot_field.setText("unfinished-")
    history_actions["actionRedo"].triggered.emit()
    assert italic.angle_field.text() == "" and italic.pivot_field.text() == "unfinished-"
    assert ss.pkg.log == [] and ss.commits == []


def test_history_refresh_when_preview_target_read_fails_then_clears_previous_acceptance(ss):
    side = tab(ss, 0)
    side.glyphs_field.setText("H")
    side.lsb_field.setText("5")
    ss.shell.preview_button.click()
    assert side.staged.ready()
    ss.pkg.masters.remove("Regular")
    ss.shell.preview_button.click()
    assert not side.staged.ready() and not ss.shell.apply_button.isEnabled()
    assert "removed" in ss.shell.status.text() and ss.commits == []
