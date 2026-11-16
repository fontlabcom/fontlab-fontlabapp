# this_file: tests/test_fly_demo_routing.py
"""Qualify the real lazy finder used by Scripts from the known sibling source in an isolated interpreter."""

from pathlib import Path
import subprocess
import sys
import textwrap


FLY_SOURCE = Path(__file__).resolve().parents[2] / "fontlab-fly" / "src"


def test_demo_routes_when_loaded_then_share_real_provider_objects_and_metadata():
    result = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent('''
            import importlib
            import sys
            from pathlib import Path
            sys.path.insert(0, sys.argv[1])
            import fly
            assert Path(fly.__file__).resolve() == (Path(sys.argv[1]) / "fly/__init__.py").resolve()
            assert "fontlabapp" not in sys.modules
            assert "PythonQt" not in sys.modules
            for alias, canonical in (
                ("fly.ap", "fontlabapp"),
                ("fly.ap.qt.safe", "fontlabapp.qt.safe"),
                ("fly.ap.core.history.glyphs", "fontlabapp.core.history.glyphs"),
                ("fly.fp.memory", "fontlab_fontport.memory"),
                ("fly.pens.recording", "fontlab_pens.recording"),
            ):
                provider = importlib.import_module(canonical)
                metadata = tuple(getattr(provider, key, None) for key in ("__name__", "__spec__", "__package__", "__loader__", "__file__"))
                assert importlib.import_module(alias) is provider, alias
                assert tuple(getattr(provider, key, None) for key in ("__name__", "__spec__", "__package__", "__loader__", "__file__")) == metadata
            assert "PythonQt" not in sys.modules
        '''), str(FLY_SOURCE)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_standins_when_routed_then_real_finder_retains_identity_and_none_spec():
    result = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent('''
            import importlib
            import sys
            from pathlib import Path
            sys.path.insert(0, sys.argv[1])
            from types import ModuleType
            import fly
            assert Path(fly.__file__).resolve() == (Path(sys.argv[1]) / "fly/__init__.py").resolve()
            for alias, canonical in (("fly.fl", "echopy.fontlab"), ("fly.qt", "PythonQt")):
                provider = ModuleType(canonical)
                provider.__spec__ = None
                sys.modules[canonical] = provider
                assert importlib.import_module(alias) is provider
                assert provider.__name__ == canonical
                assert provider.__spec__ is None
        '''), str(FLY_SOURCE)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
