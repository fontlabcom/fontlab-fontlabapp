# this_file: tests/test_package_boundaries.py
"""App must not depend on Glyport; Fontport only in the fontui FontParts editors.

Issue 122 T13b made App import neither peer. Issue 201 moved the FontParts-bound
Qt editors back into ``fontlabapp.fontui``, so those modules (``FONTPORT_EDITORS``)
may import ``fontlab_fontport``, as may ``fontui.feature_blocks`` (active-font
feature I/O, moved back with the editors). ``fontlabapp.fontui._load`` and
``fontui._fontport.require_fontport`` turn a missing Fontport into an
``ImportError`` that names the ``fontport`` extra.

What it does: parses every module under ``src/fontlabapp`` and fails when any
of them imports ``fontlab_glyport``, or ``fontlab_fontport`` outside the allowed
fontui modules. It also fails when ``pyproject.toml`` lists Glyport anywhere,
Fontport anywhere but the optional ``fontport`` extra, or any uv source other
than the non-peer ``fontlab-python-pens`` leaf.

How it works: AST only. Nothing is imported or executed. Static imports,
``__import__`` and ``importlib.import_module`` calls with a literal name are
all checked. Names in docstrings and tombstone messages are strings, not
imports, so they pass.

Why: Glyport depends on App, and Fontport's App integration is an optional
extra. A peer import elsewhere in App would close a packaging cycle, so App
could not be installed alone.
"""

import ast
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "fontlabapp"
PEERS = frozenset({"fontlab_glyport", "fontlab_fontport"})
PEER_DISTRIBUTIONS = ("fontlab-glyport", "fontlab-fontport")
#: The only modules that may import Fontport (FontParts-bound editors, issue 201,
#: and the feature-source helpers that returned with them).
FONTPORT_EDITORS = frozenset(
    SRC / "fontui" / f"{name}.py"
    for name in (
        "batch",
        "designspace_sources",  # Read-only source reports use Fontport readers.
        "detached_transform",
        "feature_blocks",
        "fontinfo",
        "groups",
        "kerning",
        "sequence",
        "shaping",
        "tmetrics",
        "transform",
        "ufo_roundtrip_editor",
    )
)
DYNAMIC_IMPORTERS = frozenset({"__import__", "import_module"})


def peer_imports(source: str) -> list[str]:
    """Return the peer module names that ``source`` imports, in order."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module or ""]
        elif isinstance(node, ast.Call) and _is_dynamic_import(node):
            names = [node.args[0].value]
        else:
            continue
        found += [name for name in names if name.split(".")[0] in PEERS]
    return found


def _is_dynamic_import(node: ast.Call) -> bool:
    """Tell whether ``node`` is ``__import__("x")`` or ``[mod.]import_module("x")``."""
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
    return (
        name in DYNAMIC_IMPORTERS
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    )


@pytest.mark.parametrize(
    "source,expected",
    [
        ("import fontlab_fontport", ["fontlab_fontport"]),
        ("import fontlab_glyport.ui as u", ["fontlab_glyport.ui"]),
        ("from fontlab_fontport.ui import x", ["fontlab_fontport.ui"]),
        ("def f():\n    from fontlab_glyport import y", ["fontlab_glyport"]),
        ("__import__('fontlab_fontport.ui')", ["fontlab_fontport.ui"]),
        ("importlib.import_module('fontlab_glyport')", ["fontlab_glyport"]),
        ("from . import fontlab_fontport", []),
        ("import fontlabapp.fontui", []),
        ("'fontlab_fontport.ui'  # only a string", []),
        ("x = 'import fontlab_glyport'", []),
    ],
)
def test_peer_imports_when_source_given_then_detects_only_real_imports(
    source: str, expected: list[str]
) -> None:
    assert peer_imports(source) == expected, source


def test_app_source_when_parsed_then_fontport_imports_stay_in_fontui_editors() -> None:
    files = sorted(SRC.rglob("*.py"))
    assert files, f"no App sources found under {SRC}"
    offenders = {
        str(path.relative_to(ROOT)): hits
        for path in files
        if (hits := peer_imports(path.read_text(encoding="utf-8")))
        and not (
            path in FONTPORT_EDITORS
            and path.is_relative_to(SRC / "fontui")
            and all(hit.split(".")[0] == "fontlab_fontport" for hit in hits)
        )
    }
    assert not offenders, f"App imports a peer package: {offenders}"


def test_fontport_editors_when_parsed_then_each_one_imports_fontport() -> None:
    """The allowlist stays honest: an editor that dropped Fontport leaves it."""
    stale = [
        str(path.relative_to(ROOT))
        for path in sorted(FONTPORT_EDITORS)
        if not peer_imports(path.read_text(encoding="utf-8"))
    ]
    assert not stale, f"allowlisted but no Fontport import: {stale}"


def test_pyproject_when_read_then_fontport_is_only_an_optional_extra() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    fontport = project["optional-dependencies"]["fontport"]
    assert len(fontport) == 1 and re.fullmatch(
        r"fontlab[-_]fontport(?:[<>=!~].+)?", fontport[0]
    ), fontport
    requirements = list(project.get("dependencies", []))
    for name, extra in project.get("optional-dependencies", {}).items():
        if name != "fontport":  # the one place Fontport may appear
            requirements += extra
    requirements += data.get("dependency-groups", {}).get("dev", [])
    bad = [
        r
        for r in requirements
        if r.lower().replace("_", "-").startswith(PEER_DISTRIBUTIONS)
    ]
    assert not bad, f"peer requirement outside the fontport extra: {bad}"
    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    # Only the zero-dependency pens leaf may have a source: it is not a peer.
    assert set(sources) <= {"fontlab-python-pens"}, f"peer uv source: {sources}"


# First Fontport tag containing the Issue 241 write-back fixes (5b8211f: UFO
# anchor/guideline copies and one contour shape among several). v1.2.1 lacks it.
FONTPORT_ISSUE241_FLOOR = (1, 2, 2)


def test_pyproject_when_read_then_fontport_floor_includes_issue241_writeback() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    (requirement,) = data["project"]["optional-dependencies"]["fontport"]
    match = re.fullmatch(r"fontlab[-_]fontport>=(\d+)\.(\d+)\.(\d+)", requirement)
    assert match, f"fontport extra must be a plain >=X.Y.Z floor: {requirement}"
    floor = tuple(int(part) for part in match.groups())
    assert floor >= FONTPORT_ISSUE241_FLOOR, (
        f"{requirement} admits a Fontport without the Issue 241 write-back fixes;"
        f" need >={'.'.join(map(str, FONTPORT_ISSUE241_FLOOR))}"
    )


#: What a studio module may import from this workspace: the public fontui and
#: core/hints surfaces, its own package and the native host. Never a peer.
STUDIO_ALLOWED = ("fontlabapp.fontui", "fontlabapp.core", "fontlabapp.hints", "fontlabapp.studios", "fontlab")
STUDIO_PRIVATE_FONTUI = "fontlabapp.fontui."


def studio_imports(source: str) -> list[str]:
    """Return workspace/peer module names a studio source imports (absolute imports)."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            found.append(node.module or "")
        elif isinstance(node, ast.Call) and _is_dynamic_import(node):
            found.append(node.args[0].value)
    roots = PEERS | {"fontlabapp", "fontlab", "fontgate", "fontlab_glyport", "fontlab_fontport"}
    return [name for name in found if name.split(".")[0] in roots]


def studio_offence(name: str) -> bool:
    """True when a studio may not import ``name`` (peers, private fontui modules, other App parts)."""
    if name.split(".")[0] in PEERS or name.startswith(STUDIO_PRIVATE_FONTUI):
        return True
    return not any(name == allowed or name.startswith(allowed + ".") for allowed in STUDIO_ALLOWED)


def test_studio_offence_when_names_given_then_only_public_surfaces_pass() -> None:
    allowed = ["fontlabapp.fontui", "fontlabapp.core.history", "fontlabapp.hints.postscript", "fontlab", "fontlabapp.studios.kerning"]
    refused = ["fontlab_fontport", "fontlabapp.fontui.kerning", "fontlabapp.scripting", "fontlab_glyport.ui"]
    assert [n for n in allowed if studio_offence(n)] == []
    assert [n for n in refused if not studio_offence(n)] == []


def test_studio_sources_when_parsed_then_only_public_app_surfaces_imported() -> None:
    files = sorted((SRC / "studios").rglob("*.py"))
    assert files, "studios package missing"
    offenders = {
        str(path.relative_to(ROOT)): bad
        for path in files
        if (bad := [n for n in studio_imports(path.read_text(encoding="utf-8")) if studio_offence(n)])
    }
    assert not offenders, f"studio imports outside fontui/core/hints/fontlab: {offenders}"


def test_pyproject_when_read_then_shaping_libraries_are_core_dependencies() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    core = {req.split(">")[0].split("=")[0].split("<")[0].strip().lower() for req in data["project"]["dependencies"]}
    assert {"fonttools", "uharfbuzz"} <= core, core
    extras = data["project"]["optional-dependencies"]
    assert "fontui" in extras and "fontui-shaping" in extras, "old install lines keep resolving"
