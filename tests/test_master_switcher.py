# this_file: tests/test_master_switcher.py
# SPDX-License-Identifier: Apache-2.0
"""Original numeric axis labels, ordered buttons and explicit master activation."""

from importlib import import_module
from types import SimpleNamespace as NS

import pytest


@pytest.fixture
def api():
    return import_module("fontlabapp.masters.switcher.model")


def package():
    return NS(
        masters=["Bold", "Regular", "Light"],
        axes=[NS(shortName="wght"), NS(shortName="wdth")],
        location=lambda master: {
            "wght": {"Bold": 900, "Regular": 400, "Light": 100}[master],
            "wdth": 75.5,
        },
    )


def test_button_values_preserve_axis_order_and_exact_numeric_labels(api):
    assert api.button_values(package()) == (
        ("Light", "100 · 75.5"),
        ("Regular", "400 · 75.5"),
        ("Bold", "900 · 75.5"),
    )


def test_missing_axis_coordinate_is_omitted_without_losing_other_values(api):
    p = package()
    p.axes.append(NS(shortName="missing"))
    assert api.location_label(p, "Regular") == "400 · 75.5"
    p.axes = []
    assert api.location_label(p, "Regular") == ""
    assert api.button_values(p) == (("Bold", ""), ("Regular", ""), ("Light", ""))


def test_no_font_or_master_buttons_is_a_total_empty_result(api):
    assert api.button_values(None) == ()
    assert api.button_values(NS(masters=[], axes=[])) == ()


def test_switch_when_known_master_then_set_master_with_notify_and_no_refresh(api):
    p = package()
    calls = []
    p.setMaster = lambda *args: calls.append(args)
    api.switch(p, "Bold")
    assert calls == [("Bold", True)], f"switch must call only setMaster(name, True): {calls}"
    assert not hasattr(api, "_native"), "switch must not load a native refresh"
    with pytest.raises(ValueError, match="master"):
        api.switch(p, "missing")
    assert calls == [("Bold", True)], f"an unknown master must call nothing: {calls}"


def test_ambiguous_duplicate_master_names_are_refused_before_any_buttons(api):
    p = package()
    p.masters.append("Bold")
    with pytest.raises(ValueError, match="unique"):
        api.button_values(p)
