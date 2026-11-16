# this_file: tests/test_component_panel.py
"""Shared ComponentPanel base of the Components scripts (issue 122, T14f).

The panel runs on the PythonQt double of ``test_anchor_panel`` and the
FontLab doubles of ``test_component_writer``, which log every native call.
The tests prove the preview, the Apply gate, the one-Undo call shape with the
retained component, and the signal cleanup, not native FontLab behaviour.
"""

from module_paths import module_file as _module_file
import ast
import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import test_anchor_panel as qtd
import test_component_writer as fld

import fontlabapp.anchors.panel.model as anchor_panel  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.components.panel.model as cp
import fontlabapp.components.writer as cw
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402
import fontlabapp.metrics.panel.model as mp
import fontlabapp.core.scripting as scripting  # noqa: PLR0402

SOURCE = _module_file("_component_panel")
LOG = fld.LOG
STAMP = "UTC"  # the QDateTime double of test_anchor_panel.fake_qt


class Combo(qtd.Widget):
    """A QComboBox double: PythonQt reads currentIndex as a property."""

    currentIndex = 0


class Native(fld.Native):
    """The component ``fontlab`` double, plus the main window palette."""

    def __init__(self):
        super().__init__()
        self.palette = qtd.Palette({(qtd.Palette.WindowText,): 7})

    def MainWindow(self):
        return NS(palette=self.palette)


@pytest.fixture
def env(monkeypatch):
    """Load the real ``_component_panel`` over the PythonQt and FontLab doubles."""
    LOG.clear()
    qtd.LOG.clear()
    native = Native()
    qt = qtd.fake_qt()
    qt.QtGui.QComboBox = Combo
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.setitem(sys.modules, "fontlab", native)
    monkeypatch.delitem(sys.modules, "fontlabapp.components.panel.ui", raising=False)
    state = NS(package=None, names=[], facts=history.auto_facts(()), native=native)
    monkeypatch.setattr(scripting, "current_package", lambda pid=None: (
        state.package if state.package is not None and pid in (None, state.package.id) else None
    ))
    monkeypatch.setattr(scripting, "names_selected_names", lambda: list(state.names))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: state.facts)
    module = importlib.import_module("fontlabapp.components.panel.ui")
    yield module, state
    sys.modules.pop("fontlabapp.components.panel.ui", None)


def font(*glyphs, pid=5):
    """A package double with masters L and B; ``findName`` resolves the glyphs."""
    found = {g.name: g for g in glyphs}
    return NS(id=pid, isNull=False, masters=["L", "B"], master="L", findName=found.get)


def decompose_panel(module, package_of):
    """A subclass like the Decompose script: one row per component."""

    class Decompose(module.ComponentPanel):
        TITLE, KEY, ACTION, DONE = "Decompose Components", "test_decompose", "Decompose", "Decomposed"
        HEADERS = ("Glyph · master", "Component", "Becomes")

        def build_controls(self):
            self.scope = self.scope_box()
            self.watch(self.scope.currentIndexChanged)

        def planner(self):
            package = package_of()

            def plan(glyph, master, layer):
                rows = []
                for shape in cw.components(layer):
                    why = cw.copy_problem(package, (glyph.name, master), shape, master)
                    name = cw.base_of(shape)
                    if why:
                        rows.append(cw.Change(name, "", "", problem=why))
                        continue
                    rows.append(cw.Change(name, "", cw.parts_text(*cw.part_counts(package, shape, master)), shape.id))
                return rows

            return plan

        def editor(self):
            return cw.EjectEditor(unlock=True)

    return Decompose


def accented(state):
    package, aacute, component = fld.accented()
    state.package = font(*package.glyphs.values())
    state.names = ["Aacute"]
    return aacute, component


# ---------------------------------------------------------------- module helpers
def test_panel_type_when_called_then_component_panel_class_and_shared_helpers(env):
    module, _ = env
    assert cp.panel_type() is module.ComponentPanel
    assert cp.muted is mp.muted and cp.ink is anchor_panel.ink
    assert cp.readable_palette is anchor_panel.readable_palette
    assert (cp.ERROR_COLOR, cp.MAX_ROWS) == ("#d33", 500)


def test_module_when_cold_imported_then_only_stdlib_and_no_qt():
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
import fontlabapp.components.panel.model
lazy = {'fontlabapp.components.panel.ui', 'fontlabapp.components.writer', 'fontlabapp.core.scripting', 'PythonQt', 'fontlab'}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------- panel behaviour
def test_panel_when_no_font_or_no_selection_then_explains_and_blocks(env):
    module, state = env
    panel = decompose_panel(module, lambda: state.package)()
    assert panel.subtitle.text == "Open a font first." and not panel.apply_button.enabled
    state.package = font(fld.Glyph("a", L=[]))
    panel.reload_button.clicked.emit()
    assert panel.subtitle.text.startswith("Select glyphs") and not panel.apply_button.enabled


def test_panel_when_planned_then_preview_and_one_undo_apply_with_retained_component(env):
    module, state = env
    aacute, component = accented(state)
    panel = decompose_panel(module, lambda: state.package)()
    assert panel.subtitle.text == "1 glyph: Aacute"
    assert panel.table.texts() == [["Aacute · L", "A", "1 contour"]]
    assert panel.status.text == "1 component change on 1 layer" and panel.apply_button.enabled
    LOG.clear()
    panel.apply_button.clicked.emit()
    assert fld.history_events() == [
        ("init", "Aacute/L"),
        ("init", "Aacute"),
        ("stamp", "Aacute", STAMP),
        ("notify", "Decompose Components",
         [f"shape-{component.id}", f"data-{component.id}", f"builder-{component.id}",
          "Aacute/L", "Aacute"], (True,)),
        ("stamp", "Aacute", STAMP),
    ]  # fmt: skip
    assert panel.status.text == "Decomposed 1 component on 1 layer"
    assert panel.last_result == {"pending_note": "", "edits": 1, "layers": 1, "skipped": [], "pending_updates": ()}
    assert component not in aacute.by_master["L"].shapes


def test_panel_when_scope_is_all_masters_then_every_master_planned(env):
    module, state = env
    accented(state)
    panel = decompose_panel(module, lambda: state.package)()
    assert panel.chosen_masters() == ["L"]
    panel.scope.currentIndex = 1
    assert panel.chosen_masters() == ["L", "B"]


def test_panel_when_base_cannot_be_copied_then_red_row_and_apply_off(env):
    module, state = env
    accented(state)
    state.package.findName("A").by_master["L"].shapes[0].transform = fld.Transform(affine=False)
    panel = decompose_panel(module, lambda: state.package)()
    assert panel.table.texts() == [["Aacute · L", "A", "base A holds a shape that cannot be copied"]]
    assert panel.table.cells[0, 2].foreground.color().value == "#d33"
    assert panel.status.text == "Aacute · L: base A holds a shape that cannot be copied"
    assert not panel.apply_button.enabled


def test_panel_when_glyph_is_base_of_auto_composite_then_blocked_row_first(env):
    module, state = env
    accented(state)
    state.facts = history.auto_facts([("Aacutedot", True, ("Aacute",))])
    panel = decompose_panel(module, lambda: state.package)()
    assert panel.table.texts()[0] == ["Aacute", "blocked", "base of auto Aacutedot"]
    assert "Aacute: base of auto Aacutedot" in panel.status.text
    assert not panel.apply_button.enabled


def test_panel_when_updates_queued_then_writes_discloses_and_queue_kept(env):
    module, state = env
    accented(state)
    panel = decompose_panel(module, lambda: state.package)()
    state.native.pending.append(41)
    LOG.clear()
    panel.apply()
    assert fld.history_events() and state.native.pending == [41]
    assert panel.last_result["pending_updates"] == (41,) and "8537" in panel.status.text and panel.last_result["pending_note"] in panel.status.text


def test_panel_when_font_master_or_glyph_changed_then_apply_refused(env):
    module, state = env
    accented(state)
    panel = decompose_panel(module, lambda: state.package)()
    LOG.clear()
    state.package.master = "B"
    with pytest.raises(ValueError, match="Master changed; Reload selection."):
        panel.apply()
    state.package = font(fld.Glyph("b", L=[]))
    with pytest.raises(ValueError, match="Glyphs changed; Reload selection."):
        panel.apply()
    state.package = font(fld.Glyph("Aacute", L=[]), pid=9)
    with pytest.raises(ValueError, match="The font changed; press Reload selection."):
        panel.apply()
    assert fld.history_events() == []


def test_panel_when_first_scan_raises_then_error_status_and_no_apply(env, monkeypatch):
    module, state = env
    accented(state)

    def broken():
        raise OSError("selection unreadable")

    monkeypatch.setattr(scripting, "names_selected_names", broken)
    panel = decompose_panel(module, lambda: state.package)()
    assert panel.status.text == "Error: selection unreadable"
    assert not panel.apply_button.enabled and panel.close_button.enabled


def test_panel_when_closed_then_signals_disconnected_and_deleted(env, monkeypatch):
    module, state = env
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    accented(state)
    panel = decompose_panel(module, lambda: state.package)()
    sys._fontlab_samples["test_decompose"] = panel
    signals = [s for s, _ in panel._connections]
    assert len(signals) == 4
    qtd.LOG.clear()
    panel.close_button.clicked.emit()
    assert all(s.slots == [] for s in signals) and panel._connections == []
    assert qtd.LOG == [("qt-close",), ("deleteLater",)]
    assert "test_decompose" not in sys._fontlab_samples


# ---------------------------------------------------------------- source rules
def test_component_panel_class_when_parsed_then_every_method_documented_and_typed():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), feature_version=(3, 11))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    assert cls.name == "ComponentPanel" and ast.get_docstring(cls)
    methods = [f for f in cls.body if isinstance(f, ast.FunctionDef)]
    assert not [f.name for f in methods if not ast.get_docstring(f)]
    untyped = [
        f.name for f in methods
        if f.returns is None or any(a.annotation is None for a in f.args.args if a.arg != "self")
    ]
    assert not untyped, untyped


def test_component_panel_class_when_parsed_then_never_shadows_native_members():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    assigned = {
        n.attr for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
        and isinstance(n.value, ast.Name) and n.value.id == "self"
    }
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    defined = {f.name for f in cls.body if isinstance(f, ast.FunctionDef)}
    assert not (assigned | defined) & qtd.NATIVE_MEMBERS


def test_component_panel_when_parsed_then_shared_calls_go_through_modules():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = {
        alias.name for n in tree.body if isinstance(n, ast.ImportFrom)
        and n.module in ("fontlabapp.core.scripting", "fontlabapp.components.writer", "fontlabapp.core.history.glyphs",
                         "fontlabapp.core.edit_guards")
        for alias in n.names
    }  # fmt: skip
    assert imported == set(), "a copied name would ignore a replaced function"
