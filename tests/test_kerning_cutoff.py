# this_file: tests/test_kerning_cutoff.py
"""Independent original-contract oracle and actual shared transaction controls."""

from copy import deepcopy

import fontlabapp.kerning.batch as kerning_batch
import fontlabapp.kerning.cutoff as cutoff
import fontlabapp.core.scripting as scripting
import pytest
from test_kerning_batch import font_double


def test_full_boundary_oracle_all_explicit_kinds_and_stored_order():
    pairs = {}
    kinds = [("A", "V"), ("@L_A", "V"), ("A", "@R_V"), ("@L_A", "@R_V")]
    for i in range(-2001, 2002):
        value = i / 4
        pairs[str(i)] = {pair: value for pair in kinds}
    result = cutoff.plan(pairs)
    assert list(result) == list(pairs)
    for master, values in pairs.items():
        expected = {}
        for pair, amount in values.items():
            if amount < -250:
                expected[pair] = -250
            elif amount > 100:
                expected[pair] = 100
        assert result[master] == expected
    assert cutoff.plan({"Empty": {}, "Zero": {("A", "V"): 0}}) == {
        "Empty": {},
        "Zero": {},
    }


@pytest.mark.parametrize(
    "value", [True, "3", None, float("inf"), float("-inf"), float("nan")]
)
def test_bad_source_amount_refused(value):
    with pytest.raises(ValueError, match="finite"):
        cutoff.plan({"Regular": {("A", "V"): value}})


def test_expired_deadline_refuses_empty_or_quiet_source():
    for facts in ({}, {"Empty": {}}, {"Quiet": {("A", "V"): 10}}):
        with pytest.raises(TimeoutError):
            cutoff.plan(facts, deadline=-1)


@pytest.mark.parametrize("changed", ["first", "last", "both", "none"])
def test_real_batch_any_master_repair_preserves_kinds_zero_absence_and_history(
    monkeypatch, changed
):
    font, kerns, history, _ = font_double(monkeypatch)
    for index, (master, kern) in enumerate(kerns.items()):
        value = (
            -251
            if changed == "both"
            or (changed == "first" and index == 0)
            or (changed == "last" and index == 1)
            else -250
        )
        kern.values = {
            ("A", "V"): value,
            ("@L_A", "V"): 101 if value == -251 else 100,
            ("A", "@R_V"): -1000 if value == -251 else -250,
            ("@L_A", "@R_V"): 1000 if value == -251 else 100,
            ("T", "V"): 0,
        }
    before = deepcopy({m: k.values for m, k in kerns.items()})
    groups = deepcopy({m: k.groups for m, k in kerns.items()})
    result = cutoff.apply(font)
    assert result == {m: 4 if before[m]["A", "V"] == -251 else 0 for m in kerns}
    wanted = {
        m: {pair: max(-250, min(100, value)) for pair, value in values.items()}
        for m, values in before.items()
    }
    assert {m: k.values for m, k in kerns.items()} == wanted
    assert {m: k.groups for m, k in kerns.items()} == groups
    assert font.master == "Bold"
    assert history == ([] if changed == "none" else [before, wanted])
    assert all(
        ("V", "A") not in k.values and k.values["T", "V"] == 0 for k in kerns.values()
    )


@pytest.mark.parametrize("mutation", ["master", "class", "pair", "font"])
def test_stale_whole_snapshot_refuses_before_history(monkeypatch, mutation):
    font, kerns, history, state = font_double(monkeypatch)
    kerns["Light"].values["A", "V"] = -251
    snapshot = kerning_batch.snapshot_kerning(font)
    if mutation == "master":
        font.masters.append("Other")
    elif mutation == "class":
        kerns["Light"].groups["L_A"] = (["T"], "KernLeft")
    elif mutation == "pair":
        kerns["Bold"].values["A", "V"] = 101
    else:
        state.package = None
    before = deepcopy({m: k.values for m, k in kerns.items()})
    with pytest.raises(ValueError):
        cutoff.apply(font, expected=snapshot)
    assert history == [] and {m: k.values for m, k in kerns.items()} == before


def test_fractional_history_refusal_retains_source(monkeypatch):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].values["A", "V"] = -250.5
    before = deepcopy({m: k.values for m, k in kerns.items()})
    with pytest.raises(ValueError, match="fractional"):
        cutoff.apply(font)
    assert history == [] and {m: k.values for m, k in kerns.items()} == before


def test_failed_later_master_keeps_undo_and_no_success_report(monkeypatch, capsys):
    font, kerns, history, _ = font_double(monkeypatch)
    for kern in kerns.values():
        kern.values["A", "V"] = 101
    kerns["Bold"].fail = True
    with pytest.raises(RuntimeError, match="partially changed.*Undo"):
        cutoff.run()
    assert len(history) == 2 and history[0] != history[1]
    assert capsys.readouterr().out == ""


def test_public_run_reports_all_master_counts_after_success(monkeypatch, capsys):
    font, kerns, history, _ = font_double(monkeypatch)
    kerns["Light"].values["A", "V"] = -251
    assert cutoff.run() == {"Light": 1, "Bold": 0}
    text = capsys.readouterr().out
    assert text.index("Light") < text.index("Bold")
    assert "Light: 1" in text and "Bold: 0" in text and "[-250, 100]" in text
    assert len(history) == 2


def test_missing_font_refuses_without_output(monkeypatch, capsys):
    monkeypatch.setattr(scripting, "current_package", lambda: None)
    with pytest.raises(ValueError, match="Open a font"):
        cutoff.run()
    assert capsys.readouterr().out == ""
