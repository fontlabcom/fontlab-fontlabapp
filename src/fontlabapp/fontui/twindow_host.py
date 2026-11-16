# this_file: src/fontlabapp/fontui/twindow_host.py
# SPDX-License-Identifier: Apache-2.0
"""Optional native text bridge alongside the existing Fontport edit protocol.

Outline and metric writes stay on Fontport's explicit-layer ``edit_glyph`` and
kerning ``apply`` boundaries. This host supplies notifications and the active
Glyph window's literal text, without importing native modules in offline tests.
"""

from collections.abc import Callable
from typing import Any, Protocol


class Host(Protocol):
    """Injectable notification/text boundary shared by the T windows."""

    def read_text(self) -> str | None:
        """Return available literal text, or None without an accessible target."""
        ...

    def write_text(self, text: str) -> bool:
        """Write available literal text; False means the target is inaccessible."""
        ...

    def subscribe(
        self, owner: Any, callback: Callable, fonts: Callable, text_callback: Callable | None = None
    ) -> None:
        """Attach notifications and polling to the window's owned lifetime.

        Font changes call ``callback``; a host-text change calls ``text_callback``
        (default: ``callback``).
        """
        ...


class FontLabHost:
    """Follow one font and one exact active Glyph-window text block.

    shortcut: named/layer-specific symbols are not literal text, support their
    round trip only after a lossless shared token parser is available.
    """

    def __init__(self, font: Any, native: Any = None) -> None:
        self.font = font
        self.native = native
        self.block_id: int | None = None

    def _block(self) -> Any:
        from fontlabapp.glyphs.case_coverage.views import active_model

        native = self.native
        if native is None:
            try:
                import fontlab as native
            except ImportError:
                return None
        identity = getattr(getattr(self.font, "_backend", None), "font_id", None)
        if identity is None:
            return None
        workspace = native.flWorkspace.instance()
        if workspace.activeFontPanel is not None:
            return None
        block = active_model(native, workspace)
        # Fontport font_id is the FontGate id (findPackageId compares fgId);
        # flPackage.id is a different, address-like workspace identity.
        if block is None or int(block.package.fgId) != identity:
            return None
        if self.block_id is None:
            self.block_id = int(block.id)
        if int(block.id) != self.block_id:
            return None
        self.native = native
        return block

    def read_text(self) -> str | None:
        """Read exact Unicode scalars; never infer text from rendered glyph names."""
        block = self._block()
        if block is None:
            return None
        chars = []
        for symbol in block.symbolList().symbols():
            if symbol.name or symbol.layerName:
                return None
            code = int(symbol.unicode)
            if not 0 <= code <= 0x10FFFF or 0xD800 <= code <= 0xDFFF:
                raise ValueError("The Glyph window contains an invalid Unicode scalar.")
            chars.append(chr(code))
        return "".join(chars)

    def write_text(self, text: str) -> bool:
        """Replace only this font's captured active literal-text block and verify it."""
        if not isinstance(text, str):
            raise TypeError("Glyph-window text must be a string.")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
            raise ValueError("Glyph-window text contains a surrogate.")
        # Slash names and per-symbol masters cannot be represented losslessly here.
        if "/" in text or self.read_text() is None:
            return False
        native, block = self.native, self._block()
        if block is None:
            return False
        from fontlabapp.core.native_tabs import preserve_rendered_activation

        symbols = native.fgSymbolList([native.fgSymbol(ord(char)) for char in text])
        workspace = native.flWorkspace.instance()
        with preserve_rendered_activation(workspace):
            if self._block() is None:
                return False
            native.flItems().requestContent(symbols, 0)
        if self.read_text() != text:
            raise RuntimeError("FontLab did not retain the requested Glyph-window text.")
        native.UpdateActiveCanvas()
        return True

    def subscribe(
        self, owner: Any, callback: Callable, fonts: Callable, text_callback: Callable | None = None
    ) -> None:
        """Use existing font/history hooks; poll text because typing emits no history.

        A text change calls ``text_callback`` (default: ``callback``).
        """
        from PythonQt import QtCore

        from .lifecycle import follow_changes, follow_history

        follow_changes(owner, callback, fonts)
        follow_history(owner, callback)
        timer = QtCore.QTimer(owner.widget)
        timer.setInterval(250)
        previous = [None]

        def poll(*args: Any) -> None:
            if owner.closed:
                timer.stop()
                return
            try:
                text = self.read_text()
                if text is not None and text != previous[0]:
                    (text_callback or callback)()
                    previous[0] = text
            except Exception as error:  # noqa: BLE001 - native timer boundary
                owner.diagnostic.setText(f"Glyph-window text sync: {error}")

        owner.connect(timer.timeout, poll)
        timer.start()
