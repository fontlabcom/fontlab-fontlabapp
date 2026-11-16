# this_file: src/fontlabapp/plugmix/__init__.py
"""Deprecated one-release alias for :mod:`fontlabapp.plugins`."""

import importlib
import importlib.abc
import importlib.util
import sys
import warnings

warnings.warn(
    "fontlabapp.plugmix is deprecated; use fontlabapp.plugins (removed next release)",
    DeprecationWarning,
    stacklevel=2,
)
_core = importlib.import_module("fontlabapp.plugins")


class _Alias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Keep legacy imports on the same registry, class and lifecycle objects."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(__name__ + "."):
            canonical = fullname.replace(__name__, "fontlabapp.plugins", 1)
            module = self._resolve(canonical)
            spec = module.__spec__ if module is not None else None
            if spec is not None:
                return importlib.util.spec_from_loader(
                    fullname, self, is_package=spec.submodule_search_locations is not None
                )
        return None

    def create_module(self, spec):
        module = self._resolve(spec.name.replace(__name__, "fontlabapp.plugins", 1))
        self._specs[spec.name] = module.__spec__
        return module

    def exec_module(self, module):
        name = module.__spec__.name
        module.__spec__ = self._specs.pop(name)

    @staticmethod
    def _resolve(canonical):
        spec = importlib.util.find_spec(canonical)
        if spec is not None:
            return importlib.import_module(canonical)
        parts = canonical.split(".")
        kinds = {"plugins": "reporter", "filters": "filter", "palettes": "palette",
                 "tools": "tool", "general_plugins": "general"}
        if len(parts) == 4 and parts[2] in kinds:
            registry = importlib.import_module("fontlabapp.plugins.registry")
            for cls in registry.current().available(kinds[parts[2]]).values():
                if cls.__module__.rsplit(".", 1)[-1] == parts[3]:
                    return sys.modules[cls.__module__]
        return None

    _specs = {}


if not any(type(finder).__module__ == __name__ for finder in sys.meta_path):
    sys.meta_path.insert(0, _Alias())


def __getattr__(name):
    return getattr(_core, name)
