# this_file: src/fontlabapp/fontui/core_pythonqt_labs/profiles/e01_e03_actions.py
# SPDX-License-Identifier: Apache-2.0
"""Shell actions publish exact names from each retained profile's current model."""
from typing import Any

from fontlabapp.qt.properties import value

FILTERS = frozenset(('Glyph Sorting and Filtering', 'Glyph Sorting and Filtering with Dates',
                     'Glyph Filter Model with Date Range', 'Glyph Filter Model with Local Dates'))
TREES = frozenset(('Glyph Metadata Tree', 'Glyph Metadata Outline', 'Editable Glyph Tree', 'Editable Glyph Outline'))


def bind_tree(child: Any) -> Any:
    """Pin source names to immutable occurrence IDs before local cell edits."""
    original = child.refresh

    def remember() -> None:
        draft = child.editor.model._draft if child.editor is not None else None
        child.preview_names = {} if draft is None else {
            identity: str(draft.cells(identity)[0]) for identity in draft.children(0)
        }

    def refresh(*args: Any, **kwargs: Any) -> None:
        previous = child.editor
        original(*args, **kwargs)
        if child.editor is not previous:
            remember()

    remember()
    child.refresh = refresh
    return child


def names(child: Any, title: str) -> tuple[str, ...]:
    """Read the visible model, keeping source identities after sorting/filtering."""
    if title in FILTERS:
        model = child.proxy
        return tuple(str(model.data(model.index(row, 0))) for row in range(model.rowCount()))
    if title in TREES:
        view = child.editor.view if title.startswith('Editable') else child.view
        index = value(view, 'currentIndex')
        if not index.isValid():
            return ()
        while index.parent().isValid():
            index = index.parent()
        if title.startswith('Editable'):
            name = child.preview_names.get(int(index.internalId()))
            return (name,) if name is not None else ()
        return (str(index.sibling(index.row(), 0).data()),)
    if title == 'Glyph Name Filter':
        return tuple(child.visible_names)
    if title == 'Glyph Name Pattern Lab':
        return tuple(row['name'] for row in (child.result or {}).get('glyph_matches', ()))
    if title == 'Expandable Glyph Search':
        from .expandable_search import search
        return search(tuple(row[0] for row in child._capture()), value(child.query, 'text'),
                      value(child.case, 'checked'), value(child.exact, 'checked'), value(child.reverse, 'checked'))
    if title.startswith('Glyph Metrics and Revisions'):
        return tuple(row[0] for row in child.facts.advances) if child.facts else ()
    if title.startswith('Glyph Spacing Offset'):
        return tuple(row.name for row in child.facts.rows) if child.facts else ()
    if title.startswith('Glyph Spacing Worksheet'):
        return tuple(row.glyph_name for row in child.snapshot.rows) if child.snapshot else ()
    if title == 'Glyph Metrics Model' and hasattr(child, 'lab_proxy'):
        model = child.lab_proxy
        return tuple(str(model.data(model.index(row, 0))) for row in range(model.rowCount()))
    if title in ('Glyph Metrics Model', 'Glyph Metrics Form'):
        return tuple(row.name for row in child.snapshot.rows) if child.snapshot else ()
    return ()


def bindings(child: Any, title: str, publish: Any) -> dict[str, Any]:
    """Connect explicit read-only shell actions; original controls keep their guards."""
    refresh = child.preview if title in ('Expandable Glyph Search', 'Font Units Calculator') else child.refresh

    def preview() -> None:
        if title in ('Expandable Glyph Search', 'Font Units Calculator', 'Glyph Metrics Form'):
            child.preview()
        publish(names(child, title))

    def dirty() -> bool:
        if title.startswith('Editable Glyph'):
            return child.editor is not None and child.editor.model.edited
        if title == 'Glyph Metrics Form' and child.snapshot and child.snapshot.rows:
            return value(child.advance_box, 'value') != child.snapshot.rows[0].advance
        return False

    return {'refresh': refresh, 'preview': preview, 'dirty': dirty}
