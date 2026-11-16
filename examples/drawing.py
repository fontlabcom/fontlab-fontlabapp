# this_file: examples/drawing.py
"""Run inside FontLab: real Preview/Glyph overlay and owned compositions."""

from pathlib import Path

from fly.ap import Application
from grablab import Grab
from fly.qt import QtGui


def paint(painter) -> None:
    painter.fillRect(8, 8, 12, 12, QtGui.QColor("#ff0000"))
    painter.setPen(QtGui.QColor("#008000"))
    painter.drawLine(30, 30, 60, 60)
    painter.drawText(30, 80, "Overlay Łódź")


def build(widget) -> None:
    layout = QtGui.QVBoxLayout(widget)
    layout.addWidget(QtGui.QLabel("Native composition", widget))
    layout.addWidget(QtGui.QLineEdit(widget))


app = Application()
folder = Path.home() / "Desktop" / "fontlab-overlay"
folder.mkdir(exist_ok=True)
grab = Grab(application=app, folder_base=folder)
with app.control as fl:
    with fl.preview.draw(paint) as drawing:
        grab.getWidgetSVG(fl.preview.widget, folder / "preview.svg")
        drawing.raise_if_failed()
    glyph_windows = fl.glyph_windows()
    if glyph_windows:
        glyph = glyph_windows[0]
        with glyph.draw(paint) as drawing:
            grab.getWidgetSVG(glyph.canvas.viewPort, folder / "glyph.svg")
            grab.getPixmapPNG(glyph.canvas.viewPort.grab(), folder / "glyph.png")
            drawing.raise_if_failed()
    # Retain a handle to keep composed UI open; close() removes only that UI.
    panel = fl.create_panel("My panel", build)
    dialog = fl.create_dialog("My dialog", build)
    widget = fl.create_widget(build=build)
    panel.close()
    dialog.close()
    widget.close()
