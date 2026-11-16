# this_file: tests/test_core_pythonqt_labs_e07_e09.py
"""Every retained proof, Unicode and review profile has an embedded route."""
import importlib
import pytest
from legacy_panel_qt import legacy_qt as legacy_qt, font_host as font_host


def test_profiles_have_all_original_routes():
    module = importlib.import_module('fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09')
    assert {key: len(rows) for key, rows in module.PROFILES.items()} == {'E07': 8, 'E08': 7, 'E09': 5}
    for rows in module.PROFILES.values():
        assert len({title for title, build in rows}) == len(rows)
        assert all(callable(build) for title, build in rows)


def test_registry_dispatch_and_character_map_variants(monkeypatch):
    from types import SimpleNamespace
    import sys
    from fontlabapp.fontui.core_pythonqt_labs.profiles import e07_e09

    seen = []
    monkeypatch.setattr(e07_e09, 'import_module', lambda name: SimpleNamespace(build=lambda parent: seen.append((name, parent))))
    e07_e09.build_profile('glyph_proof_groups', 'parent')
    assert seen == [('fontlabapp.fontui.core_pythonqt_labs.profiles.glyph_proof_groups', 'parent')]
    monkeypatch.setitem(sys.modules, 'PythonQt', SimpleNamespace(QtCore='core', QtGui='gui'))
    monkeypatch.setitem(sys.modules, 'fontlabapp.glyphs.character_map.capture', SimpleNamespace(capture='capture'))
    monkeypatch.setitem(sys.modules, 'fontlabapp.glyphs.character_map.ui', SimpleNamespace(panel_type=lambda core, gui, part: lambda parent, capture: (core, gui, part, parent, capture)))
    assert e07_e09.character_map(2, 'parent') == ('core', 'gui', 2, 'parent', 'capture')
    assert e07_e09.character_map(3, 'parent') == ('core', 'gui', 3, 'parent', 'capture')


def test_migrated_builders_use_original_constructor_routes(monkeypatch):
    from types import SimpleNamespace
    import sys
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09 import PROFILES

    qt = SimpleNamespace()
    monkeypatch.setitem(sys.modules, 'fly', SimpleNamespace(qt=qt))
    for rows in PROFILES.values():
        for title, callback in rows:
            if title.startswith('Glyph Character Map') or title == 'Unicode Issues Dock':
                continue
            module = importlib.import_module('fontlabapp.fontui.core_pythonqt_labs.profiles.' + callback.args[0])
            if title in ('Glyph Batch Recipe Settings', 'Glyph Proof Batch Wizard', 'Glyph Proof Groups', 'Proof Text Coverage Dialog'):
                monkeypatch.setattr(module, 'main', lambda parent: ('main', parent))
                assert module.build('parent') == ('main', 'parent')
            elif title == 'Apply Unicode Map':
                panel = SimpleNamespace(table=SimpleNamespace(horizontalHeader=lambda: SimpleNamespace(setSectionResizeMode=lambda mode: None), setSortingEnabled=lambda enabled: None))
                qt.QtGui = SimpleNamespace(QHeaderView=SimpleNamespace(Interactive='interactive'))
                monkeypatch.setattr(module, 'panel_type', lambda: lambda parent: panel)
                assert module.build('parent') is panel
            elif hasattr(module, 'panel_type'):
                monkeypatch.setattr(module, 'panel_type', lambda *args: lambda parent: ('panel', parent))
                assert module.build('parent') == ('panel', 'parent')
            else:
                monkeypatch.setattr(module, 'show', lambda binding, parent, *, embedded: (binding, parent, embedded))
                assert module.build('parent') == (qt, 'parent', True)


def test_dock_embedding_retains_refused_close_for_retry(monkeypatch):
    from types import SimpleNamespace
    import sys
    from fontlabapp.fontui.core_pythonqt_labs.profiles import unicode_issues_dock

    class MainWindow:
        def __init__(self, parent):
            self.parent = parent

    answers = iter([False, True])
    monkeypatch.setitem(sys.modules, 'fly', SimpleNamespace(qt=SimpleNamespace(QtGui=SimpleNamespace(QMainWindow=MainWindow))))
    monkeypatch.setattr(unicode_issues_dock, 'show', lambda qt, host, **kwargs: SimpleNamespace(close_owned=lambda: next(answers)))
    host = unicode_issues_dock.build('parent')
    events = []
    event = SimpleNamespace(accept=lambda: events.append('accepted'), ignore=lambda: events.append('refused'))
    host.closeEvent(event)
    assert host.controller is not None
    host.closeEvent(event)
    assert events == ['refused', 'accepted']




@pytest.mark.parametrize('lab,index', [(lab, index) for lab, count in [('E07', 8), ('E08', 7), ('E09', 5)] for index in range(count)])
def test_real_profile_builders_create_embeddable_widgets(legacy_qt, font_host, monkeypatch, lab, index):  # noqa: F811 - fixtures
    """Build real controls; only native font capture is replaced at its boundary."""
    import fly
    from types import SimpleNamespace
    from PySide6 import QtCore, QtWidgets
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09 import PROFILES
    from fontlabapp.core import scripting
    from fontlabapp.glyphs.catalog import model as catalogue

    qt = SimpleNamespace(QtCore=QtCore, QtGui=legacy_qt.gui)
    monkeypatch.setattr(fly, 'qt', qt)
    monkeypatch.setattr(scripting, 'current_package', lambda *args, **kwargs: None)
    import sys
    monkeypatch.setattr(sys.modules['fontlab'], 'CurrentFont', lambda: None, raising=False)
    def no_font(*args, **kwargs):
        raise ValueError('Open a font first.')
    monkeypatch.setattr(catalogue, 'capture', no_font)
    parent = QtWidgets.QWidget()
    legacy_qt.owned.append(parent)
    widget = PROFILES[lab][index][1](parent)
    legacy_qt.owned.append(widget)
    widget.setParent(parent, QtCore.Qt.Widget)
    assert isinstance(widget, QtWidgets.QWidget)
    assert not widget.isWindow()
    assert widget.close() is True


@pytest.mark.parametrize('title', [
    'Glyph Batch Recipe Settings', 'Glyph Proof Batch Wizard', 'Glyph Proof Groups',
    'Glyph Proof Worksheet', 'Pair Proof Generator', 'Saved Proof Sample',
    'Glyph Proof Layout', 'Glyph Proof Pad', 'Glyph Coverage Grid', 'Glyph Encoding Chart',
    'Glyph Character Map', 'Glyph Character Map - Styles', 'Proof Text Coverage Dialog',
    'Unicode Issues Dock', 'Apply Unicode Map', 'Glyph Mark Colours', 'Glyph Review Form',
    'Glyph Review Priorities', 'Glyph Mark Colour Board', 'Glyph Review Cards',
])
def test_shell_actions_publish_profile_results_and_preserve_drafts(title):
    from types import SimpleNamespace as NS
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09_actions import bindings, REFRESH

    calls, published = [], []
    panel = NS(snapshot=(('A', 'U+0041', ''),), drafts={}, pending=False, dirty=False,
               names=('A',), cards=(('A', 'Review', 'Note'),), draft='A',
               current_row=1, table_view=NS(currentIndex=lambda: NS(isValid=False)), text=NS(text='A'), output=NS(toPlainText=lambda: '{"glyphs": ["A"]}' if title == 'Glyph Batch Recipe Settings' else '/A'),
               output_box=NS(toPlainText=lambda: '/A'), sample_text=lambda: 'A',
               issue_snapshot=(('A', 'duplicate'), ('A', 'missing')),
               has_draft=lambda: True, apply=lambda: calls.append('apply'), rows=[{'ready': True}],
               is_ready=lambda row: row['ready'])
    setattr(panel, REFRESH[title], lambda: calls.append('refresh'))
    owner = NS(controller=panel) if title == 'Unicode Issues Dock' else panel
    actions = bindings(owner, title, published.append)
    actions['refresh']()
    assert calls == ['refresh']
    actions['preview']()
    assert published and published[0] in ('A', '/A', ('A',))
    assert actions['dirty']() == (title == 'Glyph Review Cards')
    panel.dirty = True
    assert actions['dirty']()
    if 'apply' in actions:
        assert actions['ready']()
        actions['apply']()
        assert calls[-1] == 'apply'
        panel.snapshot, panel.rows = (), []
        assert not actions['ready']()


def test_worksheet_preview_refuses_unsubmitted_local_draft():
    from types import SimpleNamespace as NS
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09_actions import proof_text
    with pytest.raises(ValueError, match='Apply Draft'):
        proof_text(NS(pending=True), 'Glyph Proof Worksheet')


@pytest.mark.parametrize('name', ['glyph_batch_recipe_settings', 'proof_text_coverage_dialog'])
def test_dialog_capture_rejects_surrogate_and_expired_reads(monkeypatch, name):
    from types import SimpleNamespace as NS
    from fontlabapp.glyphs.catalog import model as catalogue
    module = importlib.import_module('fontlabapp.fontui.core_pythonqt_labs.profiles.' + name)
    monkeypatch.setattr(catalogue, 'capture', lambda **kwargs: NS(rows=(('A', 'U+D800', ''),)))
    with pytest.raises(ValueError, match='scalar'):
        module.glyph_rows()
    ticks = iter((0, 3))
    monkeypatch.setattr(module, 'monotonic', lambda: next(ticks))
    with pytest.raises(TimeoutError, match='expired'):
        module.glyph_rows()


@pytest.mark.parametrize('case', ['no-font', 'no-glyph', 'no-layer', 'infinite', 'empty-shapes'])
def test_spacing_capture_validates_whole_boundary(monkeypatch, case):
    from types import SimpleNamespace as NS
    from fontlabapp.core import scripting
    from fontlabapp.fontui.core_pythonqt_labs.profiles import glyph_proof_layout as module
    layer = NS(id=3, isNull=False, advanceWidth=float('inf') if case == 'infinite' else 500,
               shapesCount=0)
    glyph = NS(id=2, name='A', isNull=False, isValid=True, package=NS(id=1),
               findLayer=lambda name: None if case == 'no-layer' else layer)
    package = NS(id=1, fgId=4, master='Regular', findName=lambda name: None if case == 'no-glyph' else glyph)
    monkeypatch.setattr(scripting, 'current_package', lambda: None if case == 'no-font' else package)
    if case == 'empty-shapes':
        assert module.capture_spacing(('A',)) == (('A', 500.0, None, None),)
    else:
        with pytest.raises(ValueError):
            module.capture_spacing(('A',))


def test_layout_rejects_duplicate_names_and_empty_strip():
    from fontlabapp.fontui.core_pythonqt_labs.profiles import glyph_proof_layout as module
    with pytest.raises(ValueError, match='Duplicate'):
        module.check_names(('A', 'A'))
    with pytest.raises(ValueError, match='positive strip'):
        module.strip_widths((), 100)


def test_worksheet_rejects_invalid_counts_names_and_large_output(monkeypatch):
    from fontlabapp.fontui.core_pythonqt_labs.profiles import glyph_proof_worksheet as module
    with pytest.raises(ValueError):
        module.validate_draft('bad')
    with pytest.raises(ValueError, match='slash-name'):
        module.build_rows((('a/b', '', ''),), {})
    monkeypatch.setattr(module, 'MAX_PROOF_CHARS', 2)
    with pytest.raises(ValueError, match='million'):
        module.build_rows((('A', '', ''),), {})


def test_worksheet_live_controls_refuse_missing_pending_and_dirty_data(legacy_qt, font_host, monkeypatch):  # noqa: F811 - fixtures
    import fly
    from types import SimpleNamespace as NS
    from PySide6 import QtCore
    from fontlabapp.fontui.core_pythonqt_labs.profiles import glyph_proof_worksheet as module
    qt = NS(QtCore=QtCore, QtGui=legacy_qt.gui)
    monkeypatch.setattr(fly, 'qt', qt)
    panel = module.show(qt, capture=lambda: NS(rows=()), embedded=True)
    legacy_qt.owned.append(panel)
    with pytest.raises(ValueError, match='Open a font'):
        panel.apply_draft()
    panel.pending = True
    for action in (panel.copy_report, panel.export_report):
        with pytest.raises(ValueError, match='Apply Draft'):
            action()
    panel.pending = False
    panel.owned_model = None
    for action in (panel.copy_report, panel.export_report):
        with pytest.raises(ValueError, match='snapshot'):
            action()
    panel.dirty = True
    with pytest.raises(ValueError, match='Reset Draft'):
        panel.refresh()
    assert panel.close() is False
    panel.dirty = False
    assert panel.close() is True


def test_saved_sample_external_destruction_is_idempotent(legacy_qt, font_host, monkeypatch):  # noqa: F811 - fixtures
    import fly
    from types import SimpleNamespace as NS
    from PySide6 import QtCore
    from fontlabapp.fontui.core_pythonqt_labs.profiles import saved_proof_sample as module
    qt = NS(QtCore=QtCore, QtGui=legacy_qt.gui)
    monkeypatch.setattr(fly, 'qt', qt)
    panel = module.show(qt, None, embedded=True)
    legacy_qt.owned.append(panel)
    panel.release_owner()
    panel.release_owner()
    assert panel not in module._PANELS


@pytest.mark.parametrize('name', ['glyph_mark_colours', 'glyph_review_form', 'apply_unicode_map'])
def test_local_apply_button_uses_replaced_live_callback(legacy_qt, font_host, monkeypatch, name):  # noqa: F811 - fixtures
    import fly
    import sys
    from types import SimpleNamespace as NS
    from PySide6 import QtCore, QtWidgets
    from fontlabapp.core import scripting
    module = importlib.import_module('fontlabapp.fontui.core_pythonqt_labs.profiles.' + name)
    qt = NS(QtCore=QtCore, QtGui=legacy_qt.gui)
    monkeypatch.setattr(fly, 'qt', qt)
    monkeypatch.setattr(scripting, 'current_package', lambda *args, **kwargs: None)
    monkeypatch.setattr(sys.modules['fontlab'], 'CurrentFont', lambda: None, raising=False)
    panel = module.build(None)
    legacy_qt.owned.append(panel)
    calls = []
    panel.apply = lambda: calls.append('guarded-apply')
    button = next(button for button in panel.findChildren(QtWidgets.QPushButton) if button.text() in ('Apply', 'Apply Map'))
    button.setEnabled(True)
    button.click()
    assert calls == ['guarded-apply']


def test_dock_local_close_button_uses_replaced_live_callback(legacy_qt, font_host, monkeypatch):  # noqa: F811 - fixtures
    import fly
    from types import SimpleNamespace as NS
    from PySide6 import QtCore, QtWidgets
    from fontlabapp.core import scripting
    from fontlabapp.fontui.core_pythonqt_labs.profiles import unicode_issues_dock as module
    qt = NS(QtCore=QtCore, QtGui=legacy_qt.gui)
    monkeypatch.setattr(fly, 'qt', qt)
    monkeypatch.setattr(scripting, 'current_package', lambda *args, **kwargs: None)
    host = module.build(None)
    legacy_qt.owned.append(host)
    calls, original = [], host.controller.close_owned
    host.controller.close_owned = lambda: calls.append('whole-lab-close') or False
    button = next(button for button in host.findChildren(QtWidgets.QPushButton) if button.text() == 'Close')
    button.click()
    assert calls == ['whole-lab-close']
    host.controller.close_owned = original
    assert host.close() is True
