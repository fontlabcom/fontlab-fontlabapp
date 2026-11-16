# this_file: tests/test_selection_carrier.py
"""Bind Font-window selection to the intended registered FontGate carrier."""

from types import SimpleNamespace as NS

import fontlabapp.core.scripting as api
import pytest


class Font:
    def __init__(self, identifier):
        self.id = identifier

    def __len__(self):
        return 3

    def __getitem__(self, index):
        return NS(name=["A", "B", "C"][index])


@pytest.fixture
def source(monkeypatch):
    fl = NS(font=Font(700), Selected=lambda i: i != 1)
    monkeypatch.setattr(api, "_native", lambda name: NS(fl=fl))
    monkeypatch.setattr(api, "monotonic", lambda: 0.0)
    return fl


def test_expected_carrier_binds_same_named_fonts_and_preserves_zero_arg(source):
    assert api.names_font_window_selection(expected_fg_id=700, deadline=1) == ["A", "C"]
    source.font = Font(701)
    assert api.names_font_window_selection() == ["A", "C"]
    with pytest.raises(ValueError, match="carrier"):
        api.names_font_window_selection(expected_fg_id=700)


@pytest.mark.parametrize("font", [None, NS()])
def test_missing_or_unreadable_carrier_is_diagnosed(source, font):
    source.font = font
    with pytest.raises(ValueError, match="carrier"):
        api.names_font_window_selection(expected_fg_id=700)
    if font is None:
        assert api.names_font_window_selection() == []


class LegacyFont(Font):
    """FontLab 9: the legacy Font has file_name but no id."""

    def __init__(self, path):
        self.file_name = path


def _workspace(monkeypatch, source, package):
    ws = NS(currentPackage=package)
    natives = {"FL": NS(fl=source), "fontlab": NS(flWorkspace=NS(instance=lambda: ws))}
    monkeypatch.setattr(api, "_native", lambda name: natives[name])


def test_legacy_font_without_id_when_saved_path_matches_then_selection_read(source, monkeypatch):
    source.font = LegacyFont("/fonts/A.vfj")
    _workspace(monkeypatch, source, NS(isNull=False, fgId=700, path="/fonts/A.vfj"))
    assert api.names_font_window_selection(expected_fg_id=700) == ["A", "C"]


@pytest.mark.parametrize(
    "path,package",
    [
        ("/fonts/A.vfj", NS(isNull=False, fgId=700, path="/fonts/B.vfj")),  # other file
        ("", NS(isNull=False, fgId=700, path="")),  # unsaved: no identity
        ("/fonts/A.vfj", NS(isNull=False, fgId=701, path="/fonts/A.vfj")),  # other package
        ("/fonts/A.vfj", None),  # no current package
    ],
)
def test_legacy_font_without_id_when_identity_unproven_then_refused(source, monkeypatch, path, package):
    source.font = LegacyFont(path)
    _workspace(monkeypatch, source, package)
    with pytest.raises(ValueError, match="carrier"):
        api.names_font_window_selection(expected_fg_id=700)


def test_carrier_change_mid_loop_rejects_partial_selection(source):
    def selected(i):
        source.font = Font(701)
        return True

    source.Selected = selected
    with pytest.raises(ValueError):
        api.names_font_window_selection(expected_fg_id=700)


@pytest.mark.parametrize("at", [0, 2, 5])
def test_deadline_before_and_during_whole_font_loop(source, monkeypatch, at):
    ticks = iter(range(20))
    monkeypatch.setattr(api, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError):
        api.names_font_window_selection(deadline=at)


def test_zero_arg_carrier_does_not_require_new_identity_property(source):
    del source.font.id
    assert api.names_font_window_selection() == ["A", "C"]
