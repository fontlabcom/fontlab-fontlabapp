# this_file: tests/test_shimgen.py
"""The static shim is generated from a capture through the live tree's own code."""

import ast
import json
from pathlib import Path

import pytest

from fontlabapp.core.shimgen import generate_py, generate_pyi, replay, write

SHIM = Path(__file__).resolve().parents[1] / "generated" / "fontlabapp_shim"

CAPTURE = {
    "schema": 1,
    "captured": "2026-10-15",
    "host": {"app": "fontlab9", "app_version": "9.0.0", "locale": "en_US", "qt_version": None},
    "menus": [
        {"title": "&Glyph", "objectName": "menuGlyph", "entries": [
            {"text": "Add Component...", "objectName": "actionAdd_Component", "shortcut": "Ctrl+\\"},
            {"text": "Flatten Glyph", "objectName": "actionFogFlatten_Glyph", "visible": False},
            {"text": "&Flatten Glyph", "objectName": "actionFlatten_Glyph"},
            {"title": "Flag", "objectName": "menuFlag", "entries": [
                {"text": "+10", "objectName": "actionFlag_Plus10"},
                {"text": "-10", "objectName": "actionFlag_Minus10"},
            ]},
        ]},
        {"title": "&Script", "objectName": "menuScripts", "dynamic": True, "dropped": 3, "entries": [
            {"text": "Refresh Scripts", "objectName": "actionRefreshScripts"},
        ]},
        {"title": "&Window", "objectName": "menuWindow", "entries": [
            {"title": "&Panels", "objectName": "menuPanels", "entries": [
                {"text": "&Anchors && Pins", "objectName": "actionPinsPanel", "toolTip": "Anchors & Pins panel"},
                {"text": "Import", "objectName": "actionImportPanel"},
            ]},
        ]},
    ],
    "actions": [{"text": "Secret", "objectName": "actionSecret", "statusTip": "@mainwindow.actionSecret"}],
    "catalogue": {"actions": [{"id": "remove_overlap", "label": "remove overlap"}], "count": 1},
    "widgets": [],
}


def test_pyi_when_fixture_then_valid_python_with_tree_classes():
    text = generate_pyi(CAPTURE)
    tree = ast.parse(text)
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    assert {"MenuBar", "GlyphMenu", "GlyphFlagMenu", "ScriptMenu", "Actions", "Panels", "GlyphActions"} <= classes
    assert "    add_component: Action\n" in text
    assert "Ctrl+\\\\." in text, "backslash shortcut is escaped in the docstring"
    assert "    fog_flatten_glyph: Action\n" in text and "Hidden in the captured session." in text
    # identity rule: -10's objectName sorts first, so it keeps the plain name
    assert "    n10: Action\n" in text and "    flag_plus10: Action\n" in text
    assert text.index("flag_plus10") < text.index("n10"), "menu order kept (+10 first)"
    assert "    anchors_and_pins: Panel\n" in text and "PanelId 13" in text
    assert '"Glyph > Add Component",' in text and '"actionSecret",' in text
    assert "    remove_overlap: GlyphAction\n" in text
    assert "def __getattr__(self, name: str) -> Action | Menu" in text.split("class ScriptMenu")[1].split("class ")[0]


def test_pyi_when_generated_twice_then_identical():
    assert generate_pyi(CAPTURE) == generate_pyi(json.loads(json.dumps(CAPTURE)))


def test_py_facade_when_generated_then_tiny_lazy_module():
    text = generate_py(CAPTURE)
    assert len(text.splitlines()) < 25
    namespace = {}
    exec(compile(text, "fontlabapp.py", "exec"), namespace)  # noqa: S102 - generated facade under test
    assert "host" not in namespace, "the facade imports fontlabapp.core.host only on attribute access"


def test_py_facade_when_fontlabapp_missing_then_probes_are_attribute_errors(tmp_path):
    import subprocess
    import sys

    (tmp_path / "shim_facade.py").write_text(generate_py(CAPTURE), encoding="utf-8")
    code = (
        "import sys; sys.path[:] = [p for p in sys.path if 'fontlab-fontlabapp' not in p];"
        "import shim_facade as m;"
        "assert getattr(m, '__all__', None) is None and not hasattr(m, '__wrapped__');"
        "assert not hasattr(m, 'definitely_not_exported');"
        "assert not hasattr(m, 'menu'), 'missing fontlabapp is an AttributeError'"
    )
    env = {"PYTHONPATH": str(tmp_path), "PATH": "/usr/bin:/bin"}
    subprocess.run([sys.executable, "-S", "-c", code], check=True, cwd=tmp_path, env=env)


def test_py_facade_when_unknown_name_then_attribute_error_without_importing_fontlabapp(tmp_path):
    import subprocess
    import sys

    (tmp_path / "shim_facade.py").write_text(generate_py(CAPTURE), encoding="utf-8")
    decoy = tmp_path / "fontlabapp"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("raise SystemExit('fontlabapp imported')\n", encoding="utf-8")
    code = "import shim_facade as m; assert not hasattr(m, 'definitely_not_exported'); print('ok')"
    done = subprocess.run([sys.executable, "-S", "-c", code], cwd=tmp_path, capture_output=True,
                          text=True, env={"PYTHONPATH": str(tmp_path)}, check=False)
    assert done.stdout.strip() == "ok", done.stdout + done.stderr


def test_replay_when_fixture_then_host_api_without_fontlab():
    host = replay(CAPTURE)
    assert host.menu.glyph.add_component.path == "Glyph > Add Component"
    with pytest.raises(RuntimeError):
        host.glyph_actions.remove_overlap(["A"])


def test_write_when_unknown_schema_then_raises(tmp_path):
    path = tmp_path / "capture.json"
    path.write_text(json.dumps({**CAPTURE, "schema": 2}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        write(path, tmp_path / "out")


delivered = pytest.mark.skipif(not (SHIM / "capture.json").exists(), reason="sdist has no generated/")


@delivered
def test_delivered_shim_when_regenerated_then_unchanged(tmp_path):
    (tmp_path / "capture.json").write_bytes((SHIM / "capture.json").read_bytes())
    written = write(tmp_path / "capture.json", tmp_path / "out")
    assert sorted(p.name for p in written) == ["__init__.py", "__init__.pyi", "provenance.json"]
    for path in written:
        assert path.read_bytes() == (SHIM / path.name).read_bytes(), (
            f"{path.name} is stale: run python -m fontlabapp.core.shimgen {SHIM / 'capture.json'} {SHIM}"
        )


@delivered
def test_delivered_shim_when_names_then_all_resolve_in_replayed_tree():
    capture = json.loads((SHIM / "capture.json").read_text(encoding="utf-8"))
    host = replay(capture)
    tree = ast.parse((SHIM / "__init__.pyi").read_text(encoding="utf-8"))
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

    def check(class_name, node):
        for stmt in classes[class_name].body:
            if isinstance(stmt, ast.AnnAssign):
                name, kind = stmt.target.id, stmt.annotation.id
                child = getattr(node, name)
                if kind != "Action":
                    check(kind, child)

    check("MenuBar", host.menu)
    for stmt in classes["Panels"].body:
        if isinstance(stmt, ast.AnnAssign):
            getattr(host.panels, stmt.target.id)
