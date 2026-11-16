# this_file: tests/test_demo_scripts_plugmix.py
"""Offline runs of Scripts/Utilities/Plugmix Demo.py under stubbed natives.

Plugmix's boot, registry and the message box are stubbed; the run checks the
listing by kind, the install-failure message and that importing runs nothing.
Offline results are not native FontLab acceptance.
"""

from types import SimpleNamespace

import fontlabapp.plugins
from _demo_support import Recorder, qt_namespace, run_script, script_path, stub_module

DEMO = script_path("Utilities", "Plugmix Demo")


def setup(monkeypatch, install):
    """Stub the natives, boot, registry and message box; return the box recorder."""
    qt = qt_namespace()
    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(monkeypatch, "fontlab", MainWindow=lambda: "main-window")
    stub_module(monkeypatch, "fontlabapp.plugins.boot", install=install)
    plugins = {
        "reporter": {"node_count": SimpleNamespace(title="Node Count"), "blindfold": SimpleNamespace(title="Blindfold")},
        "filter": {"delete_small_paths": SimpleNamespace(title="Delete Small Paths")},
    }
    registry = stub_module(
        monkeypatch,
        "fontlabapp.plugins.registry",
        available=lambda kind: plugins.get(kind, {}),
        enabled=lambda: ("node_count",),
    )
    # An earlier test may have bound the real submodule on the package already.
    monkeypatch.setattr(fontlabapp.plugins, "registry", registry, raising=False)
    box = Recorder()
    stub_module(monkeypatch, "fontlabapp.qt.dialogs", run_standard_message_box=box)
    return box


def test_plugmix_demo_when_main_then_installs_and_lists_plugins_by_kind(monkeypatch) -> None:
    install = Recorder()
    box = setup(monkeypatch, install)
    run_script(DEMO)
    assert install.calls == [((), {})], "installs once"
    (args, _), = box.calls
    assert args[1:3] == ("main-window", "Plugmix Demo") and args[4] == "Information"
    assert args[3].splitlines() == [
        "Reporters (2):", "  Blindfold", "  Node Count (on)",
        "Filters (1):", "  Delete Small Paths",
        "Palettes (0):", "Tools (0):", "Generals (0):",
    ]


def test_plugmix_demo_when_install_fails_then_warns_and_lists_nothing(monkeypatch) -> None:
    def fail():
        raise ValueError("other config directory")

    box = setup(monkeypatch, fail)
    run_script(DEMO)
    (args, _), = box.calls
    assert args[3] == "Plugmix did not install: other config directory" and args[4] == "Warning"


def test_plugmix_demo_when_imported_then_nothing_runs(monkeypatch) -> None:
    install = Recorder()
    box = setup(monkeypatch, install)
    run_script(DEMO, run_name="imported")
    assert install.calls == [] and box.calls == []
