# this_file: tests/issue205_painting.py
"""Existing real-Qt adapter plus an observer that keeps the real raster output."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from legacy_panel_qt import QtCore, QtGui, QtWidgets, legacy_qt as legacy_qt


class Painter(QtGui.QPainter):
    def __init__(self, image):
        super().__init__(image)
        self.labels, self.paths, self.lines, self.dots = [], [], [], []

    def drawText(self, *args):
        self.labels.append(args[-1])
        return super().drawText(*args)

    def drawPath(self, path):
        self.paths.append(QtGui.QPainterPath(path))
        return super().drawPath(path)

    def fillPath(self, path, brush):
        self.paths.append(QtGui.QPainterPath(path))
        return super().fillPath(path, brush)

    def drawLine(self, *args):
        self.lines.append(args)
        return super().drawLine(*args)

    def drawPoint(self, point):
        self.dots.append(QtCore.QPointF(point))
        return super().drawPoint(point)


def render(view):
    image = QtGui.QImage(
        max(800, view.width), max(600, view.height), QtGui.QImage.Format_ARGB32
    )
    image.fill(QtCore.Qt.transparent)
    painter = Painter(image)
    try:
        view.draw(painter)
    finally:
        assert painter.end(), "The real raster painter must always finish"
    assert image != QtGui.QImage(), "Drawing must retain its real image"
    return NS(
        image=image,
        labels=painter.labels,
        paths=painter.paths,
        lines=painter.lines,
        dots=painter.dots,
    )


@pytest.fixture
def painting(legacy_qt, monkeypatch):
    names = (
        "components.inspect.views",
        "anchors.inspect.views",
        "guides.inspect.views",
        "masters.interpolation.view",
        "proof.inspectors.views",
    )
    modules = {
        "proof": legacy_qt.modules["_proof_views"],
        "masters": legacy_qt.modules["_masters_views"],
    }
    for short in names:
        name = "fontlabapp." + short
        parent_name, _, child = name.rpartition(".")
        parent = importlib.import_module(parent_name)
        monkeypatch.delattr(parent, child, raising=False)
        monkeypatch.delitem(sys.modules, name, raising=False)
        modules[short] = importlib.import_module(name)

    def own(widget):
        widget.resize(640, 400)
        legacy_qt.owned.append(widget)
        return widget

    path = QtGui.QPainterPath()
    path.addRect(0, 0, 200, 700)
    return NS(modules=modules, own=own, path=path, qt=legacy_qt)
