# this_file: src/fontlabapp/masters/switcher/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Use the existing owned Masters shell for the compact master-button panel."""

from importlib import import_module
from typing import Any

from fontlabapp.masters.inspect.ui import MastersDialog

data = import_module("fontlabapp.masters.switcher.model")


class SwitcherDialog(MastersDialog):
    """Bind font/master labels after Close exists; reject stale source before clicks."""

    def load_initial(self) -> None:
        """Read complete labels first; glyph selection is not used by this panel."""
        self.names = []
        self.masters = list(self.package.masters) if self.package is not None else []
        self.current_master = self.package.master if self.package is not None else ""
        self._button_values = data.button_values(self.package)
        self.populate_buttons(self._button_values)

    def source_values(self, *, cached: bool = False) -> Any:
        """Compare exact displayed master order/locations with current native source."""
        if self.package is None:
            return None
        return self._button_values if cached else data.button_values(self.package)

    def ensure_snapshot(self) -> None:
        """Allow an outside current-master change, while preserving explicit targets."""
        try:
            self.check_binding()
            if not self._snapshot_valid or self.package is None:
                raise ValueError("Master buttons are incomplete; reopen this tool.")
            if tuple(self.package.masters) != self._display_masters:
                raise ValueError("Masters changed; reopen this tool.")
            if self.source_values() != self._source:
                raise ValueError("Master locations changed; reopen this tool.")
            shown = tuple(
                (master, button.text) for master, button in self.buttons.items()
            )
            expected = tuple(
                (master, master + (f"\n{label}" if label else ""))
                for master, label in self._button_values
            )
            if shown != expected:
                raise ValueError("Master button labels changed; reopen this tool.")
        except Exception:
            self.invalidate()
            raise

    def invalidate(self) -> None:
        """Disable stale buttons and release captured metadata and native font handles."""
        for button in getattr(self, "buttons", {}).values():
            button.setEnabled(False)
        self._button_values = ()
        super().invalidate()
