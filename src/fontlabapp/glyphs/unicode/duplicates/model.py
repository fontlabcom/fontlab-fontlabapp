# this_file: src/fontlabapp/glyphs/unicode/duplicates/model.py
# SPDX-License-Identifier: Apache-2.0
"""Complete ordered Duplicate Unicodes preview and chosen removal plan.

Adapted from the Apache-2.0 rescued FontLab sample. Repeated associations remain
visible; no Unicode/name normalization or automatic keeper enforcement is added.
"""

from dataclasses import dataclass

TITLE = "Duplicate Unicodes"
KEY = "names_duplicate_unicodes"


@dataclass(frozen=True)
class Glyph:
    """Font-owned identity and ordered Unicode assignments, with stale fences."""

    fg_id: int
    identity: int
    name: str
    codes: tuple[int, ...]
    layers: tuple
    stamp: tuple


@dataclass(frozen=True)
class Snapshot:
    """Complete current font domain and automatic dependency observations."""

    context: tuple
    glyphs: tuple[Glyph, ...]
    dependencies: tuple


@dataclass(frozen=True)
class Group:
    """One numerically ordered shared codepoint, including literal occurrences."""

    code: int
    keeper: str
    names: tuple[str, ...]


def groups(glyphs: tuple[Glyph, ...]) -> tuple[Group, ...]:
    """Prefer first primary owner, otherwise first owner in unchanged font order."""
    users, names, ids, native_ids = {}, set(), set(), set()
    for glyph in glyphs:
        if (
            not isinstance(glyph.name, str)
            or not glyph.name
            or glyph.name in names
            or glyph.fg_id in ids
            or glyph.identity in native_ids
        ):
            raise ValueError("Ambiguous glyph identity or name.")
        names.add(glyph.name)
        ids.add(glyph.fg_id)
        native_ids.add(glyph.identity)
        for code in glyph.codes:
            if type(code) is not int or not 0 <= code <= 0x10FFFF:
                raise ValueError("Unreadable Unicode assignment.")
            users.setdefault(code, []).append(glyph)
    found = []
    for code, owners in sorted(users.items()):
        if len(owners) > 1:
            keeper = next(
                (g.name for g in owners if g.codes[0] == code), owners[0].name
            )
            found.append(Group(code, keeper, tuple(g.name for g in owners)))
    return tuple(found)


def plan(facts: Snapshot, removals: list[tuple[str, int]]) -> tuple:
    """Remove only checked preview pairs; keep each remaining list's exact order.

    FontGate's list setter deduplicates its input. Refuse a target whose surviving
    repeated codes would therefore be collapsed as an unrelated side effect.
    """
    valid = {
        (name, group.code) for group in groups(facts.glyphs) for name in group.names
    }
    drop = {}
    for name, code in removals:
        if (name, code) not in valid:
            raise ValueError("Removal does not match this complete preview; rescan.")
        drop.setdefault(name, set()).add(code)
    by_name = {glyph.name: glyph for glyph in facts.glyphs}
    jobs = []
    for name, codes in drop.items():
        glyph = by_name[name]
        remaining = tuple(code for code in glyph.codes if code not in codes)
        if len(remaining) != len(set(remaining)):
            raise ValueError(
                "Native Unicode assignment would collapse unrelated repeated codes."
            )
        jobs.append((glyph, remaining))
    return tuple(jobs)


def show() -> object:
    """Open the complete writer lazily through Fly or directly inside FontLab."""
    from fontlabapp.glyphs.unicode.duplicates.ui import dialog_type
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(dialog_type(), KEY)
