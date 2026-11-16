# this_file: tests/test_mark_colour_selection.py
"""Pedro's initial-colour additive policy, including filtered native cells."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace as NS

import fontlabapp.glyphs.selection._mark_colors_native as native
import fontlabapp.glyphs.selection.mark_colors as api
import pytest


@pytest.mark.parametrize(
    "marks, selected, expected",
    [
        ([], [], ()),
        ([0, 60, 120], [], ()),
        ([0, 60, 120], [0], (1, 2)),
        ([0, 60, 120, 60], [0, 1], (2,)),
        ([0, 0, 0], [0], ()),
        ([60, 60, 120], [0], (2,)),
        ([-1, 0, 360], [1], (0, 2)),
    ],
)
def test_plan_keeps_original_colour_set(marks, selected, expected):
    rows = tuple(
        api.GlyphMark(i, f"g{i}", m, i in selected) for i, m in enumerate(marks)
    )
    assert api.plan(rows) == expected
    if rows:
        with pytest.raises(FrozenInstanceError):
            rows[0].mark = 7


def fixture(
    monkeypatch, *, visible=(0, 1, 2, 3), selected=(0,), marks=(0, 60, 120, 60)
):
    panel = object()
    package = NS(id=7, isNull=False)
    workspace = NS(activeFontPanel=panel, currentPackage=package)  # flWorkspace has no activePackage
    glyphs = [NS(name=f"g{i}", mark=m) for i, m in enumerate(marks)]
    state = set(selected)
    calls = []
    before = []

    def select(index, value=1):
        calls.append((index, value))
        if index in visible:
            if value:
                state.add(index)
            else:
                state.discard(index)

    fl = NS(font=glyphs, Selected=lambda i: i in state, Select=select)

    def guard(pid):
        before.append(pid)
        if workspace.activeFontPanel is not panel:
            raise ValueError("Activate the Font window")

    monkeypatch.setattr(
        native,
        "current_package",
        lambda pid=None: package if pid in (None, 7) else None,
    )
    monkeypatch.setattr(native, "_require_selection_window", guard)
    monkeypatch.setattr(
        native,
        "_native",
        lambda n: (
            NS(fl=fl) if n == "FL" else NS(flWorkspace=NS(instance=lambda: workspace))
        ),
    )
    return NS(
        panel=panel,
        package=package,
        workspace=workspace,
        fl=fl,
        state=state,
        calls=calls,
        glyphs=glyphs,
        guards=before,
    )


def test_filtered_cells_and_initial_multicolour_set(monkeypatch):
    f = fixture(monkeypatch, visible=(0, 1, 3), selected=(0, 1))
    assert api.select_different_mark_colours() == ()
    assert f.state == {0, 1} and f.calls == [(2, 1)]
    f = fixture(monkeypatch, visible=(0, 1, 2), selected=(0,))
    assert api.select_different_mark_colours() == ("g1", "g2")
    assert f.state == {0, 1, 2} and f.calls == [(1, 1), (2, 1), (3, 1)]


def test_empty_selection_and_one_colour_are_noops(monkeypatch):
    for selection, marks in [((), (0, 60)), ((0,), (60, 60))]:
        f = fixture(monkeypatch, selected=selection, marks=marks)
        assert api.select_different_mark_colours() == ()
        assert not f.calls and f.state == set(selection)


def test_no_font_and_wrong_window_refuse_before_writes(monkeypatch):
    f = fixture(monkeypatch)
    monkeypatch.setattr(native, "current_package", lambda *a: None)
    with pytest.raises(ValueError, match="font"):
        api.select_different_mark_colours()
    assert not f.calls
    f = fixture(monkeypatch)
    f.workspace.activeFontPanel = None
    with pytest.raises(ValueError, match="Font window"):
        api.select_different_mark_colours()
    assert not f.calls and f.state == {0}


@pytest.mark.parametrize("change", ["mark", "selection", "name", "package", "panel"])
def test_metadata_or_selection_changed_before_apply_refuses(monkeypatch, change):
    f = fixture(monkeypatch)
    original = api.plan

    def plan(rows):
        result = original(rows)
        if change == "mark":
            f.glyphs[1].mark = 3
        elif change == "selection":
            f.state.add(1)
        elif change == "name":
            f.glyphs[1].name = "changed"
        elif change == "package":
            f.workspace.currentPackage = NS(id=99)
        else:
            f.workspace.activeFontPanel = None
        return result

    with monkeypatch.context() as patch:
        patch.setattr(api, "plan", plan)
        with pytest.raises(ValueError):
            api.select_different_mark_colours()
    assert not f.calls


def test_late_setter_failure_rolls_back_only_new_selection(monkeypatch):
    f = fixture(monkeypatch)
    original = f.fl.Select

    def fail(index, value=1):
        original(index, value)
        if index == 2 and value:
            raise RuntimeError("owned setter error")

    f.fl.Select = fail
    with pytest.raises(RuntimeError, match="restored"):
        api.select_different_mark_colours()
    assert f.state == {0}


def test_incomplete_or_unsafe_rollback_is_reported(monkeypatch):
    f = fixture(monkeypatch)
    original = f.fl.Select

    def fail(index, value=1):
        original(index, value)
        if index == 1:
            if value:
                f.workspace.activeFontPanel = None
            raise RuntimeError("owned error")

    f.fl.Select = fail
    with pytest.raises(RuntimeError, match="may remain"):
        api.select_different_mark_colours()
    assert f.state == {0, 1}


def test_invalid_selected_value_refuses(monkeypatch):
    f = fixture(monkeypatch)
    f.fl.Selected = lambda i: None
    with pytest.raises(ValueError, match="selection"):
        api.select_different_mark_colours()
    assert not f.calls


def test_selected_colour_set_does_not_grow_during_iteration(monkeypatch):
    f = fixture(monkeypatch, marks=(0, 60, 60, 120))
    assert api.select_different_mark_colours() == ("g1", "g2", "g3")
    assert f.state == {0, 1, 2, 3}
    assert api.select_different_mark_colours() == ()


def test_unrelated_selection_change_is_rejected_and_rolls_back(monkeypatch):
    f = fixture(monkeypatch, marks=(0, 0, 60))
    original = f.fl.Select

    def bad(index, value=1):
        original(index, value)
        if value:
            f.state.add(1)

    f.fl.Select = bad
    with pytest.raises(RuntimeError, match="restored"):
        api.select_different_mark_colours()
    assert f.state == {0}


def test_lost_initial_selection_is_not_falsely_reported_restored(monkeypatch):
    f = fixture(monkeypatch)
    original = f.fl.Select

    def bad(index, value=1):
        original(index, value)
        if value:
            f.state.discard(0)

    f.fl.Select = bad
    with pytest.raises(RuntimeError, match="may remain"):
        api.select_different_mark_colours()
    assert 0 not in f.state


def test_stale_current_package_guard_refuses(monkeypatch):
    f = fixture(monkeypatch)
    calls = []

    def package(pid=None):
        calls.append(pid)
        return f.package if pid is None else None

    monkeypatch.setattr(native, "current_package", package)
    with pytest.raises(ValueError, match="changed"):
        api.select_different_mark_colours()
    assert not f.calls
