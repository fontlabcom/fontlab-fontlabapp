# this_file: tests/test_master_point_counts.py
"""Reza master-only occurrence report: full native-shaped and pure contracts."""

import fontlabapp.masters.point_counts.model as model
import fontlabapp.masters.point_counts.native as api
import pytest
from fontlabapp.contours.point_counts.model import Counts, LayerCount
from test_point_counts_native import contour, shape

pytest_plugins = ["test_point_counts_native"]


def test_render_keeps_exact_original_blocks_and_trailing_newline():
    rows = (
        LayerCount("Bold", Counts(2, 1, 2, 3)),
        LayerCount("Empty😀", Counts(0, 0, 0, 0)),
    )
    assert (
        model.render(rows)
        == "Layer: Bold\nTotal: 5 Points - 2 Handles, 3 Nodes, 3 Paths\n\nLayer: Empty😀\nTotal: 0 Points - 0 Handles, 0 Nodes, 0 Paths\n"
    )
    assert model.render(()) == ""


def masters(domain):
    for layer in domain.glyph.layers:
        layer.isMasterLayer = True
    return domain


def test_capture_preserves_stored_master_order_repeated_selected_occurrences_and_empty(
    domain,
):
    masters(domain)
    domain.workspace.activeFontPanel = None
    domain.bold.shapes = [
        shape([contour(["on", "control", "control", "on"]), contour([])]),
        shape(component=True),
    ]

    class Auxiliary:
        id = 999
        isMasterLayer = False

        @property
        def shapes(self):
            raise AssertionError("Auxiliary paths must not be read")

    domain.glyph.layers.insert(1, Auxiliary())
    rows = api.capture()
    assert [r.name for r in rows] == ["Bold", "Regular"] * 3
    assert rows[0].counts == Counts(1, 1, 2, 2) and rows[1].counts == Counts(0, 0, 0, 0)


def test_empty_selection_and_no_masters_render_empty_window_content(domain):
    masters(domain)
    domain.legacy.Selected = lambda i: False
    assert api.capture() == ()
    domain.legacy.Selected = lambda i: True
    for layer in domain.glyph.layers:
        layer.isMasterLayer = False
    assert api.capture() == ()


@pytest.mark.parametrize("role", [None, 1, lambda: True])
def test_unreadable_master_property_is_not_coerced_or_called(domain, role):
    masters(domain)
    domain.bold.isMasterLayer = role
    with pytest.raises(ValueError, match="master"):
        api.capture()


def test_changed_master_domain_refuses_whole_snapshot(domain, monkeypatch):
    masters(domain)
    original = api._read
    calls = []

    def read(selected, deadline):
        result = original(selected, deadline)
        calls.append(True)
        if len(calls) == 1:
            domain.bold.name = "Changed"
        return result

    monkeypatch.setattr(api, "_read", read)
    with pytest.raises(ValueError):
        api.capture()


def test_deadline_refuses_prefix(domain, monkeypatch):
    masters(domain)
    monkeypatch.setattr(api, "monotonic", lambda: 0)
    monkeypatch.setattr(api.reader, "monotonic", lambda: 3)
    with pytest.raises(TimeoutError):
        api.capture()


def test_quadratic_endpoints_are_included_by_existing_verified_reader(domain):
    masters(domain)
    domain.regular.shapes = [shape([contour(["on", "off", "on"])])]
    assert api.capture()[1].counts == Counts(1, 1, 1, 1)


@pytest.mark.parametrize(
    "kinds,closed,expected",
    [
        (["on", "off", "on"], False, Counts(1, 1, 1, 1)),
        (["on", "off"], True, Counts(0, 1, 1, 1)),
        (["on", "control", "control", "on", "off", "on"], False, Counts(1, 2, 3, 1)),
        (["off", "control"], False, Counts(0, 0, 2, 1)),
    ],
)
def test_literal_quadratic_cubic_mixed_and_control_only_counts(
    domain, kinds, closed, expected
):
    masters(domain)
    domain.regular.shapes = [shape([contour(kinds, closed)])]
    assert api.capture()[1].counts == expected


@pytest.mark.parametrize("problem", ["identity", "invalid"])
def test_invalid_selected_identity_or_master_refuses_whole_snapshot(
    domain, monkeypatch, problem
):
    masters(domain)
    if problem == "invalid":
        domain.bold.isValid = False
    else:
        original = api.selection.capture

        def selected(deadline):
            result = original(deadline)
            domain.glyph.id = 999
            return result

        monkeypatch.setattr(api.selection, "capture", selected)
    with pytest.raises(ValueError):
        api.capture()
