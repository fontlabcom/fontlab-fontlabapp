# this_file: tests/test_kerning_batch.py
"""Owned explicit kerning/history doubles assert atomic preflight and exact batches."""

from copy import deepcopy
from types import SimpleNamespace as NS

import fontlabapp.kerning.batch as batch
import fontlabapp.kerning.edit.model as edit
import pytest
from fontlabapp.core import scripting


def font_double(monkeypatch):
    class Kern:
        def __init__(self, values):
            self.values = values
            self.groups = {"L_A": (["A"], "KernLeft"), "R_V": (["V"], "KernRight")}
            self.fail = False

        def items(self):
            def side(name):
                return NS(
                    id=name.lstrip("@"),
                    mode="groupMode" if name.startswith("@") else "glyphMode",
                )

            return [
                (NS(left=side(a), right=side(b)), value)
                for (a, b), value in self.values.items()
            ]

        def set(self, key, value):
            if self.fail:
                raise RuntimeError("setter failed")
            if value != 0:  # Native zero setter deliberately drops zero.
                self.values[decode(key)] = value

        def remove(self, key):
            self.values.pop(decode(key), None)

        def scale(self, value):
            self.values = {key: amount * value for key, amount in self.values.items()}

    def decode(key):
        return tuple(("@" if mode == "groupMode" else "") + name for name, mode in key)

    kerns = {
        "Light": Kern({("A", "V"): -10, ("T", "V"): 0}),
        "Bold": Kern({("A", "V"): -30, ("T", "V"): -5}),
    }
    history = []
    state = NS(package=None)
    package = NS(
        id=7,
        isNull=False,
        masters=["Light", "Bold"],
        master="Bold",
        upm=1000,
        kerning=kerns.__getitem__,
        findName=lambda name: NS(isNull=False) if name in {"A", "V", "T"} else None,
        checkInitHistoryState=lambda flags: None,
        mastersContainer=lambda: "masters",
        kerningContainer=lambda: "kerning",
    )
    state.package = package

    def checkpoint(name, objects):
        assert objects == [package, "masters", "kerning"], (
            "Only package/containers may enter history"
        )
        history.append(deepcopy({name: k.values for name, k in kerns.items()}))

    native = NS(
        flWorkspace=NS(instance=lambda: NS(currentPackage=state.package)),
        flItems=NS(notifyChangesApplied=checkpoint),
    )
    monkeypatch.setattr(scripting, "_native", lambda name: native)
    monkeypatch.setattr(batch, "_native", lambda name: native)
    return package, kerns, history, state


def test_batch_preflights_later_master_before_any_history_or_write(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    before = deepcopy({m: k.values for m, k in kerns.items()})
    with pytest.raises(ValueError, match="Unknown glyph"):
        batch.write_kerning(
            font, {"Light": {("A", "V"): -11}, "Bold": {("missing", "V"): -12}}, "Edit"
        )
    assert history == [] and {m: k.values for m, k in kerns.items()} == before


def test_batch_one_checkpoint_preserves_zero_presence_unrelated_pairs_and_master(
    monkeypatch,
):
    font, kerns, history, _ = font_double(monkeypatch)
    before = deepcopy({m: k.values for m, k in kerns.items()})
    assert batch.write_kerning(
        font, {"Light": {("A", "V"): -15}, "Bold": {("A", "V"): 0}}, "Edit"
    )
    expected = {
        "Light": {("A", "V"): -15, ("T", "V"): 0},
        "Bold": {("A", "V"): 0, ("T", "V"): -5},
    }
    assert {m: k.values for m, k in kerns.items()} == expected
    assert history == [before, expected], (
        "One before/after checkpoint must include all edited masters"
    )
    assert font.master == "Bold"
    for master in kerns:
        kerns[master].values = deepcopy(history[0][master])
    assert {m: k.values for m, k in kerns.items()} == before, (
        "Owned Undo restores the whole batch"
    )
    for master in kerns:
        kerns[master].values = deepcopy(history[1][master])
    assert {m: k.values for m, k in kerns.items()} == expected, (
        "Owned Redo restores the whole batch"
    )


def test_noop_and_delete_absent_do_not_initialize_history(monkeypatch):
    font, _, history, _ = font_double(monkeypatch)
    font.checkInitHistoryState = lambda _: pytest.fail("No-op initialized history")
    assert not batch.write_kerning(
        font, {"Light": {("A", "V"): -10, ("V", "A"): None}}, "No-op"
    )
    assert not history


@pytest.mark.parametrize("mutation", ["font", "closed", "pairs", "classes", "masters"])
def test_stale_snapshot_refuses_before_mutation(monkeypatch, mutation):
    font, kerns, history, state = font_double(monkeypatch)
    snapshot = batch.snapshot_kerning(font)
    if mutation == "font":
        state.package = NS(id=8, isNull=False)
    elif mutation == "closed":
        state.package = None
    elif mutation == "pairs":
        kerns["Bold"].values["V", "A"] = -1
    elif mutation == "classes":
        kerns["Light"].groups["L_A"] = (["T"], "KernLeft")
    else:
        font.masters.append("Other")
    with pytest.raises(ValueError, match="stale|current"):
        batch.write_kerning(
            font, {"Light": {("A", "V"): -20}}, "Edit", expected=snapshot
        )
    assert not history


@pytest.mark.parametrize(
    "value", [1.5, float("nan"), float("inf"), 2**31, -(2**31) - 1, True]
)
def test_bad_desired_values_fail_before_history(monkeypatch, value):
    font, _, history, _ = font_double(monkeypatch)
    with pytest.raises(ValueError):
        batch.write_kerning(font, {"Light": {("A", "V"): value}}, "Edit")
    assert not history


def test_fractional_history_even_on_unedited_master_is_refused(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Bold"].values["A", "V"] = -30.25
    with pytest.raises(ValueError, match="fractional"):
        batch.write_kerning(font, {"Light": {("A", "V"): -20}}, "Edit")
    assert not history


def test_fractional_refusal_names_master_pair_and_value(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Bold"].values["A", "@R_V"] = -30.25
    with pytest.raises(ValueError) as caught:
        batch.write_kerning(font, {"Light": {("A", "V"): -20}}, "Edit")
    text = str(caught.value)
    assert "Kerning on Bold: A @R_V = -30.25 is not a whole number" in text, text
    assert "no changes applied" in text, text
    assert not history


def test_fractional_refusal_names_the_staged_edit_value(monkeypatch):
    font, _, history, _ = font_double(monkeypatch)
    with pytest.raises(ValueError, match=r"Kerning on Light: A V = -20\.5 is not a whole"):
        batch.write_kerning(font, {"Light": {("A", "V"): -20.5}}, "Edit")
    assert not history


def test_side_text_when_typed_then_group_gets_at_and_glyph_stays_plain():
    assert batch._side_text(("R_V", "groupMode")) == "@R_V"
    assert batch._side_text(("V", "glyphMode")) == "V"
    assert batch._side_text("T") == "T"


def test_fractional_refusal_names_an_existing_pair_on_the_other_master(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].values["T", "V"] = 0.5
    with pytest.raises(ValueError, match=r"Kerning on Light: T V = 0\.5 is not a whole"):
        batch.write_kerning(font, {"Bold": {("A", "V"): -31}}, "Edit")
    assert not history


@pytest.mark.parametrize(
    "pair", [("@R_V", "V"), ("A", "@L_A"), ("@missing", "V"), ("", "V"), ["A", "V"]]
)
def test_pair_structure_and_class_side_fail_before_history(monkeypatch, pair):
    font, _, history, _ = font_double(monkeypatch)
    if isinstance(pair, list):
        with pytest.raises(ValueError):
            batch.validate_pair(font, "Light", pair)
    else:
        with pytest.raises(ValueError):
            batch.write_kerning(font, {"Light": {pair: -20}}, "Edit")
    assert not history


def test_failed_write_retains_after_checkpoint_and_honest_partial_message(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Bold"].fail = True
    with pytest.raises(RuntimeError, match="partially changed.*Undo"):
        batch.write_kerning(
            font, {"Light": {("A", "V"): -20}, "Bold": {("A", "V"): -40}}, "Edit"
        )
    assert len(history) == 2 and history[0] != history[1], (
        "Partial edits must retain native Undo access"
    )


def test_failed_snapshot_does_not_write(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Bold"].items = lambda: (_ for _ in ()).throw(RuntimeError("read failed"))
    with pytest.raises(RuntimeError, match="read failed"):
        batch.write_kerning(font, {"Light": {("A", "V"): -20}}, "Edit")
    assert not history


@pytest.mark.parametrize(
    "value,percent,wanted",
    [(1, 50, 1), (-1, 50, -1), (3, 150, 5), (-3, 150, -5), (0, 0, 0)],
)
def test_half_away_scaling(value, percent, wanted):
    assert edit.scaled(value, percent) == wanted


def test_copy_modes_zero_absence_and_summary():
    source = {("A", "V"): 0, ("T", "V"): -15}
    target = {("A", "V"): 10, ("V", "A"): -1}
    assert edit.copy_plan(source, target, "replace", 100) == {
        ("A", "V"): 0,
        ("T", "V"): -15,
        ("V", "A"): None,
    }
    assert edit.copy_plan(source, target, "missing", 100) == {("T", "V"): -15}
    assert edit.copy_plan(source, target, "matching", 100) == {("A", "V"): 0}
    assert edit.summary(target, edit.copy_plan(source, target, "replace", 100)) == (
        1,
        1,
        1,
    )
    with pytest.raises(ValueError):
        edit.copy_plan(source, target, "unknown", 100)


def test_round_threshold_and_per_master_scale_plans(monkeypatch):
    font, _kerns, _, _ = font_double(monkeypatch)
    assert edit.round_to(-7.5, 5) == -10 and edit.round_to(7.5, 5) == 10
    assert edit.scale_plan(font, ["Light"], 0, True) == {
        "Light": {("A", "V"): (-10, None)}
    }
    assert edit.scale_plan(font, ["Light"], 0, False) == {
        "Light": {("A", "V"): (-10, 0)}
    }
    assert edit.round_plan(font, ["Light"], 20, True) == {
        "Light": {("A", "V"): (-10, -20), ("T", "V"): (0, None)}
    }
    assert edit.small_pairs(font, ["Light", "Bold"], 10) == {
        "Light": [("T", "V", 0)],
        "Bold": [("T", "V", -5)],
    }
    with pytest.raises(ValueError):
        edit.round_to(1, 0)


def test_cell_parsing_bounds_and_invalid_replaces_only_its_own_stage():
    assert edit.parse_cell(" −3 ") == -3 and edit.parse_cell("") is None
    assert edit.parse_cell("2.5") == 2, (
        "Retain the Pair Editor integer-cell rounding contract"
    )
    staged, errors = {(("A", "V"), "Light"): -20, (("T", "V"), "Bold"): -5}, {}
    edit.stage_cell(staged, errors, (("A", "V"), "Light"), "abc", -10)
    assert (
        staged == {(("T", "V"), "Bold"): -5} and errors[(("A", "V"), "Light")] == "abc"
    )
    edit.stage_cell(staged, errors, (("A", "V"), "Light"), "0", -10)
    assert staged[(("A", "V"), "Light")] == 0 and not errors
    for text in ["nan", "inf", str(2**31)]:
        with pytest.raises(ValueError):
            edit.parse_cell(text)


@pytest.mark.parametrize(
    "edits,label",
    [
        ({"Unknown": {}}, "Edit"),
        ({"Light": {("A", "V"): -20}}, ""),
        ({"Light": {("A", "V"): -20}}, "   "),
    ],
)
def test_invalid_master_or_blank_label_changes_nothing(monkeypatch, edits, label):
    font, _, history, _ = font_double(monkeypatch)
    with pytest.raises(ValueError):
        batch.write_kerning(font, edits, label)
    assert not history


def test_native_readback_failure_reports_partial_and_keeps_undo(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].set = lambda key, value: None
    with pytest.raises(RuntimeError, match="partially changed.*Undo.*readback"):
        batch.write_kerning(font, {"Light": {("A", "V"): -21}}, "Edit")
    assert len(history) == 2


def test_class_pair_and_deletion_preserve_unrelated_master(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    untouched = deepcopy(kerns["Bold"].values)
    batch.write_kerning(
        font, {"Light": {("@L_A", "@R_V"): -20, ("T", "V"): None}}, "Class edits"
    )
    assert kerns["Light"].values == {("A", "V"): -10, ("@L_A", "@R_V"): -20}
    assert kerns["Bold"].values == untouched and len(history) == 2


def test_copy_all_modes_run_with_one_native_batch_and_scaled_explicit_zero(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    result = edit.copy_run(font, "Light", ["Bold"], "replace", 150, undo_name="Copy")
    assert result == {"Bold": (0, 2, 0)}
    assert kerns["Bold"].values == {("A", "V"): -15, ("T", "V"): 0}
    assert kerns["Light"].values == {("A", "V"): -10, ("T", "V"): 0}
    assert len(history) == 2


def test_remove_run_checks_every_master_then_writes_once(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    result = edit.remove_run(font, ["Light", "Bold"], 10, undo_name="Remove")
    assert result == {"Light": 1, "Bold": 1}
    assert kerns["Light"].values == {("A", "V"): -10} and kerns["Bold"].values == {
        ("A", "V"): -30
    }
    assert len(history) == 2


def test_unknown_source_master_refused_before_native_accessor(monkeypatch):
    font, _, history, _ = font_double(monkeypatch)
    with pytest.raises(ValueError, match="Unknown.*master"):
        edit.copy_run(font, "Absent", ["Bold"], "replace", 100, undo_name="Copy")
    assert not history


def test_unknown_class_mode_and_null_glyph_are_refused(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].groups["L_A"] = (["A"], "UnknownMode")
    with pytest.raises(ValueError, match="wrong-side"):
        batch.write_kerning(font, {"Light": {("@L_A", "V"): -20}}, "Edit")
    font.findName = lambda name: NS(isNull=True)
    with pytest.raises(ValueError, match="Unknown glyph"):
        batch.write_kerning(font, {"Light": {("A", "V"): -20}}, "Edit")
    assert not history


def test_stale_class_member_when_unrelated_pair_edited_then_write_succeeds(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].values["@L_A", "@R_V"] = -80
    kerns["Light"].groups["L_A"] = (["A", "Aacute"], "KernLeft")  # Aacute absent
    batch.write_kerning(font, {"Light": {("T", "V"): -15}}, "Edit")
    assert kerns["Light"].values[("T", "V")] == -15
    assert kerns["Light"].values[("@L_A", "@R_V")] == -80
    assert history[-1]["Light"][("T", "V")] == -15
    assert history[-1]["Light"][("@L_A", "@R_V")] == -80  # untouched pair kept
    with pytest.raises(ValueError, match="Unknown glyph: Aacute"):
        batch.write_kerning(font, {"Light": {("@L_A", "V"): -20}}, "Edit")


def test_class_sides_involving_and_partner_validation_use_native_side_roles(
    monkeypatch,
):
    font, kerns, _, _ = font_double(monkeypatch)
    kerns["Light"].values["@L_A", "@R_V"] = -80
    assert edit.class_sides(font, "Light", "A") == ("@L_A", None)
    assert edit.involving(font, ["Light"], "A") == {
        ("A", "V"): {"Light": -10},
        ("@L_A", "@R_V"): {"Light": -80},
    }
    assert edit.partner_exists(font, ["Light"], ("@L_A", "V"))
    assert not edit.partner_exists(font, ["Light"], ("@R_V", "V"))
    assert edit.native_side("@L_A") == ("L_A", True)


@pytest.mark.parametrize("value", [-2000, 2000])
def test_exact_native_reopen_range_endpoints_are_accepted(monkeypatch, value):
    font, kerns, history, _ = font_double(monkeypatch)
    assert batch.write_kerning(font, {"Light": {("A", "V"): value}}, "Boundary")
    assert kerns["Light"].values["A", "V"] == value and len(history) == 2


@pytest.mark.parametrize("value", [-2001, 2001])
def test_one_unit_outside_reopen_range_refuses_before_history_or_write(
    monkeypatch, value
):
    font, kerns, history, _ = font_double(monkeypatch)
    before = deepcopy({master: kern.values for master, kern in kerns.items()})
    font.checkInitHistoryState = lambda _: pytest.fail(
        "Range failure initialized history"
    )
    with pytest.raises(ValueError, match="save/reopen range"):
        batch.write_kerning(font, {"Light": {("A", "V"): value}}, "Outside")
    assert (
        not history
        and {master: kern.values for master, kern in kerns.items()} == before
    )


def test_late_master_outside_reopen_range_leaves_earlier_master_untouched(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    before = deepcopy({master: kern.values for master, kern in kerns.items()})
    with pytest.raises(ValueError, match="Bold.*save/reopen range"):
        batch.write_kerning(
            font,
            {"Light": {("A", "V"): -21}, "Bold": {("A", "V"): 2001}},
            "Late invalid",
        )
    assert (
        not history
        and {master: kern.values for master, kern in kerns.items()} == before
    )


def test_untouched_master_outside_range_when_other_master_written_then_allowed(monkeypatch):
    """Only changed masters are range-checked (Scriptmix TODO:80)."""
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Bold"].values["T", "V"] = -2001
    assert batch.write_kerning(font, {"Light": {("A", "V"): -21}}, "Other master")
    assert kerns["Light"].values["A", "V"] == -21 and len(history) == 2
    assert kerns["Bold"].values["T", "V"] == -2001


def test_changed_master_with_existing_outside_value_when_other_pair_written_then_refused(monkeypatch):
    """A changed master still validates its whole final state, untouched extremes included."""
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Bold"].values["T", "V"] = -2001
    with pytest.raises(ValueError, match="Bold.*save/reopen range"):
        batch.write_kerning(font, {"Bold": {("A", "V"): -21}}, "Same master")
    assert not history and kerns["Bold"].values["A", "V"] == -30


@pytest.mark.parametrize("replacement", [None, -2000, 0, 2000])
def test_corrected_or_deleted_existing_outside_value_is_allowed(
    monkeypatch, replacement
):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Bold"].values["T", "V"] = -2001
    batch.write_kerning(
        font,
        {"Light": {("A", "V"): -21}, "Bold": {("T", "V"): replacement}},
        "Repair range",
    )
    assert kerns["Light"].values["A", "V"] == -21 and len(history) == 2
    assert (
        (("T", "V") not in kerns["Bold"].values)
        if replacement is None
        else (kerns["Bold"].values["T", "V"] == replacement)
    )


@pytest.mark.parametrize("upm", [0, -1, float("nan"), float("inf"), None, "1000", True])
def test_invalid_upm_refuses_changing_batch_before_history_or_write(monkeypatch, upm):
    font, kerns, history, _ = font_double(monkeypatch)
    font.upm = upm
    before = deepcopy({master: kern.values for master, kern in kerns.items()})
    with pytest.raises(ValueError, match="units per em"):
        batch.write_kerning(font, {"Light": {("A", "V"): -21}}, "Invalid UPM")
    assert (
        not history
        and {master: kern.values for master, kern in kerns.items()} == before
    )


@pytest.mark.parametrize("upm,value", [(500, 1001), (2000, 4001)])
def test_range_follows_current_font_upm_instead_of_fixed_2000(monkeypatch, upm, value):
    font, _, history, _ = font_double(monkeypatch)
    font.upm = upm
    with pytest.raises(ValueError, match="save/reopen range"):
        batch.write_kerning(font, {"Light": {("A", "V"): value}}, "Current UPM")
    assert not history


def test_true_noop_keeps_existing_outside_values_and_invalid_upm_untouched(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    font.upm = None
    kerns["Bold"].values["T", "V"] = -2001
    before = deepcopy({master: kern.values for master, kern in kerns.items()})
    assert not batch.write_kerning(font, {"Light": {("A", "V"): -10}}, "No-op")
    assert (
        not history
        and {master: kern.values for master, kern in kerns.items()} == before
    )


def test_write_kerning_when_unrecorded_edit_precedes_then_notify_order_pre_then_post(
    monkeypatch,
):
    """An earlier history-less edit gets its own row, so Undo rolls the two back separately."""
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].values[("A", "V")] = -5  # script edit, never notified
    unrecorded = deepcopy({m: k.values for m, k in kerns.items()})
    assert batch.write_kerning(font, {"Light": {("A", "V"): -20}}, "Edit")
    assert len(history) == 2, "Pre-notify then post-notify: two Undo rows"
    assert history[0] == unrecorded, "Pre-notify captures the unrecorded edit alone"
    assert history[1] == {m: k.values for m, k in kerns.items()}
    assert history[1]["Light"][("A", "V")] == -20
def test_stale_class_member_elsewhere_does_not_block_unrelated_edit(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].groups["L_A"] = (["A", "Gone"], "KernLeft")
    kerns["Light"].values[("@L_A", "V")] = -7
    assert batch.write_kerning(font, {"Light": {("T", "V"): 3}}, "Edit"), (
        "A class member absent from the font must not block an unrelated edit"
    )
    assert kerns["Light"].values[("T", "V")] == 3
    assert kerns["Light"].values[("@L_A", "V")] == -7
    assert len(history) == 2


def test_stale_class_member_in_edited_pair_still_refused(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].groups["L_A"] = (["A", "Gone"], "KernLeft")
    with pytest.raises(ValueError, match="Unknown glyph: Gone"):
        batch.write_kerning(font, {"Light": {("@L_A", "V"): 3}}, "Edit")
    assert history == []
