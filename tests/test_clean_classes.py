# this_file: tests/test_clean_classes.py
"""Original five-line writer semantics and complete preflight/failure ordering."""

from types import SimpleNamespace as NS
import pytest
from fontlabapp.features.classes.model import Snapshot, changes, apply, render


@pytest.mark.parametrize(
    "code,names,expected",
    [
        (" A\tB\n", ("A", "B"), None),
        ("", (), None),
        (" A missing\tA\nB ", ("A", "B"), "A A B"),
        ("missing missing", (), ""),
        ("A\u00a0gone\u2028B", ("A", "B"), "A B"),
        ("@other A # comment", ("A",), "A"),
        ("a A a", ("a",), "a a"),
    ],
)
def test_original_exact_split_membership_order_duplicates_and_noop(
    code, names, expected
):
    facts = Snapshot((1,), names, (("class", code),))
    result = changes(facts)
    assert result == (() if expected is None else (("class", code, expected),))


class Bridge:
    def __init__(self):
        self.facts = Snapshot(
            (1,),
            ("A", "B"),
            (("first", " A missing A "), ("keep", "\tB\n"), ("empty", "gone")),
        )
        self.events = []
        self.fail = ""
        self.poisoned = False

    def capture(self, *, deadline=None):
        self.events.append("capture")
        return self.facts

    def begin(self):
        self.events.append("begin")

    def write(self, name, members):
        self.events.append(("write", name, members))
        if self.fail == "write":
            raise RuntimeError("write failed")
        self.facts = Snapshot(
            self.facts.context,
            self.facts.names,
            tuple(
                (n, " ".join(members) if n == name else c)
                for n, c in self.facts.classes
            ),
        )

    def end(self):
        self.events.append("end")
        if self.fail == "end":
            raise RuntimeError("notification failed")


def test_real_whole_class_writer_keeps_noops_and_groups_all_changes():
    b = Bridge()
    facts = b.facts
    assert apply(b, facts) == {"classes": 2, "tokens": 2}
    assert [event for event in b.events if isinstance(event, tuple)] == [
        ("write", "first", ("A", "A")),
        ("write", "empty", ()),
    ]
    assert b.events.count("begin") == b.events.count("end") == 1
    assert b.facts.classes[1] == ("keep", "\tB\n")
    assert "first" in render(facts) and "missing" in render(facts)


@pytest.mark.parametrize("failure", ["write", "end"])
def test_partial_or_notification_failure_never_success_and_poison_bridge(failure):
    b = Bridge()
    b.fail = failure
    with pytest.raises(RuntimeError, match="Undo"):
        apply(b, b.facts)
    assert b.poisoned and b.events.count("end") == 1
    with pytest.raises(RuntimeError, match="reopen"):
        apply(b, b.facts)


def test_stale_source_and_empty_plan_never_open_history():
    b = Bridge()
    old = b.facts
    b.facts = Snapshot((2,), old.names, old.classes)
    with pytest.raises(ValueError, match="changed"):
        apply(b, old)
    assert "begin" not in b.events
    b.facts = Snapshot((1,), ("A",), (("keep", " A\n"),))
    assert apply(b, b.facts) == {"classes": 0, "tokens": 0}
    assert "begin" not in b.events


def test_public_show_uses_lazy_shared_registry_factory_and_native_bridge(monkeypatch):
    import importlib
    import sys

    api = importlib.import_module("fontlabapp.features.classes.model")
    native = importlib.import_module("fontlabapp.features.classes.native")
    panel = importlib.import_module("fontlabapp.features.classes.ui")
    scripts = importlib.import_module("fontlabapp.core.scripting")
    sentinel = object()
    parent = object()
    monkeypatch.setattr(native, "Bridge", lambda backend: sentinel)
    monkeypatch.setattr(
        panel,
        "panel_type",
        lambda core, gui: lambda received, bridge: (received, bridge),
    )
    monkeypatch.setattr(
        scripts, "show_script_dialog", lambda factory, key: (key, factory(parent))
    )
    import fontlabapp

    monkeypatch.setattr(
        fontlabapp, "_native", lambda name: NS(QtCore="core", QtGui="gui")
    )
    assert api.show(object()) == ("clean_classes", (parent, sentinel))


def test_silent_native_noop_cannot_claim_success(monkeypatch):
    bridge = Bridge()
    monkeypatch.setattr(bridge, "write", lambda *args: None)
    with pytest.raises(RuntimeError, match="Undo"):
        apply(bridge, bridge.facts)
    assert bridge.poisoned
