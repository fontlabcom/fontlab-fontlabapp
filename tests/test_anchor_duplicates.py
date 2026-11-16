# this_file: tests/test_anchor_duplicates.py
"""Complete original duplicate policy and native identity-safe removal plan."""

from dataclasses import FrozenInstanceError

import pytest

from fontlabapp.anchors.duplicates.model import Layer, Pin, Snapshot, findings, plan


def pins(*records):
    return tuple(Pin(index + 1, *record) for index, record in enumerate(records))


@pytest.mark.parametrize(
    "records, expected",
    [
        ([], []),
        (
            [("top", 1, 2), ("top.1", 8, 9)],
            [("duplicate name", ("top", "top.1"), (2,))],
        ),
        (
            [("top.1", 8, 9), ("top", 1, 2)],
            [("duplicate name", ("top.1", "top"), (2,))],
        ),
        (
            [("top.1.2", 0, 0), ("top.1", 0, 0), ("top", 0, 0)],
            [("duplicate name", ("top.1", "top"), (3,))],
        ),
        (
            [("top.²", 9, 9), ("top", 0, 0)],
            [("duplicate name", ("top.²", "top"), (2,))],
        ),
        (
            [("top.1", 0, 0), ("bottom.1", 0.1, 0.1)],
            [("coincident", ("top.1", "bottom.1"), (2,))],
        ),
        ([("a", 0.5, -0.5), ("b", -0.5, 0.5)], [("coincident", ("a", "b"), (2,))]),
        ([("a", 1.5, -1.5), ("b", 2.5, -2.5)], [("coincident", ("a", "b"), (2,))]),
        (
            [("top", 0, 0), ("top.1", 9, 9), ("other", 0, 0)],
            [("duplicate name", ("top", "top.1"), (2,))],
        ),
        ([("", 0, 0), (".1", 9, 9)], [("duplicate name", ("", ".1"), (2,))]),
    ],
)
def test_findings_preserve_complete_original_partition_and_first_occurrence(
    records, expected
):
    assert [(r.kind, r.names, r.extras) for r in findings(pins(*records))] == expected


def test_plan_keeps_automatic_layers_and_coincident_opt_in_and_master_order():
    values = pins(("top", 1, 2), ("top.1", 3, 4), ("x", 8, 9), ("y", 8, 9))
    layers = tuple(
        Layer("A", master, 10, index, auto, values)
        for index, (master, auto) in enumerate(
            [("Regular", False), ("Bold", True), ("Light", False)], 20
        )
    )
    facts = Snapshot((1,), ("A",), ("A",), ("Regular", "Bold", "Light"), layers, ())
    assert plan(facts, False) == ((layers[0], (2,)), (layers[2], (2,)))
    assert plan(facts, True) == ((layers[0], (2, 4)), (layers[2], (2, 4)))
    assert not plan(Snapshot((), (), (), (), (), ()), False)
    with pytest.raises(FrozenInstanceError):
        values[0].name = "changed"


def test_ambiguous_repeated_pin_identity_refuses_before_action():
    a, b = Pin(1, "top", 1, 2), Pin(1, "top.1", 3, 4)
    with pytest.raises(ValueError, match="identity"):
        findings((a, b))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_coordinates_refuse_complete_result(bad):
    with pytest.raises(ValueError, match="finite"):
        findings((Pin(1, "top", bad, 2),))


def test_public_show_resolves_owned_native_backend_and_lazy_factory(monkeypatch):
    from types import SimpleNamespace as NS

    import fontlabapp
    import fontlabapp.anchors.duplicates.model as api
    import fontlabapp.anchors.duplicates.native as native
    import fontlabapp.anchors.duplicates.ui as panel
    from fontlabapp.core import scripting

    backend = object()
    expected = object()
    calls = []
    monkeypatch.setattr(
        fontlabapp, "_native", lambda name: NS(QtCore="core", QtGui="gui")
    )
    monkeypatch.setattr(native, "Backend", lambda: backend)
    monkeypatch.setattr(
        panel,
        "panel_type",
        lambda core, gui: (
            lambda parent, b: (calls.append((core, gui, parent, b)), expected)[1]
        ),
    )
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda factory, key: factory(key)
    )
    assert api.show() is expected
    assert calls == [("core", "gui", api.KEY, backend)]
