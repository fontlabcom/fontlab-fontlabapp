# this_file: src/fontlabapp/features/classes/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Complete class writer on the shared owned snapshot/Close lifecycle."""

from typing import Any
import fontlabapp.features.classes.model as api


def panel_type(core: Any, gui: Any) -> type:
    """Bind only at invocation; keep every native class write behind Apply."""
    from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog

    class CleanClassesDialog(SnapshotTextDialog):
        KEY = "clean_classes"

        def __init__(self, parent: Any, bridge: Any) -> None:
            self.bridge, self.apply_button, self.busy = bridge, None, False
            super().__init__(
                parent,
                "Clean Classes",
                self.KEY,
                "Remove missing glyph names from every OpenType class. Member order and duplicates are kept. Valid classes are left untouched. Review the replacements, then Apply.",
                bridge.capture,
                api.render,
                lambda report: f"{len(api.changes(report))} classes to clean.",
            )
            self.apply_button = gui.QPushButton("Apply")
            self.root.addWidget(self.apply_button)
            self._connect(self.apply_button.clicked, lambda *args: self.apply())
            self.enable_apply()

        def enable_apply(self) -> None:
            """A complete current snapshot is required, including after failures."""
            if self.apply_button is not None and not self._closed:
                self.apply_button.setEnabled(
                    not self._closed
                    and not self.busy
                    and self.report is not None
                    and bool(api.changes(self.report))
                )

        def refresh(self) -> None:
            """Use the shared complete refresh and synchronize the write control."""
            if self.busy or self._closed:
                return
            super().refresh()
            self.enable_apply()

        def apply(self) -> None:
            """Run the real ordered batch; stale or partial results never become success."""
            if self._closed or self.busy or self.report is None:
                return
            self.busy = True
            self.enable_apply()
            result = None
            try:
                result = api.apply(self.bridge, self.report)
                if not self._closed:
                    self.busy = False
                    self.refresh()
                    if self.report is None:
                        raise RuntimeError(
                            "Changes were applied, but the rescan failed; use Edit > Undo if needed."
                        )
                    self.status.setText(
                        f"Cleaned {result['classes']} classes; removed {result['tokens']} missing names."
                    )
            except Exception as error:  # noqa: BLE001 - contain native slot failures
                if not self._closed:
                    self.report = None
                    self.output.clear()
                    self.status.setText(str(error))
            finally:
                self.busy = False
                self.enable_apply()

        def _destroyed(self) -> None:
            """Release the private backend together with the shared exact callbacks."""
            self.bridge = None
            super()._destroyed()

        def closeEvent(self, event: Any) -> None:
            """The backend cannot remain reachable through a closed writer."""
            self.bridge = None
            super().closeEvent(event)

    return CleanClassesDialog
