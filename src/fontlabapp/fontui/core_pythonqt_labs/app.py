# this_file: src/fontlabapp/fontui/core_pythonqt_labs/app.py
# SPDX-License-Identifier: Apache-2.0
"""Embed complete lesson profiles in the shared shell with a read-only preview."""
from importlib import import_module

from PythonQt import QtCore

from fontlabapp import fontui
from fontlabapp.core.scripting import current_package
from fontlabapp.fontui.lifecycle import Owned
from fontlabapp.studios import TabSpec

from .closing import CloseFilter

TITLES = {
    'E01': 'Model Filtering Lab', 'E02': 'Tree Models Lab',
    'E03': 'Metrics Controls Lab', 'E04': 'Calendar Lab',
    'E05': 'Completion Lab', 'E06': 'Drag Drop Lab',
    'E07': 'Proof Composition Lab', 'E08': 'Unicode Lab',
    'E09': 'Review Model Lab',
}


def profiles(lab_id):
    """Load only the requested lab family's constructors."""
    group = ('e01_e03', 'e04_e06', 'e07_e09')[(int(lab_id[1:]) - 1) // 3]
    return import_module(f'{__package__}.profiles.{group}').PROFILES[lab_id]


def bindings(lab_id, child, title, publish):
    group = ('e01_e03_actions', 'e04_e06', 'e07_e09')[(int(lab_id[1:]) - 1) // 3]
    return import_module(f'{__package__}.profiles.{group}').bindings(child, title, publish)


def target(package):
    """Identity and master of the captured native target, never a mutable row."""
    return None if package is None else (package.id, str(package.master))


def guarded(callback, package, expected):
    """Refuse current-font captures before and after crossing native readers."""
    def run(*args, **kwargs):
        if target(package()) != expected:
            raise ValueError('The active font or master changed. Reopen this lab for that target.')
        result = callback(*args, **kwargs)
        if target(package()) != expected:
            raise ValueError('The active font or master changed during capture. Reopen this lab.')
        return result
    return run


def publish(shell, payload, layer):
    """Send actual profile output to the captured, read-only preview."""
    if shell.preview is None:
        shell.set_status('Open a font and reopen the lab to preview this result.')
    elif shell.preview_kind == 'tmetrics':
        shell.preview.set_layer(layer)
        shell.preview.set_text(payload if isinstance(payload, str) else ' '.join('/' + name for name in payload))
    elif payload:
        shell.preview.load(payload[0], layer)


class Profile(Owned):
    """Own an existing lesson controller; preserve refused Close for retry."""

    def __init__(self, parent, child):
        super().__init__(parent)
        self.child = child
        widget = getattr(child, 'widget', child)
        widget.hide()
        widget.setParent(self.widget)
        widget.setWindowFlags(QtCore.Qt.Widget)
        self.layout.addWidget(widget)
        widget.show()

    def close(self):
        if not self._child_closed:
            if self.child.close() is False:
                raise RuntimeError('Lesson Close refused; retry Close')
            if not getattr(self.child, '_close_complete', True):
                raise RuntimeError('Lesson cleanup incomplete; retry Close')
            self._child_closed = True
        super().close()


def show(lab_id, *, profile=None, parent=None, font=None, package=None):
    """Keep all profile state across tab switches; previews never write font data."""
    if lab_id not in TITLES:
        raise ValueError(f'Unknown lab: {lab_id}')
    specs = profiles(lab_id)
    titles = [title for title, build in specs]
    if profile is not None and profile not in titles:
        raise ValueError(f'Unknown {lab_id} profile: {profile}')
    kind = 'tglyph' if lab_id in ('E02', 'E09') else 'tmetrics'
    package = package or current_package
    expected = target(package())
    active_font = fontui.current_font()
    if font is not None and active_font is not None and font is not active_font:
        raise ValueError('The supplied font is not the active font. Activate it before opening this lab.')
    shell = fontui.app_shell(TITLES[lab_id], kind, parent=parent, package=package)
    try:
        captured = active_font if font is None else font
        if captured is not None:
            factory = fontui.glyph_view if kind == 'tglyph' else fontui.metrics_preview
            shell.set_preview(factory(captured, shell.widget, controls=True,
                                      read_only=True, hint_check=shell.hint_check,
                                      layer=expected[1] if expected else None))
        else:
            shell.set_status('Open a font to use the live preview. Lesson controls remain available.')
        shell.lesson_close_filters = []
        for title, build in specs:
            child = guarded(build, package, expected)(shell.widget)
            for owner in (child, getattr(child, 'controller', None)):
                for attribute in ('capture', '_capture', 'refresh', 'require_snapshot', 'apply', 'mark', 'apply_mark'):
                    callback = getattr(owner, attribute, None)
                    if callable(callback):
                        setattr(owner, attribute, guarded(callback, package, expected))
            panel = shell.add_tab(TabSpec(title, lambda app, child=child: Profile(app.widget, child)))
            closer = CloseFilter(shell, getattr(child, 'widget', child))
            shell.lesson_close_filters.append(closer)
            controller = getattr(child, 'controller', None)
            if controller is not None and callable(getattr(controller, 'close_owned', None)):
                controller.close_owned = closer.route(controller.close_owned)
            actions = bindings(lab_id, child, title, lambda payload: publish(shell, payload, expected[1] if expected else None))
            for action in ('refresh', 'preview', 'apply'):
                if actions.get(action) is not None:
                    actions[action] = guarded(actions[action], package, expected)
            shell.set_actions(panel, **actions)
        shell.set_about(
            f'{TITLES[lab_id]}\nEach named tab retains its original lesson controls and editing policy. '
            'Use the tab controls to refresh or apply its work; switching tabs keeps drafts. '
            'The shared glyph/text preview is read-only.\n'
            'Sources: https://github.com/fontlabcom/fontlab-python-examples and '
            'https://github.com/fontlabcom/fontlab-fontlabapp\n'
            'Credits and licences: original profile docstrings and package NOTICE. '
            'Shared composition: FontLab App contributors, Apache-2.0.'
        )
        shell.tabs.setCurrentIndex(titles.index(profile) if profile is not None else 0)
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell
