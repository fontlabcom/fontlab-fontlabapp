# this_file: tests/test_common_glyphs_panel.py
"""Actual standalone Qt controls, repeat launch and retained cleanup failures."""

from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from test_spacing_worksheet import GUI, QtCore, drain, valid
from fontlabapp.glyphs.common.model import Font, Glyph, Production, analyze
from fontlabapp.glyphs.common.ui import panel_type
import fontlabapp.glyphs.common.lifetime as lifetime


def report():
    return analyze(
        (Font(1, 2, "Family", (Glyph("a", (97, 65)),)),),
        lambda name, **kw: Production("a", "database"),
    )


def test_actual_report_controls_default_off_unavailable_refresh_close_and_destroy():
    refresh = Mock(return_value=report())
    p = panel_type(GUI)(None, report(), refresh)
    p.show()
    drain()
    assert not p.isModal() and not p.charcoal.isChecked() and not p.charcoal.isEnabled()
    assert not p.mark_button.isEnabled() and "8564" in p.hold.text()
    assert p.editor.toPlainText().startswith(report()["source_text"])
    assert "U+0041" in p.editor.toPlainText() and p.editor.isReadOnly()
    p.refresh_button.click()
    assert refresh.call_count == 1 and p.snapshot["count"] == 1
    p.mark_common()
    assert "unavailable" in p.status.text() and refresh.call_count == 1
    p.close_button.click()
    drain()
    assert not valid(p) and not lifetime.pending()


def test_failed_refresh_keeps_whole_last_snapshot_with_explicit_failure():
    refresh = Mock(side_effect=ValueError("fonts changed"))
    p = panel_type(GUI)(None, report(), refresh)
    original = p.editor.toPlainText()
    p.refresh_button.click()
    assert p.editor.toPlainText() == original and "fonts changed" in p.status.text()
    p.close()
    drain()


def test_close_failure_retains_exact_owner_and_all_error_receipts_then_recovers(
    monkeypatch,
):
    p = panel_type(GUI)(None, report(), Mock())
    original = p.scopes[0].records[0]
    p.scopes[0].records[0] = (NS(disconnect=lambda slot: False), original[1], False)
    assert p.close() is False and lifetime.pending()[id(p)].owner is p
    original_error = lifetime.pending()[id(p)].errors[0]
    with pytest.raises(RuntimeError, match="cleanup"):
        lifetime.require_clear()
    with pytest.raises(ExceptionGroup):
        lifetime.recover(deadline=lifetime.monotonic() + 3)
    assert (
        lifetime.pending()[id(p)].errors[0] is original_error
        and len(lifetime.pending()[id(p)].errors) == 2
    )
    p.scopes[0].records[0] = original
    receipts = lifetime.recover(deadline=lifetime.monotonic() + 3)
    assert (
        receipts[0].owner is p
        and len(receipts[0].errors) == 2
        and not lifetime.pending()
    )
    drain()


def test_construction_failure_cleanup_and_failed_cleanup_hold_original_exceptions(
    monkeypatch,
):
    made = []

    class Dialog(GUI.QDialog):
        def __init__(self, parent):
            GUI.QDialog.__init__(self, parent)
            made.append(self)

    gui = NS(**vars(GUI))
    gui.QDialog = Dialog
    gui.QCheckBox = Mock(side_effect=ValueError("construction failed"))
    with pytest.raises(ValueError, match="construction failed"):
        panel_type(gui)(None, report(), Mock())
    drain()
    assert not valid(made[-1])

    def fail(self):
        raise RuntimeError("delete failed")

    monkeypatch.setattr(Dialog, "deleteLater", fail)
    with pytest.raises(ExceptionGroup) as caught:
        panel_type(gui)(None, report(), Mock())
    owner = made[-1]
    assert isinstance(caught.value.exceptions[0], ValueError)
    assert lifetime.pending()[id(owner)].errors[0] is caught.value
    monkeypatch.delattr(Dialog, "deleteLater")
    lifetime.recover(deadline=lifetime.monotonic() + 3)
    drain()


def test_close_deadline_and_recovery_cancellation_never_discard_owner(monkeypatch):
    import fontlabapp.glyphs.common.ui as panel

    p = panel_type(GUI)(None, report(), Mock())
    now = NS(value=0)
    monkeypatch.setattr(panel, "monotonic", lambda: now.value)
    original = p.scopes[0].finish

    def slow(**kwargs):
        result = original(**kwargs)
        now.value = 1
        return result

    monkeypatch.setattr(p.scopes[0], "finish", slow)
    assert not p.close() and id(p) in lifetime.pending()
    with pytest.raises(InterruptedError):
        lifetime.recover(deadline=lifetime.monotonic() + 3, cancelled=lambda: True)
    assert id(p) in lifetime.pending()
    monkeypatch.setattr(p.scopes[0], "finish", original)
    now.value = 0
    lifetime.recover(deadline=lifetime.monotonic() + 3)
    drain()


def test_controller_replaces_only_owned_panel_fences_failures_and_cleans_show_overrun(
    monkeypatch,
):
    import fontlabapp.glyphs.common.controller as controller

    capture = Mock(return_value=report())
    monkeypatch.setattr(controller, "capture", capture)
    monkeypatch.setattr(
        controller,
        "_native",
        lambda name: NS(QtGui=GUI, QtCore=QtCore)
        if name == "PythonQt"
        else NS(MainWindow=lambda: None),
    )
    a = controller.show(Mock())
    b = controller.show(Mock())
    drain()
    assert not valid(a) and valid(b) and lifetime.current() is b
    b.close()
    drain()
    now = NS(value=0)
    monkeypatch.setattr(controller, "monotonic", lambda: now.value)
    import fontlabapp.glyphs.common.ui as panel

    monkeypatch.setattr(panel, "monotonic", lambda: now.value)

    class SlowShow(GUI.QDialog):
        def show(self):
            GUI.QDialog.show(self)
            now.value = 9

    gui = NS(**vars(GUI))
    gui.QDialog = SlowShow
    monkeypatch.setattr(
        controller,
        "_native",
        lambda name: NS(QtGui=gui, QtCore=QtCore)
        if name == "PythonQt"
        else NS(MainWindow=lambda: None),
    )
    with pytest.raises(ExceptionGroup):
        controller.show(Mock())
    assert lifetime.pending(), "Over-budget display must keep the failed owner"
    lifetime.recover(deadline=lifetime.monotonic() + 3)
    drain()
    assert not lifetime.pending()


def test_parent_destruction_fences_callbacks_and_releases_only_owned_registry():
    p = panel_type(GUI)(None, report(), Mock())
    foreign = object()
    lifetime.windows()[lifetime.KEY] = p
    lifetime.windows()["foreign_common_test"] = foreign
    p.deleteLater()
    drain()
    assert not valid(p) and p.closed and not any(s.records for s in p.scopes)
    assert not lifetime.pending() and lifetime.current() is None
    assert lifetime.windows().pop("foreign_common_test") is foreign
    p.failure(RuntimeError("after native destruction"))
    p.refresh()
    p.mark_common()
    assert p.last_failure.args == ("after native destruction",), (
        "No native label access after destruction"
    )


def test_controller_preflight_owner_refusal_and_display_failure_cleanup(monkeypatch):
    import fontlabapp.glyphs.common.controller as controller

    capture = Mock(return_value=report())
    binding = Mock(
        side_effect=lambda name: NS(QtGui=GUI, QtCore=QtCore)
        if name == "PythonQt"
        else NS(MainWindow=lambda: None)
    )
    monkeypatch.setattr(controller, "capture", capture)
    monkeypatch.setattr(controller, "_native", binding)
    capture.side_effect = ValueError("Insufficient fonts")
    with pytest.raises(ValueError, match="Insufficient"):
        controller.show(Mock())
    assert not binding.called and lifetime.current() is None
    capture.side_effect = None
    p = controller.show(Mock())
    original = p.recover_owned
    monkeypatch.setattr(
        p, "recover_owned", Mock(side_effect=RuntimeError("old owner cleanup failed"))
    )
    with pytest.raises(RuntimeError, match="old owner"):
        controller.show(Mock())
    attempts = capture.call_count
    with pytest.raises(RuntimeError, match="cleanup"):
        controller.show(Mock())
    assert capture.call_count == attempts and lifetime.pending()[id(p)].owner is p
    monkeypatch.setattr(p, "recover_owned", original)
    lifetime.recover(deadline=lifetime.monotonic() + 3)
    drain()
    made = []

    class RaiseFails(GUI.QDialog):
        def __init__(self, parent):
            GUI.QDialog.__init__(self, parent)
            made.append(self)

        def raise_(self):
            raise RuntimeError("display failed")

    gui = NS(**vars(GUI))
    gui.QDialog = RaiseFails
    monkeypatch.setattr(
        controller,
        "_native",
        lambda name: NS(QtGui=gui, QtCore=QtCore)
        if name == "PythonQt"
        else NS(MainWindow=lambda: None),
    )
    with pytest.raises(RuntimeError, match="display failed"):
        controller.show(Mock())
    drain()
    assert not valid(made[0]) and not lifetime.pending() and lifetime.current() is None


def test_multiple_failed_owners_partial_recovery_keeps_originals_and_untouched_deadline(
    monkeypatch,
):
    done = NS(recover_owned=Mock())
    fail = NS(recover_owned=Mock(side_effect=RuntimeError("second cleanup failed")))
    first_error, second_error = RuntimeError("first"), RuntimeError("second")
    lifetime.retain(done, first_error)
    lifetime.retain(fail, second_error)
    with pytest.raises(ExceptionGroup) as caught:
        lifetime.recover(deadline=lifetime.monotonic() + 3)
    assert caught.value.recovered[0].errors == [first_error]
    assert lifetime.pending()[id(fail)].errors[0] is second_error
    fail.recover_owned.side_effect = TimeoutError("deadline during owner")
    with pytest.raises(ExceptionGroup):
        lifetime.recover(deadline=lifetime.monotonic() + 3)
    assert len(lifetime.pending()[id(fail)].errors) == 3
    fail.recover_owned.side_effect = None
    lifetime.recover(deadline=lifetime.monotonic() + 3)
    assert not lifetime.pending()


def test_busy_and_closed_refresh_never_capture_or_mutate():
    refresh = Mock(return_value=report())
    p = panel_type(GUI)(None, report(), refresh)
    p.busy = True
    p.refresh()
    assert not refresh.called
    p.busy = False
    p.close()
    p.refresh()
    p.mark_common()
    assert not refresh.called
    drain()


def test_unicode_diagnostic_text_preserves_nbsp_line_separators_nul_and_supplementary():
    import json

    snapshot = analyze(
        (
            Font(
                1,
                2,
                "Family",
                tuple(
                    Glyph(name, (code,))
                    for name, code in (
                        ("nbsp", 0xA0),
                        ("line", 0x2028),
                        ("nul", 0),
                        ("supplementary", 0x1F600),
                    )
                ),
            ),
        ),
        lambda name, **kw: Production(name, "database"),
    )
    p = panel_type(GUI)(None, snapshot, Mock())
    from fontlabapp.glyphs.common.model import render

    raw_display = render(snapshot)
    assert (
        "\u00a0 " in raw_display and "\u2028 " in raw_display and "😀 " in raw_display
    ), "Human source input retains NBSP/LS/non-BMP before Qt conversion"
    human_characters = (
        p.editor.toPlainText()
        .split("Number of common glyphs: 4\n\n", 1)[1]
        .split("\n\n\nNice names:", 1)[0]
    )
    assert human_characters == "  \n \\u0000 😀 ", (
        "Record actual standalone Qt primary-section normalization and disclosed NUL display escape"
    )
    assert human_characters != snapshot["characters"], (
        "Do not claim literal primary text copying survived normalization"
    )
    assert "copying can normalize" in p.representation.text()
    diagnostics = p.editor.toPlainText().split(
        "Encodings and production metadata:\n", 1
    )[1]
    assert "\0" not in p.editor.toPlainText(), (
        "Never send a literal NUL through the known lossy native QString boundary"
    )
    assert json.loads(diagnostics)["characters"] == snapshot["characters"], (
        "Qt plain-text normalization must not lose exact Unicode facts in copyable JSON"
    )
    assert json.loads(diagnostics)["source_text"] == snapshot["source_text"], (
        "The complete original primary report survives in escaped JSON, including raw NUL"
    )
    p.close()
    drain()
