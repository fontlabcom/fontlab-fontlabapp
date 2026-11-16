# this_file: tests/test_studio_layer_manager.py
"""Layer Manager (A18): parity with the 10 absorbed scripts, dry runs and the one labelled Undo step.

Each write test checks the single ``AppShell.history`` call (label, glyphs,
target layers, retained objects, window) and the values the fake font
received. Planning functions are compared with the pinned originals by AST.
"""

from _demo_support import stub_natives

import ast
import hashlib
import importlib
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from _layer_manager_originals import ORIGINALS, PINNED
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.layer_manager"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "fontlabapp" / "studios" / "layer_manager"
DEMO = ROOT / "Scripts" / "Masters" / "Layer Manager Demo.py"
ENVS = {
    "scriptmix": os.environ.get("FONTLAB_SCRIPTMIX", ""),
    "examples": os.environ.get("FONTLAB_EXAMPLES", ""),
}
#: Original title -> the port modules holding its verbatim definitions.
PORTS = {
    "Copy Layer Between Masters": ("copy_masters",),
    "Master Twins": ("twins",),
    "Duplicate Current Layer": ("_duplicate",),
    "Restore Backup Layer": ("_restore",),
    "Use Layer As Master": ("_use_master",),
    "Layer Cleanup": ("cleanup",),
    "Empty Layers": ("_empty",),
    "Set Intermediate Layer": ("intermediate",),
    "Deliver Glyphs": ("deliver",),
    "Copy Layers From Font": ("_from_font",),
}


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
_IDS = iter(range(1000, 10**6))


class Pin:
    def __init__(self, name, x, y):
        self.name = name
        self.point = qt().QtCore.QPointF(x, y)


class Contour:
    name = ""
    closed = True
    isTT = False  # noqa: N815 - native API

    def nodes(self):
        return []

    def getProperties(self):  # noqa: N802 - native API
        return {}


class Transform:
    """A ``QTransform`` stand-in: ``m11()``..``m33()`` read the identity."""

    def __getattr__(self, name):
        if len(name) == 3 and name[0] == "m":
            return lambda: float(name[1] == name[2])
        raise AttributeError(name)


TRANSFORM = Transform()


class Shape:
    def __init__(self, contours=1, component="", name=""):
        self.id = next(_IDS)
        self.isComponent = bool(component)
        self.contours = [Contour() for _ in range(contours)]
        self.shapeData = NS(
            componentGlyph=component,
            name=name,
            note="",
            referenceCount=1,
            componentLayer="",
        )
        self.name, self.transform, self.active, self.selected = (
            name,
            TRANSFORM,
            False,
            False,
        )
        self.cloned_from = None

    def clone(self):
        copy = Shape(len(self.contours), self.shapeData.componentGlyph)
        copy.cloned_from = self
        return copy


class Layer:
    def __init__(self, glyph, name, shapes=(), *, width=500, anchors=(), master=True, auto=False,
                 locked=False, mask=False, service=False, visible=False):  # fmt: skip
        self.glyph, self.name, self.id = glyph, name, next(_IDS)
        self.shapes = list(shapes)
        self.anchors = [Pin(*a) for a in anchors]
        self.advanceWidth = width
        self.isMasterLayer, self.autoLayer, self.isLocked = master, auto, locked
        self.isMaskLayer, self.isService, self.isVisible = mask, service, visible
        self.metricsLeft = self.metricsRight = self.metricsWidth = ""
        self.isNull = False
        self.hasHints = self.hasTTH = False
        self.log = glyph.pkg.log

    def removeShape(self, shape):  # noqa: N802 - native API
        self.shapes.remove(shape)
        self.log.append(("remove", self.glyph.name, self.name, shape.id))

    def addShape(self, shape):  # noqa: N802 - native API
        self.shapes.append(shape)
        self.log.append(("add", self.glyph.name, self.name, shape.id))

    def changed(self):
        pass

    def update(self):
        return True

    isValid = True  # noqa: N815 - native API
    isImg = False  # noqa: N815 - native API
    isImgLayer = False  # noqa: N815 - native API
    guidelines = note = recipe = lib = ""
    hasTTData = False  # noqa: N815 - native API
    position = None

    def isCompatible(self, other, strict):  # noqa: N802 - native API
        return not getattr(other, "incompatible", False)

    def getMasterPosition(self):  # noqa: N802 - native API
        return self.position

    def clone(self):
        copy = Layer(
            self.glyph,
            self.name,
            [s.clone() for s in self.shapes],
            width=self.advanceWidth,
            master=False,
        )
        copy.cloned_from = self
        return copy

    def getMaskLayer(self, create):  # noqa: N802 - native API
        return self.glyph.findLayer(f"mask.{self.name}")

    def getImgLayer(self, create):  # noqa: N802 - native API
        return None

    def setActive(self):  # noqa: N802 - native API
        self.glyph.active = self

    def addAnchor(self, pin):  # noqa: N802 - native API
        self.anchors.append(pin)

    def removeAnchor(self, pin):  # noqa: N802 - native API
        self.anchors.remove(pin)


class Glyph:
    def __init__(self, pkg, name):
        self.pkg, self.name, self.id = pkg, name, next(_IDS)
        self.layers = []
        self.isNull = False
        self.unicodes = []

    active = None
    metricsLeft = metricsRight = metricsWidth = ""

    def findLayer(self, name):  # noqa: N802 - native API
        return next((la for la in self.layers if la.name == name), None)

    def addLayer(self, layer):  # noqa: N802 - native API
        layer.glyph = self
        self.layers.append(layer)
        self.pkg.log.append(("addLayer", self.name, layer.name))

    def removeLayer(self, layer):  # noqa: N802 - native API
        self.layers.remove(layer)
        self.pkg.log.append(("removeLayer", self.name, layer.name))

    def bindDependencies(self):  # noqa: N802 - native API
        pass

    def updateActiveLayer(self, create):  # noqa: N802 - native API
        return self.active or self.layers[0]

    def interpolateInstance(self, location, create):  # noqa: N802 - native API
        made = Layer(
            self, "Interpolated", outline(len(self.layers[0].shapes)), master=False
        )
        made.position = {k.lower(): v for k, v in location.items()}
        return made


class Package:
    def __init__(self, masters=("Regular", "Bold")):
        self.id = next(_IDS)
        self.fgId = self.id + 1000
        self.isNull = False
        self.info = NS(unitsPerEm=1000)
        self.masters = list(masters)
        self.master = self.masters[0]
        self.glyphs = {}
        self.log = []
        self.axes = [NS(name="Weight", shortName="wt", designMin=100, designMax=900)]

    def add(self, name, layers):
        """``layers``: {layer name: kwargs for ``Layer``}."""
        glyph = Glyph(self, name)
        for layer, kwargs in layers.items():
            kwargs = dict(kwargs)
            master = kwargs.pop("master", layer in self.masters)
            glyph.layers.append(Layer(glyph, layer, master=master, **kwargs))
        self.glyphs[name] = glyph
        return glyph

    def findName(self, name):  # noqa: N802 - native API
        return self.glyphs.get(name)

    @property
    def fgPackage(self):  # noqa: N802 - native API
        return [
            NS(name=g.name, unicodes=list(g.unicodes)) for g in self.glyphs.values()
        ]

    def layer(self, name, layer):
        return self.glyphs[name].findLayer(layer)


def outline(count=1):
    return [Shape(1) for _ in range(count)]


def package():
    pkg = Package()
    pkg.add("A", {"Regular": dict(shapes=outline(2), width=600, anchors=[("top", 300, 700)]),
                  "Bold": dict(shapes=outline(1), width=650, anchors=[("top", 320, 720)])})  # fmt: skip
    pkg.add(
        "B",
        {
            "Regular": dict(shapes=outline(1), width=550),
            "Bold": dict(shapes=[], width=560, locked=True),
        },
    )
    pkg.add(
        "C",
        {
            "Regular": dict(shapes=[Shape(0, "A")], width=600),
            "Bold": dict(shapes=outline(1)),
        },
    )
    return pkg


class NativePin(Pin):
    def __init__(self, point):
        self.name, self.point, self.anchor = "", point, False


class Workspace:
    """``flWorkspace.instance()``: the open packages (each is its own ``flPackage``)."""

    def __init__(self):
        self.fonts = []

    def instance(self):
        return self

    def packages(self):
        return list(self.fonts)

    def findPackageId(self, fg_id):  # noqa: N802 - native API
        return next((p for p in self.fonts if p.fgId == fg_id), None)


ORPHAN = NS(name="", pkg=NS(log=[]))


class NativeFontLab:
    """The native ``fontlab`` module: the anchor writer's ``flPinPoint`` and the open fonts."""

    flPinPoint = NativePin  # noqa: N815 - native API

    def __init__(self):
        self.flWorkspace = Workspace()  # noqa: N815 - native API

    @staticmethod
    def flPackage(item):  # noqa: N802 - native API
        return item

    def AllFonts(self):  # noqa: N802 - native API
        return [NS(id=p.fgId, path=f"Font{p.fgId}.vfc") for p in self.flWorkspace.fonts]

    @staticmethod
    def flLayer():  # noqa: N802 - native API
        return Layer(ORPHAN, "", master=False)

    @staticmethod
    def flLocation(values):  # noqa: N802 - native API
        return dict(values)


class Recorder:
    """``AppShell.history`` stand-in: records the call, runs mutate and read-back."""

    def __init__(self, shell, refuse=None):
        self.shell, self.calls, self.refuse = shell, [], refuse

    def __call__(self, label, glyphs, mutate, *, layers, read_back=None, retain=(), allow_bases=False,
                 window=None):  # fmt: skip
        self.calls.append(
            NS(
                label=label,
                glyphs=[g.name for g in glyphs],
                layers=[(la.glyph.name, la.name) for la in layers],
                retain=list(retain),
                allow_bases=allow_bases,
                window=window,
            )  # fmt: skip
        )
        if self.refuse:
            self.shell.set_status(self.refuse)
            return None
        created = mutate()
        return NS(mismatches=list(read_back()) if read_back else [], pending_note="", pending_updates=(),
                  created=tuple(created or ()))  # fmt: skip


class Forbidden:
    def __call__(self, *args, **kwargs):
        raise AssertionError("read-only action opened history")


@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.core.edit_guards as edit_guards
    import fontlabapp.core.history.glyphs as history
    from fontlabapp.core.scripting import layer_manager_backends

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def load(self, *args):
            self.calls.append(args)

    monkeypatch.setattr(edit_guards, "pending_updates", lambda native=None: ())
    native = NativeFontLab()
    monkeypatch.setitem(sys.modules, "fontlab", native)
    facts = NS(value=history.auto_facts([]))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts.value)
    restored = []
    contour_copy = NS(restore_shape=lambda old, new, *a, **k: restored.append((old.id, new.id)),
                      repair_nodes=lambda old, new: None)  # fmt: skip

    active = NS(package=None)

    def open_app(
        pkg=None, selection=("A", "B", "C"), history_type=Recorder, extra=None
    ):
        pkg = package() if pkg is None else pkg
        active.package = pkg
        chosen = list(selection)
        layer_selection = NS(
            capture=lambda deadline: NS(occurrences=[NS(glyph_name=n) for n in chosen])
        )
        glyph_catalog = NS(
            capture=lambda: NS(rows=[(n,) for n in active.package.glyphs])
        )
        native.flWorkspace.fonts = [pkg]
        window_checks = []
        scripting = NS(current_package=lambda: active.package,
                       names_font_window_selection=lambda expected_fg_id, deadline: list(chosen))  # fmt: skip
        guards = NS(**{n: getattr(edit_guards, n) for n in ("append_note", "disclose", "pending_note")},
                    require_selection_window=window_checks.append, pending_updates=lambda native=None: (),
                    require_no_editors=lambda **kwargs: window_checks.append("no editors"))  # fmt: skip
        found = NS(**{**vars(layer_manager_backends()), "contour_copy": contour_copy, "selection": layer_selection,
                      "catalog": glyph_catalog, "scripting": scripting, "guards": guards, **(extra or {})})  # fmt: skip
        studio = importlib.import_module(PKG)
        shared = importlib.import_module(f"{PKG}._shared")
        monkeypatch.setattr(shared, "backends", lambda: found)
        kerning = sys.modules["fontlabapp.studios._kerning"]
        monkeypatch.setattr(kerning, "names_selected_names", lambda: list(chosen))
        preview = QtPreview()
        shell = studio.show(package=lambda: active.package, font=lambda: "font",
                            preview=lambda shell, tool: preview)  # fmt: skip
        studio_qt.owned.append(shell)
        tool = shell.layer_manager_tool
        recorder = history_type(shell)
        shell.history = recorder
        panels = {
            title: view.__self__ for title, view in zip(studio.TAB_TITLES, tool.views)
        }
        return NS(shell=shell, tool=tool, pkg=pkg, preview=preview, panels=panels, studio=studio, history=recorder,
                  selection=chosen, active=active, facts=facts, restored=restored, backends=found,
                  native=native, window_checks=window_checks)  # fmt: skip

    return open_app


def rows(panel, grid="grid"):
    return [(r.glyph_name, r.layer, tuple(r.values)) for r in getattr(panel, grid).rows]


def text(widget):
    value = widget.text
    return value() if callable(value) else value


# ---------------------------------------------------------------- shell, registry, parity
def test_show_when_opened_then_six_tabs_tglyph_preview_and_masters(opened):
    app = opened(history_type=lambda shell: Forbidden())
    assert app.studio.TAB_TITLES == ("Copy between masters", "Twins", "Backups", "Intermediate", "Clean-up",
                                     "Deliver")  # fmt: skip
    assert list(app.panels) == list(app.studio.TAB_TITLES)
    assert app.tool.app == "Layer Manager"
    assert app.tool.masters == ["Regular", "Bold"]
    assert app.tool.preview is app.preview
    assert app.pkg.log == []


def test_registry_when_imported_then_lazy_and_idempotent():
    import fontlabapp.studios as studios

    studio = importlib.import_module(PKG)
    assert studio.register_tabs() == studio.register_tabs() == studio.TAB_TITLES
    assert tuple(spec.title for spec in studios.tabs(studio.APP)) == studio.TAB_TITLES
    for module in {studio.PANELS[t][0] for t in studio.TAB_TITLES} | {"_shared", "app"}:
        assert f"{PKG}.{module}" not in sys.modules, module


def test_backends_when_loaded_then_reused_app_modules(monkeypatch):
    import fontlabapp.core.scripting as scripting

    found = scripting.layer_manager_backends()
    assert found.contour_copy.__name__ == "fontlabapp.contours.copy"
    assert found.outlines.__name__ == "fontlabapp.contours.writer"
    assert found.masters.__name__ == "fontlabapp.masters.inspect.model"
    assert found.selection.__name__ == "fontlabapp.masters.layers.selection"
    assert found.creation.__name__ == "fontlabapp.glyphs.creation"
    seen = []
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: seen.append(name) or NS(CurrentFont=lambda: "font"),
    )
    assert seen == [] and found.fontlab.CurrentFont() == "font" and seen == ["fontlab"]


def strip_fly(node):
    """Drop the originals' function-local ``fly`` imports (the ports read module names instead)."""
    for child in ast.walk(node):
        body = getattr(child, "body", None)
        if isinstance(body, list):
            child.body = [
                s
                for s in body
                if not (
                    isinstance(s, (ast.Import, ast.ImportFrom))
                    and "fly" in ast.unparse(s)
                )
            ]
    return node


def definitions(source):
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            found[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names = (
                    [target]
                    if isinstance(target, ast.Name)
                    else getattr(target, "elts", [])
                )
                found.update({n.id: node for n in names if isinstance(n, ast.Name)})
        elif isinstance(node, ast.AnnAssign):
            found[node.target.id] = node
    return found


def ported(title):
    found = {}
    for module in PORTS[title]:
        for name, node in definitions(
            (SOURCE / f"{module}.py").read_text(encoding="utf-8")
        ).items():
            found.setdefault(name, node)
    return found


@pytest.mark.parametrize("title", sorted(ORIGINALS))
def test_originals_when_ported_then_pure_functions_match_the_script_ast(title):
    _, path, digest, names, source = ORIGINALS[title]
    assert path.endswith(".py") and len(digest) == 64 and names
    expected, found = definitions(source), ported(title)
    assert set(names) <= set(expected), title
    for name in names:
        assert ast.dump(strip_fly(found[name])) == ast.dump(
            strip_fly(expected[name])
        ), f"{title}: {name}"


def test_originals_when_listed_then_all_ten_scripts_pinned():
    assert sorted(ORIGINALS) == sorted(PORTS)
    assert sum(repo == "examples" for repo, *_ in ORIGINALS.values()) == 1


@pytest.mark.parametrize("title", sorted(ORIGINALS))
def test_originals_when_checkout_present_then_pinned_hash_matches(title):
    repo, path, digest, _, _ = ORIGINALS[title]
    variable = {"scriptmix": "FONTLAB_SCRIPTMIX", "examples": "FONTLAB_EXAMPLES"}[repo]
    if not ENVS[repo]:
        pytest.skip(f"{variable} is not set: pinned {repo} hashes not checked")
    data = subprocess.run(["git", "-C", ENVS[repo], "show", f"{PINNED[repo]}:{path}"], capture_output=True,
                          check=False)  # fmt: skip
    if data.returncode:
        pytest.skip(
            f"pinned {repo} commit {PINNED[repo]} not available in {variable}={ENVS[repo]}"
        )
    assert hashlib.sha256(data.stdout).hexdigest() == digest


def test_label_when_one_or_many_glyphs_then_name_or_count(studio_qt):  # noqa: F811
    shared = importlib.import_module(f"{PKG}._shared")
    assert shared.label("copy layers", ["A", "A"]) == "Layer Manager: copy layers A"
    assert (
        shared.label("copy layers", ["A", "B"]) == "Layer Manager: copy layers 2 glyphs"
    )


# ---------------------------------------------------------------- Copy between masters
def test_copy_when_opened_then_plan_lists_targets_and_skips_without_writing(opened):
    app = opened(history_type=lambda shell: Forbidden())
    panel = app.panels["Copy between masters"]
    assert rows(panel) == [
        ("A", "Bold", ("Bold", 1, 2, "650", "600", "")),
        ("B", "Bold", ("Bold", "", "", "", "", "locked layer (skipped)")),
        ("C", "Bold", ("Bold", "", "", "", "", "source has no outline (skipped)")),
    ]
    assert text(panel.status) == "1 layer will be replaced from Regular"
    assert text(panel.subtitle) == "3 glyphs: A, B, C"
    assert not panel.target_checks["Regular"].isEnabled()
    panel.grid.select("A", "Bold")
    assert app.preview.calls[-1] == ("A", "Bold")
    assert app.pkg.log == []


def test_copy_when_applied_then_one_labelled_step_on_target_layer(opened):
    app = opened()
    panel = app.panels["Copy between masters"]
    target = app.pkg.layer("A", "Bold")
    panel.press()
    (call,) = app.history.calls
    assert call.label == "Layer Manager: copy layers A"
    assert (
        call.layers == [("A", "Bold")] and call.glyphs == ["A"] and call.window is None
    )
    assert len(target.shapes) == 2 and all(
        s.cloned_from in app.pkg.layer("A", "Regular").shapes for s in target.shapes
    )
    assert target.advanceWidth == 600
    assert (target.anchors[0].point.x(), target.anchors[0].point.y()) == (300, 700)
    assert len(app.restored) == 2
    assert text(panel.status) == "Replaced 1 layer in 1 glyph"
    source = app.pkg.layer("A", "Regular")
    assert len(source.shapes) == 2 and source.advanceWidth == 600


def test_copy_when_options_off_then_width_and_anchors_kept(opened):
    app = opened(selection=["A"])
    panel = app.panels["Copy between masters"]
    panel.copy_width.setChecked(False)
    panel.anchors.setChecked(False)
    panel.press()
    target = app.pkg.layer("A", "Bold")
    assert target.advanceWidth == 650 and target.anchors[0].point.x() == 320


def test_copy_when_source_changed_then_targets_rechecked_and_source_disabled(opened):
    app = opened(selection=["A"])
    panel = app.panels["Copy between masters"]
    panel.target_checks["Bold"].setChecked(False)
    assert (
        text(panel.status) == "Nothing to copy" and not panel.apply_button.isEnabled()
    )
    panel.source.setCurrentIndex(1)
    assert (
        panel.target_checks["Regular"].isChecked()
        and not panel.target_checks["Bold"].isEnabled()
    )
    assert rows(panel) == [("A", "Regular", ("Regular", 2, 1, "600", "650", ""))]


def test_copy_when_anchor_problems_then_original_notes(opened):
    pkg = package()
    pkg.add("D", {"Regular": dict(shapes=outline(), anchors=[("top", 0, 0)]),
                  "Bold": dict(shapes=outline(), anchors=[("top", 5, 5)])})  # fmt: skip
    pkg.add("E", {"Regular": dict(shapes=outline(), anchors=[("top", 1, 1), ("top", 2, 2)]),
                  "Bold": dict(shapes=outline())})  # fmt: skip
    pkg.add(
        "F",
        {
            "Regular": dict(shapes=outline(), anchors=[("bottom", 1, 1)]),
            "Bold": dict(shapes=outline()),
        },
    )
    pkg.glyphs["F"].findLayer("Bold").metricsLeft = "=A"
    pkg.add(
        "G",
        {
            "Regular": dict(shapes=outline(), anchors=[("bottom", 1, 1)]),
            "Bold": dict(shapes=outline()),
        },
    )
    app = opened(pkg, selection=["D", "E", "F", "G"])
    panel = app.panels["Copy between masters"]
    assert [r[2][-1] for r in rows(panel)] == [
        "anchor top would move to 0, 0; FontLab cannot redo it (fl#8527)",
        "several anchors named top (skipped)",
        "metrics link or expression (skipped)",
        "",
    ]
    panel.press()
    assert (
        text(panel.status)
        == "Replaced 1 layer in 1 glyph · anchors missing in targets: bottom"
    )


def test_copy_when_no_selection_or_font_changed_then_original_refusals(opened):
    app = opened(selection=[])
    panel = app.panels["Copy between masters"]
    assert (
        text(panel.subtitle)
        == "Select glyphs in the Font window. Then press Use selection."
    )
    assert not panel.apply_button.isEnabled()
    app.selection.append("A")
    panel.reselect_button.click()
    assert rows(panel)[0][0] == "A"
    app.active.package = package()
    panel.press()
    assert text(panel.status) == "The font changed. Run this script again."
    assert app.history.calls == []
    app.active.package = None
    panel.reselect()
    assert (
        text(panel.subtitle)
        == "Open a font and select glyphs. Then run this script again."
    )


def test_copy_when_font_edited_after_list_then_stale_refusal_and_no_write(opened):
    app = opened(selection=["A"])
    panel = app.panels["Copy between masters"]
    app.pkg.layer("A", "Regular").shapes.append(Shape(1))
    panel.press()
    assert (
        text(panel.status)
        == "The layers changed since the list was made; check the list again."
    )
    assert app.history.calls == []
    assert rows(panel)[0][2][2] == 3


def test_copy_when_history_refuses_or_read_back_misses_then_status_kept(
    opened, monkeypatch
):
    app = opened(
        selection=["A"],
        history_type=lambda shell: Recorder(shell, refuse="Refused: Glyph window"),
    )
    panel = app.panels["Copy between masters"]
    panel.press()
    assert app.shell.status.text() == "Refused: Glyph window"
    assert len(app.pkg.layer("A", "Bold").shapes) == 1
    app.shell.history = Recorder(app.shell)
    monkeypatch.setattr(Layer, "update", lambda self: True)
    target = app.pkg.layer("A", "Bold")
    monkeypatch.setattr(target, "addShape", lambda shape: None, raising=False)
    panel.press()
    assert "did not read back as planned: A · Bold: 0 contours, planned 2" in text(
        panel.status
    )


def test_copy_when_clone_loses_contours_or_update_fails_then_runtime_errors(
    studio_qt,  # noqa: F811
    opened,
):
    app = opened(selection=["A"])
    copy = importlib.import_module(f"{PKG}.copy_masters")
    shape = Shape(2)
    shape.clone = lambda: Shape(1)
    with pytest.raises(
        RuntimeError, match="FontLab clone changed the contour count of a shape."
    ):
        copy.clone_shape(shape)
    app.pkg.layer("A", "Bold").update = lambda: False
    app.history.calls.clear()
    with pytest.raises(RuntimeError, match="FontLab could not update 'A' in 'Bold'."):
        pairs = app.panels["Copy between masters"].plan()
        copy.copy_pairs(NS(shell=NS(history=lambda *a, **k: k and a[2]())), pairs)
    assert copy.copy_pairs(app.tool, [])["layers"] == 0


# ---------------------------------------------------------------- Twins
def test_twins_when_opened_then_copy_and_kept_rows_without_writing(opened):
    app = opened(history_type=lambda shell: Forbidden())
    panel = app.panels["Twins"]
    assert rows(panel) == [
        ("A", "Bold", ("Regular", "Bold", "copy")),
        ("C", "Bold", ("Regular", "Bold", "copy")),
        ("B", None, ("", "", "kept: locked layer")),
    ]
    assert (
        text(panel.status)
        == "2 layers to copy · 1 kept. Check master compatibility afterwards."
    )
    assert app.pkg.log == []


def test_twins_when_copied_then_one_step_retains_removed_components(
    opened, monkeypatch
):
    app = opened(selection=["C"])
    import fontlabapp.core.history.glyphs as history

    monkeypatch.setattr(
        history, "component_history", lambda shape: [("kept", shape.id)]
    )
    pkg = app.pkg
    pkg.add(
        "D", {"Regular": dict(shapes=outline(1)), "Bold": dict(shapes=[Shape(0, "A")])}
    )
    app.selection[:] = ["D"]
    panel = app.panels["Twins"]
    panel.reselect()
    removed = pkg.layer("D", "Bold").shapes[0]
    panel.press()
    (call,) = app.history.calls
    assert call.label == "Layer Manager: copy twins D"
    assert call.layers == [("D", "Bold")] and call.retain == [("kept", removed.id)]
    target = pkg.layer("D", "Bold")
    assert [s.cloned_from for s in target.shapes] == pkg.layer("D", "Regular").shapes
    assert text(panel.status) == "Copied 1 layers."
    assert len(pkg.layer("D", "Regular").shapes) == 1


def test_twins_when_options_change_then_original_refusals(opened):
    app = opened(selection=[])
    panel = app.panels["Twins"]
    assert text(panel.subtitle) == "Select glyphs or choose All glyphs."
    panel.all_glyphs.setChecked(True)
    assert {r[0] for r in rows(panel)} == {"A", "B", "C"}
    for box in panel.switches:
        box.setChecked(False)
    assert text(panel.subtitle) == "Choose at least one content kind."
    panel.to_master.setCurrentIndex(0)
    assert text(panel.subtitle) == "Choose two different masters."
    app.active.package = package()
    panel.press()
    assert text(panel.status) == "The font changed; press Refresh."
    app.active.package = Package(masters=("Regular",))
    panel.reselect_button.click()
    assert text(panel.subtitle) == "Open a font with at least two masters."


def test_twins_when_read_back_fails_then_undo_hint_appended(opened):
    app = opened(selection=["A"])
    panel = app.panels["Twins"]
    app.pkg.layer("A", "Bold").addShape = lambda shape: None
    panel.press()
    assert text(panel.status).endswith(
        " Native changes may remain; use Edit > Undo"
    ) or "Edit > Undo" in text(panel.status)
    assert len(app.history.calls) == 1


# ---------------------------------------------------------------- Backups
def backups(app, mode):
    tab = app.panels["Backups"]
    titles = [t for t, _ in tab.MODES]
    tab.mode.setCurrentIndex(titles.index(mode))
    assert tab.current().widget.isVisibleTo(tab.widget)
    return tab.current()


def test_backups_when_backed_up_then_new_layers_not_master_not_auto_one_step(opened):
    pkg = package()
    pkg.add("D", {"Regular": dict(shapes=outline(1)), "Bold": dict(shapes=outline(1)),
                  "Regular backup old": dict(shapes=outline(1), master=False)})  # fmt: skip
    app = opened(pkg, selection=["A", "D"])
    panel = backups(app, "Back up")
    panel.suffix.setText("v1")
    panel.scope_choice.setCurrentIndex(1)
    assert rows(panel) == [
        ("A", "Regular", ("Regular", "Regular backup v1", "New backup")),
        ("A", "Bold", ("Bold", "Bold backup v1", "New backup")),
        ("D", "Regular", ("Regular", "Regular backup v1", "New backup")),
        ("D", "Bold", ("Bold", "Bold backup v1", "New backup")),
        ("D", None, ("", "Regular backup old", "Existing backup")),
    ]
    panel.press()
    (call,) = app.history.calls
    assert (
        call.label == "Layer Manager: back up 2 glyphs"
        and call.layers == []
        and call.glyphs == ["A", "D"]
    )
    made = pkg.layer("A", "Bold backup v1")
    assert (
        made.cloned_from is pkg.layer("A", "Bold")
        and made.isMasterLayer is False
        and made.autoLayer is False
    )
    assert text(panel.status) == "Created 4 backup layer(s)"
    assert len(pkg.layer("A", "Bold").shapes) == 1


def test_backups_when_suffix_invalid_or_no_selection_then_shared_refusals(opened):
    app = opened(selection=["A"], history_type=lambda shell: Forbidden())
    panel = backups(app, "Back up")
    panel.suffix.setText("a@b")
    assert text(panel.subtitle) == "Backup names must not contain @, # or |temp|."
    app.selection.clear()
    panel.reselect()
    assert text(panel.subtitle) == "Select a glyph first."


def test_backups_when_restored_with_delete_then_retains_and_removes_backup(
    opened, monkeypatch
):
    import fontlabapp.core.history.glyphs as history

    monkeypatch.setattr(
        history, "component_history", lambda shape: [("kept", shape.id)]
    )
    pkg = package()
    glyph = pkg.glyphs["A"]
    backup = Layer(
        glyph,
        "Regular backup v1",
        outline(3),
        width=610,
        anchors=[("top", 1, 2)],
        master=False,
    )
    mask = Layer(
        glyph, "mask.Regular backup v1", [Shape(0, "B")], master=False, mask=True
    )
    glyph.layers += [backup, mask]
    app = opened(pkg, selection=["A", "B"])
    panel = backups(app, "Restore")
    assert [panel.backup.itemText(i) for i in range(panel.backup.count())] == [
        "Regular backup v1"
    ]
    assert rows(panel) == [
        ("A", "Regular", ("Regular", "2 → 3", "600 → 610", "")),
        ("B", None, ("", "", "", "no layer with this name")),
    ]
    assert (
        text(panel.status)
        == "1 glyph will get “Regular backup v1” back · cells read now → after"
    )
    panel.delete_after.setChecked(True)
    panel.press()
    (call,) = app.history.calls
    assert call.label == "Layer Manager: restore backup A" and call.layers == [
        ("A", "Regular")
    ]
    assert call.retain == [("kept", s.id) for s in backup.shapes + mask.shapes]
    target = pkg.layer("A", "Regular")
    assert len(target.shapes) == 3 and target.advanceWidth == 610
    assert backup not in glyph.layers and mask not in glyph.layers
    assert text(panel.status) == "Restored 1 master layer in 1 glyph · deleted 2 layers"
    assert [panel.backup.itemText(i) for i in range(panel.backup.count())] == []


def test_backups_when_restore_backup_shown_then_kept_and_counted(opened):
    pkg = package()
    glyph = pkg.glyphs["A"]
    backup = Layer(glyph, "Regular backup v1", outline(1), master=False)
    glyph.layers.append(backup)
    glyph.active = backup
    app = opened(pkg, selection=["A"])
    panel = backups(app, "Restore")
    panel.delete_after.setChecked(True)
    panel.press()
    assert backup in glyph.layers
    assert (
        text(panel.status)
        == "Restored 1 master layer in 1 glyph · kept 1 shown backup(s)"
    )


def test_backups_when_no_backup_then_original_refusal_in_status(opened):
    app = opened(selection=["A"], history_type=lambda shell: Forbidden())
    panel = backups(app, "Restore")
    assert (
        text(panel.status)
        == "No backup layers in these glyphs. Make some with Duplicate Current Layer."
    )
    assert not panel.apply_button.isEnabled()


def test_backups_when_used_as_master_then_renames_in_one_step(opened):
    pkg = package()
    glyph = pkg.glyphs["A"]
    alt = Layer(glyph, "Regular@ old", outline(1), master=False)
    glyph.layers.append(alt)
    old = pkg.layer("A", "Regular")
    app = opened(pkg, selection=["A", "B"])
    panel = backups(app, "Use as master")
    assert [panel.layer.itemText(i) for i in range(panel.layer.count())] == [
        "Regular@ old"
    ]
    stamp = panel.stamp
    assert rows(panel) == [
        ("A", "Regular", ("master", "Regular", f"Regular@ {stamp}")),
        ("A", "Regular@ old", ("chosen", "Regular@ old", "Regular")),
    ]
    panel.apply()
    (call,) = app.history.calls
    assert call.label == "Layer Manager: use as master A"
    assert sorted(call.layers) == [
        ("A", "Regular"),
        ("A", "Regular@ old"),
    ]  # names before the renames
    assert alt.name == "Regular" and old.name == f"Regular@ {stamp}"
    assert text(panel.status) == "A: 'Regular@ old' is now the master layer"


def test_backups_when_master_locked_or_rename_kept_then_refused_and_names_restored(
    opened, monkeypatch
):
    pkg = package()
    glyph = pkg.glyphs["B"]
    glyph.layers.append(Layer(glyph, "Bold@ old", outline(1), master=False))
    app = opened(pkg, selection=["B"], history_type=lambda shell: Forbidden())
    panel = backups(app, "Use as master")
    assert (
        text(panel.subtitle)
        == "Layer 'Bold' of 'B' is locked, automatic, a mask or a service layer."
    )
    assert not panel.apply_button.isEnabled()
    mod = importlib.import_module(f"{PKG}._use_master")
    a, b = NS(name="x"), NS(name="y")

    class Sticky(NS):
        def __setattr__(self, key, value):
            if value != "z":
                object.__setattr__(self, key, value)

    c = Sticky(name="c")
    jobs = [{"glyph": NS(name="G"), "steps": [("master", "x", "x2"), ("chosen", "c", "z")],
             "targets": {"master": a, "chosen": c, "master mask": None, "chosen mask": None}}]  # fmt: skip
    shell = NS(history=lambda title, glyphs, mutate, **k: mutate())
    with pytest.raises(RuntimeError, match="FontLab kept the name 'c' instead of 'z'."):
        mod.apply_renames(NS(shell=shell), jobs)
    assert a.name == "x" and b.name == "y"


# ---------------------------------------------------------------- Intermediate
def test_intermediate_when_added_then_location_layers_in_one_step_not_master(opened):
    app = opened()
    panel = app.panels["Intermediate"]
    assert (
        list(panel.axis_controls) == ["wt"] and panel.axis_controls["wt"].value() == 500
    )
    panel.axis_controls["wt"].setValue(550)
    assert rows(panel) == [
        ("A", None, (":wt=550", "add interpolated layer")),
        ("B", None, (":wt=550", "kept: locked, service or image master layer")),
        ("C", None, (":wt=550", "add interpolated layer")),
    ]
    panel.press()
    (call,) = app.history.calls
    assert (
        call.label == "Layer Manager: add intermediate layers 2 glyphs"
        and call.layers == []
    )
    made = app.pkg.layer("A", ":wt=550")
    assert (
        made.isMasterLayer is False
        and made.autoLayer is False
        and made.position == {"wt": 550.0}
    )
    assert (
        text(panel.status)
        == "Added 2 intermediate layer(s); B: kept: locked, service or image master layer"
    )
    panel.redraw()
    assert rows(panel)[0][2][1] == "kept: layer already exists"


def test_intermediate_when_no_axes_or_add_fails_then_original_refusals(
    opened, monkeypatch
):
    pkg = package()
    pkg.axes = []
    app = opened(pkg, history_type=lambda shell: Forbidden())
    panel = app.panels["Intermediate"]
    assert (
        text(panel.subtitle)
        == "Declare axes with unique short names in Font Info first."
    )
    pkg2 = package()
    pkg2.layer("C", "Bold").incompatible = True
    app2 = opened(pkg2, selection=["A", "C"])
    panel = app2.panels["Intermediate"]
    assert rows(panel)[1][2][1] == "kept: master outlines are incompatible"
    monkeypatch.setattr(Glyph, "addLayer", lambda self, layer: None)
    panel.press()
    assert text(panel.status) == (
        "FontLab did not finish adding layers: A: FontLab did not add the layer.. Native changes may remain; use Edit > Undo."
    )


# ---------------------------------------------------------------- Clean-up
def cleanup(app, mode):
    tab = app.panels["Clean-up"]
    tab.mode.setCurrentIndex([t for t, _ in tab.MODES].index(mode))
    assert tab.current().widget.isVisibleTo(tab.widget)
    return tab.current()


def extra_package():
    pkg = package()
    glyph = pkg.glyphs["A"]
    for name, kwargs in (("mask.Regular", dict(shapes=outline(1), mask=True)),
                         ("Regular backup v1", dict(shapes=[Shape(0, "C")])),
                         ("Regular#alt", dict(shapes=outline(1))), ("sketch", dict()),
                         ("held", dict(shapes=outline(1), locked=True))):  # fmt: skip
        glyph.layers.append(Layer(glyph, name, master=False, **kwargs))
    return pkg


def test_cleanup_when_ticked_by_kind_then_one_step_deletes_and_retains(
    opened, monkeypatch
):
    import fontlabapp.core.history.glyphs as history

    monkeypatch.setattr(
        history, "component_history", lambda shape: [("kept", shape.id)]
    )
    app = opened(extra_package(), selection=["A"])
    panel = cleanup(app, "Delete ticked")
    assert rows(panel) == [
        ("A", "mask.Regular", ("mask.Regular", "mask", 1, "")),
        ("A", "Regular backup v1", ("Regular backup v1", "backup", 0, "")),
        ("A", "Regular#alt", ("Regular#alt", "alternate", 1, "")),
        ("A", "sketch", ("sketch", "other", 0, "")),
        ("A", "held", ("held", "other", "locked layer (kept)", "")),
    ]
    assert (
        text(panel.status) == "5 extra layers · 0 ticked for deletion"
        and not panel.apply_button.isEnabled()
    )
    panel.kind_buttons["backup"].click()
    assert [r[2][3] for r in rows(panel)] == ["", "yes", "", "", ""]
    panel.grid.select("A", "sketch")
    panel.row_button.click()
    panel.grid.select("A", "held")
    panel.row_button.click()
    assert text(panel.status) == "5 extra layers · 2 ticked for deletion"
    backup = app.pkg.layer("A", "Regular backup v1")
    panel.press()
    (call,) = app.history.calls
    assert call.label == "Layer Manager: delete layers A" and call.layers == [
        ("A", "Regular")
    ]
    assert call.retain == [("kept", backup.shapes[0].id)]
    assert (
        app.pkg.layer("A", "sketch") is None and app.pkg.layer("A", "held") is not None
    )
    assert text(panel.status) == "Deleted 2 layers from 1 glyph"
    panel.none_button.click()
    assert text(panel.status) == "3 extra layers · 0 ticked for deletion"


def test_cleanup_when_layers_change_after_ticking_then_original_refusal(opened):
    app = opened(extra_package(), selection=["A"])
    panel = cleanup(app, "Delete ticked")
    panel.kind_buttons["other"].click()
    glyph = app.pkg.glyphs["A"]
    glyph.layers.remove(glyph.findLayer("sketch"))
    panel.press()
    assert text(panel.status) == "The layers changed. Check the table and tick again."
    assert app.history.calls == []
    app.selection.clear()
    panel.reselect()
    assert (
        text(panel.subtitle)
        == "Select glyphs in the Font window. Then press Use selection."
    )


def test_empty_when_listed_then_deletes_in_one_step_and_skips_shown(opened):
    app = opened(extra_package(), selection=["A", "B"])
    panel = cleanup(app, "Empty layers")
    glyph = app.pkg.glyphs["A"]
    glyph.layers.append(Layer(glyph, "blank", master=False))
    panel.reselect()
    glyph.active = glyph.findLayer("blank")
    panel.reselect()
    assert rows(panel) == [
        ("A", "sketch", ("sketch", "delete")),
        ("A", None, ("blank", "skipped: shown layer")),
    ]
    assert text(panel.status) == "1 empty layer will be deleted · 1 skipped"
    panel.press()
    (call,) = app.history.calls
    assert call.label == "Layer Manager: delete empty layers A" and call.layers == [
        ("A", "Regular")
    ]
    assert call.retain == []
    assert (
        text(panel.status)
        == "Deleted 1 empty layer from 1 glyph: A/sketch. Skipped 1: A/blank: shown layer."
    )
    assert text(panel.status) != ""
    panel.redraw()
    assert text(panel.status) == "No empty layer in the selected glyphs."


# ---------------------------------------------------------------- Deliver
def deliver_mode(app, mode):
    tab = app.panels["Deliver"]
    tab.mode.setCurrentIndex([t for t, _ in tab.MODES].index(mode))
    assert tab.current().widget.isVisibleTo(tab.widget)
    return tab.current()


def snapshot(pkg):
    """Everything a cross-font write could touch in ``pkg``."""
    return [
        (g.name, la.name, [s.id for s in la.shapes], la.advanceWidth,
         [(p.name, p.point.x(), p.point.y()) for p in la.anchors], tuple(g.unicodes))
        for g in pkg.glyphs.values() for la in g.layers
    ]  # fmt: skip


def creation_fake(calls):
    import fontlabapp.glyphs.creation as creation

    def create_glyphs(target, specs, title, facts, allow_rebuild=False):
        calls.append((title, [s.name for s in specs], allow_rebuild))
        for spec in specs:
            glyph = target.add(
                spec.name, {m: dict(shapes=[], width=w) for m, w in spec.layers}
            )
            glyph.unicodes = list(spec.unicodes)
        return NS(mismatches=[], glyphs=[s.name for s in specs])

    return NS(REBUILD_LABEL=creation.REBUILD_LABEL, UNDO_TEXT=creation.UNDO_TEXT, NewGlyph=creation.NewGlyph,
              rebuild_note=creation.rebuild_note, create_glyphs=create_glyphs, auto_signatures=lambda t, f: {},
              auto_changes=lambda t, before: [], auto_candidates=lambda t, f, names: {})  # fmt: skip


def deliver_app(opened, selection=("A", "C")):
    made = []
    app = opened(selection=selection, extra={"creation": creation_fake(made)})
    app.pkg.glyphs["A"].unicodes = [0x41]
    destination = Package()
    app.native.flWorkspace.fonts.append(destination)
    return app, destination, made


def test_deliver_when_previewed_and_delivered_then_only_destination_written_in_one_step(
    opened,
):
    app, destination, made = deliver_app(opened)
    panel = deliver_mode(app, "Deliver glyphs")
    assert (
        text(panel.subtitle)
        == "2 source glyphs · activate a destination Font window, then Preview"
    )
    source, before = app.pkg, snapshot(app.pkg)
    app.active.package = destination
    panel.preview()
    assert rows(panel) == [
        ("A", "Regular", ("Regular", "Regular", "add; Unicode assigned on creation")),
        ("A", "Bold", ("Bold", "Bold", "add; Unicode assigned on creation")),
        (
            "C",
            None,
            (
                "",
                "",
                "kept: Components cannot be delivered; use plain outlines or FontLab's native Paste.",
            ),
        ),
    ]
    assert text(panel.status) == "1 glyphs to deliver · 1 kept"
    assert app.history.calls == []
    app.window_checks.clear()
    panel.press()
    assert made == [("Layer Manager: deliver glyphs A", ["A"], False)]
    (call,) = app.history.calls
    assert call.label == "Layer Manager: deliver glyphs A" and call.glyphs == ["A"]
    assert (
        call.layers == [("A", "Regular"), ("A", "Bold")] and call.allow_bases is False
    )
    assert app.window_checks == [destination.id, "no editors"]
    assert snapshot(source) == before, "the source font must stay unchanged"
    delivered = destination.glyphs["A"]
    assert [len(la.shapes) for la in delivered.layers] == [2, 1]
    assert [la.advanceWidth for la in delivered.layers] == [600, 650]
    assert delivered.unicodes == [0x41]
    assert text(panel.status) == "Delivered 1 glyphs in 2 layers; 1 added."


def test_deliver_when_same_font_stale_or_reloaded_then_original_refusals(opened):
    app, destination, _ = deliver_app(opened)
    panel = deliver_mode(app, "Deliver glyphs")
    panel.preview()
    assert text(panel.status) == "Activate a different destination font."
    assert not panel.apply_button.isEnabled()
    app.active.package = destination
    panel.preview()
    destination.add("A", {"Regular": {}, "Bold": {}})
    panel.press()
    assert text(panel.status) == "The delivery changed; click Preview again."
    panel.preview()
    app.tool.reload()
    assert text(panel.status) == "The fonts changed; click Preview again."
    assert app.history.calls == []
    assert panel.source_names == ["A", "C"], "a reload never rebinds the source"


def test_deliver_when_no_source_selection_then_original_refusal(opened):
    app, _, _ = deliver_app(opened, selection=())
    panel = deliver_mode(app, "Deliver glyphs")
    assert text(panel.status) == "Select source glyphs, then reopen this panel."
    panel.preview()
    assert text(panel.status) == "Reopen this tool with a source selection."


def from_font_app(opened):
    app = opened(selection=["A", "B"])
    source = package()
    source.layer("A", "Regular").shapes = outline(3)
    source.layer("A", "Regular").advanceWidth = 610
    source.layer("A", "Regular").anchors = [Pin("top", 310, 710)]
    app.native.flWorkspace.fonts.append(source)
    panel = deliver_mode(app, "Copy layers from font")
    panel.guarded(panel.reload_selection)()
    return app, source, panel


def test_from_font_when_copied_then_one_destination_step_with_window_guard(opened):
    app, source, panel = from_font_app(opened)
    assert (
        text(panel.status) == "2 destination glyphs selected. Edit the mapping names."
    )
    assert get_text(panel.source_picker) == f"Font{source.fgId}.vfc [{source.fgId}]"
    before = snapshot(source)
    panel.guarded(panel.preview_copy)()
    assert rows(panel) == [("A", "Regular", ("Regular", "Regular", "Copy")),
                           ("B", "Regular", ("Regular", "Regular", "Copy"))]  # fmt: skip
    panel.guarded(panel.copy_rows)()
    assert text(panel.status) == "Preview and confirm the destination changes."
    assert app.history.calls == []
    panel.guarded(panel.preview_copy)()
    panel.confirm_box.setChecked(True)
    panel.guarded(panel.copy_rows)()
    (call,) = app.history.calls
    assert (
        call.label == "Layer Manager: copy layers from font 2 glyphs"
        and call.window == app.pkg.id
    )
    assert call.layers == [("A", "Regular"), ("B", "Regular")] and call.glyphs == [
        "A",
        "B",
    ]
    assert snapshot(source) == before, "the source font must stay unchanged"
    target = app.pkg.layer("A", "Regular")
    assert len(target.shapes) == 3 and target.advanceWidth == 610
    assert [(p.name, p.point.x(), p.point.y()) for p in target.anchors] == [
        ("top", 310, 710)
    ]
    assert text(panel.status) == "Copied 2 layers; kept 0. One Undo step."
    panel.guarded(panel.copy_rows)()
    assert text(panel.status) == "Preview first."


def test_from_font_when_incoming_suffix_then_new_layer_is_not_master_or_auto(opened):
    app, source, panel = from_font_app(opened)
    panel.mode_picker.setCurrentIndex(1)
    panel.guarded(panel.preview_copy)()
    assert rows(panel)[0] == ("A", "Regular.copy", ("Regular", "Regular.copy", "Copy"))
    panel.confirm_box.setChecked(True)
    panel.guarded(panel.copy_rows)()
    (call,) = app.history.calls
    assert call.layers == [], "a new layer is created inside the step"
    made = app.pkg.layer("A", "Regular.copy")
    assert made.isMasterLayer is False and made.autoLayer is False
    assert len(made.shapes) == 3 and len(app.pkg.layer("A", "Regular").shapes) == 2


def test_from_font_when_fonts_change_then_original_refusals(opened):
    app, source, panel = from_font_app(opened)
    panel.guarded(panel.preview_copy)()
    panel.confirm_box.setChecked(True)
    source.layer("A", "Regular").advanceWidth = 620
    panel.guarded(panel.copy_rows)()
    assert text(panel.status) == "Source or destination changed; Preview again."
    panel.guarded(panel.preview_copy)()
    panel.confirm_box.setChecked(True)
    app.active.package = source
    panel.guarded(panel.copy_rows)()
    assert (
        text(panel.status)
        == "Keep both fonts open and the destination current; choose another source."
    )
    app.active.package = app.pkg
    app.native.flWorkspace.fonts.remove(source)
    panel.guarded(panel.reload_selection)()
    panel.guarded(panel.preview_copy)()
    assert text(panel.status) == "Choose another open source font."
    panel.mapping_table.setRowCount(2)
    app.native.flWorkspace.fonts.append(source)
    panel.guarded(panel.reload_selection)()
    panel.guarded(panel.add_mapping)()
    panel.guarded(panel.preview_copy)()
    assert text(panel.status) == "Fill both layer names in every mapping row."
    assert app.history.calls == []


def test_from_font_when_name_or_collision_invalid_then_original_text(studio_qt):  # noqa: F811
    from fontlabapp.studios.layer_manager import _from_font

    with pytest.raises(ValueError, match="Use a nonempty layer name"):
        _from_font.checked_name("Regular@1")
    with pytest.raises(ValueError, match="Choose a listed collision mode."):
        _from_font.collision("Regular", ".copy", "Merge", True)
    with pytest.raises(ValueError, match="Enter a nonempty suffix."):
        _from_font.collision("Regular", "", "Incoming + suffix", True)
    assert _from_font.collision("Regular", ".b", "Destination + suffix", True) == (
        "Regular",
        "Regular.b",
    )


def _plain_layer(**over):
    base = dict(
        isNull=False, autoLayer=False, isLocked=False, isService=False, hasHints=False, hasTTH=False,
        guidelines=[], metricsLeft="", metricsRight="", metricsWidth="", shapes=[], anchors=[],
    )  # fmt: skip
    base.update(over)
    return NS(**base)


def _node(**over):
    base = dict(getProperties=lambda: {}, getProperty=lambda _k: None)
    base.update(over)
    return NS(**base)


def _source_shape(contour):
    return NS(isComponent=False, contours=[contour])


@pytest.mark.parametrize(
    ("layer", "message"),
    [
        (None, "layer is missing"),
        (_plain_layer(isNull=True), "layer is missing"),
        (_plain_layer(autoLayer=True), "automatic, locked or service layer"),
        (_plain_layer(isLocked=True), "automatic, locked or service layer"),
        (_plain_layer(isService=True), "automatic, locked or service layer"),
        (_plain_layer(hasHints=True), "hints or guides are not transferred"),
        (_plain_layer(hasTTH=True), "hints or guides are not transferred"),
        (_plain_layer(guidelines=["g"]), "hints or guides are not transferred"),
        (_plain_layer(metricsLeft="=A"), "metric expressions are not transferred"),
        (_plain_layer(metricsWidth="=A"), "metric expressions are not transferred"),
        (_plain_layer(shapes=[NS(isComponent=True)]), "components are not transferred"),
        (_plain_layer(anchors=[NS(name="top"), NS(name="top")]), "repeated anchor names"),
        (
            _plain_layer(shapes=[_source_shape(NS(getProperties=lambda: {"k": 1}, nodes=lambda: []))]),
            "custom node or contour properties",
        ),
        (
            _plain_layer(shapes=[_source_shape(NS(getProperties=lambda: {}, nodes=lambda: [_node(getProperties=lambda: {"k": 1})]))]),
            "custom node or contour properties",
        ),
        (
            _plain_layer(shapes=[_source_shape(NS(getProperties=lambda: {}, nodes=lambda: [_node(getProperty=lambda _k: 0.5)]))]),
            "custom node or contour properties",
        ),
    ],
)  # fmt: skip
def test_from_font_usable_when_content_cannot_transfer_then_refuses(
    studio_qt,  # noqa: F811
    layer,
    message,
):
    from fontlabapp.studios.layer_manager import _from_font

    with pytest.raises(ValueError, match=message):
        _from_font.usable(layer, source=True)


def test_from_font_usable_when_destination_has_properties_then_not_inspected(studio_qt):  # noqa: F811
    from fontlabapp.studios.layer_manager import _from_font

    contour = NS(getProperties=lambda: {"k": 1}, nodes=lambda: [])
    _from_font.usable(_plain_layer(shapes=[_source_shape(contour)]), source=False)


def _capture_layer(x=1.0, width=500.0, contours=1):
    node = NS(x=x, y=2.0, isOn=lambda: True, nodeState=0x21, name="n")
    contour = NS(closed=True, isTT=False, name="c", nodes=lambda: [node])
    matrix = NS(
        **{
            f"m{i}{j}": (lambda i=i, j=j: float(i == j))
            for i in (1, 2, 3)
            for j in (1, 2, 3)
        }
    )
    shape = NS(
        name="s",
        shapeData=NS(name="d", note=""),
        transform=matrix,
        contours=[contour] * contours,
    )
    anchor = NS(name="top", point=NS(x=lambda: 3, y=lambda: 4))
    return NS(shapes=[shape], anchors=[anchor], advanceWidth=width)


def test_from_font_layer_data_when_captured_then_masks_selection_bit(studio_qt):  # noqa: F811
    from fontlabapp.studios.layer_manager import _from_font

    data = _from_font.layer_data(_capture_layer(), float("inf"))
    assert data["width"] == 500.0 and data["anchors"] == (("top", 3.0, 4.0),)
    (shape,) = data["shapes"]
    assert shape[4][0][3] == ((1.0, 2.0, True, 1, "n"),), (
        "bit 0x20 is dropped from nodeState"
    )


def test_from_font_layer_data_when_deadline_passed_then_times_out(studio_qt):  # noqa: F811
    from fontlabapp.studios.layer_manager import _from_font

    with pytest.raises(TimeoutError, match="Layer capture expired"):
        _from_font.layer_data(_capture_layer(), 0.0)


def test_from_font_layer_data_when_not_finite_then_refuses(studio_qt):  # noqa: F811
    from fontlabapp.studios.layer_manager import _from_font

    with pytest.raises(ValueError, match="must be finite"):
        _from_font.layer_data(_capture_layer(x=float("inf")), float("inf"))


def get_text(combo):
    value = combo.currentText
    return value() if callable(value) else value


# ---------------------------------------------------------------- demo and window assembly
def test_demo_when_run_then_shows_or_warns(monkeypatch):
    import fontlabapp
    import fontlabapp.qt.dialogs as dialogs

    calls = []
    studio = importlib.import_module(PKG)
    monkeypatch.setattr(studio, "show", lambda: calls.append("show"))
    runpy.run_path(str(DEMO), run_name="__main__")
    assert calls == ["show"]

    def broken():
        raise RuntimeError("no font")

    monkeypatch.setattr(studio, "show", broken)
    stub_natives(monkeypatch, fontlabapp, lambda name: NS(MainWindow=lambda: 'main', QtGui=NS(QMessageBox=NS(Ok=1))))  # fmt: skip
    monkeypatch.setattr(
        dialogs, "run_standard_message_box", lambda *a: calls.append(a[2:5])
    )
    runpy.run_path(str(DEMO), run_name="__main__")
    assert calls[-1] == (
        "Layer Manager Demo",
        "Layer Manager did not open: no font",
        "Warning",
    )
    assert runpy.run_path(str(DEMO), run_name="demo")["TITLE"] == "Layer Manager Demo"


@pytest.mark.usefixtures("studio_qt")
def test_app_when_default_preview_then_controlless_tglyph_on_current_master(
    monkeypatch,
):
    import fontlabapp.fontui as fontui

    app_module = importlib.import_module(f"{PKG}.app")
    seen = []
    monkeypatch.setattr(
        fontui,
        "glyph_view",
        lambda font, parent, **kw: seen.append((font, parent, kw)) or "view",
    )
    pkg = Package()
    shell = NS(widget="widget", hint_check="check", package=lambda: pkg)
    tool = app_module.tool_for(shell)
    assert app_module.tool_for(shell) is tool and tool.app == "Layer Manager"
    tool._font = lambda: None
    assert app_module.glyph_preview(shell, tool) is None
    tool._font = lambda: "font"
    assert app_module.glyph_preview(shell, tool) == "view"
    shell.package = lambda: None
    app_module.glyph_preview(shell, tool)
    assert [kw["layer"] for _, _, kw in seen] == ["Regular", None]
    assert seen[0] == ("font", "widget", {"layer": "Regular", "controls": False, "label_prefix": "Layer Manager",
                                          "hint_check": "check"})  # fmt: skip


@pytest.mark.usefixtures("studio_qt")
def test_app_when_assembly_fails_then_shell_closed_and_error_raised(monkeypatch):
    import fontlabapp.fontui as fontui

    closed = []

    class Shell:
        def close(self):
            closed.append(True)

    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: Shell())
    studio = importlib.import_module(PKG)

    def broken(shell, tool):
        raise RuntimeError("no preview")

    with pytest.raises(RuntimeError, match="no preview"):
        studio.show(package=lambda: None, font=lambda: None, preview=broken)
    assert closed == [True]
    assert studio.tool_for(NS()).app == "Layer Manager"


# --- review fix round 1: total skipped rows, stale keys on native ids ---------


def test_empty_when_glyph_refused_then_row_without_layer_not_index_error(
    opened, monkeypatch
):
    import fontlabapp.core.history.glyphs as history

    _empty = importlib.import_module(f"{PKG}._empty")
    assert _empty.skipped_row("A: auto glyph") == (
        "A",
        None,
        ("", "skipped: auto glyph"),
    )
    assert _empty.skipped_row("A/x: shown layer") == (
        "A",
        None,
        ("x", "skipped: shown layer"),
    )
    assert _empty.skipped_row("odd") == ("odd", None, ("", "skipped"))
    pkg = extra_package()
    pkg.layer("A", "sketch").shapes = []
    pkg.add("Z", {"Regular": dict(shapes=outline(1)), "blank": dict(master=False)})
    real = history.refusal
    monkeypatch.setattr(
        history,
        "refusal",
        lambda facts, name, op: "auto glyph" if name == "Z" else real(facts, name, op),
    )
    app = opened(pkg, selection=["A", "Z"])
    panel = cleanup(app, "Empty layers")
    assert ("Z", None, ("", "skipped: auto glyph")) in rows(panel)
    panel.press()
    (call,) = app.history.calls
    assert call.label == "Layer Manager: delete empty layers A"


class Rewrapped:
    """A fresh Python wrapper on each read, as PythonQt may return: same ``.id``."""

    def __init__(self, item):
        object.__setattr__(self, "_item", item)

    def __getattr__(self, name):
        return getattr(self._item, name)

    def __setattr__(self, name, value):
        setattr(self._item, name, value)

    def __eq__(self, other):
        return self._item is getattr(other, "_item", other)

    def __hash__(self):
        return hash(id(self._item))


@pytest.fixture
def rewrap(monkeypatch):
    """Call to make every later findName/findLayer return a new wrapper."""

    def start():
        find_layer, find_name = Glyph.findLayer, Package.findName

        def wrapped(find):
            def read(self, name):
                found = find(self, name)
                return None if found is None else Rewrapped(found)

            return read

        monkeypatch.setattr(Glyph, "findLayer", wrapped(find_layer))
        monkeypatch.setattr(Package, "findName", wrapped(find_name))

    return start


def _rewrap_setup(app, tab):
    if tab == "Copy between masters":
        return app.panels[tab]
    if tab == "Twins":
        app.pkg.add(
            "D", {"Regular": dict(shapes=outline(2)), "Bold": dict(shapes=outline(1))}
        )
        app.selection[:] = ["D"]
        panel = app.panels[tab]
        panel.reselect()
        return panel
    if tab == "Back up":
        panel = backups(app, "Back up")
        panel.suffix.setText("v1")
        return panel
    if tab == "Restore":
        glyph = app.pkg.glyphs["A"]
        glyph.layers.append(Layer(glyph, "Regular backup v1", outline(3), master=False))
        panel = backups(app, "Restore")
        panel.reselect()
        return panel
    if tab == "Use as master":
        glyph = app.pkg.glyphs["A"]
        glyph.layers.append(Layer(glyph, "Regular@ old", outline(1), master=False))
        panel = backups(app, "Use as master")
        panel.reselect()
        return panel
    panel = app.panels["Intermediate"]
    panel.axis_controls["wt"].setValue(550)
    return panel


@pytest.mark.parametrize(
    "tab",
    [
        "Copy between masters",
        "Twins",
        "Back up",
        "Restore",
        "Use as master",
        "Intermediate",
    ],
)
def test_stale_key_when_native_objects_rewrapped_then_apply_still_writes(
    opened, rewrap, tab
):
    app = opened(selection=["A"])
    panel = _rewrap_setup(app, tab)
    shown = panel.shown
    assert shown and panel.apply_button.isEnabled(), tab
    rewrap()
    assert panel.key(panel.plan()) == shown
    panel.press()
    assert text(panel.status) != shared_stale(), tab
    assert len(app.history.calls) == 1, (tab, text(panel.status))


def shared_stale():
    return importlib.import_module(f"{PKG}._shared").STALE


def test_refusal_text_when_status_text_is_property_then_string_is_used(studio_qt):  # noqa: F811
    from types import SimpleNamespace as NS

    from fontlabapp.studios.layer_manager._shared import refusal_text

    prop = NS(shell=NS(status=NS(text="Refused: Glyph window")))  # PythonQt: str property
    call = NS(shell=NS(status=NS(text=lambda: "Refused: Glyph window")))  # PySide: method
    blank = NS(shell=NS(status=NS(text="")))
    assert refusal_text(prop) == refusal_text(call) == "Refused: Glyph window"
    assert refusal_text(blank) == "The write was refused."
