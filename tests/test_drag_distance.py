# this_file: tests/test_drag_distance.py
"""FontLab PythonQt exposes startDragDistance only on the QApplication instance (A2 report 15 section 2b)."""

from importlib import import_module
from types import SimpleNamespace

import pytest

from fontlabapp.qt.properties import _DEFAULT_DRAG_DISTANCE as DEFAULT_DRAG_DISTANCE, start_drag_distance

BASE = "fontlabapp.fontui.core_pythonqt_labs.profiles."
HANDLES = [
    "deferred_glyph_report",
    "draggable_glyph_names",
    "font_drop_inspector",
    "font_file_drop_shelf",
    "glyph_pair_board",
    "proof_word_magnets",
]


def app_class(instance_value, class_value=None, has_instance=True):
    """Fake QApplication class: class attribute and instance() as in FontLab."""
    instance = SimpleNamespace(startDragDistance=lambda: instance_value) if has_instance else None
    return SimpleNamespace(startDragDistance=class_value, instance=lambda: instance)


def test_start_drag_distance_when_class_none_then_reads_instance():
    assert start_drag_distance(app_class(10)) == 10
    assert start_drag_distance(app_class(25)) == 25


def test_start_drag_distance_when_instance_and_class_both_numbers_then_instance_wins():
    assert start_drag_distance(app_class(7, class_value=15)) == 7


def test_start_drag_distance_when_no_instance_then_class_value_then_default():
    assert start_drag_distance(app_class(0, class_value=7, has_instance=False)) == 7
    assert start_drag_distance(app_class(0, has_instance=False)) == DEFAULT_DRAG_DISTANCE


def test_start_drag_distance_when_class_has_no_instance_method_then_class_value():
    assert start_drag_distance(SimpleNamespace(startDragDistance=4)) == 4
    assert start_drag_distance(SimpleNamespace()) == DEFAULT_DRAG_DISTANCE


def test_start_drag_distance_when_instance_value_not_int_then_skipped():
    assert start_drag_distance(app_class(None, class_value=6)) == 6
    assert start_drag_distance(app_class(True, class_value=None)) == DEFAULT_DRAG_DISTANCE


@pytest.mark.parametrize("name", HANDLES)
def test_handles_use_the_shared_instance_lookup(name):
    import inspect

    source = inspect.getsource(import_module(BASE + name))
    assert "start_drag_distance(gui.QApplication)" in source
    assert 'value(gui.QApplication, "startDragDistance")' not in source


from test_studio_labs_e04_e06 import real_qt  # noqa: E402,F401  (fixture)

LABELS = HANDLES


@pytest.mark.parametrize("name", LABELS)
@pytest.mark.parametrize("move,starts", [(9, False), (10, True), (25, True)])
def test_drag_handle_when_class_attribute_none_then_threshold_from_instance(real_qt, name, move, starts):
    qt, app = real_qt
    real = qt.QtGui.QApplication

    class FontLabApplication(real):
        startDragDistance = None  # PythonQt class attribute; the instance holds 10

    qt.QtGui.QApplication = FontLabApplication
    module = import_module(BASE + name)
    facts = SimpleNamespace(rows=(SimpleNamespace(name="A", unicodes=(65,)),))
    panel = module.panel_type(qt, lambda *args: facts)()
    calls = []
    panel.drag_output = lambda: calls.append(1)
    left = qt.QtCore.Qt.LeftButton
    point = lambda x: SimpleNamespace(x=lambda: x, y=lambda: 0)
    panel.export.mousePressEvent(SimpleNamespace(pos=lambda: point(0), button=lambda: left))
    panel.export.mouseMoveEvent(SimpleNamespace(pos=lambda: point(move), buttons=lambda: left))
    assert bool(calls) is starts
    panel.close()
