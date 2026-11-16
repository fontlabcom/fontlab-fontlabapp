# this_file: tests/test_fontui_livesync.py
# SPDX-License-Identifier: Apache-2.0
"""Echo suppression rules and the Qt-free TMetrics glyph metric write."""

import math

import pytest

from _tmetrics_fakes import EditableFont, composite_font
from fontlabapp.fontui.livesync import Echo
from fontlabapp.fontui.tmetrics_model import sidebearings, write_metric


def test_echo_when_nothing_recorded_then_every_fingerprint_is_stale():
    echo = Echo()
    assert echo.stale("a") is True, "without an own write every change refreshes"


def test_echo_when_own_write_matches_then_reset_is_skipped_repeatedly():
    echo = Echo()
    echo.record("own")
    assert echo.stale("own") is False, "the window's own write is not an external change"
    assert echo.stale("own") is False, "a repeated notification of the same write is skipped too"


def test_echo_when_external_change_then_refresh_and_token_dropped():
    echo = Echo()
    echo.record("own")
    assert echo.stale("external") is True, "a different fingerprint refreshes"
    assert echo.token is None, "the token is dropped after an external change"


def test_echo_when_second_external_change_returns_to_old_state_then_stale_token_refreshes():
    echo = Echo()
    echo.record("own")
    assert echo.stale("external") is True, "first external change refreshes"
    assert echo.stale("own") is True, "a later return to the recorded state is not our echo"


def test_echo_when_cleared_then_matching_fingerprint_refreshes():
    echo = Echo()
    echo.record("own")
    echo.clear()
    assert echo.stale("own") is True, "a cleared echo never suppresses"


def test_write_metric_when_rsb_then_width_changes_and_undo_name_set():
    font = EditableFont()
    assert write_metric(font, "A", "rsb", 50) is True, "a changed RSB is written"
    assert sidebearings(font, "A") == (650, 0, 50), "RSB grows the advance only"
    assert font.edits == [("A", "public.default", "TMetrics: RSB A")], "one write on the default layer"


def test_write_metric_when_width_then_advance_set():
    font = EditableFont()
    assert write_metric(font, "V", "width", 640.0) is True, "a changed width is written"
    assert font.ufo["V"].width == 640, "width is the new advance"
    assert font.edits[0][2] == "TMetrics: width V", "undo name names the field and glyph"


def test_write_metric_when_lsb_then_contours_anchors_components_shift_and_rsb_kept():
    font = composite_font()
    assert write_metric(font, "A", "lsb", 30) is True, "LSB is written"
    width, lsb, rsb = sidebearings(font, "A")
    assert (width, lsb, rsb) == (630, 30, 0), "LSB shifts the outline and keeps RSB"
    assert font.ufo["A"].anchors[0].x == 330, "anchors move with the outline"
    assert font.edits[0][2] == "TMetrics: LSB A", "undo name for LSB"
    assert write_metric(font, "B", "lsb", 10) is True, "composite LSB is written"
    assert font.ufo["B"].components[0].transformation[4] == -20, "component offset moves from LSB 30 to 10"
    assert sidebearings(font, "B")[1] == 10, "composite LSB reads back"


def test_write_metric_when_value_already_holds_then_no_write():
    font = EditableFont()
    assert write_metric(font, "A", "width", 600) is False, "an unchanged value is not written"
    assert font.edits == [], "no edit_glyph call"


@pytest.mark.parametrize(
    ("name", "metric", "value", "error", "text"),
    [
        ("A", "height", 1, ValueError, "Unknown metric"),
        ("A", "rsb", math.inf, ValueError, "finite"),
        ("Z", "rsb", 1, ValueError, "Glyph not found"),
    ],
)
def test_write_metric_when_bad_input_then_raises_without_write(name, metric, value, error, text):
    font = EditableFont()
    with pytest.raises(error, match=text):
        write_metric(font, name, metric, value)
    assert font.edits == [], "nothing is written on refusal"


def test_write_metric_when_empty_glyph_sidebearing_then_refused():
    font = EditableFont()
    font.ufo.newGlyph("space").width = 250
    with pytest.raises(ValueError, match="no outline"):
        write_metric(font, "space", "lsb", 10)
    assert write_metric(font, "space", "width", 300) is True, "an empty glyph's width is writable"


def test_write_metric_when_font_has_no_edit_glyph_then_type_error():
    import _cov_qt as fq

    with pytest.raises(TypeError, match="Read-only"):
        write_metric(fq.FontModel(fq.ufo_font()), "A", "rsb", 5)


def test_write_metric_when_backend_write_fails_then_font_unchanged():
    font = EditableFont()
    font.fail = RuntimeError("history guard refused")
    with pytest.raises(RuntimeError, match="history guard"):
        write_metric(font, "A", "rsb", 50)
    assert font.ufo["A"].width == 600 and font.edits == [], "a failed write leaves the font as it was"
