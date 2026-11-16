# this_file: tests/test_fontui_table.py
"""GlyphTable on real offscreen Qt: sorting, resizing, filtering and the selection signal."""

from _studio_qt import studio_qt  # noqa: F401 - fixture

ROWS = [("B", "Regular", (20,)), ("A", "Regular", (100,)), ("C", "Bold", (3,))]


def make(studio_qt, rows=ROWS):  # noqa: F811
    table = studio_qt.modules.table.GlyphTable(["Glyph", "Width"])
    studio_qt.owned.append(table)
    table.set_rows(rows)
    return table


def names(table):
    return [table.proxy.index(r, 0).data() for r in range(table.proxy.rowCount())]


def test_table_when_header_sorted_then_numbers_sort_as_numbers(studio_qt):  # noqa: F811
    table = make(studio_qt)
    assert table.view.isSortingEnabled()
    table.view.sortByColumn(1, studio_qt.QtCore.Qt.AscendingOrder)
    assert names(table) == ["C", "B", "A"]
    table.view.sortByColumn(0, studio_qt.QtCore.Qt.DescendingOrder)
    assert names(table) == ["C", "B", "A"]


def test_table_when_columns_dragged_then_sections_resize(studio_qt):  # noqa: F811
    table = make(studio_qt)
    header = table.view.horizontalHeader()
    gui = studio_qt.modules.table.QtGui
    assert header.sectionResizeMode(0) == gui.QHeaderView.Interactive
    header.resizeSection(0, 137)
    assert header.sectionSize(0) == 137


def test_table_when_filtered_then_only_matching_rows_show(studio_qt):  # noqa: F811
    table = make(studio_qt)
    table.filter_box.setText("c")
    assert names(table) == ["C"]
    table.filter_box.setText("")
    assert len(names(table)) == 3


def test_table_when_row_selected_then_emits_glyph_and_layer(studio_qt):  # noqa: F811
    table = make(studio_qt)
    seen = []
    table.row_selected.connect(lambda name, layer: seen.append((name, layer)))
    table.view.sortByColumn(1, studio_qt.QtCore.Qt.AscendingOrder)
    table.view.setCurrentIndex(table.proxy.index(0, 0))
    assert seen == [("C", "Bold")]
    assert table.select("A", "Regular")
    assert seen[-1] == ("A", "Regular")
    assert not table.select("Z")


def test_table_when_rows_replaced_then_old_rows_go(studio_qt):  # noqa: F811
    table = make(studio_qt)
    table.set_rows([("X", None, (1,))])
    assert names(table) == ["X"]
    assert table.rows[0].layer is None


def test_table_when_closed_then_slots_released_and_no_emit(studio_qt):  # noqa: F811
    table = make(studio_qt)
    seen = []
    slot = lambda *a: seen.append(a)  # noqa: E731
    table.row_selected.connect(slot)
    table.row_selected.disconnect(slot)
    table.row_selected.connect(slot)
    table.close()
    assert table.row_selected.slots == []
    table._current_changed(table.proxy.index(0, 0))
    assert seen == []


def test_table_when_resorted_then_selection_keeps_captured_glyph_and_layer(studio_qt):  # noqa: F811 - imported fixture
    table = make(studio_qt)
    assert table.select("C", "Bold")
    table.view.sortByColumn(1, studio_qt.QtCore.Qt.DescendingOrder)
    index = table.proxy.mapToSource(table.view.currentIndex())
    assert table.rows[index.row()].glyph_name == "C"
    assert table.rows[index.row()].layer == "Bold"


def test_table_when_layer_column_then_layer_is_second_cell_and_values_follow(studio_qt):  # noqa: F811
    table = studio_qt.modules.table.GlyphTable(
        ["Glyph", "Master", "LSB", "Note"], None, True
    )
    studio_qt.owned.append(table)
    table.set_rows([("A", "Bold", ("5 -> 7", "n")), ("B", None, ("1", ""))])
    cells = [
        [table.model.item(r, c).text() for c in range(4)] for r in range(2)
    ]
    assert cells == [["A", "Bold", "5 -> 7", "n"], ["B", "", "1", ""]], (
        "Master column holds the layer; LSB and Note hold their own values"
    )


def test_table_when_no_layer_column_then_layer_stays_hidden(studio_qt):  # noqa: F811
    table = make(studio_qt)
    assert table.model.item(0, 1).text() == "20", "values fill the column after Glyph"
