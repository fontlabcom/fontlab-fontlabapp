# this_file: src/fontlabapp/studios/font_audit/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""The six Font Audit tabs: Overview, Glyph table, Unicode, Empty, Case & small caps, Unreferenced.

What: plain Qt widgets over the shared ``Studio``. Lists use the shared
sortable ``GlyphTable``; choosing a row shows its glyphs in the read-only
TMetrics preview (contract §1.8). Buttons name their action. Overview also
holds Label Statistics (mark colour and name suffix groups): like the
Overview cards it summarises the whole font, and its row click selects that
group as the original did. Nothing here edits the font or calls history.
Used by ``fontlabapp.studios.font_audit`` (tab builders).
"""

import pathlib
from collections.abc import Callable
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui

from . import model
from .session import APP, ERRORS, Studio

NO_FONT = "Open a font first."
SELECT = "Select in Font window"


def _button(owner: Any, layout: Any, text: str, slot: Callable[[], Any]) -> Any:
    button = QtGui.QPushButton(text, owner)
    button.setAccessibleName(text)
    button.clicked.connect(lambda *args: slot())
    layout.addWidget(button)
    return button


def _check(owner: Any, layout: Any, text: str, checked: bool, slot: Callable[[], Any] | None = None) -> Any:
    box = QtGui.QCheckBox(text, owner)
    box.setAccessibleName(text)
    box.setChecked(checked)
    if slot is not None:
        box.toggled.connect(lambda *args: slot())
    layout.addWidget(box)
    return box


def _label(owner: Any, layout: Any, text: str = "") -> Any:
    label = QtGui.QLabel(text, owner)
    label.setWordWrap(True)
    layout.addWidget(label)
    return label


def _get(value: Any) -> Any:
    """PythonQt exposes some getters as properties, PySide6 as methods."""
    return value() if callable(value) else value


def _row(name: str, layer: Any, values: tuple) -> tuple:
    """A ``GlyphTable`` row ``(glyph_name, layer, values)``."""
    return (name, layer, tuple(values))


def _clipboard(text: str) -> None:
    QtGui.QApplication.clipboard().setText(text)


class Tab:
    """A tab widget bound to the studio; ``refresh`` runs after every reload."""

    def __init__(self, studio: Studio) -> None:
        self.studio = studio
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        self.subtitle = _label(self.widget, self.layout)
        studio.views.append(self.refresh)

    def table(self, columns: list[str], slot: Callable[..., Any], stretch: int = 1) -> Any:
        table = fontui.glyph_table(columns, self.widget)
        table.row_selected.connect(slot)
        self.layout.addWidget(self.studio.shell.embed(table), stretch)
        return table

    def refresh(self) -> None:  # pragma: no cover - overridden
        pass

    def run(self, action: Callable[[], Any]) -> Any:
        """Run a button action; a refusal goes to the status line."""
        try:
            return action()
        except ERRORS as error:
            self.studio.say(f"{APP}: {error}")
            return None


class OverviewTab(Tab):
    """Font Overview cards and master metrics, plus Label Statistics."""

    def __init__(self, studio: Studio) -> None:
        super().__init__(studio)
        self.cards_label = _label(self.widget, self.layout)
        self.metrics = self.table(list(model.METRIC_COLUMNS), lambda *args: None)
        self.note = _label(self.widget, self.layout)
        self.label_title = _label(self.widget, self.layout)
        self.add = _check(self.widget, self.layout, "Add to selection", False)
        self.marks_table = self.table(["Mark colour", "Glyphs"], self.mark_chosen)
        self.suffix_table = self.table(["Name suffix", "Glyphs"], self.suffix_chosen)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        _button(self.widget, buttons, "Refresh", studio.reload)
        self.cards: dict[str, Any] = {}
        self.marks: list = []
        self.suffixes: list = []
        self.package_id: Any = None

    def refresh(self) -> None:
        cat = self.studio.catalogue
        self.package_id = None
        self.marks, self.suffixes = [], []
        if cat is None:
            self.cards = {}
            self.subtitle.setText(NO_FONT)
            self.cards_label.setText("–")
            self.note.setText("No font open.")
            self.label_title.setText(NO_FONT)
            for table in (self.metrics, self.marks_table, self.suffix_table):
                table.set_rows([])
            return
        self.cards = model.overview_cards(cat)
        self.subtitle.setText(model.subtitle(cat))
        self.cards_label.setText("   ".join(f"{key}: {value:,}" for key, value in self.cards.items()))
        package = self.studio.package()
        rows = self.studio.metrics(package) if package is not None else []
        self.metrics.set_rows([
            _row(row[0], None, (*(model.metric_text(v) for v in row[1:5]), row[5])) for row in rows
        ])
        self.note.setText(model.OVERVIEW_STATUS)
        labels = model.font_labels(cat)
        self.marks, self.suffixes = model.statistics(labels)
        self.label_title.setText(model.label_subtitle(labels, self.marks, self.suffixes))
        self.marks_table.set_rows([_row(model.mark_label(m), None, (len(n),)) for m, n in self.marks])
        self.suffix_table.set_rows([_row(s or "(no suffix)", None, (len(n),)) for s, n in self.suffixes])
        self.package_id = cat.package_id

    def mark_chosen(self, label: str, *args: Any) -> None:
        index = [model.mark_label(m) for m, _ in self.marks]
        self.run(lambda: self.select_group(self.marks, index.index(label) if label in index else -1))

    def suffix_chosen(self, label: str, *args: Any) -> None:
        index = [s or "(no suffix)" for s, _ in self.suffixes]
        self.run(lambda: self.select_group(self.suffixes, index.index(label) if label in index else -1))

    def select_group(self, groups: list, row: int) -> list[str] | None:
        """Select a mark or suffix group, optionally keeping the current selection (Label Statistics)."""
        self.studio.check(self.package_id)
        if not 0 <= row < len(groups):
            return None
        _key, names = groups[row]
        self.studio.show_glyphs(names)
        current = self.studio.selection() if _get(self.add.isChecked) else []
        selected = self.studio.select(list(dict.fromkeys(current + list(names))), self.package_id)
        self.studio.say(f"Selected {len(selected)} glyph{model.plural(len(selected))}")
        return selected


class GlyphTableTab(Tab):
    """Glyph Table CSV: scope, sortable table, Copy CSV and Export CSV."""

    def __init__(self, studio: Studio, clipboard: Callable[[str], Any] = _clipboard) -> None:
        super().__init__(studio)
        self.clipboard = clipboard
        self.selection: list[str] = []
        self.header: list[str] = []
        self.rows: list[list[Any]] = []
        self.last_result: dict | None = None
        form = QtGui.QHBoxLayout()
        self.layout.addLayout(form)
        form.addWidget(QtGui.QLabel("Glyphs", self.widget))
        self.scope = QtGui.QComboBox(self.widget)
        self.scope.setAccessibleName("Glyphs")
        form.addWidget(self.scope)
        form.addWidget(QtGui.QLabel("File", self.widget))
        self.path = QtGui.QLineEdit(self.widget)
        self.path.setAccessibleName("File")
        self.path.setPlaceholderText(model.CSV_DEFAULT)
        form.addWidget(self.path, 1)
        _button(self.widget, form, "Choose…", self.choose)
        self.chooser: Any = None
        self.view: Any = None
        self.view = self.table(["glyph"], self.row_chosen)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        _button(self.widget, buttons, "Refresh", studio.reload)
        self.copy_button = _button(self.widget, buttons, "Copy CSV", lambda: self.run(self.copy))
        self.export_button = _button(self.widget, buttons, "Export CSV", lambda: self.run(self.export))
        self.scope.currentIndexChanged.connect(lambda *args: self.fill())
        self.path.textChanged.connect(lambda *args: self.update_buttons())

    def refresh(self) -> None:
        """Re-read the selection and choose the original default scope (Selected when more than one)."""
        self.selection = self.studio.selection() if self.studio.catalogue is not None else []
        self.scope.blockSignals(True)
        self.scope.clear()
        self.scope.addItem("All glyphs")
        self.scope.addItem(f"Selected glyphs ({len(self.selection)})")
        self.scope.setCurrentIndex(1 if len(self.selection) > 1 else 0)
        self.scope.blockSignals(False)
        self.fill()

    def names(self) -> list[str]:
        cat = self.studio.catalogue
        if cat is None:
            return []
        return [r.name for r in cat.records] if _get(self.scope.currentIndex) == 0 else list(self.selection)

    def fill(self) -> None:
        cat = self.studio.catalogue
        self.header, self.rows = [], []
        if cat is None:
            self.subtitle.setText(NO_FONT)
            self._replace_table(["glyph"])
            self.update_buttons()
            return
        self.header, self.rows = model.table(cat, self.names())
        self.subtitle.setText(model.table_subtitle(cat, self.rows))
        self._replace_table(self.header)
        self.view.set_rows([_row(row[0], None, tuple(row[1:])) for row in self.rows])
        self.update_buttons()

    def _replace_table(self, columns: list[str]) -> None:
        """GlyphTable columns are fixed, so a new master list gets a new table."""
        if self.view is not None and list(self.view.columns) == list(columns):
            self.view.set_rows([])
            return
        old = self.view
        self.view = fontui.glyph_table(list(columns), self.widget)
        self.view.row_selected.connect(self.row_chosen)
        self.layout.insertWidget(self.layout.indexOf(old.widget) if old is not None else 1,
                                 self.studio.shell.embed(self.view), 1)
        if old is not None:
            old.widget.hide()
            old.close()

    def update_buttons(self) -> None:
        """Export needs rows and a file; Copy needs rows (the original rule)."""
        path = _get(self.path.text).strip()
        self.export_button.setEnabled(bool(self.rows) and bool(path))
        self.copy_button.setEnabled(bool(self.rows))
        if not path and self.studio.catalogue is not None:
            self.studio.say(model.CSV_HINT)

    def row_chosen(self, name: str, *args: Any) -> None:
        self.studio.show_glyphs([name])

    def choose(self) -> None:
        """Non-modal save dialog; the chosen path lands in the File field."""
        if self.chooser is not None:
            self.chooser.close()
        self.chooser = QtGui.QFileDialog(self.widget, model.CSV_TITLE, _get(self.path.text) or model.CSV_DEFAULT,
                                         model.CSV_FILTER)
        self.chooser.setAcceptMode(QtGui.QFileDialog.AcceptSave)
        self.chooser.setDefaultSuffix("csv")
        self.chooser.fileSelected.connect(lambda path, *args: self.path.setText(path))
        self.chooser.open()

    def copy(self) -> None:
        """Copy the complete computed CSV snapshot to the clipboard."""
        self.clipboard(model.to_csv(self.header, self.rows))
        self.studio.say(f"Copied {len(self.rows)} rows")

    def export(self, path: Any = None) -> Any:
        """Write the computed snapshot to the chosen UTF-8 (BOM) CSV file."""
        path = path or _get(self.path.text).strip()
        if not path or not self.rows:
            raise ValueError(model.CSV_HINT)
        size = model.write_csv(path, self.header, self.rows)
        self.last_result = {"path": path, "rows": len(self.rows), "bytes": size}
        self.studio.say(f"Wrote {len(self.rows)} rows to {pathlib.Path(path).name}")
        return path


class UnicodeTab(Tab):
    """Unicode Coverage: blocks the font touches, coverage and selection of a block's glyphs."""

    def __init__(self, studio: Studio) -> None:
        super().__init__(studio)
        self.show_all = _check(self.widget, self.layout, "Show untouched blocks", False, self.refresh)
        self.view = self.table(["Block", "Range", "Coverage", "Glyphs"], self.row_chosen)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        _button(self.widget, buttons, "Refresh", studio.reload)
        self.select_button = _button(self.widget, buttons, "Select block glyphs in Font window",
                                     lambda: self.run(self.select_block))
        self.codes: dict[int, str] = {}
        self.rows: list[tuple] = []
        self.outside: list[int] = []
        self.current = -1
        self.package_id: Any = None

    def refresh(self) -> None:
        cat = self.studio.catalogue
        self.package_id, self.codes, self.rows, self.outside, self.current = None, {}, [], [], -1
        self.view.set_rows([])
        if cat is None:
            self.subtitle.setText(NO_FONT)
            return
        self.codes = model.font_codes(cat)
        self.rows, self.outside = model.coverage(list(self.codes), bool(_get(self.show_all.isChecked)))
        self.subtitle.setText(model.coverage_subtitle(self.codes, self.rows))
        self.view.set_rows([
            _row(name, None, (f"{start:04X}–{end:04X}", model.percent(covered, total),
                                         f"{covered} / {total}"))
            for start, end, name, covered, total in self.rows
        ])
        self.studio.say(model.coverage_status(self.rows, self.outside))
        self.package_id = cat.package_id

    def row_chosen(self, name: str, *args: Any) -> None:
        names = [r[2] for r in self.rows]
        self.current = names.index(name) if name in names else -1
        if self.current >= 0:
            start, end = self.rows[self.current][:2]
            self.studio.show_glyphs(model.block_names(self.codes, start, end))

    def select_block(self, row: int | None = None) -> list[str] | None:
        """Select encoded glyphs in the requested block of the scanned font."""
        self.studio.check(self.package_id)
        row = self.current if row is None else row
        if not 0 <= row < len(self.rows):
            return None
        start, end, name = self.rows[row][:3]
        selected = self.studio.select(model.block_names(self.codes, start, end), self.package_id)
        self.studio.say(f"{name}: selected {len(selected)} glyph{model.plural(len(selected))}")
        return selected


class EmptyTab(Tab):
    """Empty Glyphs: glyphs without contours on some or all masters."""

    def __init__(self, studio: Studio) -> None:
        super().__init__(studio)
        self.skip = _check(self.widget, self.layout, model.HIDE_SPACES, True, self.refresh)
        self.view: Any = None
        self.view = self.table(["Glyph"], self.row_chosen)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        _button(self.widget, buttons, "Rescan", studio.reload)
        self.select_button = _button(self.widget, buttons, SELECT, lambda: self.run(self.select_rows))
        self.rows: list[tuple[str, list[str]]] = []
        self.masters: tuple[str, ...] = ()
        self.current: str | None = None
        self.package_id: Any = None

    def refresh(self) -> None:
        cat = self.studio.catalogue
        self.package_id, self.rows, self.current = None, [], None
        self.select_button.setEnabled(False)
        if cat is None:
            self.subtitle.setText(NO_FONT)
            self.view.set_rows([])
            return
        self.masters = cat.masters
        self.rows = model.scan_empty(cat, bool(_get(self.skip.isChecked)))
        columns = ["Glyph", *self.masters]
        if list(self.view.columns) != columns:
            old = self.view
            self.view = fontui.glyph_table(columns, self.widget)
            self.view.row_selected.connect(self.row_chosen)
            self.layout.insertWidget(self.layout.indexOf(old.widget), self.studio.shell.embed(self.view), 1)
            old.widget.hide()
            old.close()
        self.view.set_rows([
            _row(name, None, tuple("empty" if m in empty else "✓" for m in self.masters))
            for name, empty in self.rows
        ])
        self.subtitle.setText(model.empty_subtitle(self.rows, self.masters))
        self.studio.say(f"Click a row to preview it; use {SELECT} to select it (all rows when none is chosen)." if self.rows else "")
        self.select_button.setEnabled(bool(self.rows))
        self.package_id = cat.package_id

    def row_chosen(self, name: str, *args: Any) -> None:
        self.current = name
        self.studio.show_glyphs([name])

    def select_rows(self, rows: list[int] | None = None) -> list[str] | None:
        """Select the chosen row, or every row when none is chosen (the original rule)."""
        if self.package_id is None:
            raise ValueError("Refresh the report with an open font first.")
        self.studio.check(self.package_id)
        if rows is None:
            names = [self.current] if self.current else [name for name, _ in self.rows]
        else:
            names = [self.rows[r][0] for r in rows if 0 <= r < len(self.rows)]
        selected = self.studio.select(names, self.package_id)
        self.studio.say(f"Selected {len(selected)} glyph{model.plural(len(selected))}")
        return selected


class CaseTab(Tab):
    """Case Coverage and Smallcap Consistency: the original windows, opened from one tab."""

    def __init__(self, studio: Studio) -> None:
        super().__init__(studio)
        self.subtitle.setText(
            "Case Coverage finds missing uppercase and lowercase counterparts and export-policy conflicts. "
            "Smallcap Consistency checks small caps against capitals, lowercase and kerning groups."
        )
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        _button(self.widget, buttons, "Open Case Coverage", lambda: self.run(self.case_coverage))
        _button(self.widget, buttons, "Show Smallcap Consistency report", lambda: self.run(self.smallcaps))
        self.layout.addStretch(1)
        self.window: Any = None

    def refresh(self) -> None:
        pass

    def case_coverage(self) -> Any:
        """Open the original Case Coverage dialog with the launcher's GlyphData callbacks."""
        studio = self.studio
        if studio.case_metadata is None or studio.case_preferred is None:
            raise ValueError("Case Coverage needs GlyphData; open Font Audit from its Scriptmix launcher.")
        self.window = studio.backends().case_coverage.show(studio.case_metadata, studio.case_preferred)
        return self.window

    def smallcaps(self) -> Any:
        """Capture afresh, then open or replace the owned Smallcap Consistency report."""
        backends = self.studio.backends()
        report = backends.smallcaps.current_report()
        self.window = backends.reports.show_report(
            report, title="Smallcap Consistency", key="report_smallcap_consistency"
        )
        return self.window


class UnreferencedTab(Tab):
    """Select Unreferenced Glyphs: unencoded glyphs nothing refers to, for review."""

    SUBTITLE = (
        "Unencoded glyphs not used as components, in auto recipes, in the feature code or in its "
        "classes. Many are alternates waiting for a feature: review before deleting anything."
    )

    def __init__(self, studio: Studio) -> None:
        super().__init__(studio)
        self.view = self.table(["Glyph", "Hint"], self.row_chosen)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        _button(self.widget, buttons, "Refresh", studio.reload)
        self.select_button = _button(self.widget, buttons, SELECT, lambda: self.run(self.apply))
        self.rows: list[tuple[str, str]] = []
        self.package_id: Any = None
        self.last_result: dict | None = None

    def refresh(self) -> None:
        self.rows, self.package_id = [], None
        self.select_button.setEnabled(False)
        self.view.set_rows([])
        if self.studio.catalogue is None:
            self.subtitle.setText("Open a font, then run this script again.")
            return
        try:
            package = self.studio.package()
            self.rows = [tuple(row) for row in self.studio.backends().unreferenced.unreferenced(package)]
        except ERRORS as error:
            self.subtitle.setText(self.SUBTITLE)
            self.studio.say(f"{APP}: {error}")
            return
        self.subtitle.setText(self.SUBTITLE)
        self.view.set_rows([_row(name, None, (hint,)) for name, hint in self.rows])
        self.select_button.setEnabled(bool(self.rows))
        count = len(self.rows)
        self.studio.say(f"{count} unreferenced glyph{model.plural(count)}" if count
                        else "Every glyph is encoded or referenced")
        self.package_id = package.id

    def row_chosen(self, name: str, *args: Any) -> None:
        self.studio.show_glyphs([name])

    def apply(self) -> list[str]:
        """Select the exact candidates only while a fresh scan still gives the same rows."""
        self.studio.check(self.package_id)
        fresh = [tuple(row) for row in self.studio.backends().unreferenced.unreferenced(self.studio.package())]
        if fresh != self.rows:
            raise ValueError("Unreferenced glyphs changed; refresh this tab.")
        names = [name for name, _ in self.rows]
        selected = self.studio.select(names, self.package_id)
        self.last_result = {"selected": len(set(names))}
        self.studio.say(f"Selected {self.last_result['selected']} glyphs in the Font window for review")
        return selected


TAB_CLASSES = {
    "Overview": OverviewTab,
    "Glyph table": GlyphTableTab,
    "Unicode": UnicodeTab,
    "Empty": EmptyTab,
    "Case & small caps": CaseTab,
    "Unreferenced": UnreferencedTab,
}

__all__ = ["TAB_CLASSES", "CaseTab", "EmptyTab", "GlyphTableTab", "OverviewTab", "Tab", "UnicodeTab",
           "UnreferencedTab"]
