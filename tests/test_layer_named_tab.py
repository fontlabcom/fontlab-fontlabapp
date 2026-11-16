# this_file: tests/test_layer_named_tab.py
"""Exercise actual shared tab preparation with owned native-shaped controls."""

from types import SimpleNamespace as NS

import pytest
import test_named_tab

import fontlabapp.proof.tabs.named as api

host = test_named_tab.host
named = test_named_tab.named


def test_layer_specific_symbols_preserve_unencoded_names_layers_and_repeats(named):
    rows = (("A.alt", "Thin"), ("A.alt", "Sketch"), ("A.alt", "Thin"))
    api.open_layer_tab(rows, expected_id=7, master="Regular")
    values = named.state.populations[0][0].values
    assert tuple((s.name, s.layerName) for s in values) == rows
    assert named.old_shape.active is True and named.shape.active is False


@pytest.mark.parametrize(
    "rows", [None, [], ("A",), (("A",),), (("A", None),), (("", "Thin"),), (("A", ""),)]
)
def test_bad_complete_layer_request_opens_no_tab(named, rows):
    with pytest.raises((ValueError, TypeError)):
        api.open_layer_tab(rows, expected_id=7, master="Regular")
    assert named.state.populations == []


def test_empty_layer_sequence_and_bad_master_follow_shared_source_fences(named):
    api.open_layer_tab((), expected_id=7, master="Regular")
    assert named.state.populations[0][0].values == []
    with pytest.raises(TypeError):
        api.open_layer_tab((), expected_id=7, master=None)


def test_layer_request_rejects_slow_build_before_tab_creation(named):
    named.state.seconds = 99
    with pytest.raises(TimeoutError):
        api.open_layer_tab(
            (("A", "Thin"),), expected_id=7, master="Regular", deadline=1
        )
    assert named.state.populations == []


# ---------------------------------------------------------------- open_layer_rows (T14i, G10 review C2)
LAYERS = {"A": ("Thin", "Bold"), "B": ("Thin",), "space": ("Regular",)}


@pytest.fixture
def rows_host(named):
    shape = named.shape

    def find(name):
        if name not in LAYERS:
            return None
        layers = [NS(name=n, isNull=False, shapes=[shape]) for n in LAYERS[name]]
        return NS(
            isNull=False,
            layers=layers,
            findLayer=lambda n: next((x for x in layers if x.name == n), None),
        )

    named.package.findName = find
    return named


def shown(host):
    return [v if isinstance(v, str) else (v.name, v.layerName) for v in host.state.populations[0][0].values]


def test_open_layer_rows_when_rows_spaces_and_blank_row_then_one_tab_in_order(rows_host):
    rows = (("A", "Thin"), api.SPACE, ("A", "Bold")), (), (("B", "Thin"),)
    api.open_layer_rows(rows, expected_id=7, master="Regular")
    assert len(rows_host.state.populations) == 1, "one tab for all rows"
    assert shown(rows_host) == [("A", "Thin"), " ", ("A", "Bold"), "\n", "\n", ("B", "Thin")]
    assert rows_host.state.tabs == [""] and rows_host.state.calls[-2:] == ["disconnect", "delete"]


def test_open_layer_rows_when_leading_and_double_spaces_then_kept(rows_host):
    api.open_layer_rows((( api.SPACE, api.SPACE, ("B", "Thin")),), expected_id=7, master="Regular")
    assert shown(rows_host) == [" ", " ", ("B", "Thin")]


def test_open_layer_rows_when_empty_then_empty_tab(rows_host):
    api.open_layer_rows((), expected_id=7, master="Regular")
    assert shown(rows_host) == []


@pytest.mark.parametrize(
    "rows",
    [
        None,
        [],
        (((("A", "Thin"),),),),
        ([("A", "Thin")],),
        ((("A", "Thin"), [None, ""]),),
        (((None, "Thin"),),),
        ((("", "Thin"),),),
        ((("A", ""),),),
        ((("A",),),),
        (("A", "Thin"),),
    ],
    ids=["none", "list", "nested", "row-list", "space-list", "none-layer", "empty-name", "empty-layer", "short", "flat"],
)
def test_open_layer_rows_when_bad_request_then_no_symbol_and_no_tab(rows_host, rows):
    made = []
    rows_host.native.fgSymbol = lambda name: made.append(name) or NS(name=name)
    with pytest.raises((ValueError, TypeError)):
        api.open_layer_rows(rows, expected_id=7, master="Regular")
    assert made == [] and rows_host.state.populations == [] and not rows_host.state.calls


@pytest.mark.parametrize("item", [("A", "Light"), ("missing", "Thin")])
def test_open_layer_rows_when_layer_missing_then_value_error_before_any_symbol(rows_host, item):
    made = []
    rows_host.native.fgSymbol = lambda name: made.append(name) or NS(name=name)
    with pytest.raises(ValueError, match="no tab opened"):
        api.open_layer_rows(((( "B", "Thin"), item),), expected_id=7, master="Regular")
    assert made == [] and rows_host.state.populations == [] and not rows_host.state.calls


def test_open_layer_rows_when_font_changed_then_refused(rows_host):
    rows_host.state.current = False
    with pytest.raises(ValueError, match="source font changed"):
        api.open_layer_rows(((( "B", "Thin"),),), expected_id=7, master="Regular")
    assert rows_host.state.populations == []


def test_open_layer_rows_when_master_changed_or_bad_then_refused(rows_host):
    rows_host.package.master = "Bold"
    with pytest.raises(ValueError, match="source master changed"):
        api.open_layer_rows(((( "B", "Thin"),),), expected_id=7, master="Regular")
    with pytest.raises(TypeError):
        api.open_layer_rows((), expected_id=7, master=None)
    assert rows_host.state.populations == []


def test_open_layer_rows_when_deadline_passed_then_no_tab(rows_host):
    rows_host.state.seconds = 99
    with pytest.raises(TimeoutError):
        api.open_layer_rows(((( "B", "Thin"),),), expected_id=7, master="Regular", deadline=1)
    assert rows_host.state.populations == []
