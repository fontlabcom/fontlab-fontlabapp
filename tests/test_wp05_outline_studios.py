# this_file: tests/test_wp05_outline_studios.py
"""Original-panel embedding retains explicit auxiliary layers and close ownership."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401
from _contour_fakes import Package, NShape, square


@pytest.fixture
def composition(studio_qt, monkeypatch):  # noqa: F811
    from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QDoubleSpinBox, QVBoxLayout, QWidget
    for key in ('fontlabapp.fontui.outline_studios', 'fontlabapp.fontui.raise_ascender'):
        monkeypatch.delitem(sys.modules, key, raising=False)
    module = importlib.import_module('fontlabapp.fontui.outline_studios')
    pkg = Package()
    pkg.add('A', lambda log: [NShape([square(log)], log=log)])
    pkg.add('B', lambda log: [NShape([square(log)], log=log)])
    current = [pkg]
    calls = []

    class Panel(QDialog):
        def __init__(self, parent):
            super().__init__(parent)
            self.glyphs = [pkg.findName('B'), pkg.findName('A')]
            self.masters = list(pkg.masters)
            self.apply_button = QPushButton('Legacy apply', self)
            self.close_button = QPushButton('Close', self)
            self.reload_button = QPushButton('Reload', self)
            self.status = QLabel('ready', self)
            self.spin = QDoubleSpinBox(self)
            self.spin.setValue(10)
            self.table = QTableWidget(0, 2, self)
            self.layout_box = QVBoxLayout(self)
            self.layout_box.addWidget(self.table)
            self.fail_close = False
            self.refresh()
        def live_glyphs(self):
            return current[0], self.glyphs
        def chosen_masters(self):
            return ['Regular']
        def options(self):
            return {'all_masters': tuple(self.masters)}
        def fill(self, plan):
            self.table.setRowCount(len(self.glyphs))
            for i, glyph in enumerate(self.glyphs):
                self.table.setItem(i, 0, QTableWidgetItem(glyph.name + ' · Regular'))
                self.table.setItem(i, 1, QTableWidgetItem('10'))
        def refresh(self):
            self.fill(None)
            self.apply_button.setEnabled(True)
        def reload(self):
            calls.append('reload')
            self.refresh()
        def apply(self):
            calls.append('apply')
            self.status.setText('applied')
        def close(self):
            if self.fail_close:
                return False
            calls.append('close')
            return super().close()
    class Preview(QWidget):
        def load(self, *args):
            calls.append(('load', *args))
        def refresh(self):
            calls.append('preview refresh')
    preview = Preview()
    mappings = {label: Panel for specs in module.PANELS.values() for label, _, _ in specs}
    shell = module.fontui.outline_studio('Align and Nudge', package=lambda: current[0], font=lambda: object(),
                        preview=lambda *a: preview, panels=mappings)
    studio_qt.owned.append(shell)
    task = next(child for child in shell.children if isinstance(child, module.OutlineTask))
    shell.tabs.setCurrentWidget(task.widget)
    yield NS(module=module, pkg=pkg, current=current, calls=calls, shell=shell,
             task=task, mappings=mappings, preview=preview, qt=studio_qt)


def test_native_task_when_inputs_target_or_font_change_then_refuse(composition):
    c = composition
    with pytest.raises(ValueError, match='Preview'):
        c.task.apply()
    c.shell.preview_button.click()
    assert c.task.ready()
    c.task.panel.spin.setValue(20)
    c.shell.apply_button.click()
    assert 'apply' not in c.calls
    c.shell.preview_button.click()
    c.pkg.layer('A', 'Regular').shapes[0].contours[0].nodes()[0].nodeState = 3
    assert not c.task.ready()
    c.shell.preview_button.click()
    c.shell.apply_button.click()
    assert c.calls.count('apply') == 1
    assert not c.task.ready()
    c.current[0] = Package()
    c.shell.preview_button.click()
    assert 'captured font' in c.shell.status.text() or 'Open a font' in c.shell.status.text()


def test_native_task_when_rows_sort_then_activation_keeps_captured_layer(composition):
    c = composition
    c.shell.preview_button.click()
    c.task.panel.table.sortItems(0, c.qt.QtCore.Qt.AscendingOrder)
    c.task.panel.table.selectRow(0)
    assert ('load', 'A', 'Regular') in c.calls
    c.task.panel.table.clearSelection()
    c.task.row_chosen()
    c.task.studio.preview = None
    c.task.row_chosen()


def test_native_task_when_discard_then_refresh_and_inline_apply_safe(composition):
    c = composition
    c.shell.preview_button.click()
    c.shell.refresh_button.click()
    assert 'discard staged' in c.shell.status.text()
    c.task.discard()
    c.shell.refresh_button.click()
    assert 'reload' in c.calls
    c.task.panel.apply()
    assert 'apply' not in c.calls
    assert c.task.panel.apply_button.isHidden()


def test_native_task_when_close_refused_then_owner_retained_for_retry(composition):
    c = composition
    c.task.panel.fail_close = True
    with pytest.raises(RuntimeError, match='refused Close'):
        c.task.close()
    assert not c.task._close_complete
    c.task.panel.fail_close = False
    c.task.close()
    assert c.task._close_complete
    c.task.close()


def test_native_composition_when_transform_then_all_seven_exact_tasks(composition):
    c = composition
    shell = c.module.show('Transform Studio', package=lambda: c.pkg, font=lambda: object(),
        preview=lambda *a: None, panels=c.mappings)
    c.qt.owned.append(shell)
    assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == [
        'Transform', 'Slant', 'Smart Slant', 'Rotate Selection', 'Reflect Horizontally',
        'Reflect Vertically', 'Raise Ascender', 'About']


def test_native_composition_when_constructor_fails_then_shell_closed(composition, monkeypatch):
    c = composition
    original = c.module.fontui.app_shell
    made = []
    def shell(*args, **kwargs):
        result = original(*args, **kwargs)
        made.append(result)
        return result
    monkeypatch.setattr(c.module.fontui, 'app_shell', shell)
    with pytest.raises(KeyError):
        c.module.show('Align and Nudge', package=lambda: c.pkg, font=lambda: object(),
                      preview=lambda *a: None, panels={})
    assert made[0]._close_complete


def test_native_preview_when_view_load_fails_then_plan_not_accepted(composition):
    c = composition
    def fail(*args):
        raise RuntimeError('paint failed')
    c.preview.load = fail
    c.shell.preview_button.click()
    assert not c.task.ready()
    assert 'paint failed' in c.shell.status.text()


def test_native_preview_when_panel_refuses_or_contains_error_then_not_accepted(composition):
    c = composition
    c.task.panel.refresh = lambda: c.task.panel.apply_button.setEnabled(False)
    c.shell.preview_button.click()
    assert not c.task.ready()
    def fail():
        c.task.panel.slot_error = 'native planner refused'
    c.task.panel.refresh = fail
    c.shell.preview_button.click()
    assert not c.task.ready()
    assert 'native planner refused' in c.shell.status.text()
