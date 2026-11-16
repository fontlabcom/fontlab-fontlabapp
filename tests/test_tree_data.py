# this_file: tests/test_tree_data.py
"""Immutable generic tree topology and complete font-metadata adaptation."""

import pytest
from fontlabapp.glyphs.tree.model import from_table
from fontlabapp.qt.tables.filter.model import Table
from fontlabapp.qt.trees.data import Tree


def test_tree_keeps_order_repeated_values_and_arbitrary_depth():
    rows = (
        (-1, ("A", "root")),
        (0, ("A",)),
        (1, ("leaf", "value", "third")),
        (-1, ("B", "")),
    )
    tree = Tree(("Name", "Details"), rows)
    assert tree.rows is rows and tree.headers == ("Name", "Details")
    with pytest.raises(AttributeError):
        tree.rows = ()


@pytest.mark.parametrize(
    "headers,rows",
    [
        ((), ()),
        (["A"], ()),
        ((1,), ()),
        (("A",), []),
        (("A",), ((True, ("A",)),)),
        (("A",), ((0, ("A",)),)),
        (("A",), ((-2, ("A",)),)),
        (("A",), ((-1, []),)),
        (("A",), ((-1, ()),)),
        (("A",), ((-1, (1,)),)),
        (("A",), ((0,),)),
    ],
)
def test_tree_rejects_mutable_invalid_cyclic_or_unreadable_input(headers, rows):
    with pytest.raises((TypeError, ValueError)):
        Tree(headers, rows)


def test_empty_tree_and_complete_metadata_rows_keep_missing_and_multiple_assignments():
    assert Tree(("A",), ()).rows == ()
    table = Table(
        ("Glyph", "Unicode", "Modified"),
        (("A", "U+0041 U+0391", "2026-01-01 01:00:00"), ("a.alt", "", "")),
    )
    tree = from_table(table)
    assert tree.rows == (
        (-1, ("A", "U+0041 U+0391")),
        (0, ("Unicode", "U+0041")),
        (0, ("Unicode", "U+0391")),
        (0, ("Modified", "2026-01-01 01:00:00")),
        (-1, ("a.alt", "Not encoded")),
        (4, ("Unicode", "Not encoded")),
        (4, ("Modified", "Not recorded")),
    )
    assert from_table(Table(("A", "B", "C"), ())).rows == ()


def test_metadata_conversion_rejects_wrong_capture_and_expired_complete_budget():
    with pytest.raises(TypeError):
        from_table(None)
    with pytest.raises(TimeoutError):
        from_table(Table(("A", "B", "C"), (("A", "U+0041", ""),)), deadline=0)


def test_capture_passes_the_same_deadline_into_the_existing_native_reader(monkeypatch):
    import sys
    import time
    from types import ModuleType

    import fontlabapp.glyphs.tree.model as api

    module = ModuleType("fontlabapp.glyphs.catalog.native")
    seen = []
    module.capture = lambda **kw: seen.append(kw) or Table(("A", "B", "C"), ())
    monkeypatch.setitem(sys.modules, module.__name__, module)
    deadline = time.monotonic() + 10
    assert api.capture(deadline=deadline).rows == () and seen == [
        {"deadline": deadline}
    ]


@pytest.mark.parametrize(
    "entry,outline", [("show_outline", True), ("show_tree", False)]
)
def test_public_entrypoints_use_lazy_owned_dialog_and_exact_capture(
    monkeypatch, entry, outline
):
    import sys
    from types import ModuleType

    import fontlabapp.glyphs.tree.model as api
    import fontlabapp.core.scripting as script_api

    calls = []
    module = ModuleType("fontlabapp.glyphs.tree.ui")
    module.GlyphTreeDialog = lambda *args: calls.append(args) or "owned"
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(
        script_api, "show_script_dialog", lambda factory, key: (factory("parent"), key)
    )
    result = getattr(api, entry)()
    assert result == (
        "owned",
        "glyph_metadata_outline" if outline else "glyph_metadata_tree",
    )
    assert calls == [
        (
            "parent",
            "Glyph Metadata Outline" if outline else "Glyph Metadata Tree",
            result[1],
            api.capture,
            outline,
        )
    ]


def test_cold_imports_do_not_load_fontlab_bindings_or_other_bridges():
    import subprocess
    import sys
    from pathlib import Path

    import fontlabapp.glyphs.tree.model as api

    script = """
import importlib.abc,sys,dataclasses
class OnlyStdlib(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] not in sys.stdlib_module_names | {'fontlabapp'}:
   raise AssertionError(fullname)
sys.meta_path.insert(0,OnlyStdlib());sys.path.insert(0,sys.argv[1])
import fontlabapp.glyphs.tree.model,fontlabapp.qt.trees.data,fontlabapp.qt.trees.readonly
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str((Path(__file__).resolve().parents[1] / "src"))],
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("entry", ["show_outline", "show_tree"])
def test_public_ui_refuses_worker_thread_before_loading_or_constructing_widgets(
    monkeypatch, entry
):
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from types import ModuleType

    import fontlabapp.glyphs.tree.model as api
    import fontlabapp.core.scripting as script_api

    module = ModuleType("fontlabapp.glyphs.tree.ui")

    def forbidden(*args):
        raise AssertionError("worker reached widget construction")

    module.GlyphTreeDialog = forbidden
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(
        script_api, "show_script_dialog", lambda factory, key: factory(None)
    )
    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(RuntimeError, match="main UI thread"),
    ):
        pool.submit(getattr(api, entry)).result()
