# this_file: tests/test_e01_table_embedding.py
"""E01's real shell embeds all four table factories and owns their cleanup."""
import importlib
import sys
from types import SimpleNamespace

import pytest
import test_filter_table_dialog as ui
from test_filter_table_layout import ROWS
from fontlabapp.qt.tables.filter.model import Table

panel = ui.panel


@pytest.mark.parametrize('selected', range(7))
@pytest.mark.parametrize('points', [9, 13])
def test_e01_when_each_profile_selected_then_tables_fit_refresh_and_close(panel, monkeypatch, selected, points):
    from PythonQt import QtGui
    before = ui.APP.font()
    font = ui.QtGui.QFont(before)
    font.setPointSize(points)
    ui.APP.setFont(font)
    modules = ('fontlabapp.fontui.lifecycle', 'fontlabapp.fontui.table',
               'fontlabapp.fontui.appshell', 'fontlabapp.fontui.core_pythonqt_labs.app')
    for name in modules:
        monkeypatch.delitem(sys.modules, name, raising=False)
    # PythonQt places item models in QtGui; the table fixture already bridges regex.
    monkeypatch.setattr(QtGui, 'QSortFilterProxyModel', ui.Proxy)
    for name in ('QStringListModel', 'QItemSelectionModel'):
        monkeypatch.setattr(QtGui, name, getattr(ui.QtCore, name), raising=False)
    if not hasattr(ui.QtCore, 'QRegExp'):
        from test_regexp_panel import core_for_panel
        regexp_ui = importlib.import_module('fontlabapp.qt.regexp.ui')
        panel_type = regexp_ui.panel_type
        # Reuse the regexp panel's scripted Qt6 calls; Qt5 keeps native QRegExp.
        monkeypatch.setattr(regexp_ui, 'panel_type', lambda core, gui: panel_type(core_for_panel(), gui))
    shell_module = importlib.import_module(modules[2])
    monkeypatch.setattr(shell_module, 'available_geometry', lambda widget: ui.QtCore.QRect(0, 0, 1920, 1440))
    app = importlib.import_module(modules[3])
    native = importlib.import_module('fontlabapp.glyphs.catalog.native')
    state = SimpleNamespace(rows=ROWS, calls=0, master='Regular')
    def capture():
        state.calls += 1
        return Table(('Glyph', 'Description', 'Modified'), state.rows)
    monkeypatch.setattr(native, 'capture', capture)
    monkeypatch.setattr(app.fontui, 'current_font', lambda: None)
    monkeypatch.setattr(app.fontui, 'app_shell', shell_module.AppShell)
    specs = app.profiles('E01')
    shell = None
    try:
        shell = app.show('E01', profile=specs[selected][0],
                         package=lambda: SimpleNamespace(id=7, master=state.master))
        ui.APP.processEvents()
        assert shell.tabs.currentIndex() == selected
        owners = [owner for owner in shell.children if isinstance(owner, app.Profile)]
        assert len(owners) == 7
        tables = [owner for owner in owners if hasattr(owner.child, 'source_view')]
        assert len(tables) == 4
        for owner in tables:
            child = owner.child
            shell.tabs.setCurrentWidget(owner.widget)
            ui.APP.processEvents()
            assert child.parent() is owner.widget and not child.isWindow()
            assert owner.widget.rect().contains(child.geometry())
            for view in (child.source_view, child.proxy_view):
                assert view.model().rowCount() == 8
                for row in range(8):
                    rectangle = view.visualRect(view.model().index(row, 0))
                    assert rectangle.top() >= 0 and rectangle.bottom() < view.viewport().height()
                for column in range(3):
                    option = ui.QtWidgets.QStyleOptionViewItem()
                    option.initFrom(view)
                    option.locale = view.locale()
                    widths = [view.itemDelegate().sizeHint(option, view.model().index(row, column)).width() for row in range(8)]
                    assert view.columnWidth(column) >= max(widths)
                assert view.horizontalScrollBar().maximum() == 0
            count = state.calls
            child.refresh_button.click()
            assert state.calls == count + 1
            state.master = 'Bold'
            with pytest.raises(ValueError, match='active font'):
                child.refresh()
            shell.refresh_button.click()
            assert 'active font' in shell.status.text()
            assert state.calls == count + 1
            state.master = 'Regular'
            before_size = shell.widget.size()
            for rows in ((), ROWS * 20, ROWS):
                state.rows = rows
                shell.refresh_button.click()
                assert child.model.rowCount() == len(rows)
                assert shell.widget.size() == before_size
        tables[0].child.close_button.click()
        ui.APP.processEvents()
        assert shell._close_complete and not shell.children
        for owner in tables:
            assert owner._close_complete
            assert owner.child._closed and owner.child._capture is None
    finally:
        if shell is not None and not shell._close_complete:
            shell.close()
        ui.QtCore.QCoreApplication.sendPostedEvents(None, ui.QtCore.QEvent.DeferredDelete)
        ui.APP.setFont(before)
        for name in modules:
            sys.modules.pop(name, None)
