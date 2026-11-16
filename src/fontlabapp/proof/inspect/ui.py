# this_file: src/fontlabapp/proof/inspect/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Share owned Proof panels, complete scans and stale native-wrapper refusal."""

from functools import wraps
from typing import Any

from fontlabapp.glyphs.names.ui import NamesDialog, QtCore, QtGui, muted
from fontlabapp.core.scripting import close_script_dialog, current_package


def snapshot_refresh(method: Any) -> Any:
    """Publish only complete results from the panel's explicitly bound font."""

    @wraps(method)
    def refresh(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            self.prepare_initial()
            self.check_binding()
            result = method(self, *args, **kwargs)
            self.check_binding()
            self._snapshot_valid = self._bound_id is not None
            self._scanned_id = self._bound_id
            return result
        except Exception:
            self.invalidate()
            raise

    return refresh


class ProofDialog(NamesDialog):
    """Reuse the native theme and guarded signals; own only proof UI state."""

    def __init__(self, parent: Any, title: str, key: str) -> None:
        super().__init__(parent, title, key)
        self.package = None
        self._bound_id = None
        self._binding_set = False
        self._initial_ready = False

    def prepare_initial(self) -> None:
        """Read the complete initial font state only after all owned controls exist."""
        if self._initial_ready:
            return
        self.package = None
        self.clear_initial_state()
        package = current_package()
        package_id = package.id if package is not None else None
        if self._binding_set and package_id != self._bound_id:
            raise ValueError(
                "The original font is no longer current; reload or reopen this tool."
            )
        self._bound_id, self._binding_set = package_id, True
        self.package = package
        try:
            self.load_initial()
            self.check_binding()
        except Exception:
            self.package = None
            self.clear_initial_state()
            raise
        self._initial_ready = True

    def clear_initial_state(self) -> None:
        """Discard incomplete source caches while retaining the captured font identity."""
        for name in ("glyphs", "masters"):
            if hasattr(self, name):
                setattr(self, name, [])
        if hasattr(self, "cmap"):
            self.cmap, self.names = {}, set()
        if hasattr(self, "available"):
            self.available = set()

    def add_proof_view(
        self, view: Any, *, background: bool = False, horizontal_off: bool = False
    ) -> None:
        """Own the original scroll wrapper and bind its cached painter callbacks."""
        view.before_draw = self.check_binding
        view.on_error = self.drawing_failed
        self.scroll_area = QtGui.QScrollArea()
        self.scroll_area.setWidget(view)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setFrameShape(QtGui.QFrame.NoFrame)
        if background:
            self.scroll_area.setBackgroundRole(QtGui.QPalette.Base)
            self.scroll_area.setAutoFillBackground(True)
        if horizontal_off:
            self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.root.addWidget(self.scroll_area, 1)

    def add_proof_footer(
        self, *, copy_words: bool = False, reload_selection: bool = False
    ) -> None:
        """Create the original status/Copy/Reload/Close controls on the shared shell."""
        footer = QtGui.QHBoxLayout()
        self.status = QtGui.QLabel()
        self.status.setStyleSheet(f"color: {muted(self)};")
        footer.addWidget(self.status, 1)
        if copy_words:
            self.copy_button = QtGui.QPushButton("Copy words")
            footer.addWidget(self.copy_button)
        if reload_selection:
            self.reload_button = QtGui.QPushButton("Reload selection")
            footer.addWidget(self.reload_button)
        self.close_button = QtGui.QPushButton("Close")
        footer.addWidget(self.close_button)
        self.root.addLayout(footer)

    def initial_refresh(self) -> None:
        """Keep a closable empty panel and visible diagnosis after an opening read failure."""
        try:
            self.refresh()
        except Exception as error:  # noqa: BLE001 - contain native callback errors
            self.invalidate()
            self.slot_error = repr(error)
            self.status.setText("Error: " + self.slot_error)

    def check_binding(self) -> None:
        """Check current identity before dereferencing any cached native wrapper."""
        if self._bound_id is not None and current_package(self._bound_id) is None:
            raise ValueError(
                "The original font is no longer current; reload or reopen this tool."
            )

    def ensure_snapshot(self) -> None:
        """Refuse stale Copy and draw callbacks without accessing closed packages."""
        try:
            self.check_binding()
            if not self._snapshot_valid:
                raise ValueError("Results are incomplete; reload or reopen this tool.")
        except Exception:
            self.invalidate()
            raise

    def drawing_failed(self, text: str) -> None:
        """Clear incomplete proofs and surface native painter failures honestly."""
        self.invalidate()
        self.status.setText("Drawing failed: " + text)

    def invalidate(self) -> None:
        """Clear partial native outlines, rows and words without changing the font."""
        self._snapshot_valid, self._scanned_id = False, None
        for name in ("rows", "words", "glyph_names"):
            if hasattr(self, name):
                setattr(self, name, [])
        grid = getattr(self, "grid", None)
        if grid is not None and grid.cells:
            grid.cells, grid.masters, grid.painted = [], [], 0
            grid.update()
        view = getattr(self, "view", None)
        if view is not None:
            if hasattr(view, "rows") and view.rows:
                view.rows = []
                view.update()
            elif hasattr(view, "run") and (view.run or view.sizes):
                view.run, view.sizes, view.width_units = [], [], 0
                view.update()
        listing = getattr(self, "result_view", None)
        if listing is not None:
            listing.setPlainText("")
        button = getattr(self, "copy_button", None)
        if button is not None:
            button.setEnabled(False)

    def closeEvent(self, event: Any) -> None:
        """Clear bound callbacks and disconnect all owned signals before deletion."""
        for name in ("grid", "view"):
            view = getattr(self, name, None)
            if view is not None:
                view.before_draw = view.on_error = None
        self.invalidate()
        self.glyphs = []
        self.package = None
        self._bound_id = None
        close_script_dialog(self, event, self._key)
