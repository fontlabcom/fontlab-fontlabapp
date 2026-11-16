# this_file: tests/test_bracket_layers.py
"""Full bracket-name and reverse component closure contract, without originals."""

import importlib
import sys
from itertools import product
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.masters.layers.brackets.model import Glyph, analyse, render, tab_names


def row(name, layers=(), components=()):
    return Glyph(name, tuple(layers), frozenset(components))


def test_report_when_nested_components_then_source_groups_sorted_and_full_font_scope():
    result = analyse(
        (
            row("C", (), ["B"]),
            row("A", ["Regular", "[500]"]),
            row("B", (), ["A"]),
            row("unrelated"),
        )
    )
    assert result.bracket_glyphs == frozenset(
        {"A"}
    ) and result.component_glyphs == frozenset({"B", "C"})
    assert result.total == 3 and result.glyph_count == 4 and result.overlap == 0
    assert (
        render(result)
        == "Glyphs with Bracket Layers (1):\nA\n\nAffected Components (2):\nB, C\n\nTotal affected glyphs: 3"
    )
    assert tab_names(result) == (("A",), ("B", "C"))


@pytest.mark.parametrize(
    "layers,match",
    [
        (("[100]",), True),
        (("]", "["), False),
        (("][",), True),
        (("foo [bar] aux",), True),
        (("{500}",), False),
        ((), False),
    ],
)
def test_pattern_when_layer_names_supplied_then_exact_both_brackets_in_one_name(
    layers, match
):
    assert bool(analyse((row("A", layers),)).bracket_glyphs) is match


@pytest.mark.parametrize("cycle", [False, True])
def test_overlap_when_seed_is_also_dependant_then_groups_preserved_total_unique(cycle):
    rows = (
        row("A", ["[1]"], ["B"] if cycle else []),
        row("B", ["[2]"], ["A"]),
        row("C", (), ["B"]),
    )
    result = analyse(rows)
    assert result.bracket_glyphs == frozenset({"A", "B"})
    assert result.component_glyphs == frozenset(
        {"A", "B", "C"} if cycle else {"B", "C"}
    )
    assert result.total == 3 and result.overlap == (2 if cycle else 1)
    assert tab_names(result) == (("A", "B"), ("A", "B", "C") if cycle else ("B", "C"))
    assert "Overlapping group members:" in render(result)


def test_empty_self_reference_unicode_and_dangling_references_keep_scope():
    assert (
        render(analyse(()))
        == "Glyphs with Bracket Layers (0):\n\n\nAffected Components (0):\n\n\nTotal affected glyphs: 0"
    )
    result = analyse(
        (
            row("Ż", ["[a]"], ["Ż", "", "missing"]),
            row("A", (), ["Ż", "missing"]),
            row("empty"),
        )
    )
    assert tab_names(result) == (("Ż",), ("A", "Ż")) and result.total == 2


@pytest.mark.parametrize(
    "args,exc",
    [
        (("", (), frozenset()), ValueError),
        (("A", [], frozenset()), TypeError),
        (("A", (None,), frozenset()), TypeError),
        (("A", (), []), TypeError),
        (("A", (), frozenset({None})), TypeError),
    ],
)
def test_input_when_malformed_then_reject_before_report(args, exc):
    with pytest.raises(exc):
        Glyph(*args)


def test_font_domain_when_ambiguous_then_no_report():
    for rows, exc in [
        (None, TypeError),
        ([row("A")], TypeError),
        ((object(),), TypeError),
        ((row("A"), row("A")), ValueError),
    ]:
        with pytest.raises(exc):
            analyse(rows)


def test_all_three_node_graphs_and_seed_sets_match_independent_transitive_matrix():
    names = ("A", "B", "C")
    for bits in product((False, True), repeat=9):
        reach = [list(bits[i * 3 : i * 3 + 3]) for i in range(3)]
        for k in range(3):
            for i in range(3):
                for j in range(3):
                    reach[i][j] = reach[i][j] or (reach[i][k] and reach[k][j])
        for selected in product((False, True), repeat=3):
            glyphs = tuple(
                row(
                    names[j],
                    ("[1]",) if selected[j] else (),
                    [names[i] for i in range(3) if bits[i * 3 + j]],
                )
                for j in range(3)
            )
            result = analyse(glyphs)
            expected = {
                names[j]
                for i in range(3)
                for j in range(3)
                if selected[i] and reach[i][j]
            }
            assert result.component_glyphs == expected, (
                bits,
                selected,
                expected,
                result,
            )
            assert result.total == len(
                {n for n, s in zip(names, selected) if s} | expected
            )


def test_launchers_when_called_then_lazy_shared_registry_and_native_route(monkeypatch):
    from fontlabapp.masters.layers.brackets import model as api

    show = Mock(return_value="owned panel")
    open_tab = Mock()
    cls = type("Dialog", (), {"KEY": "bracket_layers"})
    monkeypatch.setitem(
        sys.modules, "fontlabapp.masters.layers.brackets.ui", NS(BracketLayersDialog=cls)
    )
    monkeypatch.setitem(
        sys.modules, "fontlabapp.masters.layers.brackets.native", NS(open_tab=open_tab)
    )
    monkeypatch.setattr(
        importlib.import_module("fontlabapp.core.scripting"), "show_script_dialog", show
    )
    assert api.show() == "owned panel"
    show.assert_called_once_with(cls, "bracket_layers")
    assert api.open_tab() is None
    open_tab.assert_called_once_with()


def test_cold_import_when_host_modules_unavailable_then_core_stays_host_free():
    import subprocess
    import sys

    code = """
import importlib.abc, sys
class Forbidden(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'fontlab', 'fontgate', 'PythonQt', 'PySide6', 'fontlab_glyport', 'fontlab_fontport', 'GlyphsApp'}:
            raise AssertionError('Unexpected host import: ' + fullname)
sys.meta_path.insert(0, Forbidden())
import fontlabapp.masters.layers.brackets.model as api
assert api.analyse((api.Glyph('A', ('[100]',)),)).total == 1
assert not any(name in sys.modules for name in ('fontlabapp.masters.layers.brackets._snapshot', 'fontlabapp.masters.layers.brackets.native', 'fontlabapp.masters.layers.brackets.ui'))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=15, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
