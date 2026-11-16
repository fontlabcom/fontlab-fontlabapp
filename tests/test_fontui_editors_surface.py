# this_file: tests/test_fontui_editors_surface.py
"""The FontParts editor factories are public, listed and documented (issue 201).

They came from ``fontlab_fontport.ui`` (issue 122 T15 surface test).
"""

import ast
from pathlib import Path

import fontlabapp.fontui as fontui

ROOT = Path(__file__).resolve().parents[1]
FACTORIES = (
    "font_info_editor",
    "groups_editor",
    "kerning_editor",
    "transform_editor",
    "batch_panel",
    "glyph_sequence",
)


def _public_functions(path: Path) -> set[str]:
    """Top-level functions without a leading underscore."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }


def test_all_when_compared_then_it_lists_every_public_factory() -> None:
    defined = _public_functions(ROOT / "src/fontlabapp/fontui/__init__.py")
    assert defined <= set(fontui.__all__), defined - set(fontui.__all__)
    assert set(FACTORIES) <= defined, set(FACTORIES) - defined
    assert all(callable(getattr(fontui, name)) for name in FACTORIES)


def test_readme_when_read_then_editor_factories_are_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in FACTORIES:
        assert f"`{name}" in readme, f"README.md does not document {name}"
    assert "fontlab-fontlabapp[fontport]" in readme, "README must name the extra"


def test_fontui_sources_when_distributed_then_all_declare_apache_2_0():
    sources = sorted((ROOT / "src/fontlabapp/fontui").rglob("*.py"))
    assert sources, "The complete fontui source scope must exist"
    missing = [
        str(path.relative_to(ROOT))
        for path in sources
        if "# SPDX-License-Identifier: Apache-2.0"
        not in path.read_text().splitlines()[:5]
    ]
    assert not missing, f"Fontui sources missing the owner-approved licence: {missing}"
