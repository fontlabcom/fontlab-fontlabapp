# this_file: src/fontlabapp/qt/tables/selection.py
"""Injected Qt table row selection; retain both native selection mechanisms.

Call on the widget's UI thread. Callers own callback guards, selection policy,
widget lifetime and exception handling. No binding, font or foreign API imports.
The model path keeps input order/duplicates and checks current bounds per row;
the range path preserves integer conversion, deduplication and sorted ranges.
Neither path blocks native signals or changes a widget's selection mode.
"""
from collections.abc import Callable, Iterable
from typing import Any


def select_model_rows(
    widget: Any, rows: Iterable[int], flags: Any,
    row_count: Callable[[], int], *, extend: bool = False,
) -> None:
    """Apply Select|Rows; replace or extend without Qt's selectRow replacement.

    Read row_count per nonnegative row after acquiring the model and selection
    model. Preserve native callback timing, duplicates and propagated errors.
    """
    if not extend:
        widget.clearSelection()
    model, selection = widget.model(), widget.selectionModel()
    for row in rows:
        if 0 <= row < row_count():
            selection.select(model.index(row, 0), flags.Select | flags.Rows)


def selected_model_rows(widget: Any) -> list[int]:
    """Return sorted unique full-row selections from the native selection model."""
    return sorted({index.row() for index in widget.selectionModel().selectedRows()})


def select_table_ranges(
    widget: Any, indexes: Iterable[Any], column_count: Callable[[], int],
    range_factory: Callable[[], Callable[..., Any]],
) -> None:
    """Replace with full-column table ranges; keep unfiltered converted rows.

    Clear first, then read the current column count and range type, then consume indexes.
    Native range construction and selection errors propagate without rollback.
    A zero column count deliberately passes a final column of -1, as before.
    """
    widget.clearSelection()
    last = column_count() - 1
    range_class = range_factory()
    for row in sorted({int(i) for i in indexes}):
        widget.setRangeSelected(range_class(row, 0, row, last), True)


def selected_range_rows(widget: Any) -> list[int]:
    """Expand overlapping inclusive native table ranges into sorted unique rows."""
    rows = set()
    for selected in widget.selectedRanges():
        rows.update(range(selected.topRow(), selected.bottomRow() + 1))
    return sorted(rows)
