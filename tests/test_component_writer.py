# this_file: tests/test_component_writer.py
"""Shared component eject and write kernel of the Components scripts (issue 122, T14f).

The FontLab and PythonQt doubles log every native call in one list, so the
tests check the exact protocol: the retained component, data and builder are
read before history; init history; write; stamp; ONE notify(retain + layers
+ glyphs, True); stamp; read-back. They also pin every base refusal of
``copy_problem``. They do not prove native FontLab Undo/Redo behaviour.
"""

import ast
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import fontlabapp.components.writer as cw
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__

LOG: list = []
STAMP = "UTC stamp"
SMOOTH = 0x30  # fake flNode.NodeKind["SmoothMask"]
IDS = iter(range(1000, 10**6))


# ---------------------------------------------------------------- doubles
class Transform:
    def __init__(self, dx=0.0, dy=0.0, affine=True):
        self._dx, self._dy, self.affine = dx, dy, affine

    def dx(self):
        return self._dx

    def dy(self):
        return self._dy

    def isAffine(self):
        return self.affine


class Builder:
    def __init__(self, owner, result=True):
        self.owner, self.result = owner, result
        self.marker = f"builder-{owner}"

    def update(self):
        LOG.append(("refresh", self.owner))
        return self.result


class Data:
    def __init__(self, owner, base="", layer="", note=""):
        self.owner = owner
        self.componentGlyph, self.componentLayer, self.note = base, layer, note
        self.marker = f"data-{owner}"
        self._builder = Builder(owner)

    @property
    def builder(self):
        LOG.append(("read-builder", self.owner))
        return self._builder


class Node:
    def __init__(self, state):
        self.nodeState = state


class Contour:
    def __init__(self, states):
        self._nodes = [Node(s) for s in states]

    def nodes(self):
        return self._nodes


class Shape:
    """A contour shape (``base`` empty) or a component of glyph ``base``."""

    def __init__(self, base="", contours=(), *, name="", note="", layer="",
                 affine=True, composite=False, parts=None):  # fmt: skip
        self.id = next(IDS)
        self.name = name
        self.isComponent = bool(base)
        self.isComposite = composite or bool(base)
        self.transform = Transform(affine=affine)
        self._data = Data(self.id, base, layer, note)
        self.contours = [Contour(states) for states in contours]
        self.contentLocked = True
        self.parts = parts  # the copies that ejectTo returns
        self.marker = f"shape-{self.id}"

    @property
    def shapeData(self):
        LOG.append(("read-data", self.id))
        return self._data

    @property
    def includesList(self):
        return list(self.parts or [])

    def ejectTo(self):
        return [copy_of(part) for part in self.parts or []]


def copy_of(shape):
    """A detached native copy: Smooth recomputed (cleared), name and note lost."""
    copy = Shape(shape._data.componentGlyph, [], layer=shape._data.componentLayer)
    copy.contours = [Contour([n.nodeState & ~SMOOTH | 0x1 for n in c.nodes()])
                     for c in shape.contours]  # fmt: skip
    return copy


class Layer:
    isNull = False

    def __init__(self, glyph, master, shapes=(), *, auto=False):
        self.name = f"{glyph}/{master}"
        self.autoLayer = auto
        self.shapes = list(shapes)
        self.ignore = self.fail = False
        self.update_result = True

    def removeShape(self, shape):
        if self.fail:
            raise RuntimeError("boom write")
        LOG.append(("remove", self.name, shape.id))
        if not self.ignore:
            self.shapes.remove(shape)

    def insertShape(self, index, shape):
        LOG.append(("insert", self.name, index, shape.id))
        if not self.ignore:
            self.shapes.insert(index, shape)

    def changed(self):
        LOG.append(("changed", self.name))

    def update(self):
        return self.update_result

    def checkInitHistoryState(self, flag):
        LOG.append(("init", self.name))


class Glyph:
    isNull = False

    def __init__(self, name, **layers):
        self.name = name
        self.by_master = {
            m: Layer(name, m, shapes, auto=m.endswith("auto")) for m, shapes in layers.items()
        }

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


class Package:
    def __init__(self, *glyphs):
        self.glyphs = {g.name: g for g in glyphs}

    def findName(self, name):
        return self.glyphs.get(name)


class Native:
    """The ``fontlab`` double."""

    def __init__(self):
        self.pending: list = []
        self.flGlyph = NS(updatedFgGlyphs=lambda: tuple(self.pending))
        self.flNode = NS(NodeKind={"SmoothMask": SMOOTH})
        self.items: list = []

    def flItems(self):
        return self

    def notifyChangesApplied(self, title, items, *flags):
        self.items = list(items)
        LOG.append(("notify", title, [getattr(i, "marker", None) or i.name for i in items], flags))


@pytest.fixture
def native(monkeypatch):
    """Install the FontLab and PythonQt doubles; clear the call log."""
    LOG.clear()
    fake = Native()
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: STAMP)))
    monkeypatch.setitem(sys.modules, "fontlab", fake)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    return fake


def facts(*records):
    return history.auto_facts(records)


def accented():
    """A (one contour) + Aacute = component of A on master L."""
    a = Glyph("A", L=[Shape(contours=[[0, SMOOTH | 0x4]], name="bowl", note="keep")])
    component = Shape("A")
    component.parts = a.by_master["L"].shapes
    aacute = Glyph("Aacute", L=[Shape(contours=[[0]]), component])
    return Package(a, aacute), aacute, component


def history_events():
    return [e for e in LOG if e[0] in {"init", "stamp", "notify"}]


# ---------------------------------------------------------------- small helpers
def test_helpers_when_called_then_exact_texts():
    assert (cw.half_up(14.5), cw.half_up(-14.5)) == (15, -14)
    assert (cw.plural(1, "layer"), cw.plural(2, "layer")) == ("1 layer", "2 layers")
    assert cw.fmt(700.0) == "700" and cw.offset_text((40.0, -12.5)) == "40, -12.5"
    assert cw.shown([str(i) for i in range(9)]) == "0, 1, 2, 3, 4, 5, 6, 7 …"
    assert cw.parts_text(1, 0) == "1 contour"
    assert cw.parts_text(2, 1) == "2 contours + 1 component"
    shape = Shape("A")
    shape.transform = Transform(3.0, -4.0)
    assert cw.offset(shape) == (3.0, -4.0)
    assert cw.MAX_DEPTH == 64


def test_shape_index_when_shape_gone_then_value_error_asks_for_reload(native):
    _, aacute, component = accented()
    layer = aacute.by_master["L"]
    assert cw.shape_index(layer, component.id) == 1
    with pytest.raises(ValueError, match="changed since the scan; press Reload selection"):
        cw.shape_index(layer, -1)


def test_layer_of_when_missing_or_null_then_none_and_nothing_created():
    glyph = Glyph("A", L=[])
    assert cw.layer_of(glyph, "L") is glyph.by_master["L"]
    assert cw.layer_of(glyph, "B") is None and "B" not in glyph.by_master
    glyph.by_master["L"].isNull = True
    assert cw.layer_of(glyph, "L") is None


# ---------------------------------------------------------------- collect
def test_collect_when_layers_auto_blocked_or_missing_then_only_plain_layers_in_work():
    plain = Glyph("A", L=[], Lauto=[])
    blocked = Glyph("B", L=[])

    def planner(glyph, master, layer):
        if glyph.name == "B":
            return [cw.Change("x", "", "", "edit"), cw.Change("y", "", "", problem="bad")]
        return [cw.Change("x", "", "new", "edit"), cw.Change("note", "", "shown only")]

    plan = cw.collect([plain, blocked], ["L", "Lauto", "Missing"], planner)
    assert plan.work == [(plain, plain.by_master["L"], ["edit"])]
    assert plan.edits == 1
    assert plan.skipped == ["A/Lauto"]
    assert ("A · Lauto", cw.Change("2 rows", "", "auto layer, skipped")) in plan.rows
    assert plan.problems == ["B · L: bad"]
    assert [label for label, _ in plan.rows] == ["A · L", "A · L", "A · Lauto", "B · L", "B · L"]


# ---------------------------------------------------------------- refusals before history
def test_require_safe_when_updates_are_queued_then_writes_and_discloses(native, capsys):
    _, aacute, component = accented()
    native.pending.append(41)
    layer = aacute.by_master["L"]
    work = [(aacute, layer, [component.id])]
    cw.require_safe(work, facts())
    result = cw.apply_work(work, "Decompose", facts(), cw.EjectEditor(unlock=True))
    assert component not in layer.shapes and native.pending == [41]
    assert result["pending_updates"] == (41,) and "8537" in result["pending_note"]
    import fontlabapp.core.edit_guards as guards
    guards.disclose(result)
    output = capsys.readouterr().out
    assert "(41,)" in output and result["pending_note"] in output


def test_require_safe_when_glyph_is_base_of_auto_composite_then_refuses_once(native):
    _, aacute, _ = accented()
    work = [(aacute, aacute.by_master["L"], [1]), (aacute, aacute.by_master["L"], [2])]
    found = facts(("Aacutedot", True, ("Aacute",)))
    assert cw.blocked_rows(work, found) == [
        ("Aacute", cw.Change("blocked", "", "", problem="base of auto Aacutedot"))
    ], "one row per glyph, not per layer"
    with pytest.raises(ValueError, match=r"cannot undo edits to these glyphs: Aacute: base of auto Aacutedot\. Choose"):
        cw.require_safe(work, found)
    cw.require_safe(work, facts(("Aacute", False, ("A",))))
    assert LOG == []


# ---------------------------------------------------------------- copy_problem
def chain(levels, last=None):
    """G0 -> G1 -> ... -> G<levels>: each glyph holds one component of the next."""
    glyphs = [Glyph(f"G{i}", L=[Shape(f"G{i + 1}")]) for i in range(levels)]
    glyphs.append(last or Glyph(f"G{levels}", L=[Shape(contours=[[0]])]))
    return Package(*glyphs), glyphs[0].by_master["L"].shapes[0]


@pytest.mark.parametrize(
    ("levels", "expected"),
    [(63, ""), (64, "components nest more than 64 levels")],
)
def test_copy_problem_when_nesting_is_at_the_depth_limit_then_last_accepted_first_refused(levels, expected):
    package, shape = chain(levels)
    assert cw.copy_problem(package, ("G0", "L"), shape, "L") == expected


def test_copy_problem_when_components_loop_then_refused():
    a = Glyph("A", L=[Shape("B")])
    b = Glyph("B", L=[Shape("A")])
    package = Package(a, b)
    assert cw.copy_problem(package, ("A", "L"), a.by_master["L"].shapes[0], "L") == (
        "components loop through A"
    )
    x = Glyph("X", L=[Shape("A")])
    package.glyphs["X"] = x
    assert cw.copy_problem(package, ("X", "L"), x.by_master["L"].shapes[0], "L") == (
        "components loop through A"
    ), "a loop below the edited glyph"


def test_copy_problem_when_base_is_shared_twice_then_visited_once_and_accepted():
    dot = Glyph("dot", L=[Shape(contours=[[0]])])
    colon = Glyph("colon", L=[Shape("dot"), Shape("dot")])
    package = Package(dot, colon)
    shape = Shape("colon")
    assert cw.copy_problem(package, ("X", "L"), shape, "L") == ""


@pytest.mark.parametrize(
    ("make", "expected"),
    [
        (lambda: Glyph("B", L=[Shape(contours=[[0]], affine=False)]),
         "base B holds a shape that cannot be copied"),
        (lambda: Glyph("B", L=[Shape(contours=[[0]], composite=True)]),
         "base B holds a shape that cannot be copied"),
        (lambda: Glyph("B", Other=[]), "base B has no plain layer L"),
        (lambda: Glyph("B", L=[], Lauto=[]), "base B has no plain layer Lauto"),
        (lambda: Glyph("Other", L=[]), "base B has no plain layer L"),
    ],
    ids=["inner-perspective", "non-component-composite", "no-layer", "auto-layer", "no-glyph"],
)  # fmt: skip
def test_copy_problem_when_base_cannot_be_copied_then_exact_reason(make, expected):
    package = Package(make())
    layer = "Lauto" if "Lauto" in expected else ""
    shape = Shape("B", layer=layer)
    assert cw.copy_problem(package, ("A", "L"), shape, "L") == expected


def test_copy_problem_when_reason_is_one_level_down_then_reported():
    package, shape = chain(2, last=Glyph("G2", L=[Shape(contours=[[0]], affine=False)]))
    assert cw.copy_problem(package, ("G0", "L"), shape, "L") == (
        "base G2 holds a shape that cannot be copied"
    )


def test_copy_problem_when_outer_transform_is_perspective_then_decompose_in_fontlab():
    package, shape = chain(1)
    shape.transform = Transform(affine=False)
    assert cw.copy_problem(package, ("G0", "L"), shape, "L") == (
        "perspective transform: decompose it in FontLab"
    )


def test_part_counts_when_base_has_contours_and_components_then_counts_them():
    base = Glyph("B", L=[Shape(contours=[[0], [0]]), Shape(contours=[[0]]), Shape("C")], X=[])
    package = Package(base)
    assert cw.part_counts(package, Shape("B"), "L") == (3, 1)
    assert cw.part_counts(package, Shape("B", layer="X"), "L") == (0, 0)
    assert cw.part_counts(package, Shape("missing"), "L") == (0, 0)


# ---------------------------------------------------------------- eject
def test_keep_raw_state_when_copied_then_smooth_bits_name_and_note_back_source_untouched(native):
    source = Shape(contours=[[SMOOTH | 0x4, 0x8]], name="bowl", note="keep")
    copy = copy_of(source)
    cw.keep_raw_state(source, copy)
    assert [n.nodeState for n in copy.contours[0].nodes()] == [SMOOTH | 0x4 | 0x1, 0x8 | 0x1]
    assert copy.name == "bowl" and copy._data.note == "keep"
    assert [n.nodeState for n in source.contours[0].nodes()] == [SMOOTH | 0x4, 0x8]
    assert (source.name, source._data.note) == ("bowl", "keep")


def test_keep_raw_state_when_source_is_component_then_no_node_walk(monkeypatch):
    monkeypatch.delitem(sys.modules, "fontlab", raising=False)
    source, copy = Shape("C", name="inner"), Shape("C")
    cw.keep_raw_state(source, copy)  # no native module needed: returns before the mask
    assert copy.name == "inner"


def test_eject_when_builder_refuses_then_runtime_error(native):
    _, _, component = accented()
    component._data._builder.result = False
    with pytest.raises(RuntimeError, match="could not refresh component A"):
        cw.eject(component)


def test_eject_when_copy_count_differs_then_runtime_error(native):
    _, _, component = accented()
    component.ejectTo = list
    with pytest.raises(RuntimeError, match="could not copy the parts of A"):
        cw.eject(component)


@pytest.mark.parametrize("unlock", [True, False])
def test_eject_editor_prepare_when_unlock_then_only_new_contours_unlocked(native, unlock):
    inner = Shape("C")
    contour = Shape(contours=[[0]])
    outer = Shape("B", parts=[contour, inner])
    layer = Layer("X", "L", [outer])
    steps = cw.EjectEditor(unlock=unlock).prepare(layer, [outer.id])
    [(shape, copies, placed)] = steps
    assert shape is outer and placed == [] and len(copies) == 2
    assert copies[0].contentLocked is (not unlock)
    assert copies[1].contentLocked is True, "a component copy is never unlocked"
    assert LOG[:3] == [("read-data", outer.id), ("read-builder", outer.id), ("refresh", outer.id)], (
        "the cache refresh comes before the copy"
    )


# ---------------------------------------------------------------- apply_work
def test_apply_work_when_ejected_then_retained_first_deep_and_read_before_history(native):
    _, aacute, component = accented()
    layer = aacute.by_master["L"]
    work = [(aacute, layer, [component.id])]
    result = cw.apply_work(work, "Decompose", facts(), cw.EjectEditor(unlock=True))
    assert result == {"pending_note": "", "edits": 1, "layers": 1, "pending_updates": ()}
    copy = layer.shapes[1]
    assert history_events() == [
        ("init", "Aacute/L"),
        ("init", "Aacute"),
        ("stamp", "Aacute", STAMP),
        ("notify", "Decompose",
         [f"shape-{component.id}", f"data-{component.id}", f"builder-{component.id}",
          "Aacute/L", "Aacute"], (True,)),
        ("stamp", "Aacute", STAMP),
    ]  # fmt: skip
    assert native.items[:3] == [component, component._data, component._data._builder]
    first_init = LOG.index(("init", "Aacute/L"))
    builder_reads = [i for i, e in enumerate(LOG) if e == ("read-builder", component.id)]
    assert len(builder_reads) == 2, "one read for the cache refresh, one for retain"
    assert max(builder_reads) < first_init, "the retained builder is read before history opens"
    assert LOG.index(("remove", "Aacute/L", component.id)) > first_init
    assert ("insert", "Aacute/L", 1, copy.id) in LOG and ("changed", "Aacute/L") in LOG
    assert component not in layer.shapes and copy.name == "bowl" and copy.contentLocked is False
    assert [n.nodeState for n in copy.contours[0].nodes()] == [0x1, SMOOTH | 0x4 | 0x1]


class InPlaceEditor(cw.Editor):
    """An in-place writer that removes nothing."""

    def write(self, layer, steps):
        LOG.append(("move", layer.name, tuple(steps)))


def test_apply_work_when_nothing_is_removed_then_two_argument_notify(native):
    _, aacute, _ = accented()
    work = [(aacute, aacute.by_master["L"], ["e1", "e2"])]
    assert cw.apply_work(work, "Move", facts(), InPlaceEditor()) == {"pending_note": "", "edits": 2, "layers": 1, "pending_updates": ()}
    assert history_events() == [
        ("init", "Aacute/L"),
        ("init", "Aacute"),
        ("stamp", "Aacute", STAMP),
        ("notify", "Move", ["Aacute/L", "Aacute"], ()),
        ("stamp", "Aacute", STAMP),
    ]
    assert ("move", "Aacute/L", ("e1", "e2")) in LOG


def test_apply_work_when_work_is_empty_then_zeros_and_no_native_call(native):
    assert cw.apply_work([], "Move", facts(), InPlaceEditor()) == {"edits": 0, "layers": 0, "pending_updates": (), "pending_note": ""}
    assert LOG == []


def test_apply_work_when_font_keeps_component_then_did_not_store(native):
    _, aacute, component = accented()
    layer = aacute.by_master["L"]
    layer.ignore = True
    with pytest.raises(RuntimeError, match=r"did not store 1 change\(s\): Aacute/L/A\. Check those layers"):
        cw.apply_work([(aacute, layer, [component.id])], "Decompose", facts(), cw.EjectEditor(True))
    assert len([e for e in LOG if e[0] == "notify"]) == 1


def test_apply_work_when_write_fails_then_partial_write_error_and_one_notify(native):
    _, aacute, component = accented()
    layer = aacute.by_master["L"]
    layer.fail = True
    with pytest.raises(history.PartialWriteError, match="use Edit > Undo"):
        cw.apply_work([(aacute, layer, [component.id])], "Decompose", facts(), cw.EjectEditor(True))
    assert len([e for e in LOG if e[0] == "notify"]) == 1, "the partial edit stays one Undo step"


def test_apply_work_when_layer_update_refused_then_partial_write_error(native):
    _, aacute, _ = accented()
    layer = aacute.by_master["L"]
    layer.update_result = False
    with pytest.raises(history.PartialWriteError, match="use Edit > Undo") as caught:
        cw.apply_work([(aacute, layer, ["e"])], "Move", facts(), InPlaceEditor())
    assert "could not update layer Aacute/L" in str(caught.value.errors[0])


def test_apply_work_when_glyph_is_refused_then_no_history(native):
    _, aacute, component = accented()
    with pytest.raises(ValueError, match="Refused"):
        cw.apply_work([(aacute, aacute.by_master["L"], [component.id])], "Decompose",
                      facts(("Aacute", True, ())), cw.EjectEditor(True))  # fmt: skip
    assert history_events() == []


# ---------------------------------------------------------------- offset writer
class Matrix:
    """A QTransform double: m11, m12, m21, m22, dx, dy."""

    def __init__(self, m11=1.0, m12=0.0, m21=0.0, m22=1.0, dx=0.0, dy=0.0, affine=True):
        self.values, self.affine = (m11, m12, m21, m22, dx, dy), affine

    def m11(self):
        return self.values[0]

    def m12(self):
        return self.values[1]

    def m21(self):
        return self.values[2]

    def m22(self):
        return self.values[3]

    def dx(self):
        return self.values[4]

    def dy(self):
        return self.values[5]

    def isAffine(self):
        return self.affine


def moved(shape, matrix):
    shape.transform = matrix
    shape.changed = lambda: LOG.append(("shape-changed", shape.id))
    return shape


@pytest.mark.parametrize(
    ("matrix", "plain"),
    [
        (Matrix(dx=40, dy=-12), True),
        (Matrix(m11=1 + 1e-7), True),
        (Matrix(m11=1.5), False),
        (Matrix(m22=-1), False),
        (Matrix(m12=0.2), False),
        (Matrix(m21=0.2), False),
        (Matrix(affine=False), False),
    ],
    ids=["translation", "within-epsilon", "scale", "mirror", "slant-12", "slant-21", "perspective"],
)
def test_plain_move_when_transform_is_checked_then_only_pure_translation(matrix, plain):
    assert cw.plain_move(moved(Shape("A"), matrix)) is plain


def test_move_editor_when_applied_then_offset_set_matrix_kept_and_read_back(native, monkeypatch):
    qt = NS(QtCore=sys.modules["PythonQt"].QtCore, QtGui=NS(QTransform=Matrix))
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    component = moved(Shape("acute"), Matrix(m11=2.0, m12=0.5, dx=1, dy=2))
    glyph = Glyph("Aacute", L=[Shape(contours=[[0]]), component])
    layer = glyph.by_master["L"]
    work = [(glyph, layer, [(component.id, (150.0, 200.0))])]
    result = cw.apply_work(work, "Align", facts(), cw.MoveEditor())
    assert result == {"pending_note": "", "edits": 1, "layers": 1, "pending_updates": ()}
    assert component.transform.values == (2.0, 0.5, 0.0, 1.0, 150.0, 200.0)
    assert layer.shapes[1] is component, "edited in place, never copied"
    assert ("shape-changed", component.id) in LOG
    assert history_events()[3] == ("notify", "Align", ["Aacute/L", "Aacute"], ())


def test_move_editor_when_font_keeps_old_offset_then_did_not_store(native):
    component = moved(Shape("acute"), Matrix(dx=1, dy=2))
    layer = Layer("Aacute", "L", [component])
    editor = cw.MoveEditor()
    prepared = [(layer, editor.prepare(layer, [(component.id, (150.0, 2.0))]))]
    assert editor.check(prepared) == ["Aacute/L/acute"]
    assert editor.retain(prepared[0][1]) == [], "an in-place move removes nothing"
    with pytest.raises(ValueError, match="Reload selection"):
        editor.prepare(layer, [(-1, (0.0, 0.0))])


def test_apply_work_when_parsed_then_one_geometry_commit_with_retain_and_read_back():
    import fontlabapp.masters.layers.writer as lw

    assert cw.apply_work is lw.apply_work, "component_writer re-exports the generic kernel"
    tree = ast.parse(Path(lw.__file__).read_text(encoding="utf-8"))
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "apply_work")
    calls = [n for n in ast.walk(func) if isinstance(n, ast.Call) and ast.unparse(n.func) == "history.commit"]
    assert len(calls) == 1
    keywords = {k.arg: ast.unparse(k.value) for k in calls[0].keywords}
    assert keywords["operation"] == "'geometry'" and keywords["retain"] == "retain"
    assert "read_back" in keywords


def test_module_when_cold_imported_then_only_stdlib_and_nothing_native():
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.components.writer
lazy = {'fontlabapp.guides.inspect.model', 'fontlabapp.core.scripting', 'fontlab', 'PythonQt'}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
