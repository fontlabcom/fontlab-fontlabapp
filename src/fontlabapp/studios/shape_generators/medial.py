# this_file: src/fontlabapp/studios/shape_generators/medial.py
# SPDX-License-Identifier: Apache-2.0
"""Myanmar medial-ra controls hosted with the unchanged all-master model."""
from types import SimpleNamespace
from typing import Any

from .._kerning_ui import button, get, row, spin
from ..derived_glyphs._shared import CopiesPanel
from . import myanmar


class MedialPanel(CopiesPanel):
    """Keep default U+103C resolution, width groups and whole-target refusals."""
    HEADERS = ('Template', 'Extensions', 'Bounds / action')
    SELECTION = False
    UNDO = 'create Myanmar medial-ra variants'

    def __init__(self, tool: Any) -> None:
        self.source_type = myanmar.panel_type()
        super().__init__(tool)
        self.names = tool.selected_names()

    def build_controls(self, form: Any) -> None:
        self.group_count = spin(self.widget, 1, 5, 5, slot=self.contain(self.refresh))
        row(self.widget, form, 'Width groups', self.group_count)

    def add_buttons(self, footer: Any) -> None:
        button(self.widget, footer, 'Use selection', self.contain(self.reselect))

    def survey(self, package: Any, facts: Any, allow_rebuild: bool) -> list[Any]:
        self.live()
        state = SimpleNamespace(names=self.names or [], group_count=SimpleNamespace(value=get(self.group_count.value)))
        return self.source_type.survey(state, package, facts, allow_rebuild)

    def jobs(self, rows: list[Any]) -> list[Any]:
        return myanmar.prepare(rows)

    def plan_key(self, package: Any, rows: list[Any]) -> Any:
        return package.id, get(self.group_count.value), myanmar.preview_key(rows)

    def cells(self, record: Any) -> tuple:
        values = self.source_type.cells(SimpleNamespace(font_package=self.live), record)
        return record.source, self.tool.current, tuple(values[1:])
