# this_file: src/fontlabapp/core/legacy/examples.py
# SPDX-License-Identifier: Apache-2.0
"""Launch exact relocated scripts without certifying their host compatibility."""

import os
import runpy
import sys
from importlib import import_module, util
from pathlib import Path
from typing import Any

_NAMESPACES: dict[Path, dict[str, Any]] = {}


def _port_package(script: Path) -> Path | None:
    """Recognize the two preserved port trees that share the part1 host protocol."""
    for parent in script.parents:
        if (
            parent.name == "ports"
            and parent.parent.name == "part2"
            and parent.parent.parent.name == "rescued"
        ):
            return parent.parent.parent / "part1"
        if (
            parent.name == "ports"
            and parent.parent.name == "pyqt-official-ports"
            and parent.parent.parent.name == "part3"
            and parent.parent.parent.parent.name == "rescued"
        ):
            return parent.parent.parent.parent / "part1"
    return None


def _legacy_host(package: Path) -> Any:
    """Expose preserved helpers under their original import name, lazily.

    The alias stays available for callbacks. Refuse a different loaded copy so
    existing widget classes and ownership are never silently replaced.
    """
    entry = (package / "__init__.py").resolve(strict=True)
    name = "fontlab_python_examples"
    loaded = sys.modules.get(name)
    if loaded is not None:
        if Path(str(getattr(loaded, "__file__", ""))).resolve() != entry:
            raise RuntimeError(f"{name} already loaded from another location")
    else:
        previous = {key for key in sys.modules if key.startswith(name + ".")}
        if previous:
            raise RuntimeError(
                f"{name} submodules already loaded without their package"
            )
        spec = util.spec_from_file_location(name, entry)
        module = util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            for key in list(sys.modules):
                if key == name or key.startswith(name + "."):
                    del sys.modules[key]
            raise
    return import_module(name + ".launcher")._host()


def _show(handle: Any, qt: Any) -> None:
    """Use the preserved launcher's show policy and handle-owned cleanup."""
    try:
        if handle.widget.inherits("QWidget"):
            handle.widget.setAttribute(qt.QtCore.Qt.WA_QuitOnClose, False)
        handle.widget.show()
    except BaseException as error:
        try:
            handle.close()
        except BaseException as cleanup:  # noqa: BLE001 - preserve the initiating failure
            error.add_note(f"Example handle cleanup also failed: {cleanup!r}")
        raise


def _launch_port(script: Path, package: Path) -> dict[str, Any]:
    qt = _legacy_host(package)
    namespace = _NAMESPACES.get(script)
    handle = namespace.get("__rescued_handle__") if namespace else None
    if handle is None or handle.owner.closed:
        # Old main guards forward to the old named catalog, whose layout moved.
        namespace = runpy.run_path(str(script), run_name="fontlab_rescued_port")
        build = namespace.get("build")
        if not callable(build):
            raise NotImplementedError(
                f"Rescued port has no callable build(qt): {script}"
            )
        handle = build(qt)
        namespace["__rescued_handle__"] = handle
    _NAMESPACES.pop(script, None)
    _show(handle, qt)
    return namespace


def _prepare_getgo_namespace(script: Path) -> None:
    """Bind the retained GetGo namespace without importing an unrelated examples package.

    Namespace imports need the original examples root. Retain that module for
    callbacks, but refuse cached modules from another tree before running code.
    This enables imports only; fixtures and native compatibility remain separate.
    """
    directory = script.parent
    if [directory.name, *(p.name for p in directory.parents[:3])] != [
        "getgo",
        "examples",
        "part2",
        "rescued",
    ]:
        return
    root = directory.parent
    for name, module in tuple(sys.modules.items()):
        if name != "examples" and not name.startswith("examples."):
            continue
        locations = getattr(module, "__path__", None)
        paths = (
            list(locations)
            if locations is not None
            else [getattr(module, "__file__", None)]
        )
        if not paths or any(
            not path
            or not Path(path).resolve().is_relative_to(root)
            or (name == "examples" and Path(path).resolve() != root)
            for path in paths
        ):
            raise RuntimeError(f"{name} already loaded from another examples tree")
    if "examples" not in sys.modules:
        spec = util.spec_from_loader("examples", loader=None, is_package=True)
        spec.submodule_search_locations = [str(root)]
        sys.modules["examples"] = util.module_from_spec(spec)


def launch(path: str | Path) -> dict[str, Any]:
    """Run a relocated script beside its resources and retain its globals.

    Ordinary scripts run as __main__. Rescued ports use build(qt) with the
    preserved part1 host/ownership helpers; their live handle is returned under
    __rescued_handle__ and reused until closed. No QApplication is created.
    Retained GetGo entries bind their original examples namespace explicitly;
    an already loaded foreign namespace is refused before executing the entry.
    Only cwd and sys.path are restored; script effects and exceptions propagate.
    """
    script = Path(path).resolve(strict=True)
    if not script.is_file():
        raise ValueError(f"Expected a script file: {script}")
    _prepare_getgo_namespace(script)
    directory, original_path, entries = Path.cwd(), sys.path, list(sys.path)
    try:
        sys.path.insert(0, str(script.parent))
        os.chdir(script.parent)
        package = _port_package(script)
        namespace = (
            _launch_port(script, package)
            if package is not None
            else runpy.run_path(str(script), run_name="__main__")
        )
        _NAMESPACES[script] = namespace
        return namespace
    finally:
        try:
            os.chdir(directory)
        finally:
            original_path[:] = entries
            sys.path = original_path
