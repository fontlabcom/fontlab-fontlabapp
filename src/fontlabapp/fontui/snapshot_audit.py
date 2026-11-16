# this_file: src/fontlabapp/fontui/snapshot_audit.py
# SPDX-License-Identifier: Apache-2.0
"""Shared shell windows of read-only report tabs over the existing snapshot owners.

What: each route reuses an existing ``(capture, render, status)`` triple (the one
its own dialog already uses) in one tab of the shared ``AppShell``. Refresh
replaces the whole report atomically; a failed capture clears the text and
shows the reason in the shell status. Reports never write fonts or files.
Close: a completed shell close releases the module handle.
"""

from collections.abc import Callable
from threading import current_thread, main_thread
from typing import Any

from PythonQt import QtGui

from .appshell import AppShell
from .lifecycle import Owned

_HANDLES: list[Any] = []


class SnapshotAuditTab(Owned):
    """One report tab: selectable read-only text and an atomic Refresh."""

    def __init__(self, shell: Any, title: str, description: str, capture: Callable[[], Any],
                 render: Callable[[Any], str], status: Callable[[Any], str]) -> None:
        super().__init__(shell.widget)
        self.shell, self.title = shell, title
        self._capture, self._render, self._status = capture, render, status
        self.report = None
        self.description = QtGui.QLabel(description)
        self.description.setWordWrap(True)
        self.output = QtGui.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.layout.addWidget(self.description)
        self.layout.addWidget(self.output, 1)
        shell.set_actions(self, refresh=self.refresh)

    def refresh(self) -> None:
        """Replace the whole snapshot, or clear it and show the read failure."""
        self.report = None
        try:
            self.output.clear()
            report = self._capture()
            text, status = self._render(report), self._status(report)
        except Exception as error:  # noqa: BLE001 - native capture failures are shown, not raised
            self.shell.set_status(str(error))
            return
        self.output.setPlainText(text)
        self.report = report
        self.shell.set_status(status)


class _Spec:
    def __init__(self, title: str, *parts: Any, tab_type: type = SnapshotAuditTab) -> None:
        self.title, self.parts, self.tab_type = title, parts, tab_type

    def build(self, shell: Any) -> Any:
        tab = self.tab_type(shell, self.title, *self.parts)
        shell.snapshot_tabs = [*getattr(shell, "snapshot_tabs", ()), tab]
        return tab


class SnapshotShell(AppShell):
    """The shell; a completed close releases the module handle."""

    def close(self) -> None:
        super().close()
        if self in _HANDLES:
            _HANDLES.remove(self)


def show_snapshots(title: str, routes: tuple, about: str, *, parent: Any = None,
                   only: str | None = None, tab_type: type = SnapshotAuditTab) -> Any:
    """Open one shell with a tab per route ``(title, description, capture, render, status)``.

    ``only`` selects a single route by title; ``tab_type`` replaces the tab class. Native captures run on the main thread.
    """
    if current_thread() is not main_thread():
        raise RuntimeError("Open report windows on the main UI thread.")
    chosen = [r for r in routes if only is None or r[0] == only]
    if not chosen:
        raise ValueError(f"Unknown report: {only}")
    shell = SnapshotShell(title, None, parent=parent)
    _HANDLES.append(shell)
    try:
        for route in chosen:
            shell.add_tab(_Spec(*route, tab_type=tab_type))
        shell.set_about(about)
        for tab in shell.snapshot_tabs:
            tab.refresh()
        shell.show()
    except BaseException as error:
        try:
            shell.close()
        except Exception as cleanup:  # noqa: BLE001 - retain the failed owner visibly
            error.add_note(f"{title} cleanup incomplete; owner retained: {cleanup}")
        raise
    return shell
