# this_file: src/fontlabapp/fontui/outline_generators.py
# SPDX-License-Identifier: Apache-2.0
"""Public backend bridge for the outline generator studio's existing writers."""

from importlib import import_module
from typing import Any

MODULES = {
    "contour_copy": "fontlabapp.contours.copy",
    "history": "fontlabapp.core.history.glyphs",
    "layer_writer": "fontlabapp.masters.layers.writer",
    "selection_panel": "fontlabapp.contours.selection.panel.model",
    "outline_panel": "fontlabapp.contours.panel.model",
    "writer": "fontlabapp.contours.writer",
    "metrics": "fontlabapp.metrics.panel.model",
    "angular_session": "fontlabapp.contours.angularizzle.session",
    "angular_native": "fontlabapp.contours.angularizzle.native",
    "angular_settings": "fontlabapp.contours.angularizzle.settings",
    "lifecycle": "fontlabapp.fontui.lifecycle",
    "glyph_copies": "fontlabapp.glyphs.copies",
    "glyph_creation": "fontlabapp.glyphs.creation",
    "qt": "PythonQt",
    "fontlab": "fontlab",
    "fontgate": "fontgate",
    "fl": "fontlab",
}


class Backends:
    """The fixed backend set; native modules load only when a route uses them."""

    def __getattr__(self, name: str) -> Any:
        if name not in MODULES:
            raise AttributeError(name)
        return import_module(MODULES[name])

    def cleanup_failure(self, owner: Any, error: BaseException) -> None:
        """Retain a failed shell owner if its cleanup also fails."""
        from fontlabapp.qt.widgets import _cleanup_failure
        _cleanup_failure(owner, error)


def backends() -> Backends:
    """Return the limited services used by the outline generator studios."""
    return Backends()
