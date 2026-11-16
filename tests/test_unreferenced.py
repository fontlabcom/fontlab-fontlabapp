# this_file: tests/test_unreferenced.py
# SPDX-License-Identifier: Apache-2.0
"""Keep all original unreferenced-glyph exclusions and exact ordered source."""

from importlib import import_module
from types import SimpleNamespace as NS

import pytest

api = import_module("fontlabapp.glyphs.unreferenced")


@pytest.fixture
def source(monkeypatch):
    names = [
        ".notdef",
        "A",
        "A.alt",
        "a-cy",
        "component",
        "recipe",
        "classed",
        "unused",
    ]
    layers = {name: NS(name="Regular", recipe="", shapes=[]) for name in names}
    layers["A"].shapes = [
        NS(isComponent=True, shapeData=NS(componentGlyph="component"))
    ]
    layers["A"].recipe = "recipe + A"
    glyphs = {
        name: NS(name=name, isNull=False, layers=[layers[name]]) for name in names
    }
    groups = {
        "usedClass": NS(isFeaGroup=lambda: True),
        "other": NS(isFeaGroup=lambda: True),
    }

    class Groups(dict):
        def getAsClassRecords(self):
            return ["usedClass: classed'", "other: unused"]

    state = NS(
        prefix="# ignored include(foo);\n@usedClass; sub a-cy by A;",
        encodings={"A": [0, 65]},
    )
    font = NS(
        groups=Groups(groups),
        features=NS(
            get_prefix=lambda: state.prefix,
            __iter__=lambda: iter(()),
        ),
    )

    class Features:
        def get_prefix(self):
            return state.prefix

        def __iter__(self):
            # fgOTLayout's sequence protocol yields feature CODE, not tag keys.
            return iter([self.get_feature("liga")])

        def keys(self):
            return ["liga"]

        def get_feature(self, tag):
            assert tag == "liga"
            return "# unused is only a comment"

    font.features = Features()
    monkeypatch.setattr(api, "_native", lambda name: NS(CurrentFont=lambda: font))
    monkeypatch.setattr(api, "font_glyph_names", lambda: list(names))
    monkeypatch.setattr(
        api,
        "names_font_glyphs",
        lambda: [(n, state.encodings.get(n, [])) for n in names],
    )
    return NS(
        package=NS(findName=glyphs.get),
        glyphs=glyphs,
        layers=layers,
        state=state,
        font=font,
        names=names,
    )


def test_candidates_preserve_every_exclusion_font_order_and_alternate_hint(source):
    assert api.unreferenced(source.package) == [
        ("A.alt", "alternate of A?"),
        ("unused", ""),
    ]
    assert api.class_members(source.font, {"usedClass"}) == {"classed"}
    assert api.tokens("@class-a [a-cy A.alt]; # hidden\n") == {
        "class-a",
        "a-cy",
        "A.alt",
    }
    assert api.feature_source(source.font).startswith(source.state.prefix + "\n")


def test_zero_and_secondary_encodings_exclude_candidates(source):
    source.state.encodings.update({"A.alt": [0], "unused": [65, 0xE000]})
    assert api.unreferenced(source.package) == []


def test_include_refusal_ignores_comments_but_accepts_hyphenated_names(source):
    assert api.unreferenced(source.package)
    source.state.prefix += "\ninclude (external.fea);"
    with pytest.raises(ValueError, match=r"include\(\)"):
        api.unreferenced(source.package)


def test_missing_glyph_refuses_partial_candidates(source):
    del source.glyphs["unused"]
    with pytest.raises(ValueError, match="Glyph source changed"):
        api.unreferenced(source.package)


def test_snapshot_detects_raw_recipe_encoding_and_feature_changes(source):
    before = api.source_values(source.package)
    source.layers["unused"].recipe = "A"
    assert api.source_values(source.package) != before
    source.layers["unused"].recipe = ""
    assert api.source_values(source.package) == before
    source.state.encodings["unused"] = [0xE001]
    assert api.source_values(source.package) != before
    source.state.encodings.pop("unused")
    source.state.prefix += "\n# Raw source changes must also invalidate"
    assert api.source_values(source.package) != before


def test_empty_no_font_helpers_produce_no_candidates():
    assert api.source_values(None) is None
    assert api.unreferenced(None) == []


def test_component_references_from_noncurrent_layers_exclude_candidates(source):
    source.glyphs["A"].layers.append(
        NS(
            name="Auxiliary",
            recipe="",
            shapes=[NS(isComponent=True, shapeData=NS(componentGlyph="unused"))],
        )
    )
    assert api.unreferenced(source.package) == [("A.alt", "alternate of A?")]


def test_encoding_order_change_refuses_a_partial_candidate_list(source, monkeypatch):
    monkeypatch.setattr(api, "names_font_glyphs", lambda: [("unused", [])])
    with pytest.raises(ValueError, match="Font encoding order changed"):
        api.unreferenced(source.package)


def test_empty_bound_font_has_no_candidates(source):
    source.names.clear()
    assert api.unreferenced(source.package) == []


def test_feature_references_use_native_mapping_keys_not_sequence_values(source):
    source.font.features.get_feature = lambda tag: (
        "sub unused by A;" if tag == "liga" else ""
    )
    assert api.unreferenced(source.package) == [("A.alt", "alternate of A?")]
    assert "sub unused by A;" in api.feature_source(source.font)
