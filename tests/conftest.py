# this_file: tests/conftest.py
"""Root test conftest: pytest puts ``tests/`` on sys.path, so nested test
directories (``tests/plugmix``) can import shared helpers such as
``paint_safety``."""

import sys
from types import ModuleType

import pytest


@pytest.fixture(autouse=True)
def isolate_demo_fly_aliases(request):
    """Keep real Fly imports from retaining a previous demo's canonical stand-ins."""
    source = request.path.read_text(encoding="utf-8")
    if "Scripts" not in source and "examples/" not in source and "_demo_support" not in source:
        yield
        return
    import fly

    aliases = {name: module for name, module in sys.modules.copy().items() if name.startswith("fly.")}
    roots = {name: fly.__dict__[name] for name in fly.ALIASES if name in fly.__dict__}
    parents = {
        name: module.__dict__.copy()
        for name, module in sys.modules.copy().items()
        if isinstance(module, ModuleType) and name.startswith(("fontlabapp", "fontlab_fontport", "fontlab_glyport"))
    }
    for name in aliases:
        sys.modules.pop(name)
    for name in roots:
        fly.__dict__.pop(name, None)
    try:
        yield
    finally:
        for name in list(sys.modules):
            if not name.startswith("fly."):
                continue
            alias, dot, suffix = name[4:].partition(".")
            canonical = fly.ALIASES.get(alias, alias) + (dot + suffix if dot else "")
            parent, _, child = canonical.rpartition(".")
            module = sys.modules.get(parent)
            if parent in parents and module is not None:
                if child in parents[parent]:
                    module.__dict__[child] = parents[parent][child]
                else:
                    module.__dict__.pop(child, None)
            sys.modules.pop(name)
        sys.modules.update(aliases)
        for name in fly.ALIASES:
            fly.__dict__.pop(name, None)
        fly.__dict__.update(roots)
