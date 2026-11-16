# this_file: src/fontlabapp/proof/inspectors/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Inspector source guards on the existing owned Masters/Proof/Names shell."""

from functools import wraps
from importlib import import_module
from typing import Any

from fontlabapp.masters.inspect.ui import (
    MastersDialog,
    snapshot_refresh as _masters_refresh,
)
from fontlabapp.masters.inspect.model import widths as raw_widths

api = import_module("fontlabapp.proof.inspectors.model")


def snapshot_refresh(method: Any) -> Any:
    """Keep shared scan semantics and check the domain after final source reads."""
    scan = _masters_refresh(method)

    @wraps(method)
    def refresh(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            result = scan(self, *args, **kwargs)
            if (
                self._scope_whole
                and tuple(api.all_names(self.package)) != self._scope_names
            ):
                raise ValueError(
                    "Font glyph order changed during refresh; refresh this tool."
                )
            self.check_binding()
            domain = (
                (tuple(self.package.masters), self.package.master)
                if self.package
                else ((), "")
            )
            if domain != (self._display_masters, self._display_master):
                raise ValueError("Masters changed during refresh; refresh this tool.")
            return result
        except Exception:
            self.invalidate()
            raise

    return refresh


class InspectorsDialog(MastersDialog):
    """Keep original inspector interfaces while sharing lifecycle and selection."""

    def __init__(self, parent: Any, title: str, key: str) -> None:
        """Initialize value-only state before the shared shell builds all controls."""
        self.paths, self.info, self._outline_sources = {}, {}, {}
        if key == "outlines_node_statistics":
            self.flagged = []
        self.ascender, self.descender = 800, -200
        super().__init__(parent, title, key)

    def initial_refresh(self) -> None:
        """Finish original aliases and painter callbacks before the first native read."""
        if self._key == "metrics_width_table":
            self.select_button = self.apply_button
        if self._key == "metrics_spacing_string_preview":
            self.close_button.setDefault(True)
        view = getattr(self, "view", None)
        if view is not None:
            view.before_draw = self.draw_guard
            view.failure_cleanup = self.paint_cleanup
        super().initial_refresh()

    def load_initial(self) -> None:
        """Read scope only after Close exists; spacing does not require selection."""
        if self._key == "metrics_spacing_string_preview":
            self.masters = list(self.package.masters) if self.package else []
            self.current_master = self.package.master if self.package else ""
        else:
            super().load_initial()
        self.sync_controls()
        if self._key == "metrics_width_table":
            self.glyphs = []

    def sync_controls(self) -> None:
        """Populate original selectors after binding, blocking construction signals."""
        for name, values, chosen in (
            ("master", self.masters, self.current_master),
            ("glyph_combo", self.names, self.names[0] if self.names else ""),
        ):
            combo = getattr(self, name, None)
            if combo is None:
                continue
            old = combo.currentText
            previous = combo.blockSignals(True)
            try:
                combo.clear()
                for value in values:
                    combo.addItem(value)
                selected = old if old in values else chosen
                if selected in values:
                    combo.setCurrentIndex(values.index(selected))
            finally:
                combo.blockSignals(previous)
        if self._key == "metrics_width_table":
            self.select_button = self.apply_button

    def apply(self) -> None:
        """Dispatch Width Table's original footer action through its public method."""
        self.select_flagged()

    def source_values(self, *, cached: bool = False) -> Any:
        """Capture/recheck exactly the values behind displayed data and selections."""
        if self.package is None:
            return None
        if self._key == "metrics_width_table":
            rows = (
                self.rows
                if cached
                else api.report(self.require_glyphs(self.names), self.masters)
            )
            raw = tuple(
                (glyph.name, tuple(raw_widths(glyph, self.masters)))
                for glyph in self.require_glyphs(self.names)
            )
            rounded = tuple(
                (name, tuple(values), trend) for name, values, trend in rows
            )
            if tuple(
                (
                    name,
                    tuple(
                        None if value is None else round(value) for _, value in values
                    ),
                )
                for name, values in raw
            ) != tuple((name, values) for name, values, _ in rounded):
                raise ValueError("Widths changed during scan; refresh this tool.")
            self.check_binding()
            if (tuple(self.package.masters), self.package.master) != (
                tuple(self.masters),
                self.current_master,
            ):
                raise ValueError("Masters changed during scan; refresh this tool.")
            return rounded, raw
        if self._key == "outlines_node_statistics":
            whole = self.source.currentIndex == 1
            names = tuple(api.all_names(self.package)) if whole else tuple(self.names)
            if (whole, names) != (self._scope_whole, self._scope_names):
                raise ValueError(
                    "Source scope or font glyph order changed; refresh this tool."
                )
            counts = (
                self.data
                if cached
                else {
                    glyph.name: api.glyph_counts(glyph, self.masters)
                    for glyph in self.require_glyphs(names)
                }
            )
            return whole, names, {name: dict(values) for name, values in counts.items()}
        if self._key == "outlines_contour_order_view":
            name = self.glyph_combo.currentText
            if not name:
                return None
            if cached:
                return name, self.view.columns
            glyph = self.require_glyphs([name])[0]
            return name, [
                (
                    master + (" (auto)" if layer.autoLayer else ""),
                    [] if layer.autoLayer else api.contour_info(layer),
                )
                for master, layer in api.master_layers(glyph, self.masters).items()
            ]
        master = self.chosen_master()
        names = [] if cached else api.parse_text(self.text.text, self.package)
        rows = self.rows if cached else api.layout(self.package, names, master)
        paths = (
            dict(self._outline_sources)
            if cached
            else {
                (name, master): api.outline_source(
                    self.package.findName(name).findLayer(master)
                )
                for name, *_ in rows
            }
        )
        return (
            self.text.text,
            master,
            tuple(rows),
            paths,
            self.ascender if cached else self.package.ascender_value,
            self.descender if cached else self.package.descender_value,
        )

    def require_glyphs(self, names: Any) -> list[Any]:
        """Resolve complete captured membership; never silently drop deleted names."""
        glyphs = [self.package.findName(name) for name in names]
        if any(g is None or g.isNull for g in glyphs):
            raise ValueError("Glyph source changed; refresh or reopen this tool.")
        return glyphs

    def ensure_snapshot(self) -> None:
        """Recheck domain/identity after source scans as well as before the action."""
        try:
            super().ensure_snapshot()
            self.check_binding()
            if (
                self._key == "outlines_node_statistics"
                and self._scope_whole
                and tuple(api.all_names(self.package)) != self._scope_names
            ):
                raise ValueError(
                    "Font glyph order changed during source check; refresh this tool."
                )
            if (tuple(self.package.masters), self.package.master) != (
                self._display_masters,
                self._display_master,
            ):
                raise ValueError(
                    "Masters changed during source check; refresh this tool."
                )
        except Exception:
            self.invalidate()
            raise

    def draw_guard(self) -> None:
        """Allow empty diagnosed paints; refuse stale native values before painting."""
        self.check_binding()
        if self._snapshot_valid:
            self.ensure_snapshot()

    def paint_cleanup(self) -> None:
        """Clear failed values even when the original report hook itself failed."""
        view = getattr(self, "canvas", None) or getattr(self, "view", None)
        error = view.paint_error if view is not None else ""
        self.invalidate()
        if error and not self.last_error:
            self.show_error(RuntimeError(error))

    def invalidate(self) -> None:
        """Clear partial results/paths/handles without replenishing empty repaints."""
        canvas, view = getattr(self, "canvas", None), getattr(self, "view", None)
        populated = bool(self.rows or self.paths or self.info)
        view_populated = view is not None and bool(view.columns)
        super().invalidate()
        self.paths, self.info, self._outline_sources = {}, {}, {}
        if self._key == "outlines_node_statistics":
            self.flagged = []
        if self._key == "metrics_width_table":
            self.glyphs = []
        if view is not None:
            view.columns = []
            if view_populated:
                view.update()
        if canvas is not None and populated:
            canvas.update()
        button = getattr(self, "select_button", None)
        if button is not None:
            button.setEnabled(False)

    def closeEvent(self, event: Any) -> None:
        """Detach all inspector-owned callbacks before shared signal destruction."""
        for name in ("canvas", "view"):
            view = getattr(self, name, None)
            if view is not None:
                view.before_draw = view.on_error = None
                if name == "view":
                    view.failure_cleanup = None
                if name == "canvas":
                    view.owner = None
                else:
                    view.report = None
        super().closeEvent(event)
