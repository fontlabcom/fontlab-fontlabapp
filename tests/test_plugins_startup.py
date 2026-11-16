# this_file: tests/test_plugins_startup.py
"""Startup-block preservation using only temporary user data."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def startup():
    spec = importlib.util.spec_from_file_location(
        "startup_under_test", ROOT / "src/fontlabapp/plugins/startup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "original",
    [
        b"",
        b"x = 1",
        b"x = 1\n",
        b"x = 1\r\n",
        b"\xef\xbb\xbf# utf-8\n",
        b"# coding: latin-1\nname = '\xe9'\n",
    ],
)
def test_startup_install_remove_preserves_every_original_byte(
    startup, tmp_path, original
):
    path = tmp_path / "initScript.py"
    path.write_bytes(original)
    path.chmod(0o640)
    assert startup.update_startup(tmp_path)
    installed = path.read_bytes()
    compile(installed, str(path), "exec")
    assert not startup.update_startup(tmp_path)
    assert path.read_bytes() == installed
    assert path.stat().st_mode & 0o777 == 0o640
    assert startup.update_startup(tmp_path, remove=True)
    assert path.read_bytes() == original
    assert not startup.update_startup(tmp_path, remove=True)


def test_startup_missing_file_and_surrounding_new_content(startup, tmp_path):
    target = tmp_path / "new"
    assert not startup.update_startup(target, remove=True)
    assert not target.exists()
    assert startup.update_startup(target)
    path = target / "initScript.py"
    path.write_bytes(b"before = 1\n" + path.read_bytes() + b"after = 2")
    startup.update_startup(target, remove=True)
    assert path.read_bytes() == b"before = 1\nafter = 2"


@pytest.mark.parametrize(
    "content",
    [
        b"\n# BEGIN fontlabapp.plugins (owned separator)\n",
        b"# END fontlabapp.plugins\n",
        b"# BEGIN fontlabapp.plugins (owned separator)\n# END fontlabapp.plugins\n",
        b"\n# BEGIN fontlabapp.plugins (owned separator)\n# END fontlabapp.plugins",
        b"\n# BEGIN fontlabapp.plugins (owned separator)\n# END fontlabapp.plugins\n"
        * 2,
    ],
)
@pytest.mark.parametrize("remove", [False, True])
def test_startup_bad_markers_never_write(startup, tmp_path, content, remove):
    path = tmp_path / "initScript.py"
    path.write_bytes(content)
    with pytest.raises(ValueError, match="markers"):
        startup.update_startup(tmp_path, remove=remove)
    assert path.read_bytes() == content


def test_startup_symlink_and_replace_failure_preserve_user_file(
    startup, tmp_path, monkeypatch
):
    path = tmp_path / "initScript.py"
    target = tmp_path / "original"
    target.write_bytes(b"untouched")
    path.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        startup.update_startup(tmp_path)
    assert target.read_bytes() == b"untouched"
    path.unlink()
    path.write_bytes(b"old")

    def fail(*args):
        raise PermissionError("cannot replace")

    monkeypatch.setattr(startup.os, "replace", fail)
    with pytest.raises(PermissionError):
        startup.update_startup(tmp_path)
    assert path.read_bytes() == b"old"
    assert list(tmp_path.glob(".initScript-*")) == []


def test_hook_contains_install_failure(startup, monkeypatch, capsys):
    calls = []
    fake = SimpleNamespace(install=lambda: calls.append("boot"))
    monkeypatch.setitem(sys.modules, "fontlabapp.plugins", fake)
    # An earlier test may have cached the real lazy alias; resolve it afresh.
    monkeypatch.delitem(sys.modules, "fly.ap.plugins", raising=False)
    exec(startup.HOOK, {})
    assert calls == ["boot"]

    def fail():
        raise RuntimeError("broken plugin host")

    fake.install = fail
    exec(startup.HOOK, {})
    assert "broken plugin host" in capsys.readouterr().out


def test_startup_hook_when_executed_then_uses_real_fly_and_canonical_plugin_install(startup):
    code = """
import importlib
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import fly
assert Path(fly.__file__).resolve() == (Path(sys.argv[1]) / "fly/__init__.py").resolve()
import fontlabapp.plugins as plugins
calls = []
plugins.install = lambda: calls.append("install")
assert "from fly.ap.plugins import install" in sys.argv[2]
exec(sys.argv[2], {})
assert calls == ["install"]
assert importlib.import_module("fly.ap.plugins") is plugins
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code,
         str(ROOT.parent / "fontlab-fly" / "src"), startup.HOOK.decode("utf-8")],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
