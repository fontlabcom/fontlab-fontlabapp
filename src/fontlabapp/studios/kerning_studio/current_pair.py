# this_file: src/fontlabapp/studios/kerning_studio/current_pair.py
# SPDX-License-Identifier: Apache-2.0
"""Original Kern To Max slot capture, staged in the shared Kerning Studio.

Independent behaviour rewrite after Alex Slobzheninov, Glyphs-Scripts,
Apache-2.0. Retains the Scriptmix selected-or-active slot contract and typed
class resolution; no TypeRig code or sibling-script runtime imports.
"""

import math
from collections.abc import Callable
from time import monotonic
from typing import Any

from fontlabapp.core.scripting import current_package, kerning_tool_backends, layer_selection_api
from fontlabapp.studios._kerning_ui import Panel, button

TITLE = 'Kern To Max'
selection = layer_selection_api()
kerning = kerning_tool_backends().batch


def selected_pair() -> tuple[Any, Any, Any]:
    """Refuse nonadjacent, cross-master and auxiliary selected/active slots."""
    captured = selection.capture(monotonic() + 2.0)
    package = current_package()
    rows = captured.occurrences
    if package is None or captured.context[0] != package.id:
        raise ValueError('Open a font and select a pair first.')
    if captured.context[2] != 'editor' or len(rows) != 2:
        raise ValueError('Select exactly two adjacent glyphs in a Glyph window.')
    left, right = rows
    if left.block_id != right.block_id or right.index != left.index + 1:
        raise ValueError('Select consecutive glyphs in one text block.')
    if any(not row.layer.isMasterLayer for row in rows):
        raise ValueError('Select master layers; auxiliary layers have no kerning.')
    if left.layer.name != right.layer.name or left.layer.name not in package.masters:
        raise ValueError('Both glyphs must show the same declared master.')
    return package, left, right


def pair_key(groups: dict, left: str, right: str) -> tuple:
    """Keep exactly one side-compatible class, otherwise a typed glyph identity."""
    result = []
    for index, name in enumerate((left, right)):
        permitted = ('KernLeft', 'KernBothSide') if index == 0 else ('KernRight', 'KernBothSide')
        matches = [key for key, (members, mode) in groups.items() if name in members and mode in permitted]
        if len(matches) > 1:
            raise ValueError(f'Glyph {name} has multiple kerning groups on one side.')
        result.append((matches[0], 'groupMode') if matches else (name, 'glyphMode'))
    return tuple(result)


def facts(package: Any, rows: tuple) -> tuple:
    """Compare immutable slot/layer identity and advance values before Apply."""
    return (package.id, tuple((row.block_id, row.index, row.glyph_id, row.layer_id,
                              row.glyph_name, str(row.layer.name), float(row.layer.advanceWidth))
                             for row in rows))


class CurrentPairStage:
    """Accept the captured current pair; never re-plan after the user presses Apply."""

    def __init__(self, package: Callable[[], Any] = current_package) -> None:
        self.package = package
        self.before: Any = None
        self.identity: Any = None
        self.edits: dict = {}
        self.report: dict = {}

    def preview(self) -> dict:
        self.before = None
        package, left, right = selected_pair()
        source = self.package()
        if source is None or source.id != package.id:
            raise ValueError('The original font changed; reopen this tool.')
        widths = [float(row.layer.advanceWidth) for row in (left, right)]
        if any(not math.isfinite(width) or width < 0 for width in widths):
            raise ValueError('Both advance widths must be finite and nonnegative.')
        value, master = -int(min(widths) / 2), str(left.layer.name)
        identity = facts(package, (left, right))
        before = kerning.snapshot_kerning(package, typed=True)
        pair = pair_key(before.groups[master], left.glyph_name, right.glyph_name)
        records = before.pairs[master]
        glyphs = ((left.glyph_name, 'glyphMode'), (right.glyph_name, 'glyphMode'))
        overrides = [f'{master}: {candidate[0][0]} · {candidate[1][0]} = {records[candidate]:g}'
                     for candidate in dict.fromkeys((glyphs, (glyphs[0], pair[1]), (pair[0], glyphs[1])))
                     if candidate != pair and candidate in records]
        if facts(package, (left, right)) != identity:
            raise ValueError('Selected pair advances changed during preview; try again.')
        self.identity = identity
        self.edits = {master: {pair: value}}
        self.report = {'value': value, 'changed': records.get(pair) != value, 'overrides': overrides,
                       'glyphs': (left.glyph_name, right.glyph_name), 'master': master}
        self.before = before
        return dict(self.report)

    def ready(self) -> bool:
        return self.before is not None

    def apply(self) -> dict:
        if self.before is None:
            raise ValueError('Preview Changes before applying Kern To Max.')
        before, self.before = self.before, None
        package, left, right = selected_pair()
        source = self.package()
        if source is None or source.id != package.id or facts(package, (left, right)) != self.identity:
            raise ValueError('The original selected pair or advances changed; preview again.')
        written = kerning.write_kerning(package, self.edits, TITLE, expected=before)
        return {**self.report, 'changed': bool(self.report['changed'] and written)}


def run() -> dict:
    """Retain the original immediate console action through the same checked stage."""
    stage = CurrentPairStage()
    stage.preview()
    result = stage.apply()
    return {key: result[key] for key in ('value', 'changed', 'overrides')}


class CurrentPairPanel(Panel):
    """Preview the selected adjacent slots before applying their derived limit."""

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.stage = CurrentPairStage(tool.shell.package)
        self.grid = self.table(['Glyph pair', 'Master', 'Value', 'Overriding exceptions kept'])
        self.subtitle.setText('Select exactly two adjacent slots in a Glyph window. Preview captures their shown master and advances.')
        button(self.widget, self.layout, 'Discard current-pair preview', self.refresh)
        tool.shell.set_actions(self.widget, refresh=self.refresh, preview=self.preview,
                               apply=self.apply, ready=self.stage.ready, dirty=self.stage.ready,
                               apply_label='Apply Kern To Max')

    def refresh(self) -> None:
        self.stage.before = None
        self.grid.set_rows([])

    def preview(self) -> None:
        self.refresh()
        report = self.stage.preview()
        self.grid.set_rows([('  '.join(report['glyphs']), report['master'],
                             (report['master'], report['value'], '; '.join(report['overrides'])))])
        self.tool.show_pair(*report['glyphs'], report['master'])
        self.tool.say(f"Kern To Max preview: {report['value']} units; overriding exceptions are kept.")

    def apply(self) -> None:
        report = self.stage.apply()
        self.tool.say(f"Kern To Max: {'Set' if report['changed'] else 'Unchanged at'} {report['value']} units.")
        if self.tool.preview is not None:
            self.tool.preview.refresh()
