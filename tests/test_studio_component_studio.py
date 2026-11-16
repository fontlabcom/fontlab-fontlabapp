# this_file: tests/test_studio_component_studio.py
"""Component Studio (A15): parity with the 9 Scriptmix scripts, dry runs and the one labelled Undo step.

Each write test checks the single ``AppShell.history`` call (label, glyphs,
(glyph, master) layers, retained objects) and the values FontLab received.
Dump from selection and the lock listing must not call it nor change any
shape. Pure functions are compared with the Scriptmix originals by AST.
"""

from _demo_support import stub_natives

import ast
import hashlib
import importlib
import inspect
import itertools
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from _component_studio_originals import ORIGINALS
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.component_studio"
ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "Scripts" / "Components" / "Component Studio Demo.py"
SCRIPTMIX = Path(
    os.environ.get("FONTLAB_SCRIPTMIX", ROOT.parents[0] / "fontlab-python-scriptmix")
)
TAB_MODULES = {
    "Build From Recipes": "build",
    "Replace Reference": "replace",
    "Decompose": "decompose",
    "Decompose Named Components": "decompose",
    "Decompose Serif Components": "decompose",
    "Copy Offsets Between Masters": "offsets",
    "Set Component Locations": "locations",
    "Unlock Lock": "locks",
}
LOCAL_IMPORT = "    from fly import pr\n"


def _forget_studio_children():
    import fontlabapp.studios as studios

    for name in [n for n in sys.modules if n.startswith("fontlabapp.studios.")]:
        sys.modules.pop(name)
        studios.__dict__.pop(name.split(".")[2], None)


@pytest.fixture(autouse=True)
def fresh_studios():
    _forget_studio_children()
    yield
    _forget_studio_children()


def qt():
    return importlib.import_module("PythonQt")


# ---------------------------------------------------------------- fakes
class Contour:
    def nodes(self):
        return []


class Shape:
    """A component of ``base`` (with ``offset``) or an outline with ``contours`` contours."""

    _ids = itertools.count(1)

    def __init__(self, pkg, *, base=None, offset=(0, 0), scale=1.0, contours=1, source="",
                 refs=1, locked=False, selected=False):  # fmt: skip
        self.pkg, self.id = pkg, next(Shape._ids)
        self.isComponent = self.isComposite = base is not None
        self.shapeData = NS(componentGlyph=base, componentLayer=source, note="", referenceCount=refs,
                            builder=NS(update=lambda: True))  # fmt: skip
        self.transform = qt().QtGui.QTransform(scale, 0, 0, 1, *offset)
        self.contours = [] if base is not None else [Contour() for _ in range(contours)]
        self.name, self.contentLocked, self.selected = "", locked, selected
        self.master = ""

    def changed(self):
        self.pkg.log.append(("shape changed", self.id))

    @property
    def includesList(self):  # noqa: N802 - native API
        base = self.pkg.glyphs[self.shapeData.componentGlyph]
        return base.findLayer(self.shapeData.componentLayer or self.master).shapes

    def ejectTo(self):  # noqa: N802 - native API
        copies = []
        for part in self.includesList:
            if part.isComponent:
                copy = Shape(
                    self.pkg,
                    base=part.shapeData.componentGlyph,
                    source=part.shapeData.componentLayer,
                )
                copy.master = self.master
            else:
                copy = Shape(self.pkg, contours=len(part.contours), locked=True)
            copies.append(copy)
        return copies


class Layer:
    def __init__(self, pkg, glyph, master, shapes=(), *, auto=False, width=500):
        self.pkg, self.glyph, self.name = pkg, glyph, master
        self.advanceWidth, self.autoLayer, self.isNull = width, auto, False
        self.isLocked = self.isMaskLayer = self.isService = False
        self.shapes = list(shapes)
        for shape in self.shapes:
            shape.master = master

    def removeShape(self, shape):  # noqa: N802 - native API
        self.pkg.log.append(("remove", self.glyph, self.name, shape.id))
        self.shapes.remove(shape)

    def insertShape(self, index, shape):  # noqa: N802 - native API
        self.pkg.log.append(("insert", self.glyph, self.name, index))
        self.shapes.insert(index, shape)
        return shape

    def changed(self):
        self.pkg.log.append(("layer changed", self.glyph, self.name))

    def update(self):
        return True

    def getMasterPosition(self):  # noqa: N802 - native API
        return {"wt": 400.0}


class Glyph:
    def __init__(self, pkg, name, layers):
        self.pkg, self.name, self.isNull = pkg, name, False
        self._layers = {layer.name: layer for layer in layers}

    def findLayer(self, master):  # noqa: N802 - native API
        return self._layers.get(master)

    @property
    def layers(self):
        return list(self._layers.values())

    def findLayerCreate(self, master):  # noqa: N802 - native API
        self.pkg.log.append(("create layer", self.name, master))
        self._layers[master] = Layer(self.pkg, self.name, master)
        return self._layers[master]

    def updateActiveLayer(self, _flag):  # noqa: N802 - native API
        return self._layers.get(self.pkg.master)


class Package:
    def __init__(self):
        self.log, self.masters, self.master, self.glyphs, self.id, self.fgId = (
            [],
            ["Regular", "Bold"],
            "Regular",
            {},
            7,
            70,
        )
        self.axes = [
            NS(
                shortName="wt",
                name="Weight",
                designMin=100.0,
                designMax=900.0,
                designDef=400.0,
            )
        ]

    def add(self, name, per_master, **kwargs):
        """``per_master``: master -> shape factory ``(pkg) -> [Shape]`` (or None for an empty layer)."""
        layers = [
            Layer(self, name, m, make(self) if make else (), **kwargs)
            for m, make in per_master.items()
        ]
        self.glyphs[name] = Glyph(self, name, layers)
        return self.glyphs[name]

    def findName(self, name):  # noqa: N802 - native API
        return self.glyphs.get(name)

    def layer(self, name, master):
        return self.glyphs[name].findLayer(master)

    def location(self, master):
        return {"wt": 400.0 if master == "Regular" else 700.0}


def outline(count=1, **kwargs):
    return lambda pkg: [Shape(pkg, contours=count, **kwargs)]


def comps(*parts):
    """``(base, offset[, kwargs])`` per component."""
    return lambda pkg: [
        Shape(pkg, base=b, offset=o, **(rest[0] if rest else {}))
        for b, o, *rest in parts
    ]


def package():
    pkg = Package()
    pkg.add(
        "A",
        {
            "Regular": outline(2),
            "Bold": outline(
                2,
            ),
        },
        width=600,
    )
    pkg.add("acute", {"Regular": outline(1), "Bold": outline(1)}, width=200)
    pkg.add("acute.alt", {"Regular": outline(1), "Bold": outline(1)})
    pkg.add(
        "ring", {"Regular": comps(("acute", (0, 0))), "Bold": comps(("acute", (0, 0)))}
    )
    pkg.add("Aacute", {"Regular": comps(("A", (0, 0)), ("acute", (200, 600))),
                       "Bold": comps(("A", (0, 0)), ("acute", (220, 640)))}, width=600)  # fmt: skip
    pkg.add("Aring", {"Regular": comps(("A", (0, 0)), ("ring", (150, 650))),
                      "Bold": comps(("A", (0, 0)), ("ring", (150, 650)))})  # fmt: skip
    pkg.add("SerifTop", {"Regular": outline(1), "Bold": outline(1)})
    pkg.add("I", {"Regular": comps(("SerifTop", (0, 700)), ("A", (0, 0))),
                  "Bold": comps(("SerifTop", (0, 700)), ("A", (0, 0)))})  # fmt: skip
    return pkg


class Recorder:
    """``AppShell.history`` stand-in: records one call, runs mutate and read-back."""

    def __init__(self, shell, refuse=None):
        self.shell, self.calls, self.refuse, self.retained = shell, [], refuse, []

    def __call__(
        self,
        label,
        glyphs,
        mutate,
        *,
        layers,
        read_back=None,
        allow_bases=False,
        retain=(),
    ):
        self.calls.append(
            (
                label,
                [g.name for g in glyphs],
                [(la.glyph, la.name) for la in layers],
                allow_bases,
            )
        )
        self.retained.append(list(retain))
        if self.refuse:
            self.shell.set_status(self.refuse)
            return None
        mutate()
        return NS(mismatches=read_back() if read_back else [], pending_note="")


class Forbidden:
    """A history that fails the test when anything opens it."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("read-only action opened history")


def native(name):
    if name == "PythonQt":
        return qt()
    return NS(flNode=NS(NodeKind={"SmoothMask": 1}))


class FontPr:
    """``fly.pr``: ``build_glyph`` (FontLab's builder) and ``get_glyph`` (stored lock flags)."""

    def __init__(self, pkg):
        self.pkg, self.calls, self.locks, self.fail = pkg, [], {}, ""

    def call(self, tool, **arguments):
        self.calls.append((tool, arguments))
        if self.fail:
            return {"status": "error", "error": self.fail}
        if tool == "get_glyph":
            glyph = self.pkg.glyphs[arguments["glyph_name"]]
            layers = []
            for layer in glyph.layers:
                elements = [
                    {"component": {"glyphName": s.shapeData.componentGlyph}, "locked": self.locks.get(s.id, False)}
                    if s.isComponent else {"locked": False}
                    for s in layer.shapes
                ]  # fmt: skip
                layers.append({"name": layer.name, "elements": elements})
            return {"glyph": {"layers": layers}}
        name, master = arguments["glyph_name"], arguments["layer_name"]
        glyph = self.pkg.findName(name)
        if glyph is not None and glyph.findLayer(master) is None:
            return {"status": "error", "error": "Target layer not found."}
        parts = [
            {"glyph_name": p.split("@")[0]} for p in arguments["recipe"][1:].split("+")
        ]
        if arguments["dry_run"]:
            return {"status": "validated", "resolved_components": parts}
        if glyph is None:
            glyph = self.pkg.add(name, {master: None})
        self.pkg.log.append(("build", name, master, arguments["recipe"]))
        return {"status": "ok", "created": True, "resolved_components": parts}


@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.components.writer as writer
    import fontlabapp.core.history.glyphs as history
    import fontlabapp.core.scripting as scripting
    from fontlabapp.core.scripting import component_studio_backends

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            return lambda *args: self.calls.append((name, *args))

    monkeypatch.setattr(writer, "_native", native)
    import fontlabapp.core.edit_guards as edit_guards

    monkeypatch.setattr(edit_guards, "pending_updates", lambda native=None: ())
    facts = NS(value=history.auto_facts([]))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts.value)

    def open_app(pkg=None, selection=("Aacute", "Aring", "I"), history_type=Recorder):
        pkg = package() if pkg is None else pkg
        fontpr = FontPr(pkg)
        ink = NS(ink=lambda: qt().QtGui.QBrush())  # main-window palette brush
        found = NS(**{**vars(component_studio_backends()), "pr": fontpr, "panel": ink})
        studio = importlib.import_module(PKG)
        shared = importlib.import_module(f"{PKG}._shared")
        monkeypatch.setattr(shared, "backends", lambda: found)
        chosen = list(selection)
        monkeypatch.setattr(
            sys.modules["fontlabapp.studios._kerning"],
            "names_selected_names",
            lambda: list(chosen),
        )
        monkeypatch.setattr(
            scripting, "names_font_glyphs", lambda: [(n, None) for n in pkg.glyphs]
        )
        monkeypatch.setattr(
            scripting,
            "current_package",
            lambda expected=None: pkg if expected in (None, pkg.id) else None,
        )
        preview = QtPreview()
        shell = studio.show(
            package=lambda: pkg,
            font=lambda: "font",
            preview=lambda shell, tool: preview,
        )
        studio_qt.owned.append(shell)
        tool = shell.component_studio_tool
        recorder = history_type(shell)
        shell.history = recorder
        panels = {
            title: view.__self__
            for title, view in zip(studio.TAB_TITLES, tool.views, strict=True)
        }
        return NS(shell=shell, tool=tool, pkg=pkg, preview=preview, panels=panels, studio=studio, history=recorder,
                  selection=chosen, facts=facts, backends=found, fontpr=fontpr)  # fmt: skip

    return open_app


def rows(panel):
    return [(r.glyph_name, r.layer, tuple(r.values)) for r in panel.grid.rows]


def offsets(pkg, name, master):
    return [
        (s.shapeData.componentGlyph, s.transform.dx(), s.transform.dy())
        for s in pkg.layer(name, master).shapes
    ]


def builds(app):
    return [call for call in app.fontpr.calls if call[0] == "build_glyph"]


def writes(pkg):
    return [entry for entry in pkg.log if entry[0] != "layer changed"]


# ---------------------------------------------------------------- shell, registry, parity
def test_show_when_opened_then_six_tabs_tglyph_preview_and_masters(opened):
    app = opened()
    assert app.studio.TAB_TITLES == (
        "Build",
        "Replace",
        "Decompose",
        "Offsets",
        "Locations",
        "Locks",
    )
    assert list(app.panels) == list(app.studio.TAB_TITLES)
    assert app.tool.app == "Component Studio"
    assert app.tool.masters == ["Regular", "Bold"]
    assert app.tool.preview is app.preview


def test_registry_when_imported_then_lazy_and_idempotent():
    import fontlabapp.studios as studios

    studio = importlib.import_module(PKG)
    assert studio.register_tabs() == studio.register_tabs() == studio.TAB_TITLES
    assert tuple(spec.title for spec in studios.tabs(studio.APP)) == studio.TAB_TITLES
    for module in (
        "build",
        "replace",
        "decompose",
        "offsets",
        "locations",
        "locks",
        "_shared",
    ):
        assert f"{PKG}.{module}" not in sys.modules, module


def test_backends_when_loaded_then_reused_app_modules(monkeypatch):
    import fontlabapp.core.scripting as scripting

    found = scripting.component_studio_backends()
    assert found.components.__name__ == "fontlabapp.components.writer"
    assert found.recipes.__name__ == "fontlabapp.components.recipes.model"
    assert found.panel.__name__ == "fontlabapp.components.panel.model"
    assert found.history.__name__ == "fontlabapp.core.history.glyphs"
    seen = []
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: NS(call=lambda tool, **a: seen.append((name, tool, a)) or 1),
    )
    assert found.pr.call("get_glyph", font_id=3) == 1
    assert seen == [("fontpr", "get_glyph", {"font_id": 3})]


@pytest.mark.parametrize("title", sorted(ORIGINALS))
def test_originals_when_ported_then_pure_functions_match_the_script_ast(
    title,
    studio_qt,  # noqa: F811
):
    path, digest, names, source = ORIGINALS[title]
    assert path == f"Scripts/Components/{title}.py" and len(digest) == 64
    if not names:
        assert title == "Dump Component Recipes" and source == ""
        return
    module = importlib.import_module(f"{PKG}.{TAB_MODULES[title]}")
    expected = ast.parse(source.replace(LOCAL_IMPORT, ""))
    ported = [ast.parse(inspect.getsource(getattr(module, name))) for name in names]
    found = {getattr(n, "name", ""): n for tree in ported for n in tree.body}
    for node in expected.body:
        assert ast.dump(found[node.name]) == ast.dump(node), f"{title}: {node.name}"


@pytest.mark.skipif(
    not (SCRIPTMIX / ".git").exists(), reason="Scriptmix checkout not next to the App"
)
@pytest.mark.parametrize("title", sorted(ORIGINALS))
def test_originals_when_scriptmix_present_then_pinned_hash_matches(title):
    path, digest, _, _ = ORIGINALS[title]
    data = subprocess.run(
        ["git", "-C", str(SCRIPTMIX), "show", f"25c86b4:{path}"],
        capture_output=True,
        check=False,
    )
    if data.returncode:
        pytest.skip("pinned Scriptmix commit not available")
    assert hashlib.sha256(data.stdout).hexdigest() == digest


def test_label_when_one_or_many_glyphs_then_name_or_count(studio_qt):  # noqa: F811
    shared = importlib.import_module(f"{PKG}._shared")
    assert (
        shared.label("decompose components", ["A", "A"])
        == "Component Studio: decompose components A"
    )
    assert (
        shared.label("lock components", ["A", "B"])
        == "Component Studio: lock components 2 glyphs"
    )
    assert (
        shared.plural(1, "layer") == "1 layer"
        and shared.plural(2, "layer") == "2 layers"
    )
    with pytest.raises(AttributeError):
        shared.Modules("components").__wrapped__  # noqa: B018 - dunder lookups never reach the backend


# ---------------------------------------------------------------- Offsets
def test_offsets_when_copied_then_one_step_on_target_layer(opened):
    app = opened(selection=("Aacute",))
    panel = app.panels["Offsets"]
    assert panel.source() == "Regular" and panel.chosen_masters() == ["Bold"]
    assert rows(panel) == [
        ("Aacute", "Bold", ("A", "0, 0", "same")),
        ("Aacute", "Bold", ("acute", "220, 640", "200, 600")),
    ]
    assert panel.apply() is True
    assert app.history.calls == [
        (
            "Component Studio: copy component offsets Aacute",
            ["Aacute"],
            [("Aacute", "Bold")],
            False,
        )
    ]
    assert offsets(app.pkg, "Aacute", "Bold")[1] == ("acute", 200.0, 600.0)
    assert app.tool.status.startswith(
        "Component Studio: copy component offsets Aacute. Moved 1 component on 1 layer"
    )


def test_offsets_when_scaled_or_no_target_then_ratio_or_refusal(opened):
    app = opened(selection=("Aacute",))
    panel = app.panels["Offsets"]
    app.pkg.layer("Aacute", "Bold").advanceWidth = 900
    panel.scale_box.setChecked(True)
    assert rows(panel)[1][2] == ("acute", "220, 640", "300, 600")
    item = panel.target_list.item(0)
    item.setCheckState(qt().QtCore.Qt.Unchecked)
    assert (
        panel.count.text() == "Tick at least one target master."
        and not panel.apply_button.isEnabled()
    )
    item.setCheckState(qt().QtCore.Qt.Checked)
    panel.source_box.setCurrentIndex(1)
    assert panel.chosen_masters() == ["Regular"]
    assert panel.target_list.count() == 1


def test_offsets_when_components_differ_then_kept_row(opened):
    pkg = package()
    pkg.layer("Aacute", "Bold").shapes.pop()
    app = opened(pkg, selection=("Aacute",))
    assert rows(app.panels["Offsets"]) == [
        ("Aacute", "Bold", ("A", "", "different components, kept"))
    ]
    assert app.panels["Offsets"].count.text() == "0 component changes on 0 layers"


# ---------------------------------------------------------------- Decompose
def test_decompose_when_all_then_one_level_retained_and_unlocked(opened):
    app = opened(selection=("Aring",))
    panel = app.panels["Decompose"]
    assert panel.chosen_masters() == ["Regular"]
    assert rows(panel) == [("Aring", "Regular", ("A", "2 contours")),
                           ("Aring", "Regular", ("ring", "0 contours + 1 component (nested: press again)"))]  # fmt: skip
    assert panel.apply() is True
    label, glyphs, layers, _ = app.history.calls[0]
    assert (label, glyphs, layers) == (
        "Component Studio: decompose components Aring",
        ["Aring"],
        [("Aring", "Regular")],
    )
    assert (
        len(app.history.retained[0]) == 6
    )  # (shape, shapeData, builder) per removed component
    shapes = app.pkg.layer("Aring", "Regular").shapes
    assert [s.isComponent for s in shapes] == [
        False,
        True,
    ]  # A's outline; ring's inner acute stays a component
    assert not any(s.contentLocked for s in shapes if not s.isComponent)
    assert (
        app.pkg.layer("Aring", "Bold").shapes[0].isComponent
    )  # other master untouched
    assert "Decomposed 2 components on 1 layer" in app.tool.status


def test_decompose_when_serif_scope_then_only_serif_bases(opened):
    app = opened(selection=("I", "Aacute"))
    panel = app.panels["Decompose"]
    panel.kind.setCurrentIndex(2)
    assert rows(panel) == [("I", "Regular", ("SerifTop", "editable parts"))]
    assert panel.apply() is True
    assert app.history.calls[0][0] == "Component Studio: decompose Serif components I"
    assert [s.isComponent for s in app.pkg.layer("I", "Regular").shapes] == [
        False,
        True,
    ]


def test_decompose_when_named_then_subtree_flattened_on_all_masters_and_kept_rows(
    opened,
):
    pkg = package()
    pkg.layer("Aring", "Bold").isLocked = True
    app = opened(pkg, selection=("Aring", "Aacute"))
    panel = app.panels["Decompose"]
    panel.kind.setCurrentIndex(1)
    assert panel.chosen_masters() == ["Regular", "Bold"]
    assert panel.count.text() == "Enter a component source name."
    panel.source_edit.setText("ri ng")
    assert (
        panel.count.text()
        == "Enter a glyph name without control or non-breaking characters."
    )
    panel.source_edit.setText("ring")
    assert rows(panel) == [("Aring", "Regular", ("ring", "independent outlines")),
                           ("Aring", "Bold", ("ring", "kept: automatic, locked or service layer"))]  # fmt: skip
    assert panel.apply() is True
    assert app.history.calls[0][:3] == ("Component Studio: decompose named components Aring", ["Aring"],
                                        [("Aring", "Regular")])  # fmt: skip
    assert [s.isComponent for s in pkg.layer("Aring", "Regular").shapes] == [
        True,
        False,
    ]
    assert (
        "Decomposed 1 occurrences on 1 layers; review kept rows above."
        in app.tool.status
    )


def test_decompose_when_base_cannot_be_copied_then_red_row_refuses(opened):
    pkg = package()
    pkg.glyphs["A"]._layers.pop("Regular")
    app = opened(pkg, selection=("Aacute",))
    panel = app.panels["Decompose"]
    assert rows(panel)[0] == (
        "Aacute",
        "Regular",
        ("A", "base A has no plain layer Regular"),
    )
    assert panel.count.text() == "Aacute · Regular: base A has no plain layer Regular"
    assert not panel.apply_button.isEnabled()


def test_named_editor_when_unprepared_then_refused(studio_qt):  # noqa: F811
    decompose = importlib.import_module(f"{PKG}.decompose")
    with pytest.raises(ValueError, match="Prepare component copies on Apply first."):
        decompose.NamedEditor(unlock=True).prepare(NS(shapes=[]), [(1, None)])


# ---------------------------------------------------------------- refusals shared by every write tab
def test_writes_when_auto_glyph_or_base_then_refused_without_opt_in(opened):
    import fontlabapp.core.history.glyphs as history

    app = opened(selection=("Aacute",))
    app.facts.value = history.auto_facts([("Aacute.sc", True, ("Aacute",))])
    app.tool.reload()
    panel = app.panels["Offsets"]
    assert rows(panel)[0] == ("Aacute", None, ("blocked", "", "base of auto Aacute.sc"))
    assert panel.count.text().startswith(
        "FontLab cannot undo edits to these glyphs: Aacute"
    )
    assert not panel.apply_button.isEnabled() and app.history.calls == []
    assert not any("allow" in name.lower() for name in vars(panel))


def test_apply_when_font_changed_then_stale_refusal_and_no_write(opened):
    app = opened(selection=("Aacute",))
    panel = app.panels["Offsets"]
    app.pkg.layer("Aacute", "Bold").shapes[1].transform = qt().QtGui.QTransform(
        1, 0, 0, 1, 5, 5
    )
    assert panel.apply() is False
    assert (
        app.tool.status
        == "Component Studio: The glyphs changed since the dry run; press Reload selection."
    )
    app.pkg.master = "Bold"
    assert panel.apply() is False
    assert app.tool.status == "Component Studio: Master changed; Reload selection."
    app.pkg.master, app.pkg.id = "Regular", 8
    assert panel.apply() is False
    assert (
        app.tool.status == "Component Studio: The font changed; press Reload selection."
    )
    assert app.history.calls == []


def test_apply_when_history_refuses_then_status_kept_and_nothing_written(opened):
    app = opened(
        selection=("Aacute",),
        history_type=lambda shell: Recorder(shell, refuse="Glyph window refusal"),
    )
    assert app.panels["Offsets"].apply() is False
    assert app.tool.status == "Glyph window refusal"
    assert offsets(app.pkg, "Aacute", "Bold")[1] == ("acute", 220.0, 640.0)


def test_apply_when_read_back_misses_then_not_stored_text(opened, monkeypatch):
    app = opened(selection=("Aacute",))
    replace = importlib.import_module(f"{PKG}.replace")
    monkeypatch.setattr(
        replace.ReplaceEditor, "check", lambda self, prepared: ["Bold/acute.alt"]
    )
    panel = app.panels["Replace"]
    panel.old_edit.setText("acute")
    panel.new_edit.setText("acute.alt")
    panel.replan()
    assert panel.apply() is True
    assert "FontLab did not store 1 change" in app.tool.status


# ---------------------------------------------------------------- Replace
def test_replace_when_typed_then_debounced_plan_and_in_place_rename(opened):
    app = opened(selection=("Aacute", "Aring"))
    panel = app.panels["Replace"]
    assert panel.count.text() == "Type both glyph names."
    panel.old_edit.setText("acute")
    assert not panel.apply_button.isEnabled() and panel.timer.isActive()
    panel.new_edit.setText("acute")
    panel.replan()
    assert panel.count.text() == "The two names are the same."
    panel.new_edit.setText("nope")
    panel.replan()
    assert panel.count.text() == "No glyph named nope."
    panel.new_edit.setText("acute.alt")
    panel.replan()
    assert rows(panel) == [("Aacute", "Regular", ("acute", "200, 600", "acute.alt"))]
    shape = app.pkg.layer("Aacute", "Regular").shapes[1]
    assert panel.apply() is True
    assert app.history.calls[0][:3] == ("Component Studio: replace component reference Aacute", ["Aacute"],
                                        [("Aacute", "Regular")])  # fmt: skip
    assert (
        app.pkg.layer("Aacute", "Regular").shapes[1] is shape
    )  # placement kept: same shape, renamed
    assert shape.shapeData.componentGlyph == "acute.alt" and shape.transform.dx() == 200


def test_replace_when_unsafe_then_original_problems(opened):
    import fontlabapp.core.history.glyphs as history

    pkg = package()
    pkg.layer("Aacute", "Regular").shapes[1].shapeData.referenceCount = 2
    app = opened(pkg, selection=("Aacute", "ring"))
    panel = app.panels["Replace"]
    panel.glyph_scope.setCurrentIndex(1)
    panel.old_edit.setText("acute")
    panel.new_edit.setText("Aacute")
    panel.replan()
    texts = [r[2][2] for r in rows(panel)]
    assert "Aacute uses Aacute: the component would show itself" in texts
    app.facts.value = history.auto_facts(
        [("ring", False, ("acute",)), ("Aring", False, ("ring",))]
    )
    panel.refresh()
    panel.new_edit.setText("Aring")
    panel.replan()
    texts = [r[2][2] for r in rows(panel)]
    assert "Aring uses ring: the component would show itself" in texts
    panel.new_edit.setText("acute.alt")
    panel.replan()
    assert (
        "Aacute",
        "Regular",
        ("acute", "200, 600", "shared element data: change it in FontLab"),
    ) in rows(panel)
    pkg.glyphs["acute.alt"]._layers.pop("Regular")
    panel.replan()
    assert (
        "ring",
        "Regular",
        ("acute", "0, 0", "acute.alt has no layer Regular"),
    ) in rows(panel)
    panel.old_edit.setText("zzz")
    panel.replan()
    assert panel.count.text() == "No component of that glyph in scope"


# ---------------------------------------------------------------- Locks
def test_locks_when_listed_then_read_only_and_locked_written_on_apply(opened):
    app = opened(selection=("Aacute",), history_type=lambda shell: Forbidden())
    panel = app.panels["Locks"]
    first = app.pkg.layer("Aacute", "Regular").shapes[0]
    app.fontpr.locks[first.id] = True
    app.tool.reload()
    assert rows(panel) == [("Aacute", "Regular", ("A", "locked", "already locked")),
                           ("Aacute", "Regular", ("acute", "unlocked", "locked"))]  # fmt: skip
    panel.action.setCurrentIndex(1)
    assert rows(panel)[0][2] == ("A", "locked", "unlocked")
    assert writes(app.pkg) == [] and {tool for tool, _ in app.fontpr.calls} == {
        "get_glyph"
    }
    assert app.fontpr.calls[0][1] == {"font_id": 70, "glyph_name": "Aacute"}
    recorder = Recorder(app.shell)
    app.shell.history = recorder
    panel.action.setCurrentIndex(0)

    def stored(tool, **arguments):  # the write lands in FontLab's stored data
        for shape in app.pkg.layer("Aacute", "Regular").shapes:
            app.fontpr.locks[shape.id] = shape.contentLocked or app.fontpr.locks.get(
                shape.id, False
            )
        return FontPr.call(app.fontpr, tool, **arguments)

    app.fontpr.call = stored
    assert panel.apply() is True
    assert recorder.calls[0][:3] == (
        "Component Studio: lock components Aacute",
        ["Aacute"],
        [("Aacute", "Regular")],
    )
    assert app.pkg.layer("Aacute", "Regular").shapes[1].contentLocked is True
    assert "Changed 1 component on 1 layer" in app.tool.status


def test_locks_when_data_disagrees_or_fails_then_unknown_or_refusal(opened):
    app = opened(selection=("Aacute",), history_type=lambda shell: Forbidden())
    panel = app.panels["Locks"]
    locks = importlib.import_module(f"{PKG}.locks")
    assert locks.lock_states(app.pkg.layer("Aacute", "Regular"), [("A", True)]) == [
        None,
        None,
    ]
    assert locks.word(None) == "unknown"
    app.fontpr.fail = "no such glyph"
    app.tool.reload()
    assert "no such glyph" in panel.subtitle.text()
    app.fontpr.fail = ""
    app.tool.reload()
    app.pkg.id = 9
    with pytest.raises(ValueError, match="The font changed; press Reload selection."):
        panel.read_flags()
    assert writes(app.pkg) == []


# ---------------------------------------------------------------- Locations
def test_locations_when_reset_then_host_layer_names_on_all_masters(opened):
    pkg = package()
    for master in pkg.masters:
        pkg.layer("Aacute", master).shapes[1].shapeData.componentLayer = "Bold"
    app = opened(pkg, selection=("Aacute",))
    panel = app.panels["Locations"]
    assert panel.chosen_masters() == ["Regular", "Bold"] and not panel.selected_only()
    assert panel.axis_table.columnCount() == 1 and panel.axis_table.rowCount() == 4
    assert (
        panel.count.text() == "0 component changes on 0 layers"
    )  # Set without edits writes nothing
    panel.mode_box.setCurrentIndex(1)
    assert ("Aacute", "Regular", ("acute", "Bold", "Regular")) in rows(panel)
    assert ("Aacute", "Bold", ("acute", "Bold", "same, kept")) in rows(panel)
    assert panel.apply() is True
    assert app.history.calls[0][:3] == ("Component Studio: reset component locations Aacute", ["Aacute"],
                                        [("Aacute", "Regular"), ("Aacute", "Bold")])  # fmt: skip
    assert (
        pkg.layer("Aacute", "Regular").shapes[1].shapeData.componentLayer == "Regular"
    )
    assert "Changed 3 components; review kept rows above." in app.tool.status


def test_locations_when_coordinate_edited_then_encoded_location_written(opened):
    app = opened(selection=("Aacute",))
    panel = app.panels["Locations"]
    panel.scope.setCurrentIndex(0)
    assert panel.axis_table.rowCount() == 2
    assert panel.axis_table.item(1, 0).text() == "400.0"
    panel.axis_table.item(1, 0).setText("650")
    assert ("Aacute", "Regular", ("acute", "base active layer", "#wt=650")) in rows(
        panel
    )
    panel.axis_table.item(0, 0).setText("x")
    assert (
        "Aacute",
        "Regular",
        ("A", "base active layer", "kept: Enter numeric axis coordinates."),
    ) in rows(panel)
    panel.axis_table.item(0, 0).setText("1000")
    assert ("Aacute", "Regular", ("A", "base active layer",
                                  "kept: wt: choose a finite coordinate inside the design range.")) in rows(panel)  # fmt: skip
    panel.axis_table.item(0, 0).setText("400")
    assert panel.apply() is True
    assert app.history.calls[0][0] == "Component Studio: set component locations Aacute"
    assert (
        app.pkg.layer("Aacute", "Regular").shapes[1].shapeData.componentLayer
        == "#wt=650"
    )


def test_locations_when_selected_components_or_axes_change_then_original_texts(opened):
    app = opened(selection=("Aacute",))
    panel = app.panels["Locations"]
    panel.target_box.setCurrentIndex(0)
    assert (
        panel.count.text()
        == "Select components in a Glyph window, or choose All components in selected glyphs."
    )
    app.pkg.layer("Aacute", "Regular").shapes[1].selected = True
    app.pkg.layer("Aacute", "Bold").shapes.reverse()
    app.tool.reload()
    assert ("Aacute", "Bold", ("acute", "base active layer",
                               "kept: component location changed; reload selection")) in rows(panel)  # as the original  # fmt: skip
    panel.filter_edit.setText("A ")
    assert (
        panel.count.text()
        == "Enter a source name without control or non-breaking characters."
    )
    panel.filter_edit.setText("")
    app.pkg.axes = []
    panel.replan()
    assert (
        panel.count.text()
        == "Axes or masters changed; close this panel and run it again."
    )


def test_locations_coordinates_when_named_layers_then_read_or_refused(studio_qt):  # noqa: F811
    locations = importlib.import_module(f"{PKG}.locations")
    pkg = package()
    shape = pkg.layer("Aacute", "Regular").shapes[1]
    assert locations.current_coordinates(pkg, shape, "Regular") == {"wt": 400.0}
    shape.shapeData.componentLayer = "Bold"
    assert locations.current_coordinates(pkg, shape, "Regular") == {"wt": 700.0}
    shape.shapeData.componentLayer = "#wt=550"
    assert locations.current_coordinates(pkg, shape, "Regular") == {"wt": 550.0}
    shape.shapeData.componentLayer = "Medium"
    with pytest.raises(
        ValueError,
        match="Cannot read source layer Medium; use Reset or the native instance control.",
    ):
        locations.current_coordinates(pkg, shape, "Regular")
    assert locations.encode_location(pkg, {"wt": 512.5}) == "#wt=512.5"
    with pytest.raises(
        ValueError, match="Set one coordinate for each declared font axis."
    ):
        locations.encode_location(pkg, {})


# ---------------------------------------------------------------- Build
def test_build_when_opened_then_no_dry_run_until_check(opened):
    app = opened()
    panel = app.panels["Build"]
    assert builds(app) == [] and panel.count.text() == "Press Check"
    assert (
        panel.subtitle.text()
        == "One recipe per line. Check runs FontLab's builder as a dry run."
    )
    assert not panel.apply_button.isEnabled()
    panel.reloaded()
    assert rows(panel) == [
        ("Aacute.alt", "Regular", ("=A+acute@acute[_acute]", "valid: A + acute"))
    ]
    assert builds(app)[0] == ("build_glyph", {"font_id": 70, "glyph_name": "Aacute.alt",
                                   "recipe": "=A+acute@acute[_acute]", "layer_name": "Regular", "replace": False,
                                   "auto_layer": False, "dry_run": True})  # fmt: skip
    assert (
        panel.count.text() == "1 of 1 layers ready" and panel.apply_button.isEnabled()
    )
    panel.recipes.setPlainText("x = A + acute\n")
    assert (
        panel.count.text() == "Recipes changed: press Check"
        and not panel.apply_button.isEnabled()
    )


def test_build_when_parsed_then_original_line_problems(studio_qt):  # noqa: F811
    build = importlib.import_module(f"{PKG}.build")
    lines = build.parse("# note\nA\nB = \n1x = A\nok = A + b@top\nbad = A \n")
    assert [(ln.target, ln.problem) for ln in lines] == [
        ("A", "use: target = base + mark@anchor"),
        ("B", "empty target or recipe"),
        ("1x", "1x is not a valid glyph name"),
        ("ok", ""),
        ("bad = A", "remove the no-break space"),  # the original names the whole line
    ]
    assert lines[3].recipe == "=A+b@top[_top]"


def test_build_when_new_glyph_and_missing_layer_then_layers_added_in_one_step_and_built(
    opened,
):
    import fontlabapp.core.history.glyphs as history

    pkg = package()
    pkg.add("Aacute.sc", {"Regular": None})
    app = opened(pkg)
    panel = app.panels["Build"]
    panel.scope.setCurrentIndex(1)
    panel.recipes.setPlainText("Aacute.sc = A + acute@acute\nAnew = A + acute\n")
    panel.reloaded()
    assert rows(panel) == [
        ("Aacute.sc", "Regular", ("=A+acute@acute[_acute]", "valid: A + acute")),
        (
            "Aacute.sc",
            "Bold",
            ("=A+acute@acute[_acute]", "valid: adds layer Bold first"),
        ),
        ("Anew", "Regular", ("=A+acute", "valid: A + acute")),
        ("Anew", "Bold", ("=A+acute", "new glyph: press Build again for Bold")),
    ]
    assert panel.apply() is True
    assert app.history.calls == [
        ("Component Studio: add master layers Aacute.sc", ["Aacute.sc"], [], False)
    ]
    assert [e for e in pkg.log if e[0] in ("create layer", "build")] == [
        ("create layer", "Aacute.sc", "Bold"),
        ("build", "Aacute.sc", "Regular", "=A+acute@acute[_acute]"),
        ("build", "Aacute.sc", "Bold", "=A+acute@acute[_acute]"),
        ("build", "Anew", "Regular", "=A+acute"),
    ]
    assert (
        app.tool.status
        == "Built 3 layers · added 1 empty layer · 1 master still to build: press Build again"
    )
    app.facts.value = history.auto_facts([("Aacute.sc", True, ())])
    panel.reloaded()
    assert rows(panel)[0] == (
        "Aacute.sc",
        None,
        ("=A+acute@acute[_acute]", "has auto layers"),
    )
    assert panel.count.text() == "2 of 3 layers ready · fix the red lines"


def test_build_when_layer_add_refused_or_check_fails_on_apply_then_nothing_built(
    opened,
):
    pkg = package()
    pkg.add("Aacute.sc", {"Regular": None})
    app = opened(
        pkg, history_type=lambda shell: Recorder(shell, refuse="Glyph window refusal")
    )
    panel = app.panels["Build"]
    panel.scope.setCurrentIndex(1)
    panel.recipes.setPlainText("Aacute.sc = A + acute\n")
    panel.reloaded()
    assert panel.apply() is False
    assert not any(e[0] == "build" for e in pkg.log)
    app.fontpr.fail = "Recipe error"
    assert panel.apply() is False
    assert "Aacute.sc: Recipe error" in app.tool.status
    app.pkg.id = 3
    panel.apply()
    assert app.tool.status == "Component Studio: The font changed; press Check."


def test_dump_when_pressed_then_read_only_recipes_and_summary(opened, monkeypatch):
    app = opened(history_type=lambda shell: Forbidden())
    panel = app.panels["Build"]
    recipes = app.backends.recipes
    snapshot = recipes.RecipeSnapshot(7, "Regular", (recipes.RecipeLayer("Aacute", ("A", "acute")),
                                                     recipes.RecipeLayer("A", ())))  # fmt: skip
    app.backends.recipes = NS(capture=lambda: snapshot, recipes=recipes.recipes)
    text = panel.recipes.toPlainText()
    panel.dump()
    assert (
        panel.dumped.toPlainText() == "A+acute=Aacute\n" and panel.dumped.isReadOnly()
    )
    assert (
        panel.dump_status.text()
        == "Recipes: 1 · Layers: 2 · Current master: Regular. Refresh after changes."
    )
    assert (
        panel.recipes.toPlainText() == text
        and writes(app.pkg) == []
        and builds(app) == []
    )

    def refuse():
        raise ValueError("Select glyph layers before dumping component recipes.")

    app.backends.recipes = NS(capture=refuse, recipes=recipes.recipes)
    panel.dump()
    assert panel.dumped.toPlainText() == ""
    assert (
        panel.dump_status.text()
        == "Select glyph layers before dumping component recipes."
    )


# ---------------------------------------------------------------- preview, no font, demo
def test_row_chosen_when_clicked_then_preview_loads_glyph_on_master(opened):
    app = opened(selection=("Aacute",))
    app.panels["Offsets"].row_chosen("Aacute", "Bold")
    assert ("load", "Aacute", "Bold") in app.preview.calls


def test_show_when_no_font_then_every_tab_says_so(opened, studio_qt):  # noqa: F811
    studio = importlib.import_module(PKG)
    shell = studio.show(package=lambda: None, font=lambda: None)
    studio_qt.owned.append(shell)
    tool = shell.component_studio_tool
    assert tool.preview is None
    for view in tool.views:
        assert view.__self__.subtitle.text() == "Open a font first."
    assert studio.tool_for(shell) is tool


def test_demo_when_run_then_opens_or_says_why(monkeypatch):
    import fontlabapp
    import fontlabapp.qt.dialogs as dialogs

    namespace = runpy.run_path(str(DEMO))
    seen = []
    studio = importlib.import_module(PKG)
    monkeypatch.setattr(studio, "show", lambda: seen.append("show"))
    namespace["main"]()
    assert seen == ["show"]

    def broken():
        raise RuntimeError("no font")

    monkeypatch.setattr(studio, "show", broken)
    fake = NS(QtGui=NS(QMessageBox=NS(Ok=1)))
    stub_natives(monkeypatch, fontlabapp, lambda name: fake if name == 'PythonQt' else NS(MainWindow=lambda: None))
    monkeypatch.setattr(
        dialogs, "run_standard_message_box", lambda *args: seen.append(args[3])
    )
    namespace["main"]()
    assert seen[-1] == "Component Studio did not open: no font"


def test_glyph_preview_when_font_then_tglyph_on_current_master_else_none(
    monkeypatch,
    studio_qt,  # noqa: F811
):
    import fontlabapp.fontui as fontui

    cs_app = importlib.import_module(f"{PKG}.app")
    made = []
    monkeypatch.setattr(
        fontui, "glyph_view", lambda *a, **k: made.append((a, k)) or "view"
    )
    pkg = package()
    pkg.master = "Bold"
    shell = NS(package=lambda: pkg, widget="w", hint_check="h")
    assert cs_app.glyph_preview(shell, NS(font=lambda: "font")) == "view"
    assert made == [(("font", "w"), {"layer": "Bold", "controls": False, "label_prefix": "Component Studio",
                                    "hint_check": "h"})]  # fmt: skip
    assert cs_app.glyph_preview(shell, NS(font=lambda: None)) is None


def test_show_when_assembly_fails_then_shell_closed_and_error_raised(monkeypatch):
    import fontlabapp.fontui as fontui

    cs_app = importlib.import_module(f"{PKG}.app")
    closed = []
    shell = NS(close=lambda: closed.append(True))
    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: shell)

    def broken(shell, tool):
        raise RuntimeError("no preview")

    with pytest.raises(RuntimeError, match="no preview"):
        cs_app.show(package=lambda: None, font=lambda: None, preview=broken)
    assert closed == [True]
    fresh = NS(package=lambda: None, set_status=lambda text: None)
    assert cs_app.tool_for(fresh) is cs_app.tool_for(fresh)
