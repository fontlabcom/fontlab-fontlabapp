# this_file: tests/test_issue253_reporters_inspectors_layout.py
"""Real Qt geometry and owned UFO rendering; no FontLab or preference access."""
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from test_filter_table_dialog import APP, QtCore, QtGui, QtWidgets
from test_fontui_glyph_metrics import owned_font
from test_fontui_node_counts_masters import model
from fontlabapp.qt.properties import value

MODULES = tuple('fontlabapp.fontui.' + name for name in (
    'lifecycle', 'native', 'preview', 'glyph_metrics', 'node_counts_masters',
    'sequence', 'sequence_canvas', 'anchor_components', 'unicode_order',
))


@pytest.fixture(params=[(9, 'method'), (13, 'method'), (9, 'property'), (13, 'property')],
                ids=['9pt-method', '13pt-method', '9pt-property', '13pt-property'])
def real_qt(monkeypatch, request):
    before = APP.font()
    font = QtGui.QFont(before)
    points, shape = request.param
    font.setPointSize(points)
    APP.setFont(font)
    gui = NS(**{name: getattr(QtGui, name) for name in dir(QtGui) if name.startswith('Q')})
    gui.__dict__.update({name: getattr(QtWidgets, name) for name in dir(QtWidgets) if name.startswith('Q')})

    class Widget(QtWidgets.QWidget):
        # PythonQt exposes these as properties; all drawing is the real Qt backend.
        rect = property(QtWidgets.QWidget.rect)
        width = property(QtWidgets.QWidget.width)
        height = property(QtWidgets.QWidget.height)

    gui.QWidget = Widget
    if shape == 'property':
        class Checkbox(QtWidgets.QCheckBox):
            def __getattribute__(self, name):
                # Keep SIP's C++ virtual method intact; only Python reads are properties.
                if name == "sizeHint":
                    return QtWidgets.QCheckBox.sizeHint(self)
                return super().__getattribute__(name)
        gui.QCheckBox = Checkbox
    qt = NS(QtGui=gui, QtCore=QtCore, owners=[], shape=shape)
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    for name in MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield qt, points
    for owner, dialog in reversed(qt.owners):
        owner.release() if hasattr(owner, "release") else owner.close()
        dialog.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    for name in MODULES:
        sys.modules.pop(name, None)
    APP.setFont(before)


def snapshot(widget, name, points):
    target = os.environ.get('FONTLABAPP_LAYOUT_CAPTURE')
    if target:
        path = Path(target)
        path.mkdir(parents=True, exist_ok=True)
        assert widget.grab().save(str(path / f'{name}-{points}pt.png'))


@pytest.mark.parametrize(
    "failure", [None, "screen", "resize", "qt5", "none"],
    ids=["fit", "screen-fault", "resize-fault", "qt5-desktop", "qt6-no-screen"],
)
def test_reporters_when_small_display_then_labels_fit_scroll_and_states_survive(real_qt, monkeypatch, failure):
    from fontlabapp.plugins import reporters_panel, registry
    qt, points = real_qt
    classes = registry.discover()
    classes = {name: cls for name, cls in classes.items() if cls.kind == 'reporter'}
    enabled, listeners, errors = {'node_count'}, [], []
    def toggle(name):
        enabled.symmetric_difference_update({name})
        for callback in tuple(listeners):
            callback()
    state = NS(available=lambda kind: classes, enabled=lambda: tuple(enabled),
               toggle=toggle, listeners=listeners)
    class Dialog(QtWidgets.QDialog):
        failed = False
        def screen(self):
            if failure == 'qt5':
                # FontLab 9 PythonQt: "QDockWidget has no attribute named 'screen'".
                raise AttributeError("QDialog has no attribute named 'screen'")
            if failure == 'screen' and not self.failed:
                self.failed = True
                raise RuntimeError('screen unavailable')
            if failure == 'none':
                return None  # Qt 6 before the window is placed on a screen.
            return super().screen()
        def resize(self, *args):
            if failure == 'resize' and not self.failed:
                self.failed = True
                raise RuntimeError('resize unavailable')
            return super().resize(*args)
    dialog = Dialog()
    def create(parent, title, build, area):
        build(dialog)
        dialog.show()
        return NS(widget=dialog, close=dialog.close)
    monkeypatch.setattr(reporters_panel, 'import_module', lambda name: NS(create_panel=create))
    services = NS(qt=qt, sink=lambda *args: errors.append(args),
                  menus=NS(main_window=lambda: None))
    asked = []
    if failure == 'qt5':
        def geometry(widget):
            asked.append(widget)
            return QtCore.QRect(0, 0, 1600, 900)  # wide enough for three columns
        qt.QtGui.QApplication = NS(desktop=lambda: NS(availableGeometry=geometry))
    owner = reporters_panel.ReportersPanel(services, state)
    owner.show()
    qt.owners.append((owner, dialog))
    APP.processEvents()
    if failure == 'qt5':
        assert asked == [dialog], "Qt 5 desktop geometry must be asked for the panel's own screen"
    if failure in (None, 'qt5', 'none'):
        # The fit sizes cells exactly as the reflow does and widens up to three columns.
        cell = max(value(value(check, "sizeHint"), "width") for check in owner.checks.values()) + 12
        screen = 1600 if failure == 'qt5' else APP.primaryScreen().availableGeometry().width()
        limit = int(screen * 0.85)
        columns = len({check.x() for check in owner.checks.values()})
        assert dialog.width() <= limit
        assert owner.scroll.viewport().width() >= columns * cell
        assert columns == 3 or dialog.width() + cell > limit, (columns, cell, dialog.width(), limit)
        assert failure != 'qt5' or columns == 3
        assert columns >= 2 or 2 * cell > limit
    snapshot(dialog, f'reporters-{qt.shape}-{failure or "fit"}-initial', points)
    assert len(owner.checks) == 39
    margins = dialog.layout().contentsMargins()
    assert owner.scroll.maximumHeight() <= 480
    assert dialog.height() <= 480 + margins.top() + margins.bottom()
    original = dict(owner.checks)
    assert all(not a.geometry().intersects(b.geometry())
               for index, a in enumerate(owner.checks.values())
               for b in list(owner.checks.values())[index + 1:])
    for width in (760, 420, 1100, 760):
        dialog.resize(width, 480)
        APP.processEvents()
        for checkbox in owner.checks.values():
            assert checkbox.width() >= value(value(checkbox, "sizeHint"), "width"), checkbox.text()
            assert checkbox.font().pointSize() == points
        assert owner.checks == original
        assert owner.checks['node_count'].isChecked()
    last = list(owner.checks.values())[-1]
    owner.scroll.ensureWidgetVisible(last)
    APP.processEvents()
    assert owner.scroll.viewport().rect().intersects(QtCore.QRect(last.mapTo(owner.scroll.viewport(), QtCore.QPoint()), last.size()))
    assert len({check.x() for check in owner.checks.values()}) >= 2
    snapshot(dialog, f'reporters-{qt.shape}-{failure or "fit"}', points)
    owner.checks['node_indexes'].click()
    assert 'node_indexes' in enabled
    assert len(errors) == (0 if failure in (None, 'qt5', 'none') else 1)
    assert owner.sync in listeners
    owner.show()
    owner.sync()
    assert owner.checks['node_indexes'].isChecked()
    assert owner.close()
    assert not listeners and not owner.ui
    dialog.deleteLater()


@pytest.mark.parametrize('name', ['glyph_metrics', 'node_counts_masters'])
def test_inspector_when_small_display_then_real_preview_right_and_details_left(real_qt, name):
    qt, points = real_qt
    module = importlib.import_module('fontlabapp.fontui.' + name)
    font = owned_font() if name == 'glyph_metrics' else model()[0]
    owner = module.MetricsInspector(qt, font) if name == 'glyph_metrics' else module.NodeCounts(qt, font)
    dialog = QtWidgets.QDialog()
    owner.build(dialog)
    qt.owners.append((owner, dialog))
    browser = owner.browser
    browser.glyph_list.item(0).setSelected(True)
    dialog.resize(760, 580)
    dialog.show()
    APP.processEvents()
    APP.processEvents()
    APP.processEvents()
    snapshot(dialog, name + '-' + qt.shape + '-initial', points)
    preview = browser.preview
    canvas = preview.canvas
    assert canvas.mapTo(dialog, QtCore.QPoint()).x() >= browser.glyph_list.mapTo(dialog, QtCore.QPoint(browser.glyph_list.width(), 0)).x()
    assert canvas.height >= 200
    assert canvas.width >= dialog.width() * 0.4
    assert dialog.width() <= 800 and dialog.height() <= 600, dialog.size()
    assert owner.table.topLevelItemCount() == (5 if name == 'glyph_metrics' else 2)
    assert preview.data is not None
    for widget in [browser.filter_control, browser.mode_control, browser.size_control,
                   *preview.zoom_buttons.values(), *preview.option_controls.values()]:
        rect = QtCore.QRect(widget.mapTo(dialog, QtCore.QPoint()), widget.size())
        assert widget.isVisible() and widget.height() >= widget.minimumSizeHint().height(), (widget, rect, widget.minimumSizeHint())
        assert dialog.rect().contains(rect), (widget, rect, dialog.rect())
        assert widget.font().pointSize() == points
    for column in range(owner.table.columnCount()):
        assert owner.table.columnWidth(column) >= owner.table.fontMetrics().horizontalAdvance(owner.table.headerItem().text(column))
    assert owner.table.horizontalScrollBar().maximum() == 0
    assert owner.comparison.text().count('\n') == 0
    assert owner.comparison.toolTip()
    snapshot(dialog, name + '-' + qt.shape, points)
    size = dialog.size()
    owner.refresh()
    APP.processEvents()
    assert dialog.size() == size
    assert owner.release()
    dialog.deleteLater()


@pytest.mark.parametrize('name', ['anchor_components', 'unicode_order'])
def test_font_ui_lab_when_reports_beside_preview_then_controls_and_records_survive(
    real_qt, monkeypatch, name,
):
    from copy import deepcopy
    from _feature_source_qt import qt_namespace
    from ufoLib2.objects import Anchor, Component
    import shiboken6

    fixture, points = real_qt
    qt = qt_namespace()
    qt.QtGui.QWidget.height = property(QtWidgets.QWidget.height)
    if fixture.shape == 'property':
        class Checkbox(qt.QtGui.QCheckBox):
            def __getattribute__(self, key):
                if key == "sizeHint":
                    return QtWidgets.QCheckBox.sizeHint(self)
                return super().__getattribute__(key)
        qt.QtGui.QCheckBox = Checkbox
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    module = importlib.import_module('fontlabapp.fontui.' + name)
    font = owned_font()
    font['A'].anchors = [Anchor(100, 700, 'top'), Anchor(200, 700, 'top'), Anchor(0, -20, None)]
    transform = (1.1, 0.125, -0.1, 1, 30.5, -10.25)
    font['V'].components = [Component('A', transform)]
    font['A'].unicodes = [65, 0x1F600]
    before = deepcopy(font)
    cls = module.AnchorComponentInspector if name == 'anchor_components' else module.UnicodeOrderExplorer
    owner, dialog = cls(qt, font), QtWidgets.QDialog()
    owner.build(dialog)
    fixture.owners.append((owner, dialog))
    browser = owner.browser
    browser.glyph_list.item(0).setSelected(True)
    dialog.resize(760, 580)
    dialog.show()
    for _ in range(3):
        APP.processEvents()
    snapshot(dialog, name + '-' + fixture.shape + '-initial', points)
    tables = ([owner.anchor_table, owner.component_table] if name == 'anchor_components'
              else [owner.metadata_table])
    canvas = browser.preview.canvas
    assert dialog.width() <= 800 and dialog.height() <= 600, dialog.size()
    canvas_x = canvas.mapTo(dialog, QtCore.QPoint()).x()
    for table in tables:
        right = table.mapTo(dialog, QtCore.QPoint(table.width(), 0)).x()
        assert right <= canvas_x, 'Reports must be beside the preview'
    assert canvas.height >= 220 and canvas.width >= dialog.width() * 0.4
    assert browser.glyph_list.height() >= browser.glyph_list.sizeHintForRow(0)
    assert browser.preview.data is not None
    assert browser.preview.widget.findChildren(QtWidgets.QScrollArea) == []
    controls = [browser.filter_control, browser.mode_control, browser.size_control,
                browser.preview.zoom_control, *browser.preview.zoom_buttons.values(), *browser.preview.option_controls.values()]
    browser.mode_control.setCurrentIndex(1)
    browser.mode_control.setCurrentIndex(0)
    browser.size_control.setValue(120)
    browser.filter_control.setText('A')
    assert browser.glyph_list.count() == 1
    browser.filter_control.setText('')
    assert browser.glyph_list.count() == 2
    for text in ('+', '−', 'Fit'):
        browser.preview.zoom_buttons[text].click()
    assert browser.preview.zoom == 1.0
    if name == 'anchor_components':
        assert owner.anchor_rows == (('top', 100, 700), ('top', 200, 700), (None, 0, -20))
        assert owner.anchor_table.topLevelItem(2).text(0) == '—'
        assert owner.component_table.topLevelItemCount() == 0
        browser.glyph_list.item(1).setSelected(True)
        assert owner.component_rows == (('A', transform),)
        assert owner.component_table.topLevelItem(0).text(1) == str(transform)
        for checkbox in browser.preview.option_controls.values():
            initial = checkbox.isChecked()
            checkbox.click()
            assert checkbox.isChecked() is not initial
            checkbox.click()
    else:
        seq = owner.sequence
        controls += [seq.text_control, seq.mode_control, seq.direction_control,
                     seq.size_control, seq.kerning_control, seq.wrap_control]
        assert seq.scroll.frameShape() == QtWidgets.QFrame.NoFrame
        seq.text_control.setText('/A /V /A')
        seq.select_key(QtCore.Qt.Key_End)
        assert owner.occurrence_index == 2 and 'U+1F600' in str(owner.selected_rows)
        assert owner.metadata_table.topLevelItemCount() == 4
        assert 'U+1F600' in owner.metadata_table.topLevelItem(3).text(1)
        for control, change in [(seq.direction_control, lambda: seq.direction_control.setCurrentIndex(1)),
                                (seq.size_control, lambda: seq.size_control.setValue(96)),
                                (seq.kerning_control, seq.kerning_control.click),
                                (seq.wrap_control, seq.wrap_control.click)]:
            change()
            assert owner.occurrence_index == 2 and browser.preview.name == 'A'
        seq.mode_control.setCurrentIndex(0)
        seq.text_control.setText('A😀A')
        assert [g.name for g in seq.run.glyphs] == ['A', 'A', 'A']
        seq.mode_control.setCurrentIndex(1)
        seq.text_control.setText('/A /V /A')
        seq.select_key(QtCore.Qt.Key_End)
    for width, height in [(700, 580), (1000, 700), (760, 580)]:
        dialog.resize(width, height)
        owner.refresh()
        for _ in range(3):
            APP.processEvents()
        for widget in controls:
            rect = QtCore.QRect(widget.mapTo(dialog, QtCore.QPoint()), widget.size())
            assert widget.isVisible() and dialog.rect().contains(rect), (widget, rect)
            assert widget.height() >= widget.minimumSizeHint().height()
            assert widget.font().pointSize() == points
        for table in tables:
            # Ordinary scrolling must expose full values in the narrower selection pane.
            for column in range(table.columnCount()):
                table.resizeColumnToContents(column)
            if table.topLevelItemCount():
                last = table.topLevelItem(table.topLevelItemCount() - 1)
                table.scrollToItem(last, QtWidgets.QAbstractItemView.PositionAtBottom)
                table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
                assert table.visualItemRect(last).intersects(table.viewport().rect())
                assert table.header().sectionViewportPosition(table.columnCount() - 1) < table.viewport().width()
        assert browser.preview.data is not None
        if name == 'unicode_order':
            assert owner.occurrence_index == 2 and 'U+1F600' in str(owner.selected_rows)
    snapshot(dialog, name + '-' + fixture.shape + '-resized', points)
    assert font == before
    assert owner.release(), owner.problems
    assert browser._close_complete and browser.preview._close_complete
    dialog.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not shiboken6.isValid(dialog)
    fixture.owners.remove((owner, dialog))


@pytest.mark.parametrize("mode", ["grid", "list"])
@pytest.mark.parametrize("where", ["middle", "end"])
def test_browser_visible_rows_when_real_list_scrolled_then_cover_viewport(monkeypatch, mode, where):
    """Real offscreen QListWidget geometry, not stubbed ``indexAt``: 3055 rows, gaps in grid mode."""
    monkeypatch.setitem(sys.modules, 'PythonQt', NS(QtGui=QtWidgets, QtCore=QtCore))
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.native', raising=False)
    native = importlib.import_module('fontlabapp.fontui.native')
    view = QtWidgets.QListWidget()
    view.setUniformItemSizes(True)
    if mode == "grid":
        view.setViewMode(QtWidgets.QListView.IconMode)
        view.setResizeMode(QtWidgets.QListView.Adjust)
        view.setIconSize(QtCore.QSize(72, 72))
        view.setGridSize(QtCore.QSize(96, 96))
    else:
        view.setGridSize(QtCore.QSize(96, 30))
    names = tuple(f"g{index:04d}" for index in range(3055))
    view.addItems(list(names))
    view.resize(500, 400)
    view.show()
    APP.processEvents()
    bar = view.verticalScrollBar()
    bar.setValue(bar.maximum() // 2 if where == "middle" else bar.maximum())
    APP.processEvents()

    owner = NS(state=NS(names=names, mode=mode, cell_size=96), glyph_list=NS(
        viewport=view.viewport, count=view.count, item=view.item, visualItemRect=view.visualItemRect,
        currentRow=view.currentRow, verticalScrollBar=view.verticalScrollBar))
    owner._blind_rows = lambda *args: pytest.fail(f"geometry failed: {args}")
    rows = native.Browser._visible_rows(owner)
    shown = {index for index in range(view.count())
             if view.visualItemRect(view.item(index)).intersects(view.viewport().rect())}
    try:
        assert shown and shown <= set(rows), sorted(shown - set(rows))[:5]
        assert len(rows) <= len(shown) + 2 * native.ICON_MARGIN + 1
    finally:
        view.close()
        view.deleteLater()
        sys.modules.pop('fontlabapp.fontui.native', None)
