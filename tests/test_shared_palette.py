# this_file: tests/test_shared_palette.py
"""Actual owned shared-panel contrast after palette changes, including reopening."""

import re

import pytest
from test_extrema_dialog import QtCore, QtGui, panel as shared_panel


@pytest.fixture
def panel(monkeypatch):
    yield from shared_panel.__wrapped__(monkeypatch)


def test_shared_subtitle_tracks_light_dark_and_back_without_reopening(panel):
    w, _, _, _ = panel
    for foreground, background, bright in (
        ("#f1f2f3", "#24252a", True),
        ("#202126", "#fafafa", False),
    ):
        palette = w.palette
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(foreground))
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(background))
        w.setPalette(palette)
        css = w.subtitle.styleSheet()
        color = QtGui.QColor(re.search(r"#[0-9a-fA-F]+", css).group())
        assert (color.lightness() > 128) is bright, (
            "Subtitle must follow the theme text colour"
        )
    w.changeEvent(QtCore.QEvent(QtCore.QEvent.FontChange))
