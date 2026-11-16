# this_file: tests/test_fontui_batch_containment.py
"""Actual BatchPanel refuses unsafe destinations before spawning any child."""
import hashlib
import importlib
import os
from pathlib import Path
import stat
import sys

import pytest


def input_tree(path: Path) -> dict:
    result = {}
    for item in [path, *sorted(path.rglob("*"))]:
        mode = stat.S_IMODE(item.lstat().st_mode)
        if item.is_symlink():
            result[str(item.relative_to(path))] = ("link", mode, os.readlink(item))
        elif item.is_dir():
            result[str(item.relative_to(path))] = ("dir", mode)
        else:
            result[str(item.relative_to(path))] = ("file", mode, hashlib.sha256(item.read_bytes()).hexdigest())
    return result


@pytest.fixture
def actual_panel(monkeypatch):
    from _feature_source_qt import owned_application, qt_namespace
    from PySide6 import QtCore, QtWidgets
    import shiboken6
    from fontlab_fontport.recipe import Recipe

    names = ["fontlabapp.fontui." + name for name in ("batch", "batch_worker", "lifecycle")]
    previous = {name: sys.modules.pop(name, None) for name in names}
    monkeypatch.setitem(sys.modules, "PythonQt", qt_namespace())
    monkeypatch.setitem(sys.modules, "fontlab", None)
    try:
        module = importlib.import_module("fontlabapp.fontui.batch")
        with owned_application():
            parent = QtWidgets.QWidget()
            panel = None
            try:
                panel = module.BatchPanel(lambda: Recipe(), parent, python=sys.executable)
                yield panel
            finally:
                if panel is not None:
                    panel.close()
                    assert panel._batch_close["complete"], "actual batch close must acknowledge cleanup"
                QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
                if shiboken6.isValid(parent):
                    shiboken6.delete(parent)
    finally:
        for name, old in previous.items():
            sys.modules.pop(name, None)
            if old is not None:
                sys.modules[name] = old


@pytest.mark.parametrize("layout", ["later-source", "reversed-sources", "destination-symlink"])
def test_start_when_generated_target_inside_any_input_then_no_spawn_or_write(actual_panel, tmp_path, layout):
    from _feature_source_qt import font_fixture
    from fontlab_fontport.batch import BatchRunner
    from ufoLib2 import Font

    sources = [tmp_path / "A.ufo", tmp_path / "B.ufo"]
    for index, path in enumerate(sources):
        font = font_fixture("feature liga { sub A B by A; } liga;\n", str(index))
        try:
            font.save(path)
        finally:
            font.close()
    destination = sources[1] / "new-output"
    if layout == "destination-symlink":
        alias = tmp_path / "into-B"
        alias.symlink_to(sources[1], target_is_directory=True)
        destination = alias / "new-output"
    selected = list(reversed(sources)) if layout == "reversed-sources" else sources
    panel = actual_panel
    assert type(panel.runner) is BatchRunner
    panel.set_sources(selected)
    panel.destination_control.setText(str(destination))
    before = [input_tree(path) for path in sources]
    progress = (panel.progress.minimum(), panel.progress.maximum(), panel.progress.value())
    completed = []
    panel.on_finish = completed.append
    audit = {"active": True, "spawns": []}

    def observe(event, args):
        if audit["active"] and event == "subprocess.Popen":
            audit["spawns"].append(args)

    sys.addaudithook(observe)  # Observation only; no replacement of runner/worker/Popen.
    with Font.open(sources[0], lazy=False) as first, Font.open(sources[1], lazy=False) as second:
        try:
            assert panel.start() is False
            assert panel.status.text == "Not started: Batch destination must be outside every source UFO"
            assert panel.process is None and panel.jobs is None and panel.results == []
            assert not panel.running and not panel.runner.running and not panel.timer.isActive()
            assert panel.log.count() == 0 and completed == [] and audit["spawns"] == []
            assert (panel.progress.minimum(), panel.progress.maximum(), panel.progress.value()) == progress
            assert not destination.exists()
        finally:
            audit["active"] = False
            assert [input_tree(path) for path in sources] == before
            with Font.open(sources[0], lazy=False) as after_first, Font.open(sources[1], lazy=False) as after_second:
                assert first == after_first and second == after_second


@pytest.mark.parametrize("names", [("CaseInput.ufo", "caseinput.ufo"), ("Café.ufo", "Cafe\u0301.ufo")], ids=["case", "unicode"])
@pytest.mark.parametrize("reverse", [False, True], ids=["later-input", "reversed"])
def test_start_when_destination_ancestor_is_filesystem_alias_then_containment_precedes_spawn(actual_panel, tmp_path, names, reverse, record_property):
    from _feature_source_qt import font_fixture
    from fontlab_fontport.batch import BatchRunner
    from fontlab_fontport.recipe import Recipe
    from ufoLib2 import Font

    sources = [tmp_path / "A.ufo", tmp_path / names[0]]
    for index, path in enumerate(sources):
        font = font_fixture("feature liga { sub A B by A; } liga;\n", str(index))
        try:
            font.save(path)
        finally:
            font.close()
    alternate = tmp_path / names[1]
    same = alternate.exists() and alternate.samefile(sources[1])
    record_property("filesystem_alias", same)
    record_property("literal_names", repr(names))
    if not same:
        alternate.mkdir()
        assert not alternate.samefile(sources[1])
    destination = alternate / "new-output"
    selected = list(reversed(sources)) if reverse else sources
    panel = actual_panel
    assert type(panel.runner) is BatchRunner
    panel.set_sources(selected)
    panel.destination_control.setText(str(destination))
    # Actual OS refusal prevents destructive worker execution on a missing fence.
    executable = tmp_path / "non-executable-python"
    executable.write_bytes(b"owned non-executable containment safety control\n")
    executable.chmod(0o600)
    panel.python = str(executable)
    record_property("interpreter_before_start", repr((str(executable), hashlib.sha256(executable.read_bytes()).hexdigest(), stat.S_IMODE(executable.stat().st_mode))))
    assert not os.access(executable, os.X_OK)
    before = [input_tree(path) for path in sources]
    progress = (panel.progress.minimum(), panel.progress.maximum(), panel.progress.value())
    completed = []
    panel.on_finish = completed.append
    audit = {"active": True, "attempts": []}

    def observe(event, args):
        if audit["active"] and event == "subprocess.Popen":
            audit["attempts"].append(args)

    sys.addaudithook(observe)
    with Font.open(sources[0], lazy=False) as first, Font.open(sources[1], lazy=False) as second:
        try:
            if same:
                assert panel.start() is False
                record_property("status_after_start", panel.status.text)
                record_property("popen_attempts", len(audit["attempts"]))
                assert panel.status.text == "Not started: Batch destination must be outside every source UFO"
                assert panel.process is None and panel.jobs is None and panel.results == []
                assert not panel.running and not panel.runner.running and not panel.timer.isActive()
                assert panel.log.count() == 0 and completed == [] and audit["attempts"] == []
                assert (panel.progress.minimum(), panel.progress.maximum(), panel.progress.value()) == progress
                assert not destination.exists()
            else:
                jobs = [(source, destination / f"{source.stem}-transformed.ufo") for source in selected]
                iterator = panel.runner.run(jobs, Recipe())
                try:
                    results = list(iterator)
                finally:
                    iterator.close()
                assert len(results) == 2 and all(result.ok for result in results)
                for source, target in jobs:
                    with Font.open(source, lazy=False) as original, Font.open(target, lazy=False) as output:
                        assert original == output
                assert not panel.runner.running and audit["attempts"] == []
        finally:
            audit["active"] = False
            assert [input_tree(path) for path in sources] == before
            with Font.open(sources[0], lazy=False) as after_first, Font.open(sources[1], lazy=False) as after_second:
                assert first == after_first and second == after_second
