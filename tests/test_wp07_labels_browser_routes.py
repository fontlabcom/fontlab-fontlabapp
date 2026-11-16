# this_file: tests/test_wp07_labels_browser_routes.py
"""Retained label and browser actions keep their original callable contracts."""
import ast
from pathlib import Path

import pytest
from _studio_qt import studio_qt  # noqa: F401

ROOT = Path(__file__).parents[1] / "src/fontlabapp/glyphs/identity_tools"
ROUTES = {
    "glyph_labels": {
        "batch_glyph_notes": ("note_text", "plan_notes", "apply_notes", "_dialog_type", "main"),
        "glyph_notes": ("notes_in_font", "first_line", "save_note", "_dialog_type", "main"),
        "glyph_tags": ("_dialog_type", "main"),
        "mark_color_palette": ("_dialog_type", "main"),
        "select_by_mark": ("main",),
        "select_different_mark_colours": ("main",),
    },
    "glyph_browser": {
        "character_info": ("describe", "main"),
        "glyph_finder": ("matcher", "find", "main"),
        "glyph_metadata_tree": ("main",),
        "glyph_name_completion": ("main",),
    },
}


@pytest.mark.parametrize("studio,module,contracts", [
    (studio, module, contracts) for studio, routes in ROUTES.items()
    for module, contracts in routes.items()
])
def test_retained_route_has_original_callable_contract_and_app_imports(studio, module, contracts):
    path = ROOT / studio / (module + ".py")
    tree = ast.parse(path.read_text())
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert set(contracts) <= functions
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("fly")
        if isinstance(node, ast.Import):
            assert not any(alias.name.startswith("fly") for alias in node.names)


@pytest.mark.parametrize("studio,expected", [("glyph_labels", 6), ("glyph_browser", 4)])
def test_studio_assembles_all_retained_tabs_with_readonly_glyph_preview(monkeypatch, studio, expected):
    import importlib

    calls = []
    class Route:
        def __init__(self, title, build, **kwargs):
            self.title, self.build, self.options = title, build, kwargs
    from fontlabapp import fontui
    monkeypatch.setattr(fontui, "identity_route", Route)
    monkeypatch.setattr(fontui, "identity_studio", lambda *args, **kwargs: calls.append((args, kwargs)) or "shell")
    monkeypatch.setattr(fontui, "identity_panel", lambda *args, **kwargs: (args, kwargs))
    module = importlib.import_module(f"fontlabapp.studios.{studio}.app")
    assert module.show(parent="parent", font="font", package="package", tab="target") == "shell"
    (_title, routes), options = calls[0]
    assert len(routes) == expected
    assert options == {"preview": "tglyph", "parent": "parent", "font": "font", "package": "package", "tab": "target"}
    assert all(route.build("owner") for route in routes)
    assert len({route.title for route in routes}) == expected


def test_different_colours_preview_apply_and_stale_refusals(studio_qt, monkeypatch):  # noqa: F811
    import importlib
    import sys
    from types import SimpleNamespace as NS

    from fontlabapp.glyphs.selection.mark_colors import GlyphMark

    name = "fontlabapp.glyphs.identity_tools.glyph_labels.different_colours"
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)
    package = NS(id=7)
    before = (GlyphMark(0, "A", 10, True), GlyphMark(1, "B", 20, False))
    state = NS(package=package, rows=before, added=("B",))
    monkeypatch.setattr(module, "current_package", lambda expected=None: state.package if expected in (None, 7) else None)
    monkeypatch.setattr(module, "_capture", lambda fl: state.rows)
    monkeypatch.setattr(module, "_native", lambda name: NS(fl="FL"))
    monkeypatch.setattr(module, "select_different_mark_colours", lambda: state.added)
    panel = module.Panel()
    studio_qt.owned.append(panel)
    assert "Candidates: B" in panel.status.text()
    assert panel.apply() == ("B",)
    assert panel.status.text() == "Added: B"
    state.added = ()
    state.rows = ()
    with pytest.raises(ValueError, match="changed"):
        panel.apply()
    panel.refresh()
    assert "Candidates: None" in panel.status.text()
    assert panel.apply() == ()
    assert panel.status.text() == "Added: None"
    state.package = None
    with pytest.raises(ValueError, match="changed"):
        panel.apply()
    with pytest.raises(ValueError, match="Open a font"):
        panel.refresh()


@pytest.mark.parametrize("native_property", [False, True])
def test_label_controls_stage_tag_and_mark_actions_before_apply(monkeypatch, native_property):
    import importlib
    import sys
    from types import SimpleNamespace as NS

    class Signal:
        def __init__(self):
            self.slots = []
        def connect(self, slot):
            self.slots.append(slot)
        def disconnect(self, slot):
            self.slots.remove(slot)
        def emit(self):
            for slot in self.slots:
                slot()

    class Combo:
        def __init__(self, parent):
            self.index = 0
            self.currentIndex = 0 if native_property else lambda: self.index
        def addItems(self, items):
            self.items = items
        def setCurrentIndex(self, index):
            self.index = index
            if native_property:
                self.currentIndex = index

    made = []
    def build(parent):
        calls = []
        panel = NS(_connections=[], calls=calls, root=NS(insertWidget=lambda *args: None),
                   tag=NS(returnPressed=Signal()), status=NS(setText=calls.append),
                   add_button=NS(clicked=Signal()), remove_button=NS(clicked=Signal()),
                   swatches={0: NS(clicked=Signal()), 113: NS(clicked=Signal())},
                   add_tag=lambda: calls.append("add"), remove_ticked=lambda: calls.append("remove"),
                   apply=lambda value: calls.append(("apply", value)))
        def connect(signal, slot):
            signal.connect(slot)
            panel._connections.append((signal, slot))
        panel._connect = connect
        for signal in (panel.tag.returnPressed, panel.add_button.clicked, panel.remove_button.clicked,
                       *(button.clicked for button in panel.swatches.values())):
            connect(signal, lambda: calls.append("old write"))
        made.append(panel)
        return panel

    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtGui=NS(QComboBox=Combo)))
    prefix = "fontlabapp.glyphs.identity_tools.glyph_labels"
    for module in ("glyph_tags", "mark_color_palette"):
        monkeypatch.setitem(sys.modules, prefix + "." + module, NS(_dialog_type=lambda: build))
    controls = importlib.import_module(prefix + ".controls")
    tags = controls.tags(None)
    tags.tag.returnPressed.emit()
    tags.add_button.clicked.emit()
    tags.remove_button.clicked.emit()
    assert tags.calls == []
    tags.apply_staged()
    tags.operation.setCurrentIndex(1)
    tags.apply_staged()
    assert tags.calls == ["add", "remove"]
    marks = controls.marks(None)
    with pytest.raises(ValueError, match="Choose a mark"):
        marks.apply_staged()
    marks.swatches[113].clicked.emit()
    assert not any(isinstance(value, tuple) for value in marks.calls)
    marks.apply_staged()
    assert marks.calls[-1] == ("apply", 113)
    marks.swatches[0].clicked.emit()
    marks.apply_staged()
    assert marks.calls[-1] == ("apply", 0)


def test_browser_panels_reuse_complete_tree_and_completion(monkeypatch):
    import sys
    from types import SimpleNamespace as NS

    from fontlabapp.glyphs.identity_tools.glyph_browser import panels
    monkeypatch.setitem(sys.modules, "fontlabapp.glyphs.tree.model", NS(capture="tree capture"))
    monkeypatch.setitem(sys.modules, "fontlabapp.glyphs.tree.ui", NS(GlyphTreeDialog=lambda *args: args))
    monkeypatch.setitem(sys.modules, "fontlabapp.glyphs.catalog.native", NS(capture="catalog capture"))
    monkeypatch.setitem(sys.modules, "fontlabapp.glyphs.completion.ui", NS(GlyphCompletionDialog=lambda *args: args))
    assert panels.tree("parent") == ("parent", "Glyph Metadata Tree", "glyph_metadata_tree", "tree capture", False)
    assert panels.completion("parent") == ("parent", "catalog capture")


@pytest.mark.parametrize("studio,module,target,attribute", [
    ("glyph_browser", "glyph_metadata_tree", "fontlabapp.glyphs.tree.model", "show_tree"),
    ("glyph_browser", "glyph_name_completion", "fontlabapp.glyphs.completion.model", "show"),
    ("glyph_labels", "select_different_mark_colours", "fontlabapp.glyphs.selection.mark_colors", "select_different_mark_colours"),
])
def test_retained_small_routes_call_the_original_complete_action(monkeypatch, studio, module, target, attribute):
    import runpy
    import sys
    from types import SimpleNamespace as NS
    calls = []
    monkeypatch.setitem(sys.modules, target, NS(**{attribute: lambda: calls.append("called")}))
    path = ROOT / studio / (module + ".py")
    imported = runpy.run_path(str(path))
    imported["main"]()
    runpy.run_path(str(path), run_name="__main__")
    assert calls == ["called", "called"]


@pytest.mark.parametrize("studio", ["glyph_labels", "glyph_browser"])
def test_studio_lazy_export_opens_only_on_explicit_show(monkeypatch, studio):
    import importlib
    from types import SimpleNamespace as NS
    module = importlib.import_module("fontlabapp.studios." + studio)
    app = importlib.import_module("fontlabapp.studios." + studio + ".app")
    monkeypatch.setattr(app, "show", lambda **kwargs: NS(**kwargs))
    assert module.show(tab="test").tab == "test"


def test_character_panel_leaves_refresh_to_captured_shell(monkeypatch):
    import sys
    from types import SimpleNamespace as NS

    from fontlabapp.glyphs.identity_tools.glyph_browser import panels
    stopped = []
    panel = NS(timer=NS(stop=lambda: stopped.append(True)))
    monkeypatch.setitem(sys.modules, "fontlabapp.glyphs.identity_tools.glyph_browser.character_info", NS(CharacterInfo=lambda parent: panel))
    assert panels.character(None) is panel
    assert stopped == [True]
