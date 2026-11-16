# this_file: tests/test_tombstones.py
"""App keeps no Vanilla session; old imports name the Glyport home."""

import ast
import importlib
import sys
from pathlib import Path

import pytest

import fontlabapp

SESSION_HOME = "fontlab_glyport.ui.session"
VANILLA = Path(fontlabapp.__file__).parent / "core/legacy/vanilla.py"
PEERS = ("fontlab_glyport", "fontlab_fontport")


@pytest.fixture(autouse=True)
def _fresh_import():
    sys.modules.pop("fontlabapp.core.legacy.vanilla", None)
    yield
    sys.modules.pop("fontlabapp.core.legacy.vanilla", None)


def test_vanilla_when_module_imported_then_import_error_names_session_home():
    module = importlib.import_module("fontlabapp.core.legacy.vanilla")
    with pytest.raises(ImportError) as info:
        module.VanillaSession
    assert SESSION_HOME in str(info.value), str(info.value)
    assert "VanillaSession" in str(info.value), str(info.value)


def test_vanilla_when_from_import_form_then_import_error_names_session_home():
    with pytest.raises(ImportError, match=SESSION_HOME.replace(".", r"\.")):
        exec("from fontlabapp.core.legacy.vanilla import VanillaSession", {})  # noqa: S102 - the import form is the subject


def test_vanilla_when_attribute_form_then_import_error_names_session_home():
    with pytest.raises(ImportError, match=SESSION_HOME.replace(".", r"\.")):
        exec("import fontlabapp.core.legacy.vanilla\nfontlabapp.vanilla.VanillaSession", {})  # noqa: S102 - the import form is the subject


def test_vanilla_when_source_parsed_then_it_imports_nothing():
    tree = ast.parse(VANILLA.read_text(encoding="utf-8"))
    assert "from fly.gp.ui.session import VanillaSession" in ast.get_docstring(tree)
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not imports, "tombstone must import nothing: " + ast.dump(imports[0])


def test_vanilla_when_imported_then_no_peer_package_is_loaded():
    before = set(sys.modules)
    module = importlib.import_module("fontlabapp.core.legacy.vanilla")
    with pytest.raises(ImportError):
        module.VanillaSession
    leaked = {n for n in set(sys.modules) - before if n.split(".")[0] in PEERS}
    assert not leaked, leaked
