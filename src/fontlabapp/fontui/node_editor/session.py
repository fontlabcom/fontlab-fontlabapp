# this_file: src/fontlabapp/fontui/node_editor/session.py
# SPDX-License-Identifier: Apache-2.0
"""Captured preview acceptance for the distinct Node Editor write policies."""

from time import monotonic

import fontlabapp.core.history.glyphs as history
import fontlabapp.core.scripting as scripting
import fontlabapp.contours.writer as writer
from fontlabapp.contours.nodes.duplicator import native


class NativePlan:
    """Accept one source snapshot; native execution rechecks it before staging."""

    def __init__(self, package, mode):
        self.package_id, self.layer = package.id, package.master
        self.mode = mode
        self.accepted = None

    @property
    def dirty(self):
        return self.accepted is not None

    def target(self):
        package = scripting.current_package(self.package_id)
        if package is None:
            raise ValueError("The captured font changed or closed; reopen Node Editor.")
        if package.master != self.layer:
            raise ValueError("The captured layer changed; restore it or reopen Node Editor.")
        return package

    def discard(self):
        self.accepted = None

    def preview(self):
        self.discard()
        self.target()
        deadline = monotonic() + 3
        before = native.capture(self.mode, deadline)
        if before.context[0] != self.package_id:
            raise ValueError("Selection belongs to another font.")
        result = native.plan(before.source, self.mode)
        native.check(deadline)
        self.accepted = before
        return result

    def apply(self):
        self.target()
        if self.accepted is None:
            raise ValueError("Preview changes before Apply.")
        accepted = self.accepted
        self.discard()
        return native.execute(self.mode, expected=accepted, report=False)


class PerGlyphPlan(NativePlan):
    """Keep the independent per-glyph, compatible-master policy and its writer."""

    def __init__(self, package, panel):
        super().__init__(package, "per-glyph")
        self.panel = panel

    def capture(self):
        deadline = monotonic() + 3
        package = self.target()
        _, glyphs = self.panel.live_glyphs()
        facts = history.scan_auto_facts(package)
        masters = self.panel.chosen_masters()
        options = self.panel.options()
        plan = writer.collect(glyphs, masters, self.panel.planner(), facts, **options)
        if plan.problems:
            raise ValueError(plan.problems[0])
        relevant = {(glyph.name, layer.name): (glyph, layer) for glyph, layer, _ in plan.work}
        names = set(masters)
        if options.get("compatible"):
            names.update(options["all_masters"])
        edited = {glyph.name: glyph for glyph, _, _ in plan.work}
        for glyph in edited.values():
            for name in names:
                layer = glyph.findLayer(name)
                if layer is not None and not layer.isNull:
                    relevant[(glyph.name, layer.name)] = (glyph, layer)
        for row in self.panel._selected_occurrences:
            if row.glyph.name in edited:
                relevant[(row.glyph.name, row.layer.name)] = (row.glyph, row.layer)
        records = tuple(native.read_layer(layer, glyph, deadline)[:2]
                        for glyph, layer in relevant.values())
        rows = tuple((label, c.name, c.old, c.new, c.problem, c.key) for label, c in plan.rows)
        native.check(deadline)
        stamp = (records, rows, facts, options, self.panel._selection_snapshot)
        return plan, facts, options, stamp

    def preview(self):
        self.discard()
        plan, facts, options, stamp = self.capture()
        self.panel.fill(plan)
        if not plan.work:
            raise ValueError("Nothing to change.")
        self.accepted = stamp
        return plan

    def apply(self):
        if self.accepted is None:
            raise ValueError("Preview changes before Apply.")
        plan, facts, options, stamp = self.capture()
        if stamp != self.accepted:
            self.discard()
            raise ValueError("Node preview changed; preview again.")
        self.discard()
        result = writer.apply_work(plan.work, "Node Editor: Duplicate", facts,
                                   self.panel.editor(), allow_bases=options["allow_bases"])
        result["skipped"] = len(plan.refused) + len(plan.skipped)
        self.panel.last_result = result
        self.panel.refresh()
        return result
