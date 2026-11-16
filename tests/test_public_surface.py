# this_file: tests/test_public_surface.py
"""The issue-122 shared modules publish a complete, documented surface (T14).

What it checks, per module:
    - every name in ``__all__`` exists, and ``from <module> import *`` works;
    - every public top-level name (def, class or assignment without a leading
      underscore) is in ``__all__``, so nothing public is left unlisted;
    - every exported def and class has its own docstring, and so does every
      public method (and ``__init__``) of an exported class.

How: the module source is parsed with ``ast``, so docstrings and names come
from the file itself, never from inherited or generated ``__doc__`` values
(``NamedTuple`` writes one automatically). Constants cannot hold a docstring;
they are documented with ``#:`` comments and are only checked for listing.

Import rule: ``importlib.import_module`` selects each explicit domain module.
Root subpackages and legacy aliases also resolve before the native fallback.
"""

import ast
import importlib
import re
from pathlib import Path
from types import ModuleType

import pytest


def test_current_usage_docs_when_scanned_then_teach_domain_paths_instead_of_flat_aliases():
    from fontlabapp._legacy import ALIASES, FACADES

    root = Path(__file__).resolve().parents[1]
    docs = list((root / "examples").glob("*.md")) + [
        root / "DEPENDENCIES.md",
        root / "generated/fontlabapp_shim/README.md",
    ]
    contents = {str(path.relative_to(root)): path.read_text() for path in docs}
    contents["README.md usage"] = (
        (root / "README.md")
        .read_text()
        .split("### Migration from flat module names", 1)[0]
    )
    for path, source in contents.items():
        for old in ALIASES.keys() - FACADES.keys():
            for prefix in (old, old.replace("fontlabapp.", "fly.ap.", 1)):
                assert not re.search(
                    r"(?<![\w.])" + re.escape(prefix) + r"(?!\w)", source
                ), f"{path} teaches legacy path {prefix}; use {ALIASES[old]}"


MODULES = (
    "fontlabapp.contours.affine",
    "fontlabapp.anchors.panel.model",
    "fontlabapp.anchors.writer",
    "fontlabapp.components.creation",
    "fontlabapp.components.panel.model",
    "fontlabapp.components.writer",
    "fontlabapp.contours.copy",
    "fontlabapp.qt.painting.editor",
    "fontlabapp.qt.menus",
    "fontlabapp.qt.dialogs",
    "fontlabapp.qt.safe",
    "fontlabapp.fontui",
    "fontlabapp.core.edit_guards",
    "fontlabapp.core.history.masters",
    "fontlabapp.glyphs.catalog.model",
    "fontlabapp.glyphs.copies",
    "fontlabapp.glyphs.creation",
    "fontlabapp.hints.postscript",
    "fontlabapp.core.history.glyphs",
    "fontlabapp.masters.layers.writer",
    "fontlabapp.metrics.master_writer",
    "fontlabapp.metrics.panel.model",
    "fontlabapp.proof.tabs.named",
    "fontlabapp.glyphs.names.model",
    "fontlabapp.contours.panel.model",
    "fontlabapp.contours.transform.model",
    "fontlabapp.contours.writer",
    "fontlabapp.contours.selection.panel.model",
    "fontlabapp.metrics.zones.native",
)


def _tree(module: ModuleType) -> ast.Module:
    """Parse the module's own source file."""
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def _public_top_level(tree: ast.Module) -> set[str]:
    """Names that the module body defines without a leading underscore."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {n for n in names if not n.startswith("_")}


def _undocumented(tree: ast.Module, exported: set[str]) -> list[str]:
    """Exported defs/classes, and their public methods, that lack a docstring."""
    missing: list[str] = []
    for node in tree.body:
        if (
            not isinstance(node, (ast.FunctionDef, ast.ClassDef))
            or node.name not in exported
        ):
            continue
        if not ast.get_docstring(node):
            missing.append(node.name)
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            if item.name.startswith("_") and item.name != "__init__":
                continue
            if not ast.get_docstring(item):
                missing.append(f"{node.name}.{item.name}")
    return missing


@pytest.mark.parametrize("name", MODULES)
def test_all_when_read_then_every_listed_name_exists_and_star_import_works(
    name: str,
) -> None:
    module = importlib.import_module(name)
    exported = getattr(module, "__all__", None)
    assert exported, f"{name} has no __all__"
    absent = [n for n in exported if not hasattr(module, n)]
    assert not absent, f"{name}.__all__ lists missing names: {absent}"
    scope: dict = {}
    exec(f"from {name} import *", scope)  # noqa: S102 - the star import is the subject
    assert set(exported) <= set(scope), f"star import of {name} lost names"


#: Public top-level names kept out of ``__all__`` on purpose, per module.
NOT_EXPORTED: dict[str, set[str]] = {}


@pytest.mark.parametrize("name", MODULES)
def test_all_when_compared_with_source_then_no_public_name_is_unlisted(
    name: str,
) -> None:
    module = importlib.import_module(name)
    exported = set(getattr(module, "__all__", ()))
    kept_out = NOT_EXPORTED.get(name, set())
    assert not kept_out & exported, (
        f"{name}: excluded names are exported: {kept_out & exported}"
    )
    unlisted = _public_top_level(_tree(module)) - exported - kept_out
    assert not unlisted, f"{name}: public but not in __all__: {sorted(unlisted)}"


@pytest.mark.parametrize("name", MODULES)
def test_exports_when_parsed_then_every_def_class_and_method_has_a_docstring(
    name: str,
) -> None:
    module = importlib.import_module(name)
    missing = _undocumented(_tree(module), set(getattr(module, "__all__", ())))
    assert not missing, f"{name}: no docstring on {missing}"


def test_readme_when_read_then_moved_table_names_every_tombstone() -> None:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(
        encoding="utf-8"
    )
    rest = readme.partition("## Moved in 1.2.0")[2]
    assert rest, "README needs a '## Moved in 1.2.0' section"
    table = rest.split("\n## ", 1)[0]
    expected = [
        "fontlabapp.core.legacy.vanilla.VanillaSession",
        "fontlab_glyport.ui.session.VanillaSession",
        "fontlabapp.core.scripting.read_feature_blocks",
        "fontlabapp.core.scripting.write_feature_blocks",
        "fontlabapp.fontui.feature_blocks",
        "fontlab_fontport.ui",
        "fontlabapp.fontui",
        "MainWindowNotFound",
    ]
    # Whole identifiers only: "groups" must not pass on "groups_view" alone.
    absent = [
        i for i in expected if not re.search(rf"(?<!\w){re.escape(i)}(?!\w)", table)
    ]
    assert not absent, f"README migration table misses {absent}"


def test_undocumented_when_class_method_lacks_docstring_then_reported() -> None:
    tree = ast.parse(
        'class A:\n    """A."""\n    def __init__(self):\n        pass\n'
        '    def run(self):\n        """Run."""\n    def _x(self):\n        pass\n'
        "def f():\n    pass\n"
    )
    assert _undocumented(tree, {"A", "f"}) == ["A.__init__", "f"]


def test_public_top_level_when_parsed_then_private_and_imports_excluded() -> None:
    tree = ast.parse(
        "import os\nX = 1\n_y = 2\nZ: int = 3\ndef g():\n    pass\nclass _H:\n    pass\n"
    )
    assert _public_top_level(tree) == {"X", "Z", "g"}
