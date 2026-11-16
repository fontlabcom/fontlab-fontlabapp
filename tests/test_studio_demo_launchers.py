# this_file: tests/test_studio_demo_launchers.py
"""Launcher scripts for the Phase D studios: open the studio, or warn why not."""

from _demo_support import stub_natives

import importlib
import runpy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[1]

# (demo path under Scripts, TITLE, studio module, name used in the warning)
LAUNCHERS = [
    (
        "Anchors/Anchor Studio Demo.py",
        "Anchor Studio Demo",
        "anchor_studio",
        "Anchor Studio",
    ),
    (
        "Contours/Align & Nudge Demo.py",
        "Align & Nudge Demo",
        "align_nudge",
        "Align & Nudge",
    ),
    (
        "Contours/Outline Doctor Demo.py",
        "Outline Doctor Demo",
        "outline_doctor",
        "Outline Doctor",
    ),
    (
        "Contours/Transform Studio Demo.py",
        "Transform Studio Demo",
        "transform_studio",
        "Transform Studio",
    ),
    (
        "Kerning/Kerning Batch Window Demo.py",
        "Kerning Batch Window Demo",
        "kerning_batch",
        "Kerning Batch",
    ),
    (
        "Kerning/Kerning Browser Demo.py",
        "Kerning Browser Demo",
        "kerning_browser",
        "Kerning Browser",
    ),
    (
        "Kerning/Kerning Studio Demo.py",
        "Kerning Studio Demo",
        "kerning_studio",
        "Kerning Studio",
    ),
    (
        "Masters/Interpolation Doctor Demo.py",
        "Interpolation Doctor Demo",
        "interpolation_doctor",
        "Interpolation Doctor",
    ),
    (
        "Metrics/Spacing Studio Demo.py",
        "Spacing Studio Demo",
        "spacing_studio",
        "Spacing Studio",
    ),
    ("Proof/Proof Studio Demo.py", "Proof Studio Demo", "proof_studio", "Proof Studio"),
    ("Reports/Font Audit Demo.py", "Font Audit Demo", "font_audit", "Font Audit"),
]
IDS = [row[2] for row in LAUNCHERS]


@pytest.mark.parametrize(("demo", "title", "module", "name"), LAUNCHERS, ids=IDS)
def test_demo_when_run_as_main_then_shows_studio(
    monkeypatch, demo, title, module, name
):
    studio = importlib.import_module(f"fontlabapp.studios.{module}")
    calls: list[str] = []
    monkeypatch.setattr(studio, "show", lambda: calls.append("show"))
    runpy.run_path(str(ROOT / "Scripts" / demo), run_name="__main__")
    assert calls == ["show"], f"{demo} should call {module}.show() once"


@pytest.mark.parametrize(("demo", "title", "module", "name"), LAUNCHERS, ids=IDS)
def test_demo_when_show_raises_then_warns_with_reason(
    monkeypatch, demo, title, module, name
):
    import fontlabapp
    from fontlabapp.qt import dialogs

    studio = importlib.import_module(f"fontlabapp.studios.{module}")

    def refuse() -> None:
        raise RuntimeError("no font")

    calls: list[tuple] = []
    monkeypatch.setattr(studio, "show", refuse)
    stub_natives(monkeypatch, fontlabapp, lambda _n: NS(MainWindow=lambda: 'main', QtGui=NS(QMessageBox=NS(Ok=1))))
    monkeypatch.setattr(
        dialogs, "run_standard_message_box", lambda *a, **k: calls.append(a[2:5])
    )
    runpy.run_path(str(ROOT / "Scripts" / demo), run_name="__main__")
    assert calls == [(title, f"{name} did not open: no font", "Warning")]


@pytest.mark.parametrize(("demo", "title", "module", "name"), LAUNCHERS, ids=IDS)
def test_demo_when_imported_then_exposes_title(demo, title, module, name):
    assert (
        runpy.run_path(str(ROOT / "Scripts" / demo), run_name="demo")["TITLE"] == title
    )
