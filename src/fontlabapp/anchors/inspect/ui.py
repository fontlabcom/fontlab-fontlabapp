# this_file: src/fontlabapp/anchors/inspect/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Anchor-specific state on the verified Components/Proof/Names lifecycle.

Only Compatibility's explicit rescan adopts changed anchor values. Selector and
paint actions validate the previous source before drawing their new options.
"""

from functools import wraps
from importlib import import_module
from typing import Any

from fontlabapp.components.inspect.ui import (
    ComponentsDialog,
    action,
    snapshot_refresh as _component_refresh,
)

api = import_module("fontlabapp.anchors.inspect.model")


def snapshot_refresh(method: Any) -> Any:
    """Keep existing complete-scan guards and freeze each displayed geometry scope."""
    scan = _component_refresh(method)

    @wraps(method)
    def refresh(self: Any, *args: Any, **kwargs: Any) -> Any:
        if self._scanning:
            return method(self, *args, **kwargs)
        try:
            self.prepare_initial()
            self.check_domain()
            explicit_rescan = (
                self._key == "anchors_compatibility_report"
                and method.__name__ == "rescan"
            )
            if self._snapshot_valid and not explicit_rescan:
                self.ensure_snapshot()
            self._draw_names = self.geometry_names()
            result = scan(self, *args, **kwargs)
            if self.geometry_names() != self._draw_names:
                raise ValueError(
                    "Displayed glyph scope changed during scan; reopen this tool."
                )
            self._result_options = self.option_values()
            self.check_domain()
            self._ever_published = self._ever_published or self._snapshot_valid
            return result
        except Exception:
            self.invalidate()
            raise

    return refresh


class AnchorsDialog(ComponentsDialog):
    """Retain original anchor interfaces without another signal/binding framework."""

    def __init__(self, parent: Any, title: str, key: str) -> None:
        """Construct only plain state before the original controls and Close."""
        super().__init__(parent, title, key)
        self.bases, self.marks, self._draw_names = [], [], []
        self.points, self.offsets = {}, {}
        self._result_options = None
        self._ever_published = self._reopen_required = False
        self._selection_domain = None

    def set_choices(self, combo: Any, values: list[str], chosen: str = "") -> None:
        """Populate original selectors after binding with construction signals blocked."""
        previous = combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItems(values)
            if chosen in values:
                combo.setCurrentIndex(values.index(chosen))
        finally:
            combo.blockSignals(previous)

    def load_initial(self) -> None:
        """Reuse ordered font/master capture; defer all anchor reads until Close exists."""
        if self._reopen_required:
            raise ValueError("The previous source was invalidated; reopen this tool.")
        super().load_initial()
        if self.package is None:
            return
        if self._key == "anchors_cloud_view":
            self.glyphs = api.selected_glyphs(self.package)
            self.selection = [glyph.name for glyph in self.glyphs]
            self.set_choices(self.name, api.anchor_names(self.glyphs, self.masters))
        elif self._key == "anchors_compatibility_report":
            if self._selection_domain is None:
                self._selection_domain = tuple(api.exact_selected_names())
            self.selection = list(self._selection_domain)
            self.scope.setItemText(1, f"Selected glyphs ({len(self.selection)})")
        else:
            self.bases, self.marks = api.classify(
                self.package, self.names, self.current_master
            )
            chosen = [name for name in api.selected_names() if name in self.bases]
            self.set_choices(self.base, self.bases, chosen[0] if chosen else "")
            self.set_choices(self.mark, self.marks)
        self.check_domain()

    def geometry_names(self) -> list[str]:
        """Return the plain displayed glyph domain independently of anchor selectors."""
        if self._key == "anchors_cloud_view":
            return list(self.selection)
        if self._key == "anchors_mark_attachment_preview":
            return list(
                dict.fromkeys(
                    name
                    for name in (self.base.currentText, self.mark.currentText)
                    if name
                )
            )
        return []

    def source_values(self) -> Any:
        """Compare raw anchors and the previously captured displayed outline domain."""
        if self.package is None:
            return None
        names = self.selection if self._key == "anchors_cloud_view" else self.names
        return api.source_values(self.package, names, self.masters, self._draw_names)

    def option_values(self) -> tuple:
        """Freeze which original selectors produced the current cached display."""
        if self._key == "anchors_cloud_view":
            return (self.name.currentText,)
        if self._key == "anchors_compatibility_report":
            return (self.scope.currentIndex,)
        return self.base.currentText, self.mark.currentText, self.family.currentText

    def check_results(self) -> None:
        """Check original displayed data against a final read of the same native source."""
        if self.package is None:
            return
        options = (
            self.option_values()
            if self._scanning or self._result_options is None
            else self._result_options
        )
        if self._key == "anchors_compatibility_report":
            names = self.names if options[0] == 0 else self.selection
            expected = api.anchor_sets(self.package, names, self.masters)
            actual = self.rows
        elif self._key == "anchors_cloud_view":
            name = options[0]
            expected = {
                master: api.cloud(self.glyphs, master, name) if name else []
                for master in self.masters
            }
            actual = self.points
        else:
            expected = {}
            for master in self.masters:
                base = api.attachment_layer_of(self.package, options[0], master)
                mark = api.attachment_layer_of(self.package, options[1], master)
                if base is not None:
                    expected[master] = (
                        api.attachment(base, mark, options[2])
                        if mark is not None and options[2]
                        else None
                    )
            actual = self.offsets
        if actual != expected:
            raise ValueError("Anchor results changed during scan; reopen this tool.")

    def draw_guard(self) -> None:
        """Refuse an unrefreshed option change before painting cached panel data."""
        if self._snapshot_valid and self.option_values() != self._result_options:
            self.invalidate()
            raise ValueError(
                "Displayed options changed without refresh; reopen this tool."
            )
        super().draw_guard()

    def initial_refresh(self) -> None:
        """Finish callbacks and show a complete empty diagnosed panel after read errors."""
        view = getattr(self, "view", None)
        if view is not None:
            view.before_draw = self.draw_guard
            view.on_error = view.failure_cleanup = self.paint_failed
        try:
            if self._key == "anchors_compatibility_report":
                self.rescan()
            elif self._key == "anchors_mark_attachment_preview":
                self.pair_changed()
            else:
                self.refresh()
        except Exception as error:  # noqa: BLE001 - native opening boundary
            self.invalidate()
            self.show_error(error)

    def invalidate(self) -> None:
        """Release all anchor results/native paths; empty paints do not queue updates."""
        if self._ever_published and self._key != "anchors_compatibility_report":
            self._reopen_required = True
        view = getattr(self, "view", None)
        populated = view is not None and bool(view.panels)
        if view is not None:
            view.panels = []
        self.points, self.offsets = {}, {}
        self.bases, self.marks, self._draw_names = [], [], []
        self._result_options = None
        super().invalidate()
        if populated:
            view.update()

    def closeEvent(self, event: Any) -> None:
        """Disconnect all owned callbacks before the shared native widget teardown."""
        self._selection_domain = None
        view = getattr(self, "view", None)
        if view is not None:
            view.before_draw = view.on_error = view.failure_cleanup = None
        super().closeEvent(event)
