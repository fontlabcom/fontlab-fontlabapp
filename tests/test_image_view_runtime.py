# this_file: tests/test_image_view_runtime.py
"""Standalone owned Qt pixels, transparency and DPI; never loaded in FontLab."""

import os
from types import SimpleNamespace as NS

import fontlabapp.qt.images.view as api
import pytest

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    from PySide6 import QtCore, QtGui, QtWidgets
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize("mode", ["down", "fit", "none", "stretch"])
@pytest.mark.parametrize("ratio", [1, 1.5, 2])
@pytest.mark.parametrize("size", [(4, 3), (13, 9)])
def test_present_real_pixmap_has_expected_dimensions_dpr_and_transparency(
    mode, ratio, size
):
    class Label(QtWidgets.QLabel):
        def devicePixelRatioF(self):
            return ratio

        def setPixmap(self, value):
            # Qt6 stores an icon and its getter may return display-DPR pixels.
            # Capture the real QPixmap delivered at this helper's API boundary.
            self.delivered = QtGui.QPixmap(value)
            super().setPixmap(value)

    label = Label()
    calls = []

    def render(scale):
        calls.append(scale)
        image = QtGui.QImage(
            max(1, round(8 * scale)),
            max(1, round(4 * scale)),
            QtGui.QImage.Format_ARGB32_Premultiplied,
        )
        image.fill(QtGui.QColor(30, 100, 200, 160))
        image.setDevicePixelRatio(scale)
        return QtGui.QPixmap.fromImage(image)

    api.present(NS(QtCore=QtCore), label, render, size=size, natural=(8, 4), mode=mode)
    factor = {
        "down": min(size[0] / 8, size[1] / 4, 1),
        "fit": min(size[0] / 8, size[1] / 4),
        "none": 1,
        "stretch": 1,
    }[mode]
    assert calls == [factor * ratio]
    pixmap = (
        label.pixmap()
        if os.environ.get("FONTLABAPP_TEST_QT5") == "1"
        else label.delivered
    )
    assert not label.pixmap().isNull()
    expected = (
        (round(size[0] * ratio), round(size[1] * ratio))
        if mode == "stretch"
        else (round(8 * factor * ratio), round(4 * factor * ratio))
    )
    assert (
        pixmap.width(),
        pixmap.height(),
    ) == expected and pixmap.devicePixelRatio() == ratio
    pixels = pixmap.toImage()
    assert (
        pixels.hasAlphaChannel()
        and pixels.pixelColor(pixels.width() // 2, pixels.height() // 2).alpha() == 160
    )
    api.present(None, label)
    assert label.pixmap() is None or label.pixmap().isNull()
    label.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
