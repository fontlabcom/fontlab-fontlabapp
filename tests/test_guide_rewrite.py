# this_file: tests/test_guide_rewrite.py
"""Preserve complete guide values and reject an entire bad batch before mutation."""

from copy import deepcopy
from types import SimpleNamespace as NS

import fontlabapp.guides.rewrite.model as api
import pytest


@pytest.mark.parametrize(
    "cells,wanted",
    [
        (
            ["Regular", "9", "-1.234", "0", " name "],
            ("Regular", (0.0, -1.23, 0.0, "name")),
        ),
        (["Bold", "-2.345", "9", "270", "v"], ("Bold", (-2.35, 0.0, 90.0, "v"))),
        (["Light", "", "", "-30", "a"], ("Light", (0.0, 0.0, 150.0, "a"))),
    ],
)
def test_parse_row_retains_original_axis_rules_and_rounding(cells, wanted):
    assert api.parse_row(cells, 4) == wanted, (
        "Guide cells must retain original normalization"
    )


@pytest.mark.parametrize("text", ["no number", "nan", "inf", "-inf", "1e999"])
def test_parse_row_refuses_nonfinite_or_nonnumeric_with_row_number(text):
    with pytest.raises(ValueError, match="row 5:"):
        api.parse_row(["Regular", text, "0", "20", "name"], 4)


def test_scaled_and_filter_keep_complete_original_geometry_rules():
    h = (0.0, 17.0, 0.0, "Baseline")
    v = (100.0, 0.0, 90.0, "Guide")
    a = (100.0, 20.0, 45.0, "Angle")
    assert api.scaled(h, 2) == h
    assert api.scaled(v, 2) == (200.0, 0.0, 90.0, "Guide")
    assert api.scaled(a, 2) == (200.0, 20.0, 26.57, "Angle")
    assert api.matches(a, "Angled", "ANG") and not api.matches(a, "Horizontal", "")


@pytest.fixture
def owned(monkeypatch):
    events = []

    def guide(record, style="original"):
        return NS(record=record, style=style, isHint=False)

    class Layer:
        autoLayer = False

        def __init__(self, values):
            self.guidelines = values

        def checkInitHistoryState(self, flags):
            events.append(("init", self))

        def removeGuides(self, h, v):
            events.append(("remove", self))
            self.guidelines = [g for g in self.guidelines if g.isHint]

        def appendGuidelines(self, values):
            events.append(("append", self))
            self.guidelines.extend(values)

    class Glyph:
        name = "H"
        lastModified = "old"

        def checkInitHistoryState(self, flags):
            events.append(("init", self))

    def copy(g):
        events.append(("copy", g))
        return deepcopy(g)

    def create(r):
        events.append(("new", r))
        return guide(r, "new")

    native = NS(
        flGuideLine=copy,
        flItems=lambda: NS(
            notifyChangesApplied=lambda title, items: events.append(
                ("notify", title, items)
            )
        ),
        UpdateAll=lambda: events.append(("update",)),
    )
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "UTC stamp")))
    monkeypatch.setattr(api, "_native", lambda n: native if n == "fontlab" else qt)
    monkeypatch.setattr(api, "guide_record", lambda g: g.record)
    monkeypatch.setattr(api, "new_guide", create)
    monkeypatch.setattr(
        api, "require_safe_targets", lambda p, n: events.append(("preflight", n))
    )
    return NS(events=events, guide=guide, Layer=Layer, Glyph=Glyph, package=object())


def test_replace_clears_to_empty_keeps_hints_and_records_one_final_history(owned):
    o = owned
    g = o.Glyph()
    hint = NS(isHint=True, style="hint")
    layer = o.Layer([o.guide((0, 1, 0, "old")), hint])
    assert api.replace_guides(o.package, [(g, layer, [])], "Owned") == {"layers": 1}
    assert layer.guidelines == [hint], (
        "Empty wanted records must remove real guides and preserve hints"
    )
    assert [e[0] for e in o.events] == [
        "preflight",
        "init",
        "init",
        "remove",
        "notify",
        "update",
    ]
    assert (
        o.events[-2] == ("notify", "Owned", [layer, g])
        and g.lastModified == "UTC stamp"
    )


def test_replace_preconstructs_entire_batch_and_preserves_matching_style(owned):
    o = owned
    g = o.Glyph()
    keep = o.guide((3, 0, 90, "keep"), "coloured tagged")
    l1 = o.Layer([keep])
    l2 = o.Layer([])
    assert api.replace_guides(
        o.package,
        [(g, l1, [keep.record, (0, 8, 0, "new")]), (g, l2, [(0, 9, 0, "other")])],
    ) == {"layers": 2}
    kinds = [e[0] for e in o.events]
    assert kinds.index("new") < kinds.index("init") and kinds.count("new") == 2
    assert max(i for i, k in enumerate(kinds) if k in ("copy", "new")) < kinds.index(
        "remove"
    )
    assert l1.guidelines[0].style == "coloured tagged" and l1.guidelines[0] is not keep
    assert kinds.count("notify") == 1 and kinds.count("init") == 3


def test_exact_noop_does_not_preflight_or_create_history(owned):
    o = owned
    g = o.Glyph()
    guide = o.guide((0, 4, 0, "kept"))
    layer = o.Layer([guide])
    assert api.replace_guides(o.package, [(g, layer, [guide.record])]) == {"layers": 0}
    assert api.clear(o.package, [(g, layer, [guide])]) == {
        "layers": 0,
        "removed": 0,
        "left": 0,
    }
    assert not o.events and layer.guidelines == [guide]


def test_unsafe_batch_refuses_before_copy_creation_history_or_mutation(
    owned, monkeypatch
):
    o = owned
    layer = o.Layer([o.guide((0, 1, 0, "old"))])

    def refuse(*args):
        raise ValueError("automatic dependants")

    monkeypatch.setattr(api, "require_safe_targets", refuse)
    with pytest.raises(ValueError, match="automatic dependants"):
        api.replace_guides(o.package, [(o.Glyph(), layer, [])])
    assert not o.events and len(layer.guidelines) == 1


def test_bad_later_native_construction_preserves_complete_batch(owned, monkeypatch):
    o = owned
    l1 = o.Layer([])
    l2 = o.Layer([])

    def create(r):
        if r[1] == 9:
            raise ValueError("bad later guide")
        return o.guide(r)

    monkeypatch.setattr(api, "new_guide", create)
    with pytest.raises(ValueError, match="bad later guide"):
        api.replace_guides(
            o.package,
            [(o.Glyph(), l1, [(0, 8, 0, "ok")]), (o.Glyph(), l2, [(0, 9, 0, "bad")])],
        )
    assert not l1.guidelines and not l2.guidelines
    assert [e[0] for e in o.events] == ["preflight"]


def test_clear_uses_complete_retained_native_guide_and_reports_actual_counts(owned):
    o = owned
    g = o.Glyph()
    keep = o.guide((3, 0, 90, "keep"), "colour tags raw geometry")
    layer = o.Layer([o.guide((0, 1, 0, "drop")), keep])
    assert api.clear(o.package, [(g, layer, [keep])]) == {
        "layers": 1,
        "removed": 1,
        "left": 0,
    }
    assert layer.guidelines[0].style == keep.style and layer.guidelines[0] is not keep


def test_target_records_merge_replace_and_zero_width_follow_original_rules(monkeypatch):
    import fontlabapp.guides.records as records

    monkeypatch.setattr(records, "guide_record", lambda guide: guide.record)
    h = NS(record=(0.0, 17.0, 0.0, "h"), isHint=False)
    v = NS(record=(50.0, 0.0, 90.0, "v"), isHint=False)
    source = NS(advanceWidth=100, guidelines=[h, v])
    target = NS(advanceWidth=200, guidelines=[h])
    assert api.target_records(source, target, False, True) == [
        h.record,
        (100.0, 0.0, 90.0, "v"),
    ]
    assert api.target_records(source, target, True, False) == [h.record, v.record]
    target.advanceWidth = 0
    assert api.target_records(source, target, False, True) is None
    assert api.target_records(source, target, True, False) == [h.record, v.record]


def test_direct_auto_layer_refuses_before_preflight_and_history(owned):
    o = owned
    layer = o.Layer([o.guide((0, 1, 0, "old"))])
    layer.autoLayer = True
    with pytest.raises(ValueError, match="automatic layers"):
        api.replace_guides(o.package, [(o.Glyph(), layer, [])])
    assert not o.events and len(layer.guidelines) == 1


def test_partial_native_failure_still_records_one_undo_and_update(owned, monkeypatch):
    o = owned
    g = o.Glyph()
    layer = o.Layer([o.guide((0, 1, 0, "old"))])

    def fail(values):
        raise RuntimeError("append failed after native removal")

    monkeypatch.setattr(layer, "appendGuidelines", fail)
    with pytest.raises(RuntimeError, match="append failed"):
        api.replace_guides(o.package, [(g, layer, [(0, 2, 0, "new")])], "Owned failure")
    assert not layer.guidelines
    assert g.lastModified == "UTC stamp"
    assert o.events[-2:] == [("notify", "Owned failure", [layer, g]), ("update",)]
