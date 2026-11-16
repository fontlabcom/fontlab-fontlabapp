# this_file: tests/test_fontui_kerning_proof.py
"""Actual borrowed RFont kerning workflow and complete owned-font preservation."""

from copy import deepcopy
import base64
import importlib
import pickle
from types import SimpleNamespace

import pytest
import _cov_qt as fq
import test_fontui_glyph_metrics as _fixtures

composition_env = _fixtures.composition_env

PAIR = ("public.kern1.A", "public.kern2.V")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==")


@pytest.fixture
def real_fonts(composition_env, monkeypatch):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend

    from ufoLib2.objects import Anchor, Guideline, Image

    source = fq.ufo_font()
    source.info.familyName, source.info.styleName = "Owned kerning proof", "Regular"
    source.lib["owned"] = {"nested": [True, 1, "preserve"]}
    source.features.text = "feature liga { sub A V by A; } liga;"
    source.images["owned.png"] = PNG
    source.data["owned/payload.bin"] = b"owned\0\xff"
    glyph = source["A"]
    glyph.note, glyph.lib["owned"] = "Preserve note", [1, 2, 3]
    glyph.image = Image("owned.png", (1.25, .2, -.1, .9, 13.5, -17.75))
    glyph.anchors = [Anchor(100, 700, "top", identifier="owned-anchor")]
    glyph.guidelines = [Guideline(25, 0, 90, "owned-guide")]
    source.newGlyph("B").width = 420
    glyph.getPointPen().addComponent("B", (1, 0, 0, 1, 10, 20))
    source.layers.newLayer("owned.background").newGlyph("untouched").width = 333
    source.kerning[("B", "V")] = 7
    source.glyphOrder = ["A", "B", "V"]
    backends = [UFOBackend(source), UFOBackend(deepcopy(source))]
    fonts = [RFont(backend) for backend in backends]
    expected = [deepcopy(backend.font) for backend in backends]
    writes, closes, owners, forbidden = [], [], [], []

    def refuse(name):
        def unexpected(*args, **kwargs):
            forbidden.append(name)
            raise AssertionError("Unexpected borrowed-font mutator: " + name)
        return unexpected

    for backend in backends:
        setter = backend.set_kerning

        def apply(values, *, _setter=setter, _backend=backend, **kwargs):
            writes.append((_backend, dict(values)))
            return _setter(values, **kwargs)

        monkeypatch.setattr(backend, "set_kerning", apply)
        monkeypatch.setattr(backend, "close", lambda: closes.append(True))
        for name in ("write_glyph", "edit_image", "new_glyph", "remove_glyph",
                     "rename_glyph", "new_layer", "remove_layer", "rename_layer",
                     "set_info", "set_info_many", "set_groups", "set_lib",
                     "set_features", "set_feature_blocks", "save_options", "save"):
            monkeypatch.setattr(backend, name, refuse(name))
    state = SimpleNamespace(env=composition_env, fonts=fonts, backends=backends,
                            expected=expected, writes=writes, closes=closes, owners=owners)
    yield state
    for owner in reversed(owners):
        if hasattr(owner, "release"):
            assert owner.release()
        else:
            owner.close()
            assert owner._close_complete and owner.preview._close_complete
    assert not closes, "UI must never close borrowed fonts"
    assert not forbidden, "UI attempted an unrelated backend mutation"
    for backend, before in zip(backends, expected):
        assert backend.font == before, "Complete font/resources changed unexpectedly"
        assert pickle.dumps(backend.font) == pickle.dumps(before)
        assert backend.font.images["owned.png"] == PNG and not backend.closed


def editor_for(state):
    module = importlib.import_module("fontlabapp.fontui.kerning")
    editor = module.KerningEditor(state.fonts[0], state.env.parent)
    state.owners.append(editor)
    editor.pair_list.setCurrentRow(editor.rows.index(PAIR))
    assert [(g.name, g.x) for g in editor.preview.run.glyphs] == [("A", 0), ("V", 520)]
    editor.preview.select_key(state.env.qt.QtCore.Qt.Key_Home)
    return editor


@pytest.mark.parametrize("route", ["changed", "empty", "read_error", "stale_error"])
def test_refresh_when_real_read_pending_then_clear_before_read_and_truthful_final(real_fonts, monkeypatch, route):
    from fontlab_fontport.errors import StaleObjectError

    state = real_fonts
    editor = editor_for(state)
    prior = editor.preview.run
    backend = state.backends[0]
    if route == "changed":
        backend.font.kerning[PAIR] = -120
    elif route == "empty":
        backend.font.kerning.clear()
    state.expected[0] = deepcopy(backend.font)
    original = backend.get_kerning
    reads = []
    error = OSError("owned read failure") if route == "read_error" else StaleObjectError("owned stale read")

    def read():
        child = editor.preview
        reads.append((child.run, dict(child.outlines), child.selected_index))
        if route.endswith("error"):
            raise error
        return original()

    monkeypatch.setattr(backend, "get_kerning", read)
    assert editor.refresh() is (not route.endswith("error"))
    if route.endswith("error"):
        assert editor.preview.run is None and not editor.preview.outlines
        assert editor.preview.selected_index is None and not editor.editable
        assert editor.diagnostic.text == editor.preview.diagnostic.text == str(error)
    else:
        assert editor.preview.run is not prior
        assert [(g.name, g.x) for g in editor.preview.run.glyphs] == [("A", 0), ("V", 480 if route == "changed" else 600)]
        assert editor.preview.selected_index == 0
    assert reads and reads[0] == (None, {}, None), "Old proof survives the first fallible model read"
    assert not state.writes


@pytest.mark.parametrize("first", ["left_control", "right_control"])
def test_empty_pair_when_ordinary_signals_then_independent_proof_survives_reload(real_fonts, first):
    editor = editor_for(real_fonts)
    getattr(editor, first).setText("")
    getattr(editor, "right_control" if first == "left_control" else "left_control").setText("")
    assert editor.preview.run is None and not editor.preview.outlines
    editor.preview.text_control.setText("/V /A")
    editor.reload_button.clicked.emit()
    assert [(g.name, g.x) for g in editor.preview.run.glyphs] == [("V", 0), ("A", 600)]
    assert not real_fonts.writes


@pytest.mark.parametrize("independent", [False, True])
def test_inspect_when_both_fields_cleared_without_signals_then_no_linked_success_claim(real_fonts, independent):
    editor = editor_for(real_fonts)
    if independent:
        editor.preview.text_control.setText("/V /A")
    prior = editor.preview.run
    for control in (editor.left_control, editor.right_control):
        blocked = control.blockSignals(True)
        control.setText("")
        control.blockSignals(blocked)
    editor.inspect()
    assert editor.diagnostic.text == importlib.import_module("fontlabapp.fontui.kerning").EMPTY_PAIR_TEXT
    assert not editor.delete_button.enabled
    assert editor.preview.run is prior, "Valid proof text need not be erased by an empty pair prompt"
    assert [(g.name, g.x) for g in prior.glyphs] == ([("V", 0), ("A", 600)] if independent else [("A", 0), ("V", 520)])
    real_fonts.backends[0].font.kerning[PAIR] = -120
    real_fonts.expected[0].kerning[PAIR] = -120
    assert editor.refresh()
    assert editor.preview.run is not prior
    assert (editor.left_control.text, editor.right_control.text) == PAIR
    assert [(g.name, g.x) for g in editor.preview.run.glyphs] == [("A", 0), ("V", 480)]
    assert not real_fonts.writes


def test_show_when_real_font_then_owned_integrated_editor(real_fonts):
    module = importlib.import_module("fontlabapp.fontui.kerning_proof")
    owner = module.show(real_fonts.fonts[0], real_fonts.env.parent)
    real_fonts.owners.append(owner)
    assert owner.editor.font is real_fonts.fonts[0]
    assert owner.editor.preview.font is real_fonts.fonts[0]
    assert owner in module._HANDLES


def window_for(state):
    module = importlib.import_module("fontlabapp.fontui.kerning_proof")
    owner = module.show(state.fonts[0], state.env.parent)
    state.owners.append(owner)
    return owner


def type_pair(editor, left="A", right="V", value="0"):
    editor.left_control.setText(left)
    editor.right_control.setText(right)
    editor.value_control.setText(value)


@pytest.mark.parametrize("value", ["-40", "0", "-12.5"])
def test_apply_when_real_value_then_exact_readback_and_one_callback(real_fonts, value):
    owner = window_for(real_fonts)
    editor = owner.editor
    callbacks = []
    editor.on_apply = lambda font, pairs: callbacks.append((font, pairs))
    type_pair(editor, value=value)
    editor.apply_button.clicked.emit()
    real_fonts.expected[0].kerning[("A", "V")] = float(value)
    assert dict(editor.font.kerning) == dict(real_fonts.expected[0].kerning)
    assert callbacks == [(real_fonts.fonts[0], dict(real_fonts.expected[0].kerning))]
    assert len(real_fonts.writes) == 1 and "effective: " + value in editor.diagnostic.text
    assert editor.preview.run.glyphs[1].x == 600 + float(value)
    editor.apply_button.clicked.emit()
    assert len(real_fonts.writes) == len(callbacks) == 1
    editor.delete_button.clicked.emit()
    del real_fonts.expected[0].kerning[("A", "V")]
    assert len(real_fonts.writes) == len(callbacks) == 2
    assert "effective: -80" in editor.diagnostic.text
    assert editor.preview.run.glyphs[1].x == 520
    editor.delete_button.clicked.emit()
    assert len(real_fonts.writes) == len(callbacks) == 2


@pytest.mark.parametrize("left,right,value", [
    ("A", "V", ""), ("A", "V", "NaN"), ("A", "V", "Inf"),
    ("A", "V", "1e999"), ("A", "V", "words"), ("", "V", "1"),
    ("missing", "V", "1"), ("public.kern2.V", "V", "1"),
])
def test_apply_when_invalid_then_complete_fonts_preserved(real_fonts, left, right, value):
    editor = window_for(real_fonts).editor
    callbacks = []
    editor.on_apply = lambda *args: callbacks.append(args)
    type_pair(editor, left, right, value)
    assert editor.edit("apply") is False
    assert editor.diagnostic.text and not real_fonts.writes and not callbacks


@pytest.mark.parametrize("failure", ["refuse", "ignore", "partial"])
def test_apply_when_backend_fails_then_truthful_state_and_no_callback(real_fonts, monkeypatch, failure):
    editor = window_for(real_fonts).editor
    callbacks = []
    editor.on_apply = lambda *args: callbacks.append(args)
    backend = real_fonts.backends[0]

    def write(values, **kwargs):
        if failure == "partial":
            backend.font.kerning[("A", "V")] = 3
            real_fonts.expected[0].kerning[("A", "V")] = 3
        if failure != "ignore":
            raise OSError("owned write failure")

    monkeypatch.setattr(backend, "set_kerning", write)
    type_pair(editor, value="-10")
    assert editor.edit("apply") is False
    assert not callbacks
    assert ("readback differs" if failure == "ignore" else "owned write failure") in editor.diagnostic.text


def test_callback_when_raises_after_real_write_then_success_not_replayed(real_fonts):
    editor = window_for(real_fonts).editor
    calls = []

    def fail(*args):
        calls.append(args)
        raise RuntimeError("owned callback failure")

    editor.on_apply = fail
    type_pair(editor, value="5")
    assert editor.edit("apply") is True
    real_fonts.expected[0].kerning[("A", "V")] = 5.0
    assert len(calls) == len(real_fonts.writes) == 1
    assert "Applied kerning; refresh callback failed" in editor.diagnostic.text


def test_close_when_accepted_callback_finishes_window_then_fenced_and_deferred(real_fonts):
    owner = window_for(real_fonts)
    editor, child = owner.editor, owner.editor.preview
    observed = []

    def close(*args):
        owner._finished()
        observed.append((editor.closed, child.closed, editor.widget.deleted, child.widget.deleted))
        editor.apply_button.clicked.emit()

    editor.on_apply = close
    type_pair(editor, value="5")
    editor.apply_button.clicked.emit()
    real_fonts.expected[0].kerning[("A", "V")] = 5.0
    assert observed == [(True, True, False, False)]
    assert len(real_fonts.writes) == 1
    while real_fonts.env.queue:
        real_fonts.env.queue.pop(0)()
    assert owner._released and editor._close_complete and child._close_complete


@pytest.mark.parametrize("target", ["none", "empty"])
def test_show_when_no_pairs_then_none_distinguished_from_empty(real_fonts, target):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend
    from ufoLib2 import Font

    font = None if target == "none" else RFont(UFOBackend(Font()))
    module = importlib.import_module("fontlabapp.fontui.kerning_proof")
    owner = module.show(font, real_fonts.env.parent)
    real_fonts.owners.append(owner)
    assert owner.editor.font is font and owner.editor.preview.font is font
    assert not owner.editor.rows
    assert owner.editor.editable is (target == "empty")


def test_show_when_host_current_changes_then_explicit_target_is_retained(real_fonts):
    from fontlab_fontport.world import FontWorld

    class Host:
        active = 1

        def font_ids(self):
            return [1, 2]

        def current_font_id(self):
            return self.active

        def backend(self, identifier, *, owned):
            assert not owned
            return real_fonts.backends[identifier - 1]

    host = Host()
    world = FontWorld(host)
    target, other = world.AllFonts()
    host.active = 2
    assert world.CurrentFont() is other
    module = importlib.import_module("fontlabapp.fontui.kerning_proof")
    owner = module.show(target, real_fonts.env.parent)
    real_fonts.owners.append(owner)
    assert owner.editor.font is owner.editor.preview.font is target
    assert owner.editor.refresh()
    assert owner.editor.font is target and target is not world.CurrentFont()
    real_fonts.backends[0].closed = True
    try:
        assert owner.editor.refresh() is False
        assert owner.editor.font is target and owner.editor.preview.run is None
    finally:
        real_fonts.backends[0].closed = False


@pytest.mark.parametrize("stage", ["hide", "deleteLater", "ack"])
def test_release_when_child_refuses_then_retained_until_retry(real_fonts, monkeypatch, stage):
    owner = window_for(real_fonts)
    child = owner.editor.preview
    target, name = (child, "close") if stage == "ack" else (child.widget, stage)
    original = getattr(target, name)
    monkeypatch.setattr(target, name, lambda: False)
    assert owner.release() is False
    assert not owner._released and owner._stranded[0] is child
    monkeypatch.setattr(target, name, original)
    assert owner.release() and child._close_complete


def test_release_when_busy_or_destroyed_then_deferred_and_idempotent(real_fonts):
    owner = window_for(real_fonts)
    child = owner.editor.preview
    owner._busy = 1
    assert owner.release() is False and not child.widget.deleted
    owner._busy = 0
    owner._destroyed()
    while real_fonts.env.queue:
        real_fonts.env.queue.pop(0)()
    assert owner._released and child._close_complete and owner.release()


@pytest.mark.parametrize("returned", [None, False, 0])
def test_release_when_child_acknowledges_then_return_truthiness_is_irrelevant(real_fonts, monkeypatch, returned):
    owner = window_for(real_fonts)
    child = owner.editor.preview
    close = child.close

    def acknowledged():
        close()
        return returned

    monkeypatch.setattr(child, "close", acknowledged)
    assert owner.release() and child._close_complete


def test_release_when_disconnect_refuses_then_same_owner_retries(real_fonts, monkeypatch):
    owner = window_for(real_fonts)
    child = owner.editor.preview
    signal, _ = next(record for record in child.connections if record is not child._own_observer and record is not child._parent_observer)
    disconnect = signal.disconnect
    monkeypatch.setattr(signal, "disconnect", lambda callback: False)
    assert owner.release() is False and owner._stranded[0] is child
    monkeypatch.setattr(signal, "disconnect", disconnect)
    assert owner.release() and child._close_complete


def test_show_when_target_label_fails_then_visible_target_diagnostic(real_fonts, monkeypatch):
    from fontlabapp.fontui.model import FontListState

    def fail(font):
        raise ValueError("owned metadata failure")

    monkeypatch.setattr(FontListState, "label", fail)
    owner = window_for(real_fonts)
    assert "Target unavailable: owned metadata failure" == owner.target.text


@pytest.mark.parametrize("error_type", [KeyboardInterrupt, SystemExit])
def test_constructor_when_cleanup_interrupted_then_original_and_retry_handle_survive(real_fonts, monkeypatch, error_type):
    module = importlib.import_module("fontlabapp.fontui.kerning_proof")
    original = module.KerningProof.build
    error = ValueError("owned build failure")
    retained = []

    def build(self, content):
        original(self, content)
        retained.append((self, self.editor.preview.close))

        def interrupt():
            raise error_type("owned cleanup interrupt")

        monkeypatch.setattr(self.editor.preview, "close", interrupt)
        raise error

    monkeypatch.setattr(module.KerningProof, "build", build)
    with pytest.raises(BaseException) as caught:
        module.show(real_fonts.fonts[0], real_fonts.env.parent)
    owner, close = retained[0]
    real_fonts.owners.append(owner)
    assert owner in module._HANDLES and not owner._released
    assert caught.value is error or isinstance(caught.value, BaseExceptionGroup)
    assert any("cleanup was interrupted" in note for note in caught.value.__notes__)
    monkeypatch.setattr(owner.editor.preview, "close", close)
    assert owner.release()


@pytest.mark.parametrize("role", ["editor", "sequence", "dialog"])
@pytest.mark.parametrize("refuse", [False, True])
def test_constructor_when_actual_partial_owner_then_original_error_and_retry(real_fonts, monkeypatch, role, refuse):
    module = importlib.import_module("fontlabapp.fontui.kerning_proof")
    cls = (importlib.import_module("fontlabapp.fontui.kerning").KerningEditor
           if role == "editor" else importlib.import_module("fontlabapp.fontui.sequence").Sequence)
    captured, restores = [], []
    error = ValueError("owned construction failure")
    if role == "dialog":
        original = module.KerningProof.build

        def failed(self, content):
            original(self, content)
            captured.append(self.editor)
            if refuse:
                target = self.editor.preview.widget
                restores.append((target, target.hide))
                monkeypatch.setattr(target, "hide", lambda: False)
            raise error

        monkeypatch.setattr(module.KerningProof, "build", failed)
    else:
        original = cls.__init__

        def failed(self, *args, **kwargs):
            original(self, *args, **kwargs)
            captured.append(self)
            if refuse:
                restores.append((self.widget, self.widget.hide))
                monkeypatch.setattr(self.widget, "hide", lambda: False)
            raise error

        monkeypatch.setattr(cls, "__init__", failed)
    with pytest.raises(BaseException) as caught:
        module.show(real_fonts.fonts[0], real_fonts.env.parent)

    def contains(failure):
        return failure is error or isinstance(failure, BaseExceptionGroup) and any(contains(e) for e in failure.exceptions)

    assert contains(caught.value) and captured
    if refuse:
        assert module._HANDLES
        owner = module._HANDLES[-1]
        real_fonts.owners.append(owner)
        assert not owner._released
        for target, hide in restores:
            monkeypatch.setattr(target, "hide", hide)
        assert owner.release()
    assert all(child._close_complete for child in captured)


def test_show_when_parent_omitted_then_existing_native_parent_route(real_fonts, monkeypatch):
    import fontlabapp
    from fontlabapp.qt import safe

    module = importlib.import_module("fontlabapp.fontui.kerning_proof")
    monkeypatch.setattr(fontlabapp, "_native", lambda name: real_fonts.env.qt if name == "PythonQt" else object())
    monkeypatch.setattr(safe, "main_window", lambda host, qt: real_fonts.env.parent)
    owner = module.show(real_fonts.fonts[0])
    real_fonts.owners.append(owner)
    assert owner.editor.font is real_fonts.fonts[0]


def test_cold_import_when_optional_providers_blocked_then_inert():
    import os
    import subprocess
    import sys

    code = '''import sys
class Block:
    def find_spec(self, name, *args):
        if name.split('.')[0] in ('PythonQt', 'fontlab', 'fontlab_fontport', 'fontgate'):
            raise AssertionError('cold import requested ' + name)
sys.meta_path.insert(0, Block())
import fontlabapp.fontui.kerning_proof as module
assert module.__all__ == ('show',) and module._HANDLES == []
'''
    env = {k: v for k, v in os.environ.items() if k not in ("COVERAGE_PROCESS_CONFIG", "COVERAGE_PROCESS_START")}
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("boundary", ["scope", "child"])
@pytest.mark.parametrize("failure", ["refusal", KeyboardInterrupt, SystemExit])
def test_release_when_teardown_fails_then_real_actions_are_fenced_until_retry(real_fonts, monkeypatch, boundary, failure):
    owner = window_for(real_fonts)
    editor, child = owner.editor, owner.editor.preview
    type_pair(editor, left=PAIR[0], right=PAIR[1], value="-25")
    callbacks, updates = [], []
    editor.on_apply = lambda *args: callbacks.append(args)
    child.on_update = lambda *args: updates.append(args)
    stale_apply = next(callback for signal, callback in editor.connections
                       if signal is editor.apply_button.clicked)
    target, name = (owner.scope, "finish") if boundary == "scope" else (child.widget, "hide")
    original = getattr(target, name)

    def refuse():
        if failure == "refusal":
            return False
        raise failure("owned teardown interruption")

    monkeypatch.setattr(target, name, refuse)
    try:
        if failure == "refusal":
            assert owner.release() is False
        else:
            with pytest.raises(failure, match="owned teardown interruption"):
                owner.release()
        assert not owner._released and owner in importlib.import_module("fontlabapp.fontui.kerning_proof")._HANDLES
        editor.apply_button.clicked.emit()
        editor.delete_button.clicked.emit()
        stale_apply()
        direct = (editor.edit("apply"), editor.edit("delete"))
        child.refresh()
        child._notify_update()
        assert not real_fonts.writes, "Teardown has begun: no subsequent real backend write is permitted"
        assert not callbacks and not updates
        assert editor.closed and child.closed and editor.on_apply is None
        assert direct == (False, False)
    finally:
        monkeypatch.setattr(target, name, original)
        assert owner.release()
    assert editor._close_complete and child._close_complete and owner._released
    assert owner not in importlib.import_module("fontlabapp.fontui.kerning_proof")._HANDLES


def test_refresh_when_real_update_clears_pair_then_one_layout_read_pass_and_publication(real_fonts, monkeypatch):
    editor = editor_for(real_fonts)
    child = editor.preview
    module = importlib.import_module("fontlabapp.fontui.sequence")
    layout = module.layout_names
    get_kerning = real_fonts.backends[0].get_kerning
    layouts, reads, publications = [], [], []

    def measured_layout(*args, **kwargs):
        layouts.append(True)
        return layout(*args, **kwargs)

    def measured_read():
        reads.append(True)
        return get_kerning()

    monkeypatch.setattr(module, "layout_names", measured_layout)
    monkeypatch.setattr(real_fonts.backends[0], "get_kerning", measured_read)
    assert editor.refresh()
    baseline_reads = len(reads)
    assert len(layouts) == 1 and baseline_reads > 0
    layouts.clear()
    reads.clear()

    def clear_pair(sequence):
        publications.append(sequence.run)
        if len(publications) == 1:
            for control in (editor.left_control, editor.right_control):
                blocked = control.blockSignals(True)
                control.setText("")
                control.blockSignals(blocked)

    child.on_update = clear_pair
    assert editor.refresh()
    assert len(publications) == 1, "inspect already published the actual fresh proof"
    assert len(layouts) == 1 and len(reads) == baseline_reads
    assert publications[0] is child.run
    assert [(g.name, g.x) for g in child.run.glyphs] == [("A", 0), ("V", 520)]
    assert not editor.left_control.text and not editor.right_control.text
    assert not real_fonts.writes
