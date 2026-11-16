# this_file: src/fontlabapp/components/inspect/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Five original component panels on the verified owned Proof/Names lifecycle.

Controls are constructed before binding. Every action checks exact ordered font
membership, master identity and plain displayed source, including simulations.
"""

from functools import wraps
from importlib import import_module
from typing import Any

from fontlabapp.proof.inspect.ui import ProofDialog
from fontlabapp.core.scripting import close_script_dialog, current_package

api = import_module("fontlabapp.components.inspect.model")


def snapshot_refresh(method: Any) -> Any:
    """Publish complete original scans only after a second source/domain read."""

    @wraps(method)
    def scan(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            self.prepare_initial()
            self.check_domain()
            before = self.source_values()
            if self._key == "components_count_badges" and self._snapshot_valid:
                self.ensure_snapshot()
            self._snapshot_valid = False
            self._scanning = True
            if self._key == "components_missing_bases":
                self._exists = kwargs.get("exists", args[0] if args else None)
            result = method(self, *args, **kwargs)
            after = self.source_values()
            self.check_domain()
            if after != before:
                raise ValueError(
                    "Component source changed during scan; rescan or reopen this tool."
                )
            self.check_results()
            self.check_domain()
            self._source = after
            self._snapshot_valid = self.package is not None
            self._scanned_id = self._bound_id
            self.last_error = None
            return result
        except Exception:
            self.invalidate()
            raise
        finally:
            self._scanning = False

    return scan


def action(method: Any) -> Any:
    """Guard original filters, selections, open/copy and repaint entry points."""

    @wraps(method)
    def guarded(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            if not self._scanning:
                self.ensure_snapshot()
            return method(self, *args, **kwargs)
        except Exception:
            self.invalidate()
            raise

    return guarded


class ComponentsDialog(ProofDialog):
    """Reuse existing signals, selection and late binding without a new UI framework."""

    def __init__(self, parent: Any, title: str, key: str) -> None:
        """Initialize value-only defaults before subclasses build original controls."""
        super().__init__(parent, title, key)
        self.masters, self.current_master = [], ""
        self.selection, self.names, self.glyphs = [], [], []
        self.rows, self.shown, self.counts, self.groups, self.index = [], [], {}, {}, {}
        self._domain, self._membership, self._source = None, (), None
        self._exists, self._scanning = None, False
        self._captured = False
        self.last_error = None

    def load_initial(self) -> None:
        """Capture font/master/selection only after status and Close are available."""
        if self.package is None:
            self._domain, self._membership = ((), ""), ()
            return
        if self._captured:
            self.check_domain()
        self.masters = list(self.package.masters)
        self.current_master = self.package.master
        self._domain = (tuple(self.masters), self.current_master)
        self._membership = tuple(api.font_glyph_names())
        self.names = list(self._membership)
        if self._key == "components_compatibility":
            self.selection = api.selected_names()
            self.scope.setItemText(1, f"Selected glyphs ({len(self.selection)})")
        elif self._key == "components_count_badges":
            self.glyphs = api.selected_glyphs(self.package)
            self.selection = [glyph.name for glyph in self.glyphs]
            self.scroll_area.setMinimumHeight(self.grid_height_hint())
        elif self._key == "components_report":
            self.scope.setItemText(0, f"Current master ({self.current_master})")
            self.scope.setItemText(1, f"All masters ({len(self.masters)})")
        elif self._key == "components_where_used":
            blocked = self.search.blockSignals(True)
            try:
                self.search.setText(api.current_name())
            finally:
                self.search.blockSignals(blocked)
        self.check_domain()
        self._captured = True

    def clear_initial_state(self) -> None:
        """Release partial native handles without losing the captured binding identity."""
        self.masters, self.current_master = [], ""
        self.selection, self.names, self.glyphs = [], [], []

    def check_binding(self) -> None:
        """Reject font switches/closure without touching cached native objects."""
        if self._binding_set:
            active = current_package()
            if (active.id if active is not None else None) != self._bound_id:
                raise ValueError(
                    "The original font is no longer current; reopen this tool."
                )

    def check_domain(self) -> None:
        """Recheck exact current master, ordered masters and whole-font membership."""
        self.check_binding()
        if self.package is None:
            return
        if (tuple(self.package.masters), self.package.master) != self._domain:
            raise ValueError("Masters changed since preview; reopen this tool.")
        if tuple(api.font_glyph_names()) != self._membership:
            raise ValueError("Font glyph order changed; reopen this tool.")

    def source_values(self) -> Any:
        """Read only the native values behind the complete original tool display."""
        if self.package is None:
            return None
        names = (
            self.selection
            if self._key == "components_count_badges"
            else list(self._membership)
        )
        return api.source_values(
            self.package,
            names,
            self.masters,
            geometry=self._key == "components_count_badges",
        )

    def check_results(self) -> None:
        """Ensure cached tables/index and simulated groups match the same final source."""
        if self.package is None:
            return
        if self._key == "components_report":
            expected = api.report(self.package, self.names, self.masters)
            if self.rows != expected:
                raise ValueError("Component report changed; reopen this tool.")
        elif self._key == "components_where_used":
            expected = api.usage_index(self.package, self.names, self.masters)
            if self.index != expected:
                raise ValueError("Component usage changed; reopen this tool.")
        elif self._key == "components_missing_bases":
            expected = api.missing(self.package, self.names, self.masters, self._exists)
            if self.groups != expected:
                raise ValueError("Missing component results changed; rescan this tool.")

    def ensure_snapshot(self) -> None:
        """Refuse stale native actions and recheck the domain after the last read."""
        try:
            self.check_domain()
            if not self._snapshot_valid or self.package is None:
                raise ValueError("Results are incomplete; rescan or reopen this tool.")
            if self.source_values() != self._source:
                raise ValueError(
                    "Component source changed; rescan or reopen this tool."
                )
            self.check_results()
            self.check_domain()
        except Exception:
            self.invalidate()
            raise

    def initial_refresh(self) -> None:
        """Keep failed initial reads visible, empty, diagnosed and closable."""
        grid = getattr(self, "grid", None)
        if grid is not None:
            grid.before_draw, grid.on_error = self.draw_guard, self.paint_failed
            grid.failure_cleanup = self.paint_failed
        try:
            if self._key in {"components_compatibility", "components_missing_bases"}:
                self.rescan()
            elif self._key == "components_count_badges":
                self.refresh()
            else:
                snapshot_refresh(type(self).refresh.__wrapped__)(self)
        except Exception as error:  # noqa: BLE001 - native opening boundary
            self.invalidate()
            self.show_error(error)

    def _connect(self, signal: Any, slot: Any) -> None:
        """Retain original diagnostics and contain every PythonQt callback failure."""

        def reported(*args: Any) -> None:
            try:
                slot(*args)
            except Exception as error:
                self.show_error(error)
                raise

        super()._connect(signal, reported)

    def show_error(self, error: Any) -> None:
        """Preserve the original last_error field and visible status diagnosis."""
        self.last_error = f"{type(error).__name__}: {error}"
        self.status.setText("Error: " + self.last_error)

    def draw_guard(self) -> None:
        """Empty failed panels paint once without repeating an invalidation update."""
        if self._snapshot_valid:
            self.ensure_snapshot()

    def paint_failed(self, text: str) -> None:
        """Clear failed paths and display the painter diagnosis without escaping Qt."""
        self.invalidate()
        self.last_error = text
        self.status.setText("Error: " + text)

    def invalidate(self) -> None:
        """Release all results, source handles and simulation callbacks on failure/Close."""
        self._snapshot_valid, self._scanned_id = False, None
        self.rows, self.shown, self.counts, self.groups, self.index = [], [], {}, {}, {}
        self._exists, self._source = None, None
        self.package = None
        self.clear_initial_state()
        # Initial failures can be retried only against the original numeric binding.
        self._initial_ready = False
        for name in ("table", "tree"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setRowCount(0) if name == "table" else widget.clear()
        grid = getattr(self, "grid", None)
        if grid is not None and grid.cards:
            grid.cards = []
            grid.update()
        for name in ("select_button", "copy_button"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(False)

    def closeEvent(self, event: Any) -> None:
        """Disconnect all owned signals before deletion and discard painter callbacks."""
        grid = getattr(self, "grid", None)
        if grid is not None:
            grid.before_draw = grid.on_error = grid.failure_cleanup = None
        self.invalidate()
        self._bound_id = None
        close_script_dialog(self, event, self._key)
