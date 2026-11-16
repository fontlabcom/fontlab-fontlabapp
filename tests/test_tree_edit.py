# this_file: tests/test_tree_edit.py
"""Editable-tree contracts independent of any Qt or FontLab binding."""

import pytest

from fontlabapp.qt.trees.data import Tree
from fontlabapp.qt.trees.draft import DraftTree


@pytest.fixture
def draft():
    return DraftTree(
        Tree(
            ("Glyph", "Value"),
            (
                (-1, ("A", "")),
                (0, ("Unicode", "U+0041")),
                (1, ("Detail", "nested")),
                (-1, ("B", "")),
            ),
        )
    )


def state(draft):
    return tuple(
        (node, draft.parent(node), draft.cells(node), draft.children(node))
        for node in draft.identities()
    )


def test_snapshot_is_copied_with_stable_occurrences_and_uniform_cells(draft):
    assert draft.cells(0) == ("Glyph", "Value")
    assert draft.children(0) == (1, 4)
    assert draft.children(1) == (2,)
    assert draft.parent(3) == 2
    assert draft.position(4) == 1
    assert draft.column_count == 2
    assert draft.identities() == (0, 1, 2, 3, 4)
    ragged = DraftTree(Tree(("a", "b"), ((-1, ("x",)),)))
    assert ragged.cells(1) == ("x", "")


def test_text_edits_and_headers_do_not_change_other_cells_or_source(draft):
    draft.set_cell(2, 1, "U+0042")
    draft.set_cell(0, 0, "Name")
    assert draft.cells(2) == ("Unicode", "U+0042")
    assert draft.cells(1) == ("A", "")
    assert draft.cells(0) == ("Name", "Value")


def test_insert_siblings_before_or_after_and_append_child_are_distinct(draft):
    before = draft.insert_rows(0, draft.position(4), 1, ("New entry", ""))
    after = draft.insert_rows(0, draft.position(4) + 1, 1, ("[No data]",) * 2)
    child = draft.insert_rows(1, len(draft.children(1)), 1, ("Child", ""))
    assert draft.children(0) == (1, before[0], 4, after[0])
    assert draft.children(1) == (2, child[0])
    assert draft.cells(after[0]) == ("[No data]", "[No data]")
    assert draft.parent(child[0]) == 1


def test_insert_rows_are_independent_and_deleted_handles_are_never_reused(draft):
    ids = draft.insert_rows(1, 0, 2, ("New", ""))
    draft.set_cell(ids[0], 0, "Changed")
    assert draft.cells(ids[1]) == ("New", "")
    draft.remove_rows(1, 0, 2)
    new = draft.insert_rows(1, 0, 1, ("New", ""))[0]
    assert new > max(ids)
    for old in ids:
        with pytest.raises(ValueError, match="Unknown tree node"):
            draft.cells(old)


def test_remove_rows_removes_all_descendants_and_preserves_other_occurrences(draft):
    assert draft.remove_rows(0, 0, 1) == (1, 2, 3)
    assert draft.identities() == (0, 4)
    assert draft.children(0) == (4,)
    assert draft.position(4) == 0
    assert draft.cells(4) == ("B", "")


def test_insert_columns_at_zero_preserves_hierarchy_and_occurrence_ids(draft):
    hierarchy = tuple(
        (i, draft.children(i), draft.parent(i)) for i in draft.identities()
    )
    draft.insert_columns(0, 2, "Column")
    assert draft.cells(0) == ("Column", "Column", "Glyph", "Value")
    assert draft.cells(3) == ("", "", "Detail", "nested")
    assert hierarchy == tuple(
        (i, draft.children(i), draft.parent(i)) for i in draft.identities()
    )
    draft.remove_columns(0, 2)
    assert draft.cells(3) == ("Detail", "nested")


def test_zero_columns_preserve_part2_nodes_and_part3_can_remove_them(draft):
    draft.remove_columns(0, 2)
    assert draft.column_count == 0
    assert draft.children(0) == (1, 4)
    assert draft.cells(3) == ()
    draft.insert_columns(0, 1, "[No header]")
    assert draft.cells(3) == ("",)
    draft.remove_rows(0, 0, 2)
    assert draft.identities() == (0,)


def test_empty_font_accepts_root_insertion_and_no_data_is_local():
    source = Tree(("a", "b"), ())
    draft = DraftTree(source)
    new = draft.insert_rows(0, 0, 1, ("", ""))
    assert draft.children(0) == new
    assert source.rows == ()


def test_equal_text_rows_are_independent_and_keep_the_original_snapshot():
    source = Tree(("name",), ((-1, ("same",)), (-1, ("same",))))
    draft = DraftTree(source)
    draft.set_cell(1, 0, "changed")
    assert draft.cells(2) == ("same",)
    assert source.rows == ((-1, ("same",)), (-1, ("same",)))
    with pytest.raises(ValueError):
        draft.insert_rows(0, 100, 1, ("bad",))
    assert draft.insert_rows(0, 2, 1, ("third",)) == (3,)


def test_zero_column_rows_can_be_inserted_and_restored(draft):
    draft.remove_columns(0, 2)
    created = draft.insert_rows(1, 1, 1, ())
    assert draft.cells(created[0]) == ()
    draft.insert_columns(0, 1)
    assert draft.cells(created[0]) == ("",)
    assert draft.parent(created[0]) == 1


@pytest.mark.parametrize("bad", [None, (), "text", 1, {}])
def test_constructor_requires_complete_tree(bad):
    with pytest.raises(TypeError, match="complete Tree"):
        DraftTree(bad)


def test_constructor_rejects_extra_cells_instead_of_truncating():
    with pytest.raises(ValueError, match="more cells"):
        DraftTree(Tree(("a",), ((-1, ("x", "lost")),)))


@pytest.mark.parametrize("node", [-1, 999, None, True, "1"])
def test_unknown_or_mistyped_node_is_rejected_without_changes(draft, node):
    before = state(draft)
    for action in [
        lambda: draft.cells(node),
        lambda: draft.children(node),
        lambda: draft.parent(node),
        lambda: draft.position(node),
        lambda: draft.set_cell(node, 0, "x"),
        lambda: draft.insert_rows(node, 0, 1, ("x", "")),
        lambda: draft.remove_rows(node, 0, 1),
    ]:
        with pytest.raises(ValueError, match="Unknown tree node"):
            action()
        assert state(draft) == before


@pytest.mark.parametrize(
    "position,count",
    [(-1, 1), (3, 1), (0, 0), (0, -1), (None, 1), (0, True), (False, 1), (0, 10**100)],
)
def test_bad_row_insertions_are_atomic(draft, position, count):
    before = state(draft)
    with pytest.raises(ValueError):
        draft.insert_rows(0, position, count, ("x", ""))
    assert state(draft) == before


@pytest.mark.parametrize(
    "position,count",
    [(-1, 1), (2, 1), (0, 0), (0, -1), (None, 1), (0, True), (0, 10**100)],
)
def test_bad_row_removals_are_atomic(draft, position, count):
    before = state(draft)
    with pytest.raises(ValueError):
        draft.remove_rows(0, position, count)
    assert state(draft) == before


@pytest.mark.parametrize("cells", [None, ["x", ""], ("x",), ("x", 1)])
def test_new_row_cells_require_exact_text_columns(draft, cells):
    before = state(draft)
    with pytest.raises(TypeError):
        draft.insert_rows(0, 0, 1, cells)
    assert state(draft) == before


@pytest.mark.parametrize(
    "column,value", [(-1, "x"), (2, "x"), (True, "x"), (None, "x"), (0, None), (0, 1)]
)
def test_invalid_cell_edit_is_atomic(draft, column, value):
    before = state(draft)
    with pytest.raises((TypeError, ValueError)):
        draft.set_cell(1, column, value)
    assert state(draft) == before


@pytest.mark.parametrize("method", ["insert_columns", "remove_columns"])
@pytest.mark.parametrize(
    "position,count",
    [(-1, 1), (3, 1), (0, 0), (0, -1), (None, 1), (0, True), (0, 10**100)],
)
def test_bad_column_changes_are_atomic(draft, method, position, count):
    before = state(draft)
    with pytest.raises(ValueError):
        getattr(draft, method)(position, count)
    assert state(draft) == before


def test_header_text_validation_is_atomic(draft):
    before = state(draft)
    with pytest.raises(TypeError):
        draft.insert_columns(0, 1, None)
    assert state(draft) == before


def test_root_position_is_not_a_row(draft):
    with pytest.raises(ValueError, match="root"):
        draft.position(0)
    assert draft.parent(0) is None


def test_deep_removal_is_iterative():
    draft = DraftTree(Tree(("name",), tuple((i - 1, (str(i),)) for i in range(3000))))
    assert len(draft.remove_rows(0, 0, 1)) == 3000
    assert draft.identities() == (0,)


def test_cell_limit_refuses_whole_operation_without_partial_changes(draft, monkeypatch):
    import fontlabapp.qt.trees.draft as module

    before = state(draft)
    monkeypatch.setattr(module, "MAX_CELLS", 10)
    with pytest.raises(ValueError, match="limit"):
        draft.insert_rows(0, 0, 1, ("x", ""))
    with pytest.raises(ValueError, match="limit"):
        draft.insert_columns(0, 1)
    assert state(draft) == before
    with pytest.raises(ValueError, match="limit"):
        DraftTree(Tree(("a", "b"), tuple((-1, ("x",)) for _ in range(6))))


def test_explicit_variant_value_boundary_and_fork_keep_opaque_values_by_identity(draft):
    class Opaque:
        def __deepcopy__(self, memo):
            raise AssertionError("Opaque cell values must never be copied or executed")

    value = Opaque()
    draft.set_value(1, 0, value)
    draft.set_value(2, 1, None)
    copy = draft.fork()
    assert copy.cells(1)[0] is value and copy.cells(2)[1] is None
    copy.set_value(2, 1, 123)
    copy.remove_rows(0, 1, 1)
    assert draft.children(0) == (1, 4) and draft.cells(2)[1] is None
    assert copy.cells(2)[1] == 123
    draft.set_cell(2, 1, "text")
    assert copy.cells(2)[1] == 123
