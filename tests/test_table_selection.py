# this_file: tests/test_table_selection.py
"""Preserve native selection ordering, both strategies and failure propagation."""
from types import SimpleNamespace as NS

import pytest
import fontlabapp.qt.tables.selection as shared


class Widget:
    def __init__(self, failure=None):
        self.events = []
        self.failure = failure

    def record(self, *event):
        self.events.append(event)
        if event[0] == self.failure:
            raise RuntimeError(event[0])

    def clearSelection(self):
        self.record('clear')

    def model(self):
        self.record('model')
        return self

    def selectionModel(self):
        self.record('selection')
        return self

    def index(self, row, column):
        self.record('index', row, column)
        return (row, column)

    def select(self, index, flags):
        self.record('select', index, flags)

    def count(self):
        self.record('count')
        return 3

    def columns(self):
        self.record('columns')
        return 2

    def range(self, *args):
        self.record('range', *args)
        return args

    def setRangeSelected(self, selection, selected):
        self.record('setRange', selection, selected)

    def selectedRows(self):
        self.record('selectedRows')
        return [NS(row=lambda row=row: row) for row in [2, 0, 2]]

    def selectedRanges(self):
        self.record('selectedRanges')
        return [NS(topRow=lambda: 2, bottomRow=lambda: 4),
                NS(topRow=lambda: 1, bottomRow=lambda: 2)]


@pytest.mark.parametrize('extend', [False, True])
@pytest.mark.parametrize('rows', [[], [2, 0, 2], [-1, 3, 999], [-1, 2, 0, 3]])
def test_model_selection_preserves_order_duplicates_bounds_and_extension(rows, extend):
    widget = Widget()
    shared.select_model_rows(widget, rows, NS(Select=1, Rows=32), widget.count, extend=extend)
    expected = [] if extend else [('clear',)]
    expected += [('model',), ('selection',)]
    for row in rows:
        if row >= 0:
            expected += [('count',)]
        if 0 <= row < 3:
            expected += [('index', row, 0), ('select', (row, 0), 33)]
    assert widget.events == expected


@pytest.mark.parametrize('rows', [[], [2, 0, 2], [-1, 3, 999], ['2', 0.5, '2']])
def test_range_selection_preserves_conversion_dedup_sort_and_unfiltered_rows(rows):
    widget = Widget()
    shared.select_table_ranges(widget, rows, widget.columns, lambda: widget.range)
    expected = [('clear',), ('columns',)]
    for row in sorted({int(i) for i in rows}):
        expected += [('range', row, 0, row, 1), ('setRange', (row, 0, row, 1), True)]
    assert widget.events == expected


@pytest.mark.parametrize('failure', ['clear', 'model', 'selection', 'count', 'index', 'select'])
def test_model_native_errors_propagate_at_original_operation(failure):
    widget = Widget(failure)
    with pytest.raises(RuntimeError, match=failure):
        shared.select_model_rows(widget, [0, 2], NS(Select=1, Rows=32), widget.count)
    assert widget.events[-1][0] == failure


@pytest.mark.parametrize('failure', ['clear', 'columns', 'range', 'setRange'])
def test_range_native_errors_propagate_at_original_operation(failure):
    widget = Widget(failure)
    with pytest.raises(RuntimeError, match=failure):
        shared.select_table_ranges(widget, [0, 2], widget.columns, lambda: widget.range)
    assert widget.events[-1][0] == failure


def test_invalid_range_input_is_converted_after_clear_and_column_read():
    widget = Widget()
    with pytest.raises(ValueError):
        shared.select_table_ranges(widget, ['invalid'], widget.columns, lambda: widget.range)
    assert widget.events == [('clear',), ('columns',)]


def test_reads_preserve_each_native_representation_without_mutation():
    widget = Widget()
    assert shared.selected_model_rows(widget) == [0, 2]
    assert shared.selected_range_rows(widget) == [1, 2, 3, 4]
    assert widget.events == [('selection',), ('selectedRows',), ('selectedRanges',)]


def test_empty_reads_and_zero_columns_are_not_reinterpreted():
    widget = Widget()
    widget.selectedRows = lambda: []
    widget.selectedRanges = lambda: []
    assert shared.selected_model_rows(widget) == []
    assert shared.selected_range_rows(widget) == []
    shared.select_table_ranges(widget, [1], lambda: 0, lambda: widget.range)
    assert widget.events[-2:] == [('range', 1, 0, 1, -1), ('setRange', (1, 0, 1, -1), True)]
