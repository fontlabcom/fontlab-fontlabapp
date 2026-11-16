# this_file: tests/test_kerning_identity.py
"""Keep native glyph/group identities distinct through the real shared batch."""

from copy import deepcopy

import fontlabapp.kerning.batch as batch
import fontlabapp.kerning.cutoff as cutoff
import pytest
from fontlabapp.core import scripting
from kerning_identity_fixture import C, G, owned_font


@pytest.mark.parametrize("reverse", [False, True])
def test_cutoff_preserves_all_native_modes_and_both_collision_orders(
    monkeypatch, reverse
):
    font, kerns, history = owned_font(monkeypatch, reverse)
    before = deepcopy({m: k.values for m, k in kerns.items()})
    assert cutoff.apply(font) == {"Regular": 2, "#Bold": 2}
    wanted = {
        m: {p: max(-250, min(100, v)) for p, v in rows.items()}
        for m, rows in before.items()
    }
    assert {m: k.values for m, k in kerns.items()} == wanted
    assert history == [before, wanted] and font.master == "#Bold"
    assert cutoff.apply(font) == {"Regular": 0, "#Bold": 0}
    assert len(history) == 2


def test_typed_snapshot_zero_delete_absence_and_class_validation(monkeypatch):
    font, kerns, history = owned_font(monkeypatch)
    snapshot = batch.snapshot_kerning(font, typed=True)
    glyph = (("@L", G), ("V", G))
    group = (("L", C), ("V", G))
    absent = (("@L", G), ("@R", G))
    changes = {"Regular": {glyph: 0, group: None, absent: 0}}
    assert batch.write_kerning(font, changes, "Identity edit", expected=snapshot)
    assert kerns["Regular"].values[glyph] == 0 and kerns["Regular"].values[absent] == 0
    assert group not in kerns["Regular"].values and len(history) == 2
    snapshot = batch.snapshot_kerning(font, typed=True)
    with pytest.raises(ValueError, match="class"):
        batch.write_kerning(
            font, {"Regular": {(("R", C), ("V", G)): 1}}, "bad", expected=snapshot
        )
    assert len(history) == 2


@pytest.mark.parametrize("side", [0, 1])
def test_typed_stale_fence_sees_hidden_glyph_changes_before_history(monkeypatch, side):
    font, kerns, history = owned_font(monkeypatch)
    snapshot = batch.snapshot_kerning(font, typed=True)
    pair = (("@L", G), ("V", G)) if side == 0 else (("A", G), ("@R", G))
    kerns["Regular"].values[pair] += 1
    with pytest.raises(ValueError, match="stale"):
        batch.write_kerning(font, {"Regular": {pair: 10}}, "stale", expected=snapshot)
    assert not history


def test_typed_failure_retains_partial_undo_diagnosis_and_no_counts(
    monkeypatch, capsys
):
    _font, kerns, history = owned_font(monkeypatch)
    kerns["#Bold"].fail = True
    with pytest.raises(RuntimeError, match="partially changed; use Undo"):
        cutoff.run()
    assert len(history) == 2 and capsys.readouterr().out == ""
    assert kerns["Regular"].values[(("@L", G), ("V", G))] == 100


def test_legacy_reader_refuses_ambiguous_glyph_instead_of_silent_alias(monkeypatch):
    font, _, history = owned_font(monkeypatch)
    with pytest.raises(ValueError, match="typed"):
        scripting.kerning_pairs(font, "Regular")
    assert not history


@pytest.mark.parametrize(
    "pair",
    [
        (("@L", G), ("V", G)),
        (("L", C), ("V", G)),
        (("A", G), ("@R", G)),
        (("A", G), ("R", C)),
        (("L", C), ("R", C)),
    ],
)
def test_additive_typed_programmatic_writer_needs_no_explicit_snapshot(
    monkeypatch, pair
):
    font, kerns, history = owned_font(monkeypatch)
    assert batch.write_kerning(font, {"Regular": {pair: 12}}, "typed")
    assert kerns["Regular"].values[pair] == 12 and len(history) == 2


def test_mixed_input_forms_are_canonicalized_before_native_readback(monkeypatch):
    font, kerns, history = owned_font(monkeypatch)
    snapshot = batch.snapshot_kerning(font, typed=True)
    assert batch.write_kerning(
        font, {"Regular": {("@L", "V"): 13}}, "legacy class spelling", expected=snapshot
    )
    assert kerns["Regular"].values[(("L", C), ("V", G))] == 13
    assert kerns["Regular"].values[(("@L", G), ("V", G))] == 101
    snapshot = batch.snapshot_kerning(font, typed=True)
    with pytest.raises(ValueError, match="Repeated"):
        batch.write_kerning(
            font,
            {"Regular": {("@L", "V"): 14, (("L", C), ("V", G)): 15}},
            "alias",
            expected=snapshot,
        )
    assert len(history) == 2


@pytest.mark.parametrize(
    "bad", [None, 1, (), ("", "glyphMode"), ("A", "unknown"), (False, "glyphMode")]
)
def test_bad_explicit_sides_fail_before_history(monkeypatch, bad):
    font, _, history = owned_font(monkeypatch)
    snapshot = batch.snapshot_kerning(font, typed=True)
    with pytest.raises(ValueError):
        batch.write_kerning(
            font, {"Regular": {(bad, ("V", G)): 10}}, "bad side", expected=snapshot
        )
    assert not history


def test_typed_mutation_of_class_or_master_still_stales_whole_snapshot(monkeypatch):
    font, kerns, history = owned_font(monkeypatch)
    snapshot = batch.snapshot_kerning(font, typed=True)
    kerns["#Bold"].groups["L"] = (["V"], "KernLeft")
    with pytest.raises(ValueError, match="stale"):
        cutoff.apply(font, expected=snapshot)
    assert not history


def test_typed_fractional_source_and_save_range_refuse_before_history(monkeypatch):
    font, kerns, history = owned_font(monkeypatch)
    kerns["#Bold"].values[(("A", G), ("V", G))] = 0.5
    with pytest.raises(ValueError, match="fractional"):
        cutoff.apply(font)
    assert not history
    kerns["#Bold"].values[(("A", G), ("V", G))] = 0
    font.upm = 1
    with pytest.raises(ValueError, match="save/reopen"):
        cutoff.apply(font)
    assert not history
