# this_file: src/fontlabapp/plugins/bundles.py
"""Validate and import ordinary Extensions bundles without a package install."""

import hashlib
import json
import re
import sys
from importlib import import_module, metadata
from pathlib import Path
from types import ModuleType
from typing import Any

KINDS = {"reporter": "reporters", "filter": "filters", "tool": "tools",
         "palette": "palettes", "general": "general"}
_FIELDS = {"id", "name", "kind", "version", "entry", "min_app_version"}
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def app_version() -> str | None:
    """Read the installed App version; None in an uninstalled source checkout."""
    try:
        return metadata.version("fontlab-fontlabapp")
    except metadata.PackageNotFoundError:
        return None


def manifest(bundle: Path, version: str | None = None) -> dict[str, str]:
    """Parse required fields and reject incompatible bundles before imports."""
    data = json.loads((bundle / "plugin.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(
        not isinstance(data.get(key), str) or not data[key].strip() for key in _FIELDS
    ):
        raise ValueError("plugin.json requires nonempty string fields: " + ", ".join(sorted(_FIELDS)))
    kind = data["kind"]
    if kind not in KINDS or bundle.parent.name != KINDS[kind] or not bundle.name.endswith(".fontlab" + kind.title()):
        raise ValueError("plugin kind does not match the bundle folder and suffix")
    if not _IDENTIFIER.fullmatch(data["id"]):
        raise ValueError("plugin id must be a stable identifier")
    for key in ("version", "min_app_version"):
        if not _VERSION.fullmatch(data[key]):
            raise ValueError(f"{key} must be a three-part release version")
    entry = data["entry"].split(":")
    if len(entry) != 2 or any(not part.isidentifier() for part in entry[0].split(".")) or not entry[1].isidentifier():
        raise ValueError("entry must be module:Class using Python identifiers")
    running = version or app_version()
    current = re.match(r"^(\d+)\.(\d+)\.(\d+)", running) if running else None
    if running and (current is None or tuple(map(int, current.groups())) < tuple(map(int, data["min_app_version"].split(".")))):
        raise ValueError(
            f"plugin {data['name']} requires App {data['min_app_version']} or newer (installed {running}); "
            "re-run fontlab-fontlabapp/install.vfpy"
        )
    module_path = bundle.joinpath(*entry[0].split("."))
    paths = [module_path.with_suffix(".py"), module_path / "__init__.py"]
    if not any(path.is_file() and path.resolve().is_relative_to(bundle.resolve()) for path in paths):
        raise ValueError("entry module must exist inside its bundle")
    return data


def load_bundle(bundle: str | Path, version: str | None = None) -> type:
    """Load a validated entry in a stable private namespace for relative imports.

    Modules are retained for a session, so rescanning cannot repeat import side
    effects. Restart the plugin runtime process to load edited Python source.
    """
    bundle = Path(bundle).resolve()
    data = manifest(bundle, version)
    namespace = "_fontlab_extension_" + hashlib.sha256(str(bundle).encode()).hexdigest()
    created = namespace not in sys.modules
    if created:
        package = ModuleType(namespace)
        package.__path__ = [str(bundle)]
        package.__package__ = namespace
        sys.modules[namespace] = package
    try:
        module_name, class_name = data["entry"].split(":")
        cls = getattr(import_module(f"{namespace}.{module_name}"), class_name)
        from .registry import _accept

        _accept({}, cls)
        if (cls.name, cls.title, cls.kind) != (data["id"], data["name"], data["kind"]):
            raise ValueError("manifest id/name/kind must match the entry class")
        return cls
    except BaseException:
        if created:
            for name in tuple(sys.modules):
                if name == namespace or name.startswith(namespace + "."):
                    del sys.modules[name]
        raise


def discover(root: str | Path, report: Any, version: str | None = None) -> dict[str, type]:
    """Return sorted unique plugin classes; isolate each invalid bundle."""
    from .registry import _accept

    found: dict[str, type] = {}
    root = Path(root)
    for kind, folder in sorted(KINDS.items()):
        try:
            paths = sorted((root / folder).glob("*.fontlab*"))
        except OSError as error:
            report(error, root / folder)
            continue
        for bundle in paths:
            try:
                _accept(found, load_bundle(bundle, version))
            except (Exception, SystemExit) as error:
                report(error, bundle)
    return found
