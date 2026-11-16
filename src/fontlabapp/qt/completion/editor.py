# this_file: src/fontlabapp/qt/completion/editor.py
# SPDX-License-Identifier: Apache-2.0
"""Own an injected-Qt multiline completion editor and whole vocabulary swaps.

Qt's case-insensitive proxy sorts the entire model before enabling completer
binary search; Python casefold ordering is not substituted for QString rules.
Callers connect/disconnect the exact activated(QString) overload and contain
slot errors. No native binding, host, font, preference or file is imported.
"""

from collections.abc import Callable
from typing import Any

from fontlabapp.qt.completion import events


class CompletionEditor:
    """Share mechanisms while retaining the part2 and part3 source policies."""

    def __init__(
        self,
        qt: Any,
        parent: Any,
        wire: Callable,
        unwire: Callable,
        report: Callable,
        *,
        official: bool = False,
    ) -> None:
        self.core, self.gui = qt.QtCore, qt.QtGui
        self.official, self.prefix, self._closed = official, "", False
        self._wire, self._unwire, self._report = wire, unwire, report
        self.completer = self.activation = None
        self.last_error = ""
        control, base = self, self.gui.QTextEdit

        class Editor(base):
            def keyPressEvent(self, event: Any) -> None:
                try:
                    events.key_press(control, event)
                except Exception as error:  # noqa: BLE001 - contain the owned Qt callback or teardown boundary
                    control._failed(error)

            def focusInEvent(self, event: Any) -> None:
                if control._closed:
                    return
                try:
                    if control.official and control.completer is not None:
                        control.completer.setWidget(self)
                    base.focusInEvent(self, event)
                except Exception as error:  # noqa: BLE001 - contain the owned Qt callback or teardown boundary
                    control._failed(error)

        self.widget = Editor(parent)
        self.widget.setAcceptRichText(False)

    def _failed(self, error: Exception) -> None:
        """Contain virtual-handler errors before they cross the Qt boundary."""
        if not self._closed:
            self.last_error = repr(error)
            try:
                self._report(error)
            except Exception as report_error:  # noqa: BLE001 - error reporting must not escape a virtual handler
                self.last_error += "; " + repr(report_error)

    def insert(self, word: str) -> None:
        """Insert a completion without normalizing typed case or surrounding text."""
        events.insert(self, str(word))

    def replace_words(self, words: tuple[str, ...]) -> None:
        """Replace the whole owned completer, preserving the entire draft text."""
        if self._closed:
            return
        if not isinstance(words, tuple) or any(
            not isinstance(w, str) or not w for w in words
        ):
            raise TypeError("Completion words must be a tuple of nonempty strings.")
        completer = self.gui.QCompleter(self.widget)
        try:
            source = self.gui.QStringListModel(list(words), completer)
            proxy = self.gui.QSortFilterProxyModel(completer)
            proxy.setSourceModel(source)
            proxy.setSortCaseSensitivity(self.core.Qt.CaseInsensitive)
            proxy.setSortLocaleAware(False)
            proxy.sort(0)
            completer.setModel(proxy)
            completer.setModelSorting(self.gui.QCompleter.CaseInsensitivelySortedModel)
            if self.official:
                completer.setWrapAround(False)
            self.replace_completer(completer)
        except BaseException:
            completer.deleteLater()
            raise

    def replace_completer(self, completer: Any) -> None:
        """Detach old activation/widget/popup before publishing the new owner."""
        if self._closed:
            return
        if completer is self.completer:
            return
        self.clear()
        completer.setWidget(self.widget)
        try:
            completer.setCaseSensitivity(self.core.Qt.CaseInsensitive)
            completer.setCompletionMode(self.gui.QCompleter.PopupCompletion)
            callback = self._wire(completer, self.insert)
        except BaseException:
            completer.setWidget(None)
            raise
        self.completer, self.activation = completer, callback

    def clear(self, *, destroyed: bool = False) -> None:
        """Drop exact ownership; parent destruction must not dereference children."""
        old, slot = self.completer, self.activation
        if destroyed:
            self.completer = self.activation = None
            return
        if old is None:
            return
        if slot is not None:
            self._unwire(old, slot)
            self.activation = None
        old.popup().hide()
        old.setWidget(None)
        old.deleteLater()
        self.completer = None

    def close(self, *, destroyed: bool = False) -> None:
        """Fence queued callbacks first and release caller closures even on failure."""
        if self._closed and self.completer is None:
            return
        self._closed = True
        self.clear(destroyed=destroyed)
        self._wire = self._unwire = self._report = None
