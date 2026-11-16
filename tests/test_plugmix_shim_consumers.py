# this_file: tests/test_plugmix_shim_consumers.py
# SPDX-License-Identifier: Apache-2.0
"""No in-App module may import or name the deprecated ``fontlabapp.plugmix`` shim."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "fontlabapp"
SHIM = SRC / "plugmix"
LEGACY = "fontlabapp.plugmix"
# The entry-point group is an external contract that plugin packages register under.
ALLOWED_STRINGS = {("plugins/registry.py", LEGACY)}


def _is_legacy(name: str) -> bool:
    return name == LEGACY or name.startswith(LEGACY + ".")


def _package(path: Path) -> list[str]:
    return ["fontlabapp", *path.relative_to(SRC).parent.parts]


def _resolve(node: ast.ImportFrom, package: list[str]) -> str:
    """Absolute dotted module a (possibly relative) ``from`` import refers to."""
    base = package[: len(package) - (node.level - 1)] if node.level else []
    return ".".join([*base, *([node.module] if node.module else [])])


def _offences_in(source: str, rel: str, package: list[str]) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            target = _resolve(node, package)
            names = [f"{target}.{a.name}" for a in node.names]
            if _is_legacy(target) or any(_is_legacy(n) for n in names):
                found.append(f"{rel}:{node.lineno} from-import {'.' * node.level}{node.module or ''}")
        elif isinstance(node, ast.Import):
            found += [f"{rel}:{node.lineno} import {a.name}" for a in node.names if _is_legacy(a.name)]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and LEGACY in node.value:
            if (rel, node.value) not in ALLOWED_STRINGS:
                found.append(f"{rel}:{node.lineno} string or docstring names {LEGACY} (allowed: ALLOWED_STRINGS)")
    return found


def _offences(path: Path) -> list[str]:
    return _offences_in(path.read_text(encoding="utf-8"), path.relative_to(SRC).as_posix(), _package(path))


def test_app_modules_when_scanned_then_none_outside_the_shim_name_fontlabapp_plugmix():
    modules = [p for p in SRC.rglob("*.py") if SHIM not in p.parents]
    assert modules, "the scan must see the App sources"
    offences = [item for path in modules for item in _offences(path)]
    assert offences == [], "use fontlabapp.plugins; only the shim itself keeps the old name:\n" + "\n".join(offences)


def test_scan_when_relative_or_absolute_legacy_import_then_flagged():
    package = ["fontlabapp", "glyphs"]
    for source in (
        "from fontlabapp.plugmix import x",
        "from ..plugmix import x",
        "from ..plugmix.backend import x",
        "from .. import plugmix",
        "import fontlabapp.plugmix.backend",
    ):
        assert _offences_in(source, "glyphs/m.py", package), source


def test_scan_when_similar_or_unrelated_import_then_not_flagged():
    package = ["fontlabapp", "glyphs"]
    for source in ("from ..plugmixer import x", "from .. import plugins", "from . import identity", "import fontlabapp.plugins"):
        assert _offences_in(source, "glyphs/m.py", package) == [], source
