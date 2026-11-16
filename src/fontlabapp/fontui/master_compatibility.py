# this_file: src/fontlabapp/fontui/master_compatibility.py
# SPDX-License-Identifier: Apache-2.0
"""Browse one borrowed font and compare its stored native master topology."""

from time import monotonic
from typing import Any

from .glyph_metrics import MetricsInspector

__all__ = ("show",)
_HANDLES = []


def capture(font: Any, name: str) -> Any:
    """Read existing layer diagnostics twice; reject missing or changing masters."""
    from fontlabapp.masters.layers.compatibility.model import GlyphLayers
    from fontlabapp.masters.layers.compatibility.native import _layers
    from fontlabapp.masters.layers.compatibility._records import check

    deadline = monotonic() + 2.0
    backend = getattr(font, "_backend", None)
    if not callable(getattr(backend, "_package", None)):
        raise ValueError("A registered FontLab font is required")

    def read() -> tuple:
        font._check()
        if font._backend is not backend:
            raise ValueError("Borrowed font backend changed")
        package = backend._package()
        masters = tuple(package.masters)
        if (package.fgId != backend.font_id or not masters
                or any(not isinstance(m, str) or not m for m in masters)
                or len(set(masters)) != len(masters)):
            raise ValueError("Registered font or master identity is invalid")
        glyph = package.findName(name)
        if glyph is None or glyph.isNull or glyph.name != name or glyph.package.id != package.id:
            raise ValueError("Selected glyph is missing or belongs to another font")
        layers, domain = _layers(glyph, masters, deadline)
        found = {layer.name: layer for layer in layers}
        missing = tuple(m for m in masters if m not in found)
        if missing:
            raise ValueError("Missing master layers: " + ", ".join(missing))
        return package.id, glyph.id, masters, domain, GlyphLayers(name, tuple(found[m] for m in masters))

    first = read()
    if first != read():
        raise ValueError("Font, masters or topology changed; refresh")
    check(deadline)
    return first[-1]


class CompatibilityBrowser(MetricsInspector):
    """Compose the existing browser/preview and compatibility report."""

    def __init__(self, qt: Any, font: Any) -> None:
        super().__init__(qt, font)
        self._generation = 0

    def build(self, content: Any) -> None:
        from . import _construct
        from .native import Browser

        gui = self.qt.QtGui
        layout = gui.QVBoxLayout(content)
        self.comparison, self.status = gui.QLabel(content), gui.QLabel(content)
        self.comparison.setWordWrap(True)
        self.status.setText("Select a glyph; structural checks are not an export certificate")
        layout.addWidget(self.status)
        layout.addWidget(self.comparison)
        self._wire(content)
        self.browser = _construct(Browser, self.font, content, None, False, False, self.selected)
        layout.addWidget(self.browser.widget)

    def selected(self, font: Any, names: tuple[str, ...]) -> None:
        from fontlabapp.masters.layers.compatibility.model import render

        if self._closing:
            return
        self._generation += 1
        generation = self._generation
        self.rows = ()
        self.comparison.setText("")
        try:
            if font is not self.font:
                raise ValueError("Selection belongs to another font")
            if not names:
                self.status.setText("Select a glyph")
                return
            group = capture(font, names[0])
            text = render((group,))
            if not self._closing and generation == self._generation:
                self.rows = (group,)
                self.comparison.setText(text)
                self.status.setText("Stored master topology; coordinates, hints and transforms are not compared")
        except Exception as error:
            if not self._closing and generation == self._generation:
                self._clear_preview()
                self.status.setText(str(error))

    def release(self) -> bool:
        complete = super().release()
        if complete and self in _HANDLES:
            _HANDLES.remove(self)
        return complete


def show(font: Any, parent: Any = None) -> CompatibilityBrowser:
    """Open a retained read-only browser; never switch masters or close the font."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog, OwnedWidget
    from .lifecycle import Owned

    qt = _native("PythonQt")
    owner = CompatibilityBrowser(qt, font)
    _HANDLES.append(owner)
    try:
        host = parent if parent is not None else main_window(_native("fontlab"), qt)
        owner.owned = create_dialog(host, "Master Compatibility Browser", owner.build)
    except BaseException as error:
        owner.problems.append(error)
        pending = [error]
        while pending:
            failure = pending.pop()
            failed = getattr(failure, "owner", None)
            if isinstance(failed, OwnedWidget):
                owner.owned = failed
            elif isinstance(failed, Owned):
                owner._failed_owners.append(failed)
            if isinstance(failure, BaseExceptionGroup):
                pending.extend(failure.exceptions)
        try:
            if not owner.release():
                error.add_note("Compatibility browser cleanup incomplete; owner retained")
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note("Compatibility browser cleanup interrupted; owner retained")
        raise
    return owner
