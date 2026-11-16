# this_file: tests/test_glyph_creation.py
"""Glyph creation, auto-glyph candidates and the copy generator kernel (issue 122, T14h).

The doubles log every native call in one list: the fontpr ``set_glyph`` tool,
``checkInitHistoryState``, the edits of ``fill``, the stamps and the one
notification. A package double refuses ``addGlyph``, and the ``fontlab``
double has no ``flGlyph`` constructor, so a raw insert fails the test. The
tests prove the call order and the refusals, not native FontLab Undo.
"""

import itertools
import sys
from types import SimpleNamespace as NS

import pytest

import fontlabapp.core.edit_guards as edit_guards
import fontlabapp.glyphs.copies as gc
import fontlabapp.glyphs.creation as cr
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__

LOG: list = []
STAMP = "UTC stamp"
IDS = itertools.count(1000)


# ---------------------------------------------------------------- doubles
class Transform:
    def __init__(self, dx=0.0):
        self._dx = dx

    def m11(self):
        return 1.0

    def m12(self):
        return 0.0

    def m21(self):
        return 0.0

    def m22(self):
        return 1.0

    def dx(self):
        return self._dx

    def dy(self):
        return 0.0


class Shape:
    def __init__(self, contours=(), base=None):
        self.isComponent = base is not None
        self.shapeData = NS(componentGlyph=base or "")
        self.contours = list(contours)
        self.transform = Transform()

    def addContours(self, contours, closed):
        assert isinstance(contours, list) and closed is True
        LOG.append(("addContours", len(contours)))
        self.contours.extend(contours)


class Layer:
    isNull = False

    def __init__(self, name, width=0, shapes=(), auto=False, recipe=""):
        self.name, self.advanceWidth, self.shapes = name, width, list(shapes)
        self.autoLayer, self.recipe, self.anchors = auto, recipe, []

    def checkInitHistoryState(self, level):
        LOG.append(("init", self.name))

    def addShape(self, shape):
        LOG.append(("addShape", self.name))
        self.shapes.append(shape)


class Glyph:
    isNull = False

    def __init__(self, name, layers=()):
        self.name, self.fgGlyphId, self.layers = name, next(IDS), list(layers)

    def findLayer(self, name):
        return next((x for x in self.layers if x.name == name), None)

    def findLayerCreate(self, name):
        raise AssertionError("findLayerCreate adds a layer outside history")

    def checkInitHistoryState(self, level):
        LOG.append(("init", self.name))

    @property
    def lastModified(self):
        return None

    @lastModified.setter
    def lastModified(self, value):
        LOG.append(("stamp", self.name))


class Package:
    def __init__(self, *glyphs, masters=("L", "B")):
        self.id, self.fgId = 7, 40  # object id and FontGate id differ, as in FontLab
        self.masters, self.master = list(masters), masters[0]
        self.glyphs = {g.name: g for g in glyphs}

    def findName(self, name):
        return self.glyphs.get(name)

    def addGlyph(self, glyph):
        raise AssertionError("flPackage.addGlyph is a raw insert outside Undo")


class FontPR:
    """The fontpr double: ``set_glyph(create=True)`` adds the glyph to the package.

    ``fail``: names answered with an error status. ``raises``: name ->
    exception raised by the call (``FontPR.Error`` is fontpr's refusal).
    ``created``: the "created" value of the answer.
    """

    class Error(Exception):
        """fontpr.Error: the tool refused before its command ran."""

    def __init__(self, package):
        self.package, self.calls, self.fail, self.after = package, [], set(), None
        self.raises, self.created, self.drop_parts = {}, True, False

    def call(self, name, **arguments):
        LOG.append(("fontpr", name, arguments["glyph_name"]))
        self.calls.append((name, arguments))
        target = arguments["glyph_name"]
        if target in self.raises:
            raise self.raises[target]
        if target in self.fail:
            return {"status": "error", "error": f"cannot add {target}"}
        data = arguments["glyph_data"]
        layers = [
            Layer(x["name"], x["advanceWidth"], [] if self.drop_parts else [
                Shape(base=e["component"]["glyphName"]) for e in x.get("elements", ())
            ])
            for x in data["layers"]
        ]  # fmt: skip
        self.package.glyphs[target] = Glyph(target, layers)
        if self.after is not None:
            self.after(target)
        return {"status": "ok", "created": self.created}


class Native:
    """The ``fontlab`` double. ``flGlyph`` has no constructor: a raw ``flGlyph()`` fails."""

    def __init__(self):
        self.pending = []
        self.flGlyph = NS(updatedFgGlyphs=lambda: tuple(self.pending))
        self.notified = []

    def flItems(self):
        return self

    def flShape(self):
        return Shape()

    def notifyChangesApplied(self, title, items, *flags):
        LOG.append(("notify", title, [i.name for i in items]))
        self.notified.append(list(items))


@pytest.fixture
def world(monkeypatch):
    LOG.clear()
    native = Native()
    package = Package(
        Glyph("H", [Layer("L", 600, [Shape([NS(name="c1")])]), Layer("B", 640, [Shape([NS(name="c2")])])]),
        Glyph("eacute.sc", [Layer("L", 500, [Shape(base="e")], auto=True), Layer("B", 500, auto=True)]),
        Glyph("aacute.sc", [Layer("L", 500, auto=True, recipe="a.sc+acute")]),
        Glyph("onehalf.tf", [Layer("L", 500, auto=True)]),
        Glyph("e", [Layer("L"), Layer("B")]),
    )
    tools = FontPR(package)
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: STAMP)))
    monkeypatch.setitem(sys.modules, "fontlab", native)
    monkeypatch.setitem(sys.modules, "fontpr", tools)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    return NS(native=native, package=package, tools=tools, facts=facts_of(package))


def facts_of(package):
    return history.auto_facts(
        (g.name, x.autoLayer, tuple(s.shapeData.componentGlyph for s in x.shapes if s.isComponent))
        for g in package.glyphs.values()
        for x in g.layers
    )


def spec(name, widths=(("L", 300), ("B", 320)), codes=()):
    return cr.NewGlyph(name, tuple(widths), tuple(codes))


# ---------------------------------------------------------------- glyph data and the set_glyph call
def test_glyph_data_when_codes_given_then_fontpr_json_shape():
    assert cr.glyph_data(spec("uni03A9", codes=(0x3A9,))) == {
        "name": "uni03A9",
        "layers": [{"name": "L", "advanceWidth": 300}, {"name": "B", "advanceWidth": 320}],
        "unicodes": [0x3A9],
    }
    assert "unicodes" not in cr.glyph_data(spec("A.alt")), "no code point: no unicodes key"


def test_create_glyphs_when_called_then_one_set_glyph_per_glyph_with_fgid(world):
    done = cr.create_glyphs(world.package, [spec("x.alt"), spec("uni03A9", codes=(0x3A9,))], "Make", world.facts)
    assert world.tools.calls == [
        ("set_glyph", {"font_id": 40, "glyph_name": "x.alt", "create": True, "glyph_data": cr.glyph_data(spec("x.alt"))}),
        ("set_glyph", {
            "font_id": 40, "glyph_name": "uni03A9", "create": True,
            "glyph_data": cr.glyph_data(spec("uni03A9", codes=(0x3A9,))),
        }),
    ]  # fmt: skip
    assert [g.name for g in done.glyphs] == ["x.alt", "uni03A9"] and done.mismatches == ()
    assert world.native.notified == [], "no fill: no notification of this script"
    assert [e for e in LOG if e[0] in ("init", "notify", "stamp")] == []


def test_create_glyphs_when_filled_then_one_geometry_commit_with_created_layers_and_glyphs(world, monkeypatch):
    seen = []
    real = history.commit

    def spy(title, layers, glyphs, mutate, **kwargs):
        seen.append((title, [x.name for x in layers], [g.name for g in glyphs], kwargs["operation"]))
        return real(title, layers, glyphs, mutate, **kwargs)

    monkeypatch.setattr(history, "commit", spy)

    def fill(made):
        for glyph in made.values():
            glyph.findLayer("L").addShape(Shape())

    cr.create_glyphs(world.package, [spec("x.alt"), spec("y.alt")], "Make", world.facts, fill=fill)
    assert seen == [("Make", ["L", "B", "L", "B"], ["x.alt", "y.alt"], "geometry")]
    assert LOG == [
        ("fontpr", "set_glyph", "x.alt"), ("fontpr", "set_glyph", "y.alt"),
        ("init", "L"), ("init", "B"), ("init", "L"), ("init", "B"), ("init", "x.alt"), ("init", "y.alt"),
        ("addShape", "L"), ("addShape", "L"),
        ("stamp", "x.alt"), ("stamp", "y.alt"),
        ("notify", "Make", ["L", "B", "L", "B", "x.alt", "y.alt"]),
        ("stamp", "x.alt"), ("stamp", "y.alt"),
    ]  # fmt: skip


def test_create_glyphs_when_called_then_never_raw_add_glyph(world):
    assert "addGlyph" not in cr.create_glyphs.__code__.co_names
    cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts, fill=lambda made: None)
    assert world.package.findName("x.alt") is not None, "created through set_glyph only"


def test_create_glyphs_when_glyph_window_active_then_refused_before_any_creation(world, monkeypatch):
    seen = []

    def refuse(glyphs, *, creates=False, native=None):
        seen.append((tuple(glyphs), creates))
        raise ValueError(edit_guards.CANVAS_TEXT)

    monkeypatch.setattr(edit_guards, "require_history_scope", refuse)
    with pytest.raises(ValueError, match="Switch to the Font window first"):
        cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts)
    assert seen == [((), True)], seen
    assert LOG == [] and world.tools.calls == [], "no set_glyph, no history call"


def test_create_glyphs_when_nothing_then_no_native_call(world):
    assert cr.create_glyphs(world.package, [], "Make", world.facts) == cr.Created((), ())
    assert LOG == []


@pytest.mark.parametrize(
    ("specs", "pending", "text"),
    [
        ([spec("H")], [], "Refused: H exists now"),
        ([spec("x.alt"), spec("x.alt")], [], "Refused: x.alt is listed twice"),
    ],
    ids=["exists", "twice"],
)
def test_create_glyphs_when_refused_then_value_error_before_any_creation(world, specs, pending, text):
    world.native.pending = pending
    with pytest.raises(ValueError, match=text):
        cr.create_glyphs(world.package, specs, "Make", world.facts)
    assert LOG == [] and world.tools.calls == []


def test_create_glyphs_when_rebuild_candidates_then_consent_needed(world, monkeypatch):
    with pytest.raises(ValueError, match="may rebuild auto eacute.sc") as error:
        cr.create_glyphs(world.package, [spec("e.sc")], "Make", world.facts)
    assert cr.REBUILD_LABEL in str(error.value)
    assert world.tools.calls == []
    seen = []
    real = history.commit
    monkeypatch.setattr(history, "commit", lambda *a, **k: seen.append(k["allow_bases"]) or real(*a, **k))
    cr.create_glyphs(world.package, [spec("e.sc")], "Make", world.facts, fill=lambda m: None, allow_rebuild=True)
    assert seen == [True], "the consent goes to the commit as allow_bases"


def test_create_glyphs_when_second_glyph_fails_then_error_names_created_glyphs(world):
    world.tools.fail = {"y.alt"}
    with pytest.raises(history.PartialWriteError) as error:
        cr.create_glyphs(world.package, [spec("x.alt"), spec("y.alt")], "Make", world.facts, fill=lambda m: None)
    text = str(error.value)
    assert "cannot add y.alt" in text and "new glyphs that exist now: x.alt" in text
    assert history.UNDO_HINT in text
    assert [e for e in LOG if e[0] in ("init", "notify")] == [], "no outline step after a failed creation"


def test_create_glyphs_when_name_appears_before_second_call_then_refused_without_overwrite(world):
    world.tools.after = lambda name: world.package.glyphs.setdefault("y.alt", Glyph("y.alt"))
    with pytest.raises(history.PartialWriteError) as error:
        cr.create_glyphs(world.package, [spec("x.alt"), spec("y.alt")], "Make", world.facts, fill=lambda m: None)
    text = str(error.value)
    assert "y.alt exists now; FontLab would replace its layers" in text and "new glyphs that exist now: x.alt" in text
    assert [a["glyph_name"] for _, a in world.tools.calls] == ["x.alt"], "set_glyph(create=True) replaces layers"


def test_create_glyphs_when_fontlab_reports_no_new_glyph_then_partial_error_with_hint(world):
    world.tools.created = False
    with pytest.raises(history.PartialWriteError) as error:
        cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts, fill=lambda m: None)
    assert "FontLab did not report a new glyph x.alt" in str(error.value)
    assert history.UNDO_HINT in str(error.value), "the command may have replaced layers"
    assert world.native.notified == []


@pytest.mark.parametrize("how", ["fontpr.Error", "status"])
def test_create_glyphs_when_first_glyph_refused_then_runtime_error_without_undo_hint(world, how):
    if how == "status":
        world.tools.fail = {"x.alt"}
    else:
        world.tools.raises = {"x.alt": FontPR.Error("Font id not found.")}
    with pytest.raises(RuntimeError) as error:
        cr.create_glyphs(world.package, [spec("x.alt"), spec("y.alt")], "Make", world.facts)
    assert type(error.value) is RuntimeError, "not a PartialWriteError: nothing ran"
    text = str(error.value)
    assert text.startswith("Make did not start: ") and text.endswith("No glyph was added.")
    assert history.UNDO_HINT not in text and "Undo" not in text
    assert len(world.tools.calls) == 1


def test_create_glyphs_when_first_call_times_out_then_partial_error_with_hint(world):
    world.tools.raises = {"x.alt": TimeoutError("no answer")}
    with pytest.raises(history.PartialWriteError) as error:
        cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts)
    assert "no answer" in str(error.value) and history.UNDO_HINT in str(error.value), "unknown outcome"


def test_create_glyphs_when_fill_raises_unexpected_error_then_partial_error_names_glyphs(world):
    def fill(made):
        raise AttributeError("no QDateTime")

    with pytest.raises(history.PartialWriteError) as error:
        cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts, fill=fill)
    assert "no QDateTime" in str(error.value) and "new glyphs that exist now: x.alt" in str(error.value)


@pytest.mark.parametrize("stage", ["before commit", "stamp"])
def test_create_glyphs_when_commit_raises_non_value_error_then_partial_error_names_glyphs(world, monkeypatch, stage):
    def broken(*args, **kwargs):
        raise KeyError(stage)

    monkeypatch.setattr(history, "commit", broken)
    with pytest.raises(history.PartialWriteError, match="new glyphs that exist now: x.alt"):
        cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts, fill=lambda m: None)


def test_create_glyphs_when_glyph_missing_after_call_then_partial_error(world):
    world.tools.after = lambda name: world.package.glyphs.pop(name)
    with pytest.raises(history.PartialWriteError, match="FontLab did not add the glyph x.alt"):
        cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts)


def test_create_glyphs_when_master_layer_missing_then_partial_error_without_commit(world):
    world.tools.after = lambda name: world.package.glyphs[name].layers.pop()
    with pytest.raises(history.PartialWriteError, match="x.alt has no layer B"):
        cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts, fill=lambda m: None)
    assert world.native.notified == []


def test_create_glyphs_when_updates_queued_then_writes_and_reports_before_and_during(world, capsys):
    world.native.pending = [3]
    world.tools.after = lambda name: world.native.pending.append(9)
    result = cr.create_glyphs(world.package, [spec("x.alt")], "Make", world.facts, fill=lambda m: None)
    assert result.pending_updates == (3,)
    assert result.pending_note.count("1 glyph") == 1 and "8537" in result.pending_note
    assert world.native.pending == [3, 9] and result.glyphs
    import fontlabapp.core.edit_guards as guards
    guards.disclose(result)
    output = capsys.readouterr().out
    assert result["pending_note"] in output and "8537" in output


def test_create_glyphs_when_auto_layer_changes_then_mismatch_with_read_back(world):
    def rebuild(name):
        world.package.findName("onehalf.tf").layers[0].advanceWidth = 777

    world.tools.after = rebuild
    done = cr.create_glyphs(world.package, [spec("one.tf")], "Make", world.facts, read_back=lambda: ["mine"],
                            allow_rebuild=True)  # fmt: skip
    assert done.mismatches == (
        "mine",
        "Auto glyph onehalf.tf · L changed after the write; FontLab rebuilt it. Check it.",
    )


# ---------------------------------------------------------------- components in the Add Glyph data (T14i fix 1)
PARTS = (cr.Part("L", "H"), cr.Part("B", "H", 10, -5), cr.Part("L", "e", 300))


def with_parts(name="a.unic", parts=PARTS):
    return cr.NewGlyph(name, (("L", 600), ("B", 640)), (), tuple(parts))


def test_glyph_data_when_components_then_elements_per_layer_in_order():
    assert cr.glyph_data(with_parts()) == {
        "name": "a.unic",
        "layers": [
            {"name": "L", "advanceWidth": 600, "elements": [
                {"component": {"glyphName": "H"}, "transform": {"xOffset": 0.0, "yOffset": 0.0}},
                {"component": {"glyphName": "e"}, "transform": {"xOffset": 300.0, "yOffset": 0.0}},
            ]},
            {"name": "B", "advanceWidth": 640, "elements": [
                {"component": {"glyphName": "H"}, "transform": {"xOffset": 10.0, "yOffset": -5.0}},
            ]},
        ],
    }  # fmt: skip
    assert "elements" not in cr.glyph_data(spec("x.alt"))["layers"][0], "no component: no elements key"


def test_create_glyphs_when_components_in_font_without_components_then_one_set_glyph_each(world):
    for glyph in world.package.glyphs.values():
        for layer in glyph.layers:
            layer.shapes = [x for x in layer.shapes if not x.isComponent]
    done = cr.create_glyphs(world.package, [with_parts()], "Unicase", facts_of(world.package))
    assert [(n, a["glyph_name"]) for n, a in world.tools.calls] == [("set_glyph", "a.unic")]
    assert world.tools.calls[0][1]["glyph_data"] == cr.glyph_data(with_parts())
    made = done.glyphs[0]
    assert [s.shapeData.componentGlyph for s in made.findLayer("L").shapes] == ["H", "e"]
    assert [e for e in LOG if e[0] in ("init", "notify")] == [], "the components are in the Add Glyph step"


@pytest.mark.parametrize(
    ("part", "text"),
    [
        (cr.Part("X", "H"), "a.unic · X: no such new layer"),
        (cr.Part("L", "missing"), "no base glyph missing with that layer"),
        (cr.Part("B", "onehalf.tf"), "no base glyph onehalf.tf with that layer"),
        (cr.Part("L", "a.unic"), "no base glyph a.unic with that layer"),
        (cr.Part("L", "H", float("inf")), "offset must be finite"),
    ],
    ids=["layer", "base", "base-layer", "self", "inf"],
)
def test_create_glyphs_when_component_refused_then_value_error_before_any_call(world, part, text):
    with pytest.raises(ValueError, match=text):
        cr.create_glyphs(world.package, [with_parts(parts=(part,))], "Unicase", world.facts)
    assert world.tools.calls == [] and LOG == []


def test_create_glyphs_when_fontlab_drops_components_then_partial_error_with_hint(world):
    world.tools.drop_parts = True
    with pytest.raises(history.PartialWriteError) as error:
        cr.create_glyphs(world.package, [with_parts()], "Unicase", world.facts)
    assert "FontLab did not add the components of a.unic · L" in str(error.value)
    assert "new glyphs that exist now: a.unic" in str(error.value), "the first glyph exists and is named"
    assert history.UNDO_HINT in str(error.value), "the glyph exists: its Add Glyph step can be undone"


def test_create_glyphs_when_second_glyph_drops_components_then_both_glyphs_named(world):
    real = world.tools.call

    def call(name, **arguments):
        world.tools.drop_parts = arguments["glyph_name"] == "b.unic"
        return real(name, **arguments)

    world.tools.call = call
    with pytest.raises(history.PartialWriteError) as error:
        cr.create_glyphs(world.package, [with_parts(), with_parts("b.unic")], "Unicase", world.facts)
    assert "new glyphs that exist now: a.unic, b.unic" in str(error.value)


def test_undo_text_when_components_only_then_no_outlines_step(world):
    assert cr.undo_text(filled=True) == cr.UNDO_TEXT and "outlines" in cr.UNDO_TEXT
    assert cr.undo_text(filled=False) == cr.CREATE_UNDO_TEXT == "Each new glyph is recorded as its own Undo step."
    cr.create_glyphs(world.package, [with_parts()], "Unicase", world.facts)
    assert [e for e in LOG if e[0] in ("init", "notify", "stamp")] == [], "components only: no outlines step"


def test_create_glyphs_when_component_call_times_out_then_partial_error_with_hint(world):
    world.tools.raises = {"a.unic": TimeoutError("no answer")}
    with pytest.raises(history.PartialWriteError) as error:
        cr.create_glyphs(world.package, [with_parts()], "Unicase", world.facts)
    assert "no answer" in str(error.value) and history.UNDO_HINT in str(error.value), "outcome unknown"


# ---------------------------------------------------------------- auto candidates (S7 I2)
def test_segments_when_dotted_then_suffix_parts_only():
    assert cr.segments("h.sc.ss01") == frozenset({"sc", "ss01"})
    assert cr.segments("H") == frozenset()
    assert cr.segments(".notdef") == frozenset({"notdef"})


def test_auto_candidates_when_suffix_shared_then_recipe_less_auto_owners(world):
    found = cr.auto_candidates(world.package, world.facts, ["e.sc", "one.tf", "x.scale", "A", "b.sc.ss01"])
    assert found == {
        "e.sc": ("eacute.sc",),
        "one.tf": ("onehalf.tf",),
        "b.sc.ss01": ("eacute.sc",),
    }, "own recipe (aacute.sc) is no candidate; segments match whole: x.scale is none"


def test_auto_candidates_when_owner_suffix_only_starts_alike_then_no_candidate():
    package = Package(Glyph("x.scale", [Layer("L", auto=True)]), Glyph("b.sc", [Layer("L", auto=True)]))
    found = cr.auto_candidates(package, facts_of(package), ["y.sc", "y.scale"])
    assert found == {"y.sc": ("b.sc",), "y.scale": ("x.scale",)}, "whole segments: sc is not scale"


def test_auto_candidates_when_no_auto_owner_then_empty(world):
    assert cr.auto_candidates(world.package, history.auto_facts(()), ["e.sc"]) == {}


def test_rebuild_note_when_many_then_two_names_and_ellipsis():
    assert cr.rebuild_note(("a.sc",)) == "may rebuild auto a.sc"
    assert cr.rebuild_note(("a.sc", "b.sc", "c.sc")) == "may rebuild auto a.sc, b.sc…"


def test_auto_changes_when_layer_gone_then_reported(world):
    before = cr.auto_signatures(world.package, world.facts)
    assert set(before) == {("eacute.sc", "L"), ("eacute.sc", "B"), ("aacute.sc", "L"), ("onehalf.tf", "L")}
    world.package.glyphs.pop("onehalf.tf")
    assert cr.auto_changes(world.package, before) == [
        "Auto glyph onehalf.tf · L changed after the write; FontLab rebuilt it. Check it."
    ]


# ---------------------------------------------------------------- copy generator kernel
def capital_naming(name):
    if not name[:1].isupper():
        return "", "not a capital"
    return name.lower() + ".sc", ""


def test_survey_with_when_mixed_then_exact_notes_and_rebuild_gate(world):
    world.package.glyphs["E"] = Glyph("E", [Layer("L", 500, [Shape([NS()])]), Layer("B", 500, [Shape([NS()])])])
    world.package.glyphs["K"] = Glyph("K", [Layer("L", 500, [Shape(base="H")]), Layer("B", 500)])
    rows = gc.survey_with(world.package, ["H", "E", "K", "e", "H", "Q"], capital_naming, world.facts)
    assert [(r.source, r.target, r.note, r.rebuild) for r in rows] == [
        ("H", "h.sc", "may rebuild auto eacute.sc", ("eacute.sc",)),
        ("E", "e.sc", "may rebuild auto eacute.sc", ("eacute.sc",)),
        ("K", "k.sc", "L: built from components", ()),
        ("e", "", "not a capital", ()),
        ("H", "h.sc", "repeated", ()),
        ("Q", "q.sc", "not in font", ()),
    ]
    agreed = gc.survey_with(world.package, ["E"], capital_naming, world.facts, allow_rebuild=True)
    assert [(r.note, r.rebuild, len(r.layers)) for r in agreed] == [("", ("eacute.sc",), 2)]
    plain = gc.survey_with(world.package, ["H"], lambda n: ("h.smcp", ""), world.facts)
    assert [(r.target, r.note, r.rebuild) for r in plain] == [("h.smcp", "", ())], "no shared segment: no gate"


def test_source_problem_when_layer_kinds_then_reason():
    assert gc.source_problem(None) == "no layer"
    assert gc.source_problem(Layer("L", auto=True)) == "auto layer"
    assert gc.source_problem(Layer("L", shapes=[Shape(base="x")])) == "built from components"
    assert gc.source_problem(Layer("L")) == "no outline"
    assert gc.source_problem(Layer("L", shapes=[Shape([NS()])])) == ""


def test_half_up_when_half_then_up():
    assert [gc.half_up(v) for v in (250.5, 250.49, -0.5, 3)] == [251, 250, 0, 3]


def test_generator_create_when_jobs_then_widths_at_creation_and_contours_in_one_step(world):
    contours = [NS(name="c")]
    jobs = [("h.sc", [("L", contours, 450), ("B", contours, 480)])]
    result = gc.create(world.package, jobs, "Small", world.facts, allow_rebuild=True)
    assert result == {"pending_note": "", "glyphs": 1, "layers": 2, "mismatches": [], "pending_updates": ()}
    assert world.tools.calls[0][1]["glyph_data"]["layers"] == [
        {"name": "L", "advanceWidth": 450}, {"name": "B", "advanceWidth": 480},
    ]  # fmt: skip
    made = world.package.findName("h.sc")
    assert [len(x.shapes[0].contours) for x in made.layers] == [1, 1]
    assert [[x.name for x in n] for n in world.native.notified] == [["L", "B", "h.sc"]]


def test_generator_create_when_nothing_then_zeros(world):
    assert gc.create(world.package, [], "Small", world.facts) == {"glyphs": 0, "layers": 0, "mismatches": [], "pending_updates": (), "pending_note": ""}
    assert LOG == []


def test_generator_create_when_width_differs_then_mismatch(world):
    world.tools.after = lambda name: setattr(world.package.findName(name).layers[0], "advanceWidth", 1)
    result = gc.create(world.package, [("h.sc", [("L", [NS()], 450)])], "Small", world.facts, allow_rebuild=True)
    assert result["mismatches"] == ["h.sc · L: 1 contours, width 1; planned 1, 450"]
