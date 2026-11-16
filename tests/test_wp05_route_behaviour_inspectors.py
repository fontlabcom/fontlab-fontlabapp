# this_file: tests/test_inspectors.py
# SPDX-License-Identifier: Apache-2.0
"""Complete original metrics and outline menu acceptance with native-shaped doubles."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from _smx_masters import (
    Item,
    MasterWidget,
    masters,  # noqa: F401
)
from _smx_proof import Box, Signal, Widget
from _wp05_scriptmix_shim import (  # noqa: F401
    app_module_name,
    app_source_path,
    app_sources,
    real_app,  # noqa: F401
    register_app_module,
)

ROOT = Path(__file__).parents[1]
TOOLS = [
    ("Metrics", "Spacing String Preview", "SpacingPreview"),
    ("Metrics", "Width Table", "WidthTable"),
    ("Contours", "Contour Order View", "ContourOrder"),
    ("Contours", "Node Statistics", "NodeStatistics"),
]


def inspector_path(category, title):
    moved = {"Contour Order View": "order", "Node Statistics": "statistics"}
    if title in moved:
        return ROOT / "src/fontlabapp/fontui/outline_compatibility_routes" / (moved[title] + ".py")
    return ROOT / "Scripts" / category / (title + ".py")


@pytest.mark.parametrize(
    "title,klass", [("Contour Order View", "ContourOrder"), ("Node Statistics", "NodeStatistics")]
)
def test_contour_inspector_runs_from_its_renamed_menu_entry(inspectors, monkeypatch, title, klass):
    import runpy

    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    inspectors.font()
    namespace = runpy.run_path(
        str(inspector_path("Contours", title)), run_name="__main__"
    )
    dialog = sys._fontlab_samples[namespace["KEY"]]
    assert isinstance(dialog, namespace[klass]), "File execution must show the complete editor"
    dialog.close()
    assert namespace["KEY"] not in sys._fontlab_samples, "Close must release the renamed menu"





class Check(MasterWidget):
    def __init__(self, *args):
        super().__init__(*args)
        self.checked = False
        self.toggled = Signal()

    def isChecked(self):
        return self.checked

    def setChecked(self, value):
        self.checked = value
        self.toggled.emit()


class Combo(MasterWidget):
    clear = Widget.clear


class NumericItem(Item):
    def __init__(self, parent):
        super().__init__(parent)
        self.value = parent

    def setData(self, role, value):
        self.value = value
        self.texts[0] = str(value)

    def data(self, role):
        return self.value


@pytest.fixture
def inspectors(masters, monkeypatch, app_sources):  # noqa: F811 - imported pytest fixture
    masters.qt.QtGui.QComboBox = Combo
    masters.qt.QtCore.Qt.DisplayRole = 0
    masters.qt.QtGui.QCheckBox = Check
    masters.qt.QtGui.QLineEdit = MasterWidget
    masters.qt.QtGui.QAbstractItemView.SelectRows = 1
    masters.qt.QtGui.QTableWidgetItem = NumericItem
    masters.qt.QtGui.QPalette.Mid = 8
    masters.qt.QtCore.Qt.AlignTop = 128
    for name in ["inspectors", "_inspectors_views", "_inspectors_dialog"]:
        spec = importlib.util.spec_from_file_location(
            app_module_name(name), app_source_path(app_sources, name)
        )
        module = importlib.util.module_from_spec(spec)
        register_app_module(monkeypatch, name, module)
        spec.loader.exec_module(module)
        masters.modules[name] = module

    def module(title):
        category = next(cat for cat, t, _ in TOOLS if t == title)
        spec = importlib.util.spec_from_file_location(
            title, inspector_path(category, title)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    original = masters.font

    def font():
        package, layers = original()
        package.ascender_value, package.descender_value = 800, -200
        package.findUnicode = lambda code: next(
            (g for g in masters.state.glyphs if code in g.unicodes), None
        )
        for rows in layers.values():
            for layer in rows.values():
                layer.boundingBox = NS(x=lambda: 0, width=lambda: 20, height=lambda: 20)
                for shape in layer.shapes:
                    for c in shape.contours:
                        c.nodesCount = len(c.nodes())
                        c.closed = True
        masters.modules["inspectors"].outline = lambda layer: (
            "path",
            layer.advanceWidth,
        )
        return package, layers

    masters.font, masters.module = font, module
    return masters










def test_node_auto_missing_whole_font_filter_and_exact_selection(inspectors):
    _package, layers = inspectors.font()
    inspectors.state.selected = {0}
    layers["H"]["Bold"].shapes[0].contours[0].nodesCount = 7
    layers["O"]["Bold"].autoLayer = True
    layers["n"].pop("Light")
    dialog = inspectors.module("Node Statistics").NodeStatistics()
    assert dialog.flagged == ["H"]
    dialog.apply()
    assert inspectors.state.selected == {0} and dialog.last_result == {
        "selected": ["H"]
    }
    dialog.source.setCurrentIndex(1)
    assert list(dialog.data) == ["H", "O", "n"]
    assert dialog.data["O"]["Bold"] is None and dialog.data["n"] == {"Bold": (1, 4)}
    dialog.only_flagged.setChecked(True)
    assert dialog.table.rowCount == 1 and dialog.table.item(0, 0).text() == "H"


@pytest.mark.parametrize(
    "change",
    ["source", "master", "masters", "whole_order", "whole_delete", "whole_insert"],
)
def test_node_action_refuses_stale_source_and_domain(inspectors, change):
    package, layers = inspectors.font()
    layers["H"]["Bold"].shapes[0].contours[0].nodesCount = 7
    dialog = inspectors.module("Node Statistics").NodeStatistics()
    dialog.source.setCurrentIndex(1)
    if change == "source":
        layers["H"]["Bold"].shapes[0].contours[0].nodesCount = 9
    elif change == "master":
        package.master = "Light"
    elif change == "masters":
        package.masters.reverse()
    elif change == "whole_order":
        inspectors.state.glyphs.reverse()
    elif change == "whole_delete":
        inspectors.state.glyphs.pop()
    else:
        inspectors.state.glyphs.append(NS(name="new", unicodes=[]))
    before = inspectors.state.selected.copy()
    with pytest.raises(ValueError, match="changed"):
        dialog.apply()
    assert (
        inspectors.state.selected == before
        and not dialog._snapshot_valid
        and not dialog.data
    )




# Immutable Scriptmix v1.0.6: all 45 rows serialized with sorted keys and
# separators=(",", ":"). Verify this literal from the tag, never from current rows.
RELEASED_V1_0_6_MANIFEST_SHA256 = (
    "58d98d7622a78373b989e61a21e9c947ee1354a17b69b96c042091840df749e2"
)










def test_whole_font_membership_change_during_scan_refuses_publication(
    inspectors, monkeypatch
):
    _package, layers = inspectors.font()
    mod = inspectors.module("Node Statistics")
    dialog = mod.NodeStatistics()
    original = mod.glyph_counts

    def changed(*args):
        result = original(*args)
        if len(inspectors.state.glyphs) == 3:
            inspectors.state.glyphs.append(
                NS(name="new", unicodes=[], isNull=False, findLayer=layers["H"].get)
            )
        return result

    monkeypatch.setattr(mod, "glyph_counts", changed)
    dialog.source.setCurrentIndex(1)
    assert "glyph order changed" in dialog.last_error
    assert not dialog._snapshot_valid and not dialog.data and dialog.package is None


class GeometryBox(Box):
    def __init__(self, *values):
        super().__init__(*(values or (0, 0, 0, 0)))

    def x(self):
        return self.values[0]

    def y(self):
        return self.values[1]

    def width(self):
        return self.values[2]

    def height(self):
        return self.values[3]

    def translated(self, x, y):
        return GeometryBox(self.x() + x, self.y() + y, self.width(), self.height())

    def united(self, other):
        if not self.width() and not self.height():
            return other
        left, top = min(self.left(), other.left()), min(self.top(), other.top())
        return GeometryBox(
            left,
            top,
            max(self.right(), other.right()) - left,
            max(self.bottom(), other.bottom()) - top,
        )


class GeometryPath:
    def __init__(self):
        self.points = []

    def moveTo(self, x, y):
        self.points.append((x, y))

    def lineTo(self, x, y):
        self.points.append((x, y))

    def quadTo(self, *pts):
        self.points.extend(zip(pts[::2], pts[1::2]))

    def cubicTo(self, *pts):
        self.points.extend(zip(pts[::2], pts[1::2]))

    def closeSubpath(self):
        pass

    def boundingRect(self):
        xs, ys = zip(*self.points) if self.points else ([0], [0])
        return GeometryBox(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


class Transform:
    def __init__(self, *v):
        self.v = v or (1, 0, 0, 1, 0, 0)

    def m11(self):
        return self.v[0]

    def m12(self):
        return self.v[1]

    def m21(self):
        return self.v[2]

    def m22(self):
        return self.v[3]

    def dx(self):
        return self.v[4]

    def dy(self):
        return self.v[5]

    def map(self, value):
        from _smx_masters import Point

        if isinstance(value, GeometryPath):
            return value
        return Point(
            value.x() * self.m11() + self.dx(), value.y() * self.m22() + self.dy()
        )
















