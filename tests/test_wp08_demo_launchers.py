# this_file: tests/test_wp08_demo_launchers.py
"""WP08 App demo launchers: open the window, or warn why not."""

from _demo_support import stub_natives

import importlib
import runpy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]

# (demo path under Scripts, TITLE, fontui module, name used in the warning)
LAUNCHERS = [
    ("Reports/Font Revision Comparison Demo.py", "Font Revision Comparison Demo", "font_revision_comparison", "Font Revision Comparison"),
    ("Reports/Geometry Audit Demo.py", "Geometry Audit Demo", "geometry_audit", "Geometry Audit"),
    ("Reports/Master Structure Audit Demo.py", "Master Structure Audit Demo", "master_structure_audit", "Master Structure Audit"),
    ("Reports/Metric Reports Demo.py", "Metric Reports Demo", "metric_reports", "Metric Reports"),
    ("Reports/Nodes Near Zones Demo.py", "Nodes Near Zones Demo", "nodes_near_zones", "Nodes Near Zones"),
    ("Reports/Open Contours Demo.py", "Open Contours Demo", "open_contours", "Open Contours"),
    ("Reports/Snapshot Audit Demo.py", "Snapshot Audit Demo", "geometry_audit", "Snapshot Audit"),
    ("Utilities/Reference Image Viewer Demo.py", "Reference Image Viewer Demo", "reference_images", "Reference Image Viewer"),
]
IDS = [row[0].rsplit("/", 1)[1] for row in LAUNCHERS]


@pytest.mark.parametrize(("demo", "title", "module", "name"), LAUNCHERS, ids=IDS)
def test_demo_when_run_as_main_then_shows_window(studio_qt, monkeypatch, demo, title, module, name):
    window = importlib.import_module(f"fontlabapp.fontui.{module}")
    calls: list[str] = []
    monkeypatch.setattr(window, "show", lambda: calls.append("show"))
    runpy.run_path(str(ROOT / "Scripts" / demo), run_name="__main__")
    assert calls == ["show"], f"{demo} should call {module}.show() once"


@pytest.mark.parametrize(("demo", "title", "module", "name"), LAUNCHERS, ids=IDS)
def test_demo_when_show_raises_then_warns_with_reason(studio_qt, monkeypatch, demo, title, module, name):
    import fontlabapp
    from fontlabapp.qt import dialogs

    window = importlib.import_module(f"fontlabapp.fontui.{module}")

    def refuse() -> None:
        raise RuntimeError("no font")

    calls: list[tuple] = []
    monkeypatch.setattr(window, "show", refuse)
    stub_natives(monkeypatch, fontlabapp, lambda _n: NS(MainWindow=lambda: 'main', QtGui=NS(QMessageBox=NS(Ok=1))))
    monkeypatch.setattr(dialogs, "run_standard_message_box", lambda *a, **k: calls.append(a[2:5]))
    runpy.run_path(str(ROOT / "Scripts" / demo), run_name="__main__")
    assert calls == [(title, f"{name} did not open: no font", "Warning")]


@pytest.mark.parametrize(("demo", "title", "module", "name"), LAUNCHERS, ids=IDS)
def test_demo_when_imported_then_exposes_title(demo, title, module, name):
    assert runpy.run_path(str(ROOT / "Scripts" / demo), run_name="demo")["TITLE"] == title
