# this_file: tests/test_identity_tools_shell.py
"""WP07 embedded route state, accepted previews and close ownership."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def setup(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.identity_tools', raising=False)
    module = importlib.import_module('fontlabapp.fontui.identity_tools')
    gui = module.QtGui
    package = NS(id=7, master='Regular', defaultMaster='Regular')
    state = NS(package=package, calls=[], panels=[])
    monkeypatch.setattr(module.fontui, 'app_shell', studio_qt.modules.appshell.AppShell)
    monkeypatch.setattr(module.fontui, 'current_font', lambda: None)

    class Panel(gui.QDialog):
        def __init__(self, parent):
            super().__init__(parent)
            layout = gui.QVBoxLayout(self)
            self.field = gui.QLineEdit(self)
            self.close_button = gui.QPushButton('Close', self)
            layout.addWidget(self.field)
            layout.addWidget(self.close_button)
            state.panels.append(self)
        def reload(self):
            state.calls.append('reload')
        def refresh(self):
            state.calls.append('preview')
        def apply(self):
            state.calls.append('apply')

    def make(**kwargs):
        app = module.show('Identity', [module.Route('Names', Panel, apply='apply')],
                          package=lambda: state.package, **kwargs)
        studio_qt.owned.append(app)
        return app
    return NS(module=module, make=make, state=state, gui=gui, qt=studio_qt)


def test_embedded_route_requires_current_preview_and_preserves_staging(setup):
    app = setup.make(preview=None)
    panel = setup.state.panels[0]
    assert not panel.isWindow() and panel.close_button.isHidden()
    app._run_action('apply')
    assert setup.state.calls == []
    panel.field.setText('A')
    app._run_action('refresh')
    assert setup.state.calls == []
    assert 'discard' in app.status.text()
    app._run_action('preview')
    panel.field.setText('B')
    app._run_action('apply')
    assert setup.state.calls == ['preview']
    app._run_action('preview')
    app._run_action('apply')
    assert setup.state.calls == ['preview', 'preview', 'apply']
    app._run_action('refresh')
    assert setup.state.calls[-1] == 'reload'


def test_switched_package_refuses_and_unknown_tab_closes(setup):
    app = setup.make(preview=None, tab='Names')
    app._run_action('preview')
    setup.state.package = NS(id=8)
    app._run_action('apply')
    assert setup.state.calls == ['preview']
    app._run_action('preview')
    app._run_action('refresh')
    assert setup.state.calls == ['preview']
    assert 'no longer active' in app.status.text()
    with pytest.raises(ValueError, match='Unknown task'):
        setup.make(preview=None, tab='missing')


def test_preview_captures_font_and_layer_and_owns_it(setup, monkeypatch):
    seen = []
    def preview(font, **kwargs):
        seen.append((font, kwargs))
        return setup.qt.modules.lifecycle.Owned(kwargs['parent'])
    monkeypatch.setattr(setup.module.fontui, 'glyph_view', preview)
    monkeypatch.setattr(setup.module.fontui, 'metrics_preview', preview)
    for kind in ('tglyph', 'tmetrics'):
        app = setup.make(preview=kind, font='captured')
        assert seen[-1][0] == 'captured'
        assert seen[-1][1]['read_only'] is True
        assert seen[-1][1]['layer'] == 'Regular'
        child = app.preview
        app.close()
        assert child.closed


def test_no_font_and_read_only_route(setup):
    app = setup.make(preview='tglyph')
    assert app.preview is None
    assert 'Open a font' in app.status.text()
    route = setup.module.Route('Read', lambda parent: setup.gui.QWidget(parent), refresh=None, preview=None)
    app = setup.module.show('Read', [route], preview=None, package=lambda: None)
    setup.qt.owned.append(app)
    assert not app.apply_button.isVisible()
    assert not app.refresh_button.isEnabled()


def test_failed_panel_construction_and_close_ack_are_retained(setup):
    def broken(parent):
        raise RuntimeError('build failed')
    with pytest.raises(RuntimeError, match='build failed'):
        setup.module.show('Broken', [setup.module.Route('Broken', broken)], package=lambda: None)
    app = setup.make(preview=None)
    owner = app.route_panels[0]
    original = owner.panel.close
    owner.panel.close = lambda: False
    with pytest.raises(RuntimeError, match='refused'):
        app.close()
    assert owner in app.children
    owner.panel.close = original
    app.close()
    owner.close()


def test_activation_uses_sorted_name_and_captured_layer(setup):
    app = setup.make(preview=None)
    panel = app.route_panels[0]
    table = setup.gui.QTableWidget(2, 1)
    table.setItem(0, 0, setup.gui.QTableWidgetItem('Z'))
    table.setItem(1, 0, setup.gui.QTableWidgetItem('A'))
    panel.panel.table = table
    panel.route = setup.module.Route('Names', lambda parent: None, glyph_column=0)
    app.identity_font = {'A': 1, 'Z': 2}
    app.identity_layer = 'captured'
    seen = []
    app.preview = NS(load=lambda *args: seen.append(args), set_text=lambda text: seen.append(text))
    app.preview_kind = 'tglyph'
    table.sortItems(0)
    panel.activate(table.item(0, 0))
    assert seen == [('A', 'captured')]
    app.preview_kind = 'tmetrics'
    panel.activate(table.item(1, 0))
    assert seen[-1] == '/Z'
    app.identity_font = {}
    panel.activate(table.item(0, 0))
    assert len(seen) == 2
    panel.activate(None)
    assert app.status.text().startswith('Preview:')
    table.deleteLater()


def test_fingerprint_tracks_table_checks_selection_and_tree_children(setup):
    widget = setup.gui.QWidget()
    table = setup.gui.QTableWidget(1, 1, widget)
    item = setup.gui.QTableWidgetItem('A')
    table.setItem(0, 0, item)
    tree = setup.gui.QTreeWidget(widget)
    parent = setup.gui.QTreeWidgetItem(tree, ['U+0041'])
    child = setup.gui.QTreeWidgetItem(parent, ['A'])
    before = setup.module.fingerprint(widget)
    item.setCheckState(setup.qt.QtCore.Qt.Checked)
    assert setup.module.fingerprint(widget) != before
    before = setup.module.fingerprint(widget)
    table.selectRow(0)
    assert setup.module.fingerprint(widget) != before
    before = setup.module.fingerprint(widget)
    child.setCheckState(0, setup.qt.QtCore.Qt.Checked)
    assert setup.module.fingerprint(widget) != before
    assert setup.module.view_state(NS(model=lambda: None)) == ()
    widget.deleteLater()


def test_public_identity_factories_are_lazy_and_forward_exact_arguments(monkeypatch):
    import fontlabapp.fontui as fontui
    calls = []
    fake = NS(Route=lambda *a, **k: calls.append(('route', a, k)),
              show=lambda *a, **k: calls.append(('show', a, k)))
    monkeypatch.setattr(fontui, '_load', lambda name: fake)
    fontui.identity_route('Name', apply='write')
    fontui.identity_studio('Title', (), tab='Name')
    assert calls == [('route', ('Name',), {'apply': 'write'}),
                     ('show', ('Title', ()), {'tab': 'Name'})]
    monkeypatch.setattr(fontui.importlib, 'import_module', lambda name: NS(build=lambda parent: parent))
    assert fontui.identity_panel('some.module', 'build', 'parent') == 'parent'
    monkeypatch.setattr(fontui.importlib, 'import_module', lambda name: NS(build=lambda: lambda parent: parent))
    assert fontui.identity_panel('some.module', 'build', 'parent', factory_type=True) == 'parent'


@pytest.mark.parametrize('category,title,studio', [
    ('Features', 'Feature Authoring', 'feature_authoring'),
    ('Features', 'Feature Explorer', 'feature_explorer'),
    ('Features', 'Nastaliq Connections', 'nastaliq_connections'),
    ('Font Info', 'Font Identity', 'font_identity'),
    ('Font Info', 'Encoding and Order', 'encoding_order'),
    ('Names', 'Glyph Identity', 'glyph_identity'),
    ('Names', 'Glyph Labels', 'glyph_labels'),
    ('Names', 'Glyph Browser', 'glyph_browser'),
    ('Names', 'Character Consistency', 'character_consistency'),
])
def test_demo_opens_exact_studio(category, title, studio, monkeypatch):
    import runpy
    from pathlib import Path
    called = []
    monkeypatch.setitem(sys.modules, f'fontlabapp.studios.{studio}.app', NS(show=lambda: called.append(studio)))
    runpy.run_path(str(Path(__file__).parents[1] / 'Scripts' / category / (title + ' Demo.py')), run_name='__main__')
    assert called == [studio]
    loaded = runpy.run_path(str(Path(__file__).parents[1] / 'Scripts' / category / (title + ' Demo.py')))
    loaded['main']()
    assert called == [studio, studio]


def test_declared_preview_bindings_and_tree_child_target(setup):
    app = setup.make(preview=None)
    owner = app.route_panels[0]
    seen = []
    app.preview = NS(load=lambda *args: seen.append(args), set_text=lambda text: seen.append(text))
    owner.route = setup.module.Route('Names', lambda parent: None,
                                    preview_target=lambda panel: ('A', None),
                                    preview_text=lambda panel: '/A/V', glyph_column=0)
    owner.sync_preview()
    assert seen == [('A', 'Regular'), '/A/V']
    owner.route = setup.module.Route('Names', lambda parent: None, preview_target=lambda panel: ('', None))
    owner.sync_preview()
    assert len(seen) == 2
    setup.state.package = None
    owner.sync_preview()
    assert 'no longer active' in app.status.text()
    setup.state.package = NS(id=7)
    model = setup.gui.QStandardItemModel()
    top = setup.gui.QStandardItem('A')
    top.appendRow(setup.gui.QStandardItem('Unicode'))
    model.appendRow(top)
    app.identity_font = {'A': 1}
    app.preview_kind = 'tglyph'
    owner.route = setup.module.Route('Names', lambda parent: None, glyph_column=0)
    owner.activate(top.child(0).index())
    assert seen[-1] == ('A', 'Regular')


def test_real_table_selection_drives_captured_preview(setup, monkeypatch):
    seen = []
    class Preview(setup.qt.modules.lifecycle.Owned):
        def load(self, name, layer):
            seen.append((name, layer))
    monkeypatch.setattr(setup.module.fontui, 'glyph_view', lambda font, **kw: Preview(kw['parent']))
    class Panel(setup.gui.QWidget):
        def __init__(self, parent):
            super().__init__(parent)
            self.table = setup.gui.QTableWidget(2, 1, self)
            self.table.setItem(0, 0, setup.gui.QTableWidgetItem('Z'))
            self.table.setItem(1, 0, setup.gui.QTableWidgetItem('A'))
    route = setup.module.Route('Names', Panel, refresh=None, preview=None, glyph_column=0)
    app = setup.module.show('Glyphs', [route], preview='tglyph', font={'A': 1, 'Z': 2}, package=lambda: setup.state.package)
    setup.qt.owned.append(app)
    table = app.route_panels[0].panel.table
    table.sortItems(0)
    table.setCurrentCell(0, 0)
    assert seen[-1] == ('A', 'Regular')
    setup.state.package = NS(id=8)
    table.setCurrentCell(1, 0)
    assert seen[-1] == ('A', 'Regular')
    assert 'no longer active' in app.status.text()


def test_active_tab_preview_and_tree_after_model_replacement(setup, monkeypatch):
    seen = []
    class Preview(setup.qt.modules.lifecycle.Owned):
        def load(self, name, layer):
            seen.append((name, layer))
    monkeypatch.setattr(setup.module.fontui, 'glyph_view', lambda font, **kw: Preview(kw['parent']))
    class Panel(setup.gui.QWidget):
        def __init__(self, parent):
            super().__init__(parent)
            self.field = setup.gui.QLineEdit(self)
            self.view = setup.gui.QTreeView(self)
            self.reload()
        def reload(self):
            self.model = setup.gui.QStandardItemModel(self)
            self.model.appendRow(setup.gui.QStandardItem('A'))
            self.view.setModel(self.model)
    routes = [setup.module.Route('First', Panel, preview_target=lambda p: ('A', None),
                                 glyph_column=0, glyph_table='view', preview='reload'),
              setup.module.Route('Second', Panel, preview_target=lambda p: ('Z', None), preview='reload')]
    app = setup.module.show('Glyphs', routes, preview='tglyph', font={'A': 1, 'Z': 2}, package=lambda: setup.state.package)
    setup.qt.owned.append(app)
    assert seen == [('A', 'Regular')]
    first = app.route_panels[0].panel
    first.field.setText('draft')
    app.tabs.setCurrentIndex(1)
    assert seen[-1] == ('Z', 'Regular')
    app.tabs.setCurrentIndex(0)
    assert first.field.text() == 'draft' and seen[-1] == ('A', 'Regular')
    first.field.setText('')
    old = first.view.selectionModel()
    app._run_action('refresh')
    assert first.view.selectionModel() is not old
    seen.clear()
    first.view.clicked.emit(first.model.index(0, 0))
    assert seen == [('A', 'Regular')]


@pytest.mark.parametrize('dismiss', ['escape', 'reject', 'accept'])
def test_dialog_dismissal_closes_whole_shell(setup, dismiss):
    app = setup.make(preview=None)
    panel = app.route_panels[0].panel
    assert panel.isVisible()
    if dismiss == 'escape':
        event = setup.gui.QKeyEvent(setup.qt.QtCore.QEvent.KeyPress,
                                   setup.qt.QtCore.Qt.Key_Escape,
                                   setup.qt.QtCore.Qt.NoModifier)
        setup.qt.app.sendEvent(panel, event)
    else:
        getattr(panel, dismiss)()
    assert app.closed and app._close_complete
    assert app.children == []


def test_explicit_discard_refresh_and_readonly_filters(setup):
    app = setup.make(preview=None)
    owner = app.route_panels[0]
    owner.panel.field.setText('changed')
    app._run_action('refresh')
    assert setup.state.calls == []
    owner.discard_button.click()
    assert setup.state.calls == ['reload'] and owner.accepted is None
    setup.state.package = None
    owner.discard_button.click()
    assert 'no longer active' in app.status.text()


@pytest.mark.parametrize('kind,factory', [('tglyph', 'glyph_view'), ('tmetrics', 'metrics_preview')])
def test_preview_captures_active_master_and_retains_it_after_master_switch(setup, monkeypatch, kind, factory):
    seen = []
    def build(font, **kwargs):
        seen.append(kwargs['layer'])
        return setup.qt.modules.lifecycle.Owned(kwargs['parent'])
    monkeypatch.setattr(setup.module.fontui, factory, build)
    setup.state.package.master = 'Bold'
    app = setup.make(preview=kind, font='captured')
    assert seen == ['Bold'] and app.identity_layer == 'Bold'
    setup.state.package.master = 'Light'
    app._run_action('refresh')
    assert app.identity_layer == 'Bold' and seen == ['Bold']


@pytest.mark.parametrize('master', [None, '', '   ', 1])
def test_preview_refuses_unbound_active_master(setup, monkeypatch, master):
    setup.state.package.master = master
    monkeypatch.setattr(setup.module.fontui, 'metrics_preview', lambda *a, **k: pytest.fail('unbound preview'))
    with pytest.raises(ValueError, match='active master'):
        setup.make(preview='tmetrics', font='captured')


def test_fingerprint_when_wrappers_are_recreated_then_unchanged_and_edit_detected(setup):
    class Edit:
        def __init__(self, text):
            self.text = text

        def __call__(self):  # PythonQt-style: value is read by calling
            return self.text

    class Fake:
        """Every findChildren call returns brand-new wrapper objects, like PythonQt."""

        def __init__(self):
            self.texts = ["a", "b"]

        def findChildren(self, kind):
            if kind is setup.module.QtGui.QLineEdit:
                return [NS(text=Edit(t), isReadOnly=lambda: False) for t in self.texts]
            return []

    widget = Fake()
    before = setup.module.fingerprint(widget)
    assert setup.module.fingerprint(widget) == before, (
        "Fresh wrappers for the same children must not change the fingerprint"
    )
    widget.texts[1] = "c"
    assert setup.module.fingerprint(widget) != before, "A real edit must still change it"
