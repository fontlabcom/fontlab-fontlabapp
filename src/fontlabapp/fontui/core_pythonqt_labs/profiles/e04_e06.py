# this_file: src/fontlabapp/fontui/core_pythonqt_labs/profiles/e04_e06.py
# SPDX-License-Identifier: Apache-2.0
"""Embed every calendar, completion and drag/drop teaching profile unchanged."""
from functools import partial
from importlib import import_module


def calendar(parent, *, official=False):
    """Build the original calendar controls with their distinct date policies."""
    from fontlabapp.glyphs.calendar.ui import GlyphCalendarDialog
    from fontlabapp.glyphs.catalog.native import capture

    return GlyphCalendarDialog(parent, capture, official=official)


def completion(parent, *, official=False):
    """Build the original completion editor, including its focus/IME policy."""
    from fontlabapp.glyphs.completion.ui import GlyphCompletionDialog
    from fontlabapp.glyphs.catalog.native import capture

    return GlyphCompletionDialog(parent, capture, official=official)


def calendar_proof(parent):
    """Build the explicit-generation calendar proof without opening a window."""
    import PythonQt as qt
    from .calendar_proof import show

    return show(qt, parent, embedded=True)


def drop(parent, *, name):
    """Build the complete drop profile, preserving its own staged MIME state."""
    import PythonQt as qt
    from fontlabapp.glyphs.character_map.capture import capture

    module = import_module('.' + name, __package__)
    source = module.open_in_fontlab if name == 'font_file_drop_shelf' else capture
    return module.panel_type(qt, source)(parent)


PROFILES = {
    'E04': (
        ('Glyph Modification Calendar', calendar),
        ('Glyph Modification Calendar with Formats', partial(calendar, official=True)),
        ('Calendar Proof Builder', calendar_proof),
    ),
    'E05': (
        ('Glyph Name Completion', completion),
        ('Glyph Name Completion with Focus', partial(completion, official=True)),
    ),
    'E06': (
        ('Deferred Glyph Report Drag', partial(drop, name='deferred_glyph_report')),
        ('Draggable Glyph Names', partial(drop, name='draggable_glyph_names')),
        ('Font Drop Inspector', partial(drop, name='font_drop_inspector')),
        ('Font File Drop Shelf', partial(drop, name='font_file_drop_shelf')),
        ('Glyph Pair Board', partial(drop, name='glyph_pair_board')),
        ('Proof Word Magnets', partial(drop, name='proof_word_magnets')),
    ),
}


def bindings(child, title, publish):
    """Connect real profile state to shell actions without refreshing away drafts."""
    from fontlabapp.qt.properties import value

    if title.startswith('Glyph Modification Calendar'):
        from fontlabapp.glyphs.calendar.model import on_day

        def preview():
            day = str(value(child.controls.calendar, 'selectedDate').toString('yyyy-MM-dd'))
            publish(tuple(row[0] for row in on_day(child._snapshot, day).rows))

        return {'refresh': child.refresh, 'preview': preview}
    if title == 'Calendar Proof Builder':
        return {'preview': lambda: publish(str(value(child.editor, 'plainText')))}
    if title.startswith('Glyph Name Completion'):
        return {'refresh': child.refresh,
                'preview': lambda: publish(str(value(child.controls.widget, 'plainText')))}
    if title == 'Font File Drop Shelf':
        return {}
    if title == 'Deferred Glyph Report Drag':
        return {'refresh': child.refresh,
                'preview': lambda: publish(tuple(row.name for row in child.facts.rows))}
    if title == 'Draggable Glyph Names':
        return {'refresh': child.refresh,
                'preview': lambda: publish(str(value(child.output, 'plainText'))),
                'dirty': lambda: bool(str(value(child.entry, 'text')))}
    if title == 'Font Drop Inspector':
        return {'refresh': child.refresh,
                'preview': lambda: publish(child.proof_text),
                'dirty': lambda: bool(str(value(child.entry, 'text')))}
    return {'refresh': child.refresh,
            'preview': lambda: publish(str(value(child.output, 'plainText'))),
            'dirty': lambda: bool(value(child.items, 'count') or str(value(child.entry, 'text')))}
