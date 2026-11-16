# this_file: tests/test_wp05_derived_outline.py
"""WP05 derived tabs retain algorithms while sharing a read-only glyph preview."""
import importlib
from types import SimpleNamespace as NS

import pytest
import test_studio_derived_glyphs as fixtures

opened = fixtures.opened
fresh_studios = fixtures.fresh_studios
studio_qt = fixtures.studio_qt


def test_effect_tabs_preview_and_stale_refusal(opened, monkeypatch):
    app = opened()
    tabs = importlib.import_module('fontlabapp.studios.derived_glyphs.effects')
    for mode, values in [('shadow', (40, -40)), ('effect', (30,))]:
        module = importlib.import_module('fontlabapp.studios.derived_glyphs.' + mode)
        row = NS(glyph=NS(name='A'), master='Regular', layer=NS(version=1), contours=2, note='')
        writes = []
        monkeypatch.setattr(module, 'survey', lambda *args, row=row: [row])
        monkeypatch.setattr(tabs, 'snapshot', lambda layer: layer.version)
        monkeypatch.setattr(module, 'add_shadows' if mode == 'shadow' else 'outline',
                            lambda *args, writes=writes: writes.append(args) or {'layers': 1, 'glyphs': 1})
        panel = tabs.EffectsPanel(app.tool, mode)
        panel.refresh()
        assert panel.grid.rows[0].glyph_name == 'A'
        assert panel.settings() == values
        panel.scope.setCurrentIndex(1)
        assert panel.plan(app.pkg, None) == [row]
        row.layer.version = 2
        assert not panel.apply()
        assert not writes
        panel.refresh()
        assert panel.apply()
        assert writes[-1][0] == [row]
        row.note = 'locked'
        panel.refresh()
        assert not panel.apply_button.isEnabled()
        assert panel.cells(row)[2][-1] == 'locked'
        row.layer = None
        assert panel.plan_key(app.pkg, [row])
        assert panel.row_name(row) == 'A'
        assert panel.preview_names(row) == []
        assert panel.result_text({'layers': 0, 'glyphs': 0}) == 'Nothing changed'
        assert panel.result_text({'layers': 1, 'glyphs': 2}) == 'Changed 1 layer in 2 glyphs'
    with pytest.raises(ValueError, match='Unknown'):
        tabs.EffectsPanel(app.tool, 'bad')


def test_backend_bridge_known_and_unknown(monkeypatch):
    bridge = importlib.import_module('fontlabapp.fontui.outline_generators')
    calls = []
    monkeypatch.setattr(bridge, 'import_module', lambda name: calls.append(name) or name)
    services = bridge.backends()
    for name, target in bridge.MODULES.items():
        assert getattr(services, name) == target
    with pytest.raises(AttributeError):
        _ = services.unknown
    assert calls == list(bridge.MODULES.values())


def test_outline_shell_actions_preview_and_cleanup(opened, monkeypatch):
    app = opened()
    module = importlib.import_module('fontlabapp.studios.derived_glyphs.outline')
    import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid native parent fallback
    from PySide6.QtWidgets import QWidget
    monkeypatch.setattr(module, 'snapshot', lambda layer: layer.advanceWidth)
    preview = QWidget()
    seen = []
    preview.load = lambda *args: seen.append(args)
    monkeypatch.setattr(module, 'EffectsPanel', lambda tool, mode: app.panels['Small caps'].__class__(tool))
    shell = module.show(package=lambda: app.pkg, font=lambda: 'font', preview=lambda shell, tool: preview)
    studio_qt_fixture = app.shell
    try:
        assert shell.preview_kind == 'tglyph'
        assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == [*module.TITLES, 'About']
        panel = shell.derived_glyphs_tool.views[0].__self__
        panel.row_chosen('H', 'Bold')
        assert seen[-1] == ('H', 'Bold')
        panel.row_chosen('missing', 'Regular')
        assert len(seen) == 1
        assert len(shell._actions) == 6
        shell._run_action('refresh')
        shell._run_action('preview')
        shell.tabs.setCurrentIndex(3)
        caps = shell.derived_glyphs_tool.views[3].__self__
        shell._run_action('apply')
        caps.apply_button.click()
        assert not app.writes
        caps.x_scale.setValue(80)
        shell._run_action('refresh')
        assert 'discard' in shell.status.text().lower()
        shell._run_action('preview')
        caps.x_scale.setValue(81)
        shell._run_action('apply')
        assert not app.writes
        shell._run_action('preview')
        from copy import copy
        glyph = app.pkg.findName('H')
        original_layer = glyph._layers['Regular']
        glyph._layers['Regular'] = copy(original_layer)
        shell._run_action('apply')
        assert not app.writes, 'same-width replacement layer needs a new Preview'
        glyph._layers['Regular'] = original_layer
        shell._run_action('preview')
        shell._run_action('apply')
        assert app.writes
        count = len(app.writes)
        shell._run_action('apply')
        assert len(app.writes) == count
        app.pkg.master = 'Bold'
        caps.row_chosen('H')
        assert seen[-1] == ('H', 'Regular')
        previous = app.pkg
        app.pkg = NS(id=999)
        shell._run_action('preview')
        assert 'font changed' in shell.status.text().lower()
        assert caps.package is previous
        app.pkg = previous

        monkeypatch.setattr(fontui, 'glyph_view', lambda *args, **kw: seen.append(kw) or preview)
        assert module.glyph_preview(shell, NS(font=lambda: None, current='Regular')) is None
        assert module.glyph_preview(shell, NS(font=lambda: 'font', current='Regular')) is preview
        assert seen[-1]['read_only'] is True
    finally:
        shell.close()
    assert not studio_qt_fixture.closed


def test_outline_shell_closes_on_failure(studio_qt, monkeypatch):
    import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid native parent fallback
    module = importlib.import_module('fontlabapp.studios.derived_glyphs.outline')
    closed = []
    monkeypatch.setattr(fontui, 'app_shell', lambda *a, **kw: NS(close=lambda: closed.append(True), package=lambda: None, set_status=lambda text: None))
    def fail(*args):
        raise RuntimeError('preview failed')
    with pytest.raises(RuntimeError, match='preview failed'):
        module.show(package=lambda: None, font=lambda: None, preview=fail)
    assert closed == [True]
