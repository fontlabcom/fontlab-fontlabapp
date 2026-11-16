# this_file: tests/test_studio_component_audit.py
"""Component Audit (A16): parity with the 6 Scriptmix scripts, read-only tabs and the one Unnest step.

Composites, Where used, Missing bases, Graph and Brackets run with a history
that fails the test when opened and must not change any shape. Nested
checks its single ``AppShell.history`` call (label, glyphs, (glyph, master)
layers, retained objects) and the shapes FontLab received. The pure
function of Nested Finder is compared with the Scriptmix original by AST.
"""

from _demo_support import stub_natives

import ast
import hashlib
import importlib
import inspect
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import test_studio_component_studio as t14
from _component_audit_originals import ORIGINALS
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.component_audit"
ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "Scripts" / "Components" / "Component Audit Demo.py"
SCRIPTMIX_ENV = os.environ.get("FONTLAB_SCRIPTMIX", "")
TAB_MODULES = {
    "Components Report": "composites",
    "Where Used": "where_used",
    "Missing Bases": "missing_bases",
    "Nested Finder": "nested",
    "Component Graph": "graph",
    "Bracket Layers and Components": "brackets",
}


@pytest.fixture(autouse=True)
def fresh_studios():
    t14._forget_studio_children()
    yield
    t14._forget_studio_children()


def qt():
    return importlib.import_module("PythonQt")


def package():
    """The Component Studio font plus a missing base, an auto layer and a bracket layer."""
    pkg = t14.package()
    pkg.add("Ccedilla", {"Regular": t14.comps(("C", (0, 0)), ("cedilla", (100, 0))),
                         "Bold": t14.comps(("acute", (0, 0)))})  # fmt: skip
    pkg.add("Eacute", {"Regular": t14.comps(("A", (0, 0)), ("acute", (0, 0))),
                       "Bold": t14.comps(("A", (10, 0)))}, auto=True)  # fmt: skip
    pkg.add("cedilla", {"Regular": t14.outline(1)})
    return pkg


def shapes(pkg):
    return {
        (name, layer.name): [
            (
                s.isComponent,
                s.shapeData.componentGlyph,
                s.transform.dx(),
                s.transform.dy(),
            )
            for s in layer.shapes
        ]  # fmt: skip
        for name, glyph in pkg.glyphs.items()
        for layer in glyph.layers
    }


class Graph:
    def __init__(self):
        self.opened = 0

    def show(self):
        self.opened += 1
        return "graph window"


@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QWidget

    import fontlabapp.components.inspect.model as inspect_model
    import fontlabapp.components.writer as writer
    import fontlabapp.core.edit_guards as edit_guards
    import fontlabapp.core.history.glyphs as history
    import fontlabapp.core.scripting as scripting
    import fontlabapp.masters.layers.brackets.model as brackets
    from fontlabapp.core.scripting import (
        component_audit_backends,
        component_studio_backends,
    )

    class QtPreview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def load(self, *args):
            self.calls.append(("load", *args))

    monkeypatch.setattr(
        t14.Shape, "getContours", lambda self: self.contours, raising=False
    )
    monkeypatch.setattr(writer, "_native", t14.native)
    monkeypatch.setattr(edit_guards, "pending_updates", lambda native=None: ())
    facts = NS(value=history.auto_facts([]))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts.value)

    def open_app(
        pkg=None,
        selection=("Aring", "Aacute"),
        history_type=t14.Recorder,
        current="Aring",
    ):
        pkg = package() if pkg is None else pkg
        selected, graph, updates, reports = [], Graph(), [], NS(fail="")

        def bracket_report():
            if reports.fail:
                raise TimeoutError(reports.fail)
            glyphs = tuple(
                brackets.Glyph(
                    name,
                    tuple(layer.name for layer in glyph.layers),
                    frozenset(
                        s.shapeData.componentGlyph
                        for layer in glyph.layers
                        for s in layer.shapes
                        if s.isComponent
                    ),
                )  # fmt: skip
                for name, glyph in pkg.glyphs.items()
            )
            return brackets.analyse(glyphs)

        found = NS(**{**vars(component_audit_backends()), "graph": graph, "bracket_report": bracket_report,
                      "update_all": lambda: updates.append("UpdateAll")})  # fmt: skip
        studio = importlib.import_module(PKG)
        shared = importlib.import_module(f"{PKG}._shared")
        monkeypatch.setattr(shared, "backends", lambda: found)
        cs_shared = importlib.import_module(
            "fontlabapp.studios.component_studio._shared"
        )
        ink = NS(ink=lambda: qt().QtGui.QBrush())
        monkeypatch.setattr(
            cs_shared,
            "backends",
            lambda: NS(**{**vars(component_studio_backends()), "panel": ink}),
        )
        chosen = list(selection)
        kerning = sys.modules["fontlabapp.studios._kerning"]
        monkeypatch.setattr(kerning, "names_selected_names", lambda: list(chosen))
        monkeypatch.setattr(
            kerning,
            "select_glyphs",
            lambda names, package_id=None: selected.append((list(names), package_id)),
        )
        order = NS(names=list(pkg.glyphs))
        monkeypatch.setattr(
            scripting, "names_font_glyphs", lambda: [(n, None) for n in order.names]
        )
        monkeypatch.setattr(
            inspect_model, "font_glyph_names", lambda: list(order.names)
        )
        monkeypatch.setattr(inspect_model, "current_name", lambda: current)
        activated = []
        setattr(pkg, "activateGlyph", lambda glyph: activated.append(glyph.name))
        active = NS(package=pkg)
        preview = QtPreview()
        shell = studio.show(
            package=lambda: active.package,
            font=lambda: "font",
            preview=lambda shell, tool: preview,
        )
        studio_qt.owned.append(shell)
        tool = shell.component_audit_tool
        recorder = history_type(shell)
        shell.history = recorder
        panels = {
            title: view.__self__ for title, view in zip(studio.TAB_TITLES, tool.views)
        }
        return NS(shell=shell, tool=tool, pkg=pkg, preview=preview, panels=panels, studio=studio,
                  history=recorder, selection=chosen, selected=selected, graph=graph, updates=updates,
                  activated=activated, order=order, active=active, reports=reports, facts=facts)  # fmt: skip

    return open_app


def rows(panel):
    return [(r.glyph_name, r.layer, tuple(r.values)) for r in panel.grid.rows]


def text(widget):
    value = widget.text
    return value() if callable(value) else value


# ---------------------------------------------------------------- shell, registry, parity
def test_show_when_opened_then_six_tabs_tglyph_preview_and_masters(opened):
    app = opened(history_type=lambda shell: t14.Forbidden())
    assert app.studio.TAB_TITLES == (
        "Composites",
        "Where used",
        "Missing bases",
        "Nested",
        "Graph",
        "Brackets",
    )
    assert list(app.panels) == list(app.studio.TAB_TITLES)
    assert app.tool.app == "Component Audit"
    assert app.tool.masters == ["Regular", "Bold"]
    assert app.tool.preview is app.preview


def test_registry_when_imported_then_lazy_and_idempotent():
    import fontlabapp.studios as studios

    studio = importlib.import_module(PKG)
    assert studio.register_tabs() == studio.register_tabs() == studio.TAB_TITLES
    assert tuple(spec.title for spec in studios.tabs(studio.APP)) == studio.TAB_TITLES
    for module in set(studio.PANELS[t][0] for t in studio.TAB_TITLES) | {
        "_shared",
        "app",
    }:
        assert f"{PKG}.{module}" not in sys.modules, module


def test_backends_when_loaded_then_reused_app_modules(monkeypatch):
    import fontlabapp.core.scripting as scripting
    import fontlabapp.masters.layers.brackets.native as native

    found = scripting.component_audit_backends()
    assert found.inspect.__name__ == "fontlabapp.components.inspect.model"
    assert found.graph.__name__ == "fontlabapp.components.graph.model"
    assert found.brackets.__name__ == "fontlabapp.masters.layers.brackets.model"
    monkeypatch.setattr(native, "report", lambda: "report")
    assert found.bracket_report() == "report"
    seen = []
    monkeypatch.setattr(
        scripting, "_native", lambda name: NS(UpdateAll=lambda: seen.append(name))
    )
    found.update_all()
    assert seen == ["fontlab"]


@pytest.mark.parametrize("title", sorted(ORIGINALS))
@pytest.mark.usefixtures("studio_qt")
def test_originals_when_ported_then_pure_functions_match_the_script_ast(title):
    path, digest, names, source = ORIGINALS[title]
    assert path.endswith(".py") and len(digest) == 64
    module = importlib.import_module(f"{PKG}.{TAB_MODULES[title]}")
    if not names:
        assert source == "" and title != "Nested Finder"
        assert module.__doc__ and Path(path).stem.split()[0] in module.__doc__
        return
    expected = ast.parse(source)
    ported = [ast.parse(inspect.getsource(getattr(module, name))) for name in names]
    found = {getattr(n, "name", ""): n for tree in ported for n in tree.body}
    for node in expected.body:
        assert ast.dump(found[node.name]) == ast.dump(node), f"{title}: {node.name}"


@pytest.mark.skipif(
    not SCRIPTMIX_ENV,
    reason="FONTLAB_SCRIPTMIX is not set: pinned Scriptmix hashes not checked",
)
@pytest.mark.parametrize("title", sorted(ORIGINALS))
def test_originals_when_scriptmix_present_then_pinned_hash_matches(title):
    path, digest, _, _ = ORIGINALS[title]
    data = subprocess.run(
        ["git", "-C", SCRIPTMIX_ENV, "show", f"25c86b4:{path}"],
        capture_output=True,
        check=False,
    )
    if data.returncode:
        pytest.skip(
            f"pinned Scriptmix commit 25c86b4 not available in FONTLAB_SCRIPTMIX={SCRIPTMIX_ENV}"
        )
    assert hashlib.sha256(data.stdout).hexdigest() == digest


def test_label_when_one_or_many_glyphs_then_name_or_count(studio_qt):  # noqa: F811
    shared = importlib.import_module(f"{PKG}._shared")
    assert (
        shared.label("unnest components", ["A", "A"])
        == "Component Audit: unnest components A"
    )
    assert (
        shared.label("unnest components", ["A", "B"])
        == "Component Audit: unnest components 2 glyphs"
    )
    assert (
        shared.plural(1, "glyph") == "1 glyph"
        and shared.plural(3, "glyph") == "3 glyphs"
    )


# ---------------------------------------------------------------- Composites
def test_composites_when_opened_then_original_report_rows_and_read_only(opened):
    app = opened(history_type=lambda shell: t14.Forbidden())
    before = shapes(app.pkg)
    panel = app.panels["Composites"]
    assert [r[:2] for r in rows(panel)] == [("ring", "Regular"), ("Aacute", "Regular"), ("Aring", "Regular"),
                                            ("I", "Regular"), ("Ccedilla", "Regular"), ("Eacute", "Regular")]  # fmt: skip
    assert rows(panel)[1][2] == ("Regular", "A + acute", "acute 200,600", "components")
    assert rows(panel)[-1][2][-1] == "auto"
    assert text(panel.subtitle) == ("6 composite glyphs · 12 layers with components, 2 of them auto layers. "
                                    "Double-click a row to open the glyph.")  # fmt: skip
    assert text(panel.status) == "6 of 12 rows shown"
    assert panel.scope.itemText(0) == "Current master (Regular)"
    assert panel.scope.itemText(1) == "All masters (2)"
    panel.scope.setCurrentIndex(1)
    assert len(rows(panel)) == 12
    panel.filter.setText("AUTO")
    assert [r[:2] for r in rows(panel)] == [("Eacute", "Regular"), ("Eacute", "Bold")]
    assert text(panel.status) == "2 of 12 rows shown"
    panel.copy_button.click()
    copied = qt().QtGui.QApplication.clipboard().text()
    assert copied == ("Glyph,Master,Components,Offsets,Layer\nEacute,Regular,A + acute,–,auto\n"
                      "Eacute,Bold,A,\"A 10,0\",auto\n")  # fmt: skip
    assert app.tool.status == "Copied 2 rows as CSV"
    panel.grid.select("Eacute", "Bold")
    assert app.preview.calls[-1] == ("load", "Eacute", "Bold")
    panel.open_current()
    assert app.activated == ["Eacute"] and app.updates == ["UpdateAll"]
    assert shapes(app.pkg) == before


def test_composites_when_source_changed_then_action_refused_and_cleared(opened):
    app = opened(history_type=lambda shell: t14.Forbidden())
    panel = app.panels["Composites"]
    app.pkg.layer("Aacute", "Regular").shapes[1].transform.translate(5, 0)
    panel.copy_button.click()
    assert (
        app.tool.status
        == "Component Audit: Component source changed; rescan or reopen this tool."
    )
    assert rows(panel) == [] and not panel.copy_button.isEnabled()
    panel.reload_view()
    assert rows(panel)[1][2][2] == "acute 205,600"


def test_composites_when_font_masters_or_order_changed_then_original_refusals(opened):
    app = opened(history_type=lambda shell: t14.Forbidden())
    panel = app.panels["Composites"]
    app.order.names.reverse()
    panel.open_current()  # no row chosen: nothing happens
    panel.copy_button.click()
    assert app.tool.status.endswith("Font glyph order changed; reopen this tool.")
    app.order.names.reverse()
    panel.reload_view()
    app.pkg.masters.append("Black")
    panel.copy_button.click()
    assert app.tool.status.endswith("Masters changed since preview; reopen this tool.")
    app.pkg.masters.pop()
    panel.reload_view()
    app.active.package = NS(id=99, masters=[], master="")
    panel.copy_button.click()
    assert app.tool.status.endswith(
        "The original font is no longer current; reopen this tool."
    )
    assert not panel.copy_button.isEnabled()  # cleared snapshot
    panel.action(panel.copy_csv)()
    assert app.tool.status.endswith(
        "Results are incomplete; rescan or reopen this tool."
    )


def test_composites_when_result_changed_then_report_refusal(opened, monkeypatch):
    app = opened(history_type=lambda shell: t14.Forbidden())
    panel = app.panels["Composites"]
    shared = sys.modules[f"{PKG}._shared"]
    api = shared.backends().inspect
    monkeypatch.setattr(api, "report", lambda *a: [])
    panel.copy_button.click()
    assert app.tool.status.endswith("Component report changed; reopen this tool.")


def test_composites_when_no_font_then_open_a_font(opened):
    app = opened(history_type=lambda shell: t14.Forbidden())
    app.active.package = None
    app.tool.reload()
    panel = app.panels["Composites"]
    assert text(panel.subtitle) == "Open a font first."
    assert rows(panel) == [] and not panel.copy_button.isEnabled()


# ---------------------------------------------------------------- Where used
def test_where_used_when_opened_then_current_glyph_users_and_selection_only(opened):
    app = opened(current="A", history_type=lambda shell: t14.Forbidden())
    before = shapes(app.pkg)
    panel = app.panels["Where used"]
    assert text(panel.search) == "A"
    assert rows(panel) == [("Aacute", "Regular", ("Regular, Bold", "components")),
                           ("Aring", "Regular", ("Regular, Bold", "components")),
                           ("I", "Regular", ("Regular, Bold", "components")),
                           ("Eacute", "Regular", ("Regular, Bold", "auto"))]  # fmt: skip
    assert text(panel.subtitle) == ("6 glyphs are used as components in this font. "
                                    "Click a row to select that composite in the Font window.")  # fmt: skip
    assert text(panel.status) == "A is used by 4 glyphs"
    panel.grid.select("Aring")
    assert app.selected[-1] == (["Aring"], 7)
    assert app.preview.calls[-1] == ("load", "Aring", "Regular")
    assert app.tool.status == "Selected Aring in the Font window"
    panel.select_button.click()
    assert app.selected[-1] == (["Aacute", "Aring", "I", "Eacute"], 7)
    assert app.tool.status == "Selected 4 glyphs in the Font window"
    panel.search.setText("acute")
    assert [(r[0], r[2][1]) for r in rows(panel)] == [("ring", "components"), ("Aacute", "components"),
                                                       ("Ccedilla", "components"), ("Eacute", "auto")]  # fmt: skip
    assert text(panel.status) == "acute is used by 4 glyphs"
    panel.search.setText("nothing")
    assert (
        text(panel.status) == "No glyph named “nothing”"
        and not panel.select_button.isEnabled()
    )
    panel.search.setText("")
    assert text(panel.status) == "Type a glyph name"
    panel.search.setText("cedilla")
    assert text(panel.status) == "cedilla is used by 1 glyph"
    assert shapes(app.pkg) == before


def test_where_used_when_source_changed_then_selection_refused(opened):
    app = opened(current="A", history_type=lambda shell: t14.Forbidden())
    panel = app.panels["Where used"]
    app.pkg.layer("I", "Bold").shapes.pop()
    panel.select_button.click()
    assert app.selected == []
    assert app.tool.status.endswith(
        "Component source changed; rescan or reopen this tool."
    )


# ---------------------------------------------------------------- Missing bases
def test_missing_bases_when_opened_then_grouped_list_only_and_select(opened):
    app = opened(history_type=lambda shell: t14.Forbidden())
    before = shapes(app.pkg)
    panel = app.panels["Missing bases"]
    assert rows(panel) == [("Ccedilla", "Regular", ("Regular", "C", "glyph missing"))]
    assert text(panel.subtitle) == ("Every component on all 2 masters checked against the glyphs "
                                    "and master layers of this font.")  # fmt: skip
    assert text(panel.status) == "1 missing base in 1 glyphs"
    panel.grid.select("Ccedilla")
    assert app.preview.calls[-1] == ("load", "Ccedilla", "Regular")
    panel.select_button.click()
    assert app.selected[-1] == (["Ccedilla"], 7)
    assert app.tool.status == "Selected 1 glyphs in the Font window"
    assert not hasattr(panel, "apply_button")  # list only: no fix buttons
    assert shapes(app.pkg) == before


def test_missing_bases_when_bold_layer_missing_then_reason_and_none_message(opened):
    pkg = package()
    pkg.add("Cbold", {"Bold": t14.comps(("cedilla", (0, 0)))})
    app = opened(pkg=pkg, history_type=lambda shell: t14.Forbidden())
    panel = app.panels["Missing bases"]
    assert ("Cbold", "Bold", ("Bold", "cedilla", "no Bold layer")) in rows(panel)
    assert text(panel.status) == "2 missing bases in 2 glyphs"
    clean = t14.package()
    app.active.package = clean
    app.order.names = list(clean.glyphs)
    app.tool.reload()
    assert (
        rows(panel) == [] and text(panel.status) == "Every component has its base glyph"
    )
    assert not panel.select_button.isEnabled()


def test_missing_bases_when_results_changed_then_rescan_refusal(opened, monkeypatch):
    app = opened(history_type=lambda shell: t14.Forbidden())
    panel = app.panels["Missing bases"]
    api = sys.modules[f"{PKG}._shared"].backends().inspect
    monkeypatch.setattr(api, "missing", lambda *a, **k: {})
    panel.select_button.click()
    assert app.selected == []
    assert app.tool.status.endswith(
        "Missing component results changed; rescan this tool."
    )


# ---------------------------------------------------------------- Nested
def test_nested_when_selected_then_listed_on_all_masters_and_one_unnest_step(opened):
    app = opened(selection=("Aring",))
    panel = app.panels["Nested"]
    assert panel.chosen_masters() == ["Regular", "Bold"]
    assert rows(panel) == [("Aring", "Regular", ("ring", "acute", "0 contours + 1 component")),
                           ("Aring", "Bold", ("ring", "acute", "0 contours + 1 component"))]  # fmt: skip
    assert panel.apply() is True
    label, glyphs, layers, allow = app.history.calls[0]
    assert (label, glyphs, layers, allow) == ("Component Audit: unnest components Aring", ["Aring"],
                                              [("Aring", "Regular"), ("Aring", "Bold")], False)  # fmt: skip
    assert app.history.retained[0]
    for master in ("Regular", "Bold"):
        found = [
            (s.isComponent, s.shapeData.componentGlyph)
            for s in app.pkg.layer("Aring", master).shapes
        ]
        assert found == [(True, "A"), (True, "acute")]
    assert app.tool.status.startswith(
        "Component Audit: unnest components Aring. Unnested"
    )


def test_nested_when_whole_font_then_auto_glyph_refuses_the_batch(opened):
    import fontlabapp.core.history.glyphs as history

    app = opened(selection=())
    panel = app.panels["Nested"]
    assert rows(panel) == [] and text(panel.count) == "No nested components found"
    app.facts.value = history.auto_facts([("Aring.sc", True, ("Aring",))])
    panel.glyph_scope.setCurrentIndex(1)  # Whole font re-reads the font
    assert [r[0] for r in rows(panel)] == ["Aring", "Aring", "Aring"]
    assert "FontLab cannot undo edits to these glyphs: Aring" in panel.problem
    assert not panel.apply_button.isEnabled()
    assert panel.apply() is False and app.history.calls == []
    app.facts.value = history.auto_facts([])
    panel.reload_view()
    assert panel.problem == "" and panel.apply_button.isEnabled()


def test_nested_when_glyph_changed_after_dry_run_then_stale_and_nothing_written(opened):
    app = opened(selection=("Aring",))
    panel = app.panels["Nested"]
    app.pkg.layer("Aring", "Regular").shapes.pop()
    assert panel.apply() is False
    assert app.history.calls == []
    assert "Reload selection" in app.tool.status


def test_nested_when_history_refuses_then_status_kept(opened):
    app = opened(
        selection=("Aring",),
        history_type=lambda shell: t14.Recorder(shell, refuse="Refused: no."),
    )
    panel = app.panels["Nested"]
    assert panel.apply() is False
    assert app.tool.status == "Refused: no."


# ---------------------------------------------------------------- Graph, Brackets
def test_graph_when_opened_then_shared_panel_without_history(opened):
    app = opened(history_type=lambda shell: t14.Forbidden())
    panel = app.panels["Graph"]
    assert (
        "movable graph" in str(text(panel.subtitle)) and panel.open_button.isEnabled()
    )
    panel.open_button.click()
    assert app.graph.opened == 1 and panel.window == "graph window"
    assert app.tool.status == "Component graph opened"
    app.active.package = None
    app.tool.reload()
    assert (
        text(panel.subtitle) == "Open a font first."
        and not panel.open_button.isEnabled()
    )


def test_brackets_when_opened_then_original_report_text_and_refresh(opened):
    pkg = package()
    pkg.add("dollar", {"Regular": t14.outline(1), "Regular [wt=700]": t14.outline(1)})
    pkg.add("dollar.sc", {"Regular": t14.comps(("dollar", (0, 0)))})
    app = opened(pkg=pkg, history_type=lambda shell: t14.Forbidden())
    before = shapes(app.pkg)
    panel = app.panels["Brackets"]
    shown = panel.output.toPlainText()
    assert shown.startswith(
        "Glyphs with Bracket Layers (1):\ndollar\n\nAffected Components (1):\ndollar.sc"
    )
    assert "Total affected glyphs: 2" in shown
    assert (
        text(panel.status)
        == "Scanned glyphs: 13. Distinct affected glyphs: 2. Refresh after changes."
    )
    app.reports.fail = "Bracket-layer scan expired; no partial result."
    panel.refresh_button.click()
    assert panel.output.toPlainText() == "" and panel.report is None
    assert text(panel.status) == "Bracket-layer scan expired; no partial result."
    app.active.package = None
    app.tool.reload()
    assert text(panel.subtitle) == "Open a font first."
    assert shapes(app.pkg) == before


# ---------------------------------------------------------------- demo launcher
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
    stub_natives(monkeypatch, fontlabapp, lambda name: NS(MainWindow=lambda: 'main', QtGui=NS(QMessageBox=NS(Ok=1))))
    monkeypatch.setattr(
        dialogs, "run_standard_message_box", lambda *a: calls.append(a[2:5])
    )
    runpy.run_path(str(DEMO), run_name="__main__")
    assert calls[-1] == (
        "Component Audit Demo",
        "Component Audit did not open: no font",
        "Warning",
    )


# ---------------------------------------------------------------- window assembly
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
        lambda font, parent, **kw: seen.append((font, kw)) or "view",
    )
    shell = NS(widget="widget", package=lambda: NS(master="Bold"), hint_check="check")
    tool = app_module.tool_for(shell)
    assert app_module.tool_for(shell) is tool and tool.app == "Component Audit"
    tool._font = lambda: None
    assert app_module.glyph_preview(shell, tool) is None
    tool._font = lambda: "font"
    assert app_module.glyph_preview(shell, tool) == "view"
    assert seen == [
        (
            "font",
            {
                "layer": "Bold",
                "controls": False,
                "label_prefix": "Component Audit",
                "hint_check": "check",
            },
        )
    ]


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
    assert importlib.import_module(f"{PKG}").tool_for(NS()).app == "Component Audit"
