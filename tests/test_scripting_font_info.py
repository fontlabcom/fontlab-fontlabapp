# this_file: tests/test_scripting_font_info.py
"""Explicit master plans validate before history and restore on setter failure."""

import importlib
from types import SimpleNamespace as NS

import pytest

scripting = importlib.import_module("fontlabapp.core.scripting")


class Info:
    def __init__(self, package):
        self.package = package

    def __getattr__(self, field):
        return self.package.values[self.package.master][field]

    def __setattr__(self, field, value):
        if field == "package":
            object.__setattr__(self, field, value)
            return
        self.package.events.append(("set", self.package.master, field, value))
        self.package.values[self.package.master][field] = value
        if value == 999:
            raise RuntimeError("owned setter failed after write")


@pytest.fixture
def owned(monkeypatch):
    package = NS(
        id=1,
        isNull=False,
        masters=["Regular", "Bold"],
        master="Bold",
        values={"Regular": {"ascender": 800}, "Bold": {"ascender": 900}},
        events=[],
    )

    def switch(master):
        package.events.append(("master", master))
        package.master = master

    package.setMaster = switch
    package.info = Info(package)
    package.checkInitHistoryState = lambda index: package.events.append(("init", index))
    package.mastersContainer = lambda: "owned-container"
    native = NS(
        flItems=NS(
            notifyChangesApplied=lambda title, history: package.events.append(
                ("history", title, history)
            )
        ),
        UpdateAll=lambda: package.events.append(("update",)),
    )
    monkeypatch.setattr(scripting, "_native", lambda name: native)
    monkeypatch.setattr(scripting, "current_package", lambda expected_id=None: package)
    return package


def test_plan_noop_and_whole_validation_before_history(owned):
    assert hasattr(scripting, "write_font_info"), (
        "Bounded Font Info edit helper required"
    )
    write = scripting.write_font_info
    assert write(owned, [("Regular", "ascender", 800, 800)], undo_name="Owned") == {
        "changed": 0
    }
    assert not any(e[0] in ("init", "history", "set") for e in owned.events)
    for plan in [
        [("Regular", "ascender", 700, 801)],
        [("Missing", "ascender", 800, 801)],
        [("Regular", "ascender", 800, float("nan"))],
        [("Regular", "ascender", 800, 801), ("Regular", "unknown", 1, 2)],
    ]:
        with pytest.raises(ValueError):
            write(owned, plan, undo_name="Owned")
        assert owned.values["Regular"]["ascender"] == 800
        assert owned.master == "Bold"
    assert not any(e[0] in ("init", "history", "set") for e in owned.events)


def test_plan_success_and_mutate_then_raise_rollback(owned):
    assert hasattr(scripting, "write_font_info"), (
        "Bounded Font Info edit helper required"
    )
    write = scripting.write_font_info
    result = write(owned, [("Regular", "ascender", 800, 810)], undo_name="Owned")
    assert result == {"changed": 1}
    assert owned.master == "Bold"
    assert owned.values["Bold"]["ascender"] == 900
    history = [e for e in owned.events if e[0] == "history"]
    assert len(history) == 2
    assert history[0][2] == [owned, "owned-container"]
    with pytest.raises(RuntimeError, match="owned setter"):
        write(
            owned,
            [("Regular", "ascender", 810, 820), ("Bold", "ascender", 900, 999)],
            undo_name="Owned",
        )
    assert owned.values == {"Regular": {"ascender": 810}, "Bold": {"ascender": 900}}
    assert owned.master == "Bold"


def test_normalized_empty_text_rollback_preserves_native_none(owned):
    owned.values["Regular"]["note"] = None
    with pytest.raises(RuntimeError):
        scripting.write_font_info(
            owned,
            [("Regular", "note", "", "changed"), ("Bold", "ascender", 900, 999)],
            undo_name="Owned",
        )
    assert owned.values["Regular"]["note"] is None, (
        "Rollback must preserve native None, not normalized display text"
    )


def test_bad_plans_stale_font_and_rollback_failure_are_explicit(owned, monkeypatch):
    for plan in [
        [("Regular", "ascender", 800, 810), ("Regular", "ascender", 800, 820)],
        [("Regular", "versionMinor", 1, 1000)],
        [("Regular", "ascender", 800, True)],
    ]:
        with pytest.raises(ValueError):
            scripting.write_font_info(owned, plan, undo_name="Owned")
    assert not any(event[0] == "history" for event in owned.events)
    monkeypatch.setattr(scripting, "current_package", lambda: NS(id=2))
    with pytest.raises(ValueError, match="no longer current"):
        scripting.write_font_info(owned, [], undo_name="Owned")
    monkeypatch.setattr(scripting, "current_package", lambda: owned)
    owned.values["Bold"]["ascender"] = 999
    with pytest.raises(RuntimeError, match="Partial Font Info edit; rollback failed"):
        scripting.write_font_info(
            owned,
            [("Bold", "ascender", 999, 901), ("Regular", "ascender", 800, 999)],
            undo_name="Owned",
        )


@pytest.mark.parametrize(
    "field,value",
    [("ascender", 10**1000), ("note", "bad\x00text"), ("note", "bad\ud800text")],
)
def test_native_boundary_rejects_unrepresentable_values_before_history(
    owned, field, value
):
    owned.values["Regular"][field] = 800
    with pytest.raises(ValueError):
        scripting.write_font_info(
            owned, [("Regular", field, 800, value)], undo_name="Owned"
        )
    assert not any(event[0] in ("set", "history") for event in owned.events)
