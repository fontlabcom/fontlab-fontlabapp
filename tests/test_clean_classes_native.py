# this_file: tests/test_clean_classes_native.py
"""Actual class backend contract, scalar-only native names and complete fences."""

from types import SimpleNamespace as NS
import pytest
import fontlabapp.features.classes.native as native


class Backend:
    def __init__(self):
        self.token = "font"
        self.records = [NS(name="class", glyphs=("A", "gone"))]
        self.events = []

    def current_font_id(self):
        return self.token

    def classes(self, token):
        assert token == "font"
        return tuple(self.records)

    def begin_undo(self, title):
        self.events.append(("begin", title))

    def set_class(self, token, name, members):
        self.events.append(("write", token, name, members))

    def end_undo(self):
        self.events.append("end")


@pytest.fixture
def owned(monkeypatch):
    backend = Backend()
    font = NS(id=17, glyphs=[NS(name="A"), NS(name="B")])
    monkeypatch.setattr(native, "_native", lambda name: NS(CurrentFont=lambda: font))
    return native.Bridge(backend), backend, font


def test_native_uses_actual_feature_classes_and_direct_scalar_name_scan(owned):
    bridge, backend, font = owned
    facts = bridge.capture()
    assert (
        facts.names == ("A", "B")
        and facts.classes == (("class", "A gone"),)
        and facts.context == ("font", 17)
    )
    bridge.begin()
    bridge.write("class", ("A",))
    bridge.end()
    assert backend.events == [
        ("begin", "Clean Classes"),
        ("write", "font", "class", ("A",)),
        "end",
    ]


def test_no_font_or_switched_font_refuses_and_never_writes(owned):
    bridge, backend, font = owned
    bridge.capture()
    backend.token = None
    with pytest.raises(ValueError, match="Open a font"):
        bridge.capture()
    backend.token = "another"
    with pytest.raises(ValueError, match="original font"):
        bridge.capture()
    assert backend.events == []


def test_poison_deadline_thread_drift_and_unequal_complete_passes(owned, monkeypatch):
    bridge, backend, font = owned
    bridge.poisoned = True
    with pytest.raises(RuntimeError, match="reopen"):
        bridge.capture()
    bridge.poisoned = False
    with pytest.raises(TimeoutError):
        bridge.read(0)
    monkeypatch.setattr(native, "current_thread", lambda: object())
    with pytest.raises(RuntimeError, match="UI thread"):
        bridge.read(float("inf"))
    monkeypatch.undo()


def test_names_or_classes_changing_between_passes_refuse(owned, monkeypatch):
    bridge, backend, font = owned
    old = bridge.read
    count = 0

    def read(deadline):
        nonlocal count
        count += 1
        if count == 2:
            font.glyphs.append(NS(name="changed"))
        return old(deadline)

    monkeypatch.setattr(bridge, "read", read)
    with pytest.raises(ValueError, match="changed"):
        bridge.capture()


def test_bridge_has_no_implicit_external_dependency():
    sentinel = object()
    assert native.Bridge(sentinel).backend is sentinel


def test_font_switch_before_each_class_write_refuses(owned):
    bridge, backend, font = owned
    bridge.capture()
    backend.token = "other"
    with pytest.raises(ValueError, match="before a class write"):
        bridge.write("class", ("A",))
    assert backend.events == []
