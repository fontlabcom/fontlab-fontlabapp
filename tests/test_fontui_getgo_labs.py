# this_file: tests/test_fontui_getgo_labs.py
# SPDX-License-Identifier: Apache-2.0
"""GetGo task controls own their plans, report rows and detached previews."""
import importlib
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def lab(studio_qt, monkeypatch):  # noqa: F811 - imported fixture
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.getgo_labs', raising=False)
    module = importlib.import_module('fontlabapp.fontui.getgo_labs')
    calls = []
    specs = [dict(entry='batch_transform', title='Width edits', defaults={'scale': 1.1},
                  fonts=['baar'], help='Only owned copies change.', writes=True),
             dict(entry='font_audit', title='Audit', defaults={}, fonts=['baar', 'hint'],
                  help='Read a verified copy.', writes=False)]
    provider = SimpleNamespace(title='GetGo Editing', preview='tglyph', specs=lambda: specs,
                               run=lambda name, kw: calls.append((name, kw)) or {'width': 42},
                               close=lambda: calls.append('provider close'), validate=lambda entry, kwargs: None)
    shell = module.show(provider)
    studio_qt.owned.append(shell)
    return module, shell, calls, studio_qt


def test_tabs_actions_and_controls_keep_parameters(lab):
    module, shell, calls, qt = lab
    panel = shell.getgo_panels[0]
    assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == ['Width edits', 'Audit', 'About']
    assert panel.parameters() == {'scale': 1.1}
    assert not panel.ready()
    shell._run_action('apply')
    assert not calls
    panel.accepted = panel.parameters()
    shell._run_action('apply')
    assert calls == [('batch_transform', {'scale': 1.1})]
    assert panel.table.rows[0].glyph_name == 'width'
    assert panel.table.rows[0].values == (42,)
    assert not panel.ready()
    panel.inputs['scale'].setText('bad')
    shell._run_action('preview')
    assert 'Error:' in shell.status.text()


def test_read_only_tab_runs_report_without_apply(lab):
    module, shell, calls, qt = lab
    shell.tabs.setCurrentIndex(1)
    assert shell.apply_button.isHidden()
    shell._run_action('refresh')
    assert calls == [('font_audit', {})]
    shell.close()
    assert calls[-1] == 'provider close'


def test_parameter_change_invalidates_accepted_plan_and_close_retry(lab):
    module, shell, calls, qt = lab
    panel = shell.getgo_panels[0]
    panel.accepted = panel.parameters()
    panel.inputs['scale'].setText('1.3')
    assert not panel.ready()
    assert panel.parameters() == {'scale': 1.3}
    with pytest.raises(ValueError):
        module.parameters({'scale': 'nan'}, {'scale': 1.1})
    assert module.parameters({'text': '', 'destination': ''}, {'text': 'Hi', 'destination': None}) == {'text': '', 'destination': None}


@pytest.mark.parametrize('kind,names', [('tglyph', ['A']), ('tglyph', ['alef']), ('tglyph', []), ('tmetrics', ['A'])])
def test_capture_uses_read_only_preview_and_releases_font(lab, monkeypatch, kind, names):
    module, shell, calls, qt = lab
    panel = shell.getgo_panels[0]
    panel.provider.preview = kind
    font = SimpleNamespace(keys=lambda: names, close=lambda: calls.append('font close'))
    panel.provider.capture = lambda name: (font, ('Geometry snapshot only.',))
    def preview(*args, **kwargs):
        calls.append(('preview', args, kwargs))
        return qt.modules.lifecycle.Owned(panel.page)
    monkeypatch.setitem(sys.modules, 'fontlabapp.fontui.tglyph', SimpleNamespace(TGlyph=preview))
    monkeypatch.setitem(sys.modules, 'fontlabapp.fontui.tmetrics', SimpleNamespace(TMetrics=preview))
    shell._run_action('preview')
    assert panel.ready()
    assert calls[0][2]['read_only'] is True and calls[0][2]['controls'] is False
    assert panel.note.text() == 'Unchanged source fixture preview; proposed edits are not simulated. Geometry snapshot only.'
    assert panel.table.rows[3].values == ('{"scale": 1.1}',)
    view = panel.view
    shell.close()
    assert view._close_complete and 'font close' in calls


def test_preview_failure_closes_detached_font_and_does_not_accept(lab, monkeypatch):
    module, shell, calls, qt = lab
    panel = shell.getgo_panels[0]
    panel.provider.capture = lambda name: (SimpleNamespace(keys=lambda: ['A'], close=lambda: calls.append('font close')), ())
    def refuse(*args, **kwargs):
        raise RuntimeError('preview failed')
    monkeypatch.setitem(sys.modules, 'fontlabapp.fontui.tglyph', SimpleNamespace(TGlyph=refuse))
    shell._run_action('preview')
    assert 'preview failed' in shell.status.text()
    assert calls == ['font close'] and not panel.ready()


def test_writer_refresh_never_writes_and_about_switch_keeps_drafts(lab, monkeypatch):
    module, shell, calls, qt = lab
    panel = shell.getgo_panels[0]
    monkeypatch.setattr(panel, 'capture', lambda: calls.append('capture'))
    panel.refresh()
    assert calls == ['capture']
    shell.tabs.setCurrentIndex(2)
    shell.tabs.setCurrentIndex(0)
    assert panel.inputs['scale'].text() == '1.1'
    panel.provider.run = lambda *args: {'nested': {'a': [1, 2]}}
    panel.run()
    assert panel.table.rows[0].values == ('{"a": [1, 2]}',)


def test_preview_refused_close_keeps_exact_owners_for_retry(lab):
    module, shell, calls, qt = lab
    panel = shell.getgo_panels[0]
    def refuse():
        raise RuntimeError('refused')
    panel.view = SimpleNamespace(close=refuse)
    panel.font = SimpleNamespace(close=lambda: calls.append('font close'))
    with pytest.raises(RuntimeError, match='refused'):
        shell.close()
    assert panel.view is not None and panel.font is not None
    panel.view.close = lambda: None
    shell.close()
    assert calls == ['provider close', 'font close', 'provider close']


def test_show_failure_cleans_built_children(lab):
    module, shell, calls, qt = lab
    provider = SimpleNamespace(title='GetGo', preview='tglyph', specs=lambda: (_ for _ in ()).throw(ValueError('bad spec')))
    with pytest.raises(ValueError, match='bad spec'):
        module.show(provider)


def test_partial_constructor_is_owned_and_failed_cleanup_retried(lab):
    module, shell, calls, qt = lab
    class BadText:
        def __str__(self):
            raise ValueError('bad default')
    def refuse():
        raise RuntimeError('cleanup refused')
    provider = SimpleNamespace(title='GetGo', preview='tglyph', close=refuse,
                               specs=lambda: [dict(entry='x', title='Broken', defaults={'x': BadText()},
                                                   fonts=['baar'], help='Help', writes=False)])
    with pytest.raises(RuntimeError, match='cleanup refused'):
        module.show(provider)
    assert len(module._FAILED) == 1
    failed = module._FAILED[0]
    assert failed.children
    provider.close = lambda: calls.append('retried')
    replacement = module.show(shell.getgo_panels[0].provider)
    qt.owned.append(replacement)
    assert failed._close_complete and not module._FAILED
    assert 'retried' in calls


def _strict_summarize_kerning(pairs, groups, glyph_names, limit=5):
    """App-owned stand-in for the original lesson validator's `limit` contract.

    The original `summarize_kerning` accepts exactly `None` or a non-negative `int` (a `float` or `bool`
    is refused) and slices `pairs[:limit]`. Keeping this contract here lets the App suite run without a
    sibling Examples checkout; Examples tests own the real function.
    """
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError('limit must be a nonnegative integer or None')
    return {'pairs': pairs[:limit], 'limit': limit}


@pytest.mark.parametrize('text,expected', [('5', 5), ('0', 0), ('', None), ('None', None)])
def test_kerning_limit_reaches_original_validator_as_integer_or_none(lab, text, expected):
    module = lab[0]
    parameters = module.parameters({'limit': text}, {'limit': 5})
    pairs = [{'left': 'A', 'right': 'V', 'value': index} for index in range(7)]
    report = _strict_summarize_kerning(pairs, [], ['A', 'V'], **parameters)
    assert report['limit'] == expected
    assert report['pairs'] == pairs[:expected]


@pytest.mark.parametrize('text', ['-1', '5.0', 'nan'])
def test_kerning_limit_refuses_invalid_numbers_before_native_work(lab, text):
    with pytest.raises(ValueError):
        lab[0].parameters({'limit': text}, {'limit': 5})


def test_integer_control_explains_full_list_mode(lab):
    module, shell, calls, qt = lab
    provider = shell.getgo_panels[0].provider
    provider.specs = lambda: [dict(entry='kerning_classes', title='Kerning', defaults={'limit': 5},
                                   fonts=['stroke-chan'], help='Inspect typed pairs.', writes=False)]
    replacement = module.show(provider)
    qt.owned.append(replacement)
    field = replacement.getgo_panels[0].inputs['limit']
    assert field.placeholderText() == 'Blank or None: show all entries'
    field.setText('')
    replacement._run_action('refresh')
    assert calls[-1] == ('kerning_classes', {'limit': None})


def test_original_preflight_refusal_prevents_native_preview(lab):
    module, shell, calls, qt = lab
    panel = shell.getgo_panels[0]
    panel.provider.validate = lambda *args: (_ for _ in ()).throw(ValueError('original preflight refused'))
    panel.provider.capture = lambda name: calls.append('capture')
    shell._run_action('preview')
    assert not calls and not panel.ready()
    assert 'original preflight refused' in shell.status.text()


_EXAMPLES_KERNING = (
    Path(__file__).resolve().parents[2]
    / 'fontlab-python-examples/lessons/src/fontlab_python_lessons/getgo/kerning_classes.py'
)


def _real_summarize_kerning(monkeypatch):
    """Load the sibling Examples `summarize_kerning` with its native-boundary import stubbed."""
    import importlib.util
    import types

    for name in ('fontlab_python_lessons', 'fontlab_python_lessons.getgo'):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    shared = types.ModuleType('fontlab_python_lessons.getgo._shared')
    shared.owned_font = None
    monkeypatch.setitem(sys.modules, 'fontlab_python_lessons.getgo._shared', shared)
    spec = importlib.util.spec_from_file_location('_examples_kerning_classes', _EXAMPLES_KERNING)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.summarize_kerning


@pytest.mark.skipif(not _EXAMPLES_KERNING.is_file(), reason='sibling fontlab-python-examples checkout absent')
@pytest.mark.parametrize('limit', [None, 0, 1, 5, 99, -1, 2.0, 1.5, True, False, '5'])
def test_strict_summarize_kerning_when_compared_with_examples_then_limit_contract_matches(monkeypatch, limit):
    real = _real_summarize_kerning(monkeypatch)
    pairs = [{'left': 'A', 'right': 'V', 'value': index} for index in range(7)]
    try:
        expected = real(pairs, [], ['A', 'V'], limit)
    except ValueError as error:
        with pytest.raises(ValueError, match=re.escape(str(error))):
            _strict_summarize_kerning(pairs, [], ['A', 'V'], limit)
        return
    stand_in = _strict_summarize_kerning(pairs, [], ['A', 'V'], limit)
    assert stand_in['pairs'] == expected['pairs']
    assert stand_in['limit'] == expected['limit']
