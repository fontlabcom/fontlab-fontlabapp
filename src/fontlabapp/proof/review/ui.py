# this_file: src/fontlabapp/proof/review/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Two complete read-only reviews on the existing guarded Anchors lifecycle.

Reuse late binding, signals, source publication and terminal invalidation. Override
only candidate inputs and interpolation options/results; keep original controls
in their small menu scripts. Native reads start after status and Close exist.
"""

from importlib import import_module
from typing import Any

from fontlabapp.anchors.inspect.ui import AnchorsDialog
from fontlabapp.components.inspect.ui import ComponentsDialog

cleanup = import_module("fontlabapp.glyphs.unreferenced")
interpolation = import_module("fontlabapp.masters.interpolation.model")
components = import_module("fontlabapp.components.inspect.model")
CLEANUP = "cleanup_unused_glyphs_report"


class ReviewDialog(AnchorsDialog):
    """Bind original review controls without another source or signal framework."""

    def __init__(self, parent: Any, title: str, key: str) -> None:
        """Initialize only plain candidate and blended-node state before controls."""
        super().__init__(parent, title, key)
        self.mix = []

    def load_initial(self) -> None:
        """Capture the same font/domain, then populate actual bound selector choices."""
        if self._reopen_required:
            raise ValueError("The previous source was invalidated; reopen this tool.")
        ComponentsDialog.load_initial(self)
        if self.package is None or self._key == CLEANUP:
            return
        self.names = interpolation.selected_names()
        self.selection = list(self.names)
        self.set_choices(self.glyph_combo, self.names)
        self.set_choices(self.first, self.masters)
        self.set_choices(
            self.second, self.masters, self.masters[-1] if self.masters else ""
        )
        self.check_domain()

    def geometry_names(self) -> list[str]:
        """Guard the complete captured selected outline domain behind the preview."""
        return list(self.selection) if self._key != CLEANUP else []

    def option_values(self) -> tuple:
        """Freeze which original controls produced the cached blended outlines."""
        if self._key == CLEANUP:
            return ()
        return (
            self.glyph_combo.currentText,
            self.first.currentText,
            self.second.currentText,
            self.slider.value,
        )

    def source_values(self) -> Any:
        """Read complete candidate references or selected raw outline geometry."""
        if self.package is None:
            return None
        if self._key == CLEANUP:
            return cleanup.source_values(self.package)
        return components.source_values(
            self.package, self.selection, self.masters, geometry=True
        )

    def check_results(self) -> None:
        """Check original displayed values against a final read of the same source."""
        if self.package is None:
            return
        if self._key == CLEANUP:
            if self.rows != cleanup.unreferenced(self.package):
                raise ValueError("Candidate results changed; reopen this tool.")
            return
        options = (
            self.option_values()
            if self._scanning or self._result_options is None
            else self._result_options
        )
        if not options[0]:
            a, b, mix, message = [], [], [], ""
        else:
            glyph = self.package.findName(options[0])
            layers = interpolation.master_layers(glyph, self.masters)
            first, second = layers.get(options[1]), layers.get(options[2])
            a = interpolation.outline(first) if first is not None else []
            b = interpolation.outline(second) if second is not None else []
            why = interpolation.problem(a, b)
            mix = interpolation.blend(a, b, options[3] / 100.0) if why is None else []
            message = f"Not compatible: {why}" if why is not None else ""
        if (self.view.a, self.view.b, self.view.mix, self.mix, self.view.message) != (
            a,
            b,
            mix,
            mix,
            message,
        ):
            raise ValueError("Interpolation results changed; reopen this tool.")

    def describe_selection(self, what: str = "glyph") -> bool:
        """Retain the original no-font, empty-selection and selected-name subtitle."""
        count = len(self.names)
        if self.package is None:
            self.subtitle.setText("Open a font first.")
            return False
        if not count:
            self.subtitle.setText(
                "Select glyphs in the Font window, then run this script again."
            )
            return False
        shown = ", ".join(self.names[:8]) + (" …" if count > 8 else "")
        self.subtitle.setText(f"{count} {what}{'s' if count != 1 else ''}: {shown}")
        return True

    def paint_report(self, text: str) -> None:
        """Retain the original painter-report result field and visible diagnosis."""
        self.last_error = text
        self.status.setText(text)

    def initial_refresh(self) -> None:
        """Reuse the guarded first scan, then retain the original report hook."""
        super().initial_refresh()
        view = getattr(self, "view", None)
        if view is not None:
            view.report = self.paint_report
            view.on_error = lambda text: (
                view.report(f"Drawing failed: {text}")
                if view.report is not None
                else None
            )

    def invalidate(self) -> None:
        """Release all original review values and settle empty failed paints."""
        view = getattr(self, "view", None)
        populated = view is not None and bool(
            view.a or view.b or view.mix or view.message
        )
        if view is not None:
            view.a, view.b, view.mix, view.message = [], [], [], ""
        self.mix = []
        super().invalidate()
        button = getattr(self, "apply_button", None)
        if button is not None:
            button.setEnabled(False)
        if populated:
            view.update()

    def closeEvent(self, event: Any) -> None:
        """Release the legacy report callback before existing signal/native teardown."""
        view = getattr(self, "view", None)
        if view is not None:
            view.report = None
        super().closeEvent(event)
