# this_file: src/fontlabapp/studios/vertical_metrics/diagram.py
# SPDX-License-Identifier: Apache-2.0
"""Diagram tab (read only): Vertical Metrics Diagram (Metrics) and Nodes Near Zones (Reports).

Diagram: one column per master draws the outlines of H, x, b and p against
that master's baseline, ascender, cap height, x-height and descender
(``FontMetrics(package, master)``; the current master is never switched).
One scale fits every master. A sample glyph that is missing, or has no layer
in a master, is listed below and left out. Drawing errors stay in the panel.

Nodes Near Zones: on-curve nodes that sit within the tolerance (1–30 units,
default 4) of a master's baseline, x-height, cap height, ascender or
descender but not on it, in the selected glyphs or all glyphs (the default
when nothing is selected). Selecting a row shows that glyph and master in
the TMetrics preview; "Select glyphs" selects the listed (or the chosen)
glyphs in the Font window of the font that was scanned.

The tab never writes the font and never opens a history step.
"""

from dataclasses import dataclass
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.core.scripting import current_package, select_glyphs

from .._kerning import Tool
from .._kerning_ui import Panel, button, combo, get, row, spin
from .._kerning_ui import label as text_label
from . import _shared
from ._shared import ap, fontlab

FIELDS = [
    ("Ascender", "ascender"),
    ("Cap height", "capsHeight"),
    ("x-height", "xHeight"),
    ("Descender", "descender"),
]
SAMPLE = ("H", "x", "b", "p")
LABEL_WIDTH = 84  # px: margin for the line names.
RIGHT_PAD = 16  # px after the last column.
HEAD = 22  # px: row for the master names.
FOOT = 12  # px below the lowest line.
TOP_MARGIN = 60  # units above the highest metric.
BOTTOM_MARGIN = 40  # units below the lowest metric.
FILL = 0.9  # Part of a column that the widest sample line may use.
LABEL_GAP = 16  # px between two line names in the margin.
TOLERANCE = (1, 30, 4)  # Nodes Near Zones: low, high, default (units)


class _Panel:
    """``metrics.panel.model`` as the verbatim Diagram reads it (``metrics_panel.muted``)."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(_shared.backends().panel, name)


metrics_panel = _Panel()


@dataclass(frozen=True)
class Frame:
    """Map font units to widget pixels. y grows down in the widget."""

    left: float  # px: x of the first column.
    column: float  # px: width of one master column.
    scale: float  # px per unit.
    baseline: float  # px: y of the baseline.

    def x(self, index: int, units: float) -> float:
        """Pixel x of a unit offset inside column ``index``."""
        return self.left + index * self.column + units * self.scale

    def y(self, units: float) -> float:
        """Pixel y of a height in units."""
        return self.baseline - units * self.scale


def frame(
    width: float, height: float, metrics: list[dict[str, float]], sample_width: float
) -> Frame:
    """Fit all masters' metrics and the widest sample line into the widget.

    The scale is the smaller of the height fit (all lines, the baseline and
    the margins) and the width fit (``FILL`` of a column for the widest line).
    Vertical slack is split above and below.
    """
    top = max(max(values.values()) for values in metrics) + TOP_MARGIN
    bottom = min(0, *(min(values.values()) for values in metrics)) - BOTTOM_MARGIN
    column = (width - LABEL_WIDTH - RIGHT_PAD) / len(metrics)
    room = height - HEAD - FOOT
    scale = min(room / (top - bottom), column * FILL / max(sample_width, 1))
    baseline = HEAD + max(room - (top - bottom) * scale, 0) / 2 + top * scale
    return Frame(LABEL_WIDTH, column, scale, baseline)


def line_start(area: Frame, line_width: float) -> float:
    """Unit offset that centres a sample line of ``line_width`` units in a column."""
    return (area.column / area.scale - line_width) / 2


def read_metrics(package: Any, masters: list[str]) -> dict[str, dict[str, float]]:
    """{master: {attribute: value}} from FontMetrics; never switches the master."""
    found = {}
    for master in masters:
        values = ap.fontlab.FontMetrics(package, master)
        found[master] = {key: float(getattr(values, key)) for _, key in FIELDS}
    return found


def outline(layer: Any) -> Any:
    """The layer outline as one QPainterPath in font units; read in place."""
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.WindingFill)
    for shape in layer.shapes:
        part = QtGui.QPainterPath()
        for contour in shape.getContours():
            part.addPath(contour.path())
        path.addPath(shape.transform.map(part))
    return path


def collect(
    package: Any, masters: list[str]
) -> tuple[dict[str, list[tuple[str, Any, float]]], float, list[str]]:
    """Read the sample glyphs: ({master: [(name, path, advance)]}, widest line, notes)."""
    samples: dict[str, list[tuple[str, Any, float]]] = {m: [] for m in masters}
    notes: list[str] = []
    for name in SAMPLE:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            notes.append(f"{name}: not in this font")
            continue
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                notes.append(f"{name}: no layer in {master}")
                continue
            samples[master].append((name, outline(layer), float(layer.advanceWidth)))
    widest = max((sum(a for _, _, a in line) for line in samples.values()), default=0)
    return samples, widest, notes


class Diagram(QtGui.QWidget):
    """One column per master: sample outlines plus labelled metric lines."""

    def __init__(self, owner: Any) -> None:
        """Keep the owner panel, which holds the data to draw."""
        QtGui.QWidget.__init__(self)
        self.owner = owner
        self.paint_error = ""
        self.setMinimumSize(560, 260)

    def paintEvent(self, event: Any) -> None:
        """Draw. An error is kept, never raised; the painter always ends."""
        painter = QtGui.QPainter(self)
        try:
            self.draw(painter, self.width, self.height)
            self.paint_error = ""
        except Exception as error:  # noqa: BLE001 - an error escaping paint can crash FontLab
            self.paint_error = repr(error)
        finally:
            painter.end()

    def draw(self, painter: Any, width: float, height: float) -> None:
        """Paint the background, then every master column."""
        owner = self.owner
        palette = self.palette
        painter.fillRect(
            QtCore.QRectF(0, 0, width, height), palette.color(QtGui.QPalette.Base)
        )
        masters = [m for m in owner.masters if m in owner.metrics]
        if not masters:
            painter.setPen(QtGui.QColor(metrics_panel.muted(self)))
            painter.drawText(
                QtCore.QRectF(0, 0, width, height),
                int(QtCore.Qt.AlignCenter),
                "No metrics to show.",
            )
            return
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        area = frame(
            width, height, [owner.metrics[m] for m in masters], owner.sample_width
        )
        ink = QtGui.QColor(palette.color(QtGui.QPalette.WindowText))
        guide = QtGui.QColor(palette.color(QtGui.QPalette.Mid))
        small = painter.font()
        small.setPointSizeF(max(small.pointSizeF() * 0.85, 8))
        painter.setFont(small)
        for index, master in enumerate(masters):
            self.draw_column(painter, area, index, master, ink, guide)

    def draw_column(
        self, painter: Any, area: Frame, index: int, master: str, ink: Any, guide: Any
    ) -> None:
        """Master name, metric lines, the sample outlines; line names in column 0."""
        values = self.owner.metrics[master]
        left = area.x(index, 0)
        painter.setPen(ink)
        painter.drawText(
            QtCore.QRectF(left, 0, area.column, HEAD),
            int(QtCore.Qt.AlignCenter),
            master,
        )
        lines = [("Baseline", 0.0)] + [(label, values[key]) for label, key in FIELDS]
        painter.setPen(QtGui.QPen(QtGui.QBrush(guide), 1.0))
        for _, units in lines:
            painter.drawLine(
                QtCore.QPointF(left + 6, area.y(units)),
                QtCore.QPointF(left + area.column - 6, area.y(units)),
            )
        if index == 0:
            self.draw_labels(painter, [(area.y(u), label) for label, u in lines])
        line = self.owner.samples.get(master, [])
        pen = line_start(area, sum(advance for _, _, advance in line))
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(ink))
        for _, path, advance in line:
            painter.save()
            painter.translate(area.x(index, pen), area.baseline)
            painter.scale(area.scale, -area.scale)
            painter.drawPath(path)
            painter.restore()
            pen += advance

    def draw_labels(self, painter: Any, labels: list[tuple[float, str]]) -> None:
        """Line names right-aligned in the margin, pushed apart when lines are close."""
        painter.setPen(QtGui.QColor(metrics_panel.muted(self)))
        last = None
        for y, label in sorted(labels):
            if last is not None and y < last + LABEL_GAP:
                y = last + LABEL_GAP
            painter.drawText(
                QtCore.QRectF(0, y - 9, LABEL_WIDTH - 6, 18),
                int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter),
                label,
            )
            last = y


def master_metrics(package: Any, master: Any) -> Any:
    """[(label, y)] vertical metrics of one master."""
    m = fontlab.FontMetrics(package, master)
    return [
        ("baseline", 0.0),
        ("x-height", m.xHeight),
        ("cap height", m.capsHeight),
        ("ascender", m.ascender),
        ("descender", m.descender),
    ]


def on_curve_points(layer: Any) -> Any:
    """[(x, y)] of the layer's own on-curve nodes with each shape's transform applied."""
    points = []
    for shape in layer.shapes:
        if shape.shapeData is not None and shape.shapeData.componentGlyph:
            continue
        transform = shape.transform
        for contour in shape.getContours():
            for node in contour.nodes():
                if node.isOn():
                    p = transform.map(QtCore.QPointF(node.x, node.y))
                    points.append((p.x(), p.y()))
    return points


def near_misses(points: Any, metrics: Any, tolerance: Any) -> Any:
    """[(label, metric y, node x, node y)] for points with 0 < |y - metric| <= tolerance."""
    out = []
    for x, y in points:
        for label, value in metrics:
            delta = y - value
            if 0 < abs(delta) <= tolerance:
                out.append((label, value, x, y))
    return out


def scan(package: Any, names: Any, tolerance: Any) -> Any:
    """[(glyph, master, metric label, metric y, node x, node y)]."""
    masters = list(package.masters)
    metrics = {m: master_metrics(package, m) for m in masters}
    rows = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None:
            continue
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is None:
                continue
            rows.extend(
                (name, master, *hit)
                for hit in near_misses(
                    on_curve_points(layer), metrics[master], tolerance
                )
            )
    return rows


class DiagramPanel(Panel):
    """Vertical Metrics Diagram with Nodes Near Zones below; read only."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.masters: list[str] = []
        self.metrics: dict[str, dict[str, float]] = {}
        self.samples: dict[str, list] = {}
        self.sample_width = 0.0
        self.diagram = Diagram(self)
        self.diagram.setParent(self.widget)
        self.layout.addWidget(self.diagram, 2)
        self.notes = text_label(self.widget, self.layout)
        text_label(self.widget, self.layout, "Nodes Near Zones")
        self.scope = combo(
            self.widget,
            ["Selected glyphs", "All glyphs"],
            _shared.keep(self, self.rescan),
        )
        row(self.widget, self.layout, "Glyphs", self.scope)
        self.tolerance = spin(
            self.widget,
            *TOLERANCE,
            suffix=" units",
            slot=_shared.keep(self, self.rescan),
        )
        row(self.widget, self.layout, "Within", self.tolerance)
        self.grid = _shared.MasterTable(self.widget, self.layout, ["Glyph · master", "Metric", "Node", "y", "Off by"],
                                        chosen=_shared.keep(self, self.show_row))  # fmt: skip
        self.status = text_label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.select_button = button(
            self.widget, buttons, "Select glyphs", lambda: self.run(self.select_rows)
        )
        self.rows: list[tuple] = []
        self.package_id: int | None = None

    def clear(self) -> None:
        self.masters, self.metrics, self.samples, self.sample_width = [], {}, {}, 0.0
        self.rows, self.package_id = [], None
        self.grid.set_rows([])
        self.select_button.setEnabled(False)
        self.diagram.update()

    def refresh(self) -> None:
        self.clear()
        package = self.tool.package
        self.notes.setText("")
        if package is None:
            self.subtitle.setText("Open a font first.")
            self.status.setText("")
            return
        self.masters = list(package.masters)
        self.metrics = read_metrics(package, self.masters)
        self.samples, self.sample_width, notes = collect(package, self.masters)
        self.diagram.update()
        found = sum(
            1 for name in SAMPLE if not any(n.startswith(f"{name}: not") for n in notes)
        )
        self.subtitle.setText(f"{' '.join(SAMPLE)} from each master against its own lines · "
                              f"{_shared.plural(len(self.masters), 'master')} · {found} of {len(SAMPLE)} "
                              "sample glyphs. Read only: edit the values in the Metrics table tab.")  # fmt: skip
        self.notes.setText(" · ".join(notes))
        if not self.tool.selected_names():
            self.scope.blockSignals(True)
            self.scope.setCurrentIndex(1)
            self.scope.blockSignals(False)
        self.rescan()

    def names(self) -> list[str]:
        if get(self.scope.currentIndex) == 0:
            return self.tool.selected_names()
        return [
            g.name for g in fontlab.CurrentFont().glyphs
        ]  # the original's All glyphs

    def rescan(self) -> None:
        """Nodes Near Zones: scan the chosen glyphs of the current font."""
        self.rows, self.package_id = [], None
        self.select_button.setEnabled(False)
        package = self.tool.package
        if package is None:
            self.grid.set_rows([])
            return
        names = self.names()
        tolerance = get(self.tolerance.value)
        result = scan(package, names, tolerance)
        glyphs = sorted({r[0] for r in result})
        self.grid.set_rows([(f"{name} · {master}", f"{text} {value:g}", f"{x:g}, {y:g}", f"{y:g}", f"{y - value:+g}")
                            for name, master, text, value, x, y in result],
                           keys=[f"{r[0]}\t{r[1]}" for r in result])  # fmt: skip
        self.rows, self.package_id = result, package.id
        self.select_button.setEnabled(bool(result))
        self.status.setText(f"{len(names)} glyphs × {len(package.masters)} masters checked: on-curve nodes "
                            f"1–{tolerance} units off the lines · {len(result)} near miss"
                            f"{'es' if len(result) != 1 else ''} in {_shared.plural(len(glyphs), 'glyph')}")  # fmt: skip

    def show_row(self, key: str) -> None:
        name, master = key.split("\t")
        preview = self.tool.preview
        if preview is not None:
            preview.set_text(f"/{name}")
            preview.set_layer(master)

    def select_rows(self, rows: list[int] | None = None) -> None:
        """Select the listed glyphs (or the chosen rows) only in the font that produced them."""
        if self.package_id is None:
            raise ValueError("Refresh the report before selecting glyphs.")
        package = current_package()
        if package is None or package.id != self.package_id:
            raise ValueError("stale font: Refresh the report.")
        rows = (
            rows
            if rows is not None
            else (self.grid.selected() or list(range(len(self.rows))))
        )
        names = list(
            dict.fromkeys(self.rows[r][0] for r in rows if 0 <= r < len(self.rows))
        )
        selected = select_glyphs(names, package_id=self.package_id)
        self.tool.say(f"Selected {_shared.plural(len(selected), 'glyph')}")


__all__ = ["FIELDS", "SAMPLE", "Diagram", "DiagramPanel", "Frame", "collect", "frame", "line_start",
           "master_metrics", "near_misses", "on_curve_points", "outline", "read_metrics", "scan"]  # fmt: skip
