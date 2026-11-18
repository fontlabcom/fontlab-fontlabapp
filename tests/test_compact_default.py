# this_file: tests/test_compact_default.py
"""Windows are compact by default (issue 253); ``compact=False`` is the one opt-out."""

from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt as _studio_qt
from test_spacing_worksheet import GUI, QtCore, drain

import fontlabapp.qt.widgets as widgets
from fontlabapp.qt import compact as compact_mod

studio_qt = _studio_qt
del _studio_qt


def margins(layout):
    m = layout.contentsMargins()
    return (m.left(), m.top(), m.right(), m.bottom())


@pytest.fixture
def binding(monkeypatch):
    qt = NS(QtGui=GUI, QtCore=QtCore)
    monkeypatch.setattr(widgets, "_native", lambda name: qt)
    monkeypatch.setattr(compact_mod, "_qt", lambda: qt)
    yield qt
    drain()


def roomy(content):
    layout = GUI.QVBoxLayout(content)
    layout.setContentsMargins(11, 11, 11, 11)
    layout.setSpacing(6)
    row = GUI.QHBoxLayout()
    layout.addLayout(row)
    return layout, row


def test_owned_when_created_then_root_layout_compact(studio_qt):
    owned = studio_qt.modules.lifecycle.Owned(None)
    studio_qt.owned.append(owned)
    assert margins(owned.layout) == (6, 6, 6, 6)
    assert owned.layout.spacing() == 4


def test_owned_when_compact_false_then_qt_default(studio_qt):
    owned = studio_qt.modules.lifecycle.Owned(None, compact=False)
    studio_qt.owned.append(owned)
    assert margins(owned.layout) != (6, 6, 6, 6)


def test_create_dialog_when_build_makes_roomy_layout_then_compact(binding):
    seen = {}

    def build(content):
        seen["layout"], seen["row"] = roomy(content)

    main = GUI.QMainWindow()
    owned = widgets.create_dialog(main, "T", build)
    assert margins(seen["layout"]) == (6, 6, 6, 6)
    assert seen["layout"].spacing() == 4 and seen["row"].spacing() == 4
    assert margins(seen["row"]) == (0, 0, 0, 0)
    owned.close()


def test_create_dialog_when_compact_false_then_build_metrics_kept(binding):
    seen = {}
    main = GUI.QMainWindow()
    owned = widgets.create_dialog(
        main, "T", lambda c: seen.update(layout=roomy(c)[0]), compact=False
    )
    assert margins(seen["layout"]) == (11, 11, 11, 11)
    owned.close()


@pytest.mark.parametrize("kind", ["panel", "widget"])
def test_panel_and_widget_when_built_then_compact(binding, kind):
    seen = {}
    build = lambda c: seen.update(layout=roomy(c)[0])  # noqa: E731
    if kind == "panel":
        main = GUI.QMainWindow()
        owned = widgets.create_panel(main, "T", build, "right")
    else:
        owned = widgets.create_widget(None, build, show=False)
    assert margins(seen["layout"]) == (6, 6, 6, 6)
    owned.close()
