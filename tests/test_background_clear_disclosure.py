# this_file: tests/test_background_clear_disclosure.py
"""Queue disclosure survives real backend writes and owned panel failures."""
import pytest
import fontlabapp.core.edit_guards as edit_guards
from test_background_clear_native import setup
from test_background_clear_panel import make


@pytest.mark.parametrize("masters", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_queue_disclosed_once_before_history_and_retained_on_failure(monkeypatch, masters, failure, capsys):
    backend, package, glyph, body, mask, aux, log, queue, native = setup(monkeypatch)
    queue.extend([901, 902])
    reads = []
    def read():
        reads.append(tuple(log))
        return tuple(queue)
    native.flGlyph.updatedFgGlyphs = read
    disclosure = {}
    original = body.checkInitHistoryState
    def history(zero):
        assert disclosure['pending_updates'] == (901, 902)
        original(zero)
    body.checkInitHistoryState = history
    source = backend.capture()
    if failure:
        remove = glyph.removeLayer
        def fail(target):
            remove(target)
            raise RuntimeError('after removal')
        glyph.removeLayer = fail
        with pytest.raises(RuntimeError, match='Undo'):
            backend.apply(source, masters, disclosure=disclosure)
    else:
        result = backend.apply(source, masters, disclosure=disclosure)
        assert result['backgrounds'] == 1
        assert result['pending_updates'] == (901, 902)
    assert reads == [()] and queue == [901, 902]
    assert disclosure['pending_note'] == edit_guards.pending_note((901, 902))
    assert log[-1] == ('notify', (10, 1))
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize("masters", [False, True])
def test_noop_resets_disclosure_without_reading_queue(monkeypatch, masters):
    backend, package, glyph, body, mask, aux, log, queue, native = setup(monkeypatch)
    glyph.layers.remove(mask)
    native.flGlyph.updatedFgGlyphs = lambda: pytest.fail('no-op sampled queue')
    disclosure = {'pending_updates': (901,), 'pending_note': 'stale'}
    result = backend.apply(backend.capture(), masters, disclosure=disclosure)
    assert result == {'backgrounds': 0, 'glyphs': 0, 'layers': 0, 'pending_updates': (), 'pending_note': ''}
    assert disclosure == {'pending_updates': (), 'pending_note': ''} and not log


@pytest.mark.parametrize('masters', [False, True])
@pytest.mark.parametrize('failure', ['none', 'partial', 'rescan'])
def test_real_panel_keeps_queue_warning_through_write_and_rescan(monkeypatch, masters, failure, capsys):
    backend, package, glyph, body, mask, aux, log, queue, native = setup(monkeypatch)
    queue.append(901)
    panel, state = make(monkeypatch, masters)
    panel.backend = backend
    panel.refresh()
    if failure == 'partial':
        remove = glyph.removeLayer
        def fail(target):
            remove(target)
            raise RuntimeError('partial removal')
        glyph.removeLayer = fail
    elif failure == 'rescan':
        capture = backend.capture
        def scan(*args, **kwargs):
            if mask not in glyph.layers:
                raise ValueError('rescan failed')
            return capture(*args, **kwargs)
        backend.capture = scan
    try:
        panel.apply_button.click()
        text = panel.status.text()
        assert text.count('FontLab issue 8537') == 1
        assert ('Undo' in text) == (failure != 'none')
        assert (panel.last_result is None) == (failure != 'none')
        assert capsys.readouterr().out == ''
        # A later refresh error must not inherit the previous action's warning.
        backend.capture = lambda: (_ for _ in ()).throw(ValueError('new capture error'))
        panel.refresh()
        assert '8537' not in panel.status.text()
    finally:
        panel.close()


def test_cli_discloses_nonempty_queue_before_removal(monkeypatch, capsys):
    backend, package, glyph, body, mask, aux, log, queue, native = setup(monkeypatch)
    queue.append(901)
    original = glyph.removeLayer
    def remove(target):
        assert '901' in capsys.readouterr().out
        original(target)
    glyph.removeLayer = remove
    backend.apply(backend.capture(), False)


def test_queue_changed_during_preparation_uses_latest_ids(monkeypatch):
    backend, package, glyph, body, mask, aux, log, queue, native = setup(monkeypatch)
    source = backend.capture()
    capture = backend.capture
    def scan(**kwargs):
        result = capture(**kwargs)
        queue.append(901 + len(queue))
        return result
    monkeypatch.setattr(backend, 'capture', scan)
    result = backend.apply(source, False, disclosure={})
    assert result['pending_updates'] == (901, 902)
    assert queue == [901, 902]


def test_early_failure_clears_previous_disclosure(monkeypatch):
    backend, package, glyph, body, mask, aux, log, queue, native = setup(monkeypatch)
    source = backend.capture()
    body.name = 'changed'
    disclosure = {'pending_updates': (901,), 'pending_note': 'stale'}
    with pytest.raises(ValueError, match='stale'):
        backend.apply(source, False, disclosure=disclosure)
    assert disclosure == {'pending_updates': (), 'pending_note': ''}
    assert not log
