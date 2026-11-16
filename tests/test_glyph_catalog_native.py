# this_file: tests/test_glyph_catalog_native.py
"""Read only owned SDK-shaped scalar metadata; never invoke a live FontLab."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fontlabapp.glyphs.catalog import native as api


class Glyph(NS):
    @property
    def fgGlyph(self):
        raise AssertionError("Do not touch the destructive native fgGlyph cache getter")


@pytest.fixture
def native(monkeypatch):
    package = NS(id=7, fgId=70, master="Regular", isNull=False)
    font = NS(
        id=70,
        glyphs=[
            NS(id=1, name="A", unicodes=[65]),
            NS(id=2, name="unencoded", unicodes=[]),
            NS(id=3, name="multi", unicodes=[0, 0x1F600]),
        ],
    )
    glyphs = {
        i: Glyph(
            id=100 + i,
            fgGlyphId=i,
            name=g.name,
            package=package,
            isValid=True,
            isNull=False,
            lastModified=NS(
                isValid=lambda: True, toString=lambda pattern: "2026-10-20 11:12:13"
            ),
        )
        for i, g in enumerate(font.glyphs, 1)
    }
    for glyph in glyphs.values():
        stamp = glyph.lastModified
        stamp.toLocalTime = lambda stamp=stamp: stamp
        stamp.toMSecsSinceEpoch = lambda: 0
    package.findFgId = Mock(side_effect=lambda i: glyphs[i])
    workspace = NS(currentPackage=package)
    module = NS(
        flWorkspace=NS(instance=lambda: workspace), CurrentFont=Mock(return_value=font)
    )
    monkeypatch.setattr(api, "_native", Mock(return_value=module))
    return NS(**locals())


def test_capture_when_complete_then_all_names_all_unicodes_and_native_dates_in_font_order(
    native,
):
    result = api.capture()
    assert result.headers == ("Glyph name", "Unicode", "Modified")
    assert result.rows == (
        ("A", "U+0041", "2026-10-20 11:12:13"),
        ("unencoded", "", "2026-10-20 11:12:13"),
        ("multi", "U+0000 U+1F600", "2026-10-20 11:12:13"),
    )
    assert native.package.findFgId.call_count == 6


@pytest.mark.parametrize(
    "problem",
    [
        "no-package",
        "null-package",
        "no-font",
        "wrong-font",
        "master-type",
        "duplicate-fg",
        "duplicate-name",
        "empty-name",
        "bad-name",
        "bad-unicode",
        "bool-unicode",
        "large-unicode",
        "missing-glyph",
        "null-glyph",
        "invalid-glyph",
        "wrong-fg",
        "wrong-owner",
        "wrong-name",
        "duplicate-native",
        "bad-date",
    ],
)
def test_capture_when_unreadable_then_no_partial_table(native, problem):
    g = native.glyphs[1]
    if problem == "no-package":
        native.workspace.currentPackage = None
    elif problem == "null-package":
        native.package.isNull = True
    elif problem == "no-font":
        native.module.CurrentFont.return_value = None
    elif problem == "wrong-font":
        native.font.id = 99
    elif problem == "master-type":
        native.package.master = None
    elif problem == "duplicate-fg":
        native.font.glyphs.append(native.font.glyphs[0])
    elif problem == "duplicate-name":
        native.font.glyphs[1].name = "A"
    elif problem == "empty-name":
        native.font.glyphs[0].name = ""
    elif problem == "bad-name":
        native.font.glyphs[0].name = None
    elif problem == "bad-unicode":
        native.font.glyphs[0].unicodes = ["65"]
    elif problem == "bool-unicode":
        native.font.glyphs[0].unicodes = [True]
    elif problem == "large-unicode":
        native.font.glyphs[0].unicodes = [0x110000]
    elif problem == "missing-glyph":
        native.glyphs[1] = None
    elif problem == "null-glyph":
        g.isNull = True
    elif problem == "invalid-glyph":
        g.isValid = False
    elif problem == "wrong-fg":
        g.fgGlyphId = 99
    elif problem == "wrong-owner":
        g.package = NS(id=99)
    elif problem == "wrong-name":
        g.name = "other"
    elif problem == "duplicate-native":
        native.glyphs[2].id = g.id
    elif problem == "bad-date":
        g.lastModified.toString = lambda pattern: "not a timestamp"
    with pytest.raises((ValueError, TypeError)):
        api.capture()


def test_capture_when_empty_or_undated_then_empty_domain_and_explicit_missing_cell(
    native,
):
    native.glyphs[1].lastModified.isValid = lambda: False
    assert api.capture().rows[0][2] == ""
    native.font.glyphs = []
    assert api.capture().rows == ()


def test_capture_when_mutated_between_passes_or_final_context_then_refused(native):
    calls = 0

    def current():
        nonlocal calls
        calls += 1
        if calls == 2:
            native.font.glyphs[0].unicodes = [66]
        return native.font

    native.module.CurrentFont.side_effect = current
    with pytest.raises(ValueError, match="changed"):
        api.capture()
    calls = 0

    def context():
        nonlocal calls
        calls += 1
        if calls == 3:
            native.package.master = "Bold"
        return native.font

    native.module.CurrentFont.side_effect = context
    with pytest.raises(ValueError, match="changed"):
        api.capture()


def test_capture_when_deadline_or_worker_then_no_native_access(native):
    with pytest.raises(TimeoutError):
        api.capture(deadline=-1)
    api._native.assert_not_called()
    with ThreadPoolExecutor(max_workers=1) as pool, pytest.raises(RuntimeError):
        pool.submit(api.capture).result()
    api._native.assert_not_called()


@pytest.mark.parametrize("field", ["validity", "date-type"])
def test_date_when_native_value_unreadable_then_whole_capture_refuses(native, field):
    if field == "validity":
        native.glyphs[1].lastModified.isValid = lambda: 1
    else:
        native.glyphs[1].lastModified.toString = lambda pattern: None
    with pytest.raises((TypeError, ValueError)):
        api.capture()


def test_capture_when_deadline_expires_between_rows_then_never_returns_prefix(
    native, monkeypatch
):
    clock = [0.0]
    monkeypatch.setattr(api, "monotonic", lambda: clock[0])

    def glyphs():
        yield NS(id=1, name="A", unicodes=[65])
        clock[0] = 3.0
        yield NS(id=2, name="unencoded", unicodes=[])

    native.font.glyphs = glyphs()
    with pytest.raises(TimeoutError, match="no partial"):
        api.capture(deadline=2.0)
    assert native.package.findFgId.call_count == 1


def test_capture_when_offset_stamp_then_local_text_and_original_value_preserved(native):
    from test_filter_table_dialog import QtCore

    stamp = QtCore.QDateTime.fromString("2026-03-01T15:04:05+11:00", QtCore.Qt.ISODate)
    expected = stamp.toLocalTime().toString("yyyy-MM-dd HH:mm:ss")
    assert expected != stamp.toString("yyyy-MM-dd HH:mm:ss"), (
        "Witness must distinguish stored offset and local time"
    )
    before = stamp.toMSecsSinceEpoch(), stamp.timeSpec()
    native.glyphs[1].lastModified = stamp
    assert api.capture().rows[0][2] == expected
    assert (stamp.toMSecsSinceEpoch(), stamp.timeSpec()) == before


def test_capture_when_millisecond_changes_with_same_display_second_then_refuses(native):
    from test_filter_table_dialog import QtCore

    first = QtCore.QDateTime.fromString(
        "2026-03-01T15:04:05.100+11:00", QtCore.Qt.ISODateWithMs
    )
    second = first.addMSecs(1)
    assert first.toLocalTime().toString(
        "yyyy-MM-dd HH:mm:ss"
    ) == second.toLocalTime().toString("yyyy-MM-dd HH:mm:ss")
    native.glyphs[1].lastModified = first
    calls = 0

    def current():
        nonlocal calls
        calls += 1
        if calls == 2:
            native.glyphs[1].lastModified = second
        return native.font

    native.module.CurrentFont.side_effect = current
    with pytest.raises(ValueError, match="changed"):
        api.capture()


def test_capture_when_epoch_unreadable_then_no_silently_coerced_instant(native):
    native.glyphs[1].lastModified.toMSecsSinceEpoch = lambda: None
    with pytest.raises(TypeError, match="instant"):
        api.capture()
