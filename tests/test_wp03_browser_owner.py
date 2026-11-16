# this_file: tests/test_wp03_browser_owner.py
"""Browser repeat-launch preserves failed owners until terminal cleanup."""
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401


@pytest.mark.parametrize("refusal", ["false", "incomplete", "error"])
def test_repeat_launch_retains_owner_until_close_completes(studio_qt, monkeypatch, refusal):  # noqa: F811
    from fontlabapp.studios.kerning_browser.owner import open_owned, KEY
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    calls = []
    def build():
        shell = NS(_close_complete=False, show=lambda: calls.append("show"))
        shell.close = lambda: setattr(shell, "_close_complete", True)
        return shell
    old = open_owned(build)
    terminal = old.close
    def refuse():
        old.closed = True
        if refusal == "error":
            raise RuntimeError("close refused")
        return False if refusal == "false" else None
    old.close = refuse
    def forbidden():
        pytest.fail("A second owner must not be allocated before cleanup")
    if refusal == "error":
        with pytest.raises(RuntimeError, match="close refused"):
            open_owned(forbidden)
    else:
        assert open_owned(forbidden) is old and calls == ["show"]
    assert sys._fontlab_samples[KEY] is old
    old.close = terminal
    replacement = open_owned(build)
    assert old._close_complete and replacement is not old
    assert sys._fontlab_samples[KEY] is replacement
    replacement.close()
    assert KEY not in sys._fontlab_samples


def test_factory_failure_preserves_other_key_and_default_registry(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.studios.kerning_browser.owner import open_owned
    monkeypatch.delattr(sys, "_fontlab_samples", raising=False)
    def fail():
        raise RuntimeError("factory refused")
    with pytest.raises(RuntimeError, match="factory refused"):
        open_owned(fail)
    assert sys._fontlab_samples == {}
    sys._fontlab_samples["unrelated"] = marker = object()
    with pytest.raises(RuntimeError, match="factory refused"):
        open_owned(fail)
    assert sys._fontlab_samples == {"unrelated": marker}


def test_actual_browser_replacement_and_close_release_registry(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.studios.kerning_browser.app import show
    from fontlabapp.studios.kerning_browser.owner import KEY
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    args = dict(package=lambda: None, font=lambda: None, preview=lambda *_: None, consolidated=True)
    first = show(**args)
    second = show(**args)
    assert first._close_complete and first._delete_scheduled and not first.connections
    assert sys._fontlab_samples[KEY] is second
    second.close_button.click()
    assert second._close_complete and second._delete_scheduled and not second.connections
    assert KEY not in sys._fontlab_samples


def test_late_old_close_cannot_remove_a_replacement_key(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.studios.kerning_browser.owner import open_owned, KEY
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    shell = NS(_close_complete=False)
    shell.close = lambda: setattr(shell, "_close_complete", True)
    old = open_owned(lambda: shell)
    sys._fontlab_samples[KEY] = replacement = object()
    old.close()
    assert old._close_complete and sys._fontlab_samples[KEY] is replacement
