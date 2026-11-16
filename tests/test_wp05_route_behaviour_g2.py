# this_file: tests/test_wp05_route_behaviour_g2.py
# SPDX-License-Identifier: Apache-2.0
"""Independent G2 host doubles and real installed-App API checks.

Native doubles are local to this file. Raw glyph insertion is rejected.
Host-free checks do not establish FontLab Undo/Redo or saved-font behaviour.
"""

import inspect
import itertools
import math
import runpy
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS
from typing import Any, ClassVar

import pytest
from _figure_settings_support import settings_factory
from _message_box_support import message_box_type
from _wp05_app_routes import route_path
from _wp05_scriptmix_shim import real_app  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    "Cleanup/Start From Scratch.py",
    "Components/Decompose Serif Components.py",
    "Components/Make Lower Unicase.py",
    "Components/Set Default Figures.py",
    "Contours/Retract Handles.py",
    "Contours/Simplify Selected Nodes.py",
    "Cleanup/Delete Stickers.py",
]
ISOLATED = ("fly", "fontlabapp", "echopy", "fontpr")
IDS = itertools.count(1)
SMOOTH = 0x30
Spec = tuple
SIGNALS = {
    "finished",
    "destroyed",
    "clicked",
    "textChanged",
    "toggled",
    "valueChanged",
    "currentIndexChanged",
    "itemChanged",
    "timeout",
}


def patch_app(
    monkeypatch: pytest.MonkeyPatch, module: Any, name: str, double: Any
) -> None:
    """Reject App doubles whose calling convention differs from the real App."""

    def parameters(function: Any) -> list[tuple]:
        return [
            (p.name, p.kind, p.default)
            for p in inspect.signature(function).parameters.values()
        ]

    assert parameters(getattr(module, name)) == parameters(double), (
        f"App signature mismatch: {module.__name__}.{name}"
    )
    monkeypatch.setattr(module, name, double)


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


class Widget:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.enabled = True
        self.text = ""

    def __getattr__(self, name: str) -> Any:
        if name in SIGNALS:
            signal = Signal()
            setattr(self, name, signal)
            return signal
        if name.startswith(
            ("set", "add", "insert", "block", "show", "raise", "resize")
        ):
            return lambda *args, **kwargs: None
        raise AttributeError(name)

    def setEnabled(self, flag: bool) -> None:
        self.enabled = flag

    def setText(self, text: str) -> None:
        self.text = text

    def verticalHeader(self) -> "Widget":
        return Widget()

    def horizontalHeader(self) -> "Widget":
        return Widget()


class Font:
    def pointSizeF(self) -> float:
        return 10.0

    def __getattr__(self, name: str) -> Any:
        return lambda *args: None


class Color:
    HexArgb = 1

    def __init__(self, value: Any = 0) -> None:
        self.value = value.value if isinstance(value, Color) else value

    def lightness(self) -> int:
        return 128 if not isinstance(self.value, int) else self.value

    def name(self, fmt: Any = None) -> str:
        return "#808080" if not isinstance(self.value, str) else self.value

    def setAlpha(self, value: int) -> None:
        pass


class Palette:
    Active, Inactive, Base, Text, WindowText, Link = range(6)

    def color(self, *args: Any) -> Color:
        return Color(100)

    def setColor(self, *args: Any) -> None:
        pass


class Label(Widget):
    def __init__(self, text: str = "", *args: Any) -> None:
        super().__init__()
        self.text = text
        self.font = Font()


class LineEdit(Widget):
    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.text = text

    def setText(self, text: str) -> None:
        self.text = text
        self.textChanged.emit(text)


class PlainText(Widget):
    def __init__(self) -> None:
        super().__init__()
        self.plain = ""

    def setPlainText(self, text: str) -> None:
        self.plain = text
        self.textChanged.emit()

    def toPlainText(self) -> str:
        return self.plain


class CheckBox(Widget):
    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.checked = False

    def setChecked(self, flag: bool) -> None:
        self.checked = flag
        self.toggled.emit(flag)

    def isChecked(self) -> bool:
        return self.checked


class Combo(Widget):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[str] = []
        self.currentIndex = -1

    @property
    def currentText(self) -> str:
        return self.items[self.currentIndex] if self.items else ""

    def addItem(self, text: str) -> None:
        self.items.append(text)
        self.currentIndex = max(self.currentIndex, 0)

    def addItems(self, texts: list[str]) -> None:
        for text in texts:
            self.addItem(text)

    def clear(self) -> None:
        self.items, self.currentIndex = [], -1

    def setItemText(self, index: int, text: str) -> None:
        self.items[index] = text

    def setCurrentIndex(self, index: int) -> None:
        self.currentIndex = index
        self.currentIndexChanged.emit(index)


class Button(Widget):
    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.label = text


class Item:
    def __init__(self, text: str = "") -> None:
        self._text, self._data, self._state = text, None, 0
        self.foreground = None

    def setForeground(self, brush: Any) -> None:
        self.foreground = brush

    def text(self) -> str:
        return self._text

    def setData(self, role: int, value: Any) -> None:
        self._data = value

    def data(self, role: int) -> Any:
        return self._data

    def setCheckState(self, state: int) -> None:
        self._state = state

    def checkState(self) -> int:
        return self._state

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


class ListWidget(Widget):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[Item] = []

    @property
    def count(self) -> int:
        return len(self.items)

    def item(self, row: int) -> Item:
        return self.items[row]

    def addItem(self, item: Item) -> None:
        self.items.append(item)

    def clear(self) -> None:
        self.items = []


class Table(Widget):
    def __init__(self, rows: int = 0, columns: int = 0) -> None:
        super().__init__()
        self.cells: dict[tuple[int, int], Item] = {}
        self.rows = rows

    def setRowCount(self, rows: int) -> None:
        self.rows = rows
        self.cells = {k: v for k, v in self.cells.items() if k[0] < rows}

    def setItem(self, row: int, column: int, item: Item) -> None:
        self.cells[(row, column)] = item

    def row_texts(self) -> list[list[str]]:
        columns = max((c for _, c in self.cells), default=-1) + 1
        return [
            [self.cells[(r, c)].text() for c in range(columns)]
            for r in range(self.rows)
        ]

    def colors(self) -> list[Any]:
        """Foreground colour value of the last cell of each row."""
        columns = max((c for _, c in self.cells), default=-1) + 1
        return [
            self.cells[(r, columns - 1)].foreground.color().value
            for r in range(self.rows)
        ]


class Timer(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__()
        self.starts, self.active = 0, False

    def start(self, *args: Any) -> None:
        self.starts += 1
        self.active = True

    def stop(self) -> None:
        self.active = False


class Dialog(Widget):
    registry: ClassVar[list[Any]] = []

    def __init__(self, parent: Any = None) -> None:
        super().__init__()
        self.deleted = self.shown = False
        self.palette = Palette()
        self.core_closed = 0
        Dialog.registry.append(self)

    def saveGeometry(self):
        return b"owned"

    def restoreGeometry(self, value):
        self.restored_geometry = value
        return value == b"owned"

    def closeEvent(self, event: Any) -> None:
        self.core_closed += 1

    def close(self) -> bool:
        self.closeEvent(object())
        return True

    def show(self) -> None:
        self.shown = True

    def deleteLater(self) -> None:
        self.deleted = True


class Transform:
    """QTransform(m11, m12, m21, m22, dx, dy)."""

    def __init__(
        self,
        m11: float = 1.0,
        m12: float = 0.0,
        m21: float = 0.0,
        m22: float = 1.0,
        dx: float = 0.0,
        dy: float = 0.0,
    ) -> None:
        self.values = (m11, m12, m21, m22, dx, dy)
        self.affine = True  # False: a perspective transform

    def m11(self) -> float:
        return self.values[0]

    def m12(self) -> float:
        return self.values[1]

    def m21(self) -> float:
        return self.values[2]

    def m22(self) -> float:
        return self.values[3]

    def dx(self) -> float:
        return self.values[4]

    def dy(self) -> float:
        return self.values[5]

    def isAffine(self) -> bool:
        return self.affine


def make_qt() -> ModuleType:
    qt = ModuleType("PythonQt")
    core = NS(
        QPointF=lambda x, y: NS(x=lambda: x, y=lambda: y),
        QDateTime=NS(currentDateTimeUtc=lambda: "UTC stamp"),
        QTimer=Timer,
        Qt=NS(
            Horizontal=1,
            AlignRight=2,
            ScrollBarAlwaysOff=3,
            ItemIsEnabled=4,
            ItemIsUserCheckable=8,
            UserRole=32,
            Checked=2,
            Unchecked=0,
            CaseInsensitive=0,
            MatchContains=1,
        ),
    )
    gui = NS(
        QDialog=Dialog,
        QLabel=Label,
        QLineEdit=LineEdit,
        QPlainTextEdit=PlainText,
        QCheckBox=CheckBox,
        QComboBox=Combo,
        QPushButton=Button,
        QTableWidget=Table,
        QTableWidgetItem=Item,
        QListWidget=ListWidget,
        QListWidgetItem=Item,
        QVBoxLayout=Widget,
        QHBoxLayout=Widget,
        QGridLayout=Widget,
        QCompleter=Widget,
        QFontDatabase=NS(FixedFont=0, systemFont=lambda kind: Font()),
        QPalette=Palette,
        QColor=Color,
        QBrush=lambda color: NS(color=lambda: color),
        QTransform=Transform,
        QAbstractItemView=NS(NoEditTriggers=0, NoSelection=0),
        QHeaderView=NS(Stretch=0, ResizeToContents=1),
    )
    core.QSettings = settings_factory()
    qt.QtCore, qt.QtGui = core, gui
    return qt


class Node:
    def __init__(self, x: float, y: float, state: int) -> None:
        self.x, self.y, self.nodeState = x, y, state


class ComponentContour:
    def __init__(self, nodes: list[Node]) -> None:
        self._nodes = nodes

    def nodes(self) -> list[Node]:
        return list(self._nodes)


class Builder:
    def __init__(self, world: "World") -> None:
        self.world = world

    def update(self) -> bool:
        self.world.events.append(("builder-update",))
        return self.world.builder_ok


class ShapeData:
    def __init__(self, world: "World", base: str, note: str) -> None:
        self.world, self._base, self._note = world, base, note
        self.id = next(IDS)
        self.referenceCount, self.componentLayer = 1, ""
        self.builder = Builder(world)

    @property
    def componentGlyph(self) -> str:
        return self._base

    @componentGlyph.setter
    def componentGlyph(self, name: str) -> None:
        if self.world.fail_write:
            raise RuntimeError("boom write")
        if not self.world.ignore_writes:
            self._base = name

    @property
    def note(self) -> str:
        return self._note

    @note.setter
    def note(self, text: str) -> None:
        self._note = text


class Shape:
    def __init__(
        self,
        world: "World",
        base: str | None = None,
        dx: float = 0.0,
        dy: float = 0.0,
        contours: list[list[tuple[float, float, int]]] | None = None,
        note: str = "",
        locked: bool = False,
        matrix: tuple[float, float, float, float] = (1, 0, 0, 1),
    ) -> None:
        self.world, self.id, self.owner = world, next(IDS), None
        self.isComponent = base is not None
        self.shapeData = ShapeData(world, base or "", note)
        self._transform = Transform(*matrix, dx, dy)
        self.contours = [
            ComponentContour([Node(*n) for n in c]) for c in (contours or [])
        ]
        self._locked = locked
        self.marker = f"shape-{self.id}"
        self.shapeData.marker = f"data-{self.id}"
        self.shapeData.builder.marker = f"builder-{self.id}"
        self.name = ""  # element name; ejectTo copies drop it
        self.excluded, self.opacity, self.selected = False, 1.0, False
        self.other_composite = False  # a composite shape that is not a component

    def clone(self) -> "Shape":
        return Shape(
            self.world,
            self.shapeData.componentGlyph,
            self.transform.dx(),
            self.transform.dy(),
            locked=self._locked,
        )

    @property
    def isComposite(self) -> bool:
        return self.isComponent or self.other_composite

    @property
    def transform(self) -> Transform:
        return self._transform

    @transform.setter
    def transform(self, value: Transform) -> None:
        if self.world.fail_write:
            raise RuntimeError("boom write")
        if not self.world.ignore_writes:
            self._transform = value

    @property
    def contentLocked(self) -> bool:
        return self._locked

    @contentLocked.setter
    def contentLocked(self, flag: bool) -> None:
        if self.world.fail_write:
            raise RuntimeError("boom write")
        if not self.world.ignore_writes:
            self._locked = flag

    def changed(self) -> None:
        pass

    @property
    def includesList(self) -> list["Shape"]:
        return self.world.layer(self.shapeData.componentGlyph, self.owner.master).shapes

    def ejectTo(self) -> list["Shape"]:
        """Copies with the transform applied; like FontLab, they lose raw flags and notes."""
        dx, dy = self._transform.dx(), self._transform.dy()
        copies = []
        for part in self.includesList:
            if part.isComponent:
                copy = Shape(
                    self.world,
                    part.shapeData.componentGlyph,
                    part.transform.dx() + dx,
                    part.transform.dy() + dy,
                )
            else:
                copy = Shape(
                    self.world,
                    contours=[
                        [(n.x + dx, n.y + dy, n.nodeState & ~SMOOTH) for n in c.nodes()]
                        for c in part.contours
                    ],
                )
                copy._locked = part._locked
            copies.append(copy)
        return copies


class Layer:
    isNull = False

    def __init__(
        self, world: "World", glyph: str, master: str, advance: float, auto: bool
    ) -> None:
        self.world, self.glyph, self.master, self.name = world, glyph, master, master
        self.marker = f"{glyph}/{master}"
        self.advanceWidth, self.autoLayer = advance, auto
        self.anchors: list[Any] = []
        self._shapes: list[Shape] = []

    @property
    def shapes(self) -> list[Shape]:
        return list(self._shapes)

    def add(self, shape: Shape) -> Shape:
        shape.owner = self
        self._shapes.append(shape)
        return shape

    def removeShape(self, shape: Shape) -> None:
        if self.world.fail_write:
            raise RuntimeError("boom write")
        self._shapes = [s for s in self._shapes if s.id != shape.id]

    def insertShape(self, index: int, shape: Shape) -> Shape:
        shape.owner = self
        self._shapes.insert(index, shape)
        return shape

    def changed(self) -> None:
        self.world.events.append(("changed", self.marker))

    def update(self) -> bool:
        return self.world.update_ok

    def checkInitHistoryState(self, index: int) -> None:
        self.world.events.append(("init", self.marker))


class Glyph:
    isNull = False

    def __init__(self, world: "World", name: str) -> None:
        self.world, self.name = world, name
        self.by_master: dict[str, Layer] = {}
        self._modified = "before"

    @property
    def layers(self) -> list[Layer]:
        return list(self.by_master.values())

    def findLayer(self, master: str) -> Layer | None:
        return self.by_master.get(master)

    def findLayerCreate(self, master: str) -> Layer:
        layer = Layer(self.world, self.name, master, 0, False)
        self.by_master[master] = layer
        self.world.events.append(("layer-created", f"{self.name}/{master}"))
        return layer

    def checkInitHistoryState(self, index: int) -> None:
        self.world.events.append(("init", self.name))

    @property
    def lastModified(self) -> Any:
        return self._modified

    @lastModified.setter
    def lastModified(self, value: Any) -> None:
        self._modified = value
        self.world.events.append(("stamp", self.name))


class World:
    """One owned font: masters, glyphs, selection, history log, data tools."""

    def __init__(self, masters: tuple[str, ...] = ("Light", "Bold")) -> None:
        self.masters, self.master = list(masters), masters[0]
        self.glyphs: dict[str, Glyph] = {}
        self.selected: list[str] = []
        self.events: list[Any] = []
        self.calls: list[Any] = []
        self.ignore_writes = self.fail_write = self.fail_notify = False
        self.no_font = False
        self.builder_ok = self.update_ok = True
        self.pending: list[int] = []  # flGlyph.updatedFgGlyphs()
        self.stored: dict[str, Any] = {}  # get_glyph answers that replace the default
        self.build_errors: dict[tuple[str, str], Any] = {}
        self.package = NS(
            id=7,
            fgId=70,
            isNull=False,
            masters=self.masters,
            master=self.master,
            findName=lambda name: self.glyphs.get(name),
        )

    def glyph(
        self,
        name: str,
        shapes: dict[str, list[Spec]] | None = None,
        anchors: dict[str, list[tuple]] | None = None,
        auto: tuple[str, ...] = (),
        select: bool = True,
        advances: dict[str, float] | None = None,
        masters: tuple[str, ...] | None = None,
    ) -> Glyph:
        glyph = self.glyphs.setdefault(name, Glyph(self, name))
        for master in masters or self.masters:
            layer = Layer(
                self, name, master, (advances or {}).get(master, 500), master in auto
            )
            for pin in (anchors or {}).get(master, []):
                layer.anchors.append(
                    NS(
                        name=pin[0],
                        point=NS(x=lambda v=pin[1]: v, y=lambda v=pin[2]: v),
                    )
                )
            for spec in (shapes or {}).get(master, []):
                layer.add(self.make(spec))
            glyph.by_master[master] = layer
        if select:
            self.selected.append(name)
        return glyph

    def make(self, spec: Spec) -> Shape:
        if spec[0] == "c":
            _, base, dx, dy, *rest = spec
            options = rest[0] if rest else {}
            return Shape(self, base, dx, dy, **options)
        _, contours, *rest = spec
        return Shape(self, contours=contours, **(rest[0] if rest else {}))

    def layer(self, glyph: str, master: str | None = None) -> Layer:
        return self.glyphs[glyph].by_master[master or self.master]

    def notifications(self) -> list[Any]:
        return [e for e in self.events if e[0] == "notify"]

    def history(self) -> list[Any]:
        """The history-relevant events only: init, stamp, notify (markers)."""
        return [
            e[:3] if e[0] == "notify" else e
            for e in self.events
            if e[0] in {"init", "stamp", "notify"}
        ]

    # -- data tools (fontpr)
    def call(self, tool: str, **args: Any) -> Any:
        self.calls.append((tool, args))
        if tool == "set_glyph":
            assert args["create"] is True and args["font_id"] == self.package.fgId
            name, data = args["glyph_name"], args["glyph_data"]
            assert name not in self.glyphs, (
                "set_glyph must never replace an existing glyph"
            )
            glyph = add_glyph(self, name)
            self.codes[name] = data.get("unicodes", [])
            for record in data["layers"]:
                layer = glyph.findLayer(record["name"])
                layer.advanceWidth = record["advanceWidth"]
                for element in record.get("elements", []):
                    shape = Shape(self, element["component"]["glyphName"])
                    layer.add(shape)
            if hasattr(self, "after_create"):
                self.after_create(glyph)
            self.events.append(("add-glyph", name))
            return {"status": "ok", "created": True}
        if tool == "get_glyph":
            return self.stored.get(args["glyph_name"]) or self.vfj(args["glyph_name"])
        if tool == "build_glyph":
            return self.build(args)
        raise AssertionError(tool)

    def vfj(self, name: str) -> dict:
        layers = []
        for master, layer in self.glyphs[name].by_master.items():
            elements = []
            for shape in layer.shapes:
                element: dict[str, Any] = (
                    {"component": {"glyphName": shape.shapeData.componentGlyph}}
                    if shape.isComponent
                    else {"elementData": {"contours": []}}
                )
                if shape._locked:
                    element["locked"] = True
                elements.append(element)
            layers.append({"name": master, "elements": elements})
        return {"name": name, "layers": layers}

    def build(self, args: dict) -> Any:
        key = (args["glyph_name"], args["layer_name"])
        if key in self.build_errors and not args["dry_run"]:
            error = self.build_errors[key]
            if isinstance(error, Exception):
                raise error
            return error
        glyph = self.glyphs.get(args["glyph_name"])
        if glyph is not None and glyph.findLayer(args["layer_name"]) is None:
            raise RuntimeError("Target layer not found.")
        parts = [
            p.split("@")[0] for p in args["recipe"][1:].replace("&", "+").split("+")
        ]
        resolved = [{"glyph_name": p} for p in parts]
        if args["dry_run"]:
            return {"status": "validated", "resolved_components": resolved}
        created = glyph is None
        if created:
            glyph = self.glyph(
                args["glyph_name"], masters=(args["layer_name"],), select=False
            )
        self.events.append(("build", args["glyph_name"], args["layer_name"]))
        return {"status": "ok", "created": created, "resolved_components": resolved}


class OutlineNode:
    def __init__(self, contour: "OutlineContour", x: float, y: float, on: bool) -> None:
        self.contour, self._x, self._y, self.on = contour, float(x), float(y), bool(on)

    def _write(self, name: str, value: float) -> None:
        world = self.contour.world
        if world.fail_write:
            raise RuntimeError("boom write")
        if world.round_writes:
            value = math.floor(float(value) + 0.5)
        if not world.ignore_writes:
            setattr(self, name, float(value))

    @property
    def x(self) -> float:
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        self._write("_x", value)

    @property
    def y(self) -> float:
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        self._write("_y", value)

    def isOn(self) -> bool:
        return self.on

    def convertToLine(self) -> bool:
        return self.contour.convert_to_line(self)


class OutlineContour:
    def __init__(
        self, world: "World", points: Spec, closed: bool = True, tt: bool = False
    ) -> None:
        self.world, self.closed, self.isTT = world, closed, tt
        self._nodes = [OutlineNode(self, x, y, on) for x, y, on in points]

    def nodes(self) -> list[OutlineNode]:
        return list(self._nodes)

    @property
    def nodesCount(self) -> int:
        return len(self._nodes)

    def xy(self) -> list[tuple[float, float, bool]]:
        return [(n.x, n.y, n.on) for n in self._nodes]

    def _guard(self) -> bool:
        if self.world.fail_write:
            raise RuntimeError("boom write")
        return not self.world.ignore_writes

    def reverse(self) -> None:
        if self._guard():
            self._nodes = self._nodes[:1] + self._nodes[1:][::-1]

    def setStartPoint(self, index: int) -> bool:
        if not self.closed or not 0 < index < len(self._nodes):
            return False
        if not self._nodes[index].on:
            return False
        if self._guard():
            self._nodes = self._nodes[index:] + self._nodes[:index]
        return True

    def insertOutlineNodeTo(self, t: float) -> OutlineNode:
        """Split segment int(t) at t - int(t), as FontLab does (de Casteljau)."""
        self._guard()
        k, u = int(t), t - int(t)
        on = [i for i, n in enumerate(self._nodes) if n.on]
        start, end = on[k], on[(k + 1) % len(on)]
        span = (end - start) % len(self._nodes) or len(self._nodes)
        between = [(start + j) % len(self._nodes) for j in range(1, span)]
        p = [(self._nodes[i].x, self._nodes[i].y) for i in (start, *between, end)]

        def lerp(a: tuple, b: tuple) -> tuple:
            return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)

        assert len(p) == 4, "the fake splits cubic curves only"
        p01, p12, p23 = lerp(p[0], p[1]), lerp(p[1], p[2]), lerp(p[2], p[3])
        p012, p123 = lerp(p01, p12), lerp(p12, p23)
        mid = lerp(p012, p123)
        fresh = [
            OutlineNode(self, *p01, False),
            OutlineNode(self, *p012, False),
            OutlineNode(self, *mid, True),
            OutlineNode(self, *p123, False),
            OutlineNode(self, *p23, False),
        ]
        if self.world.ignore_writes:
            return fresh[2]
        first = between[0]
        assert between == [first, first + 1], "the fake needs an unwrapped curve"
        self._nodes[first : first + 2] = fresh
        return fresh[2]

    def convert_to_line(self, node: OutlineNode) -> bool:
        if not self._guard():
            return True
        index = self._nodes.index(node)
        count = len(self._nodes)
        prev = next(
            (index - j) % count
            for j in range(1, count)
            if self._nodes[(index - j) % count].on
        )
        doomed = {(prev + j) % count for j in range(1, (index - prev) % count)}
        self._nodes = [n for i, n in enumerate(self._nodes) if i not in doomed]
        self.world.events.append(("to-line", len(doomed)))
        return True


@pytest.fixture
def components_world(monkeypatch: pytest.MonkeyPatch) -> World:
    """Install fake native modules; reset fly, fontlabapp and echopy around the test."""
    w = World()
    qt = make_qt()
    fontlab = ModuleType("fontlab")
    fontlab.flWorkspace = NS(
        instance=lambda: NS(currentPackage=None if w.no_font else w.package)
    )

    def notify(title: str, items: list, *flags: bool) -> None:
        if w.fail_notify:
            raise RuntimeError("boom notify")
        w.events.append(
            (
                "notify",
                title,
                [getattr(i, "marker", None) or i.name for i in items],
                items,
                flags,  # (True,) asks for deep history
            )
        )

    fontlab.flItems = lambda: NS(notifyChangesApplied=notify)
    fontlab.flNode = NS(NodeKind={"SmoothMask": SMOOTH})
    fontlab.CurrentGlyph = lambda: w.glyphs[w.selected[0]] if w.selected else None
    fontlab.CurrentFont = lambda: NS(glyphs=[NS(name=n, unicodes=[]) for n in w.glyphs])
    fontlab.MainWindow = lambda: NS(palette=Palette())
    fontlab.UpdateAll = lambda: w.events.append(("update-all",))
    fontlab.flGlyph = NS(updatedFgGlyphs=lambda: tuple(w.pending))
    def names() -> list[str]:
        return list(w.glyphs)
    fl = NS(Selected=lambda index: names()[index] in w.selected)

    class FLFont:
        def __len__(self) -> int:
            return len(w.glyphs)

        def __getitem__(self, index: int) -> Any:
            return NS(name=names()[index])

    fl.font = FLFont()
    native = ModuleType("FL")
    native.fl = fl
    # Isolate from other test files in the same run: they may have left spec-copied
    # `fontlabapp.*` modules or fakes behind. Snapshot, import the real packages afresh,
    # and put the snapshot back afterwards (monkeypatch restores what it deleted).
    for key in [k for k in sys.modules if k.split(".")[0] in ISOLATED]:
        monkeypatch.delitem(sys.modules, key)
    echopy = ModuleType("echopy")
    echopy.__path__ = []  # a package, so `echopy.fontpr` resolves from sys.modules
    fontpr = ModuleType("echopy.fontpr")
    fontpr.call = w.call
    echopy.fontpr = fontpr
    for name, module in (
        ("PythonQt", qt),
        ("fontlab", fontlab),
        ("FL", native),
        ("echopy", echopy),
        ("echopy.fontpr", fontpr),
        ("fontpr", fontpr),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(
        sys,
        "meta_path",
        [f for f in sys.meta_path if not getattr(f, "_fontlab_fly_alias", False)],
    )
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    Dialog.registry.clear()
    yield w
    for key in [k for k in sys.modules if k.split(".")[0] in ISOLATED]:
        del sys.modules[key]


Contour = OutlineContour


@pytest.fixture
def contours_world(components_world: Any) -> Any:
    components_world.round_writes = False
    return components_world


def current_path(relative: str) -> Path:
    """Current callable source; consolidated contour routes live in App."""
    return route_path(Path(relative).stem) if relative.startswith("Contours/") else ROOT / "Scripts" / relative


def load(relative: str) -> dict[str, Any]:
    name = "fontlabapp.fontui.outline_routes.g2_test" if relative.startswith("Contours/") else "g2_test"
    return runpy.run_path(str(current_path(relative)), run_name=name)


@pytest.fixture
def components(components_world: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Reuse the owned component native double; extend only test-local objects."""
    w = components_world
    sys.modules["fontlab"].ShapeType = {"ShapeSticker\t": 4}

    def refuse_raw(glyph: Any) -> None:
        raise AssertionError("Raw glyph insertion is forbidden.")

    w.package.addGlyph = refuse_raw
    w.package.name = "owned font"
    w.package.marker = "package"
    w.package.checkInitHistoryState = lambda index: w.events.append(("init", "package"))
    container = NS(
        marker="kerning container",
        checkInitHistoryState=lambda i: w.events.append(("init", "kerning")),
    )
    w.package.kerningContainer = lambda: container
    masters_container = NS(marker="masters container")
    w.package.mastersContainer = lambda: masters_container
    w.groups = {master: {} for master in w.masters}
    w.package.kerning = lambda master: NS(groups=w.groups[master])
    qt = sys.modules["PythonQt"]
    original = qt.QtGui.QDialog
    forbidden = {
        "layout",
        "font",
        "size",
        "move",
        "update",
        "render",
        "statusBar",
        "parent",
        "width",
        "height",
    }

    class StrictDialog(original):
        def __setattr__(self, name: str, value: Any) -> None:
            if name in forbidden:
                raise AttributeError(f"native widget member: {name}")
            super().__setattr__(name, value)

    qt.QtGui.QDialog = StrictDialog
    qt.QtCore.Qt.AlignVCenter = 4
    qt.QtCore.Qt.WindowStaysOnTopHint = 0x40000
    w.answers = []
    w.questions = []

    class StandardButtons:
        def __init__(self, value: int) -> None:
            self.value = value

    def question(*args: Any) -> int:
        if not isinstance(args[3], StandardButtons):
            raise TypeError("buttons must be StandardButtons, not int")
        w.questions.append(args)
        return w.answers.pop(0) if w.answers else 0

    qt.QtGui.QMessageBox = message_box_type(question=question)
    qt.QtGui.QMessageBox.StandardButtons = StandardButtons
    import fly.ap.core.history.glyphs as history  # noqa: PLR0402
    import fly.ap.glyphs.catalog.model as catalog

    patch_app(
        monkeypatch,
        history,
        "scan_auto_facts",
        lambda package: history.auto_facts(
            (
                glyph.name,
                layer.autoLayer,
                tuple(
                    shape.shapeData.componentGlyph
                    for shape in layer.shapes
                    if shape.isComponent
                ),
            )
            for glyph in w.glyphs.values()
            for layer in glyph.layers
        ),
    )
    w.codes = {}
    patch_app(
        monkeypatch,
        catalog,
        "capture",
        lambda *, deadline=None: NS(
            rows=tuple(
                (name, " ".join(f"U+{cp:04X}" for cp in w.codes.get(name, [])), "")
                for name in w.glyphs
            )
        ),
    )
    return w


def add_glyph(w: Any, name: str, code: int | None = None) -> Any:
    glyph = w.glyph(name, select=False)
    glyph.isNull = False
    glyph.mark = 23
    glyph.id = id(glyph)
    if code is not None:
        w.codes[name] = [code]
    for layer in glyph.layers:
        layer.id = id(layer)
        layer.isNull = False
        layer.recipe = ""
        layer.isLocked = False
        layer.isMaskLayer = layer.isService = False
        layer.guidelines = ["guide"]
        layer.metricsLeft = layer.metricsRight = layer.metricsWidth = "expression"
        layer.getMaskLayer = lambda create: None
        layer.getImgLayer = lambda create: None
        layer.clearAnchors = lambda layer=layer: layer.anchors.clear()
        layer.removeAllShapes = lambda layer=layer: layer._shapes.clear()
        layer.addShape = layer.add
        layer.resetMetricsLeft = lambda layer=layer: setattr(layer, "metricsLeft", "")
        layer.resetMetricsRight = lambda layer=layer: setattr(layer, "metricsRight", "")
        layer.resetMetricsWidth = lambda layer=layer: setattr(layer, "metricsWidth", "")
        layer.update = lambda: True
    return glyph


def prototype(w: Any, base: str = "a") -> Any:
    glyph = add_glyph(w, "prototype")
    shape = Shape(w, base)
    glyph.layers[0].add(shape)
    return shape






@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("closed", [False, True])
def test_retraction_exact_coordinates_and_open_ends(
    contours_world: Any, selected: bool, closed: bool
) -> None:
    ns = load(PATHS[4])
    contour = Contour(
        contours_world,
        [(0, 0, 1), (25, 30, 0), (70, 40, 0), (100, 0, 1)],
        closed=closed,
    )
    for i, node in enumerate(contour.nodes()):
        node.selected = i == 3
    targets = ns["moves"](contour, selected)
    assert [(x, y) for _, x, y in targets] == (
        [(100, 0)] if selected else [(0, 0), (100, 0)]
    )
    editor = ns["RetractEditor"]()
    editor.write(NS(), [targets])
    assert editor.check([(NS(name="Light"), [targets])]) == []
    assert len(contour.nodes()) == 4


def test_retract_closing_segment_and_quadratic(contours_world: Any) -> None:
    ns = load(PATHS[4])
    contour = Contour(
        contours_world, [(10, 20, 1), (60, 50, 1), (50, 60, 0), (20, 30, 0)]
    )
    assert [(x, y) for _, x, y in ns["moves"](contour, False)] == [(60, 50), (10, 20)]
    contour.isTT = True
    assert ns["moves"](contour, False) == []
    assert ns["moves"](Contour(contours_world, []), False) == []


@pytest.mark.parametrize("closed,expected", [(True, [1, 3, 5]), (False, [1, 3, 5])])
def test_simplify_exact_alternation(
    contours_world: Any, closed: bool, expected: list[int]
) -> None:
    ns = load(PATHS[5])
    contour = Contour(contours_world, [(i, i % 2, 1) for i in range(7)], closed=closed)
    for node in contour.nodes():
        node.selected = True
    assert ns["removals"](contour) == expected
    contour.removeAt = lambda index: contour._nodes.pop(index)
    ns["SimplifyEditor"]().write(NS(), [(contour, expected, 4)])
    assert [node.x for node in contour.nodes()] == [0, 2, 4, 6]


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_simplify_keeps_minimum_polygon(contours_world: Any, count: int) -> None:
    ns = load(PATHS[5])
    contour = Contour(contours_world, [(i, 0, 1) for i in range(count)])
    for node in contour.nodes():
        node.selected = True
    removed = ns["removals"](contour)
    assert len(removed) <= max(0, count - 3)


def test_simplify_curves_kept(contours_world: Any) -> None:
    contour = Contour(contours_world, [(0, 0, 1), (1, 1, 0), (2, 1, 0), (3, 0, 1)])
    for node in contour.nodes():
        node.selected = True
    assert load(PATHS[5])["removals"](contour) == []






































@pytest.mark.parametrize("relative", [PATHS[4], PATHS[5]])
def test_outline_apply_uses_real_history_one_notification(
    contours_world: Any, relative: str
) -> None:
    w = contours_world
    glyph = w.glyph("A")
    layer = glyph.layers[0]
    ns = load(relative)
    contour = Contour(w, [(i * 10, 0, 1) for i in range(7)])
    for node in contour.nodes():
        node.selected = True
    if relative == PATHS[4]:
        node = contour.nodes()[1]
        edits, editor = [[(node, 0.0, 0.0)]], ns["RetractEditor"]()
    else:
        contour.removeAt = lambda index: contour._nodes.pop(index)
        edits, editor = [(contour, [1, 3, 5], 4)], ns["SimplifyEditor"]()
    result = ns["writer"].apply_work(
        [(glyph, layer, edits)],
        ns["TITLE"],
        ns["writer"].history.auto_facts(()),
        editor,
    )
    assert result["layers"] == 1
    assert len(w.notifications()) == 1
    assert w.notifications()[0][3] == [layer, glyph]


















def test_simplify_selection_maps_to_other_master(components: Any) -> None:
    w = components
    glyph = add_glyph(w, "A")
    for layer in glyph.layers:
        shape = Shape(w)
        shape.shapeData.referenceCount = 1
        contour = Contour(w, [(i, 0, 1) for i in range(7)])
        for node in contour.nodes():
            node.selected = layer.name == "Light"
        shape.contours = [contour]
        layer.add(shape)
    ns = load(PATHS[5])
    rows = ns["changes"](glyph.layers[1], glyph.layers[0])
    assert rows[0].edit[1] == [1, 3, 5]
















def test_native_fake_constructors_reject_optional_positionals(components: Any) -> None:
    def node(point: Any, *, nodeType: str = "on") -> Any:
        return NS(point=point, nodeType=nodeType)

    def contour(nodes: list[Any], *, closed: bool = True) -> Any:
        return NS(nodes=nodes, closed=closed)

    sys.modules["fontlab"].flNode = node
    sys.modules["fontlab"].flContour = contour
    with pytest.raises(TypeError):
        sys.modules["fontlab"].flNode((0, 0), "off")
    with pytest.raises(TypeError):
        sys.modules["fontlab"].flContour([], True)












def test_app_double_signature_check_rejects_variadic_capture(
    components: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fly.ap.glyphs.catalog.model as catalog

    with pytest.raises(AssertionError, match="signature mismatch"):
        patch_app(monkeypatch, catalog, "capture", lambda **kw: None)


























def test_confirmation_native_double_rejects_int_flags(components: Any) -> None:
    box = sys.modules["PythonQt"].QtGui.QMessageBox
    with pytest.raises(TypeError, match="StandardButtons"):
        box.question(None, "title", "text", box.Yes | box.No, box.No)


















def test_migrated_simplify_direct_module_entry_opens_retained_panel(contours_world, monkeypatch):
    import fontlabapp.core.scripting as scripting
    opened = []
    monkeypatch.setattr(scripting, 'show_script_dialog', lambda panel, key: opened.append((panel, key)))
    namespace = runpy.run_module('fontlabapp.fontui.outline_routes.simplify_selected_nodes', run_name='__main__')
    assert opened == [(namespace['SimplifyPanel'], 'contours_simplify_selected_nodes')]
