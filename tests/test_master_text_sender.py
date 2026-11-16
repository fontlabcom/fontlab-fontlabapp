# this_file: tests/test_master_text_sender.py
"""Retain failed senders and all body/cleanup errors under bounded recovery."""

from types import SimpleNamespace as NS
import pytest
from fontlabapp.masters.text.sender import sender, PENDING, recover


class Emitter:
    def __init__(self):
        self.connected = self.deleted = False
        self.disconnect_fail = self.delete_fail = False
        self.texts = []

    def setText(self, text):
        self.texts.append(text)

    def connect(self, *args):
        self.connection = args
        self.connected = True
        return True

    def disconnect(self, *args):
        assert args == self.connection
        if self.disconnect_fail:
            return False
        self.connected = False
        return True

    def deleteLater(self):
        assert not self.connected, "Do not delete a sender whose disconnect failed"
        if self.delete_fail:
            raise RuntimeError("delete failed")
        self.deleted = True


def test_sender_owns_exact_private_native_slot_and_deletes_only_after_disconnect():
    emitter, receiver = Emitter(), object()
    with sender(
        NS(QLineEdit=lambda: emitter), receiver, lambda: None, lambda: None
    ) as owned:
        assert owned is emitter
        owned.setText("")
    assert emitter.deleted and not emitter.connected and not PENDING
    assert emitter.connection == (
        "textChanged(QString)",
        receiver,
        "doCreateTextBlock(QString)",
    )


@pytest.mark.parametrize(
    "body,disconnect,delete",
    [
        (True, False, False),
        (False, True, False),
        (True, True, False),
        (False, False, True),
        (True, False, True),
    ],
)
def test_body_and_cleanup_failures_remain_visible_and_recoverable(
    body, disconnect, delete
):
    emitter = Emitter()
    emitter.disconnect_fail, emitter.delete_fail = disconnect, delete
    try:
        with pytest.raises(BaseException) as caught:
            with sender(
                NS(QLineEdit=lambda: emitter), object(), lambda: None, lambda: None
            ):
                if body:
                    raise ValueError("body failed")
        if body:
            assert "body failed" in str(caught.value) or "body failed" in repr(
                caught.value
            )
        if disconnect or delete:
            assert PENDING and PENDING[-1].emitter is emitter
            with pytest.raises(ValueError, match="cleanup"):
                with sender(NS(), object(), lambda: None, lambda: None):
                    pass
            emitter.disconnect_fail = emitter.delete_fail = False
            recover(check=lambda: None)
            assert emitter.deleted and not PENDING
    finally:
        PENDING.clear()


def test_cleanup_deadline_before_disconnect_retains_sender_and_stops_setters():
    emitter = Emitter()

    def expired():
        raise TimeoutError("cleanup deadline")

    try:
        with pytest.raises(RuntimeError, match="cleanup"):
            with sender(NS(QLineEdit=lambda: emitter), object(), lambda: None, expired):
                pass
        assert emitter.connected and not emitter.deleted and PENDING
        with pytest.raises(TimeoutError):
            recover(check=expired)
        assert PENDING
        recover(check=lambda: None)
        assert emitter.deleted
    finally:
        PENDING.clear()


def test_connect_and_bootstrap_failure_cleanup_and_cancellation():
    emitter = Emitter()
    emitter.connect = lambda *a: False
    with pytest.raises(RuntimeError, match="connection"):
        with sender(
            NS(QLineEdit=lambda: emitter), object(), lambda: None, lambda: None
        ):
            pass
    assert emitter.deleted

    def cancel():
        raise InterruptedError("cancelled")

    with pytest.raises(InterruptedError):
        with sender(NS(), object(), cancel, lambda: None):
            pass
