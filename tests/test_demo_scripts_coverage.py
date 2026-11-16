# this_file: tests/test_demo_scripts_coverage.py
"""Coverage contract: every fontlabapp feature is named by an App demo (Issue 208).

What: enumerates the features on disk (every non-underscore module or package
directly under a ``fontlabapp`` domain, plus any non-underscore root module) and
asserts each is referenced by some ``Scripts/**/*.py`` file. A reference is the
explicit dotted name ``fontlabapp.<domain>.<feature>`` (or a deeper name) found
by ``ast`` in an import or in any string literal, docstrings included.
Why: the demos are the menu-level tour of the App modules. A new module with no
demo should fail here, not go unnoticed. ``EXCLUDED`` holds the only exceptions.
"""

import ast
import compileall
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "fontlabapp"
SCRIPTS = ROOT / "Scripts"
DOTTED = re.compile(r"(?:fontlabapp|fly\.ap)(?:\.[A-Za-z_][A-Za-z0-9_]*)+")

# Required private source excluded by name at any level, never features.
EXCLUDED_NAMES = {
    "_legacy": "private legacy shim, retained for old imports only",
}
# Private ("_") and dot-named entries (tool state such as a git-ignored .omc/) are skipped.
HIDDEN = ("_", ".")
# Dotted feature -> reason. Add an entry only when a demo cannot show the feature.
EXCLUDED: dict[str, str] = {}


def features() -> set[str]:
    """Dotted names of every second-level feature and every public root module."""
    found = set()
    for entry in PACKAGE.iterdir():
        if entry.name.startswith(HIDDEN) or entry.name in EXCLUDED_NAMES:
            continue
        if entry.is_file() and entry.suffix == ".py":
            found.add(f"fontlabapp.{entry.stem}")
        elif entry.is_dir():
            for child in entry.iterdir():
                name = child.stem if child.is_file() else child.name
                if name.startswith(HIDDEN) or name in EXCLUDED_NAMES:
                    continue
                if child.is_dir() or child.suffix == ".py":
                    found.add(f"fontlabapp.{entry.name}.{name}")
    return found


def names_in(path: Path) -> set[str]:
    """Every dotted ``fontlabapp...`` name an import or string literal spells out."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 11))):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.add(node.module)
            out.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.update(DOTTED.findall(node.value))
    return {"fontlabapp" + name.removeprefix("fly.ap") if name.startswith("fly.ap.") else name for name in out if name.startswith(("fontlabapp.", "fly.ap."))}


def referenced() -> set[str]:
    out: set[str] = set()
    for path in SCRIPTS.rglob("*.py"):
        out |= names_in(path)
    return out


def is_referenced(feature: str, names: set[str]) -> bool:
    return any(name == feature or name.startswith(feature + ".") for name in names)


def test_features_when_enumerated_then_filesystem_scan_finds_every_domain():
    found = features()
    assert len(found) > 100, f"suspiciously few features: {len(found)}"
    assert "fontlabapp.qt.tables" in found, "qt.tables must be enumerated"
    assert not any("__pycache__" in name or "._" in name for name in found), sorted(found)


def test_demos_when_scanned_then_every_feature_is_referenced():
    names = referenced()
    missing = sorted(f for f in features() - set(EXCLUDED) if not is_referenced(f, names))
    assert not missing, f"features with no demo reference ({len(missing)}): {missing}"


def test_excluded_when_listed_then_every_entry_still_exists_and_has_a_reason():
    found = features()
    for feature, reason in EXCLUDED.items():
        assert feature in found, f"stale exclusion {feature}: no such feature on disk"
        assert reason.strip(), f"exclusion {feature} needs a reason"
    for name, reason in EXCLUDED_NAMES.items():
        assert reason.strip(), f"excluded name {name} needs a reason"
        assert any(PACKAGE.rglob(name)) or any(PACKAGE.rglob(f"{name}.py")), (
            f"stale excluded name {name}: nothing on disk"
        )


def test_is_referenced_when_name_only_shares_a_prefix_then_not_a_match():
    names = {"fontlabapp.qt.tablesx", "fontlabapp.qt.trees.sub"}
    assert not is_referenced("fontlabapp.qt.tables", names), "prefix must not match"
    assert is_referenced("fontlabapp.qt.trees", names), "deeper name must match"
    assert is_referenced("fontlabapp.qt.tablesx", names), "exact name must match"


def test_names_in_when_comment_import_and_string_then_comment_is_ignored(tmp_path):
    source = tmp_path / "demo.py"
    source.write_text(
        '"""See fontlabapp.a.docstring."""\n'
        "# fontlabapp.a.comment\n"
        "def main():\n"
        "    from fontlabapp.a import imported\n"
        "    return 'fontlabapp.a.literal.sub x'\n",
        encoding="utf-8",
    )
    got = names_in(source)
    assert "fontlabapp.a.docstring" in got, got
    assert "fontlabapp.a.imported" in got, got
    assert "fontlabapp.a.literal.sub" in got, got
    assert "fontlabapp.a.comment" not in got, got


def test_features_when_dot_directories_exist_then_they_are_skipped(tmp_path, monkeypatch):
    (tmp_path / ".omc" / "state").mkdir(parents=True)
    (tmp_path / "core" / ".omc").mkdir(parents=True)
    (tmp_path / "core" / "real.py").write_text("", encoding="utf-8")
    monkeypatch.setitem(globals(), "PACKAGE", tmp_path)
    assert features() == {"fontlabapp.core.real"}, "dot-named tool state must not count as a feature"


@pytest.mark.parametrize("compiled", [False, True], ids=["absent-cache", "compiled-cache"])
def test_features_when_caches_absent_or_compiled_then_complete_inventory_is_unchanged(
    tmp_path, monkeypatch, compiled
):
    expected = features()
    package = tmp_path / "fontlabapp"
    shutil.copytree(PACKAGE, package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    assert not list(package.rglob("__pycache__")), "the owned copy must start cold"
    if compiled:
        for source in (package / "__init__.py", package / "core" / "__init__.py"):
            assert compileall.compile_file(str(source), force=True, quiet=1)
            assert list((source.parent / "__pycache__").glob("*.pyc"))
    monkeypatch.setitem(globals(), "PACKAGE", package)
    assert len(expected) > 100, "compare the complete package inventory"
    assert features() == expected, "root and domain caches must not change any public feature"
    assert not any("__pycache__" in name for name in features())
    test_excluded_when_listed_then_every_entry_still_exists_and_has_a_reason()


def test_excluded_when_required_legacy_source_is_missing_then_stale_assertion_fails(
    tmp_path, monkeypatch
):
    legacy = tmp_path / "_legacy.py"
    legacy.write_text("", encoding="utf-8")
    monkeypatch.setitem(globals(), "PACKAGE", tmp_path)
    test_excluded_when_listed_then_every_entry_still_exists_and_has_a_reason()
    legacy.unlink()
    with pytest.raises(AssertionError, match="stale excluded name _legacy: nothing on disk"):
        test_excluded_when_listed_then_every_entry_still_exists_and_has_a_reason()


def test_names_in_when_fly_alias_then_keeps_feature_coverage_and_ignores_comments(tmp_path):
    path = tmp_path / "demo.py"
    path.write_text("from fly.ap.qt.tables import filter\nimport fly.ap.core.history.glyphs as history\nTARGET = 'fly.ap.ui.windows'\n# fly.ap.no_such_comment\n")
    names = names_in(path)
    assert {"fontlabapp.qt.tables.filter", "fontlabapp.core.history.glyphs", "fontlabapp.ui.windows"} <= names
    assert "fontlabapp.no_such_comment" not in names
