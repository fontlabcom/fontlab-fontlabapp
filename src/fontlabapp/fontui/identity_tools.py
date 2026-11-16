# this_file: src/fontlabapp/fontui/identity_tools.py
# SPDX-License-Identifier: Apache-2.0
"""Embed retained task panels in AppShell with explicit preview acceptance."""
from dataclasses import dataclass
from typing import Any, Callable

from PythonQt import QtCore, QtGui

import fontlabapp.fontui as fontui
from fontlabapp.fontui.lifecycle import Owned
from fontlabapp.studios import TabSpec


@dataclass(frozen=True)
class Route:
    """A retained panel and its explicitly named task actions."""
    title: str
    build: Callable[[Any], Any]
    refresh: str | None = 'reload'
    preview: str | None = 'refresh'
    apply: str | None = None
    apply_label: str = 'Apply Changes'
    buttons: tuple[str, ...] = ()
    glyph_column: int | None = None
    glyph_table: str = 'table'
    preview_target: Callable[[Any], tuple[str, str | None]] | None = None
    preview_text: Callable[[Any], str] | None = None
    preview_signals: tuple[tuple[str, str], ...] = ()


def value(obj: Any, name: str) -> Any:
    result = getattr(obj, name)
    return result() if callable(result) else result


def fingerprint(widget: Any) -> tuple:
    """Capture editable fields without interpreting or normalising source text."""
    fields = ((QtGui.QLineEdit, 'text'), (QtGui.QPlainTextEdit, 'toPlainText'),
              (QtGui.QTextEdit, 'toPlainText'), (QtGui.QComboBox, 'currentText'),
              (QtGui.QAbstractButton, 'isChecked'), (QtGui.QSpinBox, 'value'),
              (QtGui.QDoubleSpinBox, 'value'))
    # Key by kind and position, not id(): PythonQt (and PySide) recreate the
    # wrapper of a Qt-owned child such as QTableCornerButton after it is
    # garbage-collected, so its id() changes between Preview and Apply.
    inputs = tuple((kind.__name__, index, value(child, attribute)) for kind, attribute in fields
                   for index, child in enumerate(widget.findChildren(kind))
                   if not getattr(child, "isReadOnly", lambda: False)())
    return inputs + tuple(view_state(view) for view in widget.findChildren(QtGui.QAbstractItemView))


def view_state(view: Any) -> tuple:
    """Include editable/checkable cells and selection in accepted table/tree plans."""
    model = view.model()
    if model is None:
        return ()

    def rows(parent: Any) -> tuple:
        result = []
        for row in range(model.rowCount(parent)):
            cells = [model.index(row, column, parent) for column in range(model.columnCount(parent))]
            result.append(tuple((model.data(cell, QtCore.Qt.DisplayRole),
                                 model.data(cell, QtCore.Qt.CheckStateRole),
                                 view.selectionModel().isSelected(cell)) for cell in cells))
            result.append(rows(cells[0]))
        return tuple(result)

    return rows(QtCore.QModelIndex())


class EscapeGuard(QtGui.QWidget):
    """Embedded dialogs close through their shell, including keyboard dismissal."""
    def __init__(self, panel: Any, shell: Any):
        super().__init__(panel)
        self.shell = shell
        self.hide()
        panel.installEventFilter(self)

    def eventFilter(self, watched: Any, event: Any) -> bool:
        if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            self.shell._run_action('close')
            return True
        return False


class Panel(Owned):
    """Retain the panel's own cleanup and require a preview of unchanged inputs."""
    def __init__(self, shell: Any, route: Route):
        super().__init__(shell.tabs)
        self.shell, self.route = shell, route
        self.panel = None
        try:
            self.panel = route.build(self.widget)
            widget = self.panel.widget if isinstance(self.panel, Owned) else self.panel
            widget.setParent(self.widget)
            widget.setWindowFlags(QtCore.Qt.Widget)
            widget.setMinimumSize(0, 0)
            self.layout.addWidget(widget)
            self.content = widget
            self.escape_guard = EscapeGuard(widget, shell)
            if isinstance(widget, QtGui.QDialog):
                self.connect(widget.finished, lambda *args: self.dismissed())
            names = ('close_button', 'reload_button', 'refresh_button') + route.buttons
            if route.apply is not None:
                names += ('apply_button',)
            for name in names:
                button = getattr(self.panel, name, None)
                if button is not None:
                    button.hide()
            if route.apply and route.refresh:
                self.discard_button = QtGui.QPushButton('Refresh anyway (staged edits may be discarded)', self.widget)
                self.layout.addWidget(self.discard_button)
                self.connect(self.discard_button.clicked, lambda *args: self.discard())
            self.baseline = fingerprint(widget)
            self.accepted = None
            current = shell.package()
            self.package_id = getattr(current, 'id', None)
            table = getattr(self.panel, route.glyph_table, None)
            if route.glyph_column is not None and table is not None and shell.preview is not None:
                signal = table.activated if isinstance(table, QtGui.QTreeView) else table.itemActivated
                self.connect(signal, self.activate)
                if isinstance(table, QtGui.QTreeView):
                    self.connect(table.clicked, self.activate)
                else:
                    self.connect(table.itemSelectionChanged, lambda *args: self.selection())
            for attribute, signal in route.preview_signals:
                self.connect(getattr(getattr(self.panel, attribute), signal), lambda *args: self.sync_preview())
            shell.set_actions(self, refresh=self.reload if route.refresh else None,
                              preview=self.preview if route.preview else None,
                              apply=self.apply if route.apply else None,
                              dirty=(lambda: fingerprint(widget) != self.baseline) if route.apply else None,
                              ready=self.ready, apply_label=route.apply_label)
        except BaseException:
            self.close()
            raise

    def discard(self) -> None:
        try:
            self.reload()
        except Exception as error:  # noqa: BLE001 - native button boundary
            self.shell.set_status(f'Refresh: {error}')

    def dismissed(self) -> None:
        if not self.shell.closed:
            self.shell._run_action('close')

    def selection(self) -> None:
        table = getattr(self.panel, self.route.glyph_table)
        item = table.currentIndex() if isinstance(table, QtGui.QTreeView) else table.currentItem()
        if item is not None:
            self.activate(item)

    def activate(self, item: Any) -> None:
        """Resolve the sorted row by its glyph name on the captured layer."""
        try:
            self.require_target()
            if isinstance(item, QtCore.QModelIndex):
                while item.parent().isValid():
                    item = item.parent()
                name = str(item.sibling(item.row(), self.route.glyph_column).data())
            else:
                table = getattr(self.panel, self.route.glyph_table)
                name = str(value(table.item(item.row(), self.route.glyph_column), 'text'))
            if name not in self.shell.identity_font:
                return
            if self.shell.preview_kind == 'tglyph':
                self.shell.preview.load(name, self.shell.identity_layer)
            else:
                self.shell.preview.set_text('/' + name)
        except Exception as error:  # noqa: BLE001 - native signal boundary
            self.shell.set_status(f'Preview: {error}')

    def sync_preview(self) -> None:
        """Use task-declared glyph/text bindings, never guess from unrelated controls."""
        if self.shell.preview is None or self.shell.tabs.currentWidget() is not self.widget:
            return
        try:
            self.require_target()
            if self.route.preview_target is not None:
                name, layer = self.route.preview_target(self.panel)
                if name:
                    self.shell.preview.load(name, layer or self.shell.identity_layer)
            if self.route.preview_text is not None:
                self.shell.preview.set_text(self.route.preview_text(self.panel))
            if self.route.glyph_column is not None:
                self.selection()
        except Exception as error:  # noqa: BLE001 - native signal boundary
            self.shell.set_status(f'Preview: {error}')

    def require_target(self) -> None:
        current = self.shell.package()
        if current is None or getattr(current, 'id', None) != self.package_id:
            self.accepted = None
            raise ValueError('Captured font is no longer active; reopen this studio for the new font.')

    def reload(self) -> None:
        self.require_target()
        getattr(self.panel, self.route.refresh)()
        self.baseline = fingerprint(self.content)
        self.accepted = None
        self.sync_preview()

    def preview(self) -> None:
        self.require_target()
        self.accepted = None
        getattr(self.panel, self.route.preview)()
        self.accepted = fingerprint(self.content)
        self.sync_preview()

    def ready(self) -> bool:
        current = self.shell.package()
        return (current is not None and getattr(current, 'id', None) == self.package_id
                and self.accepted is not None and self.accepted == fingerprint(self.content))

    def apply(self) -> None:
        getattr(self.panel, self.route.apply)()
        self.baseline = fingerprint(self.content)
        self.accepted = None

    def close(self) -> None:
        if self.panel is not None and not self._child_closed:
            result = self.panel.close()
            if result is False or not getattr(self.panel, '_close_complete', True):
                raise RuntimeError('Task panel refused to close; retry Close.')
            self._child_closed = True
        super().close()


def show(title: str, routes: tuple[Route, ...] | list[Route], *,
         preview: str | None = None, parent: Any = None, font: Any = None,
         package: Any = None, tab: str | None = None) -> Any:
    """Open one captured-font studio; original writers retain their own guards."""
    shell = fontui.app_shell(title, preview, parent=parent, package=package)
    try:
        captured = shell.package()
        layer = getattr(captured, 'master', None)
        shell.identity_layer = layer
        shell.identity_font = font
        if preview is not None:
            font = font if font is not None else fontui.current_font()
            shell.identity_font = font
            if font is None:
                shell.set_status('Open a font first, then reopen this tool.')
            else:
                if not isinstance(layer, str) or not layer.strip():
                    raise ValueError('The captured font has no active master; select a master and reopen this studio.')
                factory = fontui.glyph_view if preview == 'tglyph' else fontui.metrics_preview
                shell.set_preview(factory(font, parent=shell.widget, layer=layer,
                                          controls=False, read_only=True, hint_check=shell.hint_check))
        shell.route_panels = []
        for route in routes:
            panel = shell.add_tab(TabSpec(route.title, lambda owner, item=route: Panel(owner, item)))
            shell.route_panels.append(panel)
        shell.set_about(title + '\nTask controls preserve the original FontLab sample operations.\n'
                        'Preview Changes accepts the current inputs; edits require a new preview.\n'
                        'Source: https://github.com/fontlabcom/fontlab-fontlabapp\n'
                        'Credits and original licences: package NOTICE and each task module.')
        if tab is not None:
            names = [route.title for route in routes]
            if tab not in names:
                raise ValueError(f'Unknown task: {tab}')
            shell.tabs.setCurrentIndex(names.index(tab))
        def sync_active(*args: Any) -> None:
            for panel in shell.route_panels:
                if panel.widget is shell.tabs.currentWidget():
                    panel.sync_preview()
                    break
        shell.connect(shell.tabs.currentChanged, sync_active)
        sync_active()
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell
