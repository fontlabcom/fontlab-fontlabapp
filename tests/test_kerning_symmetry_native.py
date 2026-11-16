# this_file: tests/test_kerning_symmetry_native.py
"""Actual shared batch/history path with native-shaped exact-domain witnesses."""

from copy import deepcopy
from types import SimpleNamespace as NS

import fontlabapp.kerning.symmetry.model as model
import fontlabapp.kerning.symmetry.native as native
import fontlabapp.proof.reports.model as report_api
import pytest
from test_kerning_batch import font_double


def fixture(monkeypatch):
    font, kerns, history, state = font_double(monkeypatch)
    names = tuple(
        token[1:] if token.startswith("/") else "uni" + str(ord(token))
        for token in model.TOKENS
    )
    glyphs = {
        name: NS(id=i + 100, name=name, isNull=False) for i, name in enumerate(names)
    }
    font.findName = glyphs.get
    font.findUnicode = lambda code: glyphs.get("uni" + str(code))

    class Groups(dict):
        def asDict(self):
            return dict(self)

    for kern in kerns.values():
        kern.groups = Groups({"L": ([], "KernLeft"), "R": ([], "KernRight")})
        kern.values = {}
    kerns["Light"].values[names[0], names[1]] = -17
    return font, kerns, history, state, names


def test_original_action_writes_earlier_master_when_last_unchanged(monkeypatch):
    font, kerns, history, _, names = fixture(monkeypatch)
    report = native.run()
    expected = {(names[0], names[1]): -17, (names[1], names[0]): -17}
    assert kerns["Light"].values == expected and not kerns["Bold"].values
    assert len(history) == 2 and font.master == "Bold"
    assert report["applied"] and report["masters"][0]["mismatches"][0]["warning"]
    assert report["masters"][0]["comparisons"] == 378
    assert report["masters"][1]["mismatches"] == []


def test_zero_deletion_goes_through_complete_writer_without_seeding(monkeypatch):
    _, kerns, history, _, names = fixture(monkeypatch)
    kerns["Light"].values[names[0], names[1]] = 0
    assert native.run()["applied"]
    assert not kerns["Light"].values and len(history) == 2


def test_noop_and_all_skipped_add_no_history(monkeypatch):
    font, kerns, history, _, _ = fixture(monkeypatch)
    kerns["Light"].values.clear()
    assert not native.run()["applied"] and not history
    font.masters = ["Ctr"]
    kerns["Ctr"] = kerns["Light"]
    assert native.run()["skipped_masters"] == ["Ctr"] and not history


@pytest.mark.parametrize("kind", ["unicode", "named", "null", "empty"])
def test_missing_targets_refuse_whole_batch(monkeypatch, kind):
    font, kerns, history, _, _ = fixture(monkeypatch)
    before = deepcopy(kerns["Light"].values)
    if kind == "unicode":
        font.findUnicode = lambda code: None
    elif kind == "named":
        font.findName = lambda name: None
    elif kind == "null":
        font.findUnicode = lambda code: NS(isNull=True)
    else:
        font.findUnicode = lambda code: NS(isNull=False, id=42, name="")
    with pytest.raises(ValueError, match="target|notation"):
        native.run()
    assert not history and kerns["Light"].values == before


@pytest.mark.parametrize("mutation", ["class_order", "glyph_identity", "font", "pairs"])
def test_ordered_source_recapture_precedes_history(monkeypatch, mutation):
    font, kerns, history, state, names = fixture(monkeypatch)
    original = native.capture
    calls = []

    def capture(*args):
        if calls:
            if mutation == "class_order":
                group = kerns["Light"].groups
                group["L"] = group.pop("L")
            elif mutation == "glyph_identity":
                font.findName(names[0]).id += 1
            elif mutation == "font":
                state.package = NS(id=88, isNull=False)
            else:
                kerns["Bold"].values[names[0], names[1]] = -1
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(native, "capture", capture)
    with pytest.raises(ValueError, match="changed|current"):
        native.run()
    assert not history


def test_asdict_order_and_items_membership_disagreement_is_refused(monkeypatch):
    _, kerns, history, _, _ = fixture(monkeypatch)
    kerns["Light"].groups.asDict = lambda: {"different": ([], "KernLeft")}
    with pytest.raises(ValueError, match="groups changed"):
        native.run()
    assert not history


def test_fractional_or_out_of_range_source_keeps_existing_batch_refusals(monkeypatch):
    _, kerns, history, _, names = fixture(monkeypatch)
    kerns["Bold"].values[names[2], names[3]] = 3.5
    with pytest.raises(ValueError, match="fractional"):
        native.run()
    assert not history


def test_failed_late_writer_keeps_honest_partial_diagnosis(monkeypatch):
    _, kerns, history, _, names = fixture(monkeypatch)
    kerns["Bold"].values[names[0], names[1]] = -10
    kerns["Bold"].fail = True
    with pytest.raises(RuntimeError, match="partially changed.*Undo"):
        native.run()
    assert len(history) == 2


def test_deadline_and_no_current_font_refuse_before_history(monkeypatch):
    _, _, history, state, _ = fixture(monkeypatch)
    with pytest.raises(TimeoutError):
        native.run(deadline=-1)
    assert not history
    state.package = None
    with pytest.raises(ValueError, match="font"):
        native.run()


def test_public_report_has_complete_diagnostics_and_no_output_write(monkeypatch):
    fixture(monkeypatch)
    reports_seen = []
    monkeypatch.setattr(
        report_api, "show_report", lambda data, **kw: reports_seen.append((data, kw))
    )
    model.show()
    data, settings = reports_seen[0]
    assert settings == {"title": model.TITLE, "key": model.KEY}
    assert data["applied"] and data["targets"] == list(model.TOKENS)
    assert data["masters"][0]["mismatches"][0]["requested_value"] == -17


def test_error_report_and_postwrite_display_failure_are_distinct(monkeypatch):
    _, _, _, state, _ = fixture(monkeypatch)
    state.package = None
    monkeypatch.setattr(report_api, "show_report", lambda data, **kw: data)
    assert "font" in native.show()["error"]
    fixture(monkeypatch)

    def fail(*args, **kw):
        raise RuntimeError("display unavailable")

    monkeypatch.setattr(report_api, "show_report", fail)
    with pytest.raises(RuntimeError, match="was applied.*Undo.*display"):
        native.show()
    state.package = None


def test_display_failure_preserves_actual_partial_writer_undo_diagnosis(monkeypatch):
    _, kerns, history, _, names = fixture(monkeypatch)
    kerns['Bold'].values[names[0], names[1]] = -19
    kerns['Bold'].fail = True
    def fail(*args, **kwargs):
        raise RuntimeError('display unavailable')
    monkeypatch.setattr(report_api, 'show_report', fail)
    with pytest.raises(RuntimeError, match='partially changed.*Undo.*display'):
        native.show()
    assert len(history) == 2 and kerns['Light'].values[names[1], names[0]] == -17
