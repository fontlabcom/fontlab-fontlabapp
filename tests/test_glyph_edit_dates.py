# this_file: tests/test_glyph_edit_dates.py
"""Keep forward live dates equal to history after native UI observers run."""

from module_paths import module_name as _module_name
from contextlib import nullcontext
from importlib import import_module
from types import SimpleNamespace as NS

import pytest


@pytest.mark.parametrize("name", ["guide_rewrite", "guides", "anchor_copy"])
@pytest.mark.parametrize("observer", ["notify", "update"])
@pytest.mark.parametrize("fails", [False, True])
def test_forward_observer_cannot_change_committed_history_date(
    monkeypatch, name, observer, fails
):
    api = import_module(_module_name(name))
    glyph = NS(name="H", lastModified="before", checkInitHistoryState=lambda _: None)
    layer = NS(
        autoLayer=False,
        checkInitHistoryState=lambda _: None,
        appendGuidelines=lambda _: None,
    )
    history = []

    def notify(title, items):
        assert items == [layer, glyph]
        history.append(glyph.lastModified)
        if observer == "notify":
            glyph.lastModified = "later UTC second"
            if fails:
                raise RuntimeError("owned observer failure")

    def update():
        if observer == "update":
            glyph.lastModified = "later UTC second"
            if fails:
                raise RuntimeError("owned observer failure")

    native = NS(flItems=lambda: NS(notifyChangesApplied=notify), UpdateAll=update)
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "committed UTC second")))
    monkeypatch.setattr(
        api, "_native", lambda module: native if module == "fontlab" else qt
    )
    with (
        pytest.raises(RuntimeError, match="owned observer failure")
        if fails
        else nullcontext()
    ):
        if name == "guides":
            monkeypatch.setattr(api, "require_safe_targets", lambda *args: None)
            monkeypatch.setattr(api, "new_guide", lambda value: value)
            api.add_guides(object(), [(glyph, layer, [(0, 321, 0, "owned")])])
        else:
            monkeypatch.setattr(api, "_write", lambda *args: None)
            api._apply([(glyph, layer, [])], "Owned date boundary")
    assert history == ["committed UTC second"], (
        "Use one timestamp before history capture"
    )
    assert glyph.lastModified == history[0], (
        "A forward notification changed the value Redo will restore"
    )
