# this_file: tests/test_wp08_font_audit.py
"""WP08 report routes retain the existing report owners and category policy."""

import importlib
from types import SimpleNamespace as NS

from _studio_qt import studio_qt  # noqa: F401


def test_routes_when_built_then_each_original_report_has_named_tab(monkeypatch):
    module = importlib.import_module('fontlabapp.studios.font_audit.practical')
    calls = []
    shell = NS(set_about=lambda text: None)
    monkeypatch.setattr(module, 'show_audit', lambda **kwargs: calls.append(kwargs) or shell)
    assert module.show(classify='policy', case_metadata='meta', case_preferred='pref',
                       package=lambda: None, font=lambda: None) is shell
    assert [spec.title for spec in calls[0]['task_specs']] == [
        'Case Coverage', 'Categories to XML Lib Key', 'Empty Glyphs', 'Font Overview',
        'Glyph Table CSV', 'Label Statistics', 'Smallcap Consistency', 'Unicode Coverage',
    ]
    assert calls[0]['case_metadata'] == 'meta'
    assert calls[0]['case_preferred'] == 'pref'


def test_categories_when_refreshed_then_exact_xml_and_failure_clear(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.features.categories import model
    shell = studio_qt.modules.appshell.AppShell('test', package=lambda: None)
    shell.font_audit = NS(package=lambda: NS(id=1))
    studio_qt.owned.append(shell)
    report = model.CategorySnapshot(1, (('a&b', None), ('acute', 'Mark')))
    calls = []
    monkeypatch.setattr(model, 'capture', lambda classify: calls.append(classify) or report)
    from fontlabapp.fontui import category_report
    tab = category_report(shell, 'policy')
    shell.layout.addWidget(tab.widget)
    shell.children.append(tab)
    assert tab.output.toPlainText() == model.render(report)
    assert calls == ['policy']
    def fail(classify):
        raise ValueError('changed font')
    monkeypatch.setattr(model, 'capture', fail)
    tab.refresh()
    assert tab.output.toPlainText() == ''
    assert 'changed font' in shell.status.text()


def test_categories_when_policy_missing_then_clear_refusal(studio_qt):  # noqa: F811
    shell = studio_qt.modules.appshell.AppShell('test', package=lambda: None)
    shell.font_audit = NS(package=lambda: NS(id=1))
    studio_qt.owned.append(shell)
    from fontlabapp.fontui import category_report
    tab = category_report(shell, None)
    shell.children.append(tab)
    assert tab.output.toPlainText() == ''
    assert 'GlyphData' in shell.status.text()


def test_assembly_when_source_routes_opened_then_reuses_original_tabs(studio_qt, monkeypatch):  # noqa: F811
    from test_studio_font_audit import Backends, World
    import sys
    world = World()
    monkeypatch.setitem(sys.modules, 'fontlab', world.fontlab)
    monkeypatch.setitem(sys.modules, 'FL', NS(fl=world.fl))
    module = importlib.import_module('fontlabapp.studios.font_audit.practical')
    from fontlabapp.features.categories import model
    monkeypatch.setattr(model, 'capture', lambda classify: model.CategorySnapshot(7, ()))
    shell = module.show(
        classify='policy', package=lambda: world.current, font=lambda: None,
        preview=lambda shell, state: None, read=lambda package: None,
        case_metadata='meta', case_preferred='pref', backends=lambda: Backends(world),
    )
    studio_qt.owned.append(shell)
    assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == [
        title for title, _ in module.ROUTES
    ] + ['About']
    assert len(shell.font_audit.views) == 7
    assert shell.refresh_button.isEnabled()
    assert not shell.apply_button.isVisible()


def test_captured_package_when_active_document_changes_then_refuses():
    import pytest
    module = importlib.import_module('fontlabapp.studios.font_audit.practical')
    first = NS(id=7)
    current = [first]
    bound = module.captured_package(lambda: current[0])
    assert bound() is first
    current[0] = NS(id=7)
    assert bound() is first
    for replacement in (NS(id=8), None):
        current[0] = replacement
        with pytest.raises(ValueError, match='original font'):
            bound()
    current[0] = None
    absent = module.captured_package(lambda: current[0])
    assert absent() is None
    current[0] = first
    with pytest.raises(ValueError, match='original font'):
        absent()


def test_case_callbacks_when_other_font_active_then_never_call_backend(studio_qt, monkeypatch):  # noqa: F811
    import pytest
    from unittest.mock import Mock
    from fontlabapp.studios.font_audit import practical
    from fontlabapp.studios.font_audit import tabs
    current = [NS(id=7)]
    backend = NS(case_coverage=NS(show=Mock(return_value='case')),
                 smallcaps=NS(current_report=Mock(return_value='report')),
                 reports=NS(show_report=Mock(return_value='smallcaps')))
    state = NS(package=practical.captured_package(lambda: current[0]),
               case_metadata='meta', case_preferred='pref', views=[], backends=lambda: backend,
               reload=lambda: None)
    shell = studio_qt.modules.appshell.AppShell('test', package=lambda: None)
    studio_qt.owned.append(shell)
    shell.font_audit = state
    built = []
    original = tabs.TAB_CLASSES['Case & small caps']
    def build(studio):
        tab = original(studio)
        built.append(tab)
        return tab
    monkeypatch.setitem(tabs.TAB_CLASSES, 'Case & small caps', build)
    widget = practical.report_tab(shell, 'Case & small caps')
    shell.layout.addWidget(widget)
    tab = built[0]
    assert tab.case_coverage() == 'case'
    assert tab.smallcaps() == 'smallcaps'
    backend.case_coverage.show.reset_mock()
    backend.smallcaps.current_report.reset_mock()
    current[0] = NS(id=8)
    for action in (tab.case_coverage, tab.smallcaps):
        with pytest.raises(ValueError, match='original font'):
            action()
    backend.case_coverage.show.assert_not_called()
    backend.smallcaps.current_report.assert_not_called()
