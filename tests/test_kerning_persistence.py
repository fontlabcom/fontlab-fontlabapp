# this_file: tests/test_kerning_persistence.py
"""Exact native-shaped explicit pairs; no FontLab imports or writes."""

from types import SimpleNamespace as NS

import fontlabapp.kerning.persistence.model as api
import pytest


class Package:
    id = 7
    upm = 1000
    master = "Regular"
    masters = ("Regular", "Bold")

    def __init__(self):
        self.values = {
            "Regular": {("A", "V"): 0, ("@Left", "T"): 2000, ("X", "Y"): 2001},
            "Bold": {("T", "@Right"): -2001, ("A", "V"): -2000},
        }
        self.reads = 0
        self.on_read = lambda: None

    def kerning(self, master):
        self.reads += 1
        self.on_read()

        def side(name):
            return NS(
                id=name.lstrip("@"),
                mode="groupMode" if name.startswith("@") else "glyphMode",
            )

        return NS(
            items=lambda: [
                (NS(left=side(left), right=side(right)), value)
                for (left, right), value in self.values[master].items()
            ]
        )


@pytest.fixture
def package(monkeypatch):
    package = Package()
    state = NS(package=package)
    monkeypatch.setattr(
        api,
        "current_package",
        lambda expected=None: (
            state.package
            if expected is None
            or (state.package is not None and state.package.id == expected)
            else None
        ),
    )
    return package, state


def test_exact_boundaries_classes_zero_and_absence_are_retained(package):
    font, _state = package
    before = {master: dict(values) for master, values in font.values.items()}
    snapshot = api.capture(font)
    rows = api.report(snapshot, all_masters=True)
    assert len(rows) == 5
    assert [
        (row.master, row.left, row.right, row.value) for row in rows if row.at_risk
    ] == [("Regular", "X", "Y", 2001), ("Bold", "T", "@Right", -2001)]
    assert any(row.value == 0 and row.left == "A" for row in rows)
    assert not any(row.left == "absent" for row in rows)
    assert all(row.upm == 1000 for row in rows)
    assert "+2000" in next(row.reason for row in rows if row.value == 2001)
    assert "-2000" in next(row.reason for row in rows if row.value == -2001)
    assert all("9784" in row.reason for row in rows)
    assert len(api.report(snapshot)) == 3
    api.ensure_snapshot(font, snapshot)
    assert font.values == before and font.master == "Regular"


@pytest.mark.parametrize(
    "value",
    [None, True, "1000", 0, -1, float("nan"), float("inf"), 10**1000, 10**308, 1e308],
)
def test_invalid_upm_is_diagnosed_without_partial_results(package, value):
    font, _state = package
    font.upm = value
    with pytest.raises(ValueError, match="UPM"):
        api.capture(font)


@pytest.mark.parametrize(
    "value", [None, True, "3000", float("nan"), float("inf"), 10**1000]
)
def test_invalid_explicit_pair_value_identifies_master_and_pair(package, value):
    font, _state = package
    font.values["Bold"][("T", "@Right")] = value
    with pytest.raises(ValueError, match="Bold.*T.*@Right"):
        api.capture(font)


@pytest.mark.parametrize(
    "change", ["pair", "zero", "upm", "master", "masters", "font", "closed"]
)
def test_snapshot_rejects_every_stale_source_dimension(package, change):
    font, state = package
    snapshot = api.capture(font)
    if change == "pair":
        font.values["Bold"][("A", "V")] += 1
    elif change == "zero":
        del font.values["Regular"][("A", "V")]
    elif change == "upm":
        font.upm = 2000
    elif change == "master":
        font.master = "Bold"
    elif change == "masters":
        font.masters = ("Bold", "Regular")
    elif change == "font":
        state.package = NS(id=9)
    else:
        state.package = None
    with pytest.raises(ValueError):
        api.ensure_snapshot(font, snapshot)


def test_mid_scan_pair_change_and_read_failure_publish_no_snapshot(package):
    font, _state = package

    def change():
        if font.reads == 3:
            font.values["Regular"][("A", "V")] = 17

    font.on_read = change
    with pytest.raises(ValueError, match="changed"):
        api.capture(font)
    font.on_read = lambda: (_ for _ in ()).throw(RuntimeError("unreadable kerning"))
    with pytest.raises(RuntimeError, match="unreadable"):
        api.capture(font)


@pytest.mark.parametrize(
    "masters,active",
    [((), "Regular"), (("Regular", "Regular"), "Regular"), (("Regular",), "Missing")],
)
def test_unknown_or_duplicate_master_domain_is_refused(package, masters, active):
    font, _state = package
    font.masters, font.master = masters, active
    with pytest.raises(ValueError, match="master"):
        api.capture(font)


def test_null_font_and_bad_pair_identity_are_refused(package):
    font, _state = package
    with pytest.raises(ValueError):
        api.capture(None)
    font.values["Regular"][("", "V")] = 23
    with pytest.raises(ValueError, match="pair"):
        api.capture(font)


def test_fractional_values_are_reported_exactly_without_history_rounding(package):
    font, _state = package
    font.values["Regular"][("A", "V")] = 2000.125
    row = next(row for row in api.report(api.capture(font)) if row.left == "A")
    assert row.value == 2000.125 and row.at_risk
    with pytest.raises(ValueError, match="stale"):
        api.ensure_snapshot(font, None)


def test_mid_scan_current_font_change_is_refused(package):
    font, state = package
    font.on_read = lambda: setattr(state, "package", None)
    with pytest.raises(ValueError, match="changed"):
        api.capture(font)
