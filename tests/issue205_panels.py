# this_file: tests/issue205_panels.py
"""Owned FontGate fixtures and real Qt controls for the existing report shells."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from legacy_panel_qt import QtCore, QtGui, QtWidgets, legacy_qt as legacy_qt
from test_anchor_edit import owned as owned, extra_master


class Combo(QtWidgets.QComboBox):
    currentIndex = property(QtWidgets.QComboBox.currentIndex)
    currentText = property(QtWidgets.QComboBox.currentText)


class Edit(QtWidgets.QLineEdit):
    text = property(QtWidgets.QLineEdit.text)


class Table(QtWidgets.QTableWidget):
    palette = property(QtWidgets.QWidget.palette)
    rowCount = property(QtWidgets.QTableWidget.rowCount)
    columnCount = property(QtWidgets.QTableWidget.columnCount)


class Item(QtWidgets.QTableWidgetItem):
    def flags(self):
        return super().flags().value

    def setTextAlignment(self, flags):
        super().setTextAlignment(QtCore.Qt.AlignmentFlag(flags))

    def setFlags(self, flags):
        super().setFlags(QtCore.Qt.ItemFlag(flags))


def combo(values=("Current", "All")):
    widget = Combo()
    widget.addItems(values)
    return widget


@pytest.fixture
def panels(legacy_qt, owned, monkeypatch):
    package = owned.package
    glyph, layer = owned.glyph("A", points=(("top", 100, 700),))
    mark, mark_layer = owned.glyph("acute", points=(("_top", 50, 0),))
    for g, body in ((glyph, layer), (mark, mark_layer)):
        body.guidelines = []
        extra_master(g, body, "Bold", "").guidelines = []
    package.isNull, package.fgId, package.upm, package.axes, package.guidelines = (
        False,
        17,
        1000,
        [],
        [],
    )
    package.ascender_value, package.descender_value, package.italicAngle_value = (
        800,
        -200,
        0,
    )
    package.setMaster = lambda name, *args: setattr(package, "master", name)
    package.location = lambda name: {}
    package.findUnicode = lambda code: {65: glyph}.get(code)
    state = NS(package=package, names=["A", "acute"], selection=["A"])
    # Font order of this package (Issue 250): follows state.names as tests add glyphs.
    package.fgPackage = type(
        "FontOrder", (), {"glyphs": property(lambda _: [NS(name=n) for n in state.names])}
    )()
    native = owned.native
    native.flWorkspace = NS(instance=lambda: NS(currentPackage=state.package))
    native.CurrentFont = lambda: NS(glyphs=[glyph, mark])
    native.CurrentGlyph = lambda: glyph

    def metrics(p, master):
        owned.events.append(("metrics", master))
        return NS(xHeight=500, capsHeight=700, ascender=800, descender=-200)

    native.FontMetrics = metrics
    monkeypatch.setitem(sys.modules, "fontlab", native)
    legacy_qt.gui.QTableWidgetItem = Item
    models = {}
    for short in (
        "masters.inspect.model",
        "components.inspect.model",
        "anchors.inspect.model",
        "guides.inspect.model",
        "proof.inspectors.model",
    ):
        model = importlib.import_module("fontlabapp." + short)
        models[short] = model
        if hasattr(model, "font_glyph_names"):
            monkeypatch.setattr(model, "font_glyph_names", lambda: list(state.names))
        if hasattr(model, "all_names"):
            monkeypatch.setattr(model, "all_names", lambda *args: list(state.names))
        if hasattr(model, "selected_names"):
            monkeypatch.setattr(model, "selected_names", lambda: list(state.selection))
        if hasattr(model, "exact_selected_names"):
            monkeypatch.setattr(
                model, "exact_selected_names", lambda: list(state.selection)
            )
        if hasattr(model, "selected_glyphs"):
            monkeypatch.setattr(
                model,
                "selected_glyphs",
                lambda p: [p.findName(n) for n in state.selection],
            )
    modules = {
        "masters": legacy_qt.modules["_masters_dialog"],
        "proof": legacy_qt.modules["_proof_dialog"],
    }
    for short in (
        "components.inspect.ui",
        "anchors.inspect.ui",
        "anchors.copy.ui",
        "proof.inspectors.ui",
        "proof.review.ui",
        "masters.switcher.ui",
        "guides.inspect.ui",
        "guides.rewrite.ui",
        "guides.rewrite.editor_ui",
        "fonts.info.ui",
        "features.editor.ui",
    ):
        name = "fontlabapp." + short
        parent, _, child = name.rpartition(".")
        monkeypatch.delattr(importlib.import_module(parent), child, raising=False)
        monkeypatch.delitem(sys.modules, name, raising=False)
        modules[short] = importlib.import_module(name)
    monkeypatch.setattr(
        modules["masters"], "selected_names", lambda: list(state.selection)
    )
    monkeypatch.setattr(modules["masters"], "all_names", lambda: list(state.names))

    def own(widget):
        legacy_qt.owned.append(widget)
        return widget

    def controls(panel):
        panel.status, panel.table = QtWidgets.QLabel(), Table(0, 5)
        panel.scope, panel.source = combo(), combo()
        panel.apply_button, panel.copy_button, panel.select_button = [
            QtWidgets.QPushButton() for _ in range(3)
        ]
        return panel

    def make(cls, key):
        if issubclass(cls, modules["masters"].MastersDialog):

            class Tool(cls):
                def build(self):
                    self.table, self.scope, self.source = Table(0, 5), combo(), combo()

                def refresh(self):
                    return None

                def apply(self):
                    return None

            panel = Tool(None, "Owned report", key)
        else:
            panel = cls(None, "Owned report", key)
        own(panel)
        controls(panel)
        return panel

    return NS(
        modules=modules,
        models=models,
        state=state,
        package=package,
        glyph=glyph,
        layer=layer,
        mark=mark,
        owned=owned,
        qt=legacy_qt,
        make=make,
        own=own,
        controls=controls,
    )
