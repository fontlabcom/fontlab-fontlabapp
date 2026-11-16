# this_file: tests/_wp05_scriptmix_shim.py
# ruff: noqa: E402, F811 - ported fixtures are re-imported and then shadowed by parameters
"""Local fixture-handle helpers for the ported outline route behaviour tests."""
from pathlib import Path
from types import SimpleNamespace

from fontlabapp._legacy import ALIASES

APP_SOURCES = Path(__file__).resolve().parents[1] / 'src/fontlabapp'


def app_module_name(handle: str) -> str:
    """Resolve a local fixture handle to the canonical App module, never an alias."""
    name = 'fontlabapp.' + handle
    return ALIASES.get(name, name)


def app_namespace(namespace=None, **modules):
    """Build the domain tree for owned App doubles using local fixture handles."""
    namespace = namespace if namespace is not None else SimpleNamespace()
    for handle, module in modules.items():
        parts = app_module_name(handle).split('.')[1:]
        parent = namespace
        for part in parts[:-1]:
            if part not in vars(parent):
                setattr(parent, part, SimpleNamespace())
            parent = vars(parent)[part]
        setattr(parent, parts[-1], module)
    return namespace


def resolve_app_sources(required_helpers=None):
    return APP_SOURCES

import pytest


@pytest.fixture
def real_app(monkeypatch):
    """Load the real installed App helpers over owned FontLab and Qt fakes.

    Scripts reach shared code as ``fly.ap.<module>``. This fixture returns
    ``load(qt=..., fontlab=..., scripting={...}, completion=..., modules=[...])``.
    ``load`` imports fresh ``fontlabapp`` submodules after it registers the
    fakes as ``PythonQt`` and ``fontlab``, so App modules that bind Qt or
    scripting names at import see the fakes. ``scripting`` replaces named
    ``fontlabapp.core.scripting`` functions (font and selection access, panel
    lifecycle). Each loaded module is also registered as ``fly.ap.<module>``,
    the same object, as Fly does. It returns ``{name: module}``.

    After the test, every ``fontlabapp`` submodule and package attribute is
    restored exactly, so other tests see the App as before.
    """
    import importlib
    import sys

    package = importlib.import_module("fontlabapp")
    saved = {k: v for k, v in sys.modules.items() if k.startswith("fontlabapp.")}
    attributes = dict(vars(package))

    def load(*, qt, fontlab, scripting=None, completion=None, modules=()):
        for key in [k for k in sys.modules if k.startswith("fontlabapp.")]:
            del sys.modules[key]
        monkeypatch.setitem(sys.modules, "PythonQt", qt)
        monkeypatch.setitem(sys.modules, "fontlab", fontlab)
        shared = importlib.import_module("fontlabapp.core.scripting")
        for name, value in (scripting or {}).items():
            assert hasattr(shared, name), f"fontlabapp.core.scripting has no {name}"
            setattr(shared, name, value)
        helper = importlib.import_module("fontlabapp.core.completion")
        if completion is not None:
            helper.install = completion
        loaded = {"scripting": shared, "script_completion": helper}
        for name in modules:
            loaded[name] = importlib.import_module(app_module_name(name))
        for name, module in loaded.items():
            monkeypatch.setitem(sys.modules, app_module_name(name).replace("fontlabapp.", "fly.ap.", 1), module)
        fly = sys.modules.get("fly")
        if fly is not None and "ap" in vars(fly):
            app_namespace(fly.ap, **loaded)
        return loaded

    yield load
    for key in [k for k in sys.modules if k.startswith("fontlabapp.")]:
        del sys.modules[key]
    sys.modules.update(saved)
    for key in [k for k in vars(package) if k not in attributes]:
        delattr(package, key)
    for key, value in attributes.items():
        setattr(package, key, value)


def app_source_path(root, handle):
    return Path(root).joinpath(*app_module_name(handle).split('.')[1:]).with_suffix('.py')


def original_source(root, relative):
    raise RuntimeError('historical byte audits are not ported')


def register_app_module(patch, handle, module):
    import importlib.util
    import sys
    parts = app_module_name(handle).split('.')
    parent = sys.modules['fontlabapp']
    for index in range(1, len(parts)):
        fullname = '.'.join(parts[:index + 1])
        if index == len(parts) - 1:
            child = module
        else:
            child = sys.modules.get(fullname)
            if child is None:
                spec = importlib.util.spec_from_loader(fullname, loader=None, is_package=True)
                child = importlib.util.module_from_spec(spec)
                child.__path__ = [str(APP_SOURCES.joinpath(*parts[1:index + 1]))]
        patch.setitem(sys.modules, fullname, child)
        patch.setitem(vars(parent), parts[index], child)
        parent = child


@pytest.fixture(scope='session')
def app_sources():
    import importlib
    import importlib.util
    import sys
    importlib.import_module('fontlabapp')
    name = 'fontlabapp.core.completion'
    spec = importlib.util.spec_from_file_location(name, APP_SOURCES / 'core/completion.py')
    module = importlib.util.module_from_spec(spec)
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        yield APP_SOURCES


# ---- WP07 additions: helpers the ported identity-tool behaviour tests share ----
from _wp07_routes import behavior_path  # noqa: E402,F401


def resolve_app_sources_for_names(paths):
    return paths


def app_names_used(paths):
    """Return {"fly.ap.<module>": {names}} for every App name the sources use."""
    import ast

    found = {}
    for path in paths:
        tree = ast.parse(Path(path).read_text())
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(("fly.ap.", "fontlabapp.")):
                module = node.module.replace("fontlabapp.", "fly.ap.", 1)
                found.setdefault(module, set()).update(a.name for a in node.names)
            elif isinstance(node, ast.Import):
                for item in node.names:
                    if item.name.startswith(("fly.ap.", "fontlabapp.")) and item.asname:
                        module = item.name.replace("fontlabapp.", "fly.ap.", 1)
                        aliases[item.asname] = module
                        found.setdefault(module, set())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id in aliases):
                found[aliases[node.value.id]].add(node.attr)
    return found


def check_real_app_names(used):
    """Import the real Fly and App with no fakes; every used name must exist."""
    import importlib
    import importlib.util
    import sys

    roots = {"fly", "fontlabapp"}
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] in roots}
    for key in saved:
        del sys.modules[key]
    try:
        assert importlib.util.find_spec("fly") is not None, "Put Fly on PYTHONPATH"
        fly = importlib.import_module("fly")
        assert fly.ALIASES["ap"] == "fontlabapp"
        for module_name, wanted in used.items():
            module = importlib.import_module(module_name)
            canonical = "fontlabapp." + module_name.removeprefix("fly.ap.")
            assert module is sys.modules[canonical], module_name
            assert Path(module.__file__).resolve().is_relative_to(APP_SOURCES.resolve()), module.__file__
            for attribute in wanted:
                assert hasattr(module, attribute), f"{module_name}.{attribute}"
    finally:
        for key in [k for k in sys.modules if k.split(".")[0] in roots]:
            del sys.modules[key]
        sys.modules.update(saved)


@pytest.fixture(autouse=True)
def canonical_app_bindings():
    """Repair package child bindings left by isolated Fly/module test doubles."""
    import sys

    for name, module in sorted(sys.modules.copy().items()):
        if name.startswith("fontlabapp."):
            parent, _, child = name.rpartition(".")
            owner = sys.modules.get(parent)
            if owner is not None:
                vars(owner)[child] = module
