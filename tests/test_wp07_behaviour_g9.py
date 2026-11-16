# this_file: tests/test_issue122_G9.py
# SPDX-License-Identifier: Apache-2.0
"""Behaviour checks for three Resistenza rewrites; no native acceptance claim."""

from _wp07_routes import behavior_path
from _wp05_scriptmix_shim import app_module_name, app_names_used, app_namespace, check_real_app_names
import ast
import copy
import importlib.util
import itertools
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS
from typing import Any, ClassVar

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "Style Linker": behavior_path(ROOT / "Scripts/Names/Style Linker.py"),
}


def load(title: str) -> Any:
    """Load one menu without starting its UI."""
    spec = importlib.util.spec_from_file_location(title.replace(" ", "_"), behavior_path(PATHS[title]))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


@pytest.mark.parametrize("title", PATHS)
def test_public_contract(title: str) -> None:
    source = PATHS[title].read_text()
    tree = ast.parse(source, feature_version=(3, 11))
    assert source.startswith("# this_file: ")
    doc = ast.get_docstring(tree)
    for text in (
        "What:",
        "How:",
        "Why:",
        "Use:",
        "Benefit:",
        "Giuseppe Salerno",
        "Apache-2.0",
        "https://github.com/rsztype/Scripts",
    ):
        assert text in doc, text
    for text in ("archived", "unresolved", "issue 122", "native acceptance", "draft"):
        assert text not in source.lower(), text
    forbidden = {
        "render",
        "size",
        "layout",
        "update",
        "font",
        "move",
        "statusBar",
        "name",
        "result",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            assert (
                not {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                & forbidden
            )
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            assert node.attr not in forbidden








def instance(style: str, group: str = "", active: bool = True) -> Any:
    class Instance:
        def setSLV(self, bold: bool, italic: bool) -> None:
            self.slv = int(italic) | (int(bold) << 1)

        def autoSGN(self, family: str) -> str:
            return family if self.tsn == "Regular" else family + " " + self.tsn

    value = Instance()
    value.name = style
    value.tsn = style
    value.sgn = group
    value.slv = 0
    value.exportable = active
    value.location = {}
    value.weight, value.width, value.weightValue = "Regular", "Normal", 400
    return value


def test_style_proposals_use_native_style_group_and_whole_words() -> None:
    tool = load("Style Linker")
    values = [
        instance("Regular", "Family"),
        instance("Bold"),
        instance("Bold Italic"),
        instance("ExtraBold"),
        instance("Condensed", "Family Condensed"),
        instance("Condensed Bold Italic"),
        instance("Italic", active=False),
    ]
    assert tool.link_plan(values) == [
        (1, "Family", 2),
        (2, "Family", 3),
        (5, "Family Condensed", 3),
    ]
    assert values[1].sgn == ""


def test_style_fallback_and_duplicate_refusal() -> None:
    tool = load("Style Linker")
    assert tool.link_plan(
        [instance("Bold", "Family Bold"), instance("Bold Italic")]
    ) == [(1, "Family Bold", 1)]
    with pytest.raises(ValueError, match="Duplicate"):
        tool.link_plan([instance("Regular"), instance("Regular")])
    assert tool.link_plan([]) == []


LOG: list[tuple[str, Any]] = []
STAMP = "UTC-stamp"
IDS = itertools.count(1000)

NATIVE_MEMBERS = {
    "metric", "update", "layout", "font", "palette", "parent", "style", "size",
    "pos", "width", "height", "geometry", "show", "hide", "open", "done", "accept",
    "reject", "exec", "repaint", "move", "resize", "rect", "title", "name",
    "windowTitle", "objectName", "children", "focus", "enabled", "visible", "result",
}  # fmt: skip


class Signal:
    def __init__(self) -> None:
        self.slots: list[Any] = []

    def connect(self, slot: Any) -> None:
        self.slots.append(slot)

    def disconnect(self, slot: Any) -> None:
        self.slots.remove(slot)

    def emit(self, *args: Any) -> None:
        for slot in list(self.slots):
            slot(*args)


class Consts:
    """Any attribute is a distinct small integer, like a Qt enum."""

    def __getattr__(self, name: str) -> int:
        return sum(map(ord, name)) % 997


class FakeColor:
    HexArgb = 2

    def __init__(self, *args: Any) -> None:
        pass

    def name(self, *args: Any) -> str:
        return "#000000"

    def setAlpha(self, alpha: int) -> None:
        pass


class FakePalette:
    def color(self, *args: Any) -> FakeColor:
        return FakeColor()

    def setColor(self, *args: Any) -> None:
        pass


class FakeFont:
    def pointSizeF(self) -> float:
        return 10.0

    def __getattr__(self, name: str) -> Any:
        return lambda *a, **k: None


class Widget:
    """Accept layout calls; reject Python attributes that shadow native members."""

    SIGNALS = frozenset(
        {
            "valueChanged",
            "currentIndexChanged",
            "toggled",
            "clicked",
            "finished",
            "itemChanged",
        }
    )
    registry: ClassVar[list[Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        object.__setattr__(self, "_signals", {})
        object.__setattr__(self, "_enabled", True)
        object.__setattr__(self, "args", args)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in NATIVE_MEMBERS:
            raise AttributeError(f"Slot '{name}' can not be overwritten")
        object.__setattr__(self, name, value)

    @property
    def palette(self) -> FakePalette:
        return FakePalette()

    @property
    def font(self) -> FakeFont:
        return FakeFont()

    def __getattr__(self, name: str) -> Any:
        if name == "timer":
            return None
        if name.startswith("__"):
            raise AttributeError(name)
        if name in Widget.SIGNALS:
            return self._signals.setdefault(name, Signal())
        return lambda *a, **k: None

    def setEnabled(self, flag: bool) -> None:
        object.__setattr__(self, "_enabled", bool(flag))

    def isEnabled(self) -> bool:
        return self._enabled


class Dialog(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        Widget.registry.append(self)

    def close(self) -> bool:
        self.closeEvent(NS())
        return True

    def closeEvent(self, event: Any) -> None:
        LOG.append(("close", True))


class Label(Widget):
    def __init__(self, text: str = "", *a: Any) -> None:
        super().__init__()
        object.__setattr__(self, "_text", text)

    @property
    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:
        object.__setattr__(self, "_text", text)


class Combo(Widget):
    def __init__(self, *a: Any) -> None:
        super().__init__()
        object.__setattr__(self, "items", [])
        object.__setattr__(self, "_index", 0)

    @property
    def currentIndex(self) -> int:
        return self._index

    @property
    def currentText(self) -> str:
        return self.items[self._index] if self.items else ""

    @property
    def count(self) -> int:
        return len(self.items)

    def addItem(self, text: str) -> None:
        self.items.append(text)

    def clear(self) -> None:
        self.items.clear()
        object.__setattr__(self, "_index", 0)

    def setCurrentIndex(self, index: int) -> None:
        object.__setattr__(self, "_index", index)

    def pick(self, index: int) -> None:
        object.__setattr__(self, "_index", index)
        self.currentIndexChanged.emit(index)


class Check(Widget):
    def __init__(self, *a: Any) -> None:
        super().__init__()
        object.__setattr__(self, "_checked", False)

    def setChecked(self, flag: bool) -> None:
        object.__setattr__(self, "_checked", bool(flag))

    def isChecked(self) -> bool:
        return self._checked

    def tick(self, flag: bool) -> None:
        object.__setattr__(self, "_checked", flag)
        self.toggled.emit(flag)


class Button(Widget):
    def __init__(self, text: str = "", *a: Any) -> None:
        super().__init__()
        object.__setattr__(self, "label", text)

    def press(self) -> None:
        self.clicked.emit(False)


class Item:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.state = None
        self.item_flags = 0

    def font(self) -> FakeFont:
        return FakeFont()

    def flags(self) -> int:
        return self.item_flags

    def setFlags(self, value: int) -> None:
        self.item_flags = value

    def setCheckState(self, state: Any) -> None:
        self.state = state

    def checkState(self) -> Any:
        return self.state

    def __getattr__(self, name: str) -> Any:
        return lambda *a, **k: None


class Table(Widget):
    def __init__(self, rows: int = 0, columns: int = 0) -> None:
        super().__init__()
        object.__setattr__(self, "cells", {})
        object.__setattr__(self, "row_count", rows)

    def horizontalHeader(self) -> Widget:
        return Widget()

    def verticalHeader(self) -> Widget:
        return Widget()

    def setRowCount(self, count: int) -> None:
        object.__setattr__(self, "row_count", count)
        object.__setattr__(self, "cells", {})

    @property
    def rowCount(self) -> int:
        return self.row_count

    def setItem(self, row: int, column: int, item: Item) -> None:
        self.cells[row, column] = item

    def item(self, row: int, column: int) -> Item | None:
        return self.cells.get((row, column))

    def texts(self, row: int) -> list[str]:
        return [
            self.cells[row, c].text
            for c in sorted(c for r, c in self.cells if r == row)
        ]

    def all_texts(self) -> list[list[str]]:
        return [self.texts(row) for row in range(self.row_count)]


class Box:
    def __init__(self, left: float, bottom: float, right: float, top: float) -> None:
        self._v = (left, bottom, right - left, top - bottom)

    def x(self) -> float:
        return self._v[0]

    def y(self) -> float:
        return self._v[1]

    def width(self) -> float:
        return self._v[2]

    def height(self) -> float:
        return self._v[3]


class FakeTransform:
    def __init__(
        self,
        m11: float = 1,
        m12: float = 0,
        m21: float = 0,
        m22: float = 1,
        dx: float = 0,
        dy: float = 0,
    ):
        self.m = (m11, m12, m21, m22, dx, dy)

    def point(self, x: float, y: float) -> tuple[float, float]:
        m11, m12, m21, m22, dx, dy = self.m
        return m11 * x + m21 * y + dx, m12 * x + m22 * y + dy


class Point:
    """Fake QPointF."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self._x, self._y = float(x), float(y)

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Point) and (self._x, self._y) == (other._x, other._y)


class DateTime:
    @staticmethod
    def currentDateTimeUtc() -> str:
        return STAMP


def fake_qt() -> ModuleType:
    qt = ModuleType("fly.qt")
    gui, core = ModuleType("QtGui"), ModuleType("QtCore")
    gui.QDialog, gui.QLabel, gui.QComboBox, gui.QCheckBox = Dialog, Label, Combo, Check
    gui.QSpinBox = gui.QDoubleSpinBox = Widget
    gui.QPushButton, gui.QTableWidget, gui.QTableWidgetItem = Button, Table, Item
    gui.QVBoxLayout = gui.QHBoxLayout = gui.QGridLayout = Widget
    gui.QBrush = lambda color: color
    gui.QColor = FakeColor
    gui.QTransform = FakeTransform
    for name in ("QPalette", "QAbstractItemView", "QHeaderView"):
        setattr(gui, name, Consts())
    core.Qt = Consts()
    core.QDateTime = DateTime
    core.QPointF = Point
    qt.QtGui, qt.QtCore = gui, core
    return qt


# ---------------------------------------------------------------- FontLab fakes
class Node:
    def __init__(self, x: float, y: float, name: str = "", state: int = 0) -> None:
        self.x, self.y, self.name, self.nodeState = x, y, name, state


class Contour:
    def __init__(self, points: Any, names: Any = (), states: Any = ()) -> None:
        names, states = list(names), list(states)
        self._nodes = [
            Node(
                x,
                y,
                names[i] if i < len(names) else "",
                states[i] if i < len(states) else 0,
            )
            for i, (x, y) in enumerate(points)
        ]

    def nodes(self) -> list[Node]:
        return list(self._nodes)


def square(left: float, bottom: float, right: float, top: float, **kw: Any) -> Contour:
    return Contour([(left, bottom), (right, bottom), (right, top), (left, top)], **kw)


class Shape:
    """Fake flShape. clone() loses what FontLab's clone loses (fl#8516, fl#8538)."""

    def __init__(
        self,
        contours: Any = (),
        component: str | None = None,
        note: str = "",
        name: str = "",
    ) -> None:
        self.id = next(IDS)
        self.isComponent = component is not None
        self.shapeData = NS(
            note=note,
            name=name,
            componentGlyph=component or "",
            builder=NS(builds=component or ""),
        )
        self.contours = list(contours)
        self.active = self.selected = False
        self.drop_contour = False

    def clone(self) -> "Shape":
        copies = [Contour([(n.x, n.y) for n in c.nodes()]) for c in self.contours]
        if self.drop_contour:
            copies = copies[:-1]
        return Shape(copies)


class Pin:
    def __init__(self, name: str, x: float, y: float) -> None:
        self.name, self.point = name, Point(x, y)


class Layer:
    def __init__(
        self,
        name: str,
        glyph: Any = None,
        *,
        shapes: Any = (),
        anchors: Any = (),
        width: float = 500,
        **flags: Any,
    ):
        self.id = next(IDS)
        self.name, self.glyph = name, glyph
        self.shapes = list(shapes)
        self.anchors = list(anchors)
        self._width = width
        self.isMaskLayer = flags.pop("mask", name.startswith("mask."))
        self.isService = flags.pop("service", self.isMaskLayer)
        self.isImgLayer = flags.pop("image", False)
        self.autoLayer = flags.pop("auto", False)
        self.isLocked = flags.pop("locked", False)
        self.metricsLeft = flags.pop("metricsLeft", "")
        self.metricsRight = self.metricsWidth = ""
        self.guidelines: list[Any] = flags.pop("guidelines", [])
        self.note = flags.pop("note", "")
        self.recipe = self.lib = ""
        self.hasTTH = self.hasTTData = False
        self.isNull, self.isValid = False, True
        self.update_ok = True
        self.stubborn = False
        self.keep_components = False  # removeShape ignores components (read-back tests)
        assert not flags, flags

    @property
    def advanceWidth(self) -> float:
        return self._width

    @advanceWidth.setter
    def advanceWidth(self, value: float) -> None:
        LOG.append(("edit", ("width", self.name)))
        if not self.stubborn:
            self._width = value

    @property
    def boundingBox(self) -> Box:
        points = [
            (n.x, n.y)
            for s in self.shapes
            if not s.isComponent
            for c in s.contours
            for n in c.nodes()
        ]
        if not points:
            return Box(0, 0, 0, 0)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        return Box(min(xs), min(ys), max(xs), max(ys))

    def getMaskLayer(self, create: bool) -> Any:
        name = "mask." + self.name
        found = (
            next((x for x in self.glyph.layers if x.name == name), None)
            if self.glyph
            else None
        )
        if found is None and create:
            LOG.append(("edit", ("create mask", name)))
            found = Layer(name, self.glyph)
            self.glyph.layers.append(found)
        return found

    def checkInitHistoryState(self, level: int) -> None:
        LOG.append(("init", self.name))

    def removeShape(self, shape: Shape) -> None:
        LOG.append(("edit", ("removeShape", self.name)))
        if not (self.keep_components and shape.isComponent):
            self.shapes.remove(shape)

    def addShape(self, shape: Shape) -> Shape:
        LOG.append(("edit", ("addShape", self.name)))
        if not self.stubborn:
            self.shapes.append(shape)
        return shape

    def removeAllShapes(self) -> None:
        LOG.append(("edit", ("removeAllShapes", self.name)))
        self.shapes = []

    def applyTransform(self, transform: FakeTransform) -> None:
        LOG.append(("edit", ("move", self.name)))
        for shape in self.shapes:
            for contour in shape.contours:
                for node in contour.nodes():
                    node.x, node.y = transform.point(node.x, node.y)
        for pin in self.anchors:
            pin.point = Point(*transform.point(pin.point.x(), pin.point.y()))

    def changed(self) -> None:
        LOG.append(("edit", ("changed", self.name)))

    def update(self) -> bool:
        return self.update_ok


class Glyph:
    def __init__(
        self, name: str, layers: dict[str, dict[str, Any]] | None = None
    ) -> None:
        self.id = next(IDS)
        self.name = name
        self.isNull = False
        self.layers: list[Layer] = []
        for layer_name, spec in (layers or {}).items():
            self.layers.append(Layer(layer_name, self, **spec))
        self.active = self.layers[0] if self.layers else None
        self._stamp: Any = None
        self.remove_fails = False

    @property
    def lastModified(self) -> Any:
        return self._stamp

    @lastModified.setter
    def lastModified(self, value: Any) -> None:
        LOG.append(("stamp", self.name))
        self._stamp = value

    def layer(self, name: str) -> Layer:
        return next(x for x in self.layers if x.name == name)

    def findLayer(self, name: str) -> Layer | None:
        return next((x for x in self.layers if x.name.lower() == name.lower()), None)

    def removeLayer(self, layer: Layer) -> None:
        LOG.append(("edit", ("removeLayer", layer.name)))
        if self.remove_fails:
            return
        self.layers = [x for x in self.layers if x is not layer]

    def updateActiveLayer(self, assign: bool) -> Layer | None:
        assert assign is False
        return self.active

    def checkInitHistoryState(self, level: int) -> None:
        LOG.append(("init", self.name))


class Package:
    def __init__(
        self,
        glyphs: list[Glyph],
        masters: tuple[str, ...] = ("Light", "Bold"),
        ident: int = 7,
    ) -> None:
        self.id, self.fgId, self.masters, self.master = (
            ident,
            ident + 7000,
            list(masters),
            masters[0],
        )
        self.glyphs = {g.name: g for g in glyphs}
        self.isNull = False

    @property
    def instances(self) -> list[Any]:
        return copy.deepcopy(getattr(self, "_instances", []))

    @instances.setter
    def instances(self, values: list[Any]) -> None:
        self._instances = copy.deepcopy(values)

    def findName(self, name: str) -> Glyph | None:
        return self.glyphs.get(name)

    def records(self) -> tuple:
        return tuple(
            (
                g.name,
                bool(x.autoLayer),
                tuple(s.shapeData.componentGlyph for s in x.shapes if s.isComponent),
            )
            for g in self.glyphs.values()
            for x in g.layers
        )


class World:
    def __init__(self) -> None:
        self.package: Package | None = None
        self.selection: list[str] = []
        self.history: list[tuple[str, list[Any]]] = []
        self.flags: list[
            tuple[Any, ...]
        ] = []  # extra notify arguments (deep history flag)
        self.updates: list[Any] = []
        self.closed: list[str] = []
        self.shown: list[Any] = []

    def notifications(self) -> list[tuple[str, list[Any]]]:
        return list(self.history)

    def use(
        self,
        glyphs: list[Glyph],
        masters: tuple[str, ...] = ("Light", "Bold"),
        selection: list[str] | None = None,
    ) -> Package:
        self.package = Package(glyphs, masters)
        self.selection = [g.name for g in glyphs] if selection is None else selection
        return self.package

    def facts(self) -> Any:
        return self.app["history"].scan_auto_facts(self.package)


@pytest.fixture
def native_world(monkeypatch: pytest.MonkeyPatch, real_app: Any) -> World:
    state = World()
    LOG.clear()
    Widget.registry = []
    fly, ap = ModuleType("fly"), ModuleType("fly.ap")
    fly.__path__, ap.__path__ = [], []
    scripting = ModuleType("fly.ap.core.scripting")
    completion = ModuleType("fly.ap.core.completion")
    fontlab = ModuleType("fontlab")
    items = ModuleType("items")

    def notify(title: str, objects: list[Any], *flags: Any) -> None:
        LOG.append(("notify", title))
        state.history.append((title, list(objects)))
        state.flags.append(flags)

    items.notifyChangesApplied = notify
    fontlab.flItems = lambda: items
    fontlab.flItems.notifyChangesApplied = notify
    fontlab.UpdateAll = lambda: LOG.append(("UpdateAll", True))
    fontlab.flGlyph = NS(updatedFgGlyphs=lambda: list(state.updates))
    ap.fontlab = fontlab
    scripting.current_package = lambda expected_id=None: state.package
    scripting.names_selected_names = lambda: list(state.selection)
    scripting.names_font_glyphs = lambda: [
        (n, []) for n in (state.package.glyphs if state.package else [])
    ]

    def connect_guarded(dialog: Any, signal: Any, callback: Any) -> None:
        def guarded(*args: Any) -> None:
            try:
                callback(*args)
            except Exception as error:  # noqa: BLE001
                dialog.status.setText("Error: " + repr(error))

        signal.connect(guarded)
        dialog._connections.append((signal, guarded))

    scripting.connect_guarded = connect_guarded
    scripting.close_script_dialog = lambda dialog, event, key, **kw: (
        state.closed.append(key)
    )

    def show_script_dialog(dialog_type: Any, key: str) -> Any:
        dialog = dialog_type(None)
        state.shown.append((key, dialog))
        return dialog

    scripting.show_script_dialog = show_script_dialog
    completion.install = lambda dialog, key: NS(stop=lambda: None)
    qt = fake_qt()
    fly.ap, fly.qt = ap, qt
    for name, module in {
        "fly": fly, "fly.ap": ap, "fly.qt": qt,
        "fly.ap.core.scripting": scripting, "fly.ap.core.completion": completion,
    }.items():  # fmt: skip
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
                "show_script_dialog",
            )
        },
        completion=completion.install,
        modules=["guides", "history", "masters", "edit_guards", "metrics_panel"],
    )
    monkeypatch.setattr(
        state.app["guides"], "dependency_values", lambda package: package.records()
    )
    app_namespace(ap, scripting=state.app["scripting"])
    return state


fakes = NS(
    FakeColor=FakeColor,
    Glyph=Glyph,
    LOG=LOG,
    Layer=Layer,
    Package=Package,
    Pin=Pin,
    Point=Point,
    Shape=Shape,
    square=square,
)


@pytest.fixture
def world(native_world: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Use real App writer kernels over strict native/Qt doubles."""
    import importlib

    state = native_world
    for name in (
        "anchor_writer",
        "outline_writer",
        "instance_style_names",
        "glyph_catalog",
        "layer_selection",
        "glyph_creation",
        "glyph_copies",
        "contour_copy",
    ):
        module = importlib.import_module(app_module_name(name))
        monkeypatch.setitem(sys.modules, app_module_name(name).replace("fontlabapp.", "fly.ap.", 1), module)
        state.app[name] = module
        app_namespace(sys.modules["fly"].ap, **{name: module})
    qt = sys.modules["PythonQt"]
    native = sys.modules["fontlab"]

    def new_pin(point: Any) -> Any:
        return NS(name="", point=point, anchor=False, appearance=0)

    native.flPinPoint = new_pin
    monkeypatch.setattr(
        Node,
        "getProperties",
        lambda node: [],
        raising=False,
    )
    monkeypatch.setattr(
        Node,
        "getProperty",
        lambda node, key: getattr(node, "properties", {}).get(key),
        raising=False,
    )
    monkeypatch.setattr(Contour, "name", "", raising=False)
    monkeypatch.setattr(
        Contour,
        "getProperties",
        lambda contour: [],
        raising=False,
    )

    monkeypatch.setattr(
        fakes.Layer,
        "addAnchor",
        lambda layer, pin: layer.anchors.append(pin),
        raising=False,
    )
    monkeypatch.setattr(
        fakes.Layer,
        "removeAnchor",
        lambda layer, pin: layer.anchors.remove(pin),
        raising=False,
    )
    monkeypatch.setattr(fakes.Layer, "hasHints", False, raising=False)
    monkeypatch.setattr(fakes.Shape, "name", "", raising=False)
    monkeypatch.setattr(fakes.Shape, "transform", NS(marker="identity"), raising=False)
    # Match native clone's component identity; its lossy notes/nodes stay lossy.
    original_init = Shape.__init__

    def init_shape(shape: Any, *args: Any, **kwargs: Any) -> None:
        original_init(shape, *args, **kwargs)
        shape.shapeData.referenceCount = 1

    monkeypatch.setattr(Shape, "__init__", init_shape)
    original_clone = fakes.Shape.clone

    def clone(shape: Any) -> Any:
        value = original_clone(shape)
        value.isComponent = shape.isComponent
        value.shapeData.componentGlyph = shape.shapeData.componentGlyph
        value.shapeData.referenceCount = 1
        return value

    monkeypatch.setattr(fakes.Shape, "clone", clone)
    native.MainWindow = lambda: None
    workspace = NS(findPackageId=lambda ident: state.fonts.get(ident))
    native.flWorkspace = NS(instance=lambda: workspace)
    fly = sys.modules["fly"]
    monkeypatch.setattr(fly, "fl", native, raising=False)
    tools = NS(call=lambda *a, **k: None)
    monkeypatch.setattr(fly, "pr", tools, raising=False)
    monkeypatch.setitem(sys.modules, "fontpr", tools)
    state.fonts = {}
    state.qt = qt
    state.native = native
    state.selection_window_ids = []

    def require_window(ident: int) -> None:
        assert ident == state.package.id
        assert ident != state.package.fgId
        state.selection_window_ids.append(ident)

    monkeypatch.setattr(
        state.app["edit_guards"], "require_selection_window", require_window
    )
    monkeypatch.setattr(state.app["edit_guards"], "require_no_editors", lambda **_: None)
    monkeypatch.setattr(
        state.app["layer_selection"],
        "capture",
        lambda deadline: NS(occurrences=[NS(glyph_name=n) for n in state.selection]),
    )
    monkeypatch.setattr(
        state.app["glyph_catalog"],
        "capture",
        lambda: NS(rows=[(n, "", "") for n in state.package.glyphs]),
    )
    return state


def seed(world: Any) -> tuple[Any, Any, Any]:
    """Create an asymmetric two-master font with explicit source metadata."""
    shape = fakes.Shape(
        [fakes.square(0, 0, 50, 80, names=["a", "b", "c", "d"], states=[32, 7, 9, 0])],
        note="keep",
        name="outline",
    )
    glyph = fakes.Glyph(
        "A",
        {
            "Light": {"shapes": [shape], "width": 480},
            "Bold": {
                "shapes": [fakes.Shape([fakes.square(0, 0, 90, 100)])],
                "width": 650,
            },
        },
    )
    package = world.use([glyph])
    package.info = NS(
        familyName="Family", openTypeNamePreferredFamilyName="", unitsPerEm=1000
    )
    package.fgPackage = [NS(name="A", unicodes=[65])]
    package.instances = []
    package._masters = NS(name="masters")
    package.mastersContainer = lambda: package._masters
    package.checkInitHistoryState = lambda index: fakes.LOG.append(("init", "package"))
    glyph.metricsLeft = glyph.metricsRight = glyph.metricsWidth = ""
    world.fonts[package.fgId] = package
    return package, glyph, shape
















def test_style_write_uses_real_history_and_package_value_list(world: Any) -> None:
    tool = load("Style Linker")
    package, _, _ = seed(world)
    package.instances = [
        instance("Regular", "Family"),
        instance("Bold"),
        instance("Italic"),
        instance("ExtraBold"),
    ]
    expected = tool.instance_state(package.instances)
    plan = tool.link_plan(package.instances)
    assert tool.apply_links(package.fgId, expected, plan) == 2
    assert [(i.sgn, i.slv) for i in package.instances] == [
        ("Family", 0),
        ("Family", 2),
        ("Family", 1),
        ("", 0),
    ]
    assert world.history == [("Style Linker", [package, package._masters])] * 2
    assert ("init", "package") in fakes.LOG
    assert (
        tool.apply_links(package.fgId, tool.instance_state(package.instances), plan)
        == 0
    )
    assert len(world.history) == 2


def test_style_write_refuses_stale_switched_and_pending(world: Any) -> None:
    tool = load("Style Linker")
    package, _, _ = seed(world)
    package.instances = [instance("Regular", "Family"), instance("Bold")]
    expected = tool.instance_state(package.instances)
    plan = tool.link_plan(package.instances)
    with pytest.raises(ValueError, match="font changed"):
        tool.apply_links(-1, expected, plan)
    values = package.instances
    values[1].sgn = "changed"
    package.instances = values
    with pytest.raises(ValueError, match="Instances changed"):
        tool.apply_links(package.fgId, expected, plan)
    world.updates.append(1)
    report = []
    tool.apply_links(package.fgId, tool.instance_state(package.instances), plan, report=report)
    assert world.updates == [1] and world.history and "8537" in report[0]


def target_font(world: Any) -> Any:
    package = fakes.Package([], ("Light", "Black"), 100)
    package.fgPackage = []
    package.info = NS(familyName="Destination", unitsPerEm=1000)
    world.fonts[package.fgId] = package
    return package










@pytest.mark.parametrize("title", PATHS)
def test_panels_are_nonmodal_use_owned_signals_and_close(
    world: Any, title: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    package, _, _ = seed(world)
    package.instances = [instance("Regular", "Family"), instance("Bold")]
    # The real common shell is used; only its fake colour enum needs one member.
    monkeypatch.setattr(fakes.FakeColor, "HexArgb", 1, raising=False)
    panel = load(title).panel_type()(None)
    assert panel._connections, "Every panel owns its signals"
    assert not world.history, "Opening a panel must not edit the font"
    panel.close_button.press()
    assert ("close", True) in LOG, "Close uses the common lifecycle"












@pytest.mark.parametrize("title", PATHS)
def test_main_routes_to_shared_owned_registry(
    world: Any, title: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    package, _, _ = seed(world)
    package.instances = [instance("Regular", "Family"), instance("Bold")]
    monkeypatch.setattr(fakes.FakeColor, "HexArgb", 1, raising=False)
    menu = load(title)
    assert menu.main() is world.shown[-1][1]
    assert world.shown[-1][0] == menu.KEY




def test_style_panel_apply_and_empty_font_feedback(
    world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    package, _, _ = seed(world)
    package.instances = [instance("Regular", "Family"), instance("Bold")]
    monkeypatch.setattr(fakes.FakeColor, "HexArgb", 1, raising=False)
    panel = load("Style Linker").panel_type()(None)
    assert panel.table.all_texts()[1] == ["Bold", "Family", "✓", "", "link"]
    panel.apply_button.press()
    assert package.instances[1].slv == 2 and package.instances[1].sgn == "Family"
    assert len(world.history) == 2
    world.package = None
    panel.refresh_button.press()
    assert "Open a font" in panel.status.text
    assert not panel.apply_button.isEnabled()




@pytest.mark.parametrize("title", PATHS)
def test_close_disconnects_all_owned_signals_before_deletion(
    world: Any, title: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run the actual App cleanup, rather than accepting a close-recording fake."""
    import inspect

    package, _, _ = seed(world)
    package.instances = [instance("Regular", "Family"), instance("Bold")]
    monkeypatch.setattr(fakes.FakeColor, "HexArgb", 1, raising=False)
    scripting = world.app["scripting"]
    import importlib

    assert (
        scripting.close_script_dialog
        is importlib.import_module("fontlabapp.core.scripting").close_script_dialog
    )
    assert inspect.isfunction(scripting.close_script_dialog)
    menu = load(title)
    panel = menu.panel_type()(None)
    panel.timer = None
    stopped: list[bool] = []
    panel._completion_lifetime = NS(stop=lambda: stopped.append(True))
    owned = list(panel._connections)
    assert all(slot in signal.slots for signal, slot in owned)
    panel.close_button.press()
    assert stopped == [True]
    assert panel._connections == []
    assert all(slot not in signal.slots for signal, slot in owned)






def test_style_keeps_automatic_base_groups_instead_of_guessing_family(
    world: Any,
) -> None:
    tool = load("Style Linker")
    package, _, _ = seed(world)
    package.instances = [instance("Regular"), instance("Bold")]
    rows = tool.link_rows(package.instances)
    assert "automatic" in rows[1][-1]
    assert tool.link_plan(package.instances) == []
    package.info.familyName = "Different from instance tfn"
    assert (
        tool.apply_links(package.fgId, tool.instance_state(package.instances), []) == 0
    )
    assert not world.history
























def test_style_empty_tsn_is_visible_and_per_instance_family_is_retained(
    world: Any,
) -> None:
    package, _, _ = seed(world)
    base, bold = instance("Regular", "Separate Family"), instance("Bold")
    base.tfn = bold.tfn = "Per-instance family"
    unnamed = instance("BoldItalic")
    unnamed.tsn = ""
    package.instances = [base, bold, unnamed]
    tool = load("Style Linker")
    rows = tool.link_rows(package.instances)
    assert "missing typographic style" in rows[2][-1]
    assert (
        tool.apply_links(
            package.fgId,
            tool.instance_state(package.instances),
            tool.link_plan(package.instances),
        )
        == 1
    )
    assert [i.tfn for i in package.instances[:2]] == ["Per-instance family"] * 2
    assert [i.sgn for i in package.instances[:2]] == ["Separate Family"] * 2


def test_style_notifies_before_and_after_instance_assignment(
    world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    package, _, _ = seed(world)
    package.instances = [instance("Regular", "Family"), instance("Bold")]
    states = []

    def notify(title: str, objects: list[Any]) -> None:
        assert objects == [package, package.mastersContainer()]
        states.append([(i.sgn, i.slv) for i in package.instances])

    monkeypatch.setattr(world.native.flItems, "notifyChangesApplied", notify)
    tool = load("Style Linker")
    tool.apply_links(
        package.fgId,
        tool.instance_state(package.instances),
        tool.link_plan(package.instances),
    )
    assert states == [[("Family", 0), ("", 0)], [("Family", 0), ("Family", 2)]]
    assert ("UpdateAll", True) in LOG


def test_style_failure_retains_original_values_and_finishes_notifications(
    world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    package, _, _ = seed(world)
    package.instances = [instance("Regular", "Family"), instance("Bold")]
    tool = load("Style Linker")
    before = tool.instance_state(package.instances)
    proposals = tool.link_plan(package.instances)

    def fail(value: Any, bold: bool, italic: bool) -> None:
        raise RuntimeError("instance setter failed")

    monkeypatch.setattr(type(package.instances[1]), "setSLV", fail)
    with pytest.raises(
        RuntimeError,
        match="instance setter failed.*Native changes may remain; use Edit > Undo",
    ):
        tool.apply_links(package.fgId, before, proposals)
    assert tool.instance_state(package.instances) == before
    assert (
        world.history == [("Style Linker", [package, package.mastersContainer()])] * 2
    )





from _wp05_scriptmix_shim import app_sources, canonical_app_bindings, real_app  # noqa: E402,F401,I001
