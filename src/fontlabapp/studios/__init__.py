# this_file: src/fontlabapp/studios/__init__.py
"""Studio apps: one ``AppShell`` window with task tabs; children load lazily.

``TabSpec(title, build)`` names one tab; ``build(shell)`` returns the tab's
``Owned`` panel or widget. ``register``/``tabs`` keep a per-app registry of
specs. Studio modules import only public ``fontlabapp.fontui``,
``fontlabapp.core``, ``fontlabapp.hints`` and native ``fontlab``; a child
studio module loads only when it is first read as an attribute.
"""

import importlib
from collections.abc import Callable
from typing import Any, NamedTuple


class TabSpec(NamedTuple):
    """One studio tab: its title and the builder that makes its panel."""

    title: str
    build: Callable[[Any], Any]


_REGISTRY: dict[str, list[TabSpec]] = {}


def register(app: str, spec: TabSpec) -> TabSpec:
    """Add ``spec`` to the tabs of ``app`` (in order); return it."""
    _REGISTRY.setdefault(app, []).append(spec)
    return spec


def tabs(app: str) -> list[TabSpec]:
    """The registered tab specs of ``app``, in registration order."""
    return list(_REGISTRY.get(app, ()))


def __getattr__(name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    try:
        return importlib.import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as error:
        if error.name != f"{__name__}.{name}":
            raise
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


__all__ = ["TabSpec", "register", "tabs"]
