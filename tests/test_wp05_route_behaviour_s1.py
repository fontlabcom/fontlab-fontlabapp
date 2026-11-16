# this_file: tests/test_wp05_route_behaviour_s1.py
# ruff: noqa: E402, F811 - ported fixtures are re-imported and then shadowed by parameters
# SPDX-License-Identifier: Apache-2.0
"""Six Metrics scripts, tested against owned fakes and the real App helpers.

The fakes replace FontLab layers, the `fontlab` module and Qt widgets. The real
installed App modules (`fly.ap.metrics.panel.model`, `fly.ap.core.history.glyphs`) run over them,
reached as `fly.ap.<module>` like inside FontLab. The tests prove the planning
arithmetic, the refusal paths and the Undo shape (one notified list, no auto
layers). They do not prove native FontLab behaviour.
"""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType

import pytest
from _fgpackage_support import fg_package
from _wp05_scriptmix_shim import (
    app_namespace,
    real_app,  # noqa: F401
)

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "Scripts/Metrics"
NAMES = [
    "Italic Sidebearings",
    "Round Advances",
    "Centre In Advance",
    "Zero-Width Marks",
    "Tabular Width",
    "Scale Advances",
]
CLASS = {
    "Italic Sidebearings": "ItalicSidebearings",
    "Round Advances": "RoundAdvances",
    "Centre In Advance": "CentreInAdvance",
    "Zero-Width Marks": "ZeroWidthMarks",
    "Tabular Width": "TabularWidth",
    "Scale Advances": "ScaleAdvances",
}


# ---------------------------------------------------------------- Qt fakes
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


class Consts:
    """Any attribute is a distinct small integer, like a Qt enum."""

    def __getattr__(self, name):
        return sum(map(ord, name)) % 997


class FakeColor:
    HexArgb = 2

    def __init__(self, source=None):
        self.source = source

    def name(self, *args):
        return "#000000"

    def setAlpha(self, alpha):
        pass


class FakePalette:
    def color(self, *args):
        return FakeColor()

    def setColor(self, *args):
        pass


class FakeFont:
    def pointSizeF(self):
        return 10.0

    def __getattr__(self, name):
        return lambda *a, **k: None


class Widget:
    SIGNALS = frozenset(
        {
            "valueChanged",
            "currentIndexChanged",
            "toggled",
            "clicked",
            "finished",
            "destroyed",
        }
    )

    def __init__(self, *args, **kwargs):
        self._signals = {}
        self._enabled = True
        self.args = args

    @property
    def palette(self):
        return FakePalette()

    @property
    def font(self):
        return FakeFont()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in Widget.SIGNALS:
            return self._signals.setdefault(name, Signal())
        return lambda *a, **k: None

    def setVisible(self, flag):
        self._visible = bool(flag)

    def setEnabled(self, flag):
        self._enabled = bool(flag)

    def isEnabled(self):
        return self._enabled


class Dialog(Widget):
    def close(self):
        event = ModuleType("event")
        self.closeEvent(event)
        return True

    def closeEvent(self, event):
        pass


class Label(Widget):
    def __init__(self, text="", *a):
        super().__init__()
        self._text = text

    @property
    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class Spin(Widget):
    def __init__(self, *a):
        super().__init__()
        self._value = 0
        self.range = (0, 0)

    @property
    def value(self):
        return self._value

    def setRange(self, low, high):
        self.range = (low, high)

    def setValue(self, value):
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)


class Combo(Widget):
    def __init__(self, *a):
        super().__init__()
        self.items = []
        self._index = 0

    @property
    def currentIndex(self):
        return self._index

    def addItem(self, text):
        self.items.append(text)

    def pick(self, index):
        self._index = index
        self.currentIndexChanged.emit(index)


class Check(Widget):
    def __init__(self, *a):
        super().__init__()
        self._checked = False

    def setChecked(self, flag):
        self._checked = bool(flag)

    def isChecked(self):
        return self._checked

    def tick(self, flag):
        self._checked = flag
        self.toggled.emit(flag)


class Button(Widget):
    def __init__(self, text="", *a):
        super().__init__()
        self.label = text

    def press(self):
        self.clicked.emit(False)


class Item:
    def __init__(self, text=""):
        self.text = text
        self.bold = False

    def font(self):
        return FakeFont()

    def setFont(self, font):
        self.bold = True

    def __getattr__(self, name):
        return lambda *a, **k: None


class Table(Widget):
    def __init__(self, rows=0, columns=0):
        super().__init__()
        self.rows = rows
        self.cells = {}

    def horizontalHeader(self):
        return Widget()

    def verticalHeader(self):
        return Widget()

    def setRowCount(self, count):
        self.rows = count
        self.cells = {}

    def setItem(self, row, column, item):
        self.cells[row, column] = item

    def texts(self, row):
        columns = sorted(c for r, c in self.cells if r == row)
        return [self.cells[row, c].text for c in columns]


class Grid(Widget):
    pass


def fake_qt():
    qt = ModuleType("fly.qt")
    gui, core = ModuleType("QtGui"), ModuleType("QtCore")
    gui.QDialog = Dialog
    gui.QLabel = Label
    gui.QSpinBox = Spin
    gui.QDoubleSpinBox = Spin
    gui.QComboBox = Combo
    gui.QCheckBox = Check
    gui.QPushButton = Button
    gui.QTableWidget = Table
    gui.QTableWidgetItem = Item
    gui.QVBoxLayout = gui.QHBoxLayout = gui.QGridLayout = Grid
    gui.QBrush = lambda color: color
    gui.QColor = FakeColor
    for name in ("QPalette", "QAbstractItemView", "QHeaderView"):
        setattr(gui, name, Consts())
    gui.QPainterPath = FakePath
    gui.QTransform = FakeTransform
    core.Qt = Consts()
    core.QDateTime = DateTime
    qt.QtGui, qt.QtCore = gui, core
    return qt


# ---------------------------------------------------------------- geometry fakes
class Box:
    def __init__(self, left, bottom, right, top):
        self._v = (left, bottom, right - left, top - bottom)

    def x(self):
        return self._v[0]

    def y(self):
        return self._v[1]

    def width(self):
        return self._v[2]

    def height(self):
        return self._v[3]


def bounds(points):
    if not points:
        return Box(0, 0, 0, 0)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return Box(min(xs), min(ys), max(xs), max(ys))


class FakePath:
    def __init__(self, points=()):
        self.points = list(points)

    def addPath(self, other):
        self.points.extend(other.points)

    def isEmpty(self):
        return not self.points

    def boundingRect(self):
        return bounds(self.points)


class FakeTransform:
    def __init__(self, m11=1, m12=0, m21=0, m22=1, dx=0, dy=0):
        self.m = (m11, m12, m21, m22, dx, dy)

    def point(self, p):
        m11, m12, m21, m22, dx, dy = self.m
        return (m11 * p[0] + m21 * p[1] + dx, m12 * p[0] + m22 * p[1] + dy)

    def map(self, path):
        return FakePath(self.point(p) for p in path.points)


# ---------------------------------------------------------------- FontLab fakes
LOG: list = []  # Ordered ("init" | "edit" | "notify", detail) events of one test.
STAMP = "UTC-stamp"


class DateTime:
    @staticmethod
    def currentDateTimeUtc():
        return STAMP


class Contour:
    def __init__(self, layer):
        self.layer = layer

    def path(self):
        return FakePath(self.layer.points)


class Shape:
    isComponent = False

    def __init__(self, layer):
        self.layer = layer
        self.transform = FakeTransform()

    def getContours(self):
        return [Contour(self.layer)]

    def clone(self):
        self.layer.clones += 1
        return Shape(self.layer)


class Layer:
    isNull = False
    isMasterLayer = True

    def __init__(self, width, points=(), auto=False):
        self._width = width
        self.points = list(points)
        self.autoLayer = auto
        self.clones = 0
        self.swaps = 0
        self.transforms = []
        self.init_calls = []
        self.edit_log = []
        self.shapes = [Shape(self)]
        self.metricsLeft = self.metricsRight = self.metricsWidth = ""
        self.stubborn_width = False
        self.cache_ok = True

    @property
    def advanceWidth(self):
        return self._width

    @advanceWidth.setter
    def advanceWidth(self, value):
        self.log("width")
        if not self.stubborn_width:
            self._width = value

    def log(self, kind):
        LOG.append(("edit", kind))
        self.edit_log.append(kind)

    def checkInitHistoryState(self, level):
        LOG.append(("init", "layer"))
        self.init_calls.append(level)

    @property
    def boundingBox(self):
        return bounds(self.points)

    def removeShape(self, shape):
        self.swaps += 1
        self.shapes.remove(shape)

    def insertShape(self, index, shape):
        self.swaps += 1
        self.shapes.insert(index, shape)

    def applyTransform(self, transform):
        self.log("move")
        self.transforms.append(transform.m)
        self.points = [transform.point(p) for p in self.points]

    def changed(self):
        self.log("changed")

    def update(self):
        self.log("update")
        return self.cache_ok


class Glyph:
    isNull = False

    def __init__(self, name, layers, codes=None):
        self.name, self.layers_by_master = name, layers
        self.unicodes = list(codes or [])
        self.init_calls = []
        self._stamp = None

    @property
    def lastModified(self):
        return self._stamp

    @lastModified.setter
    def lastModified(self, value):
        LOG.append(("stamp", self.name))
        self._stamp = value

    def checkInitHistoryState(self, level):
        LOG.append(("init", "glyph"))
        self.init_calls.append(level)

    @property
    def layers(self):
        return list(self.layers_by_master.values())

    def findLayer(self, master):
        return self.layers_by_master.get(master)


class Package:
    def __init__(self, glyphs, masters=("Light", "Bold"), ident=7):
        self.id, self.master, self.masters = ident, masters[0], list(masters)
        self.glyphs = {g.name: g for g in glyphs}
        self.fgPackage = fg_package(self.glyphs)
        self.italicAngle_value = -10.0
        self.xHeight_value = 500

    def findName(self, name):
        return self.glyphs.get(name)


def rect(left, right, top=100):
    return [(left, 0), (right, 0), (right, top), (left, top)]


class World:
    """One shared fake state: font, selection, history, closed windows."""

    def __init__(self):
        self.package = None
        self.selection = []
        self.history = []
        self.closed = []
        self.shown = []
        self.font_names = []
        self.updates = []  # Queued native glyph updates (flGlyph.updatedFgGlyphs).


@pytest.fixture
def world(monkeypatch, real_app):
    state = World()
    LOG.clear()
    fly = ModuleType("fly")
    ap = app_namespace()
    scripting = ModuleType("fly.ap.core.scripting")
    completion = ModuleType("fly.ap.core.completion")

    fontlab = ModuleType("fontlab")
    items = ModuleType("items")

    def notify(title, objs):
        LOG.append(("notify", title))
        state.history.append((title, objs))

    items.notifyChangesApplied = notify
    fontlab.flItems = lambda: items
    fontlab.flGlyph = ModuleType("flGlyph")
    fontlab.flGlyph.updatedFgGlyphs = lambda: list(state.updates)
    font_api = ModuleType("FL")
    font_api.fl = ModuleType("fl")
    ap.fontlab, ap.FL = fontlab, font_api

    class FontSeq:
        def __len__(self):
            return len(state.font_names)

        def __getitem__(self, index):
            item = ModuleType("g")
            item.name = state.font_names[index]
            return item

    font_api.fl.font = FontSeq()

    scripting.current_package = lambda expected_id=None: state.package
    scripting.names_selected_names = lambda: list(state.selection)
    scripting.names_font_glyphs = lambda: [(n, []) for n in state.font_names]

    def connect_guarded(dialog, signal, callback):
        def guarded(*args):
            try:
                callback(*args)
            except Exception as error:  # noqa: BLE001
                dialog.status.setText("Error: " + repr(error))

        signal.connect(guarded)
        dialog._connections.append((signal, guarded))

    scripting.connect_guarded = connect_guarded

    def close_script_dialog(dialog, event, key, **kwargs):
        state.closed.append(key)

    scripting.close_script_dialog = close_script_dialog

    def show_script_dialog(dialog_type, key):
        dialog = dialog_type(None)
        state.shown.append((key, dialog))
        return dialog

    scripting.show_script_dialog = show_script_dialog
    completion.install = lambda dialog, key: ("completion", key)
    qt = fake_qt()
    fly.ap, fly.qt = ap, qt
    for name, module in {
        "fly": fly,
        "fly.ap": ap,
        "fly.qt": qt,
        "fly.ap.core.scripting": scripting,
        "fly.ap.core.completion": completion,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    state.app = real_app(
        qt=qt,
        fontlab=fontlab,
        scripting={
            name: getattr(scripting, name)
            for name in (
                "current_package",
                "names_selected_names",
                "names_font_glyphs",
                "connect_guarded",
                "close_script_dialog",
                "show_script_dialog",
            )
        },
        completion=completion.install,
        modules=["history", "metrics_panel"],
    )
    return state


def load(name: str, prefix: str = "s1"):
    path = METRICS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{prefix}_{CLASS[name]}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous, sys.dont_write_bytecode = (
        sys.dont_write_bytecode,
        True,
    )  # no .pyc in Scripts
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
        sys.modules.pop(spec.name, None)
    return module


def open_panel(world, name, glyphs, selection=None, masters=("Light", "Bold")):
    module = load(name)
    world.package = Package(glyphs, masters)
    world.selection = [g.name for g in glyphs] if selection is None else selection
    panel = getattr(module, CLASS[name])(None)
    return module, panel


def two_master_glyph(name="n", light=(100, 10, 90), bold=(120, 12, 108)):
    layers = {
        "Light": Layer(light[0], rect(light[1], light[2])),
        "Bold": Layer(bold[0], rect(bold[1], bold[2])),
    }
    return Glyph(name, layers)


# ---------------------------------------------------------------- files


def test_real_app_helpers_when_scripts_import_them_then_signatures_exist():
    scripting = importlib.import_module("fontlabapp.core.scripting")
    completion = importlib.import_module("fontlabapp.core.completion")
    assert list(inspect.signature(scripting.connect_guarded).parameters)[:3] == [
        "dialog",
        "signal",
        "callback",
    ]
    assert list(inspect.signature(scripting.close_script_dialog).parameters)[:3] == [
        "dialog",
        "event",
        "key",
    ]
    assert list(inspect.signature(scripting.show_script_dialog).parameters) == [
        "dialog_type",
        "key",
    ]
    for helper in ("current_package", "names_selected_names", "names_font_glyphs"):
        assert callable(getattr(scripting, helper)), helper
    assert list(inspect.signature(completion.install).parameters) == ["dialog", "key"]


# ---------------------------------------------------------------- core arithmetic


















# ---------------------------------------------------------------- panels






def edited(world, name, glyphs, configure=None, **kwargs):
    module, panel = open_panel(world, name, glyphs, **kwargs)
    if configure:
        configure(module, panel)
    panel.apply_button.press()
    return module, panel


def check_one_undo(world, title, layers, glyphs):
    """Exact order: init each, edit each, stamp, ONE notify, stamp (history.commit)."""
    assert len(world.history) == 1, "exactly one notification"
    ((name, items),) = world.history
    assert name == title
    assert items == layers + glyphs, "layers then glyphs, one list"
    stamps = [("stamp", g.name) for g in glyphs]
    edits = [("edit", kind) for layer in layers for kind in layer.edit_log]
    expected = (
        [("init", "layer")] * len(layers)
        + [("init", "glyph")] * len(glyphs)
        + edits
        + stamps
        + [("notify", title)]
        + stamps
    )
    assert LOG == expected, LOG
    for item in items:
        assert item.init_calls == [0], "checkInitHistoryState(0) once per object"
    for glyph in glyphs:
        assert glyph.lastModified == STAMP, "one shared UTC stamp"
    for layer in layers:
        assert (layer.clones, layer.swaps) == (0, 0), (
            "shapes move in place, never cloned"
        )




























def auto_composite_world(world):
    """Glyph n (width 101) is the base of the auto glyph ntilde."""
    base = two_master_glyph("n", (101, 10, 90), (101, 10, 90))
    layer = Layer(100, [], auto=True)
    shape = Shape(layer)
    shape.isComponent = True
    shape.shapeData = ModuleType("shapeData")
    shape.shapeData.componentGlyph = "n"
    layer.shapes = [shape]
    plain = two_master_glyph("o", (101, 10, 90), (101, 10, 90))
    world.package = Package([base, Glyph("ntilde", {"Light": layer}), plain])
    world.selection = ["n"]
    world.font_names = ["n", "ntilde", "o"]
    return base, plain


















# ---------------------------------------------------------------- real App names




def auto_pair(base_name, auto_name):
    base = two_master_glyph(base_name, (101, 10, 90), (101, 10, 90))
    layer = Layer(100, [], auto=True)
    shape = Shape(layer)
    shape.isComponent = True
    shape.shapeData = ModuleType("shapeData")
    shape.shapeData.componentGlyph = base_name
    layer.shapes = [shape]
    return base, Glyph(auto_name, {"Light": layer})




















