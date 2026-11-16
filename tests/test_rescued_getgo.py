# this_file: tests/test_rescued_getgo.py
"""Exercise GetGo namespace imports using owned scripts, never corpus code."""

import sys
from pathlib import Path
from types import ModuleType

import pytest

from fontlabapp.core.legacy.examples import launch


@pytest.fixture
def getgo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep namespace modules local to this owned synthetic source tree."""
    for name in list(sys.modules):
        if name == "examples" or name.startswith("examples."):
            monkeypatch.delitem(sys.modules, name)
    package = tmp_path / "rescued/part2/examples/getgo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "_shared.py").write_text("VALUE = 42\n")
    script = package / "owned.py"
    script.write_text("from examples.getgo._shared import VALUE\n")
    try:
        yield script
    finally:
        for name in list(sys.modules):
            if name == "examples" or name.startswith("examples."):
                del sys.modules[name]


def test_launch_when_getgo_imports_shared_namespace_then_resolves_owned_tree(getgo):
    original_path, entries, directory = sys.path, list(sys.path), Path.cwd()
    for _ in range(2):
        result = launch(getgo)
        assert result["VALUE"] == 42, "Resolve the preserved namespace layout"
        helper = Path(sys.modules["examples.getgo._shared"].__file__)
        assert helper == getgo.parent / "_shared.py", "Never load a foreign helper"
        assert sys.path is original_path and sys.path == entries, "Restore import path"
        assert Path.cwd() == directory, "Restore working directory after launch"


@pytest.mark.parametrize(
    "foreign", ["examples", "examples.getgo", "examples.getgo._shared"]
)
def test_launch_when_namespace_is_foreign_then_refuses_before_script_body(
    getgo, monkeypatch, foreign
):
    module = ModuleType(foreign)
    module.__path__ = [str(getgo.parents[4] / "foreign")]
    module.__file__ = str(getgo.parents[4] / "foreign/__init__.py")
    monkeypatch.setitem(sys.modules, foreign, module)
    marker = getgo.parent / "started.txt"
    getgo.write_text(
        "from pathlib import Path\nPath('started.txt').write_text('ran')\n"
    )
    original_path, entries, directory = sys.path, list(sys.path), Path.cwd()
    with pytest.raises(RuntimeError, match="examples"):
        launch(getgo)
    assert not marker.exists(), "Refuse foreign namespaces before executing any script"
    assert sys.modules[foreign] is module, "Do not delete another script's modules"
    assert sys.path is original_path and sys.path == entries, "Restore import state"
    assert Path.cwd() == directory, "Restore working directory on refusal"


def test_launch_when_getgo_raises_then_restores_import_and_working_directories(getgo):
    getgo.write_text(
        "from examples.getgo._shared import VALUE\nraise ValueError('owned failure')\n"
    )
    original_path, entries, directory = sys.path, list(sys.path), Path.cwd()
    with pytest.raises(ValueError, match="owned failure"):
        launch(getgo)
    assert sys.path is original_path and sys.path == entries, (
        "Restore path after failure"
    )
    assert Path.cwd() == directory, "Restore cwd after failure"


def test_launch_when_script_is_unrelated_then_ignores_foreign_namespace(
    tmp_path, monkeypatch
):
    foreign = ModuleType("examples")
    monkeypatch.setitem(sys.modules, "examples", foreign)
    script = tmp_path / "owned.py"
    script.write_text("VALUE = 17\n")
    assert launch(script)["VALUE"] == 17, "Do not restrict ordinary scripts"
    assert sys.modules["examples"] is foreign, "Leave unrelated modules untouched"


def test_launch_when_foreign_examples_is_on_path_then_binds_only_owned_namespace(
    getgo, tmp_path, monkeypatch
):
    foreign = tmp_path / "installed/examples"
    foreign.mkdir(parents=True)
    (foreign / "__init__.py").write_text(
        "raise RuntimeError('foreign package executed')\n"
    )
    monkeypatch.syspath_prepend(str(foreign.parent))
    assert launch(getgo)["VALUE"] == 42, (
        "Do not import an installed unrelated examples package"
    )
    assert list(sys.modules["examples"].__path__) == [str(getgo.parent.parent)]


def test_launch_when_namespace_points_to_wrong_owned_subdirectory_then_refuses(
    getgo, monkeypatch
):
    module = ModuleType("examples")
    module.__path__ = [str(getgo.parent)]
    monkeypatch.setitem(sys.modules, "examples", module)
    with pytest.raises(RuntimeError, match="examples"):
        launch(getgo)


def test_launch_when_getgo_directory_is_outside_retained_tree_then_uses_ordinary_protocol(
    tmp_path, monkeypatch
):
    module = ModuleType("examples")
    monkeypatch.setitem(sys.modules, "examples", module)
    directory = tmp_path / "unrelated/getgo"
    directory.mkdir(parents=True)
    script = directory / "owned.py"
    script.write_text("VALUE = 23\n")
    assert launch(script)["VALUE"] == 23, (
        "Scope the namespace adapter to the retained layout"
    )
    assert sys.modules["examples"] is module
