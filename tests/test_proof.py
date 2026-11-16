# this_file: tests/test_proof.py
"""Independent numerical/Qt path oracles for the shared read-only Proof helpers."""

from importlib import import_module
from types import SimpleNamespace as NS

import pytest
from PySide6 import QtCore, QtGui

proof = import_module("fontlabapp.proof.inspect.model")


def test_outline_assembles_actual_closed_open_component_transforms(monkeypatch):
    monkeypatch.setattr(proof, "_native", lambda name: NS(QtCore=QtCore, QtGui=QtGui))
    closed = QtGui.QPainterPath()
    closed.addRect(0, 0, 100, 200)
    opened = QtGui.QPainterPath()
    opened.moveTo(-20, 50)
    opened.lineTo(80, 250)
    transform = QtGui.QTransform(2, 0, 0, 3, 400, -100)
    component = QtGui.QPainterPath()
    component.addRect(0, 0, 60, 40)
    layer = NS(
        shapes=[
            NS(transform=transform, closedPath=closed, openedPath=opened),
            NS(
                transform=QtGui.QTransform.fromTranslate(-300, 900),
                closedPath=component,
                openedPath=None,
            ),
        ]
    )
    path = proof.layer_path(layer)
    box = path.boundingRect()
    assert (box.x(), box.y(), box.width(), box.height()) == (-300, -100, 900, 1040)
    assert path.fillRule() == QtCore.Qt.WindingFill
    assert path.contains(QtCore.QPointF(500, 200)), "Transformed closed outline lost"
    assert path.contains(QtCore.QPointF(-280, 920)), "Placed component lost"
    assert path.elementCount() == 12, "Open path or component omitted"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("Aé🦊", ["A", "eacute", None]),
        ("/alternate /A/unknown", ["alternate", "A", None]),
        ("/A  A", ["A", "space", "A"]),
        ("//A/", [None, "A", None]),
        ("/", [None]),
    ],
)
def test_text_preserves_missing_unicode_and_unencoded_slash_slots(text, expected):
    assert (
        proof.parse_text(
            text,
            {65: "A", 233: "eacute", 32: "space"},
            {"A", "eacute", "space", "alternate"},
        )
        == expected
    )


def test_sizes_keep_order_duplicates_exact_bounds_and_ignore_invalid_nonfinite():
    assert proof.parse_sizes("nan inf -inf 3.99 4, 10 400 400.01 nope 12.5 10") == [
        4,
        10,
        400,
        12.5,
        10,
    ]
    assert proof.parse_sizes("") == []


def test_glyph_run_exact_per_master_advances_missing_layers_and_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(proof, "layer_path", lambda layer: layer.path)

    def find(name):
        calls.append(name)
        return (
            NS(
                isNull=False,
                findLayer=lambda master: NS(
                    isNull=master == "missing",
                    path=master,
                    advanceWidth={"Light": 312.5, "Bold": 700}.get(master),
                ),
            )
            if name == "A"
            else None
        )

    package = NS(upm=1000, findName=find)
    assert proof.glyph_run(package, ["A", "A", None, "absent"], "Light") == [
        ("Light", 312.5),
        ("Light", 312.5),
        (None, 500),
        (None, 500),
    ]
    assert calls == ["A", "absent"]
    assert proof.glyph_run(package, ["A"], "Bold") == [("Bold", 700)]
    assert proof.glyph_run(package, ["A"], "missing") == [(None, 500)]
    assert proof.glyph_run(package, [], "Light") == []


def test_grid_common_scale_fits_tall_accents_and_wide_negative_overhangs():
    path = QtGui.QPainterPath()
    path.addRect(-700, -500, 3500, 2400)
    cells = [("wide", [("Light", path, 500), ("Bold", None, 0)])]
    scale = proof.grid_scale(cells, (-500, 1900), 100)
    assert scale == pytest.approx(88 / 3500)
    assert proof.path_span(path, 500) == (-700, 2800)
    assert proof.path_span(None, -50) == (-50, 0)
    assert 3500 * scale <= 88 and 2400 * scale <= 88
    assert proof.grid_scale([], (-250, 750), 100) == 0.088


def test_word_filters_keep_input_order_case_letter_and_length_semantics():
    words = ["zebra", "apple", "jazz", "about", "ab", "a", "apple"]
    chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert proof.find_words(words, chars) == [
        "zebra",
        "apple",
        "jazz",
        "about",
        "apple",
    ]
    assert proof.find_words(words, chars, must="ZA") == ["zebra", "jazz"]
    assert proof.find_words(words, chars, only="APLE") == ["apple", "apple"]
    assert proof.find_words(words, chars, "Capitalised", min_len=4, max_len=4) == [
        "Jazz"
    ]
    assert proof.find_words(words, set("JAZ"), "UPPERCASE") == ["JAZZ"]
    assert proof.find_words(words, set()) == []
    assert proof.find_words(words, chars, min_len=20, max_len=1) == []
    assert proof.find_words([], chars) == []
    assert proof.WORDS == sorted(set(proof.ENGLISH.split()) | set(proof.LATIN.split()))
    assert len(proof.WORDS) > 300


def test_selection_maps_and_current_fallback_reuse_shared_reads(monkeypatch):
    monkeypatch.setattr(
        proof,
        "names_font_glyphs",
        lambda: [("first", [65]), ("alt", [65]), ("unencoded", [])],
    )
    assert proof.font_maps() == ({65: "first"}, {"first", "alt", "unencoded"})
    assert proof.character_map() == {65: "first"}
    assert proof.font_chars() == {"A"}
    glyphs = {name: NS(name=name, isNull=False) for name in ["first", "alt"]}
    monkeypatch.setattr(
        proof, "names_selected_names", lambda: ["first", "alt", "missing"]
    )
    assert [g.name for g in proof.selected_glyphs(NS(findName=glyphs.get))] == [
        "first",
        "alt",
    ]
    assert proof.selected_glyphs(None) == []


def test_outline_read_failure_propagates_instead_of_partial_path(monkeypatch):
    monkeypatch.setattr(proof, "_native", lambda name: NS(QtCore=QtCore, QtGui=QtGui))

    class Broken:
        @property
        def closedPath(self):
            raise RuntimeError("native path read")

    with pytest.raises(RuntimeError, match="native path read"):
        proof.layer_path(NS(shapes=[Broken()]))


def test_pure_api_accessor_imports_no_native_or_optional_ui(monkeypatch):
    scripting = import_module("fontlabapp.core.scripting")
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: pytest.fail("Pure API imported native runtime"),
    )
    assert scripting.proof_api() is proof
    assert scripting.proof_api().parse_sizes("12 18") == [12, 18]


@pytest.mark.parametrize("components", [0, 1])
def test_selected_glyphs_when_contourless_current_then_resolves_shared_fallback(
    monkeypatch, components
):
    scripting = import_module("fontlabapp.core.scripting")

    class CurrentGlyph:
        name = "space" if components == 0 else "composite"
        shapes = [object()] * components

        def __len__(self):
            return 0

    current = CurrentGlyph()
    resolved = NS(name=current.name, isNull=False)
    fl = NS(font=[resolved], Selected=lambda index: False)
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: NS(fl=fl) if name == "FL" else NS(CurrentGlyph=lambda: current),
    )
    assert proof.selected_glyphs(NS(findName=lambda name: resolved)) == [resolved], (
        "Proof must retain the empty or component-only current glyph"
    )
    for missing in (None, NS(isNull=True)):
        assert (
            proof.selected_glyphs(NS(findName=lambda name, value=missing: value)) == []
        ), "Stale or null package glyphs must still be excluded"
    fl.font = None
    assert proof.selected_glyphs(NS(findName=lambda name: pytest.fail(name))) == []


def test_selected_glyphs_when_shared_read_or_resolution_fails_then_propagates(
    monkeypatch,
):
    def fail(*args):
        raise RuntimeError("native selection unavailable")

    monkeypatch.setattr(proof, "names_selected_names", fail)
    with pytest.raises(RuntimeError, match="native selection unavailable"):
        proof.selected_glyphs(NS(findName=lambda name: None))
    monkeypatch.setattr(proof, "names_selected_names", lambda: ["A"])
    with pytest.raises(RuntimeError, match="native selection unavailable"):
        proof.selected_glyphs(NS(findName=fail))
