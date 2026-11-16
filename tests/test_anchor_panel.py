# this_file: tests/test_anchor_panel.py
"""Shared AnchorPanel base and colour helpers of the Anchors scripts (issue 122, T14c).

The panel runs on a small PythonQt double (widgets with PythonQt-style
properties: ``palette``, ``font``, ``text``, ``value``) and FontLab doubles
that log every native call. The tests prove the preview, the Apply gate, the
one-Undo call shape and the signal cleanup, not native FontLab behaviour.
"""

from module_paths import module_file as _module_file
import ast
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import fontlabapp.anchors.panel.model as ap
import fontlabapp.anchors.writer as aw
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402
import fontlabapp.metrics.panel.model as mp
import fontlabapp.core.scripting as scripting  # noqa: PLR0402

LOG: list = []
SOURCE = _module_file("_anchor_panel")


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


class Color:
    HexArgb = 1

    def __init__(self, value=0):
        self.value = value.value if isinstance(value, Color) else value
        self.alpha = 255

    def lightness(self):
        return self.value if isinstance(self.value, int) else 128

    def setAlpha(self, alpha):
        self.alpha = alpha

    def name(self, *args):
        return self.value if isinstance(self.value, str) else f"#{self.alpha:02x}{self.value:06x}"


class Palette:
    Active, Inactive, Base, Text, WindowText, Link = range(6)

    def __init__(self, colours=None):
        self.colours = dict(colours or {})
        self.set = []

    def color(self, *args):
        return Color(self.colours.get(args, self.colours.get(args[-1:], 100)))

    def setColor(self, group, role, color):
        self.set.append((group, role, color.value))


class Font:
    def pointSizeF(self):
        return 10.0

    def __getattr__(self, name):
        return lambda *args: None


class Widget:
    SIGNALS = frozenset({"clicked", "valueChanged", "currentIndexChanged", "textChanged"})

    def __init__(self, *args, **kwargs):
        self.enabled, self.text, self.palette, self.font = True, "", Palette(), Font()

    def __getattr__(self, name):
        if name in Widget.SIGNALS:
            signal = Signal()
            setattr(self, name, signal)
            return signal
        if name.startswith(("set", "add", "insert", "show", "raise", "resize")):
            return lambda *args, **kwargs: None
        raise AttributeError(name)

    def setEnabled(self, flag):
        self.enabled = bool(flag)

    def setText(self, text):
        self.text = text

    def verticalHeader(self):
        return Widget()

    def horizontalHeader(self):
        return Widget()


class Label(Widget):
    def __init__(self, text="", *args):
        super().__init__()
        self.text = text


class Spin(Widget):
    def setValue(self, value):
        self.value = value
        self.valueChanged.emit(value)


class Item:
    def __init__(self, text=""):
        self.text, self.foreground = text, None

    def setForeground(self, brush):
        self.foreground = brush


class Table(Widget):
    def __init__(self, rows=0, columns=0):
        super().__init__()
        self.rows, self.cells = rows, {}

    def setRowCount(self, rows):
        self.rows, self.cells = rows, {}

    def setItem(self, row, column, item):
        self.cells[row, column] = item

    def texts(self):
        columns = max((c for _, c in self.cells), default=-1) + 1
        return [[self.cells[r, c].text for c in range(columns)] for r in range(self.rows)]


class Dialog(Widget):
    def closeEvent(self, event):
        LOG.append(("qt-close",))

    def close(self):
        self.closeEvent(NS())
        return True

    def deleteLater(self):
        LOG.append(("deleteLater",))


def fake_qt():
    gui = NS(
        QDialog=Dialog, QLabel=Label, QSpinBox=Spin, QComboBox=Widget, QPushButton=Widget,
        QTableWidget=Table, QTableWidgetItem=Item, QVBoxLayout=Widget, QHBoxLayout=Widget,
        QGridLayout=Widget, QPalette=Palette, QColor=Color, QBrush=lambda c: NS(color=lambda: c),
        QAbstractItemView=NS(NoEditTriggers=0, NoSelection=0), QHeaderView=NS(Stretch=0, ResizeToContents=1),
    )
    core = NS(
        Qt=NS(AlignRight=2, ScrollBarAlwaysOff=3),
        QPointF=lambda x, y: NS(x=lambda: x, y=lambda: y),
        QDateTime=NS(currentDateTimeUtc=lambda: "UTC"),
    )
    return NS(QtGui=gui, QtCore=core)


# ---------------------------------------------------------------- FontLab doubles
class Pin:
    def __init__(self, name, x, y):
        self.name, self.anchor, self.appearance = name, True, 0
        self._xy = (x, y)

    @property
    def point(self):
        x, y = self._xy
        return NS(x=lambda: x, y=lambda: y)

    @point.setter
    def point(self, value):
        LOG.append(("move", self.name))
        self._xy = (value.x(), value.y())


class Layer:
    isNull = False

    def __init__(self, glyph, master, pins, auto=False):
        self.name, self.autoLayer, self.anchors = f"{glyph}/{master}", auto, list(pins)

    def checkInitHistoryState(self, flag):
        LOG.append(("init", self.name))


class Glyph:
    isNull = False

    def __init__(self, name, pins, auto=()):
        self.name = name
        self.layers = {m: Layer(name, m, [Pin(*p) for p in pins], m in auto) for m in ("Light", "Bold")}

    def findLayer(self, master):
        return self.layers.get(master)

    def checkInitHistoryState(self, flag):
        LOG.append(("init", self.name))

    @property
    def lastModified(self):
        return None

    @lastModified.setter
    def lastModified(self, value):
        LOG.append(("stamp", self.name))


class Native:
    def __init__(self):
        self.pending = []
        self.flGlyph = NS(updatedFgGlyphs=lambda: tuple(self.pending))
        self.palette = Palette({(Palette.WindowText,): 7})

    def MainWindow(self):
        return NS(palette=self.palette)

    def flItems(self):
        return self

    def notifyChangesApplied(self, title, items):
        LOG.append(("notify", title, [i.name for i in items]))


@pytest.fixture
def env(monkeypatch):
    """Load the real ``_anchor_panel`` over the PythonQt and FontLab doubles."""
    LOG.clear()
    native = Native()
    monkeypatch.setitem(sys.modules, "PythonQt", fake_qt())
    monkeypatch.setitem(sys.modules, "fontlab", native)
    monkeypatch.delitem(sys.modules, "fontlabapp.anchors.panel.ui", raising=False)
    state = NS(package=None, names=[], facts=history.auto_facts(()), native=native)
    monkeypatch.setattr(scripting, "current_package", lambda pid=None: (
        state.package if state.package is not None and pid in (None, state.package.id) else None
    ))
    monkeypatch.setattr(scripting, "names_selected_names", lambda: list(state.names))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: state.facts)
    module = importlib.import_module("fontlabapp.anchors.panel.ui")
    yield module, state
    sys.modules.pop("fontlabapp.anchors.panel.ui", None)


def font(*glyphs, pid=5):
    found = {g.name: g for g in glyphs}
    return NS(id=pid, isNull=False, masters=["Light", "Bold"], master="Light", findName=found.get)


def shift_panel(module):
    """A subclass that moves every anchor right by the spin value."""

    class Shift(module.AnchorPanel):
        TITLE, KEY, ACTION = "Shift Anchors", "test_shift", "Shift"

        def build_controls(self):
            self.by = self.spin(-100, 100, 10)
            self.watch(self.by.valueChanged)

        def chosen_masters(self):
            return [self.current_master]

        def planner(self):
            by = int(self.by.value)
            if by == 99:
                raise ValueError("Too far.")

            def plan(glyph, master, layer):
                changes = []
                for pin in layer.anchors:
                    x, y = aw.raw_point(pin)
                    if by:
                        new = (x + by, y)
                        changes.append(aw.Change(pin.name, f"{x:g}, {y:g}", f"{new[0]:g}, {y:g}", ("set", pin.name, new)))
                return changes

            return plan

    return Shift


# ---------------------------------------------------------------- module helpers
def test_panel_type_when_called_then_anchor_panel_class(env):
    module, _ = env
    assert ap.panel_type() is module.AnchorPanel
    assert ap.muted is mp.muted, "reuse the metrics_panel colour helper"
    assert (ap.ERROR_COLOR, ap.MAX_ROWS) == ("#d33", 500)


def test_ink_when_called_then_brush_of_main_window_text(env):
    _, state = env
    state.native.palette = Palette({(Palette.WindowText,): 7})
    assert ap.ink().color().value == 7


def test_readable_palette_when_text_is_pale_then_window_text_wins_per_group(env):
    widget = Widget()
    widget.palette = Palette({
        (Palette.Active, Palette.Base): 250, (Palette.Active, Palette.Text): 240,
        (Palette.Active, Palette.WindowText): 20,
        (Palette.Inactive, Palette.Base): 250, (Palette.Inactive, Palette.Text): 10,
        (Palette.Inactive, Palette.WindowText): 200,
    })
    ap.readable_palette(widget)
    assert widget.palette.set == [(Palette.Active, Palette.Text, 20), (Palette.Inactive, Palette.Text, 10)]


# ---------------------------------------------------------------- panel behaviour
def test_panel_when_no_font_or_no_selection_then_explains_and_blocks(env):
    module, state = env
    panel = shift_panel(module)()
    assert panel.subtitle.text == "Open a font first." and not panel.apply_button.enabled
    state.package = font(Glyph("a", [("top", 1, 2)]))
    panel.reload_button.clicked.emit()
    assert panel.subtitle.text.startswith("Select glyphs") and not panel.apply_button.enabled


def test_panel_when_planned_then_preview_status_and_one_undo_apply(env):
    module, state = env
    a = Glyph("a", [("top", 1, 2), ("bottom", 3, 4)])
    state.package, state.names = font(a), ["a"]
    panel = shift_panel(module)()
    assert panel.subtitle.text == "1 glyph: a"
    assert panel.table.texts() == [
        ["a · Light", "top", "1, 2", "11, 2"],
        ["a · Light", "bottom", "3, 4", "13, 4"],
    ]
    assert panel.status.text == "2 anchor changes on 1 layer" and panel.apply_button.enabled
    LOG.clear()
    panel.apply_button.clicked.emit()
    assert LOG == [
        ("init", "a/Light"), ("init", "a"), ("move", "top"), ("move", "bottom"),
        ("stamp", "a"), ("notify", "Shift Anchors", ["a/Light", "a"]), ("stamp", "a"),
    ]
    assert panel.status.text == "Changed 2 anchors on 1 layer"
    assert panel.last_result == {"pending_note": "", "anchors": 2, "layers": 1, "skipped": [], "pending_updates": ()}


def test_panel_when_control_changes_then_preview_follows(env):
    module, state = env
    state.package, state.names = font(Glyph("a", [("top", 1, 2)])), ["a"]
    panel = shift_panel(module)()
    panel.by.setValue(0)
    assert panel.table.texts() == [] and not panel.apply_button.enabled
    assert panel.status.text == "0 anchor changes on 0 layers"
    panel.by.setValue(99)
    assert panel.status.text == "Too far." and not panel.apply_button.enabled


def test_panel_when_move_reaches_origin_then_status_is_redo_refusal(env):
    module, state = env
    state.package, state.names = font(Glyph("a", [("top", -10, 0)])), ["a"]
    panel = shift_panel(module)()
    assert panel.status.text == aw.ORIGIN_ERROR and not panel.apply_button.enabled
    LOG.clear()
    panel.apply_button.clicked.emit()
    assert panel.status.text.startswith("Error:") and LOG == []


def test_panel_when_glyph_owns_auto_layer_then_blocked_row_first(env):
    module, state = env
    state.package, state.names = font(Glyph("a", [("top", 1, 2)], auto=("Bold",))), ["a"]
    state.facts = history.auto_facts([("a", True, ())])
    panel = shift_panel(module)()
    rows = panel.table.texts()
    assert rows[0] == ["a", "blocked", "", "has auto layers"]
    assert panel.table.cells[0, 3].foreground.color().value == "#d33"
    assert "a: has auto layers" in panel.status.text and not panel.apply_button.enabled


def test_panel_when_updates_queued_then_writes_discloses_and_queue_kept(env):
    module, state = env
    state.package, state.names = font(Glyph("a", [("top", 1, 2)])), ["a"]
    panel = shift_panel(module)()
    state.native.pending.append(41)
    LOG.clear()
    panel.apply()
    assert LOG and state.native.pending == [41]
    assert panel.last_result["pending_updates"] == (41,) and "8537" in panel.status.text and panel.last_result["pending_note"] in panel.status.text


def test_panel_when_font_master_or_glyph_changed_then_apply_refused(env):
    module, state = env
    state.package, state.names = font(Glyph("a", [("top", 1, 2)])), ["a"]
    panel = shift_panel(module)()
    LOG.clear()
    state.package.master = "Bold"
    with pytest.raises(ValueError, match="Master changed; Reload selection."):
        panel.apply()
    state.package = font(Glyph("b", [("top", 1, 2)]))
    with pytest.raises(ValueError, match="Glyphs changed; Reload selection."):
        panel.apply()
    state.package = font(Glyph("a", [("top", 1, 2)]), pid=9)
    with pytest.raises(ValueError, match="The font changed; press Reload selection."):
        panel.apply()
    assert LOG == []


def test_panel_when_first_scan_raises_then_error_status_and_no_apply(env, monkeypatch):
    module, state = env
    state.package = font(Glyph("a", [("top", 1, 2)]))

    def broken():
        raise OSError("selection unreadable")

    monkeypatch.setattr(scripting, "names_selected_names", broken)
    panel = shift_panel(module)()
    assert panel.status.text == "Error: selection unreadable"
    assert not panel.apply_button.enabled and panel.close_button.enabled


def test_panel_when_many_rows_then_preview_capped_and_edit_complete(env):
    module, state = env
    state.package, state.names = font(Glyph("a", [(f"p{i}", i, 1) for i in range(600)])), ["a"]
    panel = shift_panel(module)()
    assert panel.rows == ap.MAX_ROWS and panel.table.rows == ap.MAX_ROWS
    assert panel.status.text == "600 anchor changes on 1 layer"


def test_panel_when_closed_then_signals_disconnected_and_deleted(env, monkeypatch):
    module, state = env
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    state.package, state.names = font(Glyph("a", [("top", 1, 2)])), ["a"]
    panel = shift_panel(module)()
    sys._fontlab_samples["test_shift"] = panel
    signals = [s for s, _ in panel._connections]
    assert len(signals) == 4
    LOG.clear()
    panel.close_button.clicked.emit()
    assert all(s.slots == [] for s in signals) and panel._connections == []
    assert LOG == [("qt-close",), ("deleteLater",)]
    assert "test_shift" not in sys._fontlab_samples


# ---------------------------------------------------------------- source rules
def test_anchor_panel_class_when_parsed_then_every_method_documented_and_typed():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), feature_version=(3, 11))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    assert cls.name == "AnchorPanel" and ast.get_docstring(cls)
    methods = [f for f in cls.body if isinstance(f, ast.FunctionDef)]
    assert not [f.name for f in methods if not ast.get_docstring(f)]
    untyped = [
        f.name for f in methods
        if f.returns is None or any(a.annotation is None for a in f.args.args if a.arg != "self")
    ]
    assert not untyped, untyped


# Members of QWidget/QDialog that a Python subclass must not shadow:
# PythonQt raises "Slot ... can not be overwritten".
NATIVE_MEMBERS = {
    "metric", "update", "layout", "font", "palette", "parent", "style", "size",
    "pos", "width", "height", "geometry", "show", "hide", "open", "done", "accept",
    "reject", "exec", "repaint", "move", "resize", "rect", "title", "name",
    "windowTitle", "objectName", "children", "focus", "enabled", "visible",
}  # fmt: skip


def test_anchor_panel_class_when_parsed_then_never_shadows_native_members():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    assigned = {
        n.attr for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
        and isinstance(n.value, ast.Name) and n.value.id == "self"
    }
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    defined = {f.name for f in cls.body if isinstance(f, ast.FunctionDef)}
    assert not (assigned | defined) & NATIVE_MEMBERS


def test_anchor_panel_when_parsed_then_shared_calls_go_through_modules():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = {
        alias.name for n in tree.body if isinstance(n, ast.ImportFrom)
        and n.module in ("fontlabapp.core.scripting", "fontlabapp.anchors.writer", "fontlabapp.core.history.glyphs")
        for alias in n.names
    }
    assert imported == set(), "a copied name would ignore a replaced function"
