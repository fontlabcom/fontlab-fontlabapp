# this_file: tests/test_font_info.py
"""Owned tests for complete Font Info migrations and safe edit plans."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from _wp07_routes import behavior_path
from _wp05_scriptmix_shim import app_namespace

ROOT = Path(__file__).parents[1]
TITLES = [
    "Glyph Order Preview and Export",
    "Master Metrics Table",
    "Names and Credits",
    "Unicode Ranges and Codepages",
    "Bump Font Version",
    "Calculate Vertical Metrics",
]


@pytest.mark.parametrize("title", [t for t in TITLES if behavior_path(ROOT / "Scripts/Font Info" / (t + ".py")).is_file()])
def test_requested_tool_exists(title):
    assert behavior_path(ROOT / "Scripts/Font Info" / (title + ".py")).is_file(), (
        "Complete requested Font Info tool missing"
    )


@pytest.fixture
def load(monkeypatch, app_sources):
    state = NS(package=None)
    native = NS()
    helpers = NS(
        current_package=lambda: state.package,
        write_font_info=lambda *a, **k: None,
        connect_guarded=lambda *a: None,
        close_script_dialog=lambda *a, **k: None,
        show_script_dialog=lambda *a: None,
    )
    # Master Metrics Table reads the properties that the App metric writer uses.
    master_metrics = NS(
        FIELDS={
            "ascender": "ascender_value",
            "descender": "descender_value",
            "xHeight": "xHeight_value",
            "capsHeight": "capsHeight_value",
        },
        ALIASES={"capHeight": "capsHeight"},
    )
    monkeypatch.setitem(
        sys.modules,
        "fly",
        NS(
            ap=app_namespace(fontlab=native, FL=NS(), master_metrics=master_metrics),
            qt=NS(QtCore=NS(), QtGui=NS(QDialog=object, QWidget=object)),
        ),
    )
    monkeypatch.setitem(sys.modules, "fly.ap.core.scripting", helpers)
    monkeypatch.setitem(sys.modules, "fly.ap.metrics.master_writer", master_metrics)
    # Exercise the actual shared panel methods against owned import doubles.
    shared_path = app_sources / "fonts/info/ui.py"
    qt = sys.modules["fly"].qt
    monkeypatch.setitem(sys.modules, "fontlabapp", NS(_native=lambda name: qt, fontlab=native, FL=sys.modules["fly"].ap.FL))
    monkeypatch.setitem(sys.modules, "fontlabapp.core.scripting", helpers)
    spec = importlib.util.spec_from_file_location(
        "fontlabapp.fonts.info.ui", behavior_path(shared_path)
    )
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    helpers.font_info_dialog_type = lambda: shared.FontInfoDialog

    def module(title):
        spec = importlib.util.spec_from_file_location(
            title, behavior_path(ROOT / "Scripts/Font Info" / (title + ".py"))
        )
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result

    return module, state, native




def test_export_chooser_when_reopened_then_reuses_owned_dialog_and_checks_font(
    load, tmp_path
):
    module, state, _ = load
    tool = module(TITLES[0])
    dialog, _ = bare_dialog(tool, state)
    dialog._preview_valid = True
    dialog.chooser = None
    dialog.refresh = lambda: None
    selected = []
    opened = []

    class Chooser:
        AcceptSave = 1

        def __init__(self, parent, *args):
            self.fileSelected = object()
            self.parent = parent

        def setAcceptMode(self, mode):
            assert mode == self.AcceptSave

        def setDefaultSuffix(self, suffix):
            assert suffix == "txt"

        def open(self):
            opened.append(self)

    tool.QtGui.QFileDialog = Chooser
    dialog._connect = lambda signal, slot: selected.append(slot)
    exports = []
    dialog.export_order = exports.append
    dialog.apply()
    dialog.apply()
    assert len(selected) == 1 and opened == [dialog.chooser, dialog.chooser]
    assert dialog.chooser.parent is dialog
    selected[0](str(tmp_path / "order.txt"))
    assert exports == [str(tmp_path / "order.txt")]


@pytest.mark.parametrize("title", [t for t in TITLES if behavior_path(ROOT / "Scripts/Font Info" / (t + ".py")).is_file()])
def test_failed_preview_and_stale_font_refuse_apply(load, title):
    module, state, _ = load
    tool = module(title)
    dialog = object.__new__(tool.Dialog)
    dialog.package_id = 1
    dialog.package = NS(id=1, master="Regular")
    dialog.preview_master = "Regular"
    dialog._preview_valid = False
    dialog.apply_button = NS(setEnabled=lambda value: None)
    dialog.status = NS(setText=lambda value: None)
    for package in [None, NS(id=2, master="Regular"), dialog.package]:
        state.package = package
        with pytest.raises(ValueError):
            dialog.apply()
    dialog.safe(lambda: (_ for _ in ()).throw(ValueError("failed preview")))
    assert not dialog._preview_valid




def metric_package():
    """Own separate master dictionaries and a dynamic native-info-like view."""
    values = {
        "Regular": {
            "ascender": 800,
            "descender": -200,
            "xHeight": 500,
            "capHeight": 700,
            "note": "regular note",
        },
        "Bold": {
            "ascender": 900,
            "descender": -250,
            "xHeight": 550,
            "capHeight": 750,
            "note": "bold note",
        },
    }
    class Package(NS):
        """Also expose the native per-master ``*_value`` metric properties."""

        def __getattr__(self, name):
            if not name.endswith("_value"):
                raise AttributeError(name)
            field = name.removesuffix("_value")
            return values[self.master]["capHeight" if field == "capsHeight" else field]

    package = Package(
        id=1, master="Bold", masters=list(values), versionMajor=1, versionMinor=999
    )
    for row in values.values():
        row.update(
            versionMajor=1, versionMinor=999, openTypeNameVersion="Version 1.999"
        )
        row.update(
            {
                field: 0
                for field in [
                    "openTypeOS2TypoAscender",
                    "openTypeOS2TypoDescender",
                    "openTypeOS2TypoLineGap",
                    "openTypeHheaAscender",
                    "openTypeHheaDescender",
                    "openTypeHheaLineGap",
                    "openTypeOS2WinAscent",
                    "openTypeOS2WinDescent",
                ]
            }
        )

    class Info:
        def __getattr__(self, field):
            return values[package.master][field]

    package.info = Info()
    package.setMaster = lambda master, notify=True: setattr(package, "master", master)
    return package, values


def bare_dialog(tool, state):
    """Build only the owned UI state needed to exercise real dialog methods."""
    dialog = object.__new__(tool.Dialog)
    package, values = metric_package()
    state.package = package
    dialog.package = package
    dialog.package_id = package.id
    dialog.preview_master = package.master
    dialog._preview_valid = False
    dialog._plan = []
    dialog.apply_button = NS(setEnabled=lambda flag: setattr(dialog, "enabled", flag))
    dialog.status = NS(setText=lambda text: setattr(dialog, "message", text))
    dialog.rows = lambda headings, rows: setattr(dialog, "display", rows)
    return dialog, values






def test_version_apply_consumes_preview_instead_of_recomputing(load):
    module, state, _ = load
    tool = module(TITLES[4])
    dialog, _ = bare_dialog(tool, state)
    dialog.changes = lambda: [("Regular", "note", "regular note", "new note")]
    dialog.refresh()
    assert dialog._preview_valid and dialog.enabled
    captured = []
    tool.write_changes = lambda package, plan: captured.append(plan) or {"changed": 1}
    dialog.changes = lambda: [("Regular", "note", "external", "unpreviewed")]
    dialog.apply()
    assert captured == [[("Regular", "note", "regular note", "new note")]]


@pytest.mark.parametrize("title", [TITLES[2]])
def test_current_master_switch_refuses_preview_apply(load, title):
    module, state, _ = load
    tool = module(title)
    dialog, _ = bare_dialog(tool, state)
    dialog._preview_valid = True
    state.package.master = "Regular"
    with pytest.raises(ValueError, match="Master changed"):
        dialog.apply()
    assert not dialog._preview_valid


def test_unicode_refresh_rereads_encodings_and_display_failure_invalidates(load):
    module, state, _ = load
    tool = module(TITLES[3])
    dialog, _ = bare_dialog(tool, state)
    tool.glyph_records = lambda package: [("A", [65])]
    dialog.refresh()
    assert dialog.last_result["bits"] == [0] and dialog._preview_valid
    tool.glyph_records = lambda package: [("Smile", [0x1F600])]
    dialog.apply()
    assert 57 in dialog.last_result["bits"] and 0 not in dialog.last_result["bits"]
    dialog.rows = lambda *args: (_ for _ in ()).throw(
        RuntimeError("owned display failed")
    )
    with pytest.raises(RuntimeError):
        dialog.refresh()
    assert not dialog._preview_valid




@pytest.mark.parametrize("title", [t for t in TITLES if behavior_path(ROOT / "Scripts/Font Info" / (t + ".py")).is_file()])
def test_panel_uses_shared_shell_instead_of_repeating_safety_methods(title):
    import ast

    source = behavior_path(ROOT / "Scripts/Font Info" / (title + ".py")).read_text()
    tree = ast.parse(source)
    dialog = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Dialog"
    )
    repeated = {"safe", "_connect", "ensure_font", "ensure_preview", "rows"}
    assert not repeated.intersection(
        node.name for node in dialog.body if isinstance(node, ast.FunctionDef)
    ), "Safety and shell methods belong to shared App panel"
    assert "font_info_dialog_type" in source

from _wp05_scriptmix_shim import app_sources, canonical_app_bindings, real_app  # noqa: E402,F401,I001
