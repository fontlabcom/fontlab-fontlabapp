# this_file: src/fontlabapp/glyphs/common/mime.py
# SPDX-License-Identifier: Apache-2.0
"""Exact report payloads through the existing Qt-owned native MIME factory.

Reuse qt_literal_text's measured NUL decoding route. A normal void sink return
transfers ownership; an exceptional/unknown handoff retains the original object
until the caller proves ownership explicitly. No clipboard access occurs here.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from fontlabapp.qt.literal_text import read_text, set_mime_text
from fontlabapp.qt.properties import value


@dataclass
class LiteralCopy:
    """One report editor's literal MIME stage, never an OS clipboard snapshot."""

    qt: Any
    editor: Any
    sink: Callable
    mime: Any = None
    unknown: bool = False
    delete_scheduled: bool = False
    last_transfer: bool = False

    def send(self, text: str, check: Callable) -> None:
        """Stage/read back exact native MIME text, then transfer on explicit action.

        The factory returns Qt-owned MIME data, avoiding PythonQt's Python-owned
        virtual-return lifetime hazard. Flush its lazy text before clearing it.
        A failed call leaves a handle for dispose/proven ownership resolution.
        """
        self.last_transfer = False
        check()
        if self.mime is not None:
            raise RuntimeError(
                "Previous literal MIME ownership/cleanup remains unresolved."
            )
        if self.qt is None:
            raise RuntimeError("Literal copy requires the FontLab Qt binding.")
        self.last_transfer = self.delete_scheduled = False
        self.mime = self.qt.QtGui.QPlainTextEdit.createMimeDataFromSelection(
            self.editor
        )
        check()
        value(self.mime, "text")
        self.mime.clear()
        set_mime_text(self.qt, self.mime, text)
        check()
        if read_text(self.qt, value(self.mime, "text")) != text:
            raise ValueError(
                "Qt MIME did not retain the exact source text; copy refused."
            )
        check()
        self.unknown = True
        if self.sink(self.mime) is not None:
            raise RuntimeError("Copy sink did not confirm the void ownership transfer.")
        self.mime, self.unknown, self.last_transfer = None, False, True
        check()

    def dispose(self, check: Callable) -> None:
        """Retire only proven owned data; preserve deletion stages across overruns."""
        check()
        if self.mime is None:
            return
        if self.unknown:
            raise RuntimeError(
                "Literal MIME handoff ownership is unknown; explicitly resolve it before cleanup."
            )
        if not self.delete_scheduled:
            self.mime.deleteLater()
            self.delete_scheduled = True
            check()
        self.mime = None

    def resolve(self, *, transferred: bool, check: Callable) -> None:
        """Resolve an exceptional handoff only after the caller proves its owner.

        True means the sink demonstrably owns this exact object; False means
        the report still owns it. Existing panel failure receipts stay retained
        until ordinary explicit recovery finishes. This method cannot guess.
        """
        check()
        if not self.unknown or type(transferred) is not bool:
            raise ValueError("Resolve only an unknown handoff with proven ownership.")
        self.unknown = False
        if transferred:
            self.mime, self.last_transfer = None, True
        else:
            self.dispose(check)
        check()
