# this_file: tests/test_api_facades.py
"""Check the additive facade imports, source identity and cold-import contract."""

import ast
import importlib
import importlib.util
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest


EXPORTS = {
    "objects": {
        "FontLab": "core.controls",
        "current_package": "core.scripting",
        "font_id": "core.scripting",
        "select_glyphs": "core.scripting",
    },
    "ui": {
        "OwnedWidget": "qt.widgets",
        "compact": "qt.compact",
        "compact_dialog": "qt.compact",
        "compact_layout": "qt.compact",
        "controls_box": "qt.compact",
        "frameless": "qt.compact",
        "split_view": "qt.compact",
        "create_dialog": "qt.widgets",
        "create_panel": "qt.widgets",
        "create_widget": "qt.widgets",
    },
    "ui.dialogs": {
        "create_dialog": "qt.widgets",
        "create_message_box": "qt.dialogs",
        "run_owned_dialog": "qt.dialogs",
        "run_standard_message_box": "qt.dialogs",
        "run_file_dialog": "qt.dialogs",
        "run_text_dialog": "qt.dialogs",
        "name_filters": "qt.dialogs",
    },
    "ui.panels": {
        "Panel": "qt.views",
        "Panels": "core.host",
        "create_panel": "qt.widgets",
    },
    "ui.widgets": {
        "OwnedWidget": "qt.widgets",
        "create_widget": "qt.widgets",
        "fit_contents": "qt.layouts.content",
        "ColorDialog": "qt.colors",
    },
    "ui.windows": {"GlyphWindow": "qt.views", "Preview": "qt.views"},
    "ui.canvas": {
        "Drawing": "qt.painting.drawing",
        "EditorPainters": "qt.painting.editor",
        "PaintContext": "qt.painting.editor",
        "AFTER_NATIVE_LAYER": "qt.painting.editor",
        "LAYER_FILTERS": "qt.painting.editor",
    },
    "menus": {
        "Menu": "core.host",
        "MenuBar": "core.host",
        "OwnedMenus": "qt.menus",
        "OWNED_MENU_TITLE": "qt.menus",
        "live": "core.host",
    },
    "ui.actions": {
        "Action": "core.host",
        "Actions": "core.host",
        "GlyphAction": "core.host",
        "GlyphActions": "core.host",
        "ActionDisabledError": "core.host",
        "live": "core.host",
    },
    "shortcuts": {"key_press_handler": "qt.events.key"},
    "signals": {
        "track_connection": "core.signals.connections",
        "disconnect_connections": "core.signals.connections",
        "quiet_callbacks": "core.signals.callbacks",
        "Scope": "core.signals.scope",
    },
    "qtsafe_api": {
        "qt_list": "qt.safe",
        "main_window": "qt.safe",
        "MainWindowNotFound": "qt.safe",
        "read_text": "qt.literal_text",
        "set_mime_text": "qt.literal_text",
        "text_fragment": "qt.literal_text",
        "line_edit_type": "qt.literal_text",
    },
}

ROOT = Path(__file__).resolve().parents[1]


def test_api_map_when_compared_to_source_then_every_module_appears_once():
    source = ROOT / "src/fontlabapp"
    actual = set()
    for path in source.rglob("*.py"):
        parts = list(path.relative_to(source).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        actual.add(".".join(("fontlabapp", *parts)))
    rows = [
        line.split("`", 2)[1]
        for line in (ROOT / "src_docs/md/guides/api-map.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| `fontlabapp")
    ]
    counts = Counter(rows)
    listed = set(counts)
    missing, extra = sorted(actual - listed), sorted(listed - actual)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    assert not (missing or extra or duplicates), (
        f"API map mismatch: missing={missing}, extra={extra}, duplicates={duplicates}"
    )


def test_api_map_when_read_then_public_names_and_domain_counts_match_source():
    text = (ROOT / "src_docs/md/guides/api-map.md").read_text(encoding="utf-8")
    domains = Counter()
    for line in text.splitlines():
        if not line.startswith("| `fontlabapp"):
            continue
        module, domain, public, _purpose = line.split(" | ", 3)
        name = module.split("`")[1]
        path = ROOT / "src" / Path(*name.split("."))
        path = (
            path.with_suffix(".py")
            if path.with_suffix(".py").exists()
            else path / "__init__.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        explicit = None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                names.update(
                    target.id for target in targets if isinstance(target, ast.Name)
                )
                if any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in targets
                ):
                    explicit = ast.literal_eval(node.value)
        expected = (
            set(explicit)
            if explicit is not None
            else {name for name in names if not name.startswith("_")}
        )
        listed = set(public.split("`")[1::2])
        assert listed == expected, f"{name}: stale public names {listed ^ expected}"
        domains[domain] += 1
    for domain, count in domains.items():
        assert f"| {domain} | {count} |" in text, f"Stale count for {domain}"
    assert f"| **Total** | **{sum(domains.values())}** |" in text, (
        "Stale total module count"
    )


def test_top_level_when_native_is_absent_then_submodule_import_still_works():
    code = """
import sys
import fontlabapp
from fontlabapp import image_viewer
assert image_viewer.__name__ == 'fontlabapp.qt.images.viewer.model'
assert not {'PythonQt', 'fontlab', 'FL'} & set(sys.modules)
try:
    fontlabapp.no_such_name
except AttributeError:
    pass
else:
    raise AssertionError('unknown attribute did not raise AttributeError')
try:
    from fontlabapp import no_such_name
except ImportError:
    pass
else:
    raise AssertionError('unknown from-import did not raise ImportError')
for name in ('FL', 'fontgate', 'fontlab', 'PythonQt', 'Qt', 'QtCore', 'QtGui'):
    try:
        fontlabapp.__getattr__(name)
    except RuntimeError as error:
        assert 'requires the native API inside FontLab' in str(error)
    else:
        raise AssertionError(name + ' did not retain its native error')
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("facade,exports", EXPORTS.items())
def test_facade_when_imported_then_sources_stay_unloaded(facade, exports):
    module_name = f"fontlabapp.{facade}"
    code = (
        "import importlib, sys\n"
        f"module = importlib.import_module({module_name!r})\n"
        f"sources = {sorted(set(exports.values()))!r}\n"
        "assert not (set(sys.modules) & {'PythonQt', 'fontlab', 'FL', 'fontgate'})\n"
        "assert all('fontlabapp.' + name not in sys.modules for name in sources)\n"
        "assert module.__all__\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("facade,exports", EXPORTS.items())
def test_facade_when_resolved_then_exports_are_original_objects(facade, exports):
    module = importlib.import_module(f"fontlabapp.{facade}")
    assert set(module.__all__) == set(exports)
    assert len(module.__doc__.splitlines()) >= 7
    for name, source in exports.items():
        spec = importlib.util.find_spec(f"fontlabapp.{source}")
        assert spec is not None and spec.origin is not None
        tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
        definitions = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
        }
        assignments = {
            target.id
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Name)
        }
        assert name in definitions | assignments, (
            f"{source}.{name} lacks a source definition"
        )
        original = importlib.import_module(f"fontlabapp.{source}")
        value = getattr(module, name)
        assert value is getattr(original, name)
        assert getattr(module, name) is value
    with pytest.raises(AttributeError):
        getattr(module, "_missing")
    with pytest.raises(AttributeError):
        getattr(module, "unknown_public_name")


@pytest.mark.parametrize("facade", EXPORTS)
def test_facade_when_documented_then_imports_are_exported_and_dir_is_public(facade):
    module = importlib.import_module(f"fontlabapp.{facade}")
    imports = [
        ast.parse(line.strip()).body[0]
        for line in module.__doc__.splitlines()
        if line.strip().startswith("from fly.ap.")
    ]
    assert imports, f"{module.__name__} has no facade import example"
    for statement in imports:
        assert isinstance(statement, ast.ImportFrom)
        assert statement.module.replace("fly.ap.", "fontlabapp.", 1) == module.__name__
        names = {alias.name for alias in statement.names}
        assert names <= set(module.__all__), (
            f"{module.__name__}: undocumented exports {names}"
        )
    assert module.__dir__() == sorted(module.__all__)
    assert dir(module) == sorted(module.__all__)


def test_legacy_actions_when_ui_facade_imported_then_host_lookup_is_unchanged(
    monkeypatch,
):
    import fontlabapp

    importlib.import_module("fontlabapp.ui.actions")
    assert "actions" not in vars(fontlabapp)
    assert importlib.util.find_spec("fontlabapp.actions") is None
    assert not (Path(__file__).resolve().parents[1] / "src/fontlabapp/actions").exists()

    expected = object()
    observed = []
    real_import = fontlabapp.import_module

    def fake_import(name):
        observed.append(name)
        if name == "fontlabapp.core.host":
            return SimpleNamespace(actions=expected)
        return real_import(name)

    monkeypatch.setattr(fontlabapp, "import_module", fake_import)
    assert fontlabapp.__getattr__("actions") is expected
    assert fontlabapp.actions is expected
    assert observed == ["fontlabapp.core.host", "fontlabapp.core.host"]


def test_facade_paths_when_compared_to_top_level_then_no_exact_or_case_collision():
    import fontlabapp

    tree = ast.parse(Path(fontlabapp.__file__).read_text(encoding="utf-8"))
    lazy = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
    )
    lazy_names = {
        node.value
        for node in ast.walk(lazy)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    required = {
        "menu",
        "actions",
        "panels",
        "glyph_actions",
        "app",
        "FL",
        "fontgate",
        "fontlab",
        "PythonQt",
        "Qt",
        "QtCore",
        "QtGui",
    }
    assert required <= lazy_names
    reserved = set(fontlabapp.__all__) | lazy_names
    root_facades = {name.split(".", 1)[0] for name in EXPORTS}
    assert not root_facades & reserved
    assert not {name.casefold() for name in root_facades} & {
        name.casefold() for name in reserved
    }
    root = Path(__file__).resolve().parents[1] / "src/fontlabapp"
    # Issue 205 added the real ``fontlabapp.qt`` package; the native ``Qt``
    # lookup must still never resolve to it (case-exact module resolution).
    assert importlib.util.find_spec("fontlabapp.Qt") is None
    assert (root / "qtsafe_api/__init__.py").is_file()


def test_qt_facade_when_imported_then_legacy_qt_lookup_remains_native():
    code = """
import importlib
import importlib.util
from types import SimpleNamespace
import fontlabapp

importlib.import_module('fontlabapp.qtsafe_api')
assert 'Qt' not in vars(fontlabapp)
assert importlib.util.find_spec('fontlabapp.Qt') is None
expected = object()
fontlabapp._native = lambda name: SimpleNamespace(Qt=expected)
assert fontlabapp.__getattr__('Qt') is expected
assert fontlabapp.Qt is expected
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
