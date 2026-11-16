# this_file: src/fontlabapp/fontui/getgo_labs.py
# SPDX-License-Identifier: Apache-2.0
"""Owned GetGo lab tabs over retained lesson providers and detached previews."""

import json
import math
from typing import Any

from PythonQt import QtGui

from ..qt.properties import value
from ..studios import TabSpec
from .appshell import AppShell
from .lifecycle import Owned
from .table import GlyphRow, GlyphTable

_FAILED: list[Any] = []


def parameters(texts: dict[str, str], defaults: dict) -> dict:
    """Parse the original lessons' text, scale and optional destination arguments."""
    result = {}
    for name, text in texts.items():
        if isinstance(defaults[name], float):
            number = float(text)
            if not math.isfinite(number) or number <= 0:
                raise ValueError('Scale must be finite and positive')
            result[name] = number
        elif type(defaults[name]) is int:
            number = None if text.strip().lower() in ('', 'none') else int(text)
            if number is not None and number < 0:
                raise ValueError('Limit must be a nonnegative integer or None')
            result[name] = number
        else:
            result[name] = None if defaults[name] is None and not text.strip() else text
    return result


class Task(Owned):
    """A tab retains its parameters and accepted plan across tab changes."""

    def __init__(self, shell: Any, provider: Any, spec: dict, page: Any) -> None:
        self.shell, self.provider, self.spec = shell, provider, spec
        self.view = self.font = self.accepted = self.table = None
        super().__init__(shell.tabs)
        self.page = page
        self.preview_layout = QtGui.QVBoxLayout(page)
        self.note = QtGui.QLabel('Preview Changes shows the unchanged source fixture and proposed lesson parameters.', page)
        self.note.setWordWrap(True)
        self.preview_layout.addWidget(self.note)
        help_label = QtGui.QLabel(spec['help'], self.widget)
        help_label.setWordWrap(True)
        self.layout.addWidget(help_label)
        self.fonts = QtGui.QComboBox(self.widget)
        self.fonts.addItems(spec['fonts'])
        self.fonts.setAccessibleName('Preview fixture')
        self.layout.addWidget(self.fonts)
        self.inputs = {}
        for name, default in spec['defaults'].items():
            self.layout.addWidget(QtGui.QLabel(name.replace('_', ' ').title(), self.widget))
            field = QtGui.QLineEdit('' if default is None else str(default), self.widget)
            field.setAccessibleName(name.replace('_', ' ').title())
            if type(default) is int:
                field.setPlaceholderText('Blank or None: show all entries')
            self.inputs[name] = field
            self.layout.addWidget(field)
            self.connect(field.textChanged, lambda *args: self.invalidate())
        self.connect(self.fonts.currentIndexChanged, lambda *args: self.invalidate())
        self.table = GlyphTable(('Result', 'Value'), self.widget)
        self.layout.addWidget(self.table.widget, 1)
        shell.set_actions(self, refresh=self.refresh, preview=self.capture,
                          apply=self.run if spec['writes'] else None, ready=self.ready,
                          apply_label='Run on disposable copy' if not spec['entry'].startswith('export_') else 'Export new subset')

    def parameters(self) -> dict:
        return parameters({name: value(field, 'text') for name, field in self.inputs.items()}, self.spec['defaults'])

    def invalidate(self) -> None:
        self.accepted = None

    def ready(self) -> bool:
        return self.accepted is not None and self.accepted == self.parameters()

    def refresh(self) -> None:
        """Keep input drafts; reports may be rerun without executing writer lessons."""
        if self.spec['writes']:
            self.capture()
        else:
            self.run()

    def capture(self) -> None:
        """Close the prior preview before replacing its owned detached font."""
        kwargs = self.parameters()
        self.invalidate()
        self.provider.validate(self.spec['entry'], kwargs)
        self.release_preview()
        self.font, losses = self.provider.capture(value(self.fonts, 'currentText'))
        try:
            if self.provider.preview == 'tmetrics':
                from .tmetrics import TMetrics
                text = kwargs.get('text') or ''.join('/' + name for name in list(self.font.keys())[:8])
                self.view = TMetrics(self.font, self.page, text=text, read_only=True, controls=False)
            else:
                from .tglyph import TGlyph
                names = list(self.font.keys())
                self.view = TGlyph(self.font, 'A' if 'A' in names else next(iter(names), None),
                                   parent=self.page, read_only=True, controls=False)
            self.preview_layout.addWidget(self.view.widget, 1)
            self.note.setText('Unchanged source fixture preview; proposed edits are not simulated. ' + '\n'.join(losses))
            self.table.set_rows([GlyphRow('Operation', None, (self.spec['title'],)),
                                 GlyphRow('Lesson fixtures', None, (', '.join(self.spec['fonts']),)),
                                 GlyphRow('Preview fixture', None, (value(self.fonts, 'currentText'),)),
                                 GlyphRow('Proposed parameters', None, (json.dumps(kwargs, ensure_ascii=False),)),
                                 GlyphRow('Scope', None, ('New geometry file; never overwrite' if self.spec['entry'].startswith('export_')
                                                        else 'New verified owned copy; discard any edits',))])
            self.accepted = kwargs
            self.shell.set_status('Source fixture and proposed parameters ready. Apply runs the lesson; this preview does not simulate its result.')
        except BaseException:
            self.release_preview()
            raise

    def run(self) -> None:
        kwargs = self.parameters()
        self.invalidate()
        report = self.provider.run(self.spec['entry'], kwargs)
        self.table.set_rows([GlyphRow(str(key), None, (item if isinstance(item, (int, float, str))
                                                     else json.dumps(item, ensure_ascii=False),))
                             for key, item in report.items()])
        self.shell.set_status('Lesson completed on its verified owned copy. See the result and any export path below.')

    def release_preview(self) -> None:
        if self.view is not None:
            self.view.close()
            self.view = None
        if self.font is not None:
            self.font.close()
            self.font = None

    def close(self) -> None:
        self.closed = True
        self.release_preview()
        self.provider.close()
        self._close_with_child(self.table)


def show(provider: Any) -> AppShell:
    """Compose all named lesson profiles without opening a font until requested."""
    while _FAILED:
        _FAILED[-1].close()
        _FAILED.pop()
    shell = AppShell(provider.title, provider.preview, package=lambda: None)
    _FAILED.append(shell)
    shell.getgo_panels = []
    stack = QtGui.QStackedWidget(shell.preview_box)
    shell.preview_layout.addWidget(stack)
    try:
        for spec in provider.specs():
            page = QtGui.QWidget(stack)
            stack.addWidget(page)
            def build(app: Any, spec: dict = spec, page: Any = page) -> Task:
                panel = Task.__new__(Task)
                shell.children.append(panel)
                panel.__init__(app, provider, spec, page)
                shell.children.remove(panel)
                shell.getgo_panels.append(panel)
                return panel
            shell.add_tab(TabSpec(spec['title'], build))
        shell.connect(shell.tabs.currentChanged, lambda index: stack.setCurrentIndex(index)
                      if index < value(stack, 'count') else None)
        shell.set_about('GetGo teaching labs\nSource: https://github.com/fontlabcom/fontlab-python-examples\n'
                        'Lesson code: Apache-2.0. Fonts retain their CC0, OFL or Apache notices.\n'
                        'Original lesson routes, defaults and verified temporary-copy guards remain in effect.\n'
                        'Geometry exports omit native hints, features, kerning, axes and other layers.\n'
                        'Preview Changes shows the unchanged source fixture and proposed parameters; it does not simulate edits. '
                        'Mutation lessons require a dedicated no-document session. Preview opens and closes '
                        'a temporary fixture, retaining only detached data.')
        shell.show()
    except BaseException:
        shell.close()
        _FAILED.remove(shell)
        raise
    _FAILED.remove(shell)
    return shell
