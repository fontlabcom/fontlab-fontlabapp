# this_file: tests/test_fontui_ufo_roundtrip.py
"""Owned real UFO storage, fake Qt callbacks, semantic losses and cleanup."""

import importlib
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import _cov_qt as fq
import pytest
from fontlab_fontport.live import RFont
from fontlab_fontport.memory import UFOBackend
from test_fontui_glyph_metrics import composition_env as _composition_env
from ufoLib2 import Font

composition_env = _composition_env


@pytest.fixture
def env(composition_env, monkeypatch):
    monkeypatch.setattr(fq.FakeWidget, 'setWindowFlags', lambda self, flags: None, raising=False)
    monkeypatch.setattr(fq.FakeWidget, 'setWindowTitle', lambda self, title: None, raising=False)
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.ufo_roundtrip_editor', raising=False)
    editor = importlib.import_module('fontlabapp.fontui.ufo_roundtrip_editor')
    module = importlib.import_module('fontlabapp.fontui.ufo_roundtrip')
    yield SimpleNamespace(**vars(composition_env), editor=editor, module=module)
    for owner in tuple(module._HANDLES):
        owner.close()
    sys.modules.pop('fontlabapp.fontui.ufo_roundtrip_editor', None)


def source():
    font = Font()
    font.info.familyName = 'Owned C7'
    font.info.unitsPerEm = 1000
    font.info.openTypeNameSampleText = 'Beyond INFO_FIELDS'
    font.features.text = 'languagesystem DFLT dflt;\n'
    font.lib['preserve'] = {'a': [1, 2]}
    font.groups['public.kern1.A'] = ['A']
    font.kerning['A', 'V'] = -15.5
    a = font.newGlyph('A')
    a.width = 600.25
    a.unicodes = [65]
    a.appendAnchor({'name': 'top', 'x': 12.5, 'y': 700})
    pen = a.getPen()
    pen.moveTo((0, 0))
    pen.lineTo((100, 0))
    pen.lineTo((0, 100))
    pen.closePath()
    font.newGlyph('V').getPen().addComponent('A', (1, 0, 0, 1, 5, 6))
    font.layers.defaultLayer.lib['layerNote'] = 'must report loss'
    font.layers.defaultLayer.color = '1,0,0,1'
    font.layers.newLayer('background').newGlyph('A').width = 500
    font.data['test.bin'] = b'\x00\xffdata'
    font.images['test.png'] = b'\x89PNG\r\n\x1a\nowned'
    return font


def test_inspect_when_default_deadline_then_generous_for_real_fonts(env):
    import inspect as _inspect
    default = _inspect.signature(env.editor.inspect).parameters['seconds'].default
    assert default == env.editor._DEFAULT_DEADLINE_SECONDS >= 60, 'a real native font needs a generous default deadline'


def test_inspect_when_full_ufo_then_complete_losses_and_borrowed_source_untouched(env, monkeypatch):
    model = source()
    before = deepcopy(model)
    backend = UFOBackend(model)
    font = RFont(backend)
    paths, destinations = [], []
    original = env.editor.ExportSession.save
    def save(self, destination):
        paths.append(Path(destination))
        return original(self, destination)
    monkeypatch.setattr(env.editor.ExportSession, 'save', save)
    original_import = env.editor.import_ufo
    def imported(model, factory):
        def capture():
            result = factory()
            destinations.append(result)
            return result
        return original_import(model, capture)
    monkeypatch.setattr(env.editor, 'import_ufo', imported)
    report = env.editor.inspect(font)
    text = str(report)
    assert 'openTypeNameSampleText' in text and 'test.png' in text and 'test.bin' in text
    assert 'layerNote' in text and 'color' in text
    assert report['export_to_reopened'] == []
    assert report['layers_checked'] == {'public.default': 2, 'background': 1}
    assert set(report['families_checked']) == {'info', 'features', 'groups', 'kerning', 'lib', 'defaultLayer', 'layerOrder', 'layers', 'images', 'data'}
    assert report['source_to_imported'] and not report['native_preservation_verified']
    assert all(item.closed for item in destinations)
    assert paths and all(not item.parent.exists() for item in paths)
    assert model == before and not backend.closed


def test_inspect_when_native_like_backend_then_loss_disclosure_without_native_claim(env):
    class NativeLike:
        font_id = 7
        def __init__(self):
            self.delegate = UFOBackend(source())
        def __getattr__(self, name):
            return getattr(self.delegate, name)
    report = env.editor.inspect(RFont(NativeLike()))
    assert report['scope'] == 'Adapter-readable native UFO model only'
    assert report['source_to_export'] is None and report['source_to_imported'] is None
    assert len(report['limitations']) >= 6


@pytest.mark.parametrize('failure', ['missing', 'closed', 'pending', 'cancelled', 'timeout', 'export', 'import', 'changed', 'backend'])
def test_inspect_when_failure_then_no_success_and_owned_temporary_cleanup(env, monkeypatch, failure):
    font = RFont(UFOBackend(source()))
    paths = []
    original_save = env.editor.ExportSession.save
    def save(self, destination):
        paths.append(Path(destination))
        if failure == 'export':
            raise OSError('save refusal')
        result = original_save(self, destination)
        if failure == 'changed':
            font._backend.font['A'].width = 999
        if failure == 'backend':
            font._backend = UFOBackend()
        return result
    monkeypatch.setattr(env.editor.ExportSession, 'save', save)
    kwargs = {}
    if failure == 'missing':
        font = None
    elif failure == 'closed':
        font.close()
    elif failure == 'pending':
        monkeypatch.setattr(font, '_check_pending', lambda: (_ for _ in ()).throw(ValueError('unfinished')))
    elif failure == 'cancelled':
        kwargs['cancelled'] = lambda: True
    elif failure == 'timeout':
        kwargs['seconds'] = -1
    elif failure == 'import':
        def broken(*args):
            raise ValueError('import refused')
        monkeypatch.setattr(env.editor, 'import_ufo', broken)
    with pytest.raises((ValueError, RuntimeError, OSError)):
        env.editor.inspect(font, **kwargs)
    assert all(not path.parent.exists() for path in paths)


def test_differences_when_absent_none_and_nested_values_then_no_truncation(env):
    assert env.editor._differences({'x': None}, {}) == [{'path': "/'x'", 'before': 'None', 'after': '<absent>'}]
    assert env.editor._differences({}, {'x': None})[0]['before'] == '<absent>'
    assert len(env.editor._differences({'x': [1, 2]}, {'x': [1, 3]})) == 1
    assert env.editor._differences({'x': 1}, {'x': 1}) == []


def test_show_when_clicked_then_actual_report_and_close(env):
    model = source()
    before = deepcopy(model)
    font = RFont(UFOBackend(model))
    owner = env.module.show(font, env.parent)
    assert owner.report is None
    owner.inspect_button.clicked.emit()
    assert owner.report and 'source_to_imported' in owner.text.toPlainText()
    assert 'Temporary staging removed' in owner.status.text
    owner.close()
    owner.close()
    assert owner._close_complete and owner not in env.module._HANDLES
    assert not owner.run() and font._backend.font == before and not font._backend.closed


def test_run_when_failure_then_previous_report_cleared(env, monkeypatch):
    owner = env.module.show(RFont(UFOBackend()), env.parent)
    assert owner.run()
    monkeypatch.setattr(env.editor, 'inspect', lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('read failed')))
    assert not owner.run() and owner.report is None and owner.text.toPlainText() == ''
    assert owner.status.text == 'read failed'


def test_run_when_close_during_read_then_fence_and_finish_cleanup(env, monkeypatch):
    owner = env.module.show(RFont(UFOBackend()), env.parent)
    def inspecting(*args, **kwargs):
        assert not owner.run()
        owner.close()
        assert owner.closed and not owner._close_complete
        return {'result': 1}
    monkeypatch.setattr(env.editor, 'inspect', inspecting)
    assert not owner.run()
    assert owner._close_complete and owner.report is None


def test_close_when_disconnect_refuses_then_retain_until_retry(env, monkeypatch):
    owner = env.module.show(RFont(UFOBackend()), env.parent)
    signal, _callback = owner.connections[-1]
    original = signal.disconnect
    monkeypatch.setattr(signal, 'disconnect', lambda callback: False)
    with pytest.raises(RuntimeError, match='disconnect'):
        owner.close()
    assert owner in env.module._HANDLES and owner.font is not None
    monkeypatch.setattr(signal, 'disconnect', original)
    owner.close()
    assert owner not in env.module._HANDLES


def test_show_when_widget_show_fails_then_cleanup(env, monkeypatch):
    original = env.editor.RoundtripEditor.__init__
    def init(self, *args):
        original(self, *args)
        self.widget.show = lambda: (_ for _ in ()).throw(ValueError('show failed'))
    monkeypatch.setattr(env.editor.RoundtripEditor, '__init__', init)
    with pytest.raises(ValueError, match='show failed'):
        env.module.show(RFont(UFOBackend()), env.parent)
    assert not env.module._HANDLES


@pytest.mark.parametrize('run_name', ['ufo_demo', '__main__'])
def test_demo_when_dispatched_then_real_owned_inspector(env, monkeypatch, run_name):
    import runpy

    from fontlab_fontport import world

    from fontlabapp.qt import safe

    font = RFont(UFOBackend(source()))
    calls = []
    class World:
        def CurrentFont(self):
            calls.append('current')
            return font
    monkeypatch.setattr(world, 'FontWorld', World)
    monkeypatch.setattr(safe, 'main_window', lambda *args: env.parent)
    monkeypatch.setitem(sys.modules, 'fontlab', SimpleNamespace())
    path = Path(__file__).resolve().parents[1] / 'Scripts/Font Editors/UFO Roundtrip Inspector Demo.py'
    namespace = runpy.run_path(str(path), run_name=run_name)
    if run_name != '__main__':
        assert calls == []
        owner = namespace['main']()
    else:
        owner = env.module._HANDLES[-1]
    assert calls == ['current'] and owner.font is font
    owner.inspect_button.clicked.emit()
    assert owner.report and not font._backend.closed
    owner.close()


def test_snapshot_when_component_and_image_have_real_transforms_then_plain_tuples_and_diffable(env):
    from fontTools.misc.transform import Transform
    from ufoLib2.objects import Image

    font = source()
    font.layers.defaultLayer['A'].image = Image(fileName='test.png', transformation=Transform(1, 0, 0, 1, 7, 8))
    snap = env.editor._snapshot(font, lambda: None)
    glyphs = snap['layers'][font.layers.defaultLayer.name]['glyphs']
    assert glyphs['V']['components'][0]['transformation'] == (1, 0, 0, 1, 5, 6)
    assert glyphs['A']['_image']['transformation'] == (1, 0, 0, 1, 7, 8)
    assert env.editor._differences(snap, deepcopy(snap)) == []


def test_differences_when_image_transform_changes_then_one_row_with_plain_tuples(env):
    from fontTools.misc.transform import Transform
    from ufoLib2.objects import Image

    before, after = source(), source()
    before.layers.defaultLayer['A'].image = Image(fileName='test.png', transformation=Transform(1, 0, 0, 1, 7, 8))
    after.layers.defaultLayer['A'].image = Image(fileName='test.png', transformation=Transform(1, 0, 0, 1, 9, 8))
    rows = env.editor._differences(env.editor._snapshot(before, lambda: None), env.editor._snapshot(after, lambda: None))
    assert len(rows) == 1
    assert rows[0]['before'] == '(1, 0, 0, 1, 7, 8)' and rows[0]['after'] == '(1, 0, 0, 1, 9, 8)'


def test_snapshot_when_empty_or_padded_glyph_note_then_equals_what_glif_stores(env):
    """GLIF stores no empty <note> and strips lines, so '' / None / padded text are one value."""
    empty, absent, padded, real = source(), source(), source(), source()
    empty.layers.defaultLayer['A'].note = ''
    padded.layers.defaultLayer['A'].note = '  hello \n\n world  '
    real.layers.defaultLayer['A'].note = 'hello\nworld'

    def rows(left, right):
        return env.editor._differences(env.editor._snapshot(left, lambda: None), env.editor._snapshot(right, lambda: None))

    assert rows(empty, absent) == []
    assert rows(padded, real) == []
    assert len(rows(real, absent)) == 1
