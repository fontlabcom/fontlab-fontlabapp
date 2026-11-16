# this_file: tests/test_alignment_zones.py
"""Independent owned controls for the complete alignment-zone staging contract."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from fontlabapp.metrics.zones.model import Editor, extent, parse_rows, suggest
from fontlabapp.metrics.zones.data import Master, Snapshot, Zone, Zones


@pytest.fixture
def editor():
    return Editor(
        Snapshot(
            31,
            "Regular",
            (
                Master("Thin", 400.5, 650.5, Zones((Zone(650, 12, "cap"),), ())),
                Master(
                    "Regular",
                    500.5,
                    700.5,
                    Zones(
                        (Zone(700, 15, "cap"), Zone(500, 12, "x"), Zone(500, 12, "x")),
                        (Zone(0, 12, "base"),),
                    ),
                ),
            ),
        )
    )


def test_complete_initial_order_duplicates_and_immutable_baseline(editor):
    assert editor.rows("Regular") == (
        ("Top", 700, 15, "cap"),
        ("Top", 500, 12, "x"),
        ("Top", 500, 12, "x"),
        ("Bottom", 0, 12, "base"),
    )
    assert editor.pending() == () and editor.plan() == ()
    with pytest.raises(FrozenInstanceError):
        editor.snapshot.current_master = "Thin"


def test_stage_all_masters_normalizes_source_numbers_kind_and_width(editor):
    edited = editor.stage("Regular", (("bottom edge", "-0.5", "-11.5", "é"),))
    edited = edited.stage("Thin", (("other", "400.5", "12.5", ""),))
    assert editor.pending() == (), "Editing must not mutate a prior staged plan"
    assert edited.rows("Regular") == (("Bottom", 0, 12, "é"),)
    assert edited.rows("Thin") == (("Top", 400, 12, ""),)
    assert edited.pending() == ("Thin", "Regular"), (
        "Apply must retain source master order"
    )
    changes = edited.plan()
    assert changes[0].before == editor.snapshot.masters[0].zones
    assert changes[1].after == Zones((), (Zone(0, 12, "é"),))


@pytest.mark.parametrize(
    "bad", ["", "oops", "nan", "inf", "-inf", None, True, nan, inf]
)
@pytest.mark.parametrize("column", [1, 2])
def test_invalid_numeric_row_rejects_whole_proposal_and_retains_all_stages(
    editor, bad, column
):
    edited = editor.add("Thin", "Bottom")
    rows = [list(row) for row in edited.rows("Regular")]
    rows[-1][column] = bad
    before = edited.plan()
    with pytest.raises(ValueError, match="row 4"):
        edited.stage("Regular", rows)
    assert edited.plan() == before and edited.pending() == ("Thin",)


def test_row_order_changes_do_not_create_false_dirty_masters(editor):
    assert editor.stage("Regular", reversed(editor.rows("Regular"))).pending() == ()
    assert editor.stage("Thin", editor.rows("Thin")).plan() == ()


def test_add_defaults_remove_multiple_selected_rows_and_restore_noop(editor):
    edited = editor.add("Regular", "Top").add("Thin", "Bottom")
    assert ("Top", 500, 12, "T: 500") in edited.rows("Regular"), "Add names the row as FontLab does"
    assert ("Bottom", 0, 12, "B: 0") in edited.rows("Thin"), "Add names the row as FontLab does"
    edited = edited.remove("Regular", [0, 2, 2])
    assert len(edited.rows("Regular")) == 3
    assert edited.rows("Thin")[-1] == ("Bottom", 0, 12, "B: 0"), "the added bottom row stays"
    assert edited.remove("Thin", [1]).pending() == ("Regular",)
    assert editor.remove("Regular", []).plan() == ()


@pytest.mark.parametrize("selection", [[-1], [4], [True], [0.5], ["1"]])
def test_remove_rejects_invalid_rows_without_changing_state(editor, selection):
    with pytest.raises(ValueError, match="selection"):
        editor.remove("Regular", selection)
    assert editor.plan() == ()


def test_suggest_uses_max_undershoot_both_heights_rounding_and_replaces_one_master(
    editor,
):
    edited = editor.add("Thin", "Bottom")
    result = edited.suggest("Regular", (-12.5, 512.1), (-14.6, 714.0))
    assert result.rows("Regular") == (
        ("Top", 700, 14, "cap height"),
        ("Top", 500, 12, "x-height"),
        ("Bottom", 0, 15, "baseline"),
    )
    assert result.zones("Thin") == edited.zones("Thin")
    assert result.pending() == ("Thin", "Regular")


@pytest.mark.parametrize(
    "lower,upper,expected",
    [
        (None, None, Zones()),
        ((0, 400), (0, 650), Zones()),
        ((10, 600), None, Zones((Zone(500, 100, "x-height"),), ())),
        (None, (-10, 690), Zones((), (Zone(0, 10, "baseline"),))),
    ],
)
def test_missing_no_overshoot_and_single_glyph_suggestions(lower, upper, expected):
    assert suggest(500, 700, lower, upper) == expected


@pytest.mark.parametrize("height", [0, -1, -1e20])
def test_flat_or_nonpositive_height_has_no_extent(height):
    assert extent(-12.5, height) is None


def test_fractional_negative_and_large_finite_extents_and_empty_named_rows():
    assert extent(-12.5, 725.25) == (-12.5, 712.75)
    assert extent(-1e100, 2e100) == (-1e100, 1e100)
    assert parse_rows(()) == Zones()
    assert parse_rows((("", -1.5, -2.5, ""),)) == Zones((Zone(-2, 2, ""),), ())


@pytest.mark.parametrize(
    "operation",
    [
        lambda e: e.rows("absent"),
        lambda e: e.add("absent", "Top"),
        lambda e: e.stage("absent", ()),
        lambda e: e.remove("absent", []),
        lambda e: e.suggest("absent", None, None),
        lambda e: e.add("Thin", "side"),
    ],
)
def test_unknown_master_or_kind_is_refused(editor, operation):
    with pytest.raises(ValueError):
        operation(editor)
    assert editor.pending() == ()


@pytest.mark.parametrize(
    "rows",
    [
        (("Top", 1, 2),),
        (("Top", 1, 2, None),),
        ((None, 1, 2, ""),),
        (("Top", 1, 2, "\x00"),),
        (("Top", 1, 2, "\ud800"),),
    ],
)
def test_malformed_cells_are_diagnosed_instead_of_dropped(rows):
    with pytest.raises(ValueError, match="row 1"):
        parse_rows(rows)


@pytest.mark.parametrize("values", [(nan, 1), (0, inf), (1e308, 1e308)])
def test_nonfinite_extent_input_or_sum_is_refused(values):
    with pytest.raises(ValueError, match="finite"):
        extent(*values)


@pytest.mark.parametrize(
    "arguments",
    [
        (nan, 700, None, None),
        (500, inf, None, None),
        (500, 700, (0, nan), None),
        (500, 700, (2, 1), None),
    ],
)
def test_suggest_rejects_invalid_metric_or_extent(arguments):
    with pytest.raises(ValueError):
        suggest(*arguments)


@pytest.mark.parametrize(
    "current,masters",
    [
        ("Regular", ()),
        ("absent", (Master("Thin", 400, 700),)),
        ("Thin", (Master("Thin", 400, 700), Master("Thin", 500, 700))),
    ],
)
def test_invalid_source_domain_cannot_form_an_editor(current, masters):
    with pytest.raises(ValueError, match="master"):
        Editor(Snapshot(31, current, masters))


def test_original_fractional_values_are_normalized_only_for_staging_and_not_mutated():
    raw = Zones((Zone(500.5, -12.5, ""),), ())
    snapshot = Snapshot(3, "M", (Master("M", 500.5, 700, raw),))
    editor = Editor(snapshot)
    assert editor.rows("M") == (("Top", 500, 12, ""),)
    assert editor.plan() == () and snapshot.masters[0].zones == raw
    plan = editor.add("M", "Bottom").plan()
    assert plan[0].before == raw, (
        "Keep raw baseline for native stale/preservation checks"
    )
    assert plan[0].after == Zones((Zone(500, 12, ""),), (Zone(0, 12, "B: 0"),)), "only the added row is named"


def test_direct_staged_constructor_normalizes_and_refuses_duplicate_or_foreign_master(
    editor,
):
    proposed = Zones((Zone(500.5, -12.5, "new"),), ())
    result = Editor(editor.snapshot, (("Regular", proposed),))
    assert result.rows("Regular") == (("Top", 500, 12, "new"),)
    with pytest.raises(ValueError, match="Duplicate"):
        Editor(editor.snapshot, (("Regular", proposed), ("Regular", proposed)))
    with pytest.raises(ValueError, match="Unknown"):
        Editor(editor.snapshot, (("absent", proposed),))


def test_overshoot_subtraction_overflow_is_diagnosed_before_staging(editor):
    with pytest.raises(ValueError, match="finite"):
        suggest(-1e308, 700, (0, 1e308), None)
    assert editor.pending() == ()


def test_proposal_iterator_failure_does_not_publish_partial_master_changes(editor):
    def interrupted_rows():
        yield ("Top", 500, 12, "first")
        raise RuntimeError("input stopped")

    with pytest.raises(RuntimeError, match="stopped"):
        editor.stage("Regular", interrupted_rows())
    assert editor.pending() == ()


def test_add_when_name_taken_in_kind_then_fontlab_suffix(editor):
    edited = editor.add("Regular", "Top").add("Regular", "Top").add("Regular", "Top")
    names = sorted(row[3] for row in edited.rows("Regular") if row[3].startswith("T: "))
    assert names == ["T: 500", "T: 500.1", "T: 500.2"], f"suffixes as _check_zone_name: {names}"
    bottom = edited.add("Regular", "Bottom").rows("Regular")
    assert ("Bottom", 0, 12, "B: 0") in bottom, "a Top name never makes a Bottom name taken"
