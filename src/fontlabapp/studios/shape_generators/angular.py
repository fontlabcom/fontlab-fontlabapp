# this_file: src/fontlabapp/studios/shape_generators/angular.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Angularizzle's bound Process/Cancel session inside the generator shell."""
from time import monotonic
from typing import Any

import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid native parent fallback

from .._kerning_ui import get

services = fontui.outline_generators_backends()


class PreviewBackend:
    """Run the same session planner, recording its result without native writes."""
    def __init__(self, session: Any) -> None:
        self.session = session
        self.after = ()

    def capture(self, deadline: float) -> Any:
        return self.session.source

    def check(self, source: Any, **kwargs: Any) -> None:
        self.session.backend.check(source, **kwargs)

    def apply(self, source: Any, before: Any, after: Any, **kwargs: Any) -> None:
        self.after = after


class AngularPanel(services.lifecycle.Owned):
    """Preserve repeated Process, duplicate batch records and explicit restoration."""
    def __init__(self, tool: Any, *, backend: Any = None, preferences: Any = None) -> None:
        super().__init__(tool.shell.widget)
        self.tool = tool
        self.session = services.angular_session.Session(backend or services.angular_native.NativeBackend())
        self.accepted = None
        self.settings = None
        if preferences is None:
            self.settings, preferences = services.angular_settings.native_preferences(services.qt.QtCore)
        self.preferences = preferences
        loaded = services.angular_settings.load(preferences)
        gui = services.qt.QtGui
        self.plane = gui.QLineEdit(loaded.plane, self.widget)
        self.plane.setAccessibleName('Minimum plane')
        self.detail = gui.QCheckBox('Keep detail', self.widget)
        self.detail.setChecked(loaded.detail)
        self.layout.addWidget(gui.QLabel('Minimum plane (units)', self.widget))
        self.layout.addWidget(self.plane)
        self.layout.addWidget(self.detail)
        self.grid = fontui.glyph_table(['Target', 'Opening contours', 'Planned contours'], self.widget)
        self.layout.addWidget(tool.shell.embed(self.grid))
        self.targets = {key: (record.glyph_name, str(record.layer.name))
                        for key, record in getattr(self.session.backend, '_bound', {}).items()}
        self.connect(self.grid.row_selected, lambda name, layer: self.run(lambda: self.chosen(name, layer)))
        if self.targets and tool.preview is not None:
            name, layer = next(iter(self.targets.values()))
            self.chosen(name, layer)
        self.discard_button = gui.QPushButton('Discard staged plan', self.widget)
        self.layout.addWidget(self.discard_button)
        self.connect(self.discard_button.clicked, lambda *args: self.run(self.discard))
        self.restore = gui.QPushButton('Restore opening paths', self.widget)
        self.layout.addWidget(self.restore)
        self.connect(self.restore.clicked, lambda *args: self.run(self.cancel))
        self.connect(self.plane.textChanged, lambda *args: self.invalidate())
        self.connect(self.detail.toggled, lambda *args: self.invalidate())
        self.baseline = self.values()
        tool.shell.set_actions(self, refresh=self.discard, preview=self.preview_plan, apply=self.apply,
                               ready=self.ready, dirty=self.dirty, apply_label='Process')
        tool.say(loaded.warning or 'Process targets the first master. Restore keeps the processed colour mark.')

    def run(self, action: Any) -> None:
        try:
            action()
        except Exception as error:  # noqa: BLE001 - contain native callback failures
            self.tool.say(str(error))

    def values(self) -> tuple:
        return str(get(self.plane.text)), self.detail.isChecked()

    def invalidate(self) -> None:
        self.accepted = None

    def dirty(self) -> bool:
        return self.accepted is not None or self.values() != self.baseline

    def discard(self) -> None:
        self.accepted = None
        self.baseline = self.values()
        self.grid.set_rows([])

    def preview_plan(self) -> None:
        self.accepted = None
        self.tool.shell.package()
        if self.session.closed:
            raise ValueError('This Angularizzle session finished. Reopen Shape Generators.')
        backend = PreviewBackend(self.session)
        trial = services.angular_session.Session(backend)
        trial.current = dict(self.session.current)
        trial.process(*self.values())
        original = {row.key: row for row in self.session.source.layers}
        self.grid.set_rows([(*self.targets.get(row.key, (row.key, None)), (len(original[row.key].paths), len(row.paths))) for row in backend.after])
        self.accepted = self.values()
        self.tool.say('Preview accepted. Process writes these bound first-master targets.')

    def ready(self) -> bool:
        self.tool.shell.package()
        return not self.session.closed and self.accepted is not None and self.accepted == self.values()

    def apply(self) -> None:
        if not self.ready():
            raise ValueError('Preview before Process.')
        self.accepted = None
        self.session.process(*self.values())
        prefs = services.angular_settings
        self.preferences[prefs.PLANE], self.preferences[prefs.CHECK] = self.values()
        if self.settings is not None:
            prefs.persist(services.qt.QtCore, self.settings, self.preferences, (prefs.PLANE, prefs.CHECK))
        self.tool.preview.refresh()
        self.tool.say('Processed. Restore opening paths retains the source colour mark.')

    def cancel(self) -> None:
        self.tool.shell.package()
        self.session.cancel()
        self.accepted = None
        self.tool.preview.refresh()
        self.tool.say('Opening paths restored; the processed colour mark is retained.')

    def chosen(self, name: str, layer: Any) -> None:
        self.tool.shell.package()
        self.session.backend.check(self.session.source, selection=False,
                                   deadline=monotonic() + services.angular_session.ACTION_SECONDS)
        if self.tool.preview is not None:
            self.tool.preview.load(name, layer)

    def close(self) -> None:
        if hasattr(self, 'session'):
            self.session.close()
        super().close()
