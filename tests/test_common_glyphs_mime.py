# this_file: tests/test_common_glyphs_mime.py
"""Exact literal payloads through existing native MIME factory, no clipboard."""

from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from test_spacing_worksheet import QtCore, GUI, drain, valid
from fontlabapp.glyphs.common.model import Font, Glyph, Production, analyze
from fontlabapp.glyphs.common.ui import panel_type
import fontlabapp.glyphs.common.lifetime as lifetime

QT = NS(QtCore=QtCore, QtGui=GUI)


def snapshot():
    return analyze(
        (
            Font(
                1,
                2,
                "Family",
                tuple(
                    Glyph(str(i), (code,))
                    for i, code in enumerate((0, 0xA0, 0x2028, 0x1F600))
                ),
            ),
        ),
        lambda name, **kw: Production(name, "database"),
    )


def test_explicit_buttons_transfer_exact_characters_and_full_report_to_owned_sink_only():
    received = []
    p = panel_type(GUI, qt=QT)(None, snapshot(), Mock(), copy_sink=received.append)
    assert not received, "Opening/reporting never reads or writes clipboard"
    p.copy_characters_button.click()
    p.copy_report_button.click()
    assert len(received) == 2
    for mime, field in zip(received, ("characters", "source_text"), strict=True):
        assert mime.text() == snapshot()[field]
        assert bytes(mime.data("text/plain")) == snapshot()[field].encode("utf-8"), (
            "NUL/NBSP/LS/non-BMP and all trailing delimiters must survive the actual MIME payload"
        )
    p.close()
    drain()
    assert all(valid(mime) for mime in received), (
        "Successful handoff belongs to receiving sink, not the retired report panel"
    )
    for mime in received:
        mime.deleteLater()
    drain()


@pytest.mark.parametrize("accepted", [False, True])
def test_failed_handoff_retains_unknown_ownership_until_explicit_proven_resolution(
    accepted,
):
    received = []
    error = RuntimeError("sink transfer failed")

    def sink(mime):
        if accepted:
            received.append(mime)
        raise error

    p = panel_type(GUI, qt=QT)(None, snapshot(), Mock(), copy_sink=sink)
    p.copy_characters_button.click()
    mime = p.literal_copy.mime
    assert p.literal_copy.unknown and valid(mime) and id(p) in lifetime.pending()
    assert lifetime.pending()[id(p)].errors[0].exceptions[0] is error
    assert "ownership is unknown" in p.status.text(), (
        "Expose the retained ownership recovery hold in the actual panel"
    )
    p.copy_characters_button.click()
    assert p.literal_copy.mime is mime, "Never overwrite the unresolved MIME owner"
    assert not p.close() and valid(mime)
    p.literal_copy.resolve(transferred=accepted, check=lambda: None)
    receipts = lifetime.recover(deadline=lifetime.monotonic() + 3)
    assert receipts[0].owner is p and receipts[0].errors
    drain()
    assert valid(mime) is accepted
    for item in received:
        item.deleteLater()
    drain()


def test_staging_failure_releases_owned_mime_without_handoff_and_cleanup_failure_is_retained(
    monkeypatch,
):
    import fontlabapp.glyphs.common.mime as module

    received = []
    p = panel_type(GUI, qt=QT)(None, snapshot(), Mock(), copy_sink=received.append)
    monkeypatch.setattr(
        module, "set_mime_text", Mock(side_effect=RuntimeError("MIME staging failed"))
    )
    p.copy_report_button.click()
    assert (
        not received
        and p.literal_copy.mime is None
        and "staging failed" in p.status.text()
    )
    p.close()
    drain()


def test_owned_mime_delete_overrun_preserves_scheduled_stage_and_failure_receipt(
    monkeypatch,
):
    from fontlabapp.glyphs.common.mime import LiteralCopy

    editor = GUI.QPlainTextEdit()
    copy = LiteralCopy(QT, editor, Mock())
    mime = GUI.QPlainTextEdit.createMimeDataFromSelection(editor)
    copy.mime = mime
    calls = []

    def check():
        calls.append(1)
        if len(calls) == 2:
            raise TimeoutError("delete overrun")

    with pytest.raises(TimeoutError):
        copy.dispose(check)
    assert copy.mime is mime and copy.delete_scheduled
    copy.dispose(lambda: None)
    assert copy.mime is None
    with pytest.raises(ValueError):
        copy.resolve(transferred=True, check=lambda: None)
    editor.deleteLater()
    drain()


def test_copy_deadline_readback_and_nonvoid_sink_failures_are_explicit(monkeypatch):
    import fontlabapp.glyphs.common.mime as module
    from fontlabapp.glyphs.common.mime import LiteralCopy

    editor = GUI.QPlainTextEdit()
    sink = Mock()
    copy = LiteralCopy(QT, editor, sink)

    def cancel():
        raise InterruptedError("copy cancelled")

    with pytest.raises(InterruptedError):
        copy.send("a", cancel)
    assert copy.mime is None and not sink.called
    monkeypatch.setattr(module, "read_text", lambda *args: "truncated")
    with pytest.raises(ValueError, match="did not retain"):
        copy.send("A\0B", lambda: None)
    assert not sink.called and not copy.unknown
    copy.dispose(lambda: None)
    monkeypatch.undo()
    copy.sink = lambda mime: False
    with pytest.raises(RuntimeError, match="void ownership"):
        copy.send("a", lambda: None)
    assert copy.unknown and copy.mime is not None
    copy.resolve(transferred=False, check=lambda: None)
    editor.deleteLater()
    drain()


def test_staging_failure_retains_failed_disposal_receipt_then_explicit_recovery(
    monkeypatch,
):
    import fontlabapp.glyphs.common.mime as module

    p = panel_type(GUI, qt=QT)(None, snapshot(), Mock(), copy_sink=Mock())
    original = p.literal_copy.dispose
    monkeypatch.setattr(
        module, "set_mime_text", Mock(side_effect=RuntimeError("MIME staging failed"))
    )
    monkeypatch.setattr(
        p.literal_copy, "dispose", Mock(side_effect=RuntimeError("MIME delete failed"))
    )
    p.copy_report_button.click()
    assert p.literal_copy.mime is not None and id(p) in lifetime.pending()
    assert "MIME delete failed" in str(
        lifetime.pending()[id(p)].errors[0].exceptions[1]
    )
    monkeypatch.setattr(p.literal_copy, "dispose", original)
    lifetime.recover(deadline=lifetime.monotonic() + 3)
    drain()


def test_default_native_handoff_slot_uses_only_injected_owned_sink_and_closed_actions_are_fenced():
    received = []
    gui = NS(**vars(GUI))
    gui.QApplication = NS(clipboard=lambda: NS(setMimeData=received.append))
    qt = NS(QtCore=QtCore, QtGui=gui)
    p = panel_type(gui, qt=qt)(None, snapshot(), Mock())
    assert not received
    p.copy_characters_button.click()
    assert received[0].text() == snapshot()["characters"]
    p.close()
    p.copy_text("characters")
    drain()
    assert len(received) == 1
    received[0].deleteLater()
    drain()
    p = panel_type(GUI)(None, snapshot(), Mock())
    p.copy_characters_button.click()
    assert (
        "requires the FontLab Qt binding" in p.status.text() and not lifetime.pending()
    )
    p.close()
    drain()


def test_post_handoff_deadline_reports_completed_transfer_without_claiming_rollback(
    monkeypatch,
):
    import fontlabapp.glyphs.common.ui as panel

    now = NS(value=0)
    received = []

    def sink(mime):
        received.append(mime)
        now.value = 3

    p = panel_type(GUI, qt=QT)(None, snapshot(), Mock(), copy_sink=sink)
    monkeypatch.setattr(panel, "monotonic", lambda: now.value)
    p.copy_characters_button.click()
    assert p.literal_copy.mime is None and p.literal_copy.last_transfer
    assert "completed before" in p.status.text() and not lifetime.pending()
    now.value = 0
    p.close()
    drain()
    received[0].deleteLater()
    drain()
