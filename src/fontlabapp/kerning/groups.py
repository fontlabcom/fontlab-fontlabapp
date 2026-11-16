# this_file: src/fontlabapp/kerning/groups.py
# SPDX-License-Identifier: Apache-2.0
"""Find the kerning classes one glyph belongs to on each pair side, read-only.

Evidence classes follow Issue 209 ``native-data-map.md`` §3:
``package.kerning(master).groups.items()`` gives ``(name, (members, mode))``
(a-stub, a-src; b: ``core.scripting.kerning_classes``, reused here). ``left``
is the class used when the glyph is a pair's first member, which is mode
KernLeft or KernBothSide (b: ``kerning.batch.MODES`` side 0); ``right`` is
the second member's, KernRight or KernBothSide. Used by
``fontlabapp.plugins.snapshot.capture``; it never calls a kerning writer.
"""

from typing import Any

from fontlabapp.core.scripting import kerning_classes

__all__ = ["read"]


def read(
    package: Any, master: str, name: str
) -> tuple[str | None, str | None, dict[str, tuple[str, ...]]]:
    """Return ``(left, right, members)`` for glyph ``name`` in ``master``.

    On each side a side-specific class wins over a both-side class, then
    native order decides, as ``kerning.symmetry`` resolves classes (b).
    ``members`` holds the members of the chosen classes only. Unknown modes
    are ignored. Missing native attributes raise.
    """
    classes = kerning_classes(package, master)

    def pick(side: str) -> str | None:
        for wanted in (side, "both"):
            for group, (members, mode) in classes.items():
                if mode == wanted and name in members:
                    return group
        return None

    left, right = pick("left"), pick("right")
    members = {
        group: tuple(classes[group][0]) for group in (left, right) if group is not None
    }
    return left, right, members
