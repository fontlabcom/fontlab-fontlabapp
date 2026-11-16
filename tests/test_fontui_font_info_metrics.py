# this_file: tests/test_fontui_font_info_metrics.py
"""Actual editor, fake borrowed info, real Qt callback and lifetime checks."""
import importlib
import sys
from types import SimpleNamespace

import pytest
from _feature_source_qt import owned_application, qt_namespace


@pytest.fixture
def panel(monkeypatch):
    names = ('fontinfo', 'lifecycle', 'font_info_metrics')
    for name in names:
        monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.' + name, raising=False)
    with owned_application() as app:
        monkeypatch.setitem(sys.modules, 'PythonQt', qt_namespace())
        monkeypatch.delitem(sys.modules, 'fontlab', raising=False)
        module = importlib.import_module('fontlabapp.fontui.font_info_metrics')
        cls = module._panel_type()
        values = dict.fromkeys(cls.FIELD_LABELS, None)
        values.update(dict.fromkeys(module._FIELDS, None))
        values.update(familyName='Family', styleName='Regular', unitsPerEm=1000,
                      openTypeHheaAscender=0)
        info = SimpleNamespace(**values)
        writes = []
        def apply(changes, **kwargs):
            writes.append(changes)
            for key, value in changes.items():
                setattr(info, key, value)
        info.apply = apply
        owner = module.show(SimpleNamespace(info=info))
        yield module, owner, info, writes
        owner.close()
        app.processEvents()
    for name in names:
        sys.modules.pop('fontlabapp.fontui.' + name, None)


def test_report_and_apply_when_captured_then_actual_editor_and_report(panel):
    module, owner, _info, writes = panel
    assert owner.report.rows[0].values == (None, None, None, 0, None, None, None, None)
    assert 'hheaAscender: 0' in owner.report_view.toPlainText()
    owner.fields['familyName'].setText('Changed')
    owner.refresh_report_button.click()
    assert owner.fields['familyName'].text == 'Changed' and not writes
    owner.apply_button.click()
    assert writes == [{'familyName': 'Changed'}]
    assert owner.report.rows[0].document == 'Changed'
    owner.close()
    owner.close()
    assert owner._close_complete and owner not in module._HANDLES
    assert not owner.refresh_report()


def test_report_when_invalid_then_clears_and_recovers(panel):
    _, owner, info, writes = panel
    info.openTypeHheaAscender = float('nan')
    assert not owner.refresh_report() and owner.report is None
    assert 'finite' in owner.report_view.toPlainText()
    info.openTypeHheaAscender = 800
    assert owner.refresh_report()
    owner.font = None
    assert not owner.refresh_report()
    assert 'No font' in owner.report_view.toPlainText()
    assert not writes


def test_show_when_display_fails_then_closes_owner(panel, monkeypatch):
    module, owner, _, _ = panel
    import fontlabapp.fontui as ui
    monkeypatch.setattr(ui, '_construct', lambda *args: owner)
    def fail():
        raise RuntimeError('display failed')
    monkeypatch.setattr(owner.widget, 'show', fail)
    with pytest.raises(RuntimeError, match='display failed'):
        module.show(owner.font)
    assert owner._close_complete


def test_apply_when_invalid_or_unchanged_then_keeps_report(panel):
    _, owner, _, writes = panel
    original = owner.report
    assert not owner.apply()
    owner.fields['unitsPerEm'].setText('0')
    assert not owner.apply()
    assert owner.report is original and not writes


def test_constructor_when_report_widget_fails_then_cleans_partial_owner(panel, monkeypatch):
    module, owner, _, _ = panel
    cls = module._panel_type()
    original = cls.__init__
    captured = []
    def fail(self, *args):
        captured.append(self)
        original(self, *args)
        raise RuntimeError('construction failed')
    monkeypatch.setattr(cls, '__init__', fail)
    monkeypatch.setattr(module, '_panel_type', lambda: cls)
    with pytest.raises(RuntimeError, match='construction failed'):
        module.show(owner.font)
    assert captured[0]._close_complete
    assert captured[0] not in module._HANDLES


def test_parent_destruction_when_owned_then_finishes(panel):
    module, owner, _, _ = panel
    from PySide6 import QtCore, QtWidgets
    parent = QtWidgets.QWidget()
    child = module.show(owner.font, parent)
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert child.closed and child._close_complete
    assert child not in module._HANDLES


def test_change_notification_when_fields_reload_then_report_follows(panel):
    """F44-1: native Undo/Redo reaches ``_changed``; the report must follow the fields."""
    _, owner, info, _ = panel
    info.openTypeHheaAscender = 765
    owner._changed()
    info.familyName = 'Undone'
    owner._changed()
    assert owner.fields['familyName'].text == 'Undone'
    assert owner.report.rows[0].values[3] == 765, "Report must follow Undo/Redo"
    assert 'hheaAscender: 765' in owner.report_view.toPlainText()


def test_change_notification_when_own_apply_echoes_then_status_kept(panel):
    """F44-2: the notify that follows Apply must not replace its status line."""
    _, owner, _, _ = panel
    owner.fields['familyName'].setText('Changed')
    assert owner.apply()
    assert owner.diagnostic.text == 'Applied font information.'
    owner._changed()
    assert owner.diagnostic.text == 'Applied font information.'


def test_change_notification_when_values_differ_after_apply_then_hint_returns(panel):
    _, owner, info, _ = panel
    owner.fields['familyName'].setText('Changed')
    assert owner.apply()
    info.familyName = 'Undone'
    owner._changed()
    assert owner.diagnostic.text.startswith('Edits are staged until Apply')
    assert owner.fields['familyName'].text == 'Undone'


def test_change_notification_when_status_not_apply_and_values_same_then_hint_returns(panel):
    """The echo guard keeps only an Apply status, not any earlier message."""
    _, owner, _, _ = panel
    owner._say('Some other status')
    owner._changed()
    assert owner.diagnostic.text.startswith('Edits are staged until Apply')
