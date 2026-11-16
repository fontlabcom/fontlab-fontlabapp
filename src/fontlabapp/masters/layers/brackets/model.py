# this_file: src/fontlabapp/masters/layers/brackets/model.py
# SPDX-License-Identifier: Apache-2.0
"""Bracket-named foreground layers and their complete component dependants.

Adapt both Reset Type Studio workflows without executing their source. The
pattern is literal: a single layer name contains both [ and ]. It does not
infer native export conditions. Both source groups retain overlapping names;
the displayed total counts their union, repairing the source's double count.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Glyph:
    """One whole glyph: every foreground layer name and direct component base."""

    name: str
    layer_names: tuple[str, ...] = ()
    components: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Every glyph needs an unambiguous nonempty name.")
        if type(self.layer_names) is not tuple or any(
            not isinstance(v, str) for v in self.layer_names
        ):
            raise TypeError("Layer names must be an immutable tuple of strings.")
        if type(self.components) is not frozenset or any(
            not isinstance(v, str) for v in self.components
        ):
            raise TypeError("Component names must be an immutable set of strings.")


@dataclass(frozen=True)
class Report:
    """Original group memberships plus distinct total and captured font scope."""

    bracket_glyphs: frozenset[str]
    component_glyphs: frozenset[str]
    glyph_count: int

    @property
    def total(self) -> int:
        return len(self.bracket_glyphs | self.component_glyphs)

    @property
    def overlap(self) -> int:
        return len(self.bracket_glyphs & self.component_glyphs)


def _affected(seeds: set[str], reverse: dict[str, set[str]]) -> frozenset[str]:
    """Reach through at least one component edge; retain cycles and seed overlap."""
    affected: set[str] = set()
    pending = deque(seeds)
    while pending:
        for name in reverse.get(pending.popleft(), ()):
            if name not in affected:
                affected.add(name)
                pending.append(name)
    return frozenset(affected)


def analyse(glyphs: tuple[Glyph, ...]) -> Report:
    """Scan the complete font domain, then follow all reverse component edges."""
    if type(glyphs) is not tuple or any(not isinstance(g, Glyph) for g in glyphs):
        raise TypeError("A complete immutable tuple of Glyph records is required.")
    if len({g.name for g in glyphs}) != len(glyphs):
        raise ValueError("Duplicate glyph names make dependencies ambiguous.")
    seeds = {
        g.name for g in glyphs if any("[" in n and "]" in n for n in g.layer_names)
    }
    reverse: dict[str, set[str]] = defaultdict(set)
    for glyph in glyphs:
        for base in glyph.components:
            reverse[base].add(glyph.name)
    return Report(frozenset(seeds), _affected(seeds, reverse), len(glyphs))


def tab_names(report: Report) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Preserve both groups, including overlap, in deterministic source-intended order."""
    return tuple(sorted(report.bracket_glyphs)), tuple(sorted(report.component_glyphs))


def render(report: Report) -> str:
    """Keep source headings/lists; explain overlap instead of overstating the total."""
    brackets, components = tab_names(report)
    result = f"Glyphs with Bracket Layers ({len(brackets)}):\n" + ", ".join(brackets)
    result += f"\n\nAffected Components ({len(components)}):\n" + ", ".join(components)
    result += f"\n\nTotal affected glyphs: {report.total}"
    if report.overlap:
        result += f"\nOverlapping group members: {report.overlap} (counted once in the total)."
    return result


def show() -> Any:
    """Open or raise the owned, read-only full-font report with Refresh/Close."""
    from fontlabapp.masters.layers.brackets.ui import BracketLayersDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(BracketLayersDialog, BracketLayersDialog.KEY)


def open_tab() -> None:
    """Open both complete groups as explicit named symbols in the captured font."""
    from fontlabapp.masters.layers.brackets.native import open_tab as run

    run()
