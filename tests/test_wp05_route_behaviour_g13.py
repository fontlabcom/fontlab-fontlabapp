# this_file: tests/test_wp05_route_behaviour_g13.py
# ruff: noqa: F811 - ported fixtures are re-imported and then shadowed by parameters
# SPDX-License-Identifier: Apache-2.0
"""Behaviour tests with owned data; these do not certify the native host."""

import importlib.util
import inspect
import math
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any
from unittest.mock import create_autospec

import pytest
from _wp05_scriptmix_shim import real_app  # noqa: F401

ROOT = Path(__file__).parents[1]

FAKED_APP_NAMES: dict[str, set[str]] = {}


def patch_app(monkeypatch: Any, module: Any, name: str, action: Any) -> Any:
    """Enforce the real callable signature on every replaced App function."""
    current = getattr(module, name)
    original = getattr(current, "_g13_original", current)
    assert parameter_shape(action) == parameter_shape(original), (
        f"{module.__name__}.{name}"
    )
    replacement = create_autospec(original, spec_set=True, side_effect=action)
    replacement._g13_original = original
    FAKED_APP_NAMES.setdefault(module.__name__, set()).add(name)
    monkeypatch.setattr(module, name, replacement)
    return replacement


def load(key: str) -> Any:
    """Load only the new independent script, without native imports."""
    assert key == "sans"
    source = ROOT / "src/fontlabapp/studios/shape_generators/sansomatic.py"
    spec = importlib.util.spec_from_file_location("g13_" + key, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
















@pytest.mark.parametrize("letter", list("AEFHILNOSTVXYZ"))
def test_sans_all_supported_letters(letter: str) -> None:
    tool = load("sans")
    commands, advance = tool.design(letter, 700, 450, 70, 55, 45)
    assert commands and advance > 0
    assert all(math.isfinite(v) for op in commands for v in op[1:])
    assert any(op[0] == "Z" for op in commands)


def test_sans_exact_H_geometry() -> None:
    commands, advance = load("sans").design("H", 700, 450, 70, 50, 40)
    assert advance == 530
    assert commands[0] == ("R", 40, 0, 70, 700)
    assert ("R", 110, 325, 310, 50) in commands


@pytest.mark.parametrize(
    "args",
    [
        ("B", 700, 450, 70, 55, 45),
        ("H", 0, 450, 70, 55, 45),
        ("O", 700, 100, 70, 55, 45),
    ],
)
def test_sans_invalid_design(args: tuple) -> None:
    with pytest.raises(ValueError):
        load("sans").design(*args)


def test_sans_keeps_existing_and_unsafe_layers() -> None:
    tool = load("sans")
    assert "kept" in tool.layer_reason(
        NS(
            shapes=[object()],
            isLocked=False,
            metricsLeft="",
            metricsRight="",
            metricsWidth="",
        )
    )
    assert "kept" in tool.layer_reason(NS(shapes=[], isLocked=True))




class HistoryItem:
    """A glyph/layer with an observable native history boundary."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.id = id(self)
        self.history = []
        self.lastModified = None
        self.autoLayer = False
        self.isNull = False

    def checkInitHistoryState(self, index: int) -> None:
        self.history.append(index)


class Layer(HistoryItem):
    def __init__(self, name: str = "Regular") -> None:
        super().__init__(name)
        self.shapes = []
        self.advanceWidth = 0
        self.isLocked = False
        self.metricsLeft = self.metricsRight = self.metricsWidth = ""
        self.updated = 0

    def addShape(self, shape: Any) -> None:
        self.shapes.append(shape)

    def changed(self) -> None:
        self.updated += 1

    def update(self) -> bool:
        return True


class Shape:
    def addContours(self, contours: list, flag: bool) -> None:
        self.contours = contours


@pytest.fixture
def host(real_app: Any, monkeypatch: Any) -> Any:
    """Load installed App writers over owned native history records."""
    import fly

    notifications = []

    class Items:
        def __call__(self) -> Any:
            return self

        def notifyChangesApplied(self, *args: Any) -> None:
            notifications.append(args)

    native = NS(flItems=Items(), flGlyph=NS(updatedFgGlyphs=list), flShape=Shape)
    qt = NS(
        QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "UTC")),
        QtGui=NS(QDialog=type("HostDialog", (), {})),
    )
    monkeypatch.setitem(vars(fly), "qt", qt)
    monkeypatch.setitem(vars(fly), "fl", native)
    modules = real_app(
        qt=qt,
        fontlab=native,
        modules=(
            "history",
            "outline_writer",
            "outline_panel",
            "contour_copy",
            "metrics_panel",
            "selection_panel",
            "kerning_batch",
            "guides",
            "proof",
            "qtsafe",
            "reports",
        ),
    )
    return NS(modules=modules, native=native, qt=qt, notifications=notifications)


def test_sans_real_outline_history_and_noop(host: Any, monkeypatch: Any) -> None:
    tool = load("sans")
    monkeypatch.setattr(tool, "build_path", lambda commands: commands)
    patch_app(
        monkeypatch,
        host.modules["contour_copy"],
        "path_contours",
        lambda path: [NS(nodes=path)],
    )
    glyph, layer = HistoryItem("H"), Layer()
    payload = tool.design("H", 700, 450, 70, 50, 40)
    writer, history = host.modules["outline_writer"], host.modules["history"]
    result = writer.apply_work(
        [(glyph, layer, [payload])],
        tool.TITLE,
        history.auto_facts([]),
        tool.editor_type()(),
    )
    assert result["layers"] == 1
    assert layer.advanceWidth == 530
    assert len(layer.shapes) == 1
    assert glyph.history == layer.history == [0]
    assert host.notifications == [(tool.TITLE, [layer, glyph])]
    assert glyph.lastModified == "UTC"
    writer.apply_work([], tool.TITLE, history.auto_facts([]), tool.editor_type()())
    assert len(host.notifications) == 1


def test_sans_partial_failure_keeps_undo_diagnosis(host: Any, monkeypatch: Any) -> None:
    tool = load("sans")
    monkeypatch.setattr(tool, "build_path", lambda commands: commands)
    patch_app(
        monkeypatch,
        host.modules["contour_copy"],
        "path_contours",
        lambda path: [object()],
    )
    first, second = Layer(), Layer("Bold")
    second.addShape = lambda shape: (_ for _ in ()).throw(RuntimeError("cannot insert"))
    glyph = HistoryItem("H")
    payload = tool.design("H", 700, 450, 70, 50, 40)
    with pytest.raises(
        RuntimeError, match="Native changes may remain; use Edit > Undo"
    ):
        host.modules["outline_writer"].apply_work(
            [(glyph, first, [payload]), (glyph, second, [payload])],
            tool.TITLE,
            host.modules["history"].auto_facts([]),
            tool.editor_type()(),
        )
    assert len(first.shapes) == 1 and not second.shapes
    assert host.notifications == [(tool.TITLE, [first, second, glyph])]


def test_sans_auto_refusal_before_history(host: Any, monkeypatch: Any) -> None:
    tool = load("sans")
    monkeypatch.setattr(tool, "build_path", lambda commands: commands)
    patch_app(
        monkeypatch,
        host.modules["contour_copy"],
        "path_contours",
        lambda path: [object()],
    )
    glyph, layer = HistoryItem("H"), Layer()
    layer.autoLayer = True
    payload = tool.design("H", 700, 450, 70, 50, 40)
    with pytest.raises(ValueError):
        host.modules["outline_writer"].apply_work(
            [(glyph, layer, [payload])],
            tool.TITLE,
            host.modules["history"].auto_facts([("H", True, ())]),
            tool.editor_type()(),
        )
    assert not layer.shapes and not host.notifications and not glyph.history


class Box:
    """Minimal control that rejects QWidget member collisions on panel objects."""

    def __init__(self, *args: Any) -> None:
        self.value = 0
        self.checked = False
        self.toggled = object()

    def setChecked(self, value: bool) -> None:
        self.checked = value

    def isChecked(self) -> bool:
        return self.checked


class SelectionBase:
    """Only the shared panel hook contract; no invented native API fallback."""

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {
            "layout",
            "font",
            "render",
            "size",
            "update",
            "controls",
            "statusBar",
        }:
            raise AttributeError(name)
        object.__setattr__(self, name, value)

    def add_row(self, label: str, *widgets: Any) -> None:
        self.control_rows.append((label, widgets))

    def watch(self, signal: Any, callback: Any = None) -> None:
        self.watched.append(signal)


class OutlineBase(SelectionBase):
    """Separate OutlinePanel double, with its exact numeric-control signature."""

    def spin(
        self, low: float, high: float, value: float, suffix: str = "", decimals: int = 0
    ) -> Any:
        return NS(value=value)


def test_sans_controls_planner_and_kept_rows(host: Any, monkeypatch: Any) -> None:
    patch_app(
        monkeypatch, host.modules["outline_panel"], "panel_type", lambda: OutlineBase
    )
    tool = load("sans")
    panel = tool.panel_type()()
    panel.control_rows, panel.watched = [], []
    panel.build_controls()
    assert len(panel.control_rows) == 5
    layer = Layer()
    glyph = NS(name="H", unicodes=[72])
    row = panel.planner()(glyph, "Regular", layer)[0]
    assert row.edit[1] == 540 and row.key == ("capital", "H")
    layer.shapes = [object()]
    kept = panel.planner()(glyph, "Regular", layer)[0]
    assert kept.edit is None and "kept" in kept.new
    assert (
        panel.planner()(NS(name="Q", unicodes=[81]), "Regular", Layer())[0].edit is None
    )








class PathFake:
    """Strict path-operation surface, retaining subtraction and curve commands."""

    def __init__(self) -> None:
        self.ops = []

    def addRect(self, *values: float) -> None:
        self.ops.append(("rect", *values))

    def addEllipse(self, *values: float) -> None:
        self.ops.append(("ellipse", *values))

    def moveTo(self, *values: float) -> None:
        self.ops.append(("move", *values))

    def lineTo(self, *values: float) -> None:
        self.ops.append(("line", *values))

    def cubicTo(self, *values: float) -> None:
        self.ops.append(("cubic", *values))

    def closeSubpath(self) -> None:
        self.ops.append(("close",))

    def united(self, other: Any) -> Any:
        self.ops.extend(other.ops)
        return self

    def subtracted(self, other: Any) -> Any:
        self.ops.append(("subtract", other.ops))
        return self


@pytest.mark.parametrize("letter", list("HANOXS"))
def test_sans_path_builder_routes_each_operation(host: Any, letter: str) -> None:
    host.qt.QtGui.QPainterPath = PathFake
    tool = load("sans")
    commands, _ = tool.design(letter, 700, 450, 70, 55, 45)
    result = tool.build_path(commands)
    assert result.ops
    if letter == "O":
        assert any(op[0] == "subtract" for op in result.ops)
    if letter == "S":
        assert sum(op[0] == "cubic" for op in result.ops) == 8






class NativeKerning:
    """Typed native keys, including explicit zeros and global scaling."""

    def __init__(self) -> None:
        self.groups = {"L": (("period", "comma"), "KernLeft")}
        self.values = {
            (("L", "groupMode"), ("A", "glyphMode")): 0,
            (("A", "glyphMode"), ("V", "glyphMode")): -70,
        }

    def items(self) -> list:
        return [
            (NS(left=NS(id=a[0], mode=a[1]), right=NS(id=b[0], mode=b[1])), value)
            for (a, b), value in self.values.items()
        ]

    def set(self, key: tuple, value: float) -> None:
        self.values[key] = value

    def remove(self, key: tuple) -> None:
        self.values.pop(key, None)

    def scale(self, factor: float) -> None:
        self.values = {key: value * factor for key, value in self.values.items()}




@pytest.mark.parametrize("letter", list("AEFHILNOSTVXYZ"))
@pytest.mark.parametrize("dimensions", [(700, 450, 70, 55, 45), (900, 600, 90, 65, 30)])
def test_sans_outline_bounds_reach_baseline_and_cap_height(
    letter: str, dimensions: tuple
) -> None:
    from fontTools.pens.boundsPen import BoundsPen

    pen = BoundsPen(None)
    commands, _ = load("sans").design(letter, *dimensions)
    for op, *values in commands:
        if op in ("R", "E"):
            x, y, width, height = values
            pen.moveTo((x, y))
            pen.lineTo((x + width, y + height))
            pen.endPath()
        elif op == "M":
            pen.moveTo(tuple(values))
        elif op == "L":
            pen.lineTo(tuple(values))
        elif op == "C":
            pen.curveTo(tuple(values[:2]), tuple(values[2:4]), tuple(values[4:]))
        elif op == "Z":
            pen.closePath()
    assert pen.bounds[1] == pytest.approx(0), f"{letter}: lower outline bound"
    assert pen.bounds[3] == pytest.approx(dimensions[0]), (
        f"{letter}: upper outline bound"
    )


def parameter_shape(function: Any) -> tuple:
    return tuple(
        (p.name, p.kind, p.default)
        for p in inspect.signature(function).parameters.values()
    )




















def test_sans_unsupported_glyph_is_named(host: Any, monkeypatch: Any) -> None:
    tool = load("sans")
    patch_app(
        monkeypatch, host.modules["outline_panel"], "panel_type", lambda: OutlineBase
    )
    panel = tool.panel_type()()
    panel.control_rows, panel.watched = [], []
    panel.build_controls()
    row = panel.planner()(NS(name="Aacute", unicodes=[193]), "Regular", Layer())[0]
    assert row.edit is None and "Aacute" in row.new and "kept" in row.new


