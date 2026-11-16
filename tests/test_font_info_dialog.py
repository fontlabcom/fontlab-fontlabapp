# this_file: tests/test_font_info_dialog.py
"""Exercise the actual lazy six-tool panel against owned Qt objects."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

scripting = importlib.import_module("fontlabapp.core.scripting")


def test_shared_panel_factory_exists_without_importing_native_ui():
    assert callable(getattr(scripting, "font_info_dialog_type", None)), (
        "Six Font Info tools need one lazy shared panel"
    )


@pytest.fixture
def panel(monkeypatch):
    assert callable(getattr(scripting, "font_info_dialog_type", None)), (
        "Shared panel factory must exist"
    )
    events = []
    state = NS(package=NS(id=7, master="Bold"))

    class Signal:
        def __init__(self):
            self.slots = []

        def connect(self, slot):
            self.slots.append(slot)

        def disconnect(self, slot):
            self.slots.remove(slot)

        def emit(self, *args):
            for slot in self.slots:
                slot(*args)

    class Widget:
        def __init__(self, *args):
            self.args = args
            self.clicked = Signal()
            self.finished, self.destroyed = Signal(), Signal()
            self.font = NS(
                pointSizeF=lambda: 10,
                setPointSizeF=lambda value: events.append(("font-size", value)),
                setBold=lambda value: events.append(("font-bold", value)),
            )
            self.palette = NS(
                color=lambda role: NS(name=lambda *args: "#102030"),
                setColor=lambda *args: None,
            )
            self.enabled = None
            self.text = ""
            self.cells = {}

        def setEnabled(self, value):
            self.enabled = value

        def setText(self, value):
            self.text = value

        def setItem(self, row, column, item):
            self.cells[row, column] = item

        def setTextAlignment(self, value):
            self.alignment = value

        def close(self):
            events.append(("close",))

        def __getattr__(self, name):
            if name in ("verticalHeader", "horizontalHeader"):
                return lambda: self
            return lambda *args: events.append((name, *args))

    class Color:
        HexArgb = 1

        def __init__(self, color):
            pass

        def setAlpha(self, value):
            events.append(("alpha", value))

        def name(self, *args):
            return "#102030"

    gui = NS(
        QDialog=Widget,
        QPalette=NS(WindowText=1, Text=2),
        QVBoxLayout=Widget,
        QHBoxLayout=Widget,
        QLabel=Widget,
        QGridLayout=Widget,
        QTableWidget=Widget,
        QColor=Color,
        QPushButton=Widget,
        QAbstractItemView=NS(NoEditTriggers=1, NoSelection=2),
        QHeaderView=NS(Stretch=1, ResizeToContents=2),
        QTableWidgetItem=Widget,
    )
    core = NS(Qt=NS(NoFocus=1, ScrollBarAlwaysOff=2, AlignRight=4, AlignVCenter=8))
    root = importlib.import_module("fontlabapp")
    monkeypatch.setattr(root, "_native", lambda name: NS(QtCore=core, QtGui=gui))
    monkeypatch.setattr(scripting, "current_package", lambda: state.package)
    monkeypatch.setitem(sys.modules, "fontlabapp.fonts.info.ui", None)
    sys.modules.pop("fontlabapp.fonts.info.ui")
    base = scripting.font_info_dialog_type()

    class Panel(base):
        def setup(self):
            events.append(("setup",))

        def refresh(self):
            events.append(("refresh",))

        def apply(self):
            events.append(("apply",))

    return Panel, state, events


def test_shell_preserves_geometry_style_controls_and_callback_order(panel):
    cls, _state, events = panel
    dialog = cls(None, title="Owned", subtitle="Owned purpose", key="owned")
    assert dialog.package_id == 7 and dialog.preview_master == "Bold"
    assert dialog.subtitle.args == ("Owned purpose",)
    assert ("setContentsMargins", 20, 18, 20, 16) in events
    assert ("setMinimumWidth", 700) in events
    assert ("setMinimumHeight", 230) in events
    assert ("font-size", 13.5) in events and ("alpha", 170) in events
    assert events[-2:] == [("setup",), ("refresh",)]
    assert len(dialog._connections) == 2
    dialog.apply_button.clicked.emit(True)
    dialog.close_button.clicked.emit(True)
    assert events[-2:] == [("apply",), ("close",)]
    dialog.rows(["Name", "Value"], [("A", 123)])
    assert dialog.table.cells[0, 0].args == ("A",)
    assert dialog.table.cells[0, 1].alignment == 12


def test_shared_failure_invalidation_identity_and_master_safety(panel):
    cls, state, _events = panel
    dialog = cls(None, title="Owned", subtitle="Owned purpose", key="owned")
    dialog._preview_valid = True
    dialog.safe(lambda: (_ for _ in ()).throw(ValueError("owned failure")))
    assert not dialog._preview_valid and not dialog.apply_button.enabled
    assert dialog.status.text == "owned failure"
    dialog._preview_valid = True
    state.package = None
    with pytest.raises(ValueError, match="original font"):
        dialog.ensure_preview()
    assert not dialog._preview_valid
    state.package = NS(id=7, master="Regular")
    dialog._preview_valid = True
    dialog.MASTER_BOUND = True
    with pytest.raises(ValueError, match="Master changed"):
        dialog.ensure_preview()
    assert not dialog._preview_valid
    dialog.MASTER_BOUND = False
    dialog._preview_valid = True
    dialog.ensure_preview()
    assert dialog.package is state.package


def test_no_font_and_failed_setup_remain_disabled(panel):
    cls, state, _events = panel
    state.package = None
    dialog = cls(None, title="Owned", subtitle="Owned purpose", key="owned")
    assert dialog.package_id is None and not dialog.apply_button.enabled
    assert dialog.subtitle.args == ("Open a font, then reopen this tool.",)

    class Failed(cls):
        def setup(self):
            raise ValueError("owned scan failed")

    broken = Failed(None, title="Owned", subtitle="Owned purpose", key="owned")
    assert not broken._preview_valid and not broken.apply_button.enabled
    assert broken.status.text == "owned scan failed"


def test_adapted_panel_retains_apache_provenance_and_distribution_license():
    import tomllib
    from pathlib import Path

    root = Path(__file__).parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text())
    assert "Apache-2.0" in metadata["project"]["license"], (
        "Adapted Apache panel must be declared with existing licenses"
    )
    assert "LICENSE" in metadata["project"]["license-files"]
    assert "NOTICE" in metadata["project"]["license-files"]
    assert (
        (root / "LICENSE")
        .read_text()
        .startswith("                                 Apache License")
    )
    assert "Font Info" in (root / "NOTICE").read_text()


def test_import_scripting_does_not_load_panel_or_pythonqt():
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            'import fontlabapp.core.scripting; import sys; assert "PythonQt" not in sys.modules; assert "fontlabapp.fonts.info.ui" not in sys.modules',
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
