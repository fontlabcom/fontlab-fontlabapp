# this_file: tests/test_layer_navigation.py
from types import SimpleNamespace as NS

import fontlabapp.masters.layers.navigation.model as nav


class Backend:
    def __init__(self):
        self.state = NS(layer="a", layers=(("a", "A"), ("b", "B")), index=2, token=(1,))
        self.calls = []

    def capture(self):
        return self.state

    def replace(self, before, target):
        self.calls.append((before.layer, target))
        self.state = NS(layer=target, layers=before.layers, index=2, token=(2,))

    def verify(self, before, target):
        assert self.state.layer == target


def test_public_pair_repeat_inverse(monkeypatch):
    backend = Backend()
    monkeypatch.setattr(nav, "_backend", lambda: backend)
    assert nav.next_layer().after_layer == "b"
    assert nav.previous_layer().after_layer == "a"
    assert backend.calls == [("a", "b"), ("b", "a")]


def test_single_layer_no_write(monkeypatch):
    backend = Backend()
    backend.state.layers = (("a", "A"),)
    monkeypatch.setattr(nav, "_backend", lambda: backend)
    assert nav.next_layer().status == "unchanged"
    assert not backend.calls


def test_capture_refuses(monkeypatch):
    def missing():
        raise ValueError("No active tab")

    monkeypatch.setattr(nav, "_backend", missing)
    assert nav.next_layer().status == "refused"


def test_write_failure_is_explicit(monkeypatch):
    backend = Backend()

    def fail(*args):
        raise RuntimeError("may have written")

    backend.replace = fail
    monkeypatch.setattr(nav, "_backend", lambda: backend)
    result = nav.next_layer()
    assert result.status == "failed"
    assert "possibly partial" in result.reason


def test_stale_source_refuses(monkeypatch):
    backend = Backend()
    snapshots = [backend.state, NS(token=(99,))]
    backend.capture = lambda: snapshots.pop(0)
    monkeypatch.setattr(nav, "_backend", lambda: backend)
    assert nav.next_layer().status == "refused"
    assert not backend.calls
