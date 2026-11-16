# this_file: tests/test_rescued_examples.py
# SPDX-License-Identifier: Apache-2.0
"""Standard-library checks using owned scripts, never archived examples."""

import gc
import sys
import tempfile
import unittest
import weakref
from pathlib import Path
from types import ModuleType

import fontlabapp.core.legacy.examples as api


class RescuedExamplesTests(unittest.TestCase):
    def test_launch_runs_main_with_sibling_import_and_relative_resource(self):
        before_cwd, before_path, entries = Path.cwd(), sys.path, list(sys.path)
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder).resolve()
            script = parent / "example.py"
            (parent / "resource.txt").write_text("owned resource")
            (parent / "rescued_owned_sibling.py").write_text("VALUE = 37\n")
            script.write_text(
                "from pathlib import Path\nimport sys\n"
                "from rescued_owned_sibling import VALUE\n"
                "resource = Path('resource.txt').read_text()\n"
                "during_cwd = Path.cwd()\nduring_path = list(sys.path)\n"
            )
            try:
                result = api.launch(script)
            finally:
                sys.modules.pop("rescued_owned_sibling", None)
            self.assertEqual(result["__name__"], "__main__")
            self.assertEqual(result["__file__"], str(script.resolve()))
            self.assertEqual(result["resource"], "owned resource")
            self.assertEqual(result["VALUE"], 37)
            self.assertEqual(result["during_cwd"], parent)
            self.assertEqual(result["during_path"][0], str(parent))
        self.assertEqual(Path.cwd(), before_cwd)
        self.assertIs(sys.path, before_path)
        self.assertEqual(sys.path, entries)

    def test_launch_restores_cwd_and_path_after_script_mutates_both_and_raises(self):
        before_cwd, before_path, entries = Path.cwd(), sys.path, list(sys.path)
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            (parent / "nested").mkdir()
            script = parent / "failing.py"
            script.write_text(
                "import os, sys\nos.chdir('nested')\n"
                "sys.path[:] = ['changed']\nsys.path = ['replaced']\n"
                "raise RuntimeError('owned script failure')\n"
            )
            with self.assertRaisesRegex(RuntimeError, "owned script failure"):
                api.launch(str(script))
        self.assertEqual(Path.cwd(), before_cwd)
        self.assertIs(sys.path, before_path)
        self.assertEqual(sys.path, entries)

    def test_launch_retains_returned_namespace_by_resolved_path(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "owned.py"
            script.write_text("class OwnedWidget:\n    pass\nwidget = OwnedWidget()\n")
            namespace = api.launch(script.parent / "." / script.name)
            reference = weakref.ref(namespace["widget"])
            self.assertIs(api._NAMESPACES[script.resolve()], namespace)
            del namespace
            gc.collect()
            self.assertIsNotNone(
                reference(),
                "Returned globals must keep top-level widget references alive",
            )

    def test_missing_or_directory_target_never_changes_caller_context(self):
        before_cwd, before_path, entries = Path.cwd(), sys.path, list(sys.path)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                api.launch(Path(folder) / "absent.py")
            with self.assertRaises(ValueError):
                api.launch(folder)
        self.assertEqual(Path.cwd(), before_cwd)
        self.assertIs(sys.path, before_path)
        self.assertEqual(sys.path, entries)


class RescuedPortTests(unittest.TestCase):
    def setUp(self):
        self.modules = {
            key: value for key, value in sys.modules.items()
            if key == "fontlab_python_examples" or key.startswith("fontlab_python_examples.")
        }
        for key in self.modules:
            del sys.modules[key]
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name).resolve() / "rescued"
        self.package = self.root / "part1"
        self.package.mkdir(parents=True)
        (self.package / "__init__.py").write_text("from .launcher import _host\n")
        (self.package / "launcher.py").write_text(
            "from types import SimpleNamespace\n"
            "qt = SimpleNamespace(QtCore=SimpleNamespace(Qt=SimpleNamespace(WA_QuitOnClose=17)))\n"
            "def _host():\n    return qt\n"
        )
        (self.package / "handle.py").write_text(
            "from types import SimpleNamespace\n"
            "class ExampleHandle:\n"
            "    def __init__(self):\n"
            "        self.owner = SimpleNamespace(closed=False)\n"
            "        self.widget = self\n        self.shown = 0\n        self.attributes = []\n"
            "    def inherits(self, name):\n        return name == 'QWidget'\n"
            "    def setAttribute(self, *args):\n        self.attributes.append(args)\n"
            "    def show(self):\n        self.shown += 1\n"
            "    def close(self):\n        self.owner.closed = True\n"
        )
        self.script = self.root / "part2/ports/insights/owned.py"
        self.script.parent.mkdir(parents=True)
        self.script.write_text(
            "from pathlib import Path\n"
            "from fontlab_python_examples.handle import ExampleHandle\n"
            "def build(qt):\n"
            "    handle = ExampleHandle()\n"
            "    handle.resource = Path('resource.txt').read_text()\n"
            "    handle.directory = Path.cwd()\n"
            "    handle.qt = qt\n"
            "    return handle\n"
            "if __name__ == '__main__':\n"
            "    raise AssertionError('obsolete named launcher must not run')\n"
        )
        (self.script.parent / "resource.txt").write_text("owned port resource")

    def tearDown(self):
        for key in list(sys.modules):
            if key == "fontlab_python_examples" or key.startswith("fontlab_python_examples."):
                del sys.modules[key]
        sys.modules.update(self.modules)

    def test_port_builds_shows_retains_and_reshows_owned_handle(self):
        before_cwd, before_path, entries = Path.cwd(), sys.path, list(sys.path)
        namespace = api.launch(self.script)
        handle = namespace["__rescued_handle__"]
        self.assertEqual(handle.resource, "owned port resource")
        self.assertEqual(handle.directory, self.script.parent)
        self.assertEqual(handle.attributes, [(17, False)])
        self.assertEqual(handle.shown, 1)
        self.assertIs(api.launch(self.script), namespace)
        self.assertEqual(handle.shown, 2, "Relaunch must reuse the live owned handle")
        handle.close()
        replacement = api.launch(self.script)["__rescued_handle__"]
        self.assertIsNot(replacement, handle, "Closed native wrappers must not be reused")
        self.assertEqual(Path.cwd(), before_cwd)
        self.assertIs(sys.path, before_path)
        self.assertEqual(sys.path, entries)

    def test_port_without_builder_reports_unsupported_instead_of_silent_success(self):
        self.script.write_text("VALUE = 'no UI builder'\n")
        with self.assertRaisesRegex(NotImplementedError, "build"):
            api.launch(self.script)
        self.assertNotIn(self.script, api._NAMESPACES)

    def test_retained_official_port_uses_the_same_owned_builder_protocol(self):
        script = self.root / "part3/pyqt-official-ports/ports/animation/owned.py"
        script.parent.mkdir(parents=True)
        script.write_bytes(self.script.read_bytes())
        (script.parent / "resource.txt").write_text("owned official resource")
        namespace = api.launch(script)
        handle = namespace["__rescued_handle__"]
        self.assertEqual(handle.resource, "owned official resource")
        self.assertEqual(handle.shown, 1)
        self.assertIs(api.launch(script)["__rescued_handle__"], handle)
        handle.close()

    def test_port_host_refusal_happens_before_executing_script(self):
        (self.package / "launcher.py").write_text(
            "def _host():\n    raise RuntimeError('existing FontLab QApplication required')\n"
        )
        self.script.write_text("raise AssertionError('port executed before host check')\n")
        with self.assertRaisesRegex(RuntimeError, "existing FontLab QApplication"):
            api.launch(self.script)

    def test_port_rejects_an_existing_foreign_legacy_package(self):
        package = ModuleType("fontlab_python_examples")
        package.__file__ = str(self.root / "foreign/__init__.py")
        sys.modules[package.__name__] = package
        with self.assertRaisesRegex(RuntimeError, "already loaded"):
            api.launch(self.script)
        self.assertIs(sys.modules[package.__name__], package)

    def test_partial_legacy_import_is_cleaned_and_orphan_modules_are_refused(self):
        (self.package / "__init__.py").write_text(
            "from . import handle\nraise RuntimeError('package import failed')\n"
        )
        with self.assertRaisesRegex(RuntimeError, "package import failed"):
            api.launch(self.script)
        self.assertFalse(any(key.startswith("fontlab_python_examples") for key in sys.modules))
        orphan = ModuleType("fontlab_python_examples.handle")
        sys.modules[orphan.__name__] = orphan
        with self.assertRaisesRegex(RuntimeError, "without their package"):
            api.launch(self.script)
        self.assertIs(sys.modules[orphan.__name__], orphan)

    def test_build_failure_propagates_and_restores_caller_context(self):
        self.script.write_text(
            "def build(qt):\n"
            "    import sys, os\n"
            "    sys.path = ['changed']\n"
            "    os.chdir('..')\n"
            "    raise ValueError('build failed')\n"
        )
        before_cwd, before_path, entries = Path.cwd(), sys.path, list(sys.path)
        with self.assertRaisesRegex(ValueError, "build failed"):
            api.launch(self.script)
        self.assertNotIn(self.script, api._NAMESPACES)
        self.assertEqual(Path.cwd(), before_cwd)
        self.assertIs(sys.path, before_path)
        self.assertEqual(sys.path, entries)

    def test_failed_reshow_closes_and_forgets_previously_retained_handle(self):
        namespace = api.launch(self.script)
        handle = namespace["__rescued_handle__"]

        def failed_show():
            raise RuntimeError("reshow failed")

        handle.show = failed_show
        with self.assertRaisesRegex(RuntimeError, "reshow failed"):
            api.launch(self.script)
        self.assertTrue(handle.owner.closed)
        self.assertNotIn(self.script, api._NAMESPACES)

    def test_ordinary_build_named_function_keeps_main_script_semantics(self):
        ordinary = self.root / "part2/ordinary.py"
        ordinary.write_text(
            "def build(qt):\n    raise AssertionError('not a port')\n"
            "executed_as = __name__\n"
        )
        namespace = api.launch(ordinary)
        self.assertEqual(namespace["executed_as"], "__main__")
        self.assertNotIn("__rescued_handle__", namespace)
        self.assertNotIn("fontlab_python_examples", sys.modules)

    def test_show_failure_closes_handle_restores_context_and_preserves_error(self):
        self.script.write_text(
            "from fontlab_python_examples.handle import ExampleHandle\n"
            "def build(qt):\n"
            "    handle = ExampleHandle()\n"
            "    def show():\n        raise ValueError('original show failure')\n"
            "    def close():\n"
            "        handle.owner.closed = True\n"
            "        raise RuntimeError('cleanup failure')\n"
            "    handle.show = show\n    handle.close = close\n"
            "    qt.failed_handle = handle\n    return handle\n"
        )
        before_cwd, before_path, entries = Path.cwd(), sys.path, list(sys.path)
        with self.assertRaisesRegex(ValueError, "original show failure") as caught:
            api.launch(self.script)
        self.assertTrue(sys.modules["fontlab_python_examples.launcher"].qt.failed_handle.owner.closed)
        self.assertIn("cleanup failure", " ".join(caught.exception.__notes__))
        self.assertNotIn(self.script, api._NAMESPACES)
        self.assertEqual(Path.cwd(), before_cwd)
        self.assertIs(sys.path, before_path)
        self.assertEqual(sys.path, entries)


if __name__ == "__main__":
    unittest.main()
