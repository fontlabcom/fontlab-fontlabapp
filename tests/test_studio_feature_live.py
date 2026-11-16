# this_file: tests/test_studio_feature_live.py
"""Real connected Qt controls in the three feature studios; native font is a double."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401
from PySide6 import QtCore, QtWidgets


@pytest.fixture
def feature_studio(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp.fontui.feature_blocks as blocks
    import fontlabapp.glyphs.catalog.model as catalog
    from fontlabapp import fontui
    from fontlabapp.core import completion, scripting

    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.identity_tools', raising=False)
    adapter = importlib.import_module('fontlabapp.fontui.identity_tools')
    gui = NS(**vars(adapter.QtGui))

    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)
    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)
    class Line(QtWidgets.QLineEdit):
        text = property(QtWidgets.QLineEdit.text)
    class Combo(QtWidgets.QComboBox):
        currentIndex = property(QtWidgets.QComboBox.currentIndex)
        currentText = property(QtWidgets.QComboBox.currentText)
        count = property(QtWidgets.QComboBox.count)
    class Viewport(QtWidgets.QWidget):
        width = property(QtWidgets.QWidget.width)
    class Scroll(QtWidgets.QScrollArea):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setViewport(Viewport(self))
    class Attachment(QtWidgets.QWidget):
        def set_panels(self, panels):
            self.panels = panels

    gui.QDialog, gui.QLabel, gui.QLineEdit, gui.QComboBox, gui.QScrollArea = Dialog, Label, Line, Combo, Scroll
    monkeypatch.setitem(sys.modules, 'PythonQt', NS(QtCore=QtCore, QtGui=gui))
    names = ['a', 'a.sc', 'b', 'b.sc', 'f', 'i', 'f_i', 'BEm1', 'BEm2', 'BEi1', 'BEf1']
    package = NS(id=17, fgId=17, master='Regular', defaultMaster='Regular', masters=['Regular', 'Bold'],
                 findName=lambda name: NS(isNull=False, findLayer=lambda layer: None) if name in names else None)
    groups = NS(items=lambda: [('Letters', NS(isFeaGroup=lambda: True))],
                getAsClassRecords=lambda: ['Letters:a b'])
    native = NS(CurrentFont=lambda: NS(glyphs=[NS(name=name) for name in names], groups=groups),
                CurrentGlyph=lambda: NS(name='a'))
    monkeypatch.setitem(sys.modules, 'fontlab', native)
    monkeypatch.setattr(scripting, 'current_package', lambda *args: package)
    monkeypatch.setattr(scripting, 'close_script_dialog', lambda panel, event, key: event.accept())
    monkeypatch.setattr(completion, 'install', lambda *args: None)
    monkeypatch.setattr(scripting, 'anchors_view_types', lambda: NS(AttachmentView=Attachment))
    source = {'prefix': '', 'features': [('liga', 'feature liga { sub f i by f_i; } liga;')]}
    monkeypatch.setattr(blocks, 'read_feature_blocks', lambda package: source)
    monkeypatch.setattr(catalog, 'capture', lambda: NS(rows=tuple((name, 'U+0061', '') for name in names)))
    monkeypatch.setattr(fontui, 'app_shell', studio_qt.modules.appshell.AppShell)

    class Proof(studio_qt.modules.lifecycle.Owned):
        def __init__(self, font, **kwargs):
            super().__init__(kwargs['parent'])
            self.texts, self.targets = [], []
        def set_text(self, text):
            self.texts.append(text)
        def load(self, name, layer):
            self.targets.append((name, layer))
    monkeypatch.setattr(fontui, 'metrics_preview', Proof)
    monkeypatch.setattr(fontui, 'glyph_view', Proof)
    for name in list(sys.modules):
        if name in ('fontlabapp.fonts.info.ui', 'fontlabapp.features.editor.ui') or name.startswith('fontlabapp.features.identity_tools.'):
            monkeypatch.delitem(sys.modules, name, raising=False)

    def make(studio):
        module = importlib.import_module('fontlabapp.studios.' + studio + '.app')
        shell = module.show(font=dict.fromkeys(names), package=lambda: package)
        studio_qt.owned.append(shell)
        return shell
    make.names, make.source = names, source
    return make


def test_authoring_actual_controls_change_proof_and_keep_source_read_only(feature_studio):
    shell = feature_studio('feature_authoring')
    suffix, classes, viewer, random = [owner.panel for owner in shell.route_panels]
    assert suffix._preview_valid, suffix.status.text()
    assert '/a/a.sc' in shell.preview.texts[-1]
    suffix.suffix.setText('missing')
    assert shell.preview.texts[-1] == ''
    shell.tabs.setCurrentIndex(1)
    assert shell.preview.texts[-1] == '/a/b'
    classes.search.setText('missing')
    assert shell.preview.texts[-1] == ''
    shell.tabs.setCurrentIndex(2)
    viewer.feature.setCurrentIndex(1)
    assert shell.preview.texts[-1] == '/f/i/f_i'
    shell.tabs.setCurrentIndex(3)
    random.source_edit.setPlainText('a a.sc')
    shell._run_action('preview')
    assert shell.preview.texts[-1] == '/a/a.sc'
    assert shell.route_panels[-1].ready()


def test_explorer_actual_base_suffix_and_table_controls_update_proof(feature_studio):
    shell = feature_studio('feature_explorer')
    alternate, ligature, suffix = [owner.panel for owner in shell.route_panels]
    alternate.base.setText('b')
    assert shell.preview.texts[-1] == '/b/b.sc'
    shell.tabs.setCurrentIndex(1)
    assert shell.preview.texts[-1] == '/f/i/f_i'
    ligature.search.setText('none')
    assert shell.preview.texts[-1] == ''
    shell.tabs.setCurrentIndex(2)
    assert '/a/a.sc' in shell.preview.texts[-1]
    suffix.table.setCurrentCell(-1, -1)
    assert shell.preview.texts[-1] == ''


def test_nastaliq_actual_alternate_and_master_selectors_load_captured_target(feature_studio):
    shell = feature_studio('nastaliq_connections')
    panel = shell.route_panels[0].panel
    assert panel._preview_valid, panel.status.text()
    panel.family_pick.setCurrentIndex(panel.family_pick.findText('BEm'))
    panel.variant_pick.setCurrentIndex(panel.variant_pick.findText('BEm2'))
    panel.master_pick.setCurrentIndex(panel.master_pick.findText('Bold'))
    assert shell.preview.targets[-1] == ('BEm2', 'Bold')
    assert panel.reload_button.isHidden()


def test_refresh_reads_new_font_names_and_exact_feature_source(feature_studio):
    authoring = feature_studio('feature_authoring')
    explorer = feature_studio('feature_explorer')
    feature_studio.names.extend(['a.alt', 'f_f'])
    feature_studio.source['features'] = [('liga', 'feature liga { sub f f by f_f; } liga;')]
    authoring.tabs.setCurrentIndex(1)
    authoring._run_action('refresh')
    assert authoring.preview.texts[-1] == '/a/b'
    authoring.tabs.setCurrentIndex(2)
    viewer = authoring.route_panels[2].panel
    viewer.feature.setCurrentIndex(1)
    authoring.route_panels[2].reload()
    assert viewer.sources[1][1] == feature_studio.source['features'][0][1]
    assert authoring.preview.texts[-1] == '/f/f_f'
    for owner in explorer.route_panels:
        owner.reload()
    alternate, ligature, suffix = [owner.panel for owner in explorer.route_panels]
    assert 'a.alt' in alternate.preview_names
    assert any(row[0] == 'f_f' for row in ligature.rows)
    assert any(row[0] == 'alt' for row in suffix.rows)
