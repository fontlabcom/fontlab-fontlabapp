# this_file: tests/test_layer_extrema_fences.py
"""Owned glyph/source/deadline fences, using the real native capture module."""

from types import SimpleNamespace as NS

import pytest
import test_layer_extrema_native as fixtures

import fontlabapp.masters.layers.extrema.native as api

host = fixtures.host


@pytest.mark.parametrize("fault", ["foreign", "null", "duplicate_id", "duplicate_name"])
def test_glyph_domain_failures_do_not_publish_prefix(host, fault):
    p, _, _ = host
    if fault == "foreign":
        p._glyphs[1].package = NS(id=99)
    elif fault == "null":
        p._glyphs[1].isNull = True
    elif fault == "duplicate_id":
        p._glyphs[1].id = p._glyphs[0].id
    else:
        p._glyphs[1].name = p._glyphs[0].name
    with pytest.raises(ValueError):
        api.capture("all")


@pytest.mark.parametrize("fault", ["font", "master", "bounds", "width", "slow"])
def test_source_drift_or_deadline_rejects_complete_capture(host, fault):
    p, state, layers = host

    def change(layer):
        if fault == "font":
            state.current = False
        elif fault == "master":
            p.master = "Thin"
        elif fault == "slow":
            state.seconds = 3
        elif state.reads == 3:
            layers[1].box.values[1 if fault == "bounds" else 2] += 1

    state.during = change
    with pytest.raises((ValueError, TimeoutError)):
        api.capture("current")


def test_missing_or_background_current_layer_is_not_replaced_with_another(host):
    _p, _, layers = host
    layers[1].isMaskLayer = True
    with pytest.raises(ValueError):
        api.capture("current")
    layers[1].isMaskLayer = False
    layers[1].name = "other"
    with pytest.raises(ValueError):
        api.capture("current")


def test_empty_font_returns_empty_capture_for_explicit_no_proof_diagnostic(host):
    p, _, _ = host
    p.glyphs = []
    assert api.capture("all").rows == ()


def test_foreign_layer_owner_is_refused_before_its_bounds_are_read(host):
    _p, state, layers = host
    layers[0].glyph = NS(id=999)
    with pytest.raises(ValueError, match="another glyph"):
        api.capture("all")
    assert state.reads == 2
