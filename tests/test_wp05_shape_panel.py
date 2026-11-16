# this_file: tests/test_wp05_shape_panel.py
"""Hosted shape routes reuse the original planner and editor contracts."""
import importlib
from types import SimpleNamespace as NS

import test_studio_derived_glyphs as fixtures

opened = fixtures.opened
fresh_studios = fixtures.fresh_studios
studio_qt = fixtures.studio_qt


def test_generator_accepts_only_reviewed_plan(opened, monkeypatch):
    app = opened()
    mod = importlib.import_module('fontlabapp.studios.shape_generators.panel')
    plans, writes = [], []
    def collect(glyphs, masters, planner, facts, **options):
        plans.append((tuple(masters), options))
        return NS(rows=[('A · Regular', NS(name='contour', old='ribbon', new='7 strips', problem=''))],
                  work=[('A', 'Regular', [])], problems=[], edits=1)
    monkeypatch.setattr(mod, 'snapshot', lambda layer: layer.advanceWidth)
    monkeypatch.setattr(mod, 'services', NS(writer=NS(collect=collect, apply_work=lambda *a, **kw: writes.append((a, kw)) or {'edits': 1, 'layers': 1, 'pending_note': 'queued'}, COMPATIBLE_LABEL='compatible', BASES_LABEL='bases'), history=NS(scan_auto_facts=lambda package: None)))
    fake = NS(TITLE='Comb', ToolPanel=NS(planner=lambda state: ('planner', state.strips.value), editor=lambda state: 'editor'))
    monkeypatch.setattr(mod, 'import_module', lambda name: fake)
    panel = mod.GeneratorPanel(app.tool, 'comb')
    panel.refresh()
    assert not panel.ready()
    panel.preview_plan()
    assert panel.ready()
    panel.controls[0].setValue(8)
    assert not panel.ready()
    panel.preview_plan()
    assert panel.ready()
    panel.apply()
    assert len(writes) == 1 and writes[0][0][1] == 'Comb'
    assert not panel.ready()
    assert 'queued' in app.tool.status


def test_generator_modes_refusals_and_row_identity(opened, monkeypatch):
    import pytest
    app = opened()
    mod = importlib.import_module('fontlabapp.studios.shape_generators.panel')
    state = NS(problems=[], work=[1], edits=1)
    def collect(*args, **kwargs):
        return NS(rows=[('A · Bold', NS(name='shape', old='', new='new', problem=''))],
                  work=state.work, problems=state.problems, edits=state.edits)
    monkeypatch.setattr(mod, 'snapshot', lambda layer: layer.advanceWidth)
    monkeypatch.setattr(mod, 'services', NS(writer=NS(collect=collect, apply_work=lambda *a, **k: {'edits': 1, 'layers': 1}, COMPATIBLE_LABEL='compatible', BASES_LABEL='bases'), history=NS(scan_auto_facts=lambda package: None)))
    source = NS(planner=lambda state: state, editor=lambda state: None)
    monkeypatch.setattr(mod, 'import_module', lambda name: NS(TITLE=name, ToolPanel=source, panel_type=lambda: source))
    for mode in ('sandblast', 'sansomatic'):
        panel = mod.GeneratorPanel(app.tool, mode)
        panel.refresh()
        assert not panel.dirty()
        assert panel.planner_state()
        panel.controls[0].setValue(90)
        assert panel.dirty()
        panel.discard()
        panel.reselect()
        calls = []
        app.tool.preview = NS(load=lambda *args, calls=calls: calls.append(args))
        panel.chosen('A', 'Bold')
        assert calls == [('A', 'Bold')]
        app.tool.preview = None
        panel.chosen('A', 'Bold')
        state.problems = ['locked']
        with pytest.raises(ValueError, match='locked'):
            panel.preview_plan()
        state.problems = []
        state.work = []
        with pytest.raises(ValueError, match='Nothing'):
            panel.preview_plan()
        state.work = [1]
        with pytest.raises(ValueError, match='plan changed'):
            panel.apply()
        panel.preview_plan()
        panel.scope.setCurrentIndex(0)
        assert not panel.ready()
        panel.preview_plan()
        panel.apply()
        original = app.active.package
        app.active.package = None
        with pytest.raises(ValueError, match='Open a font'):
            panel.capture()
        app.active.package = original
        panel.names = ['absent']
        with pytest.raises(ValueError, match='Selected glyphs'):
            panel.capture()


def test_medial_tab_reuses_original_routes(opened, monkeypatch):
    app = opened()
    model = importlib.import_module('fontlabapp.studios.shape_generators.myanmar')
    row = NS(source='A', target='ra.alt', note='', rebuild=(), layers=())
    calls = []
    source = NS(survey=lambda state, package, facts, consent: calls.append((state.names, state.group_count.value, consent)) or [row],
                cells=lambda state, record: [record.target, 'Regular: +10', 'bounds'])
    monkeypatch.setattr(model, 'panel_type', lambda: source)
    monkeypatch.setattr(model, 'prepare', lambda rows: ['prepared'])
    monkeypatch.setattr(model, 'preview_key', lambda rows: tuple(record.target for record in rows))
    module = importlib.import_module('fontlabapp.studios.shape_generators.medial')
    panel = module.MedialPanel(app.tool)
    panel.refresh()
    assert calls[-1] == (app.selection, 5, False)
    assert panel.jobs(panel.rows) == ['prepared']
    assert panel.plan_key(app.pkg, panel.rows) == (app.pkg.id, 5, ('ra.alt',))
    assert panel.cells(row) == ('A', 'Regular', ('Regular: +10', 'bounds'))
    panel.names = []
    panel.refresh()
    assert calls[-1][0] == []


def test_angular_preview_never_writes_and_process_restore_are_explicit(opened):
    import pytest
    from test_angularizzle_session import OwnedBackend, layer
    app = opened()
    viewed = []
    app.tool.preview = NS(refresh=lambda: None, load=lambda *args: viewed.append(args))
    module = importlib.import_module('fontlabapp.studios.shape_generators.angular')
    backend = OwnedBackend((layer(),))
    backend._bound = {'A': NS(glyph_name='A', layer=NS(name='Regular'))}
    panel = module.AngularPanel(app.tool, backend=backend, preferences={})
    try:
        assert viewed == [('A', 'Regular')]
        assert not panel.ready() and not panel.dirty()
        with pytest.raises(ValueError, match='Preview'):
            panel.apply()
        panel.preview_plan()
        assert not any(call[0] == 'apply' for call in backend.calls)
        assert panel.ready() and panel.dirty()
        panel.plane.setText('40')
        assert not panel.ready()
        panel.preview_plan()
        panel.apply()
        assert ('apply', False) in backend.calls
        panel.discard_button.click()
        assert not panel.dirty()
        panel.cancel()
        assert ('apply', True) in backend.calls
        with pytest.raises(ValueError, match='finished'):
            panel.preview_plan()
        panel.run(lambda: (_ for _ in ()).throw(ValueError('kept')))
        assert app.tool.status == 'kept'
    finally:
        panel.close()


def test_angular_settings_and_partial_owner_cleanup(opened, monkeypatch):
    from test_angularizzle_session import OwnedBackend, layer
    app = opened()
    app.tool.preview = NS(refresh=lambda: None)
    module = importlib.import_module('fontlabapp.studios.shape_generators.angular')
    prefs = module.services.angular_settings
    calls = []
    monkeypatch.setattr(prefs, 'native_preferences', lambda qt: ('settings', {}))
    monkeypatch.setattr(prefs, 'persist', lambda *args, calls=calls: calls.append(args))
    panel = module.AngularPanel(app.tool, backend=OwnedBackend((layer(),)))
    panel.preview_plan()
    panel.apply()
    assert calls[0][-1] == (prefs.PLANE, prefs.CHECK)
    panel.run(panel.discard)
    panel.close()
    partial = module.AngularPanel.__new__(module.AngularPanel)
    module.services.lifecycle.Owned.__init__(partial, app.shell.widget)
    partial.close()


def test_shape_shell_captures_font_and_closes_failed_assembly(studio_qt, monkeypatch):
    import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid native parent fallback
    import pytest
    from fontlabapp.studios import TabSpec
    from PySide6.QtWidgets import QWidget
    module = importlib.import_module('fontlabapp.studios.shape_generators.app')
    state = NS(package=NS(id=1, master='Regular', masters=['Regular']), failure=False)
    Owned = studio_qt.modules.lifecycle.Owned
    class Angular(Owned):
        def __init__(self, tool, **kwargs):
            super().__init__(tool.shell.widget)
            if state.failure:
                raise RuntimeError('angular failed')
    monkeypatch.setattr(module, 'AngularPanel', Angular)
    monkeypatch.setattr(module, 'GeneratorPanel', lambda tool, mode: NS(widget=QWidget(), refresh=lambda: None))
    monkeypatch.setattr(module, 'MedialPanel', lambda tool: NS(widget=QWidget()))
    monkeypatch.setattr(module, 'bind', lambda shell, tool, panel, title: shell.add_tab(TabSpec(title, lambda owner: panel.widget)))
    previews = []
    monkeypatch.setattr(fontui, 'glyph_view', lambda *args, **kwargs: previews.append(kwargs) or QWidget())
    shell = module.show(package=lambda: state.package, font=lambda: 'font', preferences={})
    try:
        assert shell.tabs.count() == 6
        assert previews[-1]['read_only']
        state.package = NS(id=2)
        with pytest.raises(ValueError, match='font changed'):
            shell.package()
    finally:
        shell.close()
    state.package = None
    empty = module.show(package=lambda: None, font=lambda: None, preferences={})
    empty.close()
    supplied = module.show(package=lambda: None, font=lambda: None, preview=lambda *args: QWidget(), preferences={})
    supplied.close()
    state.failure = True
    with pytest.raises(RuntimeError, match='angular failed'):
        module.show(package=lambda: None, font=lambda: None, preferences={})
