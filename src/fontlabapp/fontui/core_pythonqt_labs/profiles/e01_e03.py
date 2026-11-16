# this_file: src/fontlabapp/fontui/core_pythonqt_labs/profiles/e01_e03.py
# SPDX-License-Identifier: Apache-2.0
"""Embedded constructors for the twenty filtering, tree and metrics profiles.

Importing the registry is host-free. Each constructor retains the original
capture, distinct model policy and lifetime; no standalone launcher is called.
"""
from functools import partial
from importlib import import_module
from typing import Any


def _construct(module: str, name: str, parent: Any, *args: Any, **kwargs: Any) -> Any:
    return getattr(import_module(module), name)(parent, *args, **kwargs)


def _filter(parent: Any, custom: bool, official: bool) -> Any:
    from fontlabapp.glyphs.catalog.native import capture
    from fontlabapp.qt.properties import value
    child = _construct('fontlabapp.qt.tables.filter.ui', 'FilterTableDialog', parent,
                      'Glyph Filtering', f'lab_filter_{custom}_{official}', capture,
                      custom, 'Filter and sort captured glyph metadata; cells are read-only.',
                      official=official)
    # Reparenting discards top-level resize; retain the measured eight-row footprint.
    child.setMinimumSize(value(child, "size"))
    return child


def _tree(parent: Any, editable: bool, outline: bool) -> Any:
    from fontlabapp.glyphs.tree.model import capture
    if editable:
        from .e01_e03_actions import bind_tree
        return bind_tree(_construct('fontlabapp.glyphs.tree.editable.ui', 'EditableGlyphTreeDialog',
                          parent, capture, official=not outline))
    return _construct('fontlabapp.glyphs.tree.ui', 'GlyphTreeDialog', parent,
                      'Glyph Metadata', f'lab_tree_{outline}', capture, outline)


def _panel(module: str, capture_module: str, parent: Any, *args: Any, **kwargs: Any) -> Any:
    from fontlabapp import _native
    qt = _native('PythonQt')
    kind = import_module(module).panel_type(qt.QtCore, qt.QtGui)
    capture = import_module(capture_module).capture
    return kind(parent, capture, *args, **kwargs)


def _lesson(name: str, parent: Any) -> Any:
    from fontlab_python_lessons.ui import dialog_type
    from .lesson_lists import configure
    return configure(dialog_type(name)(parent), name)


def _pattern(parent: Any) -> Any:
    from fontlabapp import _native
    from fontlabapp.glyphs.pattern import _capture
    from fontlabapp.qt.regexp.ui import panel_type
    qt = _native('PythonQt')
    return panel_type(qt.QtCore, qt.QtGui)(parent, _capture)


PROFILES = {
    'E01': (
        ('Glyph Name Filter', partial(_lesson, 'glyph-name-filter')),
        ('Glyph Sorting and Filtering', partial(_filter, custom=False, official=False)),
        ('Glyph Sorting and Filtering with Dates', partial(_filter, custom=True, official=False)),
        ('Glyph Filter Model with Date Range', partial(_filter, custom=True, official=True)),
        ('Glyph Filter Model with Local Dates', partial(_filter, custom=False, official=True)),
        ('Expandable Glyph Search', partial(_construct, __package__ + '.expandable_search', 'build')),
        ('Glyph Name Pattern Lab', _pattern),
    ),
    'E02': (
        ('Glyph Metadata Tree', partial(_tree, editable=False, outline=False)),
        ('Glyph Metadata Outline', partial(_tree, editable=False, outline=True)),
        ('Editable Glyph Tree', partial(_tree, editable=True, outline=False)),
        ('Editable Glyph Outline', partial(_tree, editable=True, outline=True)),
    ),
    'E03': (
        ('Glyph Metrics Model', partial(_lesson, 'glyph-metrics-model')),
        ('Glyph Metrics Form', partial(_lesson, 'glyph-metrics-form')),
        ('Glyph Metrics and Revisions', partial(_panel, 'fontlabapp.proof.numeric.ui', 'fontlabapp.proof.numeric.launcher', part=2)),
        ('Glyph Metrics and Revisions - Detailed', partial(_panel, 'fontlabapp.proof.numeric.ui', 'fontlabapp.proof.numeric.launcher', part=3)),
        ('Glyph Spacing Offset', partial(_panel, 'fontlabapp.metrics.offset.ui', 'fontlabapp.metrics.offset.capture', part=2)),
        ('Glyph Spacing Offset - Stacked', partial(_panel, 'fontlabapp.metrics.offset.ui', 'fontlabapp.metrics.offset.capture', part=3)),
        ('Font Units Calculator', partial(_construct, __package__ + '.units_calculator', 'build')),
        ('Glyph Spacing Worksheet', partial(_panel, 'fontlabapp.metrics.worksheet.ui', 'fontlabapp.metrics.worksheet.capture', official=False)),
        ('Glyph Spacing Worksheet - Frameless', partial(_panel, 'fontlabapp.metrics.worksheet.ui', 'fontlabapp.metrics.worksheet.capture', official=True)),
    ),
}
