# this_file: tests/test_extrema_proof.py
"""Real read/choice/per-layer-symbol/tab pipeline through owned native surfaces."""

import pytest
import test_layer_extrema_native as readers
import test_named_tab

import fontlabapp.proof.extrema.model as api


@pytest.fixture
def scene(monkeypatch):
    package, state, layers = readers.host.__wrapped__(monkeypatch)
    native = test_named_tab.host.__wrapped__(monkeypatch)
    native = test_named_tab.named.__wrapped__(native, monkeypatch)
    package.id = 7
    monkeypatch.setattr(api, "monotonic", lambda: state.seconds)
    return package, state, layers, native


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("current", (("b", "Regular"), ("b", "Regular"))),
        ("all", (("b", "Sketch"), ("a", "Sketch"))),
    ],
)
def test_complete_scope_capture_and_fresh_tab_keep_both_exact_winners(
    scene, mode, expected
):
    package, _state, _layers, native = scene
    result = api.run(mode)
    assert result.layers == expected
    values = native.state.populations[0][0].values
    assert tuple((value.name, value.layerName) for value in values) == expected
    assert (
        package.master == "Regular"
        and native.old_shape.active is True
        and native.shape.active is False
    )


def test_tail_read_drift_is_caught_by_complete_pre_tab_recapture(scene):
    _, state, layers, native = scene

    def drift(layer):
        if state.reads == 4:
            layers[1].box.values[2] += 1

    state.during = drift
    with pytest.raises(ValueError, match="complete extrema source"):
        api.run("current")
    assert native.state.populations == [] and native.state.tabs == []


def test_tab_failure_carries_source_numbers_without_claiming_success(scene):
    _, _, _, native = scene
    native.state.populate_error = True
    with pytest.raises(api.ProofError, match="new tab may remain") as caught:
        api.run("all")
    assert caught.value.result.highest.top == 1000
    assert caught.value.result.lowest.bottom == -100
    assert native.old_shape.active is True and native.shape.active is False


def test_empty_font_does_not_open_any_tab(scene):
    package, _, _, native = scene
    package.glyphs = []
    with pytest.raises(ValueError, match="no eligible"):
        api.run("all")
    assert native.state.tabs == []


def test_public_all_layer_show_uses_shared_owned_registry(monkeypatch):
    import sys
    from types import SimpleNamespace

    from fontlabapp.core import scripting

    marker = object()
    monkeypatch.setitem(
        sys.modules, "fontlabapp.proof.extrema.ui", SimpleNamespace(ExtremaDialog=marker)
    )
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda factory, key: (factory, key)
    )
    assert api.show_all() == (marker, "highest_lowest_layers")
