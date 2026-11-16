# this_file: tests/_feature_source_qt.py
# SPDX-License-Identifier: Apache-2.0
"""Owned real Qt controls and explicit PythonQt property spelling for tests."""
import base64
import json
from collections.abc import Mapping

import attrs
from ufoLib2 import Font
from ufoLib2.objects import Anchor, Guideline, Image, Component

from contextlib import contextmanager
from types import SimpleNamespace


def qt_namespace():
    from PySide6 import QtCore, QtGui, QtWidgets

    class Combo(QtWidgets.QComboBox):
        currentIndex = property(QtWidgets.QComboBox.currentIndex)

    class Line(QtWidgets.QLineEdit):
        text = property(QtWidgets.QLineEdit.text)

    class Label(QtWidgets.QLabel):
        text = property(QtWidgets.QLabel.text)

    class Check(QtWidgets.QCheckBox):
        checked = property(QtWidgets.QCheckBox.isChecked)

    class Spin(QtWidgets.QSpinBox):
        value = property(QtWidgets.QSpinBox.value)

    class Widget(QtWidgets.QWidget):
        width = property(QtWidgets.QWidget.width)
        rect = property(QtWidgets.QWidget.rect)

    class Scroll(QtWidgets.QScrollArea):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setViewport(Widget(self))

    gui = SimpleNamespace(**{
        **{n: getattr(QtGui, n) for n in dir(QtGui) if not n.startswith('_')},
        **{n: getattr(QtWidgets, n) for n in dir(QtWidgets) if not n.startswith('_')},
    })
    gui.QComboBox, gui.QLineEdit, gui.QLabel = Combo, Line, Label
    gui.QCheckBox, gui.QSpinBox, gui.QWidget, gui.QScrollArea = Check, Spin, Widget, Scroll
    return SimpleNamespace(QtCore=QtCore, QtGui=gui)


@contextmanager
def owned_application():
    from PySide6 import QtCore, QtWidgets
    import shiboken6

    existing = QtWidgets.QApplication.instance()
    app = existing if existing is not None else QtWidgets.QApplication([])
    try:
        yield app
    finally:
        if existing is None:
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            app.quit()
            shiboken6.delete(app)


class TextAdapter:
    """Forward legacy actions to the actual guard, with no parallel text state."""
    def __init__(self, owner, widgets):
        from fontlabapp.fontui.feature_source import create_source_input
        self.widget = create_source_input(
            qt_namespace(), is_closed=lambda: owner.closed,
            on_change=lambda: owner._mark(),
            on_diagnostic=lambda text: owner.diagnostic.setText(text),
        )
        widgets.append((owner, self.widget))
        self.textChanged = self.widget.textChanged

    @property
    def value(self):
        return self.widget.source_text()

    @value.setter
    def value(self, text):
        assert self.widget.setPlainText(text), self.widget.diagnostic

    @property
    def readOnly(self):
        return self.widget.isReadOnly()

    @property
    def enabled(self):
        return self.widget.isEnabled()

    def __getattr__(self, name):
        return getattr(self.widget, name)


def dispose_controls(widgets):
    import shiboken6
    from PySide6 import QtCore
    for owner, widget in widgets:
        owner.closed = True
        if shiboken6.isValid(widget):
            widget.close()
            widget.deleteLater()
            QtCore.QCoreApplication.sendPostedEvents(widget, QtCore.QEvent.DeferredDelete)
        assert not shiboken6.isValid(widget)


def snapshot(widget):
    cursor, document = widget.textCursor(), widget.document()
    return (document.toRawText(), cursor.anchor(), cursor.position(),
            document.revision(), document.availableUndoSteps(), document.availableRedoSteps())


def freeze(value):
        if attrs.has(type(value)):
            return {"type": type(value).__module__ + "." + type(value).__qualname__,
                    "fields": {f.name: freeze(getattr(value, f.name)) for f in attrs.fields(type(value))}}
        if isinstance(value, Mapping):
            return {"mapping": [[freeze(k), freeze(v)] for k, v in sorted(value.items(), key=lambda kv: repr(kv[0]))]}
        if isinstance(value, (set, frozenset)):
            items = [freeze(x) for x in value]
            return {"type": type(value).__name__, "items": sorted(items, key=lambda x: json.dumps(x, sort_keys=True))}
        if isinstance(value, (list, tuple)):
            return {"type": type(value).__name__, "items": [freeze(x) for x in value]}
        if isinstance(value, bytes): return {"bytes": value.hex()}
        if value is None or type(value) in (str, int, bool): return value
        if isinstance(value, float): return {"float": value.hex()}
        raise TypeError("Unqualified fixture snapshot type: " + str(type(value)))

def font_fixture(text, marker):
        font = Font(); font.info.familyName = "Owned same label"; font.info.styleName = "Regular"
        font.info.unitsPerEm = 1000; font.info.ascender = 800; font.info.descender = -200
        font.features.text = text
        font.lib["owned"] = {"marker": marker, "nested": [True, 1, 1.5, b"\x00\xff"]}
        font.groups["public.kern1.A"] = ["A"]; font.kerning[("A", "B")] = -25.5
        font.images["owned.png"] = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==")
        font.data["owned/payload.bin"] = b"owned\0\xff"
        g = font.newGlyph("A"); g.width = 600.25; g.height = 900.5; g.unicodes = [65]
        g.note = "unchanged Ω"; g.lib["owned"] = [marker]
        g.anchors = [Anchor(100.5, 700, "top")]; g.guidelines = [Guideline(25, 0, 90, "guide")]
        g.image = Image("owned.png", (1, 0, 0, 1, 13.5, -17.75))
        pen = g.getPen(); pen.moveTo((0,0)); pen.lineTo((100,0)); pen.lineTo((100,100)); pen.closePath()
        g.components.append(Component("B", (1, 0, 0, 1, 10.5, 20)))
        font.newGlyph("B").width = 420
        layer = font.layers.newLayer("owned.background"); layer.lib["owned"] = marker
        layer.newGlyph("untouched").width = 333
        return font
