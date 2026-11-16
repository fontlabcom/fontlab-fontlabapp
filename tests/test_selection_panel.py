# this_file: tests/test_selection_panel.py
"""Shared selection-layer panel and copy-generator panel (issue 122, T14h).

The panels run on a small PythonQt double: widgets read ``text``, ``value``
and ``currentIndex`` as properties, as PythonQt does, and a widget refuses
Python attributes that shadow native QDialog members. ``scripting`` and
``history`` are replaced through their modules. The tests prove the hooks,
the preview, the Apply gate, the consent tick, the reselect refusal path
and the signal cleanup, not native FontLab behaviour.
"""

from module_paths import module_file as _module_file
import ast
import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import fontlabapp.glyphs.copies as gc
import fontlabapp.glyphs.creation as cr
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.core.scripting as scripting  # noqa: PLR0402
import fontlabapp.contours.selection.panel.model as sp

PANEL = _module_file("_selection_panel")
NATIVE_MEMBERS = {
    "metric", "update", "layout", "font", "palette", "parent", "style", "size", "pos", "width",
    "height", "geometry", "show", "hide", "open", "done", "accept", "reject", "exec", "repaint",
    "move", "resize", "rect", "title", "name", "windowTitle", "objectName", "children", "focus",
    "enabled", "visible", "result", "render", "statusBar", "close", "scroll", "grab", "find",
    "event", "actions", "cursor", "locale", "mask", "lower", "raise_", "x", "y",
}  # fmt: skip
LOG: list = []


# ---------------------------------------------------------------- PythonQt double
class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class Widget:
    SIGNALS = frozenset({"clicked", "toggled", "currentIndexChanged", "valueChanged"})

    def __init__(self, *args):
        object.__setattr__(self, "_signals", {})
        object.__setattr__(self, "_enabled", True)
        object.__setattr__(self, "args", args)

    def __setattr__(self, name, value):
        if name in NATIVE_MEMBERS:
            raise AttributeError(f"Slot '{name}' can not be overwritten")
        object.__setattr__(self, name, value)

    @property
    def font(self):
        return NS(pointSizeF=lambda: 10.0, setPointSizeF=lambda v: None, setBold=lambda f: None)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in Widget.SIGNALS:
            return self._signals.setdefault(name, Signal())
        return lambda *a, **k: None

    def setEnabled(self, flag):
        object.__setattr__(self, "_enabled", bool(flag))

    def isEnabled(self):
        return self._enabled


class Dialog(Widget):
    def close(self):
        self.closeEvent(NS())
        return True


class Label(Widget):
    def __init__(self, text="", *args):
        super().__init__()
        object.__setattr__(self, "_text", text)

    @property
    def text(self):
        return self._text

    def setText(self, text):
        object.__setattr__(self, "_text", text)


class Combo(Widget):
    def __init__(self, *args):
        super().__init__()
        object.__setattr__(self, "items", [])
        object.__setattr__(self, "_index", 0)

    @property
    def currentIndex(self):
        return self._index

    def addItem(self, text):
        self.items.append(text)

    def pick(self, index):
        object.__setattr__(self, "_index", index)
        self.currentIndexChanged.emit(index)


class Check(Widget):
    def __init__(self, text="", *args):
        super().__init__()
        object.__setattr__(self, "label", text)
        object.__setattr__(self, "_checked", False)

    def setChecked(self, flag):
        changed = self._checked != bool(flag)
        object.__setattr__(self, "_checked", bool(flag))
        if changed:  # Qt emits only on a change
            self.toggled.emit(bool(flag))

    def isChecked(self):
        return self._checked


class Spin(Widget):
    def __init__(self, *args):
        super().__init__()
        object.__setattr__(self, "_value", 0)

    @property
    def value(self):
        return self._value

    def setValue(self, value):
        object.__setattr__(self, "_value", value)

    def turn(self, value):
        object.__setattr__(self, "_value", value)
        self.valueChanged.emit(value)


class Button(Widget):
    def __init__(self, text="", *args):
        super().__init__()
        object.__setattr__(self, "label", text)

    def press(self):
        self.clicked.emit(False)


class Item:
    def __init__(self, text=""):
        self.text, self.alignment = text, None

    def setTextAlignment(self, flags):
        self.alignment = flags


class Table(Widget):
    def __init__(self, rows=0, columns=0):
        super().__init__()
        object.__setattr__(self, "cells", {})
        object.__setattr__(self, "row_count", rows)
        object.__setattr__(self, "headers", [])
        object.__setattr__(self, "columns", columns)

    def setHorizontalHeaderLabels(self, labels):
        object.__setattr__(self, "headers", list(labels))

    def horizontalHeader(self):
        return Widget()

    def verticalHeader(self):
        return Widget()

    def setRowCount(self, count):
        object.__setattr__(self, "row_count", count)
        object.__setattr__(self, "cells", {})

    @property
    def rowCount(self):
        return self.row_count

    def setItem(self, row, column, item):
        self.cells[row, column] = item

    def texts(self, row):
        return [self.cells[row, c].text for c in sorted(c for r, c in self.cells if r == row)]


class Grid(Widget):
    def __init__(self, *args):
        super().__init__()
        object.__setattr__(self, "placed", [])

    def addWidget(self, widget, *where):
        self.placed.append((widget, where))


def fake_qt():
    gui = NS(
        QDialog=Dialog, QLabel=Label, QComboBox=Combo, QCheckBox=Check, QSpinBox=Spin,
        QPushButton=Button, QTableWidget=Table, QTableWidgetItem=Item,
        QVBoxLayout=Widget, QHBoxLayout=Widget, QGridLayout=Grid,
        QAbstractItemView=NS(NoEditTriggers=0), QHeaderView=NS(Stretch=1),
    )  # fmt: skip
    core = NS(Qt=NS(AlignRight=2, AlignVCenter=128), QDateTime=NS(currentDateTimeUtc=lambda: "UTC"))
    return NS(QtGui=gui, QtCore=core)


# ---------------------------------------------------------------- world
class World:
    def __init__(self):
        self.package = None
        self.names: list[str] = []
        self.closed: list[str] = []
        self.facts = history.auto_facts(())
        self.scans = 0


@pytest.fixture
def world(monkeypatch):
    LOG.clear()
    state = World()
    monkeypatch.setitem(sys.modules, "PythonQt", fake_qt())
    monkeypatch.delitem(sys.modules, "fontlabapp.contours.selection.panel.ui", raising=False)
    monkeypatch.setattr(scripting, "current_package", lambda expected_id=None: state.package)

    def names():
        if state.names is None:
            raise RuntimeError("selection unreadable")
        return list(state.names)

    monkeypatch.setattr(scripting, "names_selected_names", names)

    def connect_guarded(dialog, signal, callback):
        def guarded(*args):
            try:
                callback(*args)
            except Exception as error:  # noqa: BLE001 - the App guard shows the error
                dialog.status.setText("Error: " + repr(error))

        signal.connect(guarded)
        dialog._connections.append((signal, guarded))

    def close_script_dialog(dialog, event, key, **kwargs):
        for signal, slot in dialog._connections:
            signal.disconnect(slot)
        dialog._connections = []
        state.closed.append(key)

    monkeypatch.setattr(scripting, "connect_guarded", connect_guarded)
    monkeypatch.setattr(scripting, "close_script_dialog", close_script_dialog)

    def scan(package):
        state.scans += 1
        return state.facts

    monkeypatch.setattr(history, "scan_auto_facts", scan)
    yield state
    sys.modules.pop("fontlabapp.contours.selection.panel.ui", None)


def font(pid=5, masters=("L", "B")):
    return NS(id=pid, masters=list(masters), master=masters[0], fgId=40)


def row(name, master, note="", value=1):
    return NS(name=name, master=master, note=note, value=value)


def in_place(**overrides):
    """A small in-place tool: one spin box control; logs every hook call."""

    class Tool(sp.panel_type()):
        TITLE, KEY, ACTION = "Tool", "tool_key", "Do It"
        HEADERS = ("Glyph · master", "Value")

        def build_controls(self):
            self.step = QtSpin()
            self.step.setValue(3)
            self.add_row("Step", self.step)
            self.watch(self.step.valueChanged)
            LOG.append(("build_controls",))

        def plan_rows(self, package, masters):
            LOG.append(("plan_rows", tuple(masters), self.consented()))
            notes = overrides.get("notes", {})
            return [row(n, m, notes.get(n, "")) for n in self.names for m in masters]

        def cells(self, item):
            return [f"{item.name} · {item.master}", item.note or str(item.value * self.step.value)]

        def pending(self, todo):
            return f"{len(todo)} to do" if todo else "Nothing to do"

        def write(self, package, rows):
            LOG.append(("write", [f"{r.name}/{r.master}" for r in rows if not r.note]))
            if overrides.get("fail"):
                raise ValueError("Refused: test")
            return {"layers": len([r for r in rows if not r.note]), "mismatches": overrides.get("mismatches", [])}

        def result_text(self, result):
            return f"Did {result['layers']}"

        def on_reselect(self):
            LOG.append(("on_reselect",))

        def on_result(self, result):
            LOG.append(("on_result", result["layers"]))

    return Tool


def QtSpin():
    return sys.modules["PythonQt"].QtGui.QSpinBox()


# ---------------------------------------------------------------- public names (T14i)
def test_public_hooks_when_panel_built_then_every_documented_name_exists(world):
    world.package, world.names = font(), ["A"]
    panel = in_place()(None)
    missing = [name for name in (*sp.HOOKS, *sp.MEMBERS) if not hasattr(panel, name)]
    assert missing == [], missing
    for name in (*sp.HOOKS, "add_row", "apply", "refresh", "reselect", "watch", "plan", "consented"):
        assert callable(getattr(panel, name)), name
    assert hasattr(panel, "_connections"), "the private alias keeps working"
    assert set(sp.HOOKS).isdisjoint(sp.MEMBERS)


# ---------------------------------------------------------------- in-place panel
def test_panel_when_opened_then_hooks_preview_scope_and_consent(world):
    world.package, world.names = font(), ["A", "B"]
    panel = in_place()(None)
    assert LOG[0] == ("build_controls",)
    assert ("plan_rows", ("L",), False) in LOG, "current master by default, no consent"
    assert [panel.table.texts(r) for r in range(panel.table.rowCount)] == [["A · L", "3"], ["B · L", "3"]]
    assert panel.table.cells[0, 1].alignment == 130, "numbers right-aligned"
    assert panel.status.text == "2 to do" and panel.apply_button.isEnabled()
    assert panel.subtitle.text == "2 glyphs: A, B"
    assert panel.consent.label == sp.BASES_TEXT
    panel.scope.pick(1)
    assert panel.table.rowCount == 4
    panel.consent.setChecked(True)
    assert LOG[-1] == ("plan_rows", ("L", "B"), True)
    panel.step.turn(5)
    assert panel.table.texts(0) == ["A · L", "5"], "a watched control refreshes the preview"


def test_panel_when_rows_blocked_then_apply_off_and_note_shown(world):
    world.package, world.names = font(), ["A"]
    panel = in_place(notes={"A": "locked layer (skipped)"})(None)
    assert panel.table.texts(0) == ["A · L", "locked layer (skipped)"]
    assert panel.table.cells[0, 1].alignment is None, "notes are not right-aligned"
    assert not panel.apply_button.isEnabled() and panel.status.text == "Nothing to do"


def test_panel_when_applied_then_one_write_from_a_fresh_plan_and_result_text(world):
    world.package, world.names = font(), ["A"]
    panel = in_place(mismatches=["A · L: x"])(None)
    LOG.clear()
    panel.apply_button.press()
    assert LOG[:3] == [("plan_rows", ("L",), False), ("write", ["A/L"]), ("on_result", 1)]
    assert panel.status.text == "Did 1 · did not read back as planned: A · L: x"
    assert panel.last_result["layers"] == 1


def test_panel_when_write_refused_then_status_and_no_result(world):
    world.package, world.names = font(), ["A"]
    panel = in_place(fail=True)(None)
    panel.apply_button.press()
    assert panel.status.text == "Refused: test" and panel.last_result == {}


def test_panel_when_font_switched_then_apply_refused_before_write(world):
    world.package, world.names = font(), ["A"]
    panel = in_place()(None)
    world.package = font(pid=99)
    LOG.clear()
    panel.apply_button.press()
    assert ("write", ["A/L"]) not in LOG and "font changed" in panel.status.text


def test_reselect_when_refused_then_status_line_not_slot_error(world):
    """S7 M6: the reselect slot catches the refusal and shows it, as apply does."""
    world.package, world.names = font(), ["A"]
    panel = in_place()(None)
    world.package = None
    panel.selection_button.press()
    assert panel.status.text == "The font changed. Run this script again."
    world.package, world.names = font(), None
    panel.selection_button.press()
    assert panel.status.text == "selection unreadable", "RuntimeError from the selection read"
    assert "Error" not in panel.status.text


def test_reselect_when_done_then_new_names_consent_cleared_and_hook(world):
    world.package, world.names = font(), ["A"]
    panel = in_place()(None)
    panel.consent.setChecked(True)
    world.names = ["B", "C"]
    LOG.clear()
    panel.selection_button.press()
    assert not panel.consent.isChecked(), "the consent belongs to the glyphs the user saw"
    assert ("on_reselect",) in LOG
    assert [panel.table.texts(r)[0] for r in range(panel.table.rowCount)] == ["B · L", "C · L"]


def test_panel_when_no_font_or_no_selection_then_message_and_apply_off(world):
    panel = in_place()(None)
    assert panel.subtitle.text == "Open a font and select glyphs. Then run this script again."
    assert not panel.apply_button.isEnabled()
    world.package, world.names = font(), ["A"]
    panel.selection_button.press()
    assert panel.status.text == "Open a font and select glyphs. Then run this script again.", "bound to no font"
    world.names = []
    panel = in_place()(None)
    assert panel.subtitle.text == "Select glyphs in the Font window. Then press Use selection."
    assert not panel.apply_button.isEnabled()


def test_panel_when_closed_then_signals_disconnected_under_key(world):
    world.package, world.names = font(), ["A"]
    panel = in_place()(None)
    assert panel._connections
    panel.close_button.press()
    assert world.closed == ["tool_key"] and panel._connections == []


def test_panel_when_no_scope_no_consent_then_all_masters_and_widgets_absent(world):
    class Plain(in_place()):
        SCOPE, CONSENT = False, ""

    world.package, world.names = font(), ["A"]
    panel = Plain(None)
    assert panel.scope is None and panel.consent is None and panel.consented() is False
    assert panel.table.rowCount == 2, "no scope: every master"


# ---------------------------------------------------------------- copy generator panel
def copies_panel():
    class Copies(gc.panel_type()):
        TITLE, KEY, NOUN = "Make Copies", "copies_key", "capitals"

        def build_controls(self):
            self.scale = QtSpin()
            self.scale.setValue(70)
            self.add_row("Scale", self.scale)

        def survey(self, package, facts, allow_rebuild):
            LOG.append(("survey", allow_rebuild))
            rows = [gc.Row("H", "h.sc", (("L", None), ("B", None)), rebuild=("eacute.sc",))]
            if not allow_rebuild:
                rows = [gc.Row("H", "h.sc", note=cr.rebuild_note(("eacute.sc",)), rebuild=("eacute.sc",))]
            return [*rows, gc.Row("a", "", note="not a capital")]

        def jobs(self, rows):
            return [(r.target, [("L", [], 300)]) for r in rows if not r.note]

    return Copies


def test_copies_panel_when_rebuild_candidate_then_skipped_until_consent(world, monkeypatch):
    calls = []
    monkeypatch.setattr(gc, "create", lambda package, jobs, title, facts, **kw: calls.append((jobs, title, kw)) or {
        "glyphs": len(jobs), "layers": len(jobs), "mismatches": []})  # fmt: skip
    world.package, world.names = font(), ["H", "a"]
    panel = copies_panel()(None)
    assert panel.consent.label == cr.REBUILD_LABEL and panel.scope is None
    assert panel.table.headers == ["Source", "New glyph", "Action"]
    assert panel.table.texts(0) == ["H", "h.sc", "may rebuild auto eacute.sc"]
    assert not panel.apply_button.isEnabled() and panel.status.text == "0 glyphs to create"
    panel.consent.setChecked(True)
    assert panel.table.texts(0) == ["H", "h.sc", "create on 2 masters · may rebuild auto eacute.sc"]
    assert panel.table.texts(1) == ["a", "", "not a capital"]
    panel.apply_button.press()
    assert calls == [([("h.sc", [("L", [], 300)])], "Make Copies", {"allow_rebuild": True})]
    assert panel.status.text == "Created 1 glyph (1 master layer)"
    panel.selection_button.press()
    assert not panel.consent.isChecked(), "Use selection clears the consent"


def test_copies_panel_when_nothing_created_then_nothing_text(world, monkeypatch):
    monkeypatch.setattr(gc, "create", lambda *a, **k: {"glyphs": 0, "layers": 0, "mismatches": []})
    world.package, world.names = font(), ["H"]
    panel = copies_panel()(None)
    panel.consent.setChecked(True)
    panel.apply_button.press()
    assert panel.status.text == "Nothing to create"


def test_copies_panel_when_no_selection_then_noun_in_message(world):
    world.package, world.names = font(), []
    panel = copies_panel()(None)
    assert panel.subtitle.text == "Select capitals in the Font window. Then press Use selection."


# ---------------------------------------------------------------- source rules
def test_qt_classes_when_parsed_then_never_shadow_native_members():
    tree = ast.parse(PANEL.read_text(encoding="utf-8"))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    assigned = {
        n.attr for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
        and isinstance(n.value, ast.Name) and n.value.id == "self"
    }  # fmt: skip
    defined = {f.name for cls in classes for f in cls.body if isinstance(f, ast.FunctionDef)}
    assert classes and not (assigned | defined) & NATIVE_MEMBERS


def test_qt_classes_when_parsed_then_every_method_documented_and_typed():
    tree = ast.parse(PANEL.read_text(encoding="utf-8"), feature_version=(3, 11))
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        assert ast.get_docstring(cls), cls.name
        methods = [f for f in cls.body if isinstance(f, ast.FunctionDef)]
        assert not [f.name for f in methods if not ast.get_docstring(f)], cls.name
        untyped = [
            f.name for f in methods
            if f.returns is None or any(a.annotation is None for a in f.args.args if a.arg != "self")
        ]  # fmt: skip
        assert not untyped, (cls.name, untyped)


def test_qt_module_when_parsed_then_shared_calls_go_through_modules():
    tree = ast.parse(PANEL.read_text(encoding="utf-8"))
    shared = ("fontlabapp.core.scripting", "fontlabapp.core.history.glyphs", "fontlabapp.glyphs.copies", "fontlabapp.glyphs.creation")
    imported = {
        alias.name for n in tree.body if isinstance(n, ast.ImportFrom) and n.module in shared
        for alias in n.names
    }  # fmt: skip
    assert imported == set(), "a copied name would ignore a replaced function"


# ---------------------------------------------------------------- cold import
@pytest.mark.parametrize(
    "module",
    [
        "fontlabapp.contours.selection.panel.model", "fontlabapp.glyphs.creation", "fontlabapp.glyphs.copies",
        "fontlabapp.contours.copy", "fontlabapp.hints.postscript",
    ],
)  # fmt: skip
def test_module_when_cold_imported_then_only_stdlib_and_no_qt(module):
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
lazy = {{'fontlabapp.contours.selection.panel.ui', 'fontlabapp.core.scripting', 'PythonQt', 'fontlab', 'fontpr', 'fontgate'}}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr


def test_panel_type_when_called_then_loads_private_class_lazily(world):
    first = sp.panel_type()
    assert first is importlib.import_module("fontlabapp.contours.selection.panel.ui").SelectionPanel
    assert gc.panel_type() is importlib.import_module("fontlabapp.contours.selection.panel.ui").CopiesPanel
    assert issubclass(gc.panel_type(), first)


def test_copies_when_controls_change_then_facts_reused_until_reselect(world):
    world.package, world.names = font(), ["H"]
    panel = copies_panel()(None)
    assert world.scans == 1
    assert panel.facts is world.facts
    panel.watch(panel.scale.valueChanged)
    panel.scale.valueChanged.emit(71)
    panel.consent.setChecked(True)
    assert world.scans == 1, "control signals must not scan the font"
    panel.selection_button.press()
    assert world.scans == 2, "Use selection must take fresh facts"
    panel.scan()
    assert world.scans == 3, "explicit Refresh must take fresh facts"


def test_copies_when_apply_then_one_fresh_scan_plans_and_writes(world, monkeypatch):
    world.package, world.names = font(), ["H"]
    panel = copies_panel()(None)
    panel.consent.setChecked(True)
    fresh = history.auto_facts((("new", False, ("H",)),))
    world.facts = fresh
    received = []
    monkeypatch.setattr(gc, "create", lambda package, jobs, title, facts, **kw: received.append(facts) or {"glyphs": 1, "layers": 2, "mismatches": []})
    panel.apply_button.press()
    assert received == [fresh] and panel.facts is fresh
    assert world.scans == 2, "one initial scan and one Apply scan"


def test_copies_when_write_fails_then_preview_keeps_the_apply_scan(world, monkeypatch):
    world.package, world.names = font(), ["H"]
    panel = copies_panel()(None)
    fresh = history.auto_facts((("new", False, ("H",)),))
    world.facts = fresh
    def fail(*args, **kwargs):
        raise ValueError("refused")
    monkeypatch.setattr(gc, "create", fail)
    panel.apply()
    assert panel.facts is fresh and world.scans == 2
    assert panel.status.text == "refused"
