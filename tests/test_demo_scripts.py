# this_file: tests/test_demo_scripts.py
"""Structural gate for every ``Scripts/<Category>/<Title> Demo.py`` (Issue 208).

What: discovers every ``Scripts/**/*.py`` and checks the menu layout, the
two-line header, the What/Use/Safety docstring, Python 3.11 syntax, stdlib-only
module-level imports and the ``__main__`` guard. It also resolves every
``fly.ap`` import by AST through its canonical provider: the module must exist under ``src/fontlabapp`` and
each imported name must be defined there (or be a submodule). Nothing is
imported, so native code never loads.
Why: FontLab's installer copies ``Scripts/<Category>/<Tool>.py`` into the
Scripts menu, so a wrong path, a stale import or a module-level native import
breaks the menu entry at the owner's desk. New demo files need no edit here.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "Scripts"
SOURCE = ROOT / "src"
CATEGORIES = {
    "Anchors", "Components", "Contours", "Features", "Font Info", "Guides", "Kerning",
    "Masters", "Metrics", "Names", "Objects", "Proof", "Reports", "Utilities", "Widgets",
    "Font Editors",
}
FORBIDDEN_ROOTS = {"PySide2", "PySide6", "PyQt5", "PyQt6"}
SCRIPT_FILES = sorted(SCRIPTS.rglob("*.py"))
IDS = [str(path.relative_to(SCRIPTS)) for path in SCRIPT_FILES]
SKIP_BODIES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 11))


def walk_outside(node: ast.AST, skip: tuple):
    """Yield descendants of ``node``, not entering the bodies of ``skip`` types."""
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, skip):
            yield from walk_outside(child, skip)


def canonical(dotted: str) -> str:
    """Resolve the documented App namespace without importing native code."""
    return "fontlabapp" + dotted.removeprefix("fly.ap") if dotted == "fly.ap" or dotted.startswith("fly.ap.") else dotted


def module_file(dotted: str) -> Path | None:
    """The source file or package ``__init__`` of ``dotted`` under src, else None."""
    base = SOURCE.joinpath(*canonical(dotted).split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def defined_names(path: Path) -> set[str]:
    """Names a module binds at its top level, including inside if/try blocks.

    Comprehension targets are local to the comprehension and do not count.
    """
    names: set[str] = set()
    skip = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    for node in walk_outside(parse(path), skip):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def fontlabapp_imports(tree: ast.Module) -> list[tuple[str, str | None]]:
    """(module, imported name or None) for every App/Fly import, at any depth."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(alias.name, None) for alias in node.names if canonical(alias.name).split(".")[0] == "fontlabapp"]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and canonical(node.module or "").split(".")[0] == "fontlabapp":
            found += [(node.module, alias.name) for alias in node.names]
    return found


def test_scripts_when_listed_then_not_empty() -> None:
    assert SCRIPT_FILES, "Scripts/ holds no demo scripts"


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=IDS)
def test_demo_when_placed_then_menu_layout_holds(path: Path) -> None:
    relative = path.relative_to(ROOT)
    assert len(relative.parts) == 3, f"{relative}: must be Scripts/<Category>/<Tool>.py"
    assert relative.parts[1] in CATEGORIES, f"{relative}: unknown category {relative.parts[1]!r}"
    assert path.name.endswith(" Demo.py"), f"{relative}: file name must end with ' Demo.py'"


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=IDS)
def test_demo_when_read_then_header_and_docstring_state_what_use_safety(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == f"# this_file: {path.relative_to(ROOT).as_posix()}"
    assert lines[1] == "# SPDX-License-Identifier: Apache-2.0"
    doc = ast.get_docstring(parse(path)) or ""
    for label in ("What:", "Use:", "Safety:"):
        assert re.search(rf"^{label} \S", doc, re.MULTILINE), f"{path.name}: docstring lacks a '{label}' paragraph"


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=IDS)
def test_demo_when_parsed_then_imports_are_lazy_and_stdlib_only_at_module_level(path: Path) -> None:
    tree = parse(path)
    for node in walk_outside(tree, SKIP_BODIES):
        if isinstance(node, ast.Import):
            roots = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            roots = [(node.module or "").split(".")[0]]
        else:
            continue
        for root in roots:
            assert root in sys.stdlib_module_names, f"{path.name} line {node.lineno}: module-level import of {root!r}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            assert not {name.split(".")[0] for name in names} & FORBIDDEN_ROOTS, f"{path.name}: forbidden import {names}"


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=IDS)
def test_demo_when_parsed_then_ends_with_main_guard(path: Path) -> None:
    last = parse(path).body[-1]
    guard = (
        isinstance(last, ast.If)
        and ast.unparse(last.test) == "__name__ == '__main__'"
        and [ast.unparse(statement) for statement in last.body] == ["main()"]
        and not last.orelse
    )
    assert guard, f"{path.name}: must end with `if __name__ == \"__main__\": main()`"


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=IDS)
def test_demo_when_importing_fontlabapp_then_modules_and_names_exist(path: Path) -> None:
    imports = fontlabapp_imports(parse(path))
    for dotted, name in imports:
        source = module_file(dotted)
        assert source is not None, f"{path.name}: no source for module {dotted}"
        if name is not None and name != "*":
            ok = name in defined_names(source) or module_file(f"{dotted}.{name}") is not None
            assert ok, f"{path.name}: {dotted} defines no {name!r}"


MODULE_LITERAL = re.compile(r"(?:fontlabapp|fly\.ap)(?:\.[A-Za-z_]\w*)+")


def module_literals(tree: ast.Module) -> list[str]:
    """Every dotted ``fontlabapp.<name>...`` path spelled in a non-docstring string.

    Covers whole-value literals (``import_module`` lists, ``MODULES`` tuples),
    f-string parts and prose in messages: the places the coverage contract
    credits. Docstrings are exempt; they describe and do not name targets.
    """
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
    }
    return [
        match.group(0)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
        for match in MODULE_LITERAL.finditer(node.value)
    ]


def unresolved_literal(dotted: str) -> str | None:
    """Why ``dotted`` is not a module (plus at most one defined name), else None."""
    parts = canonical(dotted).split(".")
    for cut in range(len(parts), 0, -1):
        source = module_file(".".join(parts[:cut]))
        if source is None:
            continue
        rest = parts[cut:]
        if not rest:
            return None
        if len(rest) == 1 and rest[0] in defined_names(source):
            return None
        return f"{'.'.join(parts[:cut])} has no {'.'.join(rest)!r}"
    return "no module"


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=IDS)
def test_demo_when_naming_fontlabapp_in_a_string_then_it_resolves(path: Path) -> None:
    for literal in module_literals(parse(path)):
        problem = unresolved_literal(literal)
        assert problem is None, f"{path.name}: string {literal!r}: {problem}"


def test_gate_when_scanning_scripts_then_string_literals_are_found() -> None:
    assert sum(len(module_literals(parse(path))) for path in SCRIPT_FILES) > 0, "no fontlabapp string literal matched"


def test_gate_when_given_a_bogus_literal_then_it_is_rejected() -> None:
    tree = ast.parse("A = 'fontlabapp.core.no_such_module'\nB = 'fontlabapp.core.scripting.no_such_name'\nC = 'fontlabapp.core.a.b.c'")
    bogus = module_literals(tree)
    assert len(bogus) == 3
    assert all(unresolved_literal(literal) for literal in bogus), "every bogus literal must be reported"
    assert unresolved_literal("fontlabapp.core.scripting") is None
    assert unresolved_literal("fontlabapp.core.scripting.show_script_dialog") is None
    messages = ast.parse("A = 'Opens fontlabapp.core.no_such for you'\nB = f'{A} fontlabapp.core.also_missing.'")
    assert module_literals(messages) == ["fontlabapp.core.no_such", "fontlabapp.core.also_missing"], "prose and f-string names are resolved too"
    assert all(unresolved_literal(name) for name in module_literals(messages)), "prose naming a missing module is reported"
    split = ast.parse("x = 'fontlabapp.core.' + 'no_such'")
    assert module_literals(split) == ["fontlabapp.core"], "a concatenated name yields only its literal part"
    documented = ast.parse('"""Mentions fontlabapp.core.no_such."""\ndef f():\n    """Also fontlabapp.core.gone."""\n')
    assert module_literals(documented) == [], "docstrings are exempt"


def test_gate_when_name_is_a_comprehension_target_then_it_is_not_defined(tmp_path: Path) -> None:
    module = tmp_path / "m.py"
    module.write_text("rows = [leak for leak in range(3)]\nfor looped in rows:\n    pass\n", encoding="utf-8")
    names = defined_names(module)
    assert "leak" not in names, "a comprehension target is local to the comprehension"
    assert {"rows", "looped"} <= names, "a module-level assignment and for target are real bindings"


def test_gate_when_given_a_bad_import_then_helpers_reject_it() -> None:
    """The resolver itself must refuse a missing module and a missing name."""
    assert module_file("fontlabapp.core.no_such_module") is None
    assert "no_such_name" not in defined_names(module_file("fontlabapp.core.menu_names"))
    assert "snake" in defined_names(module_file("fontlabapp.core.menu_names"))
    assert "_native" in defined_names(module_file("fontlabapp"))


def test_gate_when_given_fly_paths_then_checks_real_canonical_exports() -> None:
    tree = ast.parse("from fly.ap.core.scripting import show_script_dialog\nimport fly.ap.core.history.glyphs as history")
    assert fontlabapp_imports(tree) == [("fly.ap.core.scripting", "show_script_dialog"), ("fly.ap.core.history.glyphs", None)]
    assert module_file("fly.ap.core.scripting") == module_file("fontlabapp.core.scripting")
    assert unresolved_literal("fly.ap.core.scripting.show_script_dialog") is None
    assert unresolved_literal("fly.ap.core.scripting.no_such_name")
    assert unresolved_literal("fly.ap.core.no_such_module")
    assert module_literals(ast.parse("x = 'fly.ap.core.no_such_module'")) == ["fly.ap.core.no_such_module"]


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=IDS)
def test_demo_when_importing_public_apis_then_uses_fly(path: Path) -> None:
    canonical_roots = {"fontlabapp", "fontlab_fontport", "fontlab_glyport", "fontlab_pens", "fontlab", "fontgate", "fontpr", "PythonQt", "typerig"}
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        assert not {name.split(".")[0] for name in names} & canonical_roots, f"{path.name}: public provider import bypasses Fly: {names}"
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_native" for node in ast.walk(parse(path)))
