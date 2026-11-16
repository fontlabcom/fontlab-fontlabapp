# this_file: src/fontlabapp/studios/anchor_transfer/fonts.py
# SPDX-License-Identifier: Apache-2.0
"""Between fonts tab: Copy Anchors Between Fonts as a dry run, then one Undo step in the destination.

Every original choice, with its default: source and destination font and
layer (or "*All masters*", matched by name), "Copy from" all or selected
glyphs, "Which anchors" all or a comma-separated list, "Location" absolute
or relative (x scaled by the advance ratio), "Handle Collision" overwrite or
rename (default), "Collision rename" incoming or destination (default),
the "Addon suffix" (".bak") and "Use italic angle" with its angle (10°).
Refresh captures both fonts and lists every edit
``anchors.crossfont.model.copy_layer`` plans; Copy writes them through the
crossfont backend as one ``Anchor Transfer: copy anchors from <font> to
<subject>`` Undo step in the destination font. The same font on both sides
is refused. Two-font history and reopen are qualified natively in T29.
"""

from typing import Any

from PythonQt import QtGui

from .._kerning_ui import Panel, button, check, combo, get, label, line_edit, row, spin
from . import transfer
from ._panel import show_glyph

COLUMNS = ["Glyph", "Master", "Layers", "Action", "Anchor", "Position"]
SOURCE_SCOPES = ["All glyphs", "Selected glyphs"]
ANCHOR_SCOPES = ["All anchors", "Specific anchors"]
LOCATIONS = ["Absolute", "Relative"]
COLLISIONS = ["Overwrite", "Rename"]
RENAMES = ["Incoming", "Destination"]


class FontsPanel(Panel):
    """Copy Anchors Between Fonts."""

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.ready = False  # option slots fire while the controls are built
        form = QtGui.QVBoxLayout()
        self.layout.addLayout(form)
        refresh = self.contain(self.refresh)
        self.source_font = row(self.widget, form, "Source font:", combo(self.widget, [], self.contain(self.font_chosen)))
        self.source_layer = row(self.widget, form, "Source Layer:", combo(self.widget, [], refresh))
        self.selected = row(self.widget, form, "Copy from:", combo(self.widget, SOURCE_SCOPES, refresh))
        self.which = row(self.widget, form, "Which anchors:", combo(self.widget, ANCHOR_SCOPES, refresh))
        self.anchor_names = row(self.widget, form, "Anchors list:",
                                line_edit(self.widget, "", "Comma separated list of anchors: top, left", refresh))
        self.destination_font = row(self.widget, form, "Destination font:",
                                    combo(self.widget, [], self.contain(self.font_chosen)))
        self.destination_layer = row(self.widget, form, "Destination Layer:", combo(self.widget, [], refresh))
        self.location = row(self.widget, form, "Location:", combo(self.widget, LOCATIONS, refresh))
        self.collision = row(self.widget, form, "Handle Collision:", combo(self.widget, COLLISIONS, refresh))
        self.collision.setCurrentIndex(1)
        self.rename_side = row(self.widget, form, "Collision rename:", combo(self.widget, RENAMES, refresh))
        self.rename_side.setCurrentIndex(1)
        self.suffix = row(self.widget, form, "Addon suffix:", line_edit(self.widget, ".bak", "Examples: .new, .bak, .1", refresh))
        italic = QtGui.QHBoxLayout()  # the original's "Italic:" row: check box, then the angle
        form.addLayout(italic)
        label(self.widget, italic, "Italic:")
        self.italic = check(self.widget, italic, "Use italic angle", False, refresh)
        self.angle = spin(self.widget, 0, 20, 10, suffix="°", slot=refresh)
        self.angle.setAccessibleName("Italic:")
        italic.addWidget(self.angle, 1)
        self.grid = self.table(list(COLUMNS), self.row_chosen)
        self.count = label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(self.widget, buttons, "Copy Anchors", self.apply)
        self.fonts: tuple = ()
        self.plan: Any = None
        self.ready = True

    # options -----------------------------------------------------------------
    def options(self) -> Any:
        """The chosen ``anchors.crossfont.model.Options``."""
        specific = str(get(self.anchor_names.text)) if get(self.which.currentIndex) == 1 else None
        return transfer.font_options(
            relative=get(self.location.currentIndex) == 1,
            italic=bool(get(self.italic.isChecked)),
            angle=int(get(self.angle.value)),
            rename=get(self.collision.currentIndex) == 1,
            rename_destination=get(self.rename_side.currentIndex) == 1,
            suffix=str(get(self.suffix.text)),
            specific=specific,
        )

    def chosen(self, box: Any) -> Any:
        index = get(box.currentIndex)
        if not 0 <= index < len(self.fonts):
            raise ValueError("A chosen font closed; refresh the font lists.")
        return self.fonts[index]

    def fill_layers(self, font_box: Any, layer_box: Any) -> None:
        keep = str(get(layer_box.currentText))
        layer_box.blockSignals(True)
        layer_box.clear()
        layer_box.addItem(transfer.ALL_MASTERS)
        index = get(font_box.currentIndex)
        masters = list(self.fonts[index].masters) if 0 <= index < len(self.fonts) else []
        for master in masters:
            layer_box.addItem(master)
        if keep in masters:
            layer_box.setCurrentIndex(masters.index(keep) + 1)
        layer_box.blockSignals(False)

    def fill_fonts(self) -> None:
        """Re-read the open fonts; keep each side's font while it is still open."""
        old = [self.fonts[get(b.currentIndex)].identity if 0 <= get(b.currentIndex) < len(self.fonts) else None
               for b in (self.source_font, self.destination_font)]  # fmt: skip
        self.fonts = tuple(transfer.font_rows())
        ids = [row.identity for row in self.fonts]
        for side, (box, layers) in enumerate(((self.source_font, self.source_layer),
                                              (self.destination_font, self.destination_layer))):  # fmt: skip
            box.blockSignals(True)
            box.clear()
            for font in self.fonts:
                box.addItem(transfer.font_label(font))
            default = min(side, len(ids) - 1)
            box.setCurrentIndex(ids.index(old[side]) if old[side] in ids else default)
            box.blockSignals(False)
            self.fill_layers(box, layers)

    # state -------------------------------------------------------------------
    def clear(self) -> None:
        self.plan = None
        self.grid.set_rows([])
        self.count.setText("")
        self.apply_button.setEnabled(False)

    def font_chosen(self) -> None:
        if not self.ready:
            return
        self.fill_layers(self.source_font, self.source_layer)
        self.fill_layers(self.destination_font, self.destination_layer)
        self.refresh(reread=False)

    def refresh(self, reread: bool = True) -> None:
        if not self.ready:
            return
        self.clear()
        if reread:
            self.fill_fonts()
        if not self.fonts:
            self.subtitle.setText("No open font files found!")
            return
        if len(self.fonts) < 2:
            self.subtitle.setText("Open a second font to copy anchors into.")
            return
        source, destination = self.chosen(self.source_font), self.chosen(self.destination_font)
        self.subtitle.setText(f"{transfer.font_label(source)} → {transfer.font_label(destination)}")
        self.plan = transfer.fonts_preview(
            source.identity, destination.identity, str(get(self.source_layer.currentText)),
            str(get(self.destination_layer.currentText)), get(self.selected.currentIndex) == 1, self.options(),
        )  # fmt: skip
        plan = self.plan
        self.grid.set_rows(plan.rows)
        skipped = len(plan.snapshot.skipped)
        text = (f"{len(plan.rows)} anchor edit{'s' if len(plan.rows) != 1 else ''} in "
                f"{len(plan.names)} glyph{'s' if len(plan.names) != 1 else ''}") if plan.rows else "Nothing to process!"
        if skipped:
            text += f" · {skipped} skipped: " + "; ".join(plan.snapshot.skipped[:3]) + (" …" if skipped > 3 else "")
        if plan.problem:
            text = f"Refused. {plan.problem}"
        self.count.setText(text)
        self.apply_button.setEnabled(bool(plan.rows) and not plan.problem)

    def row_chosen(self, name: str, master: Any) -> None:
        """Preview the glyph only when the destination is the shown font."""
        if self.plan is not None and self.tool.package is not None and self.plan.args[1] == self.tool.package.id:
            show_glyph(self.tool, name, master)

    def apply(self) -> bool:
        plan = self.plan

        def write() -> bool:
            if plan is None:
                raise ValueError("Nothing to change.")
            source = next((f for f in self.fonts if f.identity == plan.args[0]), None)
            done = transfer.fonts_apply(self.tool, plan, (source.label if source else "") or "Untitled")
            status = self.tool.status
            self.tool.reload()
            self.tool.say(status)
            return done

        return bool(self.run(write))


__all__ = ["ANCHOR_SCOPES", "COLLISIONS", "COLUMNS", "LOCATIONS", "RENAMES", "SOURCE_SCOPES", "FontsPanel"]
