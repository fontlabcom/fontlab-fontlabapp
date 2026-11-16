# this_file: tests/test_angularizzle_settings.py
"""Owned preferences verify defaults, original keys and repaired checkbox case."""

import pytest

from fontlabapp.contours.angularizzle.settings import (
    CHECK,
    LEGACY_CHECK,
    PLANE,
    WINDOW,
    load,
    save,
)


@pytest.mark.parametrize("status", [0, 1])
def test_native_preferences_reads_only_tool_keys_and_flushes_only_explicit_writes(
    status,
):
    from types import SimpleNamespace

    from fontlabapp.contours.angularizzle.settings import native_preferences, persist

    class Backend:
        NoError = 0

        def __init__(self, organization, application):
            assert (organization, application) == ("FontLab", "Angularizzle")
            self.values = {PLANE: "40", LEGACY_CHECK: False, "unrelated": "keep"}
            self.reads, self.writes, self.flushed = [], [], False

        def setFallbacksEnabled(self, enabled):
            assert enabled is False

        def contains(self, key):
            return key in self.values

        def value(self, key):
            self.reads.append(key)
            return self.values[key]

        def setValue(self, key, value):
            self.writes.append(key)
            self.values[key] = value

        def sync(self):
            self.flushed = True

        def status(self):
            return status

    qt = SimpleNamespace(QSettings=Backend)
    backend, values = native_preferences(qt)
    assert backend.reads == [PLANE, LEGACY_CHECK] and "unrelated" not in values
    save(values, "80", True, (1, 2, 222, 130))
    if status:
        with pytest.raises(OSError, match="could not be saved"):
            persist(qt, backend, values, (CHECK, WINDOW))
    else:
        persist(qt, backend, values, (CHECK, WINDOW))
    assert backend.writes == [CHECK, WINDOW] and backend.flushed
    assert backend.values[PLANE] == "40" and backend.values["unrelated"] == "keep"


def test_default_plane_detail_and_window_geometry_are_source_defaults():
    settings = load({})
    assert settings.plane == "80" and settings.detail is True
    assert settings.geometry is None and settings.warning == ""


def test_existing_false_and_canonical_key_win_over_legacy_case():
    settings = load(
        {PLANE: "40", CHECK: False, LEGACY_CHECK: True, WINDOW: (1, -2, 222, 130)}
    )
    assert settings.plane == "40" and settings.detail is False
    assert settings.geometry == (1, -2, 222, 130)
    assert load({LEGACY_CHECK: False}).detail is False
    assert load({LEGACY_CHECK: "false"}).detail is False


@pytest.mark.parametrize(
    "values",
    [
        {PLANE: "x"},
        {PLANE: 4},
        {CHECK: "garbage"},
        {WINDOW: (1, 2)},
        {WINDOW: (1, 2, -1, 130)},
        {WINDOW: (True, 2, 222, 130)},
    ],
)
def test_bad_saved_values_are_diagnosed_and_replaced_with_defaults(values):
    settings = load(values)
    assert settings.plane == "80" and settings.detail is True
    assert settings.geometry is None and settings.warning


def test_save_uses_canonical_keys_and_keeps_unrelated_user_settings():
    values = {"unrelated": "keep", LEGACY_CHECK: True}
    save(values, "٨٠", False, (10, 20, 222, 130))
    assert values[PLANE] == "٨٠" and values[CHECK] is False
    assert values[WINDOW] == (10, 20, 222, 130) and values["unrelated"] == "keep"
    assert load(values).detail is False
