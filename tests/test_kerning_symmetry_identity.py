# this_file: tests/test_kerning_symmetry_identity.py
"""Original typed-mode, wrong-math, hidden-stale and master-filter regressions."""

from copy import deepcopy
from types import SimpleNamespace as NS

import fontlabapp.kerning.symmetry.model as model
import fontlabapp.kerning.symmetry.native as native
import pytest
from kerning_identity_fixture import C, G, owned_font


def raw_font(monkeypatch, reverse=False, target_at=False):
    font, kerns, history = owned_font(monkeypatch)
    names = tuple(
        token[1:] if token.startswith("/") else "u" + str(ord(token))
        for token in model.TOKENS
    )
    glyphs = {
        name: NS(id=i + 1, name=name, isNull=False)
        for i, name in enumerate((*names, "@Share", "@innocent"))
    }
    mapped = dict(
        zip(
            (ord(t) for t in model.TOKENS[7:]),
            (glyphs[n] for n in names[7:]),
            strict=True,
        )
    )
    if target_at:
        mapped[ord("A")] = glyphs["@Share"]
    font.findName = glyphs.get
    font.findUnicode = mapped.get

    class Groups(dict):
        def asDict(self):
            return dict(self)

    a = "@Share" if target_at else names[7]
    v = names[8]
    groups = Groups(
        {"Share": ([names[7]], "KernLeft"), "dummy": ([names[9]], "KernRight")}
    )
    raw = [
        ((("Share", C), (v, G)), 5),
        (((v, G), (a, G)), 40),
        ((("@Share", G), (v, G)), 17),
    ]
    if target_at:
        raw = [
            (((a, G), (v, G)), 5),
            (((v, G), (a, G)), 40),
            ((("Share", C), (v, G)), 17),
        ]
    for k in kerns.values():
        k.groups = deepcopy(groups)
        k.values = {}
    kerns["Regular"].values = dict(reversed(raw) if reverse else raw)
    return font, kerns, history, names, a, v


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("target_at", [False, True])
def test_complete_symmetry_uses_exact_modes_not_shadowed_value(
    monkeypatch, reverse, target_at
):
    font, kerns, history, _names, a, v = raw_font(monkeypatch, reverse, target_at)
    before = deepcopy({m: k.values for m, k in kerns.items()})
    result = native.run()
    forward = ((a, G), (v, G)) if target_at else (("Share", C), (v, G))
    reverse_key = ((v, G), (a, G))
    assert kerns["Regular"].values[forward] == 20
    assert kerns["Regular"].values[reverse_key] == 20
    untouched = (("Share", C), (v, G)) if target_at else (("@Share", G), (v, G))
    assert kerns["Regular"].values[untouched] == 17
    assert len(history) == 2 and history[0] == before and font.master == "#Bold"
    assert result["masters"][0]["comparisons"] == 378
    assert result["skipped_masters"] == ["#Bold"]
    assert not native.run()["applied"] and len(history) == 2


@pytest.mark.parametrize("side", [0, 1])
def test_capture_detects_raw_shadowed_pair_drift_before_any_history(monkeypatch, side):
    font, kerns, history, _names, _a, v = raw_font(monkeypatch)
    pair = (("@Share", G), (v, G)) if side == 0 else ((v, G), ("@Share", G))
    shadow = (("Share", C), (v, G)) if side == 0 else ((v, G), ("Share", C))
    kerns["Regular"].values[pair] = 101
    kerns["Regular"].values[shadow] = 100
    first = native.capture(font, lambda: None)
    kerns["Regular"].values[pair] = 102
    assert native.capture(font, lambda: None) != first
    original = native.capture
    calls = []

    def capture(*args):
        if calls:
            kerns["Regular"].values[pair] += 1
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(native, "capture", capture)
    with pytest.raises(ValueError, match="changed"):
        native.run()
    assert not history


def test_symmetry_original_hash_and_case_sensitive_ctr_filter_is_not_cutoff_policy(
    monkeypatch,
):
    font, kerns, history, _names, _a, _v = raw_font(monkeypatch)
    regular = kerns["Regular"]
    font.masters = ["Regular", "Ctr", "ctr", "Aux#Layer"]
    font.master = "Regular"
    kerns.update({m: deepcopy(regular) for m in font.masters[1:]})
    before = deepcopy({m: k.values for m, k in kerns.items()})
    result = native.run()
    assert [m["master"] for m in result["masters"]] == ["Regular", "ctr"]
    assert result["skipped_masters"] == ["Ctr", "Aux#Layer"]
    assert (
        kerns["Ctr"].values == before["Ctr"]
        and kerns["Aux#Layer"].values == before["Aux#Layer"]
    )
    assert len(history) == 2


def test_full_typed_diagnostics_are_json_values_on_real_result_surface(monkeypatch):
    import json

    raw_font(monkeypatch)
    result = native.run()
    assert json.loads(json.dumps(result)) == result
