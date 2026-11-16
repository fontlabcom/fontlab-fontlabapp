# this_file: src/fontlabapp/masters/inspect/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Share existing Proof/Names lifecycle for four read-only Masters tools."""

from functools import wraps
from typing import Any

from fontlabapp.proof.inspect.ui import ProofDialog, QtCore, QtGui
from fontlabapp.masters.inspect.model import (
    all_names,
    check_glyph,
    muted,
    overview,
    selected_names,
)
from fontlabapp.core.scripting import close_script_dialog, current_package


def make_table(headers: list[str], min_height: int = 280) -> Any:
    """Create the original nonselectable master table, retaining column sizing."""
    table = QtGui.QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
    table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QtGui.QHeaderView.Stretch)
    header.setSectionResizeMode(0, QtGui.QHeaderView.ResizeToContents)
    table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    table.setMinimumHeight(min_height)
    return table


def fill_table(table: Any, rows: list, highlight: Any = None) -> None:
    """Fill a QTableWidget; a 2-tuple row (label, note) shows the note muted across the row."""
    accent = QtGui.QColor(
        table.palette.color(QtGui.QPalette.Active, QtGui.QPalette.Link),
    )  # copy: color() can alias the palette
    ink = QtGui.QColor(
        table.palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText),
    )  # copy: color() can alias the palette
    note_color = QtGui.QColor(ink)
    note_color.setAlpha(130)
    table.clearSpans()
    table.setRowCount(0)
    table.setRowCount(len(rows))
    for row, cells in enumerate(rows):
        for column, text in enumerate(cells):
            item = QtGui.QTableWidgetItem(text)
            item.setForeground(QtGui.QBrush(ink))
            if len(cells) == 2 and column == 1:
                item.setForeground(QtGui.QBrush(note_color))
                if table.columnCount > 2:
                    table.setSpan(row, 1, 1, table.columnCount - 1)
            elif column:
                item.setTextAlignment(
                    int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter),
                )
                if highlight is not None and highlight(row, column, text):
                    bold = item.font()
                    bold.setBold(True)
                    item.setFont(bold)
                    item.setForeground(QtGui.QBrush(accent))
            table.setItem(row, column, item)


def snapshot_refresh(method: Any) -> Any:
    """Publish complete reads only; failed sources cannot remain actionable."""

    @wraps(method)
    def refresh(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            self.prepare_initial()
            self.check_binding()
            self._snapshot_valid = False
            self.masters = list(self.package.masters) if self.package else []
            self.current_master = self.package.master if self.package else ""
            domain = tuple(self.masters), self.current_master
            result = method(self, *args, **kwargs)
            self.check_binding()
            actual = (
                tuple(self.package.masters) if self.package else (),
                self.package.master if self.package else "",
            )
            if actual != domain:
                raise ValueError(
                    "Masters changed during refresh; refresh this tool again."
                )
            self._display_masters, self._display_master = domain
            self._source = self.source_values(cached=True)
            self._snapshot_valid = self.package is not None
            self._scanned_id = self._bound_id
            self.last_error = ""
            return result
        except Exception:
            self.invalidate()
            raise

    return refresh


class MastersDialog(ProofDialog):
    """Original Masters body/footer on the existing owned panel and binding logic."""

    ACTION = "Apply"

    def __init__(self, parent: Any, title: str, key: str) -> None:
        """Finish all controls and Close before any fallible native source access."""
        super().__init__(parent, title, key)
        self.names, self.masters, self.current_master = [], [], ""
        self.rows, self.data, self.areas = [], {}, {}
        self.results, self.failing, self._structures = {}, [], {}
        self._display_masters, self._display_master, self._source = (), "", None
        self._scope_names, self._scope_whole = (), False
        self.last_error = ""
        self.setMinimumWidth(520)
        palette = self.palette
        ink = QtGui.QColor(
            palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText)
        )
        for group in (QtGui.QPalette.Active, QtGui.QPalette.Inactive):
            for role in (
                QtGui.QPalette.WindowText,
                QtGui.QPalette.Text,
                QtGui.QPalette.ButtonText,
            ):
                palette.setColor(group, role, ink)
            palette.setColor(
                group,
                QtGui.QPalette.Link,
                palette.color(QtGui.QPalette.Active, QtGui.QPalette.Link),
            )
        self.setPalette(palette)
        self.subtitle.setStyleSheet(f"color: {muted(self)};")
        self.build()
        footer = QtGui.QHBoxLayout()
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {muted(self)};")
        footer.addWidget(self.status, 1)
        self.close_button = QtGui.QPushButton("Close")
        footer.addWidget(self.close_button)
        self._connect(self.close_button.clicked, lambda *a: self.close())
        if self.ACTION:
            self.apply_button = QtGui.QPushButton(self.ACTION)
            self.apply_button.setDefault(True)
            footer.addWidget(self.apply_button)
            self._connect(self.apply_button.clicked, lambda *a: self.apply())
        self.root.addLayout(footer)
        chart = getattr(self, "chart", None)
        if chart is not None:
            chart.before_draw = self.check_binding
        self.initial_refresh()

    def _connect(self, signal: Any, slot: Any) -> None:
        """Keep original last_error diagnostics as well as shared guarded callback state."""

        def reported(*args: Any) -> None:
            try:
                slot(*args)
            except Exception as error:
                self.show_error(error)
                raise

        super()._connect(signal, reported)

    def load_initial(self) -> None:
        """Bind original selection/master order without retaining glyph or layer handles."""
        self.names = selected_names() if self.package is not None else []
        self.masters = list(self.package.masters) if self.package is not None else []
        self.current_master = self.package.master if self.package is not None else ""
        source = getattr(self, "source", None)
        if source is not None:
            previous = source.blockSignals(True)
            try:
                source.setItemText(0, f"Selected glyphs ({len(self.names)})")
            finally:
                source.blockSignals(previous)

    def clear_initial_state(self) -> None:
        """Drop incomplete captured source state while retaining only its numeric binding."""
        self.names, self.masters, self.current_master = [], [], ""

    def check_binding(self) -> None:
        """Reject a closed or switched font before cached native access."""
        if self._binding_set:
            active = current_package()
            identity = active.id if active is not None else None
            if identity != self._bound_id:
                raise ValueError(
                    "The original font is no longer current; reopen this tool."
                )

    def source_values(self, *, cached: bool = False) -> Any:
        """Exact structural/metadata values displayed by actionable original panels."""
        if self.package is None:
            return None
        if self._key == "masters_overview":
            rows = tuple(self.rows) if cached else tuple(overview(self.package))
            axes = tuple(
                (axis.name, axis.tag, axis.shortName) for axis in self.package.axes
            )
            return rows, axes
        if self._key == "masters_compatibility_check":
            whole = self._scope_whole if cached else self.source.currentIndex == 1
            names = self._scope_names if cached else tuple(all_names()) if whole else ()
            if not cached and (
                whole != self._scope_whole or (whole and names != self._scope_names)
            ):
                raise ValueError(
                    "Source scope or font glyph order changed; refresh this tool."
                )
            signatures = (
                dict(self._structures)
                if cached
                else {
                    name: check_glyph(self.package.findName(name), self.masters)[0]
                    for name in self._structures
                }
            )
            return whole, names if whole else None, signatures
        return None

    def ensure_snapshot(self) -> None:
        """Preflight identity, active master, master order and exact displayed source."""
        try:
            self.check_binding()
            if not self._snapshot_valid or self.package is None:
                raise ValueError("Results are incomplete; refresh or reopen this tool.")
            if (tuple(self.package.masters), self.package.master) != (
                self._display_masters,
                self._display_master,
            ):
                raise ValueError("Masters changed since preview; refresh this tool.")
            if self.source_values() != self._source:
                raise ValueError("Source changed since preview; refresh this tool.")
        except Exception:
            self.invalidate()
            raise

    def invalidate(self) -> None:
        """Clear all partial results and unsafe native handles before leaving a failed read."""
        self._snapshot_valid, self._scanned_id = False, None
        self.rows, self.data, self.areas, self.results = [], {}, {}, {}
        self.failing, self._structures, self._source = [], {}, None
        self._scope_names, self._scope_whole = (), False
        self.package = None
        self._initial_ready = False
        self.clear_initial_state()
        table = getattr(self, "table", None)
        if table is not None:
            table.setRowCount(0)
        tree = getattr(self, "tree", None)
        if tree is not None:
            tree.clear()
        chart = getattr(self, "chart", None)
        if chart is not None:
            populated = bool(
                chart.masters
                or getattr(chart, "series", [])
                or getattr(chart, "groups", [])
            )
            chart.masters = []
            if hasattr(chart, "series"):
                chart.series = []
            if hasattr(chart, "groups"):
                chart.groups = []
            if populated:
                chart.update()
        button = getattr(self, "apply_button", None)
        if button is not None:
            button.setEnabled(False)

    def initial_refresh(self) -> None:
        """Keep failed initial panels diagnosed, visible and closable."""
        try:
            self.refresh()
        except Exception as error:  # noqa: BLE001 - native opening boundary
            self.show_error(error)

    def show_error(self, error: Any) -> None:
        """Retain the original native scenario diagnostic interface."""
        self.last_error = f"{type(error).__name__}: {error}"
        self.slot_error = repr(error)
        self.status.setText("Error: " + self.last_error)

    def paint_report(self, text: str) -> None:
        """Invalidate the failed chart while preserving a visible native paint diagnosis."""
        self.invalidate()
        self.last_error = text
        self.status.setText(text)

    def form(self) -> Any:
        """Place the original per-tool form on the shared body."""
        grid = QtGui.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.root.addLayout(grid)
        return grid

    def describe_selection(self, what: str = "glyph") -> bool:
        """Describe the original captured selection with its current-font fallback."""
        if self.package is None:
            self.subtitle.setText("Open a font first.")
            return False
        count = len(self.names)
        if not count:
            self.subtitle.setText(
                "Select glyphs in the Font window, then run this script again."
            )
            return False
        shown = ", ".join(self.names[:8]) + (" …" if count > 8 else "")
        self.subtitle.setText(f"{count} {what}{'s' if count != 1 else ''}: {shown}")
        return True

    def scope_combo(self) -> Any:
        """Keep the original current/all-master helper for script-side callers."""
        combo = QtGui.QComboBox()
        combo.addItem(f"Current master ({self.current_master})")
        combo.addItem(f"All masters ({len(self.masters)})")
        self._connect(combo.currentIndexChanged, lambda *a: self.refresh())
        return combo

    def chosen_masters(self) -> list[str]:
        """Return the original scope-combo master selection without changing it."""
        return [self.current_master] if self.scope.currentIndex == 0 else self.masters

    def teardown(self) -> None:
        """Retain the original extension hook before disconnecting owned resources."""

    def glyphs(self) -> list[Any]:
        """Resolve captured names only while the original font remains current."""
        self.check_binding()
        found = (
            [self.package.findName(name) for name in self.names] if self.package else []
        )
        return [glyph for glyph in found if glyph is not None and not glyph.isNull]

    def closeEvent(self, event: Any) -> None:
        """Disconnect every signal and release callbacks before owned native destruction."""
        self.teardown()
        chart = getattr(self, "chart", None)
        if chart is not None:
            chart.report = chart.before_draw = chart.on_error = None
        self.invalidate()
        self._bound_id = None
        close_script_dialog(self, event, self._key)
