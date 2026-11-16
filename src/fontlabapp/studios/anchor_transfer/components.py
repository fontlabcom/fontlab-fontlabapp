# this_file: src/fontlabapp/studios/anchor_transfer/components.py
# SPDX-License-Identifier: Apache-2.0
"""From components tab: Derive Anchors From Components as a dry run, then one Undo step.

Recovers missing base anchors from positioned mark components over the
whole current font and every master, with the original's rules (unchanged
``derived_points``): a scan failure shows in the tab and turns Apply off.
Apply writes one ``Anchor Transfer: derive anchors <subject>`` Undo step.
"""

from typing import Any

from . import transfer
from ._panel import AnchorPanel


class ComponentsPanel(AnchorPanel):
    """Derive Anchors From Components."""

    ACTION = "Derive"
    UNDO = "derive anchors"

    def target_glyphs(self) -> list[Any]:
        self.names = transfer.catalog_names()
        return transfer.find_glyphs(self.tool.package, self.names)

    def empty_message(self) -> str:
        return "The font has no glyphs."

    def masters(self) -> list[str]:
        return list(self.tool.masters)

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        return transfer.derive_planner(self.tool.package, self.names, masters)


__all__ = ["ComponentsPanel"]
