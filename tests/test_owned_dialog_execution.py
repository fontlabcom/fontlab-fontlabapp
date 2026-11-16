# this_file: tests/test_owned_dialog_execution.py
"""Configured Qt dialogs execute and release through one injected owned boundary."""

from types import SimpleNamespace

import pytest

import fontlabapp.qt.dialogs as api


@pytest.mark.parametrize("failure", [None, "configure", "exec", "read", "interrupt"])
def test_owned_execution_always_deletes_after_configuration_execution_or_read_failure(
    failure,
):
    events = []

    def step(name, result=None):
        events.append(name)
        if failure == name:
            raise ValueError(name)
        if failure == "interrupt" and name == "exec":
            raise KeyboardInterrupt("owned interrupt")
        return result

    dialog = SimpleNamespace(
        exec=lambda: step("exec", 7), deleteLater=lambda: step("delete")
    )
    configure = lambda current: step("configure")

    def read(current, accepted):
        assert current is dialog and accepted == 7
        return step("read", "result")

    if failure:
        with pytest.raises(KeyboardInterrupt if failure == "interrupt" else ValueError):
            api.run_owned_dialog(dialog, configure, read)
    else:
        assert api.run_owned_dialog(dialog, configure, read) == "result"
    assert events[0] == "configure" and events[-1] == "delete"
    assert events.count("delete") == 1


def test_owned_execution_leaves_cancel_result_policy_to_the_caller():
    dialog = SimpleNamespace(exec=lambda: 0, deleteLater=lambda: None)
    assert api.run_owned_dialog(
        dialog,
        lambda current: None,
        lambda current, result: (current is dialog, result),
    ) == (True, 0)
