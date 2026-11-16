# this_file: tests/test_wp05_outline_compatibility.py
"""S17 shares exact readers and write strategies with captured-target shell tabs."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401
from test_studio_outline_doctor import qt_doctor, font, same_small  # noqa: F401


@pytest.fixture
def compatibility(qt_doctor, monkeypatch):  # noqa: F811 - imported fixture
    for name in ('outline_compatibility', 'outline_editing'):
        monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.' + name, raising=False)
    module = importlib.import_module('fontlabapp.fontui.outline_compatibility')
    package = font(A=same_small)
    package.id = 7
    for master in package.masters:
        object.__setattr__(package.layer('A', master), 'advanceWidth', 600)
        object.__setattr__(package.layer('A', master), 'isNull', False)
    live = [package]
    canvas = qt_doctor.modules.lifecycle.Owned(None)
    canvas.load = lambda *args: None
    canvas.set_overlay = lambda *args: None
    canvas.refresh = lambda: None
    canvas.highlight = lambda **kwargs: None
    shell = module.fontui.show_outline_compatibility(package=lambda: live[0], selection=lambda: ['A'],
                        font=lambda: object(), preview=lambda *args: canvas)
    qt_doctor.owned.append(shell)
    return NS(module=module, shell=shell, package=package, live=live)


def test_three_routes_are_real_tabs_and_preview_is_read_only(compatibility):
    app = compatibility
    assert [app.shell.tabs.tabText(i) for i in range(app.shell.tabs.count())] == [
        'Contour Order View', 'Make Compatible', 'Node Statistics', 'About']
    order, stats = app.shell.read_tabs
    order.refresh()
    stats.refresh()
    assert order.view.columns and stats.table.rows
    assert not app.package.writes()
    with pytest.raises(ValueError, match='Preview'):
        app.shell.compatible_tab.apply_changes()


def test_read_tabs_reject_replaced_font_and_stale_counts(compatibility, monkeypatch):
    app = compatibility
    stats = app.shell.read_tabs[1]
    stats.refresh()
    monkeypatch.setattr(app.module.readers, 'glyph_counts', lambda *args: {'Regular': (1, 2), 'Bold': (2, 3)})
    with pytest.raises(ValueError, match='changed'):
        stats.select_flagged()
    app.live[0] = NS(id=999)
    with pytest.raises(ValueError, match='font'):
        stats.refresh()


def test_exact_compatible_conversion_and_staged_discard(compatibility, monkeypatch):
    from test_studio_interpolation_doctor import build_e
    from _outline_fakes import T
    app = compatibility
    app.package.add('E', build_e)
    for master in app.package.masters:
        layer = app.package.layer('E', master)
        object.__setattr__(layer, 'advanceWidth', 600)
        object.__setattr__(layer, 'isNull', False)
        for shape in layer.shapes:
            shape.transform = T()
    tab = app.shell.compatible_tab
    tab.glyphs_field.setText('E')
    before = app.package.layer('E', 'Regular').shapes[0].contours[0].nodesCount
    calls = []
    def history(label, glyphs, mutate, **kwargs):
        calls.append(label)
        mutate()
        return NS(mismatches=kwargs['read_back']())
    monkeypatch.setattr(app.shell, 'history', history)
    tab.preview_changes()
    app.shell.tabs.setCurrentIndex(1)
    app.shell._run_action('refresh')
    assert 'discard' in app.shell.status.text()
    assert tab.apply_changes()
    assert app.package.layer('E', 'Regular').shapes[0].contours[0].nodesCount == before + 2
    assert len(calls) == 1 and not tab.ready()
    tab.discard()


def test_statistics_scope_flags_selection_and_row_identity(compatibility, monkeypatch):
    app = compatibility
    tab = app.shell.read_tabs[1]
    counts = {'Regular': (1, 2), 'Bold': (2, 3)}
    monkeypatch.setattr(app.module.readers, 'glyph_counts', lambda *args: counts.copy())
    monkeypatch.setattr(app.module.readers, 'all_names', lambda *args: ['A'])
    selected = []
    monkeypatch.setattr(app.module.scripting, 'select_glyphs', lambda names, package_id: selected.append((names, package_id)) or list(names))
    tab.whole.setChecked(True)
    tab.only_flagged.setChecked(True)
    tab.refresh()
    assert tab.select_flagged() == ['A']
    assert selected == [(['A'], 7)]
    seen = []
    app.shell.preview.load = lambda *args: seen.append(args)
    tab.row_selected('A', 'Bold')
    assert seen[-1] == ('A', 'Bold')
    counts['Bold'] = (1, 2)
    tab.refresh()
    assert not tab.table.rows
    counts['Bold'] = None
    tab.only_flagged.setChecked(False)
    tab.refresh()
    assert tab.table.rows[-1].values[1:3] == ('auto', 'auto')
    app.live[0] = None
    tab.guard_refresh()
    assert tab.accepted is None and 'font' in app.shell.status.text()
    tab.row_selected('A', 'Bold')
    assert 'changed' in app.shell.status.text()


def test_order_auto_empty_and_master_refusal(compatibility):
    app = compatibility
    tab = app.shell.read_tabs[0]
    app.package.layer('A', 'Bold').autoLayer = True
    tab.refresh()
    assert tab.view.columns[-1] == ('Bold (auto)', [])
    tab.glyph.clear()
    tab.refresh()
    assert not tab.table.rows
    app.package.master = 'Bold'
    with pytest.raises(ValueError, match='master'):
        tab.refresh()


def test_default_view_requires_read_only_and_missing_font_refuses(compatibility, monkeypatch):
    module = compatibility.module
    seen = []
    monkeypatch.setattr(module.fontui, 'glyph_view', lambda *args, **kwargs: seen.append(kwargs) or 'view')
    studio = compatibility.shell.compatible_tab.studio
    assert module._preview(compatibility.shell, studio) == 'view'
    assert seen == [{'layer': 'Regular', 'controls': False, 'read_only': True, 'label_prefix': 'Outline Compatibility'}]
    with pytest.raises(ValueError, match='Open a font'):
        module.show(package=lambda: None)


def test_failed_construction_retains_cleanup_owner(compatibility, monkeypatch):
    module = compatibility.module
    from fontlabapp.fontui.appshell import AppShell
    close = AppShell.close
    monkeypatch.setattr(AppShell, 'close', lambda self: (_ for _ in ()).throw(RuntimeError('disconnect failed')))
    with pytest.raises(Exception) as caught:
        module.show(package=lambda: compatibility.package, font=lambda: (_ for _ in ()).throw(ValueError('font unavailable')))
    owner = caught.value.owner
    monkeypatch.setattr(AppShell, 'close', close)
    owner.close()
    assert owner._close_complete


def test_incomplete_refresh_refuses_results(compatibility, monkeypatch):
    tab = compatibility.shell.read_tabs[1]
    rows, flagged, columns, token = tab.read()
    count = [0]
    def unstable():
        count[0] += 1
        return rows, flagged, columns, (count[0],)
    monkeypatch.setattr(tab, 'read', unstable)
    with pytest.raises(ValueError, match='during refresh'):
        tab.refresh()
    assert tab.accepted is None
