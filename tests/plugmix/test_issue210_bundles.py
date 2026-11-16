# this_file: tests/plugmix/test_issue210_bundles.py
"""Boundary, compatibility and idempotency tests for Extensions discovery."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from fontlabapp.plugins import boot, bundles, registry


def bundle(root, folder_name="Demo", folder_kind="reporter", source=None, **changes):
    name, kind = folder_name, folder_kind
    path = root / bundles.KINDS[kind] / (name + ".fontlab" + kind.title())
    path.mkdir(parents=True, exist_ok=True)
    data = dict(id=name.lower(), name=name, kind=kind, version="1.0.0", entry="plugin:Example", min_app_version="0.1.0")
    data.update(changes)
    (path / "plugin.json").write_text(json.dumps(data))
    (path / "plugin.py").write_text(source or f'from fontlabapp.plugins import {kind.title()}\nclass Example({kind.title()}):\n name="{name.lower()}"\n title="{name}"\n')
    return path


def test_discovery_when_rescanned_then_classes_and_import_effects_are_stable(tmp_path):
    bundle(tmp_path, "Zebra")
    first = bundle(tmp_path, "Alpha", source='from .helper import Reporter\nclass Example(Reporter):\n name="alpha"\n title="Alpha"\n')
    (first / "helper.py").write_text("from fontlabapp.plugins import Reporter\n")
    errors = []
    found = bundles.discover(tmp_path, lambda e, s: errors.append(e), "1.0.0")
    assert list(found) == ["alpha", "zebra"]
    again = bundles.discover(tmp_path, lambda e, s: errors.append(e), "1.0.0")
    assert found == again and not errors
    assert bundles.load_bundle(first, "1.0.0") is found["alpha"]


@pytest.mark.parametrize("kind", bundles.KINDS)
def test_discovery_when_each_kind_then_loads_contract(tmp_path, kind):
    path = bundle(tmp_path, kind.title(), kind)
    assert bundles.load_bundle(path, "1.0.0").kind == kind


@pytest.mark.parametrize("change", [
    {"id": ""}, {"id": "../bad"}, {"name": 2}, {"kind": "unknown"},
    {"kind": "tool"}, {"version": "1"}, {"min_app_version": "1.2"},
    {"min_app_version": "9.0.0"}, {"entry": "../plugin:Example"},
    {"entry": "plugin.Example"}, {"entry": "plugin:bad-name"},
    {"entry": "missing:Example"}, {"id": "wrong"}, {"name": "Wrong"},
])
def test_discovery_when_invalid_bundle_then_reports_and_continues(tmp_path, change):
    bundle(tmp_path, "Bad", **change)
    bundle(tmp_path, "Good")
    errors = []
    found = bundles.discover(tmp_path, lambda e, s: errors.append((e, s)), "1.0.0")
    assert list(found) == ["good"]
    assert len(errors) == 1 and "Bad.fontlabReporter" in str(errors[0][1])


def test_discovery_when_import_or_json_fails_then_isolated(tmp_path):
    for index, source in enumerate(('raise RuntimeError("import failed")', 'raise SystemExit("exit")', 'Example = object')):
        bundle(tmp_path, f"Bad{index}", source=source)
    broken = bundle(tmp_path, "Broken")
    (broken / "plugin.json").write_text("[]")
    duplicate = bundle(tmp_path, "Zulu", id="good", name="Good")
    (duplicate / "plugin.py").write_text('from fontlabapp.plugins import Reporter\nclass Example(Reporter):\n name="good"\n title="Good"\n')
    bundle(tmp_path, "Good")
    errors = []
    assert list(bundles.discover(tmp_path, lambda e, s: errors.append(e), "1.0.0")) == ["good"]
    assert len(errors) == 5
    assert not any(str(broken) in str(getattr(m, "__path__", "")) for m in sys.modules.values())


def test_manifest_when_entry_is_symlink_to_source_checkout_then_loads(tmp_path):
    """Plugmix installs per-file symlinks into Extensions (2026-11-16)."""
    path = bundle(tmp_path / "ext")
    source = tmp_path / "checkout" / path.name
    source.mkdir(parents=True)
    for name in ("plugin.py", "plugin.json"):
        (source / name).write_bytes((path / name).read_bytes())
        (path / name).unlink()
        (path / name).symlink_to(source / name)
    assert bundles.load_bundle(path, "1.0.0").name == "demo"
    assert set(bundles.discover(tmp_path / "ext", lambda *a: pytest.fail(str(a)), "1.0.0")) == {"demo"}


def test_manifest_when_entry_escapes_through_symlinked_folder_then_rejected(tmp_path):
    path = bundle(tmp_path, entry="pkg:Example")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "__init__.py").write_text("Example = object")
    (path / "pkg").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="inside its bundle"):
        bundles.load_bundle(path, "1.0.0")


def test_inside_when_dotdot_component_then_rejected(tmp_path):
    path = bundle(tmp_path)
    (tmp_path / "outside.py").write_text("Example = object")
    assert bundles._inside(path / "plugin.py", path)
    assert not bundles._inside(path / ".." / "outside.py", path)
    assert not bundles._inside(path / "sub" / ".." / "plugin.py", path)


def test_manifest_when_plugin_json_folder_escapes_then_rejected(tmp_path):
    path = bundle(tmp_path)
    assert not bundles._inside(tmp_path / "plugin.json", path)


def test_manifest_when_app_too_old_then_message_names_bundle_versions_and_installer(tmp_path):
    path = bundle(tmp_path, min_app_version="1.2.10")
    with pytest.raises(ValueError) as caught:
        bundles.manifest(path, "1.2.9+74.g621033e")
    text = str(caught.value)
    assert "Demo" in text and "1.2.10" in text and "1.2.9+74.g621033e" in text, text
    assert "re-run fontlab-fontlabapp/install.vfpy" in text, text


def test_versions_and_scan_error_are_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(bundles.metadata, "version", lambda name: "1.2.3.dev2")
    assert bundles.app_version() == "1.2.3.dev2"
    path = bundle(tmp_path)
    assert bundles.manifest(path)["id"] == "demo"
    monkeypatch.setattr(bundles.metadata, "version", lambda name: (_ for _ in ()).throw(bundles.metadata.PackageNotFoundError(name)))
    assert bundles.app_version() is None
    newer = bundle(tmp_path / "src", min_app_version="9.0.0")
    assert bundles.manifest(newer)["id"] == "demo", "source checkouts must not reject bundles by version"
    with pytest.raises(ValueError, match="requires App"):
        bundles.manifest(path, "unknown")
    monkeypatch.setattr(Path, "glob", lambda *args: (_ for _ in ()).throw(OSError("denied")))
    errors = []
    assert bundles.discover(tmp_path, lambda e, s: errors.append(e)) == {}
    assert len(errors) == 5


def test_registry_when_rescanned_then_adds_once_and_preserves_active_identity(tmp_path):
    root = tmp_path / "Extensions"
    bundle(root)
    state = registry.Registry(tmp_path, extensions_dir=root)
    original = state.available()["demo"]
    bundle(root, "Later")
    assert list(state.rescan()) == ["demo", "later"]
    assert state.rescan()["demo"] is original
    fresh = registry.Registry(tmp_path, extensions_dir=root)
    assert fresh.rescan() == state.available()
    calls = []
    state.listeners.extend([lambda: (_ for _ in ()).throw(RuntimeError("bad")), lambda: calls.append(True)])
    state.enable("demo")
    state.disable("demo")
    assert calls == [True, True]


def test_registry_when_entry_metadata_fails_then_bundles_survive(tmp_path, monkeypatch):
    bundle(tmp_path)
    monkeypatch.setattr(registry.metadata, "entry_points", lambda: (_ for _ in ()).throw(ValueError("metadata")))
    errors = []
    assert list(registry.discover(lambda e, s: errors.append(e), tmp_path)) == ["demo"]
    assert len(errors) == 1


def test_legacy_imports_when_loaded_then_warn_and_share_module_identity():
    with pytest.warns(DeprecationWarning):
        legacy = importlib.import_module("fontlabapp.plugmix")
        importlib.reload(legacy)
    canonical = importlib.import_module("fontlabapp.plugins.registry")
    assert importlib.import_module("fontlabapp.plugmix.registry") is canonical
    assert importlib.import_module("fontlabapp.plugmix.filters.host") is importlib.import_module("fontlabapp.plugins.filters.host")
    assert legacy.Reporter is importlib.import_module("fontlabapp.plugins").Reporter
    assert canonical.__spec__.name == "fontlabapp.plugins.registry"
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("fontlabapp.plugmix.not_present")
    with pytest.raises(AttributeError):
        legacy.not_present


def test_legacy_concrete_import_when_reference_bundle_installed_then_resolves(tmp_path, monkeypatch):
    legacy = importlib.import_module("fontlabapp.plugmix")
    state = registry.Registry(tmp_path)
    monkeypatch.setattr(registry, "_current", state)
    canonical = "fontlabapp.plugins.plugins.node_indexes"
    old = sys.modules.pop(canonical)
    try:
        module = importlib.import_module("fontlabapp.plugmix.plugins.node_indexes")
        assert module.NodeIndexes is state.available()["node_indexes"]
        assert legacy._Alias._resolve("fontlabapp.plugins.plugins.absent") is None
    finally:
        sys.modules[canonical] = old


def test_rescan_when_saved_reporters_arrive_then_restores_once_despite_bad_plugin(tmp_path):
    from test_plugmix_registry_boot_menu import Painters

    root = tmp_path / "Extensions"
    (tmp_path / "fontlab-plugmix.json").write_text(json.dumps({"enabled": ["bad", "good"], "params": {}}))
    errors = []
    state = registry.Registry(tmp_path, lambda error, source: errors.append(str(error)), extensions_dir=root)
    painters = Painters()
    state.attach(painters, object(), lambda *args: None)
    assert state.enabled() == ("bad", "good") and not state._tokens
    bundle(root, "Bad", source='from fontlabapp.plugins import Reporter\nclass Example(Reporter):\n name="bad"\n title="Bad"\n def __init__(self):\n  raise RuntimeError("broken constructor")\n')
    bundle(root, "Good")
    state.rescan()
    assert set(state._tokens) == {"good"} and len(painters.calls) == 1
    assert errors == ["broken constructor"]
    state.rescan()
    assert set(state._tokens) == {"good"} and len(painters.calls) == 1
    assert errors == ["broken constructor", "broken constructor"]
    state.detach()
