# this_file: src/fontlabapp/studios/shape_generators/panel.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Host the original Comb, Sandblast and Sansomatic planners in sortable tabs."""
from importlib import import_module
from types import SimpleNamespace
from typing import Any

from fontlabapp.fontui import outline_generators_backends

from .._kerning_ui import Panel, button, check, combo, get, row, spin
from ..transform_studio.native import snapshot

services = outline_generators_backends()
SETTINGS = {
    'comb': (('Strips', 1, 100, 7, 0), ('Filled %', 1, 99, 50, 0)),
    'sandblast': (('Holes', 1, 1000, 50, 0), ('Radius', .1, 1000, 3, 1), ('Seed', 0, 1000000, 1, 0)),
    'sansomatic': (('Height', 1, 5000, 700, 0), ('Width', 1, 5000, 450, 0), ('Vertical stroke', 1, 5000, 70, 0), ('Horizontal stroke', 1, 5000, 55, 0), ('Side space', 0, 5000, 45, 0)),
}


class GeneratorPanel(Panel):
    """Require an accepted plan over captured glyphs, masters and geometry."""

    def __init__(self, tool: Any, mode: str) -> None:
        super().__init__(tool)
        self.mode = mode
        self.model = import_module(f'{__package__}.{mode}')
        self.source_type = self.model.panel_type() if mode == 'sansomatic' else self.model.ToolPanel
        self.names = tool.selected_names()
        self.controls = []
        self.accepted = None
        self.plan = None
        self.baseline = None
        self.cache = {}
        for title, low, high, value, decimals in SETTINGS[mode]:
            control = spin(self.widget, low, high, value, decimals=decimals, slot=self.contain(self.refresh))
            self.controls.append(control)
            row(self.widget, self.layout, title, control)
        self.scope = combo(self.widget, ['Current master', 'All masters'], self.contain(self.refresh))
        self.scope.setCurrentIndex(1)
        row(self.widget, self.layout, 'Masters', self.scope)
        self.compatible = check(self.widget, self.layout, services.writer.COMPATIBLE_LABEL, True, self.contain(self.refresh))
        self.bases = check(self.widget, self.layout, services.writer.BASES_LABEL, False, self.contain(self.refresh))
        self.grid = self.table(['Glyph', 'Item', 'Now', 'After'], self.contain(self.chosen))
        button(self.widget, self.layout, 'Use selection (discard plan)', self.contain(self.reselect))
        button(self.widget, self.layout, 'Discard staged plan', self.contain(self.discard))
        self.tool.shell.set_actions(self.widget, refresh=self.discard, preview=self.preview_plan,
                                   apply=self.apply, ready=self.ready, dirty=self.dirty,
                                   apply_label='Build' if mode == 'sansomatic' else 'Apply Changes')

    def values(self) -> tuple:
        return tuple(get(control.value) for control in self.controls)

    def planner_state(self) -> Any:
        values = [SimpleNamespace(value=value) for value in self.values()]
        if self.mode == 'comb':
            return SimpleNamespace(strips=values[0], coverage=values[1])
        if self.mode == 'sandblast':
            return SimpleNamespace(hole_count=values[0], radius=values[1], seed=values[2],
                                   hole_cache=self.cache, hole_settings=self.values())
        return SimpleNamespace(dimension_boxes=values)

    def capture(self) -> tuple:
        package = self.tool.shell.package()
        if package is None:
            raise ValueError('Open a font and select glyphs first.')
        masters = self.tool.scope(bool(get(self.scope.currentIndex)))
        glyphs = [package.findName(name) for name in self.names]
        if any(glyph is None or glyph.isNull for glyph in glyphs):
            raise ValueError('Selected glyphs changed; use selection again.')
        sources = tuple((glyph.name, master, getattr(layer, 'id', id(layer)), snapshot(layer))
                        for glyph in glyphs for master in masters
                        if (layer := glyph.findLayer(master)) is not None)
        return package, masters, glyphs, sources

    def build_plan(self) -> tuple:
        package, masters, glyphs, sources = self.capture()
        state = self.planner_state()
        facts = services.history.scan_auto_facts(package)
        plan = services.writer.collect(glyphs, masters, self.source_type.planner(state), facts,
                                       compatible=self.compatible.isChecked(), all_masters=self.tool.masters,
                                       allow_bases=self.bases.isChecked())
        key = (package.id, tuple(masters), sources, self.values(), self.compatible.isChecked(), self.bases.isChecked())
        return plan, facts, key

    def refresh(self) -> None:
        if not hasattr(self, 'grid'):
            return
        self.plan, _, self.key = self.build_plan()
        identities = {f'{name} · {master}': (name, master) for name in self.names for master in self.tool.masters}
        self.grid.set_rows([(identities.get(label, (label, self.tool.current))[0], identities.get(label, (label, self.tool.current))[1],
                             (change.name, change.old, change.problem or change.new)) for label, change in self.plan.rows])
        self.subtitle.setText(self.plan.problems[0] if self.plan.problems else f'{self.plan.edits} planned edits')
        if self.baseline is None:
            self.baseline = self.key

    def preview_plan(self) -> None:
        self.accepted = None
        self.refresh()
        if self.plan.problems or not self.plan.work:
            raise ValueError(self.plan.problems[0] if self.plan.problems else 'Nothing to apply.')
        self.accepted = self.key
        self.tool.say('Preview accepted. Apply writes the displayed plan.')

    def ready(self) -> bool:
        _, _, key = self.build_plan()
        return self.accepted is not None and key == self.accepted

    def dirty(self) -> bool:
        return self.accepted is not None or self.key != self.baseline

    def discard(self) -> None:
        self.accepted = None
        self.cache.clear()
        self.refresh()
        self.baseline = self.key

    def reselect(self) -> None:
        self.names = self.tool.selected_names()
        self.bases.setChecked(False)
        self.discard()

    def apply(self) -> None:
        plan, facts, key = self.build_plan()
        if key != self.accepted or plan.problems:
            raise ValueError('The plan changed. Preview before Apply.')
        self.accepted = None
        result = services.writer.apply_work(plan.work, self.model.TITLE, facts,
                                            self.source_type.editor(self.planner_state()),
                                            allow_bases=self.bases.isChecked())
        self.discard()
        self.tool.say(f"Changed {result['edits']} edits on {result['layers']} layers. {result.get('pending_note', '')}")

    def chosen(self, name: str, layer: Any) -> None:
        self.capture()
        if self.tool.preview is not None:
            self.tool.preview.load(name, layer)
