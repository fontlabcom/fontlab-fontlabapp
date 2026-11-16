# this_file: src/fontlabapp/studios/mark_attachment/preview.py
# SPDX-License-Identifier: Apache-2.0
"""Mark preview tab (Scriptmix Anchors · Mark Attachment Preview): read only.

Bases are glyphs with a plain anchor, marks glyphs with an ``_anchor``, on
the current master (``anchors.inspect.model.classify``, unchanged). The
anchor list holds the names X with X on the base and _X on the mark; the
first selected base is chosen by default. One panel per master draws the
base and the mark moved by ``base anchor − mark anchor``
(``attachment``), in the original ``AttachmentView``. Nothing is written.
"""

from typing import Any

from PythonQt import QtGui

from fontlabapp.core.scripting import anchors_view_types

from .._kerning import Tool
from .._kerning_ui import Panel, combo, get, label, row
from . import _shared


class MarkPreviewPanel(Panel):
    """Mark Attachment Preview: base / mark / anchor choice and one attachment panel per master."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.ready = False
        self.base = row(
            self.widget,
            self.layout,
            "Base",
            combo(self.widget, [], self.keep(self.pair_changed)),
        )
        self.mark = row(
            self.widget,
            self.layout,
            "Mark",
            combo(self.widget, [], self.keep(self.pair_changed)),
        )
        self.family = row(
            self.widget,
            self.layout,
            "Anchor",
            combo(self.widget, [], self.keep(self.draw)),
        )
        self.view = anchors_view_types().AttachmentView(self.widget)
        self.layout.addWidget(self.view, 1)
        self.status = label(self.widget, self.layout)
        self.bases: list[str] = []
        self.marks: list[str] = []
        self.offsets: dict[str, Any] = {}
        self.ready = True

    def keep(self, slot: Any) -> Any:
        return lambda *args: self.ready and self.run(slot)

    def clear(self) -> None:
        self.bases, self.marks, self.offsets = [], [], {}
        for box in (self.base, self.mark, self.family):
            box.blockSignals(True)
            box.clear()
            box.blockSignals(False)
        self.view.set_panels([])
        self.status.setText("")

    @staticmethod
    def choices(box: Any, items: list[str], chosen: str = "") -> None:
        box.blockSignals(True)
        box.clear()
        for item in items:
            box.addItem(item)
        if chosen in items:
            box.setCurrentIndex(items.index(chosen))
        box.blockSignals(False)

    def refresh(self) -> None:
        """Re-read bases and marks on the current master; keep the chosen pair when it still exists."""
        old = (get(self.base.currentText), get(self.mark.currentText))
        self.clear()
        tool = self.tool
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            return
        api = _shared.backends().inspect
        self.bases, self.marks = api.classify(
            tool.package, api.font_glyph_names(), tool.current
        )
        chosen = [name for name in tool.selected_names() if name in self.bases]
        self.choices(
            self.base,
            self.bases,
            old[0] if old[0] in self.bases else (chosen[0] if chosen else ""),
        )
        self.choices(self.mark, self.marks, old[1])
        self.pair_changed()

    def pair_changed(self) -> None:
        """The anchor names both glyphs share; keep the previous one when present."""
        api, tool = _shared.backends().inspect, self.tool
        base = api.attachment_layer_of(
            tool.package, get(self.base.currentText), tool.current
        )
        mark = api.attachment_layer_of(
            tool.package, get(self.mark.currentText), tool.current
        )
        common = (
            api.families(base, mark) if base is not None and mark is not None else []
        )
        self.choices(self.family, common, get(self.family.currentText))
        self.draw()

    def draw(self) -> None:
        """The original ``refresh``: one panel per master with a base layer; read only."""
        api, tool = _shared.backends().inspect, self.tool
        layer_of, attachment, glyph_path, anchor_points = (
            api.attachment_layer_of, api.attachment, api.glyph_path, api.anchor_points)  # fmt: skip
        base_name, mark_name, family = (get(self.base.currentText), get(self.mark.currentText),
                                        get(self.family.currentText))  # fmt: skip
        self.subtitle.setText(
            f"{mark_name or '–'} attached to {base_name or '–'} with {family or '–'} / _{family or '–'} on {len(tool.masters)} masters. {len(self.bases)} base and {len(self.marks)} mark glyphs found."
        )
        (panels, self.offsets) = ([], {})
        for master in tool.masters:
            base = layer_of(tool.package, base_name, master)
            mark = layer_of(tool.package, mark_name, master)
            if base is None:
                continue
            offset = (
                attachment(base, mark, family) if mark is not None and family else None
            )
            self.offsets[master] = offset
            mark_path = None
            point = None
            if offset is not None:
                mark_path = QtGui.QTransform(1, 0, 0, 1, offset[0], offset[1]).map(
                    glyph_path(mark)
                )
                point = anchor_points(base)[family]
            note = (
                f"offset {offset[0]}, {offset[1]}"
                if offset is not None
                else "no matching anchors"
            )
            panels.append(
                (master, glyph_path(base), mark_path, point, base.advanceWidth, note)
            )
        self.view.set_panels(panels)
        missing = [m for (m, o) in self.offsets.items() if o is None]
        self.status.setText(f"Missing anchors on {', '.join(missing)}" if missing
                            else "Mark offset = base anchor − mark anchor")  # fmt: skip
        if tool.preview is not None and base_name:
            tool.preview.set_text(
                f"/{base_name}/{mark_name}" if mark_name else f"/{base_name}"
            )


__all__ = ["MarkPreviewPanel"]
