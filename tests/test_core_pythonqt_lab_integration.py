# this_file: tests/test_core_pythonqt_lab_integration.py
"""A complete drag lab sends real profile output into its TMetrics preview."""
import importlib
import sys

from fontParts.fontshell import RFont
from test_studio_labs_e04_e06 import real_qt  # noqa: F401


def test_drag_lab_when_preview_clicked_then_metrics_receives_profile_text(real_qt, monkeypatch):  # noqa: F811
    qt, _app = real_qt
    class CheckBox(qt.QtGui.QCheckBox):
        checked = property(qt.QtGui.QCheckBox.isChecked)
    class SpinBox(qt.QtGui.QSpinBox):
        value = property(qt.QtGui.QSpinBox.value)
    class LineEdit(qt.QtGui.QLineEdit):
        text = property(qt.QtGui.QLineEdit.text)
    class DoubleSpinBox(qt.QtGui.QDoubleSpinBox):
        value = property(qt.QtGui.QDoubleSpinBox.value)
    class Viewport(qt.QtGui.QWidget):
        width = property(qt.QtGui.QWidget.width)
    class ScrollBar(qt.QtGui.QScrollBar):
        value = property(qt.QtGui.QScrollBar.value)
    class ScrollArea(qt.QtGui.QScrollArea):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setViewport(Viewport())
            self.setHorizontalScrollBar(ScrollBar())
            self.setVerticalScrollBar(ScrollBar())
    qt.QtGui.QScrollArea = ScrollArea
    qt.QtGui.QDoubleSpinBox = DoubleSpinBox
    qt.QtGui.QLineEdit = LineEdit
    qt.QtGui.QCheckBox = CheckBox
    qt.QtGui.QSpinBox = SpinBox
    for name in ('fontlabapp.fontui.lifecycle', 'fontlabapp.fontui.appshell',
                 'fontlabapp.fontui.tmetrics', 'fontlabapp.fontui.core_pythonqt_labs.app',
                 'fontlabapp.fontui.core_pythonqt_labs.closing'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module('fontlabapp.fontui.core_pythonqt_labs.app')
    monkeypatch.setattr(module.fontui, 'current_font', lambda: None)
    font = RFont()
    font.info.unitsPerEm = 1000
    font.glyphOrder = ['A', 'V']
    for name, code in [('A', 65), ('V', 86)]:
        glyph = font.newGlyph(name)
        glyph.unicode = code
        glyph.width = 500
        pen = glyph.getPen()
        pen.moveTo((0, 0))
        pen.lineTo((200, 500))
        pen.lineTo((400, 0))
        pen.closePath()
    shell = module.show('E06', font=font, package=lambda: None,
                        profile='Deferred Glyph Report Drag')
    try:
        shell.preview_button.click()
        assert shell.preview.text_control.text == '/A /V'
        assert shell.preview.read_only
        assert [cell.name for cell in shell.preview.model.cells] == ['A', 'V'], shell.preview.diagnostic.text()
        assert len(shell.children) == 7
    finally:
        shell.close()
