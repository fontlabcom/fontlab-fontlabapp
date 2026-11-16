# this_file: tests/test_common_glyphs_priority.py
"""Controller priority preserves the existing retained-owner failure protocol."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from test_spacing_worksheet import GUI, QtCore, drain, valid
from test_common_glyphs_panel import report
import fontlabapp.glyphs.common.controller as controller
import fontlabapp.glyphs.common.lifetime as lifetime


@pytest.fixture
def setup(monkeypatch):
    parent = GUI.QWidget()
    made, events = [], []
    primary, cleanup = RuntimeError("display failed"), RuntimeError("cleanup failed")
    state = NS(fail=None, cleanup_fail=False)

    class Panel(GUI.QDialog):
        def __init__(self, parent, snapshot, refresh, **kwargs):
            super().__init__(parent)
            self.snapshot = snapshot
            self.setModal(False)
            self.setWindowTitle("Common Glyphs")
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint)
            made.append(self)

        def setWindowFlags(self, flags):
            events.append("flags")
            if state.fail == "flags":
                raise primary
            super().setWindowFlags(flags)

        def show(self):
            events.append("show")
            assert self.windowFlags() & QtCore.Qt.WindowMinimizeButtonHint
            assert self.windowFlags() & QtCore.Qt.WindowStaysOnTopHint, (
                "Priority must be set before first show"
            )
            if state.fail == "show":
                raise primary
            super().show()

        def raise_(self):
            events.append("raise")
            if state.fail == "raise":
                raise primary
            super().raise_()

        def recover_owned(self, deadline, **kwargs):
            events.append("recover")
            if state.cleanup_fail:
                raise cleanup
            self.close()
            self.deleteLater()

    monkeypatch.setattr(
        controller,
        "_native",
        lambda name: NS(QtGui=GUI, QtCore=QtCore)
        if name == "PythonQt"
        else NS(MainWindow=lambda: parent),
    )
    monkeypatch.setattr(controller, "capture", Mock(return_value=report()))
    monkeypatch.setattr(controller, "panel_type", lambda *args, **kwargs: Panel)
    yield NS(
        parent=parent,
        made=made,
        events=events,
        state=state,
        primary=primary,
        cleanup=cleanup,
    )
    state.cleanup_fail = False
    if lifetime.pending():
        lifetime.recover(deadline=lifetime.monotonic() + 3)
    if lifetime.current() is not None:
        panel = lifetime.current()
        panel.recover_owned(lifetime.monotonic() + 3)
        lifetime.release(panel)
    parent.deleteLater()
    drain()


def test_priority_before_show_preserves_parent_modal_title_snapshot_and_replaces_one_owner(
    setup,
):
    a = controller.show(Mock())
    assert (
        a.parent() is setup.parent
        and not a.isModal()
        and a.windowTitle() == "Common Glyphs"
    )
    assert a.snapshot == report() and lifetime.current() is a
    b = controller.show(Mock())
    drain()
    assert not valid(a) and valid(b) and lifetime.current() is b
    assert setup.events == [
        "flags",
        "flags",
        "show",
        "raise",
        "recover",
        "flags",
        "flags",
        "show",
        "raise",
    ]


@pytest.mark.parametrize("stage", ["flags", "show", "raise"])
@pytest.mark.parametrize("cleanup_fail", [False, True])
def test_display_failure_preserves_exact_error_and_failed_owner_fence(
    setup, stage, cleanup_fail
):
    # Constructor uses a harmless setter; fail only the controller display stage.
    original = controller.panel_type

    def panel_type(*args, **kwargs):
        base = original(*args, **kwargs)

        class Constructed(base):
            def __init__(self, *args, **kwargs):
                requested = setup.state.fail
                setup.state.fail = None
                super().__init__(*args, **kwargs)
                setup.state.fail = requested

        return Constructed

    controller.panel_type = panel_type
    setup.state.fail, setup.state.cleanup_fail = stage, cleanup_fail
    try:
        with pytest.raises(ExceptionGroup if cleanup_fail else RuntimeError) as caught:
            controller.show(Mock())
        owner = setup.made[-1]
        if cleanup_fail:
            assert caught.value.exceptions == (setup.primary, setup.cleanup)
            assert (
                lifetime.pending()[id(owner)].owner is owner
                and lifetime.current() is owner
            )
            captures = controller.capture.call_count
            with pytest.raises(RuntimeError, match="cleanup"):
                controller.show(Mock())
            assert controller.capture.call_count == captures
            setup.state.cleanup_fail = False
            receipts = lifetime.recover(deadline=lifetime.monotonic() + 3)
            assert receipts[0].errors[0] is caught.value
        else:
            assert (
                caught.value is setup.primary
                and lifetime.current() is None
                and not lifetime.pending()
            )
        drain()
        assert not valid(owner)
    finally:
        controller.panel_type = original
