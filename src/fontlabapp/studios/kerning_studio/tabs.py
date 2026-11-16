# this_file: src/fontlabapp/studios/kerning_studio/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""The four Kerning Studio tabs: Text pairs, Glyph pairs, Groups and Tighten.

What: each tab is a plain Qt widget over the shared ``Studio`` state. Lists
use the shared sortable ``GlyphTable``; choosing a row updates the TMetrics
preview (contract §1.8). Buttons name their action. Groups is read-only.
Why: one window replaces seven Scriptmix kerning scripts (Phase D A1).
Used by ``fontlabapp.studios.kerning_studio`` (tab builders and ``show``).
"""

from collections.abc import Callable, Sequence
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui

from . import model
from .model import Pair, display
from .session import APP, NO_FONT, Studio, pair_text

NUDGES = (-10, -5, -1, 1, 5, 10)


def _button(owner: Any, layout: Any, text: str, slot: Callable[[], Any]) -> Any:
    button = QtGui.QPushButton(text, owner)
    button.setAccessibleName(text)
    button.clicked.connect(lambda *args: slot())
    layout.addWidget(button)
    return button


def _field(owner: Any, layout: Any, label: str, placeholder: str = "") -> Any:
    layout.addWidget(QtGui.QLabel(label, owner))
    field = QtGui.QLineEdit(owner)
    field.setPlaceholderText(placeholder)
    field.setAccessibleName(label)
    layout.addWidget(field)
    return field


def _names(text: str) -> list[str]:
    return [name for name in text.replace("/", " ").split() if name]


def _preview_text(pair: Pair) -> str | None:
    """``/left/right`` for two glyphs; None when a side is a group."""
    if any(model.is_group(side) for side in pair):
        return None
    return "/" + "/".join(pair)


class Tab:
    """A tab widget bound to the studio; ``refresh`` runs after every reload."""

    def __init__(self, studio: Studio) -> None:
        self.studio = studio
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        studio.views.append(self.refresh)

    def refresh(self) -> None:  # pragma: no cover - overridden
        pass

    def preview_text(self, text: str | None) -> None:
        if text and self.studio.preview is not None:
            self.studio.preview.set_text(text)


class PairTab(Tab):
    """A pair table with one value column per master, and the pair edit controls."""

    FIRST = "Pair"

    def __init__(self, studio: Studio) -> None:
        super().__init__(studio)
        self.pairs: dict[str, Pair] = {}
        self.selected: Pair | None = None
        self.table: Any = None
        self.columns: tuple[str, ...] = ()
        self.grid: dict[str, Any] = {}
        self.table_box = QtGui.QVBoxLayout()
        self.layout.addLayout(self.table_box, 1)
        self._controls()

    def _controls(self) -> None:
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Preview master", self.widget))
        self.master_box = QtGui.QComboBox(self.widget)
        self.master_box.setAccessibleName("Preview master")
        self.master_box.currentIndexChanged.connect(lambda *args: self._master_changed())
        row.addWidget(self.master_box)
        self.write_note = QtGui.QLabel("", self.widget)
        row.addWidget(self.write_note, 1)
        self.layout.addLayout(row)
        edit = QtGui.QHBoxLayout()
        self.value_field = _field(self.widget, edit, "Value", "0")
        _button(self.widget, edit, "Set value on selected master", self.set_value)
        self.extra_buttons(edit)
        self.layout.addLayout(edit)
        self.grid_row = QtGui.QHBoxLayout()
        self.grid_box = QtGui.QHBoxLayout()
        self.grid_row.addLayout(self.grid_box)
        _button(self.widget, self.grid_row, "Set values on all masters", self.set_grid)
        self.layout.addLayout(self.grid_row)
        steps = QtGui.QHBoxLayout()
        for step in NUDGES:
            _button(self.widget, steps, f"Nudge {step:+d}", lambda step=step: self.nudge(step))
        _button(self.widget, steps, "Kern To Max", self.kern_to_max)
        _button(self.widget, steps, "Delete pair on all masters", self.delete)
        self.layout.addLayout(steps)

    def extra_buttons(self, layout: Any) -> None:
        """Hook for tab-specific buttons on the value row."""

    # Table -----------------------------------------------------------------
    def rows(self) -> list[Pair]:  # pragma: no cover - overridden
        return []

    def refresh(self) -> None:
        studio = self.studio
        masters = tuple(studio.masters)
        self.master_box.blockSignals(True)
        self.master_box.clear()
        self.master_box.addItems(list(masters))
        if studio.master in masters:
            self.master_box.setCurrentIndex(masters.index(studio.master))
        self.master_box.blockSignals(False)
        self.write_note.setText(f"Writes go to the selected master: {studio.master}." if studio.master else NO_FONT)
        columns = (self.FIRST, *masters, "Record")
        if columns != self.columns:
            self._build_grid(masters)
            if self.table is not None:
                self.table.close()
            self.table = fontui.glyph_table(list(columns), self.widget)
            self.table.row_selected.connect(self.row_chosen)
            self.table_box.addWidget(studio.shell.embed(self.table))
            self.columns = columns
        self.pairs = {}
        records = []
        try:
            for key in self.rows():
                text = pair_text(*key)
                values = [self.cell(master, key) for master in masters]
                found = studio.value(studio.master, *key)[1] if studio.master in studio.masters else None
                records.append((text, studio.master, (*values, pair_text(*found) if found else "none")))
                self.pairs[text] = key
        except ValueError as error:
            studio.say(f"{APP}: {error}")
            self.pairs, records = {}, []
        self.table.set_rows(records)
        if self.selected is not None:
            self.table.select(pair_text(*self.selected))

    def cell(self, master: str, key: Pair) -> Any:
        return self.studio.value(master, *key)[0]

    def _build_grid(self, masters: Sequence[str]) -> None:
        """One value field per master: the Pair Editor grid (blank deletes that master's record)."""
        old, self.grid_widget = getattr(self, "grid_widget", None), QtGui.QWidget(self.widget)
        if old is not None:
            self.grid_box.removeWidget(old)
            old.deleteLater()
        cells = QtGui.QHBoxLayout(self.grid_widget)
        self.grid = {master: _field(self.grid_widget, cells, master, "none") for master in masters}
        self.grid_box.addWidget(self.grid_widget)

    def _fill_grid(self, pair: Pair) -> None:
        for master, field in self.grid.items():
            value, key = self.studio.value(master, *pair)
            field.setText(f"{value:g}" if key is not None else "")

    def row_chosen(self, text: str, _layer: Any = None) -> None:
        pair = self.pairs.get(text)
        if pair is None:
            return
        self.selected = pair
        if self.studio.master in self.studio.masters:
            self.value_field.setText(f"{self.studio.value(self.studio.master, *pair)[0]:g}")
        self._fill_grid(pair)
        preview = self.studio.preview
        if preview is not None and not any(model.is_group(side) for side in pair):
            preview.highlight_pair(*pair)

    def _master_changed(self) -> None:
        name = self.master_box.currentText
        name = name() if callable(name) else name
        if name and name != self.studio.master:
            self.studio.choose_master(name)
            self.refresh()

    # Actions ---------------------------------------------------------------
    def _pair(self) -> Pair | None:
        if self.selected is None:
            self.studio.say(f"{APP}: Choose a pair in the list first.")
        return self.selected

    def _value(self) -> float | None:
        text = self.value_field.text
        text = text() if callable(text) else text
        try:
            return float(text)
        except (TypeError, ValueError):
            self.studio.say(f"{APP}: Enter a number for the kerning value.")
            return None

    def set_value(self) -> bool:
        pair, value = self._pair(), self._value()
        return pair is not None and value is not None and self.studio.set_pair(*pair, value)

    def set_grid(self) -> bool:
        """Write each master's grid cell in one Undo step; a blank cell deletes that master's record."""
        pair = self._pair()
        if pair is None:
            return False
        values: dict[str, float | None] = {}
        for master, field in self.grid.items():
            text = field.text
            text = (text() if callable(text) else text).strip()
            try:
                values[master] = float(text) if text else None
            except ValueError:
                self.studio.say(f"{APP}: Enter a number or leave blank for {master}.")
                return False
        return self.studio.set_grid(*pair, values)

    def nudge(self, step: float) -> bool:
        pair = self._pair()
        return pair is not None and self.studio.nudge(*pair, step)

    def kern_to_max(self) -> bool:
        pair = self._pair()
        return pair is not None and self.studio.kern_to_max(*pair)

    def delete(self) -> bool:
        pair = self._pair()
        return pair is not None and self.studio.delete([pair])


class TextPairsTab(PairTab):
    """Pairs From Text + Text Preview: type text, see and set its adjacent pairs."""

    def __init__(self, studio: Studio) -> None:
        self.text = ""
        super().__init__(studio)
        row = QtGui.QHBoxLayout()
        self.text_field = _field(self.widget, row, "Text", "Type text or /names")
        self.text_field.returnPressed.connect(lambda *args: self.show_text())
        _button(self.widget, row, "Show pairs of text", self.show_text)
        self.layout.insertLayout(0, row)

    def extra_buttons(self, layout: Any) -> None:
        _button(self.widget, layout, "Set value on all listed pairs", self.set_all)

    def show_text(self, text: str | None = None) -> None:
        if text is None:
            text = self.text_field.text
            text = text() if callable(text) else text
        self.text = text
        self.preview_text(text)
        self.refresh()

    def rows(self) -> list[Pair]:
        font = self.studio.font()
        if font is None or not self.text:
            return []
        return model.text_pairs(model.parse_text(self.text, self.studio.cmap(font)))

    def set_all(self) -> bool:
        value = self._value()
        pairs = list(self.pairs.values())
        if value is None:
            return False
        if not pairs:
            self.studio.say(f"{APP}: Type text with at least one pair first.")
            return False
        subject = ", ".join(pair_text(*pair) for pair in pairs)
        return self.studio.set_pairs("kerning", subject, [(*pair, value) for pair in pairs])


class GlyphPairsTab(PairTab):
    """Pair Editor: every record involving one glyph, one column per master."""

    def __init__(self, studio: Studio) -> None:
        self.glyph = ""
        super().__init__(studio)
        row = QtGui.QHBoxLayout()
        self.glyph_field = _field(self.widget, row, "Glyph", "Glyph name")
        self.glyph_field.returnPressed.connect(lambda *args: self.show_glyph())
        _button(self.widget, row, "Show pairs of glyph", self.show_glyph)
        self.layout.insertLayout(0, row)

    def show_glyph(self, glyph: str | None = None) -> None:
        if glyph is None:
            glyph = self.glyph_field.text
            glyph = glyph() if callable(glyph) else glyph
        self.glyph = glyph.strip()
        self.refresh()

    def rows(self) -> list[Pair]:
        return model.glyph_pairs(self.studio.masters, self.glyph) if self.glyph else []

    def cell(self, master: str, key: Pair) -> Any:
        value = self.studio.masters[master].pairs.get(key)
        return "" if value is None else value

    def row_chosen(self, text: str, _layer: Any = None) -> None:
        super().row_chosen(text, _layer)
        pair = self.pairs.get(text)
        if pair is not None:
            self.preview_text(_preview_text(pair))


class GroupsTab(Tab):
    """Same Kerning Groups (read-only): a glyph's left and right group peers."""

    def __init__(self, studio: Studio) -> None:
        super().__init__(studio)
        self.glyph = ""
        row = QtGui.QHBoxLayout()
        self.glyph_field = _field(self.widget, row, "Glyph", "Glyph name")
        self.glyph_field.returnPressed.connect(lambda *args: self.show_glyph())
        _button(self.widget, row, "Show kerning groups", self.show_glyph)
        self.layout.addLayout(row)
        self.table = fontui.glyph_table(["Glyph", "Side", "Group", "Same-group glyphs"], self.widget)
        self.table.row_selected.connect(self.row_chosen)
        self.layout.addWidget(studio.shell.embed(self.table), 1)
        self.peers: dict[str, list[str]] = {}
        self.message = ""

    def show_glyph(self, glyph: str | None = None) -> None:
        if glyph is None:
            glyph = self.glyph_field.text
            glyph = glyph() if callable(glyph) else glyph
        self.glyph = glyph.strip()
        self.refresh()
        if self.message:
            self.studio.say(self.message)

    def _order(self) -> list[str]:
        font = self.studio.font()
        return self.studio.order(font) if font is not None else []

    def refresh(self) -> None:
        rows, self.peers, self.message = [], {}, ""
        glyph, data = self.glyph, self.studio.masters.get(self.studio.master or "")
        if not glyph or data is None:
            self.table.set_rows([])
            return
        try:
            peers = model.group_peers(data.groups, glyph, self._order())
            kern1, kern2 = model.side_groups(data.groups, glyph)
        except ValueError as error:
            self.table.set_rows([])
            self.message = f"Ambiguous Kerning Groups: {error}"
            return
        for side, group in (("L", kern2), ("R", kern1)):
            if group and peers[side]:
                key = f"{glyph} {side}"
                self.peers[key] = [glyph, *peers[side]]
                rows.append((key, self.studio.master, (side, display(group), " ".join(peers[side]))))
        self.table.set_rows(rows)
        if not rows:
            self.message = "No Kerning Groups: The selected glyph has no other left or right kerning-group members."
        else:
            self.message = f"{APP}: {glyph} shares kerning groups on {self.studio.master} (read-only)."

    def row_chosen(self, key: str, _layer: Any = None) -> None:
        names = self.peers.get(key)
        if names:
            self.preview_text("/" + "/".join(names))


class TightenTab(Tab):
    """Steal Kerning From Next Pair: match pair 1's gap to pair 2 at a height."""

    def __init__(self, studio: Studio) -> None:
        super().__init__(studio)
        row = QtGui.QHBoxLayout()
        self.glyphs_field = _field(self.widget, row, "Glyphs", "Four glyphs: pair, then reference pair")
        row.addWidget(QtGui.QLabel("Height", self.widget))
        self.height_box = QtGui.QDoubleSpinBox(self.widget)
        self.height_box.setRange(-10000, 10000)
        self.height_box.setAccessibleName("Height")
        row.addWidget(self.height_box)
        self.layout.addLayout(row)
        buttons = QtGui.QHBoxLayout()
        _button(self.widget, buttons, "Measure gaps", self.measure)
        _button(self.widget, buttons, "Apply matched kerning to first pair", self.apply)
        self.layout.addLayout(buttons)
        self.layout.addStretch(1)
        self.height_set = False

    def refresh(self) -> None:
        if self.height_set:
            return
        font = self.studio.font()
        x_height = getattr(getattr(font, "info", None), "xHeight", None) if font is not None else None
        if isinstance(x_height, (int, float)):
            self.height_box.setValue(x_height / 2)
            self.height_set = True

    def glyphs(self) -> list[str]:
        text = self.glyphs_field.text
        return _names(text() if callable(text) else text)

    def height(self) -> float:
        value = self.height_box.value
        return float(value() if callable(value) else value)

    def measure(self) -> tuple[int, float, float] | None:
        glyphs = self.glyphs()
        try:
            value, gap1, gap2 = self.studio.steal(glyphs, self.height())
        except (ValueError, KeyError) as error:
            self.studio.say(f"{APP}: {error}")
            return None
        self.preview_text("/" + "/".join(glyphs))
        self.studio.say(f"Unkerned gaps: {gap1:g} and {gap2:g} units; matched kerning {value}.")
        return value, gap1, gap2

    def apply(self) -> bool:
        return self.studio.apply_steal(self.glyphs(), self.height())


TAB_CLASSES: Sequence[tuple[str, type[Tab]]] = (
    ("Text pairs", TextPairsTab),
    ("Glyph pairs", GlyphPairsTab),
    ("Groups", GroupsTab),
    ("Tighten", TightenTab),
)
