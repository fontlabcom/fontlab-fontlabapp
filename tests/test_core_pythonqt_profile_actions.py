# this_file: tests/test_core_pythonqt_profile_actions.py
"""Preview actions retain exact profile result names and unsaved draft guards."""
from types import SimpleNamespace as NS

import pytest

from fontlabapp.fontui.core_pythonqt_labs.profiles.e01_e03_actions import names, bindings


@pytest.mark.parametrize('title,child,wanted', [
    ('Glyph Name Filter', NS(visible_names=('B', 'A')), ('B', 'A')),
    ('Glyph Name Pattern Lab', NS(result={'glyph_matches': [{'name': 'A'}]}), ('A',)),
    ('Glyph Name Pattern Lab', NS(result=None), ()),
    ('Glyph Metrics and Revisions', NS(facts=NS(advances=(('A', 'R', 50),))), ('A',)),
    ('Glyph Metrics and Revisions', NS(facts=None), ()),
    ('Glyph Spacing Offset', NS(facts=NS(rows=(NS(name='B'),))), ('B',)),
    ('Glyph Spacing Offset', NS(facts=None), ()),
    ('Glyph Spacing Worksheet', NS(snapshot=NS(rows=(NS(glyph_name='C'),))), ('C',)),
    ('Glyph Spacing Worksheet', NS(snapshot=None), ()),
    ('Glyph Metrics Model', NS(snapshot=NS(rows=(NS(name='D'),))), ('D',)),
    ('Glyph Metrics Form', NS(snapshot=None), ()),
    ('Font Units Calculator', NS(), ()),
    ('Expandable Glyph Search', NS(_capture=lambda: (('A', (65,)), ('B', (66,))), query=NS(text='a'), case=NS(checked=False), exact=NS(checked=False), reverse=NS(checked=False)), ('A',)),
])
def test_preview_names_when_profile_result_then_publish_exact_identity(title, child, wanted):
    assert names(child, title) == wanted


def test_bindings_when_draft_edited_then_refresh_guard_and_preview_are_explicit():
    published, events = [], []
    child = NS(refresh=lambda: events.append('refresh'), preview=lambda: events.append('preview'),
               editor=NS(model=NS(edited=True)), snapshot=NS(rows=(NS(name='A', advance=500),)),
               advance_box=NS(value=550))
    actions = bindings(child, 'Editable Glyph Tree', published.append)
    assert actions['dirty']()
    child.editor = None
    assert not actions['dirty']()
    actions = bindings(child, 'Glyph Metrics Form', published.append)
    assert actions['dirty']()
    actions['preview']()
    assert published == [('A',)] and events == ['preview']
    child.advance_box.value = 500
    assert not actions['dirty']()
    child.snapshot = None
    assert not actions['dirty']()
    actions = bindings(child, 'Font Units Calculator', published.append)
    actions['refresh']()
    actions['preview']()
    assert events == ['preview', 'preview', 'preview']
    assert not actions['dirty']()
    actions = bindings(NS(refresh=lambda: events.append('refresh'), visible_names=('B',)), 'Glyph Name Filter', published.append)
    actions['refresh']()
    actions['preview']()
    assert events[-1] == 'refresh' and published[-1] == ('B',)


def test_tree_binding_without_editor_retains_empty_source_mapping():
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e01_e03_actions import bind_tree
    child = NS(editor=None, refresh=lambda: None)
    assert bind_tree(child) is child
    child.refresh()
    assert child.preview_names == {}


def test_dirty_when_pending_is_hook_method_then_not_staged_edits():
    """Apply Unicode Map's SelectionPanel.pending is a method: always truthy, never a flag."""
    from types import SimpleNamespace as NS

    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09_actions import bindings

    panel = NS(
        preview=lambda: None, refresh=lambda: None, names=(), rows=[], is_ready=lambda row: False,
        apply=lambda: None, pending=lambda todo: None, dirty=False,
    )
    panel.refresh_names = lambda: None
    actions = bindings(panel, "Apply Unicode Map", lambda text: None)
    assert actions["dirty"]() is False, "a bound pending() method must not count as staged edits"
    panel.pending = True
    assert actions["dirty"]() is True, "a real pending flag still counts"
    panel.pending, panel.dirty = False, True
    assert actions["dirty"]() is True, "a real dirty flag still counts"


def test_bindings_when_panel_has_status_label_then_status_action_reads_its_text():
    """The shell shows the panel's refusal text after Apply (A2 report 14 E08 finding)."""
    from types import SimpleNamespace as NS

    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09_actions import bindings

    panel = NS(
        preview=lambda: None, refresh=lambda: None, names=(), rows=[], is_ready=lambda row: True,
        apply=lambda: None, pending=lambda todo: None, dirty=False,
        status=NS(text=lambda: "Close the Glyph windows first."),
    )
    panel.refresh_names = lambda: None
    actions = bindings(panel, "Apply Unicode Map", lambda text: None)
    assert actions["status"]() == "Close the Glyph windows first."
    del panel.status
    assert "status" not in bindings(panel, "Apply Unicode Map", lambda text: None)
