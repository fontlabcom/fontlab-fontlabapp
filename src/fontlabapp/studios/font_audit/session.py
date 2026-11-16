# this_file: src/fontlabapp/studios/font_audit/session.py
# SPDX-License-Identifier: Apache-2.0
"""Font Audit state: one catalogue read per refresh, previews, selection and the report backends.

What: ``Studio`` reads the current package into a ``_records.Catalogue`` on
``reload`` and re-runs every tab's view; ``preview`` shows glyph names in the
read-only TMetrics (``set_text``); ``select`` puts names in the Font window
through ``core.scripting.select_glyphs`` behind the originals' stale-font
guards; ``metrics`` reads the Overview master rows. Read-only for font data:
no edit, no history, no notify. Its only side effects are the originals':
Font-window selection, CSV files, the clipboard and the Case Coverage and
Smallcap Consistency windows. Qt-free.
Used by ``fontlabapp.studios.font_audit`` (app and tabs).
"""

from collections.abc import Callable
from typing import Any

from fontlabapp.core.scripting import (
    current_package,
    font_audit_backends,
    names_font_window_selection,
    select_glyphs,
)

from .. import _records
from . import model

APP = "Font Audit"
#: Failures shown in the status line instead of raised.
ERRORS = (ValueError, TimeoutError, RuntimeError, ImportError, OSError)
REFRESH_FIRST = "Refresh the report before selecting glyphs."
STALE = "stale font: Refresh the report."


def selected_names() -> list[str]:
    """Font-window selection in font order; [] on a native read error (no current-glyph fallback)."""
    try:
        return list(names_font_window_selection())
    except (AttributeError, RuntimeError, TypeError):
        return []


def font_metrics(package: Any) -> list[tuple]:
    """Font Overview master rows: ``(master, ascender, caps, x-height, descender, kerning pairs)``."""
    import fontlab

    rows = []
    for master in package.masters:
        metrics = fontlab.FontMetrics(package, master)
        rows.append((master, metrics.ascender, metrics.capsHeight, metrics.xHeight, metrics.descender,
                     len(package.kerning(master))))
    return rows


class Studio:
    """Shared Font Audit state for one shell."""

    def __init__(
        self,
        shell: Any,
        *,
        font: Callable[[], Any] | None = None,
        package: Callable[[], Any] | None = None,
        read: Callable[[Any], Any] | None = None,
        metrics: Callable[[Any], list] | None = None,
        selection: Callable[[], list[str]] | None = None,
        select: Callable[..., list[str]] | None = None,
        backends: Callable[[], Any] | None = None,
        case_metadata: Callable | None = None,
        case_preferred: Callable | None = None,
    ) -> None:
        import fontlabapp.fontui as fontui

        self.shell = shell
        self._font = font or fontui.current_font
        self.package = package or current_package
        self.read = read or _records.catalogue
        self.metrics = metrics or font_metrics
        self.selection = selection or selected_names
        self._select = select or select_glyphs
        self.backends = backends or font_audit_backends
        self.case_metadata = case_metadata
        self.case_preferred = case_preferred
        self.catalogue: _records.Catalogue | None = None
        self.views: list[Callable[[], Any]] = []
        self.preview: Any = None

    def font(self) -> Any:
        return self._font()

    def say(self, text: str) -> None:
        self.shell.set_status(text)

    def reload(self) -> _records.Catalogue | None:
        """Read the current package once and refresh every tab; None with no font or on failure."""
        self.catalogue = None
        try:
            package = self.package()
            if package is not None:
                self.catalogue = self.read(package)
        except ERRORS as error:
            self.say(f"{APP}: {error}")
        for view in list(self.views):
            view()
        return self.catalogue

    def show_glyphs(self, names: Any) -> None:
        """Show ``names`` in the TMetrics preview; never writes."""
        text = model.preview_text(names)
        if self.preview is not None and text:
            self.preview.set_text(text)

    def check(self, package_id: Any) -> None:
        """The originals' guard before a selection: a scan exists and its font is still current."""
        if package_id is None:
            raise ValueError(REFRESH_FIRST)
        package = self.package()
        if package is None or package.id != package_id:
            raise ValueError(STALE)

    def select(self, names: Any, package_id: Any) -> list[str]:
        """Select exactly ``names`` in the Font window of the scanned font (replace, not add)."""
        return list(self._select(list(names), package_id=package_id))


__all__ = ["APP", "ERRORS", "REFRESH_FIRST", "STALE", "Studio", "font_metrics", "selected_names"]
