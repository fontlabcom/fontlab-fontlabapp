# this_file: tests/test_master_text_controller.py
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
import fontlabapp.masters.text.controller as controller


def test_launch_captures_opening_font_and_injects_exact_owned_panel(monkeypatch):
    opening = object()
    monkeypatch.setattr(controller, "read", Mock(return_value=opening))
    panel = Mock(return_value="owned panel")
    factory = Mock(return_value=panel)
    monkeypatch.setattr(controller, "panel_type", factory)
    binding = NS(QtCore=object(), QtGui=object())
    monkeypatch.setattr(controller, "_native", lambda name: binding)
    monkeypatch.setattr(
        controller, "show_script_dialog", lambda build, key: build("parent")
    )
    assert controller.show(settings="isolated", directory="local") == "owned panel"
    assert panel.call_args.args == ("parent", opening, controller.open_proof)
    assert panel.call_args.kwargs == {
        "settings": "isolated",
        "directory": "local",
        "deadline": controller.read.call_args.args[0] + 0.5,
    }
    assert controller.read.call_args.kwargs["check"]() is None
    monkeypatch.setattr(controller, "read", Mock(side_effect=ValueError("Open a font")))
    with pytest.raises(ValueError, match="font"):
        controller.show()


@pytest.mark.parametrize(
    "next_failure", [True, False], ids=["second-failure", "second-success"]
)
def test_failed_construction_owner_fences_every_new_launch_before_capture(
    monkeypatch, next_failure
):
    import sys

    owner = object()
    registry = {"master_text_failed": owner}
    monkeypatch.setitem(sys.__dict__, "_fontlab_samples", registry)
    capture = Mock(return_value=object())
    launch = Mock(
        side_effect=ValueError("second construction failed") if next_failure else None,
        return_value="new panel",
    )
    monkeypatch.setattr(controller, "read", capture)
    monkeypatch.setattr(controller, "_native", lambda name: NS(QtCore=None, QtGui=None))
    monkeypatch.setattr(controller, "panel_type", Mock(return_value=launch))
    monkeypatch.setattr(
        controller, "show_script_dialog", lambda build, key: build(None)
    )
    with pytest.raises(RuntimeError, match="cleanup"):
        controller.show()
    assert not capture.called and not launch.called, (
        "Unresolved ownership must fence both failed and successful retries"
    )
    retained = registry["master_text_failed"]
    assert retained is owner or any(
        record.owner is owner for record in retained.values()
    ), "Never lose the original retained owner"
