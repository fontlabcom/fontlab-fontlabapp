# this_file: tests/test_legacy.py
"""Legacy paths share objects and patches; native imports use a Qt test adapter.

Compatibility checks run in subprocesses to keep native/Qt test doubles and
module-cache mutations out of other tests. This establishes import contracts,
not acceptance inside FontLab.
"""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = json.loads((ROOT / "tools/fontlabapp-mapping.json").read_text())

ADAPTER = """
import importlib, sys, types
from PySide6 import QtCore, QtGui, QtWidgets, QtSvg
gui = types.SimpleNamespace(**{n: getattr(QtGui, n) for n in dir(QtGui)})
gui.__dict__.update({n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")})
gui.__dict__.update({n: getattr(QtCore, n) for n in dir(QtCore) if n.startswith("Q")})
gui.QSvgRenderer = QtSvg.QSvgRenderer
sys.modules["PythonQt"] = types.SimpleNamespace(QtCore=QtCore, QtGui=gui, QtSvg=QtSvg,
    private=types.SimpleNamespace(QtCore=QtCore, QtGui=gui, QObject=QtCore.QObject))
sys.modules["Quartz"] = types.ModuleType("Quartz")
for native_name in ("fontlab", "fontgate", "FL"):
    sys.modules[native_name] = types.ModuleType(native_name)
import fontlabapp
fontlabapp.app = types.SimpleNamespace()
"""


def run_contract(code):
    """Run isolated checks and show exact child diagnostics on failure."""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.parametrize("order", ["old-first", "new-first"])
def test_all_aliases_when_imported_in_either_order_then_identical_and_accessible(order):
    output = run_contract(
        ADAPTER
        + f"""
import fontlabapp
from fontlabapp._legacy import ALIASES, FACADES
from pathlib import Path
reviewed = {REVIEWED!r}
count = 0
for old, new in ALIASES.items():
    if {order!r} == "old-first":
        legacy = importlib.import_module(old)
        canonical = importlib.import_module(new)
    else:
        canonical = importlib.import_module(new)
        legacy = importlib.import_module(old)
    assert canonical.__name__ == canonical.__spec__.name == new, (old, new)
    if old in FACADES:
        assert legacy is not canonical and legacy.__path__, old
    else:
        assert legacy is canonical, (old, new)
        assert sys.modules[old] is sys.modules[new], (old, new)
    parent, _, child = old.rpartition(".")
    assert getattr(importlib.import_module(parent), child) is legacy, old
    scope = {{}}
    exec("from " + parent + " import " + child + " as value", scope)
    assert scope["value"] is legacy, old
    sample = next((n for n, value in vars(canonical).items()
                   if not n.startswith("_") and getattr(value, "__module__", None) == new), None)
    if sample:
        exec("from " + old + " import " + sample + " as symbol", scope)
        assert scope["symbol"] is getattr(canonical, sample), old
    if old in reviewed:
        count += 1
print("identity entries:", count)
"""
    )
    expected = sum(
        (ROOT / "src" / (v.replace(".", "/") + ".py")).exists()
        for v in REVIEWED.values()
    )
    assert output.strip() == f"identity entries: {expected}", output


def test_attribute_access_when_no_old_import_precedes_it_then_resolves_aliases():
    run_contract(
        ADAPTER
        + """
import fontlabapp
from fontlabapp._legacy import ALIASES, FACADES
for old, new in ALIASES.items():
    if old.count(".") != 1: continue
    value = getattr(fontlabapp, old.split(".")[1])
    assert value is importlib.import_module(old if old in FACADES else new), old
"""
    )


def test_root_when_reloaded_then_finder_installed_once_and_exports_unchanged():
    run_contract("""
import fontlabapp, importlib, sys
expected = ["app", "Application", "FontLab", "menu", "actions", "panels", "glyph_actions"]
assert fontlabapp.__all__ == expected
for _ in range(3): importlib.reload(fontlabapp)
assert sum(bool(getattr(f, "_fontlabapp_legacy_finder", False)) for f in sys.meta_path) == 1
assert not {"PythonQt", "FL", "fontlab", "Quartz"} & set(sys.modules)
""")


def test_model_modules_when_cold_imported_then_no_qt_or_native_modules_loaded():
    run_contract("""
import importlib, sys
from pathlib import Path
from fontlabapp._legacy import ALIASES
for target in sorted(set(ALIASES.values())):
    if target.endswith(".model"):
        importlib.import_module(target)
        assert not {"PythonQt", "FL", "fontlab", "fontgate", "PySide6", "PyQt5"} & set(sys.modules), target
""")


def test_domain_packages_when_imported_then_no_implementation_or_qt_eagerly_loaded():
    run_contract("""
import importlib, sys
from pathlib import Path
import fontlabapp
root = Path(fontlabapp.__file__).parent
packages = {"fontlabapp"}
for init in sorted(root.rglob("__init__.py")):
    if "fontui" in init.parts: continue
    name = ".".join(init.parent.relative_to(root.parent).parts)
    packages.add(name)
    importlib.import_module(name)
assert not {"PythonQt", "FL", "fontlab", "fontgate", "PySide6", "Quartz"} & set(sys.modules)
assert not any(n.endswith(".model") for n in sys.modules if n.startswith("fontlabapp."))
assert not {n for n in sys.modules if n.startswith("fontlabapp.")} - packages - {"fontlabapp._legacy"}
""")


def test_facades_when_read_and_patched_then_moved_functions_see_both_writes():
    run_contract("""
import importlib, pickle, sys
from unittest.mock import patch
from importlib.resources import files
from fontlabapp._legacy import FACADES as facades
for old in facades:
    package = importlib.import_module(old)
    assert facades[old] not in sys.modules, old
assert not {"PythonQt", "FL", "fontlab"} & set(sys.modules)
for old, new in facades.items():
    package = importlib.import_module(old)
    canonical = importlib.import_module(new)
    assert package is not canonical, old
    scope = {}
    exec("import " + new + " as model", scope)
    assert scope["model"] is canonical, new
    assert canonical.__name__ == canonical.__spec__.name == new, new
    assert canonical.__spec__.origin == canonical.__file__, new
    assert canonical.__spec__.loader is canonical.__loader__, new
    assert not hasattr(canonical, "__path__"), new
    assert canonical.__package__ == new.rpartition(".")[0], new
    assert canonical.__file__.endswith(new.replace(".", "/") + ".py"), new
    assert package.__name__ == package.__spec__.name == old, old
    assert package.__file__.endswith(old.replace(".", "/") + "/__init__.py"), old
    assert package.__path__, old
    assert files(package).joinpath("__init__.py").is_file(), old
    original = getattr(canonical, "_native", None)
    marker = object()
    with patch(old + "._native", marker, create=True):
        assert canonical._native is marker, old
        for value in vars(canonical).values():
            if callable(value) and getattr(value, "__globals__", None) is vars(canonical):
                assert value.__globals__["_native"] is marker, old
                break
    if original is not None: assert canonical._native is original, old
    package._issue205_probe = marker
    assert canonical._issue205_probe is marker, old
    assert vars(package)["_issue205_probe"] is marker, old
    replacement = object()
    canonical._issue205_probe = replacement
    assert package._issue205_probe is replacement, old
    del package._issue205_probe
    assert "_issue205_probe" not in vars(canonical), old
    assert not hasattr(package, "_issue205_probe"), old
    try:
        del package._issue205_probe
    except AttributeError:
        pass
    else:
        raise AssertionError("deleting an absent model name must fail")
    try:
        package.__missing_dunder__
    except AttributeError:
        pass
    else:
        raise AssertionError("dunder probes must not forward")
    package.__issue205_probe__ = marker
    assert "__issue205_probe__" not in vars(canonical), old
    del package.__issue205_probe__
    scope = {}
    name = next(n for n, v in vars(canonical).items() if callable(v) and getattr(v, "__module__", None) == new)
    if name:
        exec("from " + old + " import " + name + " as sample", scope)
        assert scope["sample"] is getattr(canonical, name), old
    symbol = getattr(canonical, name)
    assert pickle.loads(pickle.dumps(symbol)) is symbol, old
    serialized = pickle.dumps(symbol)
    assert importlib.reload(canonical) is canonical, old
    assert pickle.loads(serialized) is getattr(canonical, name), old
    assert getattr(package, name) is getattr(canonical, name), old
    refreshed = getattr(canonical, name)
    assert importlib.reload(package) is package, old
    assert getattr(package, name) is refreshed, old
    child_name = new.removeprefix(old + ".").split(".")[0]
    child = vars(package)[child_name]
    setattr(package, child_name, marker)
    assert vars(package)[child_name] is marker and child_name not in vars(canonical), old
    delattr(package, child_name)
    assert child_name not in vars(package), old
    setattr(package, child_name, child)
    assert sys.modules[old] is package and sys.modules[new] is canonical, old
    via_fly = importlib.import_module(old.replace("fontlabapp.", "fly.ap.", 1))
    assert via_fly is package and getattr(via_fly, name) is refreshed, old
    assert package.__spec__.name == old and canonical.__spec__.name == new, old
""")


@pytest.mark.parametrize(
    "domain", ["masters", "anchors", "components", "guides", "hints", "proof"]
)
def test_facades_when_patched_before_first_read_then_assignment_survives_loading(
    domain,
):
    run_contract(f"""
import importlib, sys
from fontlabapp._legacy import FACADES
old = "fontlabapp." + {domain!r}
new = FACADES[old]
package = importlib.import_module(old)
assert new not in sys.modules
marker = object()
package._native = marker
canonical = importlib.import_module(new)
assert canonical is not package and canonical.__name__ == new
assert package._native is canonical._native is marker
assert vars(package)["_native"] is marker
assert not {{"PythonQt", "fontlab", "FL"}} & set(sys.modules)
del package._native
assert "_native" not in vars(canonical)
""")


def test_facade_when_monkeypatch_and_mock_patch_undo_then_real_model_functions_see_restored_globals():
    run_contract("""
import importlib
from types import SimpleNamespace
from unittest.mock import patch
from pytest import MonkeyPatch
import fontlabapp.masters as package
with MonkeyPatch.context() as monkeypatch:
    monkeypatch.setattr("fontlabapp.masters.associated_master", lambda *a: "patched")
    import fontlabapp.masters.inspect.model as model
    assert model.associated_master("anything", []) == "patched"
assert model.associated_master("Regular@backup", ["Regular"]) == "Regular"
import pickle
assert pickle.loads(b"cfontlabapp.masters\\nassociated_master\\n.") is model.associated_master
from fontlabapp.masters import layers
assert layers.__name__ == "fontlabapp.masters.layers" and layers.__path__
original = model.master_layers
with patch("fly.ap.masters.master_layers", return_value={"Regular": SimpleNamespace(advanceWidth=321)}) as read:
    assert model.widths(None, ["Regular", "Bold"]) == [("Regular", 321.0), ("Bold", None)]
    read.assert_called_once_with(None, ["Regular", "Bold"])
assert package.master_layers is model.master_layers is original
original = model.associated_master
del package.associated_master
assert not hasattr(model, "associated_master") and not hasattr(package, "associated_master")
package.associated_master = original
assert model.associated_master("Regular#bracket", ["Regular"]) == "Regular"
""")


def test_root_when_real_packages_are_requested_then_host_free_from_import_precedes_native_fallback():
    run_contract("""
import importlib, sys
import fontlabapp
def refuse_native(name):
    raise AssertionError("Native fallback reached for " + name)
fontlabapp._native = refuse_native
from fontlabapp import core, qt, glyphs, fonts, fontui, metrics, kerning, contours, features
for name in ("core", "qt", "glyphs", "fonts", "fontui", "metrics", "kerning", "contours", "features"):
    package = getattr(fontlabapp, name)
    assert package is importlib.import_module("fontlabapp." + name)
    assert package.__name__ == "fontlabapp." + name and package.__path__
assert not {"PythonQt", "fontlab", "FL", "fontgate", "PySide6"} & set(sys.modules)
""")


def test_unlisted_child_of_aliased_old_package_when_imported_then_identical_not_reexecuted():
    run_contract(
        ADAPTER
        + """
import importlib, sys
old = importlib.import_module("fontlabapp.application.context")
new = importlib.import_module("fontlabapp.core.application.context")
assert old is new, "same file must not execute twice under the old package name"
assert sys.modules["fontlabapp.application.context"] is new
try:
    importlib.import_module("fontlabapp.application.no_such_child")
except ModuleNotFoundError as error:
    assert error.name == "fontlabapp.application.no_such_child", error.name
else:
    raise AssertionError("unknown children must stay missing")
try:
    importlib.import_module("fontlabapp.zone_data.no_such_child")
except ModuleNotFoundError:
    pass
else:
    raise AssertionError("children of plain old modules must stay missing")
"""
    )


def test_finder_when_installed_again_then_replaces_stale_table():
    run_contract("""
import sys
import fontlabapp._legacy as legacy
stale = legacy._LegacyFinder()
sys.meta_path.insert(0, stale)
legacy.install()
finders = [f for f in sys.meta_path if getattr(f, "_fontlabapp_legacy_finder", False)]
assert len(finders) == 1 and finders[0] is not stale
assert finders[0].find_spec("json") is None
""")


def test_facade_models_when_parsed_then_no_global_shadows_a_child_package():
    import ast

    from fontlabapp._legacy import FACADES

    src = ROOT / "src"
    for old, new in FACADES.items():
        package_dir = src.joinpath(*old.split("."))
        children = {
            p.stem if p.suffix == ".py" else p.name
            for p in package_dir.iterdir()
            if (p.suffix == ".py" and p.stem != "__init__")
            or (p.is_dir() and (p / "__init__.py").is_file())
        }
        model = src.joinpath(*new.split(".")).with_suffix(".py")
        names = set()
        for node in ast.parse(model.read_text()).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                names.update(t.id for t in targets if isinstance(t, ast.Name))
        clash = names & children
        assert not clash, (
            f"{new} globals shadow child packages of {old}: {sorted(clash)}"
        )


def test_facade_in_current_process_when_patched_then_widths_and_namespace_undo_remain_live(
    monkeypatch,
):
    import importlib
    from types import SimpleNamespace
    from unittest.mock import patch

    package = importlib.import_module("fontlabapp.masters")
    model = importlib.import_module("fontlabapp.masters.inspect.model")
    original = model.master_layers
    with monkeypatch.context() as changes:
        changes.setattr(
            package,
            "master_layers",
            lambda *a: {"Regular": SimpleNamespace(advanceWidth=123)},
        )
        assert model.widths(None, ["Regular", "Bold"]) == [
            ("Regular", 123.0),
            ("Bold", None),
        ]
        assert vars(package)["master_layers"] is model.master_layers
    assert package.master_layers is model.master_layers is original
    with patch("fontlabapp.masters.master_layers", lambda *a: {}, create=True):
        assert model.widths(None, ["Regular"]) == [("Regular", None)]
    assert model.master_layers is original
    marker = object()
    package._issue205_probe = marker
    assert package._issue205_probe is model._issue205_probe is marker
    assert vars(package)["_issue205_probe"] is marker
    model._issue205_probe = original
    assert package._issue205_probe is original
    del package._issue205_probe
    assert not hasattr(package, "_issue205_probe") and "_issue205_probe" not in vars(
        model
    )
    with pytest.raises(AttributeError):
        del package._issue205_probe
    with pytest.raises(AttributeError):
        getattr(package, "__issue205_missing__")
    package.__issue205_metadata__ = marker
    assert (
        package.__issue205_metadata__ is marker
        and "__issue205_metadata__" not in vars(model)
    )
    del package.__issue205_metadata__
    child = package.inspect
    try:
        package.inspect = marker
        assert package.inspect is marker and "inspect" not in vars(model)
        del package.inspect
    finally:
        package.inspect = child
    from fontlabapp._legacy import _LegacyFinder

    spec = _LegacyFinder().find_spec("fontlabapp.application.context")
    assert spec.name == "fontlabapp.application.context"
    assert spec.loader.target == "fontlabapp.core.application.context"
    assert _LegacyFinder().find_spec("fontlabapp.zone_data.no_such_child") is None
