# this_file: src/fontlabapp/metrics/panel/ui.py
# SPDX-License-Identifier: Apache-2.0
"""The non-modal ``MetricsPanel`` base of the Metrics scripts (PythonQt).

Load it through ``fontlabapp.metrics.panel.model.panel_type()``, inside FontLab
only: this module imports PythonQt at load time, like ``_names_dialog``. The
plan and write model lives in ``fontlabapp.metrics.panel.model``.
"""

from types import SimpleNamespace
from typing import Any

import fontlabapp.core.edit_guards as edit_guards

from fontlabapp import _native
from fontlabapp.core.history.glyphs import AutoFacts, scan_auto_facts
from fontlabapp.metrics.panel.model import (
    ALLOW_AUTO_LABEL,
    MAX_NAMES,
    MAX_ROWS,
    NOTE_LIMIT,
    Entry,
    Planner,
    auto_dependants,
    commit,
    make_table,
    muted,
    pending,
    rebuild_note,
    survey,
)
from fontlabapp.fontui.lifecycle import follow_history
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import (
    close_script_dialog,
    connect_guarded,
    current_package,
    names_selected_names,
)

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


class MetricsPanel(QtGui.QDialog):
    """Non-modal panel: masters, script controls, live preview table, Apply, Close.

    What: a subclass sets ``TITLE``, ``KEY``, ``HEADERS`` (preview columns
    after "Glyph · master") and ``ACCENT`` (column numbers shown bold in the
    link colour), and fills in ``build``, ``subtitle_hint`` and ``planner``.
    Optional hooks: ``target_glyphs``, ``empty_message``, ``sync_controls``.

    How: every control change recomputes the preview from the live font.
    Component facts are shared by transitive skips and rebuild warnings;
    construction, Undo/Redo, Refresh, Use selection and Apply refresh them.
    Apply plans again with fresh facts and writes through
    ``metrics_panel.commit`` (one Undo step, geometry policy). The panel binds
    to the font that was current when it opened; a switched font is refused.
    A base of auto composites needs the ``ALLOW_AUTO_LABEL`` tick, and the
    tick belongs to exactly the glyphs that change now.

    Why: the preview can never be stale at Apply, and slot errors stay in the
    status line instead of reaching FontLab. Show it with
    ``scripting.show_script_dialog(Subclass, Subclass.KEY)``.
    """

    TITLE = ""
    KEY = ""
    HEADERS: tuple[str, ...] = ()
    ACCENT: tuple[int, ...] = ()
    MIN_WIDTH = 560

    def __init__(self, parent: Any = None) -> None:
        """Build all widgets first. Read the font only after the Close button exists."""
        QtGui.QDialog.__init__(self, parent)
        self._connections: list[Any] = []
        self._completion_lifetime = install(self, self.KEY)
        self.entries: list[Entry] = []
        self.names: list[str] = []
        self.package_id: int | None = None
        self.master: str | None = None
        self._history_connections = 0
        self.last_result: dict[str, Any] = {}
        self._override_for: frozenset[str] | None = None
        self._rebuild_cache: dict[frozenset[str], str] = {}
        self._facts: AutoFacts | None = None
        palette = self.palette  # FontLab may pair a light Base with a light Text.
        palette.setColor(QtGui.QPalette.Text, palette.color(QtGui.QPalette.WindowText))
        self.setPalette(palette)
        ink = palette.color(QtGui.QPalette.WindowText).name()
        self.setStyleSheet(f"QAbstractSpinBox, QAbstractItemView {{ color: {ink}; }}")
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(self.MIN_WIDTH)

        root = QtGui.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)
        heading = QtGui.QLabel(self.TITLE)
        font = heading.font
        font.setPointSizeF(font.pointSizeF() * 1.35)
        font.setBold(True)
        heading.setFont(font)
        root.addWidget(heading)
        self.subtitle = QtGui.QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet(f"color: {muted(self)};")
        root.addWidget(self.subtitle)
        self.form = QtGui.QGridLayout()
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(8)
        self.form.setColumnStretch(1, 1)
        root.addLayout(self.form)
        self.scope = QtGui.QComboBox()
        self.scope.addItem("Current master")
        self.scope.addItem("All masters")
        self.form.addWidget(QtGui.QLabel("Masters"), 0, 0)
        self.form.addWidget(self.scope, 0, 1, 1, 3)
        self.table = make_table(["Glyph · master", *self.HEADERS])
        self.allow_auto = QtGui.QCheckBox(ALLOW_AUTO_LABEL)
        self.allow_auto.setVisible(False)
        footer = QtGui.QHBoxLayout()
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {muted(self)};")
        footer.addWidget(self.status, 1)
        self.selection_button = QtGui.QPushButton("Use selection")
        self.refresh_button = QtGui.QPushButton("Refresh")
        self.close_button = QtGui.QPushButton("Close")
        self.apply_button = QtGui.QPushButton("Apply")
        self.apply_button.setDefault(True)
        for button in (self.selection_button, self.refresh_button, self.close_button, self.apply_button):
            footer.addWidget(button)
        self.build()
        root.addWidget(self.table, 1)
        root.addWidget(self.allow_auto)
        root.addLayout(footer)
        connect_guarded(self, self.allow_auto.toggled, lambda *a: self.override_toggled())
        connect_guarded(self, self.scope.currentIndexChanged, lambda *a: self.refresh())
        connect_guarded(self, self.selection_button.clicked, lambda *a: self.reselect())
        connect_guarded(self, self.refresh_button.clicked, lambda *a: self.refresh_target())
        connect_guarded(self, self.apply_button.clicked, lambda *a: self.apply())
        connect_guarded(self, self.close_button.clicked, lambda *a: self.close())
        try:
            package = current_package()
            if package is not None:
                self.package_id = package.id
                self.master = package.master
                self.names = names_selected_names()
            self.refresh()
        except Exception as error:  # noqa: BLE001 - keep a failed panel visible and closable
            self.status.setText(f"Error: {error!r}")
        try:
            self._history_connections = follow_history(
                SimpleNamespace(connect=self._connect_history), self.refresh_target
            )
        except Exception as error:  # noqa: BLE001 - manual Refresh remains available
            self.status.setText(f"Automatic Undo/Redo refresh unavailable; use Refresh. {error!r}")

    def _connect_history(self, signal: Any, callback: Any) -> None:
        """Adapt history subscriptions to the panel's guarded owned connections."""
        def slot(*args: Any) -> None:
            if self._completion_lifetime.closed:
                return
            try:
                callback(*args)
            except Exception as error:  # noqa: BLE001 - contain native callback failures
                self.status.setText(f"Error: {error!r}")

        if signal.connect(slot) is False:
            raise RuntimeError("History signal connection refused")
        self._connections.append((signal, slot))

    # ----- hooks for subclasses
    def build(self) -> None:
        """Create the controls. Add them to ``self.form`` from row 1 on; row 0 holds the masters."""
        raise NotImplementedError

    def subtitle_hint(self) -> str:
        """Return one sentence that says what the current settings will do."""
        raise NotImplementedError

    def target_glyphs(self, package: Any) -> list[Any]:
        """Return the glyphs to edit. The default is the captured selection."""
        found = [package.findName(name) for name in self.names]
        if any(g is None or g.isNull for g in found):
            raise ValueError("A captured glyph is missing. Press Use selection to choose again.")
        return found

    def planner(self, package: Any, glyphs: list[Any]) -> Planner:
        """Return the function that plans one layer for the current settings."""
        raise NotImplementedError

    def empty_message(self) -> str:
        """Return the reason shown when no glyph qualifies."""
        return "Select glyphs in the Font window. Then press Use selection."

    def sync_controls(self) -> None:
        """Enable or disable controls to match the other controls. Default: nothing."""

    # ----- helpers for subclasses
    def watch(self, signal: Any) -> None:
        """Refresh the preview whenever ``signal`` fires (guarded slot)."""
        connect_guarded(self, signal, lambda *a: self.refresh())

    def spin(self, low: int, high: int, value: int, suffix: str = "") -> Any:
        """Return a right-aligned integer spin box that refreshes the preview."""
        box = QtGui.QSpinBox()
        box.setRange(low, high)
        box.setValue(value)
        box.setAlignment(QtCore.Qt.AlignRight)
        if suffix:
            box.setSuffix(suffix)
        self.watch(box.valueChanged)
        return box

    # ----- font access
    def font_package(self) -> Any:
        """Return the bound font. Refuse a closed or switched font (``ValueError``)."""
        if self.package_id is None:
            raise ValueError("Open a font and select glyphs. Then run this script again.")
        package = current_package()
        if package is None or package.id != self.package_id:
            raise ValueError("The font changed. Run this script again.")
        return package

    def chosen_masters(self, package: Any) -> list[str]:
        """Return the captured master, or all masters requested by the control."""
        if self.scope.currentIndex == 0:
            if self.master not in package.masters:
                raise ValueError("The captured master is missing. Press Use selection to choose again.")
            return [self.master]
        return list(package.masters)

    def make_entries(self) -> list[Entry]:
        """Plan all target layers from the live font."""
        package = self.font_package()
        glyphs = self.target_glyphs(package)
        if not glyphs:
            raise ValueError(self.empty_message())
        if self._facts is None:
            self._facts = scan_auto_facts(package)
        return survey(glyphs, self.chosen_masters(package), self.planner(package, glyphs), facts=self._facts)

    # ----- actions
    def reselect(self) -> None:
        """Take the glyph selection from the Font window again."""
        package = self.font_package()
        self.names, self.master = names_selected_names(), package.master
        self.refresh_target()

    def refresh_target(self) -> None:
        """Reload dependency facts and the plan without replacing captured targets or settings."""
        if self._completion_lifetime.closed:
            return
        self._facts = None
        self._rebuild_cache = {}
        self.refresh()

    def refresh(self) -> None:
        """Recompute the preview. Any refusal disables Apply and shows its reason."""
        self.sync_controls()
        try:
            self.entries = self.make_entries()
        except Exception as error:  # noqa: BLE001 - a native read can fail; show it, stay open
            self.entries = []
            self.table.setRowCount(0)
            self.apply_button.setEnabled(False)
            if isinstance(error, ValueError):
                self.subtitle.setText(str(error))
                self.status.setText("")
            else:
                self.status.setText(f"Error: {error!r}")
            return
        seen = list(dict.fromkeys(e.glyph.name for e in self.entries))
        shown = ", ".join(seen[:MAX_NAMES]) + (" …" if len(seen) > MAX_NAMES else "")
        self.subtitle.setText(f"{self.subtitle_hint()} ({shown})")
        self.fill_table()
        todo = pending(self.entries)
        note = self.rebuild_note_for(todo)
        names = frozenset(e.glyph.name for e in todo)
        if self.allow_auto.isChecked() and (not note or self._override_for != names):
            self.allow_auto.blockSignals(True)  # The tick belonged to other glyphs.
            self.allow_auto.setChecked(False)
            self.allow_auto.blockSignals(False)
            self._override_for = None
        blocked = bool(note) and not self.allow_auto.isChecked()
        self.allow_auto.setVisible(bool(note))
        self.apply_button.setEnabled(bool(todo) and not blocked)
        text = f"{len(todo)} layer{'s' if len(todo) != 1 else ''} will change"
        if not todo:
            text = "Nothing to change"
        if len(self.rows()) > MAX_ROWS:
            text += f" · table shows the first {MAX_ROWS}"
        if blocked:
            text = self.refusal(note)
        self.status.setText(f"{text} · {note}" if note and not blocked else text)

    def override_toggled(self) -> None:
        """Bind a tick to the glyphs that change now. Another set needs a new tick."""
        names = frozenset(e.glyph.name for e in pending(self.entries))
        self._override_for = names if self.allow_auto.isChecked() else None
        self.refresh()

    def overridden(self, entries: list[Entry]) -> bool:
        """Return True when the tick belongs to exactly these changed glyphs."""
        names = frozenset(e.glyph.name for e in pending(entries))
        return self.allow_auto.isChecked() and self._override_for == names

    def refusal(self, note: str) -> str:
        """Return the text that says why a base of auto glyphs is not edited."""
        return f'Refused. {note}. Tick "{ALLOW_AUTO_LABEL}" to go on.'

    def rows(self) -> list[Entry]:
        """Return the entries that get a table row: edits and explained skips, not no-ops."""
        return [e for e in self.entries if e.plan is None or e.plan.changed]

    def fill_table(self) -> None:
        """Show the plan. ``ACCENT`` columns use the bold link colour."""
        accent = QtGui.QColor(self.palette.color(QtGui.QPalette.Link))
        shown = self.rows()[:MAX_ROWS]
        self.table.clearContents()  # a reused row must not keep cells from an earlier plan
        self.table.setRowCount(len(shown))
        for row, entry in enumerate(shown):
            label = f"{entry.glyph.name} · {entry.master}"
            cells = [label, *entry.plan.cells] if entry.plan is not None else [label, entry.note]
            for column, text in enumerate(cells):
                item = QtGui.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                if entry.plan is not None and column in self.ACCENT:
                    bold = item.font()
                    bold.setBold(True)
                    item.setFont(bold)
                    item.setForeground(QtGui.QBrush(accent))
                self.table.setItem(row, column, item)

    def rebuild_note_for(self, todo: list[Entry]) -> str:
        """Return the rebuild warning for ``todo``. Cache it per set of glyph names."""
        names = frozenset(e.glyph.name for e in todo)
        if names not in self._rebuild_cache:
            self._rebuild_cache = {names: rebuild_note(auto_dependants(self._facts, names))}
        return self._rebuild_cache[names]

    def apply(self) -> None:
        """Plan and scan again from the live font, then write. One Undo step."""
        try:
            facts = scan_auto_facts(self.font_package())
            self._facts = facts
            entries = self.make_entries()
            names = frozenset(e.glyph.name for e in pending(entries))
            note = rebuild_note(auto_dependants(facts, names))
            self._rebuild_cache = {names: note}
            allowed = self.overridden(entries)
            if note and not allowed:
                raise ValueError(self.refusal(note))
            result = commit(self.TITLE, entries, facts=facts, allow_bases=allowed)
        except Exception as error:  # noqa: BLE001 - report in the panel, never into the host
            self.refresh()
            self.status.setText(str(error) if isinstance(error, ValueError) else f"Error: {error!r}")
            return
        self.last_result = result
        self.refresh()
        layers, glyphs = result["layers"], result["glyphs"]
        text = (
            f"Changed {layers} {'layer' if layers == 1 else 'layers'} "
            f"in {glyphs} {'glyph' if glyphs == 1 else 'glyphs'}"
        )
        if result["auto_skipped"]:
            skipped = result["auto_skipped"]
            text += f" · {skipped} {'layer' if skipped == 1 else 'layers'} skipped (auto)"
        if result["mismatches"]:
            count = len(result["mismatches"])
            text += f" · {count} did not read back as planned: " + "; ".join(
                result["mismatches"][:NOTE_LIMIT]
            )
        queued = result.get("pending_note", "")
        note = " · ".join(filter(None, (note, queued)))
        text = f"{text} · {note}" if note else text
        if self._history_connections != 2:
            text += " · after Edit > Undo/Redo press Refresh to update the plan"
        self.status.setText(text)

    def closeEvent(self, event: Any) -> None:
        """Disconnect owned signals. Then delete the panel."""
        close_script_dialog(self, event, self.KEY)
