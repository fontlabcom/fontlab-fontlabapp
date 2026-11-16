# this_file: tests/plugmix/test_issue210_host_edges.py
"""Retain complete migrated host coverage on absent and partial native state."""

from types import SimpleNamespace as NS

import pytest

from fontlabapp.plugins import general, registry, tool
from fontlabapp.plugins.filters import host as filter_host
from fontlabapp.plugins.kinds import Services
from fontlabapp.plugins.tools.host import ToolHost, UnsupportedCapability
from test_plugmix_filter import MenuOwner, StubDialog
from test_plugmix_tool_general import environment


def test_tools_when_absent_or_repeated_then_no_duplicate_or_native_call(tmp_path):
    services, state, workspace, errors = environment(tmp_path)
    host = ToolHost(services, state)
    host.install()
    before = len(workspace.registered)
    host._register("smart_select")
    assert len(workspace.registered) == before
    host._unregister("absent")
    with pytest.raises(KeyError):
        host.toggle("absent")
    host.services = Services(services.qt, object(), services.menus, services.painters, services.sink)
    with pytest.raises(UnsupportedCapability):
        host._workspace()
    host.services = services
    host.close()


def test_general_owner_and_tool_when_target_absent_then_no_mutation(tmp_path, monkeypatch):
    services, state, workspace, errors = environment(tmp_path)
    plugin = general.General()
    context = general.GeneralContext(services, plugin)
    token = context.menus.add_action("Window", "Test", lambda: None)
    context.menus.remove(token)
    assert token not in context.menus.tokens
    unowned = services.menus.add_action("Window", "Other", lambda: None)
    context.menus.remove(unowned)
    monkeypatch.setattr(general.snapshot, "active_glyph", lambda fontlab: None)
    assert context.zoom_selected() is False
    tool.ToolContext(services).select((0,))
    context.close()


def test_filter_host_when_saved_filter_missing_then_skip(tmp_path):
    state = registry.Registry(tmp_path)
    state._filter_wanted = {"missing"}
    owner = MenuOwner()
    host = filter_host.FilterHost(Services(None, None, owner, None, lambda *args: None), state)
    host.install()
    assert owner.actions == {}


def test_filter_host_when_partial_or_noop_apply_then_status_and_close(tmp_path, monkeypatch):
    owner, redraws, deferred = MenuOwner(), [], []
    state = registry.Registry(tmp_path)
    services = Services(NS(QtCore=NS(QTimer=NS(singleShot=lambda delay, cb: deferred.append(cb)))), NS(UpdateActiveCanvas=lambda: redraws.append(True)), owner, None, lambda *args: None)
    host = filter_host.FilterHost(services, state)
    monkeypatch.setattr(filter_host, "FilterDialog", StubDialog)
    monkeypatch.setattr(filter_host.snapshot, "selected_layers", lambda: NS(occurrences=(object(),)))
    host.run("delete_small_paths")
    dialog = StubDialog.instances[-1]
    monkeypatch.setattr(filter_host, "apply_filter", lambda *args: (NS(refused=["bad"], skipped=[], rows=[]), {"layers": 1}))
    dialog.on_apply({"threshold": 3})
    assert dialog.status.text == "Skipped: bad" and redraws == [True] and not deferred
    monkeypatch.setattr(filter_host, "apply_filter", lambda *args: (NS(refused=[], skipped=[], rows=[]), None))
    dialog.on_apply({"threshold": 3})
    assert len(deferred) == 1 and redraws == [True]
    deferred.pop()()
    assert not owner.windows
