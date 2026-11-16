# this_file: tests/test_anchor_writer.py
"""Shared anchor plan and write kernel of the Anchors scripts (issue 122, T14c).

The FontLab and PythonQt doubles log every native call in one list, so the
tests check the exact protocol: refusals before history, init history,
write, stamp, ONE notify(layers + glyphs), stamp, read-back. They do not
prove native FontLab Undo/Redo behaviour.
"""

import ast
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import fontlabapp.anchors.copy.model as anchor_copy  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.anchors.writer as aw
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402

LOG: list = []
STAMP = "UTC stamp"


# ---------------------------------------------------------------- doubles
class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Pin:
    def __init__(self, name="", x=0.0, y=0.0, appearance=0):
        self.name, self.appearance, self.anchor = name, appearance, True
        self.expressionX = self.expressionY = ""
        self._point = Point(x, y)
        self.layer = None

    @property
    def point(self):
        return self._point

    @point.setter
    def point(self, value):
        if self.layer is not None and self.layer.ignore:
            return
        if self.layer is not None and self.layer.rounding:
            value = Point(round(value.x()), round(value.y()))
        self._point = value


class Layer:
    isNull = False

    def __init__(self, glyph, master, pins=(), *, auto=False):
        self.name = f"{glyph}/{master}"
        self.autoLayer = auto
        self.ignore = self.rounding = self.fail = False
        self.anchors = []
        for pin in pins:
            self.attach(pin)

    def attach(self, pin):
        pin.layer = self
        self.anchors.append(pin)

    def addAnchor(self, pin):
        if self.fail:
            raise RuntimeError("boom write")
        LOG.append(("add", self.name, pin.name))
        self.attach(pin)

    def removeAnchor(self, pin):
        LOG.append(("remove", self.name, pin.name))
        self.anchors = [p for p in self.anchors if p is not pin]

    def checkInitHistoryState(self, flag):
        LOG.append(("init", self.name))


class Glyph:
    isNull = False

    def __init__(self, name, **layers):
        self.name = name
        self.by_master = {m: Layer(name, m, pins, auto=m.endswith("auto")) for m, pins in layers.items()}

    def findLayer(self, master):
        return self.by_master.get(master)

    def checkInitHistoryState(self, flag):
        LOG.append(("init", self.name))

    @property
    def lastModified(self):
        return None

    @lastModified.setter
    def lastModified(self, value):
        LOG.append(("stamp", self.name, value))


class Native:
    """The ``fontlab`` double."""

    def __init__(self):
        self.pending: list = []
        self.fail_notify = False
        self.flGlyph = NS(updatedFgGlyphs=lambda: tuple(self.pending))

    def flPinPoint(self, point):
        return Pin("", point.x(), point.y())

    def flItems(self):
        return self

    def notifyChangesApplied(self, title, items):
        if self.fail_notify:
            raise RuntimeError("boom notify")
        LOG.append(("notify", title, [i.name for i in items]))


@pytest.fixture
def native(monkeypatch):
    """Install the FontLab and PythonQt doubles; clear the call log."""
    LOG.clear()
    fake = Native()
    qt = NS(QtCore=NS(QPointF=Point, QDateTime=NS(currentDateTimeUtc=lambda: STAMP)))
    monkeypatch.setitem(sys.modules, "fontlab", fake)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    return fake


def facts(*records):
    return history.auto_facts(records)


NONE = facts()


def points(layer):
    return {p.name: (p.point.x(), p.point.y()) for p in layer.anchors}


# ---------------------------------------------------------------- small pure parts
def test_half_up_when_halves_then_round_towards_plus_infinity():
    assert [aw.half_up(v) for v in (14.5, -14.5, 0.5, -0.5, 2.4)] == [15, -14, 1, 0, 2]


def test_plural_fmt_and_parse_names_when_called_then_exact_texts():
    assert aw.plural(1, "layer") == "1 layer" and aw.plural(0, "layer") == "0 layers"
    assert aw.fmt(700.0) == "700" and aw.fmt(698.4) == "698.4" and aw.fmt(-4) == "-4"
    assert aw.parse_names(" top, bottom;ogonek ,, ;") == ["top", "bottom", "ogonek"]
    assert aw.parse_names("") == []


def test_anchor_points_when_fractional_then_raw_values_and_last_name_wins():
    layer = Layer("a", "L", [Pin("top", 203.4, 698.6), Pin("x", 1, 2), Pin("x", 3, 4)])
    assert aw.raw_point(layer.anchors[0]) == (203.4, 698.6)
    assert aw.anchor_points(layer) == {"top": (203.4, 698.6), "x": (3.0, 4.0)}


def test_duplicated_and_refusal_when_names_repeat_then_sorted_blocking_rows():
    layer = Layer("a", "L", [Pin("top"), Pin("top"), Pin("b"), Pin("b"), Pin("c")])
    assert aw.duplicated(layer, ["top", "c", "b", "top"]) == ["b", "top"]
    rows = aw.refusal(["top"])
    assert rows == [aw.Change("top", "", "", problem="several anchors named top; use Duplicates Finder")]


def test_layer_of_when_missing_or_null_then_none_and_never_created():
    glyph = Glyph("a", L=[])
    assert aw.layer_of(glyph, "L") is glyph.by_master["L"]
    assert aw.layer_of(glyph, "Bold") is None
    glyph.by_master["L"].isNull = True
    assert aw.layer_of(glyph, "L") is None
    assert set(glyph.by_master) == {"L"}


def test_shown_when_more_than_limit_then_ellipsis():
    names = [f"g{i}" for i in range(9)]
    assert aw.shown(names[:8]) == ", ".join(names[:8])
    assert aw.shown(names) == ", ".join(names[:8]) + " …"


# ---------------------------------------------------------------- collect
def test_collect_when_auto_problem_and_missing_layers_then_each_listed_correctly():
    a = Glyph("a", L=[Pin("top", 1, 1)], Bauto=[Pin("top", 1, 1)])
    b = Glyph("b", L=[Pin("top", 2, 2)])

    def planner(glyph, master, layer):
        if glyph.name == "b":
            return [aw.Change("top", "", "", problem="bad")]
        return [aw.Change("top", "1, 1", "0, 1", ("set", "top", (0, 1)))]

    masters = (m for m in ["L", "Bauto", "Missing"])  # a one-pass iterable
    plan = aw.collect([a, b], masters, planner)
    assert [(g.name, layer.name, edits) for g, layer, edits in plan.work] == [
        ("a", "a/L", [("set", "top", (0, 1))])
    ]
    assert plan.skipped == ["a/Bauto"]
    assert plan.problems == ["b · L: bad"], "every glyph sees every master"
    labels = [(label, change.new) for label, change in plan.rows]
    assert labels == [("a · L", "0, 1"), ("a · Bauto", "auto layer, skipped"), ("b · L", "")]
    assert plan.rows[1][1].name == "1 anchor" and plan.anchors == 1


def test_collect_when_rows_have_no_edit_then_layer_not_in_work():
    glyph = Glyph("a", L=[Pin("top")])
    plan = aw.collect([glyph], ["L"], lambda g, m, layer: [aw.Change("top", "x", "x")])
    assert plan.work == [] and len(plan.rows) == 1 and plan.anchors == 0


# ---------------------------------------------------------------- refusals
def test_blocked_rows_when_owner_or_chained_base_then_reasons():
    a, e, x = Glyph("a", L=[]), Glyph("e", L=[]), Glyph("x", L=[])
    found = facts(("a", True, ()), ("ebar", False, ("e",)), ("ebaracute", True, ("ebar",)))
    work = [(g, g.by_master["L"], [("remove", "top", None)]) for g in (a, e, x)]
    rows = aw.blocked_rows(work, found)
    assert [(name, change.name, change.problem) for name, change in rows] == [
        ("a", "blocked", "has auto layers"),
        ("e", "blocked", "base of auto ebaracute"),
    ]


def test_require_safe_when_existing_anchor_moves_to_origin_then_redo_refusal(native):
    glyph = Glyph("a", L=[Pin("top", 5, 5)])
    layer = glyph.by_master["L"]
    with pytest.raises(ValueError) as raised:
        aw.require_safe([(glyph, layer, [("set", "top", (0, 0))])], NONE)
    assert str(raised.value) == aw.ORIGIN_ERROR
    assert "Redo" in aw.ORIGIN_ERROR
    aw.require_safe([(glyph, layer, [("set", "new", (0, 0)), ("set", "top", (0, 1))])], NONE)
    aw.require_safe([(glyph, layer, [("set", "top", (0.0, 0.5))])], NONE)
    assert LOG == [], "refusals touch nothing"


def test_require_safe_when_updates_queued_then_writes_discloses_and_keeps_queue(native, capsys):
    native.pending.append(41)
    glyph = Glyph("a", L=[Pin("top", 5, 5)])
    work = [(glyph, glyph.by_master["L"], [("set", "top", (1, 1))])]
    aw.require_safe(work, NONE)
    result = aw.apply_work(work, "Move", NONE)
    assert result["pending_updates"] == (41,) and native.pending == [41]
    assert LOG
    import fontlabapp.core.edit_guards as guards
    guards.disclose(result)
    output = capsys.readouterr().out
    assert result["pending_note"] in output and "8537" in output


def test_require_safe_when_set_name_repeats_then_refuses_but_remove_and_rename_pass(native):
    glyph = Glyph("a", L=[Pin("top", 1, 1), Pin("top", 2, 2)])
    layer = glyph.by_master["L"]
    with pytest.raises(ValueError, match=r"^a: several anchors named top; use Duplicates Finder\.$"):
        aw.require_safe([(glyph, layer, [("set", "top", (3, 3))])], NONE)
    aw.require_safe([(glyph, layer, [("remove", "top", None)])], NONE)
    aw.require_safe([(glyph, layer, [("rename", "top", "up")])], NONE)


def test_require_safe_when_glyph_is_chained_base_of_auto_then_names_it(native):
    glyph = Glyph("a", L=[Pin("top", 1, 1)])
    found = facts(("agrave", False, ("a",)), ("agravedot", True, ("agrave",)))
    with pytest.raises(ValueError) as raised:
        aw.require_safe([(glyph, glyph.by_master["L"], [("remove", "top", None)])], found)
    assert str(raised.value) == (
        "FontLab cannot undo edits to these glyphs: a: base of auto agravedot. "
        "Choose other glyphs."
    )


# ---------------------------------------------------------------- prepare / write / read back
def test_prepare_when_new_pins_then_appearance_from_anchor_copy_and_existing_kept(native):
    existing = Pin("top", 1, 1, appearance=3)
    layer = Layer("a", "L", [existing])
    steps = aw.prepare(
        layer,
        [("set", "top", (2, 3)), ("set", "Bottom", (4, 5)), ("set", "ogonek", (6, 7))],
    )
    assert [s[0] for s in steps] == ["move", "add", "add"]
    assert steps[0][1] is existing and (steps[0][2].x(), steps[0][2].y()) == (2.0, 3.0)
    new = [s[2] for s in steps[1:]]
    assert [(p.name, p.anchor, p.appearance) for p in new] == [
        ("Bottom", True, anchor_copy.APPEARANCE["bottom"]),
        ("ogonek", True, 0),
    ]
    assert existing.appearance == 3 and points(layer) == {"top": (1, 1)}, "nothing written yet"


def test_prepare_when_anchor_copy_table_changes_then_the_same_table_is_used(native, monkeypatch):
    monkeypatch.setitem(anchor_copy.APPEARANCE, "ogonek", 42)
    pin = aw.prepare(Layer("a", "L"), [("set", "ogonek", (1, 1))])[0][2]
    assert pin.appearance == 42, "reuse anchor_copy.APPEARANCE, no private copy"


def test_prepare_and_write_when_remove_and_rename_repeated_names_then_every_pin(native):
    pins = [Pin("top", 1, 1), Pin("top", 2, 2), Pin("b", 3, 3)]
    layer = Layer("a", "L", pins)
    steps = aw.prepare(layer, [("remove", "top", None), ("rename", "b", "c")])
    assert [(s[0], s[1].name) for s in steps] == [("remove", "top"), ("remove", "top"), ("rename", "b")]
    aw.write(layer, steps)
    assert [p.name for p in layer.anchors] == ["c"] and layer.anchors[0] is pins[2]


def test_unstored_when_changed_axis_differs_then_reported_untouched_axis_ignored():
    glyph = Glyph("a", L=[Pin("top", 200, 698.0), Pin("gone"), Pin("new")])
    layer = glyph.by_master["L"]
    before = [{"top": (203.0, 698.4), "gone": (0, 0), "new": (0, 0)}]
    work = [(glyph, layer, [("set", "top", (200, 698.4)), ("remove", "gone", None), ("rename", "x", "new")])]
    assert aw.unstored(work, before) == ["a/gone"], "y untouched: FontLab rounding is no error"
    work = [(glyph, layer, [("set", "top", (201, 698.4)), ("rename", "new", "x")])]
    assert aw.unstored(work, before) == ["a/top", "a/new"]


# ---------------------------------------------------------------- apply_work
def test_apply_work_when_two_layers_then_one_undo_step_in_order(native):
    glyph = Glyph("a", L=[Pin("top", 203, 698)], B=[Pin("top", 214, 700)])
    work = [
        (glyph, glyph.by_master["L"], [("set", "top", (200, 700)), ("set", "new", (1, 2))]),
        (glyph, glyph.by_master["B"], [("remove", "top", None)]),
    ]
    result = aw.apply_work(work, "Round", NONE)
    assert result == {"pending_note": "", "anchors": 3, "layers": 2, "pending_updates": ()}
    assert LOG == [
        ("init", "a/L"),
        ("init", "a/B"),
        ("init", "a"),
        ("add", "a/L", "new"),
        ("remove", "a/B", "top"),
        ("stamp", "a", STAMP),
        ("notify", "Round", ["a/L", "a/B", "a"]),
        ("stamp", "a", STAMP),
    ]
    assert points(glyph.by_master["L"]) == {"top": (200.0, 700.0), "new": (1.0, 2.0)}
    assert glyph.by_master["B"].anchors == []


def test_apply_work_when_empty_then_zero_and_no_history(native):
    assert aw.apply_work([], "Round", NONE) == {"anchors": 0, "layers": 0, "pending_updates": (), "pending_note": ""}
    assert LOG == []


def test_apply_work_when_font_does_not_keep_value_then_names_it_after_one_notify(native):
    glyph = Glyph("a", L=[Pin("top", 203, 698)])
    glyph.by_master["L"].ignore = True
    with pytest.raises(RuntimeError) as raised:
        aw.apply_work([(glyph, glyph.by_master["L"], [("set", "top", (200, 700))])], "Round", NONE)
    assert str(raised.value) == (
        "FontLab did not store 1 change(s): a/top. "
        "Check Preferences > Rounding. Check those layers before you save."
    )
    assert [e[0] for e in LOG] == ["init", "init", "stamp", "notify", "stamp"]


def test_apply_work_when_strong_rounding_moves_untouched_axis_then_no_mismatch(native):
    glyph = Glyph("a", L=[Pin("top", 203, 698.4)])
    glyph.by_master["L"].rounding = True
    result = aw.apply_work([(glyph, glyph.by_master["L"], [("set", "top", (200, 698.4))])], "R", NONE)
    assert result == {"pending_note": "", "anchors": 1, "layers": 1, "pending_updates": ()}
    assert points(glyph.by_master["L"]) == {"top": (200, 698)}


@pytest.mark.parametrize("stage", ["write", "notify"])
def test_apply_work_when_native_step_fails_after_history_then_undo_hint_and_cause(native, stage):
    glyph = Glyph("a", L=[])
    layer = glyph.by_master["L"]
    if stage == "write":
        layer.fail = True
    else:
        native.fail_notify = True
    with pytest.raises(history.PartialWriteError) as raised:
        aw.apply_work([(glyph, layer, [("set", "top", (1, 2))])], "Place", NONE)
    assert str(raised.value) == f"Place did not finish: boom {stage}. {history.UNDO_HINT}"
    assert isinstance(raised.value.__cause__, RuntimeError)
    assert LOG[-1] == ("stamp", "a", STAMP), "history is finished so Edit > Undo works"


def test_apply_work_when_glyph_owns_auto_layer_then_refused_before_history(native):
    glyph = Glyph("a", L=[Pin("top", 1, 1)])
    with pytest.raises(ValueError, match="has auto layers"):
        aw.apply_work([(glyph, glyph.by_master["L"], [("set", "top", (2, 2))])], "R", facts(("a", True, ())))
    assert LOG == []


def test_apply_work_when_parsed_then_one_geometry_commit_with_read_back():
    tree = ast.parse(Path(aw.__file__).read_text(encoding="utf-8"))
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "apply_work")
    nested = {n.name: n for n in ast.walk(func) if isinstance(n, ast.FunctionDef)}
    assert "mutate" in nested and ast.unparse(nested["mutate"].returns) == "None"
    calls = [n for n in ast.walk(func) if isinstance(n, ast.Call) and ast.unparse(n.func) == "history.commit"]
    assert len(calls) == 1
    keywords = {k.arg: ast.unparse(k.value) for k in calls[0].keywords}
    assert keywords["operation"] == "'geometry'" and keywords["read_back"] == "read_back"


@pytest.mark.parametrize("module", ["fontlabapp.anchors.writer", "fontlabapp.anchors.panel.model"])
def test_module_when_cold_imported_then_only_stdlib_and_nothing_heavy(module):
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = f"""
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import {module}
lazy = {{'fontlabapp.anchors.panel.ui', 'fontlabapp.anchors.copy.model', 'fontlabapp.core.scripting', 'fontlabapp.guides.inspect.model'}}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
