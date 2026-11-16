# this_file: src/fontlabapp/studios/kerning_studio/selected_delete.py
# SPDX-License-Identifier: Apache-2.0
"""Selected-slot Delete Kerning Pair From All Masters migrated from the Scriptmix independent Apache-2.0 rewrite.

Original inspiration: Alex Slobzheninov, https://github.com/slobzheninov/Glyphs-Scripts.
Preserves selected OR active slot capture and exact typed native writer semantics.
"""
from itertools import pairwise
from time import monotonic
from typing import Any
from fontlabapp.core import scripting
from fontlabapp.studios._kerning_ui import Panel, button

TITLE = 'Delete Kerning Pair From All Masters'
selection = scripting.layer_selection_api()
kerning = scripting.kerning_tool_backends().batch


def selected_pairs() -> tuple[Any, list[tuple[Any, Any]]]:
    """Require adjacent plain-master slots from the active owned font."""

    captured = selection.capture(monotonic() + 2.0)
    package = scripting.current_package()
    rows = captured.occurrences
    if package is None or captured.context[0] != package.id:
        raise ValueError("Open a font and select adjacent glyphs first.")
    if captured.context[2] != "editor" or len(rows) < 2:
        raise ValueError("Select at least two adjacent glyphs in a Glyph window.")
    pairs = list(pairwise(rows))
    for left, right in pairs:
        if left.block_id != right.block_id or right.index != left.index + 1:
            raise ValueError("Select consecutive glyphs in one text block.")
        if any(not row.layer.isMasterLayer for row in (left, right)):
            raise ValueError("Select master layers; auxiliary layers have no kerning.")
        if left.layer.name != right.layer.name:
            raise ValueError("Both glyphs of each pair must show the same master.")
        if str(left.layer.name) not in tuple(package.masters):
            raise ValueError("The selected layer is not a declared master.")
    return package, pairs


def pair_key(groups: dict, left: str, right: str) -> tuple:
    """Use lossless typed identities; refuse multiple groups on one side."""
    result = []
    for index, name in enumerate((left, right)):
        permitted = (
            ("KernLeft", "KernBothSide")
            if index == 0
            else ("KernRight", "KernBothSide")
        )
        matches = [
            key
            for key, (members, mode) in groups.items()
            if name in members and mode in permitted
        ]
        if len(matches) > 1:
            raise ValueError(f"Glyph {name} has multiple kerning groups on one side.")
        result.append((matches[0], "groupMode") if matches else (name, "glyphMode"))
    return tuple(result)


def plan() -> dict:
    """Delete existing records once; list exceptions that can override the result."""

    package, pairs = selected_pairs()
    before = kerning.snapshot_kerning(package, typed=True)
    edits, overrides = {}, []
    for master in package.masters:
        records = before.pairs[master]
        edits[master] = {}
        for left, right in pairs:
            key = pair_key(before.groups[master], left.glyph_name, right.glyph_name)
            if key in records:
                edits[master][key] = None
            glyphs = ((left.glyph_name, "glyphMode"), (right.glyph_name, "glyphMode"))
            for candidate in dict.fromkeys(
                (glyphs, (glyphs[0], key[1]), (key[0], glyphs[1]))
            ):
                if candidate != key and candidate in records:
                    overrides.append(
                        f"{master}: {candidate[0][0]} · {candidate[1][0]} = {records[candidate]:g}"
                    )
    removed = sum(len(values) for values in edits.values())
    return {
        "removed": removed,
        "package": package, "pairs": pairs, "edits": edits, "before": before,
        "overrides": list(dict.fromkeys(overrides)),
    }


def identity(package: Any, pairs: list) -> tuple:
    """Capture immutable selected positions and shown layer identities."""
    return (package.id, tuple((row.block_id, row.index, row.glyph_name,
                              str(row.layer.name), bool(row.layer.isMasterLayer),
                              getattr(row, "glyph_id", None), getattr(row, "layer_id", None))
                             for pair in pairs for row in pair))


class DeleteStage:
    """Keep all-master deletes separate from preview and recapture before writing."""
    def __init__(self, package: Any = scripting.current_package) -> None:
        self.package = package
        self.accepted: dict | None = None

    def ready(self) -> bool:
        return self.accepted is not None

    def preview(self) -> dict:
        self.accepted = None
        result = plan()
        source = self.package()
        if source is None or source.id != result['package'].id:
            raise ValueError('The original font changed; reopen this tool.')
        result['identity'] = identity(result['package'], result['pairs'])
        self.accepted = result
        return result

    def apply(self) -> dict:
        data, self.accepted = self.accepted, None
        if data is None:
            raise ValueError('Preview Changes before deleting selected pairs.')
        package, pairs = selected_pairs()
        source = self.package()
        if source is None or source.id != package.id or identity(package, pairs) != data['identity']:
            raise ValueError('Selected pairs changed; Preview Changes again.')
        changed = kerning.write_kerning(package, data['edits'], TITLE, expected=data['before'])
        return {'removed': data['removed'], 'changed': changed, 'overrides': data['overrides']}


def run() -> dict:
    """Preserve the immediate console action through the checked stage."""
    stage = DeleteStage()
    stage.preview()
    return stage.apply()


class DeletePanel(Panel):
    """Display every affected pair/master and retain overriding exceptions."""
    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.stage = DeleteStage(tool.shell.package)
        self.grid = self.table(['Pair', 'Master', 'Action'])
        self.subtitle.setText('Select at least two consecutive Glyph-window slots. Delete their class or glyph records on every master; exceptions remain.')
        button(self.widget, self.layout, 'Discard deletion preview', self.refresh)
        tool.shell.set_actions(self.widget, refresh=self.refresh, preview=self.preview,
                               apply=self.apply, ready=self.stage.ready, dirty=self.stage.ready,
                               apply_label='Delete selected pairs on all masters')

    def refresh(self) -> None:
        self.stage.accepted = None
        self.grid.set_rows([])

    def preview(self) -> None:
        self.refresh()
        data = self.stage.preview()
        self.grid.set_rows([(' · '.join(name for name, mode in pair), master, (master, 'Delete'))
                            for master, values in data['edits'].items() for pair in values])
        left, right = data['pairs'][0]
        self.tool.show_pair(left.glyph_name, right.glyph_name, str(left.layer.name))
        self.tool.say(f"{data['removed']} records to remove. " + '; '.join(data['overrides']))

    def apply(self) -> None:
        result = self.stage.apply()
        self.tool.say(f"Removed {result['removed']} pair/master records." if result['changed'] else 'No kerning to delete for the selected pairs.')
        if self.tool.preview is not None:
            self.tool.preview.refresh()
