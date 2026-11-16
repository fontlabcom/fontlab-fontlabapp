# this_file: tests/test_studio_mark_attachment.py
"""Mark Attachment (A14): parity with the 4 Scriptmix scripts, dry runs and the one labelled Undo step.

Each write test checks the single ``AppShell.history`` call (label, glyphs,
(glyph, master) layers, no base-edit consent) and the values FontLab
received. Mark preview and Get sample must not call it. Pure functions are
compared with the Scriptmix originals by AST.
"""

from _demo_support import stub_natives

import ast
import importlib
import inspect
import json
import math
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from _mark_attachment_originals import ORIGINALS
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.mark_attachment"
ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "Scripts" / "Anchors" / "Mark Attachment Demo.py"


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


# ---------------------------------------------------------------- fakes
class Point:
    def __init__(self, x, y):
        self._x, self._y = float(x), float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y


class Pin:
    def __init__(self, name, x, y):
        self.name, self.point, self.anchor, self.appearance = name, Point(x, y), True, 0


def qt():
    return importlib.import_module("PythonQt")


class Shape:
    """A component (``base`` at ``offset``) or a closed outline (``rect``)."""

    _ids = iter(range(1, 10_000))

    def __init__(
        self, log, *, base=None, offset=(0, 0), scale=1.0, rect=None, opened=False
    ):
        gui = qt().QtGui
        self.log, self.id = log, next(Shape._ids)
        self.isComponent = self.isComposite = base is not None
        self.shapeData = NS(componentGlyph=base, componentLayer="")
        self.transform = gui.QTransform(scale, 0, 0, 1, *offset)
        self.closedPath, self.openedPath = gui.QPainterPath(), gui.QPainterPath()
        if rect is not None:
            self.closedPath.addRect(*rect)
        if opened:
            self.openedPath.lineTo(10, 10)

    def changed(self):
        self.log.append(("shape changed", self.id))


class Layer:
    def __init__(self, log, glyph, master, anchors=None, shapes=(), *, auto=False):
        self.log, self.glyph, self.master, self.name = log, glyph, master, master
        self.advanceWidth, self.autoLayer, self.isNull = 500, auto, False
        self.isMaskLayer = self.isService = False
        self.anchors = [Pin(n, x, y) for n, (x, y) in (anchors or {}).items()]
        self.shapes = list(shapes)

    def addAnchor(self, pin):  # noqa: N802 - native API
        self.log.append(
            ("add", self.glyph, self.master, pin.name, pin.point.x(), pin.point.y())
        )
        self.anchors.append(pin)

    def changed(self):
        self.log.append(("layer changed", self.glyph, self.master))

    def update(self):
        return True


class Glyph:
    def __init__(self, name, layers):
        self.name, self.isNull = name, False
        self._layers = {layer.master: layer for layer in layers}

    def findLayer(self, master):  # noqa: N802 - native API
        return self._layers.get(master)


class Package:
    def __init__(self):
        self.log, self.masters, self.master, self.glyphs, self.id = (
            [],
            ["Regular", "Bold"],
            "Regular",
            {},
            7,
        )

    def add(self, name, per_master, **kwargs):
        """``per_master``: master -> (anchors, shapes-builder or None)."""
        layers = []
        for master, (anchors, shapes) in per_master.items():
            built = shapes(self.log) if shapes else ()
            layers.append(Layer(self.log, name, master, anchors, built, **kwargs))
        self.glyphs[name] = Glyph(name, layers)
        return self.glyphs[name]

    def findName(self, name):  # noqa: N802 - native API
        return self.glyphs.get(name)

    def layer(self, name, master):
        return self.glyphs[name].findLayer(master)


def comps(*parts):
    return lambda log: [
        Shape(log, base=b, offset=o, **k)
        for b, o, *rest in parts
        for k in (rest[0] if rest else {},)
    ]


def package():
    pkg = Package()
    pkg.add(
        "a",
        {"Regular": ({"top": (250, 500)}, None), "Bold": ({"top": (260, 520)}, None)},
    )
    pkg.add(
        "o",
        {
            "Regular": ({"top": (240, 500), "bottom": (240, 0)}, None),
            "Bold": ({"top": (250, 510)}, None),
        },
    )
    pkg.add(
        "acutecomb",
        {"Regular": ({"_top": (100, 0)}, None), "Bold": ({"_top": (100, 0)}, None)},
    )
    pkg.add("aacute", {"Regular": ({}, comps(("a", (0, 0)), ("acutecomb", (0, 0)))),
                       "Bold": ({}, comps(("a", (0, 0)), ("acutecomb", (160, 520))))})  # fmt: skip
    pkg.add("ocomb", {"Regular": ({}, comps(("o", (0, 0)), ("acutecomb", (0, 0), {"scale": 1.2}))),
                      "Bold": ({}, None)})  # fmt: skip
    rect = (0, 0, 300, 100)
    pkg.add("beh.init", {"Regular": ({}, lambda log: [Shape(log, rect=rect)]),
                         "Bold": ({}, lambda log: [Shape(log, rect=rect)])})  # fmt: skip
    pkg.add(
        "beh.medi",
        {
            "Regular": ({"entry": (299, 50)}, lambda log: [Shape(log, rect=rect)]),
            "Bold": ({}, None),
        },
    )
    pkg.add("sample", {"Regular": ({"entry": (250, 40), "exit": (50, 60)}, lambda log: [Shape(log, rect=rect)]),
                       "Bold": ({}, None)})  # fmt: skip
    return pkg


class Recorder:
    """``AppShell.history`` stand-in: records one call, runs mutate and read-back."""

    def __init__(self, shell, refuse=None):
        self.shell, self.calls, self.refuse = shell, [], refuse

    def __call__(
        self, label, glyphs, mutate, *, layers, read_back=None, allow_bases=False
    ):
        self.calls.append(
            (
                label,
                [g.name for g in glyphs],
                [(la.glyph, la.master) for la in layers],
                allow_bases,
            )
        )
        if self.refuse:
            self.shell.set_status(self.refuse)
            return None
        mutate()
        return NS(mismatches=read_back() if read_back else [], pending_note="")


def native(name):
    if name == "PythonQt":
        return NS(QtCore=NS(QPointF=Point))

    def pin_point(point):
        pin = Pin("", 0, 0)
        pin.point = point
        return pin

    return NS(flPinPoint=pin_point)


@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.anchors.inspect.model as inspect_model
    import fontlabapp.anchors.writer as writer
    import fontlabapp.core.history.glyphs as history
    from fontlabapp.core.scripting import mark_attachment_backends

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            return lambda *args: self.calls.append((name, *args))

    class View(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.panels = []

        def set_panels(self, panels):
            self.panels = panels

    monkeypatch.setattr(writer, "_native", native)
    facts = NS(value=history.auto_facts([]))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts.value)

    def open_app(pkg=None, selection=("aacute", "ocomb")):
        pkg = package() if pkg is None else pkg
        real = mark_attachment_backends()
        fake_inspect = NS(**{n: getattr(inspect_model, n) for n in
                             ("classify", "families", "attachment", "attachment_layer_of", "anchor_points")},
                          font_glyph_names=lambda: list(pkg.glyphs),
                          glyph_path=lambda layer: qt().QtGui.QPainterPath())  # fmt: skip
        found = NS(**{**vars(real), "inspect": fake_inspect})
        studio = importlib.import_module(PKG)
        shared = importlib.import_module(f"{PKG}._shared")
        monkeypatch.setattr(shared, "backends", lambda: found)
        preview_mod = importlib.import_module(f"{PKG}.preview")
        monkeypatch.setattr(
            preview_mod, "anchors_view_types", lambda: NS(AttachmentView=View)
        )
        cursive = importlib.import_module(f"{PKG}.cursive")
        monkeypatch.setattr(cursive, "current_package", lambda: pkg)
        chosen = list(selection)
        tool_type = importlib.import_module("fontlabapp.studios._kerning_app").Tool
        monkeypatch.setattr(
            sys.modules[tool_type.__module__],
            "names_selected_names",
            lambda: list(chosen),
        )
        preview = QtPreview()
        shell = studio.show(
            package=lambda: pkg,
            font=lambda: "font",
            preview=lambda shell, tool: preview,
        )
        studio_qt.owned.append(shell)
        tool = shell.kerning_tool
        recorder = Recorder(shell)
        shell.history = recorder
        panels = {
            title: view.__self__
            for title, view in zip(studio.TAB_TITLES, tool.views, strict=True)
        }
        return NS(shell=shell, tool=tool, pkg=pkg, preview=preview, panels=panels, studio=studio, history=recorder,
                  selection=chosen, facts=facts, backends=found, cursive=cursive)  # fmt: skip

    return open_app


def rows(panel):
    return [(r.glyph_name, r.layer, tuple(r.values)) for r in panel.grid.rows]


def offsets(pkg, name, master):
    return [
        (s.shapeData.componentGlyph, s.transform.dx(), s.transform.dy())
        for s in pkg.layer(name, master).shapes
    ]


# ---------------------------------------------------------------- shell, registry, parity
def test_show_when_opened_then_three_tabs_tmetrics_preview_and_masters(opened):
    app = opened()
    assert app.studio.TAB_TITLES == ("Mark preview", "Align by anchor", "Cursive")
    assert list(app.panels) == list(app.studio.TAB_TITLES)
    assert app.tool.app == "Mark Attachment"
    assert app.tool.masters == ["Regular", "Bold"]
    assert ("set_layer", "Regular") in app.preview.calls


def test_registry_when_imported_then_lazy_and_idempotent():
    import fontlabapp.studios as studios

    studio = importlib.import_module(PKG)
    assert studio.register_tabs() == studio.register_tabs() == studio.TAB_TITLES
    assert tuple(spec.title for spec in studios.tabs(studio.APP)) == studio.TAB_TITLES
    for module in ("preview", "align", "cursive", "_shared"):
        assert f"{PKG}.{module}" not in sys.modules, module


def test_backends_when_loaded_then_reused_app_modules():
    from fontlabapp.core.scripting import mark_attachment_backends

    found = mark_attachment_backends()
    assert found.inspect.__name__ == "fontlabapp.anchors.inspect.model"
    assert found.components.__name__ == "fontlabapp.components.writer"
    assert found.anchors.__name__ == "fontlabapp.anchors.writer"
    assert found.selection.__name__ == "fontlabapp.masters.layers.selection"
    assert found.masters.__name__ == "fontlabapp.masters.inspect.model"
    assert found.history.__name__ == "fontlabapp.core.history.glyphs"


def _functions(source, names):
    tree = ast.parse(source)
    found = {
        n.name: ast.dump(n)
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    }
    return [found[name] for name in names]


PORTS = {
    "Align By Anchor": "align",
    "Auto Cursive Attachment Get Sample": "cursive",
    "Auto Cursive Attachment Add Anchors": "cursive",
}
# The originals import ``fly.ap.anchors.writer`` inside two functions; the port reads the module name instead.
LOCAL_IMPORT = "    import fly.ap.anchors.writer as anchor_writer  # noqa: PLR0402 - Fly submodule import avoids native attribute lookup\n"  # noqa: E501


@pytest.mark.parametrize("title", sorted(PORTS))
def test_pure_functions_when_compared_then_ast_equal_to_scriptmix(title, studio_qt):  # noqa: F811
    path, digest, names, source = ORIGINALS[title]
    assert path.startswith("Scripts/") and len(digest) == 64
    module = importlib.import_module(f"{PKG}.{PORTS[title]}")
    port = Path(str(module.__file__)).read_text(encoding="utf-8")
    assert _functions(port, names) == _functions(
        source.replace(LOCAL_IMPORT, ""), names
    )


def test_originals_when_listed_then_all_four_scripts_pinned():
    assert sorted(ORIGINALS) == sorted([*PORTS, "Mark Attachment Preview"])
    assert ORIGINALS["Mark Attachment Preview"][2] == ()
    get, add = (
        ORIGINALS["Auto Cursive Attachment Get Sample"],
        ORIGINALS["Auto Cursive Attachment Add Anchors"],
    )
    shared = ("outline_rings", "vertical_spans", "measure_sample", "validate_profile")
    assert _functions(get[3], shared) == _functions(add[3], shared), (
        "both originals carry the same helpers"
    )


def test_shared_helpers_when_called_then_label_subject_and_module_proxy(studio_qt):  # noqa: F811
    shared = importlib.import_module(f"{PKG}._shared")
    assert (
        shared.label("align components", ["aacute"])
        == "Mark Attachment: align components aacute"
    )
    assert (
        shared.label("add cursive anchors", ["a", "b", "a"])
        == "Mark Attachment: add cursive anchors 2 glyphs"
    )
    assert (shared.plural(1, "layer"), shared.plural(2, "layer")) == (
        "1 layer",
        "2 layers",
    )
    with pytest.raises(AttributeError):
        shared.Modules("components").__wrapped__  # noqa: B018
    assert shared.Modules("components").half_up(1.5) == 2


# ---------------------------------------------------------------- Mark preview (read only)
def test_preview_when_opened_then_bases_marks_and_one_panel_per_master(opened):
    app = opened(selection=("o", "aacute"))
    panel = app.panels["Mark preview"]
    assert panel.bases == ["a", "o", "beh.medi", "sample"] and panel.marks == [
        "acutecomb"
    ]
    assert panel.base.currentText() == "o", "the first selected base is chosen"
    assert panel.family.currentText() == "top"
    assert [p[0] for p in panel.view.panels] == ["Regular", "Bold"]
    assert [p[5] for p in panel.view.panels] == ["offset 140, 500", "offset 150, 510"]
    assert panel.offsets == {"Regular": (140, 500), "Bold": (150, 510)}
    assert panel.status.text() == "Mark offset = base anchor − mark anchor"
    assert panel.subtitle.text() == (
        "acutecomb attached to o with top / _top on 2 masters. 4 base and 1 mark glyphs found."
    )
    assert ("set_text", "/o/acutecomb") in app.preview.calls
    assert app.history.calls == [] and not [
        e for e in app.pkg.log if e[0] in ("add", "shape changed")
    ]


def test_preview_when_anchor_missing_on_a_master_then_named(opened):
    app = opened(selection=("a",))
    app.pkg.layer("acutecomb", "Bold").anchors = []
    app.tool.reload()
    panel = app.panels["Mark preview"]
    assert [p[5] for p in panel.view.panels] == [
        "offset 150, 500",
        "no matching anchors",
    ]
    assert panel.status.text() == "Missing anchors on Bold"


def test_preview_when_pair_changed_then_shared_anchor_list_follows(opened):
    app = opened(selection=("a",))
    panel = app.panels["Mark preview"]
    panel.base.setCurrentIndex(panel.bases.index("o"))
    assert [panel.family.itemText(i) for i in range(panel.family.count())] == ["top"]
    assert panel.base.currentText() == "o"
    app.tool.reload()
    assert panel.base.currentText() == "o", "Refresh keeps the chosen pair"


def test_preview_when_no_font_then_original_text(opened):
    app = opened()
    app.shell.package = lambda: None
    app.tool.reload()
    panel = app.panels["Mark preview"]
    assert panel.subtitle.text() == "Open a font first."
    assert panel.view.panels == []


# ---------------------------------------------------------------- Align by anchor
def test_align_when_opened_then_original_rows_and_current_master_default(opened):
    app = opened()
    panel = app.panels["Align by anchor"]
    assert panel.scope.currentIndex() == 0
    assert panel.family.itemText(0) == "Automatic (first matching pair)"
    assert rows(panel) == [
        ("aacute", "Regular", ("acutecomb @ top", "0, 0", "150, 500")),
        ("ocomb", "Regular", ("acutecomb", "0, 0", "scaled or slanted, kept")),
    ]
    assert panel.apply_button.isEnabled()
    assert panel.count.text() == "1 component change on 1 layer"


def test_align_when_applied_all_masters_then_one_labelled_step_and_offsets(opened):
    app = opened()
    panel = app.panels["Align by anchor"]
    panel.scope.setCurrentIndex(1)
    assert ("aacute", "Bold", ("acutecomb @ top", "160, 520", "in place")) in rows(
        panel
    )
    assert panel.apply()
    assert app.history.calls == [("Mark Attachment: align components aacute", ["aacute"], [("aacute", "Regular")],
                                  False)]  # fmt: skip
    assert offsets(app.pkg, "aacute", "Regular") == [
        ("a", 0, 0),
        ("acutecomb", 150, 500),
    ]
    assert ("layer changed", "aacute", "Regular") in app.pkg.log
    assert (
        app.tool.status
        == "Mark Attachment: align components aacute. Moved 1 component on 1 layer"
    )
    assert panel.count.text() == "All marks already sit on their anchors"
    assert not panel.apply_button.isEnabled()


def test_align_when_named_pair_missing_then_no_matching_anchors(opened):
    app = opened(selection=("aacute",))
    panel = app.panels["Align by anchor"]
    app.pkg.layer("o", "Regular")  # unused base keeps "bottom" out of the choices
    items = [panel.family.itemText(i) for i in range(panel.family.count())]
    assert items == ["Automatic (first matching pair)", "top"]
    panel.family.setCurrentIndex(1)
    assert panel.choice == "top"
    assert rows(panel)[0][2][2] == "150, 500"


def test_align_when_glyph_changed_after_dry_run_then_stale_and_nothing_written(opened):
    app = opened()
    panel = app.panels["Align by anchor"]
    app.pkg.layer("a", "Regular").anchors[0].point = Point(260, 500)
    assert not panel.apply()
    assert app.history.calls == []
    assert (
        app.tool.status
        == "Mark Attachment: The glyphs changed since the dry run; press Refresh."
    )


def _base_of_auto(app):
    import fontlabapp.core.history.glyphs as history

    app.facts.value = history.auto_facts([("aacuteauto", True, ("aacute",)), ("aacute", False, ("a", "acutecomb")),
                                          ("behauto", True, ("beh.init",)), ("beh.init", False, ())])  # fmt: skip
    return history


def _assert_refused_outright(app, panel, name):
    """The originals' refusal: blocked row first, ``require_safe`` text, Apply off, no tick, no history."""
    history = app.backends.history
    why = history.refusals(app.facts.value, [name], "geometry")[name]
    assert rows(panel)[0] == (name, None, ("blocked", "", why))
    text = f"FontLab cannot undo edits to these glyphs: {name}: {why}. Choose other glyphs."
    assert panel.dry.problem == text
    assert panel.count.text() == f"Refused. {text}"
    assert not panel.apply_button.isEnabled()
    assert not hasattr(panel, "allow"), "no 'Edit bases of auto glyphs anyway' tick"
    assert not panel.apply()
    assert app.history.calls == []
    assert app.tool.status == f"Mark Attachment: {text}"


def test_align_when_base_of_auto_glyph_then_refused_outright_as_original(opened):
    app = opened(selection=("aacute",))
    _base_of_auto(app)
    app.tool.reload()
    _assert_refused_outright(app, app.panels["Align by anchor"], "aacute")


def test_cursive_when_base_of_auto_glyph_then_refused_outright_as_original(
    opened, tmp_path
):
    app = opened(selection=("beh.init",))
    _base_of_auto(app)
    panel = app.panels["Cursive"]
    panel.sample_path.setText(write_sample(tmp_path))
    _assert_refused_outright(app, panel, "beh.init")


def test_shared_when_imported_then_no_base_opt_in(studio_qt):  # noqa: F811
    shared = importlib.import_module(f"{PKG}._shared")
    assert not hasattr(shared, "ALLOW_AUTO_LABEL")
    assert "allow_bases" not in inspect.signature(shared.apply).parameters
    source = Path(str(shared.__file__)).read_text(encoding="utf-8")
    assert "Edit bases of auto glyphs anyway" not in source


def test_align_when_refused_by_history_then_status_kept(opened):
    app = opened(selection=("aacute",))
    app.shell.history = Recorder(app.shell, refuse="Glyph window: close it first.")
    assert not app.panels["Align by anchor"].apply()
    assert app.tool.status == "Glyph window: close it first."


def test_align_when_no_selection_or_font_then_says_so(opened):
    app = opened(selection=())
    panel = app.panels["Align by anchor"]
    assert (
        panel.subtitle.text() == "Select glyphs in the Font window, then press Refresh."
    )
    assert not panel.apply_button.isEnabled()
    with pytest.raises(ValueError, match="Nothing to change"):
        importlib.import_module(f"{PKG}._shared").apply(
            app.tool, "x", panel.dry, panel.plan, None
        )
    app.shell.package = lambda: None
    app.tool.reload()
    assert panel.subtitle.text() == "Open a font first."


def test_align_when_row_chosen_then_preview_shows_glyph_on_master(opened):
    app = opened()
    app.panels["Align by anchor"].row_chosen("aacute", "Bold")
    assert app.preview.calls[-2:] == [("set_text", "/aacute"), ("set_layer", "Bold")]


def test_align_when_auto_layer_then_skipped_and_listed(opened):
    pkg = package()
    pkg.add(
        "aauto",
        {
            "Regular": ({}, comps(("a", (0, 0)), ("acutecomb", (0, 0)))),
            "Bold": ({}, None),
        },
        auto=True,
    )
    app = opened(pkg=pkg, selection=("aauto", "aacute"))
    panel = app.panels["Align by anchor"]
    assert ("aauto", "Regular", ("1 row", "", "auto layer, skipped")) in rows(panel)
    assert panel.dry.skipped == ["aauto/Regular"]
    assert "1 auto layer skipped" in panel.count.text()
    assert panel.apply()
    assert app.tool.status.endswith("on 1 layer · 1 auto layer skipped")


# ---------------------------------------------------------------- Cursive
PROFILE = {"below": 50.0, "above": 50.0, "lower_angle": 0.0, "upper_angle": 0.0}


def write_sample(tmp_path, master="Regular", profile=PROFILE, raw=None):
    path = tmp_path / "sample.json"
    text = raw if raw is not None else json.dumps({"format": "fontlab-cursive-sample-1", "master": master,
                                                   "profile": profile})  # fmt: skip
    path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    return str(path)


def test_cursive_when_no_sample_then_apply_off_and_reason(opened):
    app = opened(selection=("beh.init",))
    panel = app.panels["Cursive"]
    assert not panel.apply_button.isEnabled()
    assert (
        panel.count.text() == "Choose a sample file."
    )  # the original read_sample text


def test_cursive_when_sample_chosen_then_missing_exit_and_entry_planned(
    opened, tmp_path
):
    app = opened(selection=("beh.init", "beh.medi"))
    panel = app.panels["Cursive"]
    panel.sample_path.setText(write_sample(tmp_path))
    assert panel.sample_info.text() == "No text conversion needed."
    assert rows(panel) == [
        ("beh.init", "Regular", ("exit", "missing", "(1, 50)")),
        ("beh.medi", "Regular", ("exit", "missing", "(1, 50)")),
    ]
    assert panel.count.text() == "2 anchors to add on 2 layers"
    assert panel.apply()
    assert app.history.calls == [("Mark Attachment: add cursive anchors 2 glyphs", ["beh.init", "beh.medi"],
                                  [("beh.init", "Regular"), ("beh.medi", "Regular")], False)]  # fmt: skip
    assert [e for e in app.pkg.log if e[0] == "add"] == [
        ("add", "beh.init", "Regular", "exit", 1.0, 50.0),
        ("add", "beh.medi", "Regular", "exit", 1.0, 50.0),
    ]
    assert (
        app.tool.status
        == "Mark Attachment: add cursive anchors 2 glyphs. Added 2 anchors on 2 layers"
    )
    assert panel.count.text() == "Nothing to change"


def test_cursive_when_sample_converted_or_wrong_master_then_original_texts(
    opened, tmp_path
):
    app = opened(selection=("beh.init",))
    panel = app.panels["Cursive"]
    text = json.dumps(
        {"format": "fontlab-cursive-sample-1", "master": "Regular", "profile": PROFILE}
    )
    panel.sample_path.setText(
        write_sample(tmp_path, raw=b"\xef\xbb\xbf" + text.encode() + b"\r\n")
    )
    assert panel.sample_info.text() == "BOM removed; CR/CRLF read as LF."
    assert panel.apply_button.isEnabled()
    other = tmp_path / "bold"
    other.mkdir()
    panel.sample_path.setText(write_sample(other, master="Bold"))
    assert panel.count.text() == "The sample master name must match the current master."
    assert not panel.apply_button.isEnabled()


def test_cursive_when_layer_cannot_be_fitted_then_note_row_and_apply_refused(
    opened, tmp_path
):
    pkg = package()
    pkg.add("beh.fina", {"Regular": ({}, comps(("a", (0, 0)))), "Bold": ({}, None)})
    app = opened(pkg=pkg, selection=("beh.fina",))
    panel = app.panels["Cursive"]
    panel.sample_path.setText(write_sample(tmp_path))
    assert rows(panel) == [("beh.fina", "Regular", ("cursive", "", "Use closed, decomposed outlines for cursive "
                                                    "sampling.; layer skipped"))]  # fmt: skip
    assert not panel.apply_button.isEnabled()


def test_cursive_when_get_sample_then_new_file_only_and_no_history(
    opened, tmp_path, monkeypatch
):
    app = opened(selection=("sample",))
    panel = app.panels["Cursive"]
    layer = app.pkg.layer("sample", "Regular")
    app.backends.selection = NS(
        capture=lambda deadline: NS(occurrences=[NS(layer=layer)])
    )
    target = tmp_path / "new.json"
    monkeypatch.setattr(panel, "save_path", lambda: str(target))
    document = panel.get_sample()
    assert (
        document["format"] == "fontlab-cursive-sample-1"
        and document["master"] == "Regular"
    )
    assert document["profile"]["below"] == pytest.approx(50.0) and document["profile"][
        "above"
    ] == pytest.approx(50.0)
    assert json.loads(target.read_text()) == document
    assert panel.sample_path.text() == str(target)
    assert app.tool.status == f"Saved cursive sample: {target}"
    assert app.history.calls == [] and not [e for e in app.pkg.log if e[0] == "add"]
    panel.run(panel.get_sample)
    assert (
        app.tool.status
        == "Mark Attachment: Choose a new file name; existing sample files stay unchanged."
    )
    monkeypatch.setattr(panel, "save_path", lambda: "")
    assert panel.get_sample() is None


def test_cursive_when_get_sample_refused_then_original_texts(opened, tmp_path):
    app = opened(selection=("sample",))
    panel = app.panels["Cursive"]
    layer = app.pkg.layer("sample", "Regular")
    app.backends.selection = NS(capture=lambda deadline: NS(occurrences=[]))
    panel.run(panel.get_sample)
    assert (
        app.tool.status
        == "Mark Attachment: Select exactly one glyph layer in an open font."
    )
    layer.isMaskLayer = True
    app.backends.selection = NS(
        capture=lambda deadline: NS(occurrences=[NS(layer=layer)])
    )
    panel.run(panel.get_sample)
    assert app.tool.status == "Mark Attachment: Choose a body layer for the sample."
    layer.isMaskLayer, layer.name = False, "sketch"
    panel.run(panel.get_sample)
    assert (
        app.tool.status == "Mark Attachment: The layer has no associated font master."
    )


def test_cursive_when_choose_profile_then_path_set(opened, tmp_path, monkeypatch):
    app = opened(selection=("beh.init",))
    panel = app.panels["Cursive"]
    path = write_sample(tmp_path)
    monkeypatch.setattr(panel, "open_path", lambda: path)
    panel.choose_profile()
    assert panel.sample_path.text() == path
    assert panel.apply_button.isEnabled()


def test_cursive_when_dialogs_built_then_original_options(opened, monkeypatch):
    app = opened(selection=("beh.init",))
    panel = app.panels["Cursive"]
    gui = qt().QtGui
    made = []

    class Dialog(gui.QFileDialog):
        def exec_(self):
            made.append(self)
            return 0

    monkeypatch.setattr(gui, "QFileDialog", Dialog)
    assert panel.save_path() == "" and panel.open_path() == ""
    save, opening = made
    assert (
        save.acceptMode() == gui.QFileDialog.AcceptSave
        and save.defaultSuffix() == "json"
    )
    assert save.testOption(gui.QFileDialog.DontConfirmOverwrite)
    assert opening.fileMode() == gui.QFileDialog.ExistingFile
    assert save.nameFilters() == ["Cursive sample (*.json)"]


def test_cursive_pure_functions_when_called_then_original_rules(studio_qt):  # noqa: F811
    cursive = importlib.import_module(f"{PKG}.cursive")
    assert cursive.needed_connections("beh.init") == ["exit"]
    assert cursive.needed_connections("beh.medi") == ["exit", "entry"]
    assert cursive.needed_connections("beh.fina") == ["entry"]
    rings = [[(0.0, 0.0), (300.0, 0.0), (300.0, 100.0), (0.0, 100.0), (0.0, 0.0)]]
    assert cursive.choose_attachment(rings, PROFILE, [0.5, 1.5]) == (0.5, 50.0)
    with pytest.raises(ValueError, match="positive ink"):
        cursive.validate_profile(
            {"below": 0.0, "above": 0.0, "lower_angle": 0.0, "upper_angle": 0.0}
        )
    assert math.isclose(cursive.measure_sample(rings, [(10.0, 30.0)])["below"], 30.0)


# ---------------------------------------------------------------- demo
def test_demo_when_run_then_opens_studio_or_says_why(monkeypatch, studio_qt):  # noqa: F811
    studio = importlib.import_module(PKG)
    calls = []
    monkeypatch.setattr(studio, "show", lambda: calls.append("show"))
    runpy.run_path(str(DEMO), run_name="__main__")
    assert calls == ["show"]
    runpy.run_path(str(DEMO), run_name="not_main")
    assert calls == ["show"]

    import fontlabapp
    import fontlabapp.qt.dialogs as dialogs

    def refuse():
        raise ValueError("no font")

    shown = []
    monkeypatch.setattr(studio, "show", refuse)
    monkeypatch.setattr(
        dialogs, "run_standard_message_box", lambda *args: shown.append(args[3])
    )
    stub_natives(monkeypatch, fontlabapp, lambda name: NS(QtGui=NS(QMessageBox=NS(Ok=1)), MainWindow=lambda: None))  # fmt: skip
    runpy.run_path(str(DEMO), run_name="__main__")
    assert shown == ["Mark Attachment did not open: no font"]
