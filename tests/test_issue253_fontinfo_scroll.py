# this_file: tests/test_issue253_fontinfo_scroll.py
"""Real detached Font Info compositions, full UFO preservation and QObject lifetime."""
import importlib
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from _feature_source_qt import font_fixture, freeze, owned_application, qt_namespace
from PySide6 import QtCore, QtGui, QtTest, QtWidgets
import shiboken6
from ufoLib2 import Font

APP_ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module', autouse=True)
def real_compositions():
    global app, demo, font_info_metrics, Scope, create_dialog, default_font
    with pytest.MonkeyPatch.context() as patch, owned_application() as application:
        app = application
        for name in ('fontinfo', 'font_info_metrics', 'lifecycle'):
            patch.delitem(sys.modules, 'fontlabapp.fontui.' + name, raising=False)
        patch.setitem(sys.modules, 'PythonQt', qt_namespace())
        font_info_metrics = importlib.import_module('fontlabapp.fontui.font_info_metrics')
        from fontlabapp.core.signals.scope import Scope
        from fontlabapp.qt.widgets import create_dialog
        demo = runpy.run_path(str(APP_ROOT / 'Scripts/Font Editors/Font Info Editor Demo.py'), run_name='detached_regression_demo')
        default_font = QtGui.QFont(app.font())
        yield
        app.setFont(default_font)
        for name in ('fontinfo', 'font_info_metrics', 'lifecycle'):
            sys.modules.pop('fontlabapp.fontui.' + name, None)

def drain():
    for _ in range(3):
        app.processEvents()

def size(value):
    return [value.width(), value.height()]

def geometry(widget, root):
    pos = widget.mapTo(root, QtCore.QPoint())
    rect = QtCore.QRect(pos, widget.size())
    root_rect = root.rect() if callable(root.rect) else root.rect
    return {'rect': [rect.x(), rect.y(), rect.width(), rect.height()],
            'visible': widget.isVisible(), 'inside_root': root_rect.contains(rect),
            'size_hint': size(widget.sizeHint()), 'minimum_hint': size(widget.minimumSizeHint())}

def fixture(profile):
    ufo = Font() if profile == 'empty' else font_fixture('feature kern { pos A B -25; } kern;', 'fontinfo-audit')
    if profile != 'empty':
        info = ufo.info
        info.familyName, info.styleName = 'Owned Audit Sans', 'Regular'
        info.capHeight, info.xHeight, info.italicAngle = 700, 500, 0
        info.versionMajor, info.versionMinor = 1, 0
        for key, value in zip(font_info_metrics._FIELDS, (800, -200, 0, 810, -210, 20, 220, 900)):
            setattr(info, key, value)
    if profile == 'long-values':
        ufo.info.familyName = 'Very long detached audit family Ω ' * 8
        ufo.info.styleName = 'Very long captured info source ' * 5
        for key in ('note', 'copyright', 'trademark', 'openTypeNameLicense'):
            setattr(ufo.info, key, ('A long read-only audit paragraph Ω. ' * 10 + '\n') * 12)
        ufo.info.openTypeNameManufacturerURL = 'https://example.invalid/' + 'long/' * 60
    font = ufo if profile == 'empty' else SimpleNamespace(info=demo['SampleInfo'](ufo.info))
    return ufo, font

def launch(route, font):
    if route == 'editor-demo':
        owner = demo['Demo'](sys.modules['PythonQt'], Scope, font)
        demo['_HANDLES'].append(owner)
        owner.owned = create_dialog(None, demo['TITLE'], owner.build)
        return owner.editor, owner.owned.widget, owner
    owner = font_info_metrics.show(font)
    return owner, owner.widget, None

def retire(owner, root, wrapper):
    destroyed = []
    root.destroyed.connect(lambda *_: destroyed.append(True))
    field = owner.fields['familyName']
    buttons = [owner.apply_button, owner.revert_button]
    if hasattr(owner, 'refresh_report_button'):
        buttons.append(owner.refresh_report_button)
    clicked = QtCore.SIGNAL('clicked(bool)')
    assert all(button.receivers(clicked) >= 1 for button in buttons)
    if wrapper is not None:
        wrapper.release()
        wrapper.release()
    else:
        owner.close()
        owner.close()
    assert owner.closed and owner._close_complete and not owner.connections
    assert owner.on_apply is None
    assert all(button.receivers(clicked) == 0 for button in buttons)
    if wrapper is not None:
        assert wrapper not in demo['_HANDLES'] and not wrapper.problems
    else:
        assert owner not in font_info_metrics._HANDLES
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    drain()
    assert destroyed and not shiboken6.isValid(root) and not shiboken6.isValid(field)
    return {'owner_complete': True, 'connections': 0, 'root_destroyed': True,
            'field_destroyed': True, 'handles_released': True,
            'retained_owner_model_reference': owner.font is not None,
            'retained_invalid_field_wrappers': len(owner.fields)}

def assert_footer(owner, root, route):
    names = ['apply_button', 'revert_button', 'diagnostic']
    if route == 'metrics':
        names += ['report_view', 'refresh_report_button']
    for name in names:
        control = getattr(owner, name)
        assert geometry(control, root)['inside_root'] and control.isVisible(), name
        assert control.width() > 0 and control.height() > 0, name
    if route == 'metrics':
        assert owner.report_view.viewport().height() >= owner.report_view.fontMetrics().height()


def assert_reachable(owner, root):
    areas = root.findChildren(QtWidgets.QScrollArea)
    assert len(areas) == 1, 'All 24 fields need one real outer form scroll route'
    scroll = areas[0]
    assert scroll.widgetResizable()
    assert scroll.viewport().height() >= 90
    assert scroll.verticalScrollBar().maximum() > 0
    originals = dict(owner.fields)
    for name, field in owner.fields.items():
        assert scroll.widget().isAncestorOf(field), name
        field.setFocus()
        drain()
        scroll.ensureWidgetVisible(field, 0, 0)
        # Text editors expose cursor microfocus; operate the outer bar for the whole field.
        scroll.verticalScrollBar().setValue(field.mapTo(scroll.widget(), QtCore.QPoint()).y())
        drain()
        rect = QtCore.QRect(field.mapTo(scroll.viewport(), QtCore.QPoint()), field.size())
        assert scroll.viewport().rect.contains(rect), (name, rect, scroll.viewport().rect)
        assert field.hasFocus() and field.isVisible(), name
        assert field.font().family() == default_font.family()
        assert field.font().pointSize() == app.font().pointSize()
        assert field.accessibleName() and field.placeholderText() == 'Not set'
        assert scroll.widget().layout().labelForField(field).buddy() is field
        if name in owner.MULTILINE:
            assert field.viewport().height() >= field.fontMetrics().height()
    assert owner.fields == originals and len(originals) == 24
    assert root.findChildren(QtWidgets.QTabWidget) == []


@pytest.mark.parametrize('points', [9, 13])
@pytest.mark.parametrize('route', ['editor-demo', 'metrics'])
@pytest.mark.parametrize('profile', ['empty', 'typical', 'long-values', 'long-labels'])
@pytest.mark.parametrize('dimensions', [(760, 460), (760, 580), (1000, 700)])
def test_form_when_compact_then_all_fields_reachable_and_footer_visible(points, route, profile, dimensions):
    font = QtGui.QFont(default_font); font.setPointSize(points); app.setFont(font)
    ufo, model = fixture(profile); before = freeze(ufo)
    owner, root, wrapper = launch(route, model)
    try:
        if profile == 'long-labels':
            for label in owner.widget.findChildren(QtWidgets.QLabel):
                if label is not owner.diagnostic:
                    label.setText(label.text + ' (deliberately long detached audit caption)')
        root.resize(*dimensions); root.show(); drain()
        screenshot = os.environ.get('FONTINFO_SCREENSHOTS')
        if screenshot:
            Path(screenshot).mkdir(parents=True, exist_ok=True)
            assert root.grab().save(str(Path(screenshot) / f'{route}-{profile}-{points}pt-{dimensions[0]}x{dimensions[1]}.png'))
        assert root.size().height() == dimensions[1], (root.size(), dimensions)
        assert root.size().width() == dimensions[0]
        assert_footer(owner, root, route)
        assert_reachable(owner, root)
        field = owner.fields['familyName']
        if profile == 'empty':
            assert all(f.isReadOnly() for f in owner.fields.values())
            assert not owner.apply_button.isEnabled()
            QtTest.QTest.keyClicks(field, 'Refused typing')
            assert field.text == ''
        else:
            field.selectAll(); QtTest.QTest.keyClicks(field, 'Detached staged text')
            field.selectAll(); assert field.selectedText() == 'Detached staged text'
            if route == 'metrics':
                owner.refresh_report_button.click()
                assert field.text == 'Detached staged text'
                assert len(owner.report.rows) == 1
                assert owner.report.rows[0].values == (800, -200, 0, 810, -210, 20, 220, 900)
            assert freeze(ufo) == before
            owner.revert_button.click(); assert field.text == (ufo.info.familyName or '')
            field.setText('Retained draft'); owner._changed()
            assert field.text == 'Retained draft' and 'staged edits kept' in owner.diagnostic.text
            owner.revert_button.click()
        if profile == 'long-values':
            views = [owner.fields[name] for name in owner.MULTILINE]
            if route == 'metrics': views.append(owner.report_view)
            for view in views:
                bar = view.verticalScrollBar(); bar.setValue(bar.maximum()); drain()
                assert bar.maximum() > 0 and bar.value() == bar.maximum()
        assert_footer(owner, root, route)
        assert freeze(ufo) == before
    finally:
        retire(owner, root, wrapper)
        assert freeze(ufo) == before, 'Teardown must preserve the complete borrowed UFO'


@pytest.mark.parametrize('points', [9, 13])
@pytest.mark.parametrize('route', ['editor-demo', 'metrics'])
def test_default_opening_when_unresized_then_compact(points, route):
    font = QtGui.QFont(default_font); font.setPointSize(points); app.setFont(font)
    ufo, model = fixture('typical'); before = freeze(ufo)
    owner, root, wrapper = launch(route, model)
    try:
        root.show(); drain()
        screenshot = os.environ.get('FONTINFO_SCREENSHOTS')
        if screenshot: assert root.grab().save(str(Path(screenshot) / f'{route}-default-{points}pt.png'))
        assert root.size().height() <= 580, root.size()
        if route == 'editor-demo': assert root.size().width() == 560
        assert_footer(owner, root, route)
        assert_reachable(owner, root)
    finally:
        retire(owner, root, wrapper)
        assert freeze(ufo) == before


@pytest.mark.parametrize('route', ['editor-demo', 'metrics'])
def test_apply_when_owned_sample_then_invalid_refused_and_only_explicit_edit_written(route):
    ufo, model = fixture('typical'); before = freeze(ufo)
    owner, root, wrapper = launch(route, model)
    try:
        owner.fields['unitsPerEm'].setText('0')
        assert not owner.apply() and freeze(ufo) == before
        owner.revert_button.click(); owner.fields['familyName'].setText('Applied to detached fixture')
        owner.apply_button.click(); assert ufo.info.familyName == 'Applied to detached fixture'
        assert owner.diagnostic.text == 'Applied font information.'
        if wrapper is not None: assert 'familyName' in wrapper.status.text
        after = freeze(ufo)
        ufo.info.familyName = 'Owned Audit Sans'; assert freeze(ufo) == before
        ufo.info.familyName = 'Applied to detached fixture'; assert freeze(ufo) == after
    finally:
        retire(owner, root, wrapper)
