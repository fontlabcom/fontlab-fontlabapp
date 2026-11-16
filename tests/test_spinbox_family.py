# this_file: tests/test_spinbox_family.py
"""Complete original control ranges, formatting, actual edits and teardown."""

from types import SimpleNamespace as NS
import pytest
from test_spacing_worksheet import GUI, QtCore, QTest, drain, valid
from fontlabapp.proof.numeric.model import Facts
from fontlabapp.proof.numeric.ui import panel_type


@pytest.fixture(params=[2, 3])
def panel(request):
    state = NS(error=None, calls=0)

    def capture():
        state.calls += 1
        if state.error:
            raise state.error
        return Facts(
            1000,
            (("A", "Regular", 500.5), ("B", "Regular", 600)),
            (("A", 0), ("B", None)),
        )

    p = panel_type(QtCore, GUI)(None, capture, request.param)
    p.show()
    p.activateWindow()
    drain()
    yield p, state
    if valid(p):
        assert p.close()
    drain()


def test_complete_numeric_contract(panel):
    p, _ = panel
    expected = [
        (-20, 20, 1, 0, "", ""),
        (0, 1000, 10 if p.part == 3 else 1, 100, "", "%"),
        (0, 999, 1, 99 if p.part == 3 else 25, "$", ""),
    ]
    for key, wanted in zip(("integer", "zoom", "currency"), expected):
        c = p.controls[key]
        assert (
            c.minimum(),
            c.maximum(),
            c.singleStep(),
            c.value(),
            c.prefix(),
            c.suffix(),
        ) == wanted
    assert p.controls["zoom"].specialValueText() == ("Automatic" if p.part == 3 else "")
    for key, limits, step, initial, prefix, suffix, special in (
        (
            "decimal",
            (-20, 20) if p.part == 3 else (-1000, 1000),
            1,
            0 if p.part == 3 else 12.34,
            "",
            "",
            "",
        ),
        (
            "percent",
            (0, 1000) if p.part == 3 else (-1000, 1000),
            10 if p.part == 3 else 1,
            100 if p.part == 3 else 12.34,
            "",
            "%",
            "No scaling" if p.part == 3 else "",
        ),
        (
            "money",
            (0, 1000) if p.part == 3 else (-1000, 1000),
            1,
            99.99 if p.part == 3 else 12.34,
            "$",
            "",
            "",
        ),
    ):
        c = p.controls[key]
        assert (c.minimum(), c.maximum()) == limits
        assert (
            c.singleStep(),
            c.value(),
            c.prefix(),
            c.suffix(),
            c.specialValueText(),
        ) == (step, initial, prefix, suffix, special)
        assert c.decimals() == 2
    c = p.controls["precision"]
    assert (c.minimum(), c.maximum(), c.value()) == (0, 100, 2)
    c.setValue(100)
    assert all(p.controls[k].decimals() == 100 for k in ("decimal", "percent", "money"))
    c.setValue(0)
    assert all(p.controls[k].decimals() == 0 for k in ("decimal", "percent", "money"))


def test_date_time_and_every_format_contract(panel):
    p, _ = panel
    c = p.controls
    assert c["format"].count() == (5 if p.part == 3 else 3)
    assert tuple(c["format"].itemText(i) for i in range(c["format"].count())) == (
        (
            "yyyy-MM-dd hh:mm:ss (zzz 'ms')",
            "hh:mm:ss MM/dd/yyyy",
            "hh:mm:ss dd/MM/yyyy",
            "hh:mm:ss",
            "hh:mm ap",
        )
        if p.part == 3
        else ("yyyy-MM-dd hh:mm", "dd MMM yyyy", "hh:mm AP")
    )
    if p.part == 3:
        assert c["date"].minimumDate() == QtCore.QDate(2005, 1, 1)
        assert c["date"].maximumDate() == QtCore.QDate(2010, 12, 31)
        assert c["time"].minimumTime() == QtCore.QTime(9, 0)
        assert c["time"].maximumTime() == QtCore.QTime(16, 30)
        assert c["time"].date() == QtCore.QDate(2000, 1, 1)
        assert c["time"].minimumDateTime().date() == QtCore.QDate(2000, 1, 1)
        assert c["time"].maximumDateTime().date() == QtCore.QDate(2000, 1, 1)
    else:
        assert c["meeting"].minimumDate() == QtCore.QDate(2020, 1, 1)
        assert c["meeting"].maximumDate() == QtCore.QDate(2040, 12, 31)
    if p.part == 2:
        reference = GUI.QDateTimeEdit()
        assert c["meeting"].displayFormat() == reference.displayFormat()
        reference.deleteLater()
    for i in range(c["format"].count()):
        if p.part == 2:
            c["format"].setCurrentIndex((i + 1) % c["format"].count())
        c["format"].setCurrentIndex(i)
        if p.part == 3:
            c["format"].activated[int].emit(i)
        assert c["meeting"].displayFormat() == c["format"].itemText(i)
        if p.part == 3:
            if c["meeting"].displayedSections() & GUI.QDateTimeEdit.DateSections_Mask:
                assert c["meeting"].minimumDate() == QtCore.QDate(2004, 11, 1)
                assert c["meeting"].maximumDate() == QtCore.QDate(2005, 11, 30)
            else:
                assert c["meeting"].minimumTime() == QtCore.QTime(0, 7, 20)
                assert c["meeting"].maximumTime() == QtCore.QTime(21, 0)
    assert "Unknown revision dates: 1" in p.output.toPlainText()


def test_keyboard_steps_and_live_selected_layer_arithmetic(panel):
    p, _ = panel
    c = p.controls
    c["integer"].setFocus()
    QTest.keyClick(c["integer"], QtCore.Qt.Key_Up)
    c["zoom"].stepUp()
    c["currency"].stepUp()
    c["decimal"].stepUp()
    c["percent"].stepUp()
    c["money"].stepUp()
    drain()
    assert c["integer"].value() == 1
    assert (
        "A / Regular" in p.output.toPlainText()
        and "B / Regular" in p.output.toPlainText()
    )
    assert p.result["advances_units"][0][2] == 501.5
    assert not p.last_error and p.output.isReadOnly()
    assert not p.grab().isNull()


def test_refresh_drafts_clear_failure_and_recover(panel):
    p, s = panel
    p.controls["integer"].setValue(7)
    p.controls["precision"].setValue(4)
    s.error = ValueError("source changed")
    p.refresh_button.click()
    assert p.facts is None and p.result is None and "source changed" in p.status.text()
    assert "A / Regular" not in p.output.toPlainText()
    assert p.controls["integer"].value() == 7 and p.controls["precision"].value() == 4
    s.error = None
    p.refresh_button.click()
    assert s.calls == 3 and p.result and not p.last_error


def test_close_escape_and_late_callbacks_release_only_owned_state(panel):
    p, s = panel
    p.setFocus()
    QTest.keyClick(p, QtCore.Qt.Key_Escape)
    drain()
    assert p.closed and p.capture is None and p.facts is None
    assert not p.scope.records
    p.changed()
    p.refresh()
    assert s.calls == 1


def test_callback_calculation_failure_clears_result_and_recovers(panel, monkeypatch):
    import fontlabapp.proof.numeric.ui as module

    p, _ = panel
    original = module.calculate
    monkeypatch.setattr(
        module,
        "calculate",
        lambda *args: (_ for _ in ()).throw(ValueError("bad draft")),
    )
    p.changed()
    assert (
        p.result is None and not p.output.toPlainText() and p.last_error == "bad draft"
    )
    monkeypatch.setattr(module, "calculate", original)
    p.changed()
    assert p.result and not p.last_error
    import fontlabapp.proof.numeric.results as results

    monkeypatch.setattr(results, "monotonic", lambda: float("inf"))
    p.changed()
    assert p.result is None and "expired" in p.last_error


def test_close_disconnect_failure_retries_and_parent_destruction(panel, monkeypatch):
    p, _ = panel
    original = p.scope.finish
    failed = [False]

    def finish(**kwargs):
        if not failed[0]:
            failed[0] = True
            return False
        return original(**kwargs)

    monkeypatch.setattr(p.scope, "finish", finish)
    assert not p.close() and p.closed
    assert p.close()
    drain()
    assert p.dead and not p.terminal.records


def test_destroy_parent_and_registry_remove(panel):
    import sys

    p, _ = panel
    registry = sys.__dict__.setdefault("_fontlab_samples", {})
    registry[p.key] = p
    p.deleteLater()
    drain()
    assert p.dead and p.closed and p.key not in registry
    assert p.capture is None and not p.scope.records and not p.terminal.records


def test_native_key_routing_and_close_button(panel):
    p, _ = panel
    p.setFocus()
    QTest.keyClick(p, QtCore.Qt.Key_Space)
    assert not p.closed
    p.close_button.click()
    drain()
    assert p.closed


@pytest.mark.parametrize("key", ["integer", "precision", "date", "format"])
def test_escape_from_each_editor_closes_owned_panel(panel, key):
    p, _ = panel
    control = p.controls[key]
    control.setFocus()
    QTest.keyClick(control, QtCore.Qt.Key_Escape)
    drain()
    assert p.closed and p.capture is None


def test_revision_cutoffs_keep_milliseconds_and_independent_native_sections(panel):
    p, _ = panel
    stamp = QtCore.QDateTime(QtCore.QDate(2005, 1, 2), QtCore.QTime(9, 0))
    epoch = stamp.toMSecsSinceEpoch()
    p.facts = Facts(
        1000,
        (),
        (
            ("before", epoch - 1),
            ("equal", epoch),
            ("after", epoch + 1),
            ("unknown", None),
        ),
    )
    p.controls["date"].setDate(stamp.date())
    p.controls["time"].setTime(stamp.time())
    # Part2's meeting range starts2020; retain that range and use its minimum.
    instant = stamp if p.part == 3 else p.controls["meeting"].minimumDateTime()
    p.controls["meeting"].setDateTime(instant)
    p.changed()
    text = p.output.toPlainText()
    assert "date≤2005-01-02: 3" in text
    assert "time≤09:00:00.000: 2" in text
    assert (
        f"{instant.toString('yyyy-MM-dd HH:mm:ss.zzz')}: {1 if p.part == 3 else 3}"
        in text
    )
    assert "Unknown revision dates: 1" in text


def test_invalid_profile_and_initial_failure_cleanup(monkeypatch):
    import fontlabapp.proof.numeric.ui as module

    with pytest.raises(ValueError):
        module.panel_type(QtCore, GUI)(None, lambda: None, 1)

    def bad(owner, *args):
        raise ValueError("build failed")

    monkeypatch.setattr(module, "build", bad)
    with pytest.raises(ValueError, match="build failed"):
        module.panel_type(QtCore, GUI)(None, lambda: None, 2)
    drain()
