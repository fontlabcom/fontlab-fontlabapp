# this_file: examples/native_ui.py
# Copyright (c) 2025 Fontlab Ltd. All Rights Reserved.
# Proprietary: see LICENSE-native-ui. Moved from fontlabcom/fontlab-remopy.
"""Compose native UI and Preview drawing from an ordinary external script.

Install fontlab-fontlabapp and fontlab-fly>=1.3.0 inside FontLab first;
--typerig also needs typerig.
The public RemoteFontLab alias uses fontlab_remopy.client.
Run outside FontLab: python native_ui.py --seconds 5 [--typerig].
"""

import argparse
import time
from uuid import uuid4

from fontlab_remopy import FontLab as RemoteFontLab


def show_ui(fl: RemoteFontLab, *, seconds: float = 5, typerig: bool = False) -> dict:
    """Keep owned native handles alive across calls, then remove only this UI."""
    if seconds < 0:
        raise ValueError("seconds must be nonnegative")
    key = "_remopy_ui_" + uuid4().hex

    @fl.python
    def create(key, typerig):
        import fly.fl as fontlab
        from fly.ap import FontLab
        from fly.qt import QtGui

        def build(widget):
            layout = QtGui.QVBoxLayout(widget)
            layout.addWidget(QtGui.QLabel("Created from external Python", widget))
            if typerig:
                from fly.tr.proxy.fl.gui.widgets import CustomSpinLabel

                layout.addWidget(CustomSpinLabel("Size", (0, 100, 12, 1)))
            else:
                layout.addWidget(QtGui.QLineEdit("Łódź", widget))

        def paint(painter):
            painter.setPen(QtGui.QColor("#008000"))
            painter.drawLine(20, 20, 100, 60)
            painter.drawText(20, 80, "External Python → FontLab")

        control = FontLab()
        try:
            panel = control.create_panel("External Python", build)
            dialog = control.create_dialog("External dialog", build)
            control.preview.draw(paint)
            setattr(fontlab, key, control)
            return {"panel": panel.widget.isVisible(),
                    "dialog": dialog.widget.isVisible(), "typerig": typerig}
        except BaseException:
            control.close()
            raise

    @fl.python
    def remove(key):
        import fly.fl as fontlab

        control = getattr(fontlab, key, None)
        if control is not None:
            control.close()
            delattr(fontlab, key)

    try:
        result = create(key, typerig)
        time.sleep(seconds)  # Wait outside FontLab; its UI event loop stays free.
        return result
    finally:
        remove(key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--typerig", action="store_true")
    arguments = parser.parse_args()
    with RemoteFontLab() as fl:
        print(show_ui(fl, seconds=arguments.seconds, typerig=arguments.typerig))
