# this_file: tests/test_background_clear_interruptions.py
"""Interruptions retain identity and cannot skip attempted-batch finalization."""
from time import monotonic
from types import SimpleNamespace as S

import pytest
import fontlabapp.masters.background.clear.native as api


@pytest.mark.parametrize('phase', ['remove', 'pre-date', 'notify', 'post-date'])
@pytest.mark.parametrize('kind', [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_interruption_runs_remaining_cleanup_and_retains_other_errors(phase, kind):
    log = []
    interruption = kind('stop here')
    ordinary = RuntimeError('other failure')
    class Glyph:
        def __init__(self, identity):
            self.id = identity
            self.layers = [S(id=identity * 10)]
            self.sets = 0
        def removeLayer(self, mask):
            log.append(('remove', self.id))
            self.layers.remove(mask)
            if phase == 'remove':
                raise interruption
        @property
        def lastModified(self):
            return 'before'
        @lastModified.setter
        def lastModified(self, value):
            self.sets += 1
            event = 'pre-date' if self.sets == 1 else 'post-date'
            log.append((event, self.id))
            if self.id == 1 and event == phase:
                raise interruption
            if self.id == 2 and event == 'post-date':
                raise ordinary
    one, two = Glyph(1), Glyph(2)
    def notify(*args):
        log.append(('notify',))
        if phase == 'notify':
            raise interruption
    with pytest.raises(kind) as caught:
        api.Backend._remove([(one, one.layers[0]), (two, two.layers[0])], {},
                            {1: one, 2: two}, [one, two], S(notifyChangesApplied=notify),
                            'stamp', monotonic() + 2)
    assert caught.value is interruption
    assert log[-5:] == [('pre-date', 1), ('pre-date', 2), ('notify',), ('post-date', 1), ('post-date', 2)]
    notes = '\n'.join(interruption.__notes__)
    assert 'RuntimeError' in notes and 'other failure' in notes and 'Undo' in notes
    assert len([item for item in log if item[0] == 'remove']) == (1 if phase == 'remove' else 2)
    assert not one.layers


def test_interruption_before_first_attempt_does_not_notify_or_suggest_undo(monkeypatch):
    interruption = KeyboardInterrupt('prewrite')
    calls = []
    def check(deadline):
        calls.append('check')
        if len(calls) == 2:
            raise interruption
    monkeypatch.setattr(api, 'check', check)
    owner = S(removeLayer=lambda mask: calls.append('remove'))
    with pytest.raises(KeyboardInterrupt) as caught:
        api.Backend._remove([(owner, S(id=11))], {}, {1: owner}, [],
                            S(notifyChangesApplied=lambda *args: calls.append('notify')),
                            'stamp', monotonic() + 2, {1: ()})
    assert caught.value is interruption and calls == ['check', 'check']
    assert not getattr(interruption, '__notes__', [])


@pytest.mark.parametrize('stage,confirmed', [('remove-before', 0), ('membership', 0), ('order', 1), ('fallback', 1)])
def test_interrupted_readback_finalizes_conservative_counts(monkeypatch, stage, confirmed):
    interruption = KeyboardInterrupt(stage)
    log = []
    mask = S(id=11)
    owner = S(id=1, layers=[mask], lastModified='before')
    def remove(target):
        if stage == 'remove-before':
            raise interruption
        owner.layers.remove(target)
    owner.removeLayer = remove
    reads = []
    def ids(glyph, deadline):
        reads.append(1)
        if (stage == 'membership' and len(reads) == 1) or (stage == 'order' and len(reads) == 2):
            raise interruption
        return ()
    monkeypatch.setattr(api, 'layer_ids', ids)
    def background(create):
        raise interruption
    foreground = S(getMaskLayer=background)
    with pytest.raises(KeyboardInterrupt) as caught:
        api.Backend._remove([(owner, mask)], {10: foreground}, {1: owner}, [owner],
                            S(notifyChangesApplied=lambda *args: log.append('notify')),
                            'stamp', monotonic() + 2, {1: ()})
    assert caught.value is interruption and log == ['notify']
    assert owner.lastModified == 'stamp'
    assert f'{confirmed} confirmed removals' in interruption.__notes__[-1]
    assert (mask in owner.layers) == (stage == 'remove-before')


def test_first_interruption_survives_later_cleanup_interruption():
    first, second = KeyboardInterrupt('first'), SystemExit('second')
    mask = S(id=11)
    owner = S(id=1, layers=[mask], lastModified='before')
    def remove(target):
        raise first
    def notify(*args):
        raise second
    owner.removeLayer = remove
    with pytest.raises(KeyboardInterrupt) as caught:
        api.Backend._remove([(owner, mask)], {}, {1: owner}, [owner],
                            S(notifyChangesApplied=notify), 'stamp', monotonic() + 2, {1: ()})
    assert caught.value is first
    assert any('SystemExit: second' in note for note in first.__notes__)
    assert owner.lastModified == 'stamp'
