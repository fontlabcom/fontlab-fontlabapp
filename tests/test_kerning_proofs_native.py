# this_file: tests/test_kerning_proofs_native.py
"""Complete public proof calls through actual shared tab mechanics, native-shaped host."""

from types import SimpleNamespace as NS
import pytest
import fontlabapp.kerning.proofs as api
import fontlabapp.core.scripting as scripting
import fontlabapp.proof.tabs.text as tabs
from test_text_tab import host


@pytest.mark.parametrize("mode", api.MODES)
def test_all_proofs_use_exact_native_slot_with_complete_text_cleanup_and_flags(
    host, monkeypatch, mode
):
    host.package.master = "Regular"
    monkeypatch.setattr(scripting, "current_package", lambda: host.package)
    monkeypatch.setattr(api, "monotonic", lambda: 0.0)
    api.run(mode)
    expected = list(api.proof_texts(mode))
    assert host.state.tabs == expected
    assert host.state.calls.count("create") == len(expected)
    assert host.state.calls.count("disconnect") == len(expected)
    assert host.state.calls.count("delete") == len(expected)
    assert host.shape.active is False and host.old_shape.active is True


@pytest.mark.parametrize("change", ["font", "master", "deadline"])
def test_kernking_second_tab_fences_changed_context_without_touching_first(
    host, monkeypatch, change
):
    host.package.master = "Regular"
    monkeypatch.setattr(scripting, "current_package", lambda: host.package)
    monkeypatch.setattr(api, "monotonic", lambda: 0.0)
    original = tabs._open_tab

    def first_then_change(*a, **kw):
        original(*a, **kw)
        if change == "font":
            host.state.current = False
        elif change == "master":
            host.package.master = "Bold"
        else:
            host.state.seconds = 3.0

    monkeypatch.setattr(tabs, "_open_tab", first_then_change)
    with pytest.raises((ValueError, TimeoutError)):
        api.run("kernking")
    assert host.state.tabs == [api.proof_texts("kernking")[0]]
    assert host.state.calls.count("create") == 1
    assert host.state.calls[-2:] == ["disconnect", "delete"]
    assert host.shape.active is False and host.old_shape.active is True


@pytest.mark.parametrize("failure", ["bootstrap", "emit", "connect", "disconnect"])
def test_public_proof_propagates_native_failures_and_keeps_full_cleanup(
    host, monkeypatch, failure
):
    host.package.master = "Regular"
    monkeypatch.setattr(scripting, "current_package", lambda: host.package)
    monkeypatch.setattr(api, "monotonic", lambda: 0.0)
    if failure == "connect":
        host.state.connect = False
    elif failure == "disconnect":
        host.state.disconnect = False
    else:
        host.state.failure = failure
    with pytest.raises(RuntimeError):
        api.run("kernsym")
    assert host.state.calls[-1] == "delete"
    assert host.shape.active is False and host.old_shape.active is True
