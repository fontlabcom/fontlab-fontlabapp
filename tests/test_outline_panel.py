# this_file: tests/test_outline_panel.py
"""Shared OutlinePanel and TransformPanel bases of the Contours scripts (issue 122, T14g).

The panels run on the PythonQt double of ``test_anchor_panel`` (extended
with check boxes, combos, double spin boxes and a painter) and on the
outline doubles of ``test_outline_writer``. The tests prove the preview, the
Apply gate, the one-Undo call shape, the subclass hooks, the consent tick,
the preview painter and the signal cleanup, not native FontLab behaviour.
"""

from module_paths import module_file as _module_file
import ast
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from typing import ClassVar

import pytest
import test_anchor_panel as qtd
import test_component_writer as fld
import test_outline_writer as tow

import fontlabapp.anchors.panel.model as anchor_panel  # noqa: PLR0402 - from-import hits the package __getattr__
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402
import fontlabapp.contours.panel.model as op
import fontlabapp.contours.transform.model as ot
import fontlabapp.contours.writer as ow
import fontlabapp.core.scripting as scripting  # noqa: PLR0402

LOG = fld.LOG
PANEL = _module_file("_outline_panel")
TRANSFORM = _module_file("_outline_transform")
# Members of QWidget/QDialog/QPaintDevice that a Python subclass must not shadow:
# PythonQt raises "Slot ... can not be overwritten".
NATIVE_MEMBERS = qtd.NATIVE_MEMBERS | {
    "actions", "cursor", "locale", "mask", "scroll", "find", "close", "render",
    "statusBar", "grab", "lower", "raise_", "x", "y", "frameGeometry",
}  # fmt: skip


# ---------------------------------------------------------------- PythonQt double additions
class Widget(qtd.Widget):
    SIGNALS = qtd.Widget.SIGNALS | {"toggled"}

    def __getattr__(self, name):
        if name in Widget.SIGNALS:
            signal = qtd.Signal()
            setattr(self, name, signal)
            return signal
        return qtd.Widget.__getattr__(self, name)


class CheckBox(Widget):
    def __init__(self, text="", *args):
        super().__init__()
        self.text, self.checked, self.visible = text, False, True

    def setChecked(self, flag):
        changed, self.checked = self.checked != bool(flag), bool(flag)
        if changed:  # Qt emits only on a change
            self.toggled.emit(self.checked)

    def isChecked(self):
        return self.checked

    def setVisible(self, flag):
        self.visible = bool(flag)


class Combo(Widget):
    """PythonQt reads currentIndex as a property."""

    def __init__(self, *args):
        super().__init__()
        self.currentIndex, self.items = 0, []

    def addItem(self, text):
        self.items.append(text)

    def setItemText(self, index, text):
        self.items[index] = text

    def setCurrentIndex(self, index):
        changed, self.currentIndex = self.currentIndex != index, index
        if changed:
            self.currentIndexChanged.emit(index)


class Spin(Widget):
    def __init__(self, *args):
        super().__init__()
        self.value, self.calls = 0, []

    def setRange(self, low, high):
        self.calls.append(("range", low, high))

    def setValue(self, value):
        changed, self.value = self.value != value, value
        if changed:
            self.valueChanged.emit(value)


class DoubleSpin(Spin):
    pass


class Painter:
    Antialiasing = 1
    log: ClassVar[list] = []
    fail = False

    def __init__(self, widget):
        self.ended, self.paths = False, []
        Painter.log.append(self)

    def drawPath(self, path):
        if Painter.fail:
            raise RuntimeError("boom paint")
        self.paths.append(path)

    def end(self):
        self.ended = True

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class PainterPath(tow.Path2):
    def boundingRect(self):
        return NS(united=lambda other: NS(x=lambda: 0.0, y=lambda: 0.0, width=lambda: 100.0, height=lambda: 100.0))


class Preview(qtd.Widget):
    width, height = 300, 220

    def update(self):
        LOG.append(("repaint",))


class Native(fld.Native):
    """The FontLab double plus the main window palette."""

    def __init__(self):
        super().__init__()
        self.palette = qtd.Palette({(qtd.Palette.WindowText,): 7})

    def MainWindow(self):
        return NS(palette=self.palette)


@pytest.fixture
def env(monkeypatch):
    """Load the real ``_outline_panel`` and ``_outline_transform`` over the doubles."""
    LOG.clear()
    qtd.LOG.clear()
    Painter.log.clear()
    Painter.fail = False
    native = Native()
    qt = qtd.fake_qt()
    qt.QtGui.QComboBox, qt.QtGui.QCheckBox = Combo, CheckBox
    qt.QtGui.QSpinBox, qt.QtGui.QDoubleSpinBox = Spin, DoubleSpin
    qt.QtGui.QWidget, qt.QtGui.QPainter, qt.QtGui.QPainterPath = Preview, Painter, PainterPath
    qt.QtGui.QTransform, qt.QtGui.QPen = tow.Matrix, lambda color: Widget()
    qt.QtCore.QDateTime = NS(currentDateTimeUtc=lambda: fld.STAMP)
    qt.QtCore.Qt = NS(AlignRight=2, ScrollBarAlwaysOff=3, DashLine=4, NoPen=0)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.setitem(sys.modules, "fontlab", native)
    for name in ("fontlabapp.contours.panel.ui", "fontlabapp.contours.transform.ui"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    state = NS(package=None, names=[], facts=history.auto_facts(()), native=native)
    monkeypatch.setattr(scripting, "current_package", lambda pid=None: (
        state.package if state.package is not None and pid in (None, state.package.id) else None
    ))  # fmt: skip
    monkeypatch.setattr(scripting, "names_selected_names", lambda: list(state.names))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: state.facts)
    panel_module = importlib.import_module("fontlabapp.contours.panel.ui")
    transform_module = importlib.import_module("fontlabapp.contours.transform.ui")
    yield NS(panel=panel_module, transform=transform_module), state
    for name in ("fontlabapp.contours.panel.ui", "fontlabapp.contours.transform.ui"):
        sys.modules.pop(name, None)


def font(*glyphs, pid=5):
    """A package double with masters L and B; ``findName`` resolves the glyphs."""
    found = {g.name: g for g in glyphs}
    return NS(id=pid, isNull=False, masters=["L", "B"], master="L", findName=found.get)


def square_glyph(state, name="A", **kwargs):
    found = tow.glyph(name, {"L": [tow.Shape(tow.SQUARE)], "B": [tow.Shape(tow.SQUARE)]}, **kwargs)
    state.package = font(found)
    state.names = [name]
    return found


class Shift(ow.Editor):
    """Move every node of the planned shapes by dx."""

    def __init__(self, keep=True):
        self.keep = keep

    def write(self, layer, steps):
        for step in steps:  # one step: [(shape, dx), ...] of one row
            for shape, dx in step:
                for contour in shape.contours:
                    for node in contour.nodes():
                        node.x += dx if self.keep else 0

    def check(self, prepared):
        return [] if self.keep else [layer.name for layer, _ in prepared]


def shift_panel(module, structural=False, keep=True):
    """A subclass like the Round Coordinates script: one row per layer."""

    class ShiftPanel(module.OutlinePanel):
        TITLE, KEY, ACTION, DONE, UNIT = "Shift Outlines", "test_shift", "Shift", "Shifted", "shape"
        STRUCTURAL = structural

        def build_controls(self):
            self.by = self.spin(-100, 100, 10, " units")
            self.add_row("By", self.by)
            self.hooks = ["build_controls"]

        def build_extra(self, root):
            self.hooks.append("build_extra")

        def on_reload(self):
            self.hooks.append("on_reload")

        def after_refresh(self):
            self.hooks.append("after_refresh")

        def planner(self):
            dx = int(self.by.value)
            if dx > 50:
                raise ValueError("Too far.")

            def plan(glyph, master, layer):
                shapes, notes = ow.outline_shapes(layer)
                key = ("shift", dx) if structural else None
                edit = [(s, dx) for s in shapes] if dx else None
                rows = [ow.Change("outline", "0", ow.fmt(dx), edit, key=key)] if edit else []
                return rows + ow.note_rows(notes)

            return plan

        def editor(self):
            return Shift(keep)

    return ShiftPanel


# ---------------------------------------------------------------- module helpers
def test_panel_type_when_called_then_outline_panel_class_and_anchor_panel_helpers(env):
    modules, _ = env
    assert op.panel_type() is modules.panel.OutlinePanel
    assert ot.panel_type() is modules.transform.TransformPanel
    assert issubclass(modules.transform.TransformPanel, modules.panel.OutlinePanel)
    for name in ("ink", "muted", "readable_palette", "ERROR_COLOR", "MAX_ROWS"):
        assert getattr(op, name) is getattr(anchor_panel, name), name
    assert (op.ERROR_COLOR, op.MAX_ROWS) == ("#d33", 500)


def test_public_hooks_when_panel_built_then_every_documented_name_exists(env):
    """T14i: HOOKS and MEMBERS are the documented API that G12/G15/G16 scripts use."""
    modules, state = env
    state.package = font(tow.glyph("a", {"L": []}))
    panel = shift_panel(modules.panel)()
    missing = [name for name in (*op.HOOKS, *op.MEMBERS) if not hasattr(panel, name)]
    assert missing == [], missing
    for name in (*op.HOOKS, "add_row", "apply", "refresh", "reload", "scan", "spin", "watch", "options"):
        assert callable(getattr(panel, name)), name
    assert panel.slot_error == "" and hasattr(panel, "_connections"), "the private alias keeps working"
    assert set(op.HOOKS).isdisjoint(op.MEMBERS)
    assert (op.NOT_STORED, op.UNDO_HINT) == (history.NOT_STORED, history.UNDO_HINT)
    assert op.NOT_STORED == "FontLab did not store", "G12 scripts match this text"


def test_panel_when_read_back_gap_then_status_starts_with_error_and_not_stored(env, monkeypatch):
    modules, state = env
    state.package = font(tow.glyph("a", {"L": []}))
    panel = shift_panel(modules.panel)()

    def gap(*args, **kwargs):
        raise history.unstored_error(["a/outline"])

    monkeypatch.setattr(ow, "apply_work", gap)
    monkeypatch.setattr(panel, "live_glyphs", lambda: (state.package, []))
    monkeypatch.setattr(ow, "collect", lambda *a, **k: ow.Plan(work=[(None, None, [1])]))
    panel.apply()
    assert panel.status.text.startswith("Error: " + op.NOT_STORED), panel.status.text
    assert op.NOT_STORED in panel.slot_error


# ---------------------------------------------------------------- panel behaviour
def test_panel_when_no_font_or_no_selection_then_explains_and_blocks(env):
    modules, state = env
    panel = shift_panel(modules.panel)()
    assert panel.subtitle.text == "Open a font first." and not panel.apply_button.enabled
    state.package = font(tow.glyph("a", {"L": []}))
    panel.reload_button.clicked.emit()
    assert panel.subtitle.text.startswith("Select glyphs") and not panel.apply_button.enabled


def test_panel_when_planned_then_hooks_preview_and_one_undo_apply(env):
    modules, state = env
    found = square_glyph(state)
    panel = shift_panel(modules.panel)()
    assert panel.hooks[:3] == ["build_controls", "build_extra", "on_reload"] and panel.hooks[-1] == "after_refresh"
    assert panel.scope.items == ["Current master (L)", "All masters (2)"] and panel.chosen_masters() == ["L"]
    assert not panel.compatible.visible, "the master tick is only for structural scripts"
    assert panel.table.texts() == [["A · L", "outline", "0", "10"]]
    assert panel.status.text == "1 shape on 1 layer" and panel.apply_button.enabled
    LOG.clear()
    panel.apply_button.clicked.emit()
    assert fld.history_events() == [
        ("init", "A/L"), ("init", "A"), ("stamp", "A", fld.STAMP),
        ("notify", "Shift Outlines", ["A/L", "A"], ()), ("stamp", "A", fld.STAMP),
    ]  # fmt: skip
    assert found.by_master["L"].shapes[0].contours[0].nodes()[1].x == 110
    assert panel.status.text == "Shifted 1 shape on 1 layer"
    assert panel.last_result == {"pending_note": "", "edits": 1, "layers": 1, "skipped": 0, "pending_updates": ()}


def test_panel_when_planner_raises_then_status_and_apply_off(env):
    modules, state = env
    square_glyph(state)
    panel = shift_panel(modules.panel)()
    panel.by.setValue(99)
    assert panel.status.text == "Too far." and not panel.apply_button.enabled


def test_panel_when_structural_then_all_masters_and_hold_text(env):
    modules, state = env
    square_glyph(state)
    panel = shift_panel(modules.panel, structural=True)()
    assert panel.scope.currentIndex == 1 and panel.compatible.visible and panel.compatible.isChecked()
    assert panel.status.text == "2 shapes on 2 layers"
    panel.scope.setCurrentIndex(0)
    assert panel.table.texts() == [["A · L", "outline", "0", "other masters need it too; choose All masters"]]
    assert panel.status.text == "Nothing to change · 1 glyph held for compatibility"
    assert not panel.apply_button.enabled
    panel.compatible.setChecked(False)
    assert panel.apply_button.enabled


def test_panel_when_glyph_is_auto_base_then_skipped_until_consent_and_reload_clears_it(env):
    modules, state = env
    square_glyph(state)
    state.facts = history.auto_facts([("Aacute", True, ("A",))])
    panel = shift_panel(modules.panel)()
    assert panel.table.texts()[0][:2] == ["A", "glyph"] and panel.table.texts()[0][-1] == "skipped: base of auto Aacute"
    assert panel.status.text == "Nothing to change · 1 glyph skipped" and not panel.apply_button.enabled
    panel.bases.setChecked(True)
    assert panel.apply_button.enabled
    LOG.clear()
    panel.apply()
    assert fld.history_events()[3][2] == ["A/L", "A"], "the auto composite is never notified"
    panel.bases.setChecked(True)
    panel.reload_button.clicked.emit()
    assert not panel.bases.isChecked(), "consent belongs to the glyphs the user saw"


def test_panel_when_glyph_has_auto_layer_then_other_glyphs_written_and_skip_counted(env):
    modules, state = env
    a = tow.glyph("A", {"L": [tow.Shape(tow.SQUARE)]})
    b = tow.glyph("B", {"L": [tow.Shape(tow.SQUARE)]})
    state.package, state.names = font(a, b), ["A", "B"]
    state.facts = history.auto_facts([("B", True, ())])
    panel = shift_panel(modules.panel)()
    assert ["B", "glyph", "", "skipped: has auto layers"] in panel.table.texts()
    panel.apply()
    assert panel.status.text == "Shifted 1 shape on 1 layer · 1 skipped"


def test_panel_when_font_ignores_write_then_read_back_text_without_undo_claim(env):
    modules, state = env
    square_glyph(state)
    panel = shift_panel(modules.panel, keep=False)()
    panel.apply()
    assert panel.status.text == "Error: FontLab did not store 1 change(s): A/L. Check those layers before you save."


def test_panel_when_updates_queued_then_writes_discloses_and_queue_kept(env):
    modules, state = env
    square_glyph(state)
    panel = shift_panel(modules.panel)()
    state.native.pending.append(41)
    panel.refresh()
    assert panel.apply_button.enabled
    LOG.clear()
    panel.apply()
    assert fld.history_events()
    assert panel.last_result["pending_updates"] == (41,) and "8537" in panel.status.text and panel.last_result["pending_note"] in panel.status.text
    assert state.native.pending == [41]


def test_panel_when_font_master_or_glyph_changed_then_apply_refused(env):
    modules, state = env
    square_glyph(state)
    panel = shift_panel(modules.panel)()
    LOG.clear()
    state.package.master = "B"
    panel.apply()
    assert panel.status.text == "Error: Master changed; press Reload selection."
    state.package = font(tow.glyph("b", {"L": []}))
    panel.apply()
    assert panel.status.text == "Error: Glyphs changed; press Reload selection."
    state.package = font(tow.glyph("A", {"L": []}), pid=9)
    panel.apply()
    assert panel.status.text == "Error: The font changed; press Reload selection."
    assert fld.history_events() == []


def test_spin_when_decimals_then_double_box_with_floats_else_int_box(env):
    modules, _ = env
    panel = shift_panel(modules.panel)()
    whole, fine = panel.spin(1, 100, 1), panel.spin(-80, 80, 0, "°", decimals=1)
    assert type(whole) is Spin and whole.calls == [("range", 1, 100)] and isinstance(whole.value, int)
    assert type(fine) is DoubleSpin and fine.calls == [("range", -80.0, 80.0)] and isinstance(fine.value, float)


def test_panel_when_closed_then_signals_disconnected_and_deleted(env, monkeypatch):
    modules, state = env
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    square_glyph(state)
    panel = shift_panel(modules.panel)()
    sys._fontlab_samples["test_shift"] = panel
    signals = [s for s, _ in panel._connections]
    assert len(signals) == 6
    qtd.LOG.clear()
    panel.close_button.clicked.emit()
    assert all(s.slots == [] for s in signals) and panel._connections == []
    assert qtd.LOG == [("qt-close",), ("deleteLater",)]
    assert "test_shift" not in sys._fontlab_samples


# ---------------------------------------------------------------- transform panel
def move_panel(module):
    """A subclass like the Transform script: move every layer by dx."""

    class Move(module.TransformPanel):
        TITLE, KEY, ACTION, DONE, UNIT = "Move", "test_move", "Move", "Moved", "layer item"

        def build_controls(self):
            self.dx = self.spin(-500, 500, 50, decimals=1)

        def preview_matrix(self, layer):
            return (1.0, 0.0, 0.0, 1.0, float(self.dx.value), 0.0), 25.0

        def planner(self):
            matrix = self.preview_matrix(None)[0]
            return lambda glyph, master, layer: ot.transform_changes(layer, matrix, True, "0, 0")

        def editor(self):
            return ot.TransformEditor()

    return Move


def test_transform_panel_when_refreshed_then_preview_of_first_editable_glyph(env):
    modules, state = env
    square_glyph(state)
    panel = move_panel(modules.transform)()
    assert panel.preview.before[0][1] == (100.0, 0.0, True)
    assert panel.preview.after[0][1] == (150.0, 0.0, True) and panel.preview.guide_y == 25.0
    state.facts = history.auto_facts([("A", True, ())])
    panel.reload()
    assert panel.preview.before == [] and panel.preview.after == [], "a refused glyph is not previewed"


def test_transform_panel_when_painted_then_two_paths_and_painter_always_ends(env):
    modules, state = env
    square_glyph(state)
    panel = move_panel(modules.transform)()
    panel.preview.paintEvent(None)
    painter = Painter.log[-1]
    assert panel.preview.paint_error == ""
    assert painter.ended and len(painter.paths) == 2
    assert painter.paths[1].calls[0] == ("moveTo", 50.0, 0.0)
    Painter.fail = True
    panel.preview.paintEvent(None)
    assert Painter.log[-1].ended, "the painter always ends"
    assert panel.status.text.startswith("Preview failed") and "boom paint" in panel.preview.paint_error


def test_transform_panel_when_applied_then_bakes_and_closes_without_callback(env, monkeypatch):
    modules, state = env
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    found = square_glyph(state)
    panel = move_panel(modules.transform)()
    LOG.clear()
    panel.apply()
    assert ("bake", found.by_master["L"].shapes[0].name) in LOG
    assert panel.status.text == "Moved 1 layer item on 1 layer"
    panel.close_button.clicked.emit()
    assert panel.preview.report is None and panel._connections == []


# ---------------------------------------------------------------- source rules
@pytest.mark.parametrize("source", [PANEL, TRANSFORM], ids=["panel", "transform"])
def test_qt_classes_when_parsed_then_every_method_documented_and_typed(source):
    tree = ast.parse(source.read_text(encoding="utf-8"), feature_version=(3, 11))
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        assert ast.get_docstring(cls), cls.name
        methods = [f for f in cls.body if isinstance(f, ast.FunctionDef)]
        assert not [f.name for f in methods if not ast.get_docstring(f)], cls.name
        untyped = [
            f.name for f in methods
            if f.returns is None or any(a.annotation is None for a in f.args.args if a.arg != "self")
        ]  # fmt: skip
        assert not untyped, (cls.name, untyped)


@pytest.mark.parametrize("source", [PANEL, TRANSFORM], ids=["panel", "transform"])
def test_qt_classes_when_parsed_then_never_shadow_native_members(source):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    assigned = {
        n.attr for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
        and isinstance(n.value, ast.Name) and n.value.id == "self"
    }  # fmt: skip
    defined = {f.name for cls in classes for f in cls.body if isinstance(f, ast.FunctionDef)}
    assert not (assigned | defined) & NATIVE_MEMBERS


@pytest.mark.parametrize("source", [PANEL, TRANSFORM], ids=["panel", "transform"])
def test_qt_modules_when_parsed_then_shared_calls_go_through_modules(source):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    shared = ("fontlabapp.core.scripting", "fontlabapp.contours.writer", "fontlabapp.core.history.glyphs",
              "fontlabapp.contours.transform.model", "fontlabapp.masters.layers.writer")  # fmt: skip
    imported = {
        alias.name for n in tree.body if isinstance(n, ast.ImportFrom) and n.module in shared
        for alias in n.names
    }  # fmt: skip
    assert imported == set(), "a copied name would ignore a replaced function"
