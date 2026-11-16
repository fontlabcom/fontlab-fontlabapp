# this_file: tests/test_studio_kerning_proof_demo.py
"""The Kerning Proof studio demo opens once and contains expected launch errors."""

from _demo_support import stub_natives

import importlib
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).parents[1] / "Scripts/Kerning/Kerning Proof Studio Demo.py"


@pytest.fixture
def launch(monkeypatch):
    import fontlabapp
    kerning_proof = importlib.import_module("fontlabapp.studios.kerning_proof")

    calls, messages = [], []
    qt = SimpleNamespace(QtGui=SimpleNamespace(QMessageBox=SimpleNamespace(Ok=1)))
    parent = object()
    stub_natives(monkeypatch, fontlabapp, lambda name: qt if name == 'PythonQt' else SimpleNamespace(MainWindow=lambda: parent))
    monkeypatch.setattr(kerning_proof, "show", lambda: calls.append("show"))
    monkeypatch.setitem(sys.modules, "fontlabapp.qt.dialogs", SimpleNamespace(run_standard_message_box=lambda *args: messages.append(args)))
    return SimpleNamespace(module=kerning_proof, calls=calls, messages=messages, qt=qt, parent=parent)


def test_demo_when_imported_then_defers_opening_until_main(launch):
    namespace = runpy.run_path(str(PATH), run_name="inspection")
    assert launch.calls == [] and launch.messages == []
    namespace["main"]()
    assert launch.calls == ["show"] and launch.messages == []


def test_demo_when_run_as_script_then_opens_one_studio(launch):
    runpy.run_path(str(PATH), run_name="__main__")
    assert launch.calls == ["show"] and launch.messages == []


@pytest.mark.parametrize("error_type", [ImportError, ValueError, RuntimeError])
def test_demo_when_launch_refused_then_reports_once_without_retry(launch, monkeypatch, error_type):
    def fail():
        launch.calls.append("show")
        raise error_type("Captured font unavailable")

    monkeypatch.setattr(launch.module, "show", fail)
    namespace = runpy.run_path(str(PATH), run_name="inspection")
    namespace["main"]()
    assert launch.calls == ["show"]
    assert launch.messages == [(launch.qt, launch.parent, "Kerning Proof Studio Demo",
                                "Kerning Proof did not open: Captured font unavailable", "Warning", 1)]


def test_demo_when_studio_import_unavailable_then_reports_once(launch, monkeypatch):
    monkeypatch.setitem(sys.modules, "fontlabapp.studios.kerning_proof", None)
    namespace = runpy.run_path(str(PATH), run_name="inspection")
    namespace["main"]()
    assert launch.calls == []
    assert len(launch.messages) == 1
    message = launch.messages[0]
    assert message[:3] == (launch.qt, launch.parent, "Kerning Proof Studio Demo")
    assert "fontlabapp.studios.kerning_proof" in message[3]
    assert message[4:] == ("Warning", 1)
