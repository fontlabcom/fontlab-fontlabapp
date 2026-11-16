# this_file: src/fontlabapp/masters/background/clear/model.py
# SPDX-License-Identifier: Apache-2.0
"""Complete paired background-removal scopes from Pedro Arilla; see NOTICE.

Detached facts identify whole original mask objects. No paths, anchors or other
payload are rebuilt. Native mapping/history preservation needs separate proof.
"""

from dataclasses import dataclass
from typing import Any
from time import monotonic


@dataclass(frozen=True)
class Layer:
    """One physical layer and its observed background relationship."""

    glyph_id: int
    glyph: str
    identity: int
    name: str
    master: bool
    service: bool
    mask: bool
    auto: bool
    background: int | None
    locked: bool = False


@dataclass(frozen=True)
class Snapshot:
    """Ordered complete current-font layer mapping and dependency facts."""

    context: tuple
    masters: tuple[str, ...]
    layers: tuple[Layer, ...]
    dependencies: tuple
    glyphs: tuple = ()


@dataclass(frozen=True)
class Removal:
    """One original native mask identity and every mapped foreground owner."""

    glyph_id: int
    glyph: str
    mask_id: int
    mask_name: str
    foreground_ids: tuple[int, ...]


def plan(source: Snapshot, masters: bool, deadline: float | None = None) -> tuple[Removal, ...]:
    """Preserve font/layer order; reject unrepresentable relationships prewrite.

    A native fallback can share one mask between a master and an auxiliary.
    Removing that object in master-only mode would clear an excluded background.
    Unmapped native masks have no original per-layer counterpart; diagnose them
    rather than silently adopting or leaving them in an all-background action.
    """
    deadline = monotonic() + 2 if deadline is None else deadline

    def checkpoint() -> None:
        if monotonic() >= deadline:
            raise TimeoutError("Background planning expired; refresh before clearing.")

    checkpoint()
    by_id = {row.identity: row for row in source.layers}
    if len(by_id) != len(source.layers):
        raise ValueError("Repeated layer identity has ambiguous ownership.")
    linked: dict[int, list[Layer]] = {}
    for row in source.layers:
        checkpoint()
        if row.mask or row.background is None:
            continue
        background = by_id.get(row.background)
        if (
            background is None
            or not background.mask
            or not background.service
            or background.glyph_id != row.glyph_id
            or background.glyph != row.glyph
        ):
            raise ValueError("Background mapping is missing or has an invalid owner/role.")
        linked.setdefault(background.identity, []).append(row)
    if not masters and any(row.mask and row.identity not in linked for row in source.layers):
        raise ValueError("An unmapped background mask cannot identify its original layer.")
    result, seen = [], set()
    for row in source.layers:
        checkpoint()
        if row.mask or row.background is None or (masters and not row.master):
            continue
        if row.background in seen:
            continue
        owners = linked[row.background]
        if masters and any(not owner.master for owner in owners):
            raise ValueError("Background is shared with an excluded auxiliary layer.")
        background = by_id[row.background]
        result.append(
            Removal(row.glyph_id, row.glyph, background.identity, background.name,
                    tuple(owner.identity for owner in owners))
        )
        seen.add(row.background)
    checkpoint()
    return tuple(result)


def automatic_dependants(source: Snapshot, targets: set[str], deadline: float) -> list[str]:
    """Fence transitive automatic dependencies without an unbounded graph walk."""
    reverse: dict[str, set[str]] = {}
    automatic: set[str] = set()
    for name, auto, bases in source.dependencies:
        if monotonic() >= deadline:
            raise TimeoutError("Background dependency scan expired.")
        if auto:
            automatic.add(name)
        for base in bases:
            if monotonic() >= deadline:
                raise TimeoutError("Background dependency scan expired.")
            reverse.setdefault(base, set()).add(name)
    affected, pending = set(targets), list(targets)
    while pending:
        if monotonic() >= deadline:
            raise TimeoutError("Background dependency scan expired.")
        for name in reverse.get(pending.pop(), ()):
            if name not in affected:
                affected.add(name)
                pending.append(name)
    if monotonic() >= deadline:
        raise TimeoutError("Background dependency scan expired.")
    return sorted(automatic.intersection(affected))


def _show(masters: bool) -> Any:
    """Open one independently owned scope through the shared App/Fly surface."""
    from fontlabapp import _native
    from fontlabapp.masters.background.clear.native import Backend
    from fontlabapp.masters.background.clear.ui import panel_type
    from fontlabapp.core.scripting import show_script_dialog

    qt = _native("PythonQt")
    key = "background_clear_masters" if masters else "background_clear_all"
    kind = panel_type(qt.QtCore, qt.QtGui, masters)
    return show_script_dialog(lambda parent: kind(parent, Backend()), key)


def show_all() -> Any:
    """Clear whole backgrounds across all layers of every current-font glyph."""
    return _show(False)


def show_masters() -> Any:
    """Clear whole backgrounds only on declared master layers, across the font."""
    return _show(True)
