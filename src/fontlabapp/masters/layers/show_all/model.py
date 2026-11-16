# this_file: src/fontlabapp/masters/layers/show_all/model.py
# SPDX-License-Identifier: Apache-2.0
"""Complete Slobzheninov Show All Layers occurrence/newline policy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Group:
    """One original selected occurrence; control and parentless entries are skipped."""

    parent: str | None
    layers: tuple[str, ...]
    control: bool = False


def expand(groups: tuple[Group, ...]) -> tuple[tuple[str, str] | None, ...]:
    """Keep every parent/layer occurrence and trailing control newline exactly."""
    rows = []
    for group in groups:
        if not group.control and group.parent is not None:
            rows.extend((group.parent, layer) for layer in group.layers)
            rows.append(None)
    return tuple(rows)


def run() -> dict[str, int]:
    """Open the real layer-aware proof lazily; never run the original source."""
    from fontlabapp.masters.layers.show_all.native import run as native_run

    return native_run()
