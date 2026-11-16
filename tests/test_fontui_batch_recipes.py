# this_file: tests/test_fontui_batch_recipes.py
"""Real recipe controls and batch execution through the public workbench."""
import importlib
import importlib.util
import sys

import pytest


@pytest.fixture
def actual_qt(monkeypatch):
    from _feature_source_qt import owned_application, qt_namespace
    from PySide6 import QtCore, QtWidgets
    import shiboken6

    qt = qt_namespace()
    class Combo(qt.QtGui.QComboBox):
        currentText = property(QtWidgets.QComboBox.currentText)
    class Slider(QtWidgets.QSlider):
        value = property(QtWidgets.QSlider.value)
    qt.QtGui.QComboBox, qt.QtGui.QSlider = Combo, Slider
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.setitem(sys.modules, "fontlab", None)
    names = ["fontlabapp.fontui." + name for name in
             ("batch_recipes", "batch", "batch_worker", "transform", "transform_view", "lifecycle")]
    names.append("fly.ap.fontui.batch_recipes")
    previous = {name: sys.modules.pop(name, None) for name in names}
    try:
        with owned_application() as app:
            parent = QtWidgets.QWidget()
            yield qt, parent, app
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            if shiboken6.isValid(parent):
                shiboken6.delete(parent)
    finally:
        for name, old in previous.items():
            sys.modules.pop(name, None)
            if old is not None:
                sys.modules[name] = old


def test_show_when_no_font_supplied_then_real_recipe_controls_and_batch_panel(actual_qt):
    qt, parent, app = actual_qt
    name = "fontlabapp.fontui.batch_recipes"
    assert importlib.util.find_spec(name) is not None, "The public batch recipe workbench is absent"
    module = importlib.import_module(name)
    owner = module.show(parent=parent, python=sys.executable)
    try:
        from fontlabapp.fontui.transform import TransformEditor
        from fontlabapp.fontui.batch import BatchPanel
        assert type(owner.editor) is TransformEditor
        assert type(owner.panel) is BatchPanel
        assert owner.editor.font is None and owner.editor.result is None
        assert owner.editor.diagnostic.text == "No font supplied"
        assert owner.editor.canvas.isHidden() and owner.editor.glyph_control.isHidden()
        assert not owner.editor.matrix["xx"].isHidden()
        assert owner.panel.process is None and not owner.panel.running
        assert owner.recipe() == owner.editor.recipe()
    finally:
        owner.release()
        app.processEvents()
        assert owner.editor._close_complete
        assert owner.panel._batch_close["complete"]
        assert owner._released


@pytest.fixture
def workbench(actual_qt):
    qt, parent, app = actual_qt
    module = importlib.import_module("fontlabapp.fontui.batch_recipes")
    owner = module.show(parent=parent, python=sys.executable)
    try:
        yield owner, app
    finally:
        owner.release()
        app.processEvents()
        if not owner._released:
            owner._release_now()
        assert owner._released, owner.problems
        assert owner.editor._close_complete and owner.panel._batch_close["complete"]
        from fontlabapp.fontui import batch_worker
        wait_until(app, lambda: not batch_worker._PENDING)
        assert not batch_worker._PENDING


def wait_until(app, predicate, seconds=25):
    import time
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline, "owned work did not finish"
        app.processEvents()
        time.sleep(0.005)


@pytest.fixture
def rich_inputs(tmp_path):
    from _feature_source_qt import font_fixture
    from test_fontui_batch_containment import input_tree
    from ufoLib2 import Font
    from ufoLib2.objects import Component

    paths = [tmp_path / "A.ufo", tmp_path / "B.ufo"]
    for index, path in enumerate(paths):
        font = font_fixture("feature liga { sub A B by A; } liga;\n", str(index))
        font.newGlyph("C").components.append(Component("B", (1, 0, 0, 1, 5, 7)))
        font["A"].components.append(Component("C", (1, 0, 0, 1, 2, 3)))
        font.save(path)
        font.close()
    before = [input_tree(path) for path in paths]
    models = [Font.open(path, lazy=False) for path in paths]
    try:
        yield paths, tmp_path / "outputs", models
    finally:
        assert [input_tree(path) for path in paths] == before
        for path, model in zip(paths, models, strict=True):
            with Font.open(path, lazy=False) as reopened:
                assert reopened == model
            model.close()


def configure(owner, inputs):
    paths, destination, _ = inputs
    owner.panel.set_sources(paths)
    owner.panel.destination_control.setText(str(destination))


def assert_process_released(process):
    from pathlib import Path
    assert process.child.poll() is not None
    assert process.output.fileno() == -1
    assert not Path(process.scratch).exists()


@pytest.mark.parametrize("mode", ["fractional", "disabled", "zero", "identity"])
def test_start_when_rich_inputs_then_exact_reopened_outputs_and_single_capture(workbench, rich_inputs, mode):
    from ufoLib2 import Font
    owner, app = workbench
    configure(owner, rich_inputs)
    editor = owner.editor
    editor.matrix["xx"].setText("2")
    editor.matrix["yy"].setText("3")
    editor.matrix["dx"].setText("8")
    editor.matrix["dy"].setText("-4")
    editor.intensity_field.setText("12.5")
    if mode == "disabled":
        editor.enabled_control.setChecked(False)
    elif mode == "zero":
        editor.intensity_field.setText("0")
    elif mode == "identity":
        editor.buttons["reset"].click()
    captured = []
    original = sys.getprofile()
    recipe_code = type(editor).recipe.__code__
    def observe(frame, event, arg):
        if event == "return" and frame.f_code is recipe_code:
            captured.append(arg)
    finished = []
    owner.panel.on_finish = finished.append
    try:
        sys.setprofile(observe)
        assert owner.panel.start() is True
    finally:
        sys.setprofile(original)
    process = owner.panel.process
    assert process.child.pid != __import__("os").getpid()
    assert len(captured) == 1 and captured[0] is not None
    assert owner.panel.start() is False
    wait_until(app, lambda: not owner.panel.running)
    assert [row.ok for row in owner.panel.results] == [True, True]
    assert len(finished) == 1 and finished[0] == owner.panel.results
    assert finished[0] is not owner.panel.results
    assert owner.panel.log.count() == 2
    assert owner.panel.progress.value() == 2
    assert owner.panel.status.text == "Finished: 2 succeeded, 0 failed."
    paths, destination, models = rich_inputs
    for source, model in zip(paths, models, strict=True):
        with Font.open(destination / (source.stem + "-transformed.ufo"), lazy=False) as result:
            assert result.info == model.info and result.lib == model.lib
            assert result.features.text == model.features.text
            assert result.groups == model.groups and result.kerning == model.kerning
            assert dict(result.images) == dict(model.images) and dict(result.data) == dict(model.data)
            assert result.layers.layerOrder == model.layers.layerOrder
            if mode != "fractional":
                assert result == model
            else:
                glyph = result["A"]
                assert [(p.x, p.y) for p in glyph.contours[0].points] == [(1, -0.5), (113.5, -0.5), (113.5, 124.5)]
                assert glyph.width == 675.28125 and glyph.height == 1125.625
                assert (glyph.anchors[0].x, glyph.anchors[0].y) == (114.0625, 874.5)
                assert tuple(glyph.image.transformation) == (1.125, 0, 0, 1.25, 16.1875, -22.6875)
                assert [c.baseGlyph for c in glyph.components] == ["B", "C"]
                assert result.layers["owned.background"]["untouched"].width == 374.625
    assert_process_released(process)
    assert owner.editor.font is None and owner.editor.result is None


@pytest.mark.parametrize("field,value", [("xx", "bad"), ("xx", "nan"), ("xy", "inf"),
    ("xx", "0"), ("xx", "-1"), ("intensity", "-1"), ("intensity", "101"),
    ("intensity", "nan"), ("intensity", "bad")])
def test_start_when_recipe_invalid_then_actual_refusal_without_output(workbench, rich_inputs, field, value):
    owner, app = workbench
    configure(owner, rich_inputs)
    if field == "xx" and value == "-1":
        owner.editor.intensity_field.setText("50")
    control = owner.editor.intensity_field if field == "intensity" else owner.editor.matrix[field]
    control.setText(value)
    assert owner.panel.start() is False
    assert owner.panel.status.text.startswith("Not started:")
    assert owner.panel.process is None and owner.panel.results == []
    assert not rich_inputs[1].exists()


@pytest.mark.parametrize("case", ["python", "sources", "destination", "nested", "existing"])
def test_start_when_selection_invalid_then_no_spawn(workbench, rich_inputs, monkeypatch, case):
    owner, app = workbench
    configure(owner, rich_inputs)
    paths, destination, _ = rich_inputs
    if case == "python":
        owner.panel.python = None
        monkeypatch.delenv("FONTLABAPP_BATCH_PYTHON", raising=False)
    elif case == "sources":
        owner.panel.set_sources([])
    elif case == "destination":
        owner.panel.destination_control.setText("")
    elif case == "nested":
        owner.panel.destination_control.setText(str(paths[1] / "nested"))
    else:
        destination.mkdir()
        (destination / "A-transformed.ufo").mkdir()
    assert owner.panel.start() is False
    assert owner.panel.process is None and not owner.panel.running
    assert owner.panel.status.text.startswith("Not started:")


def test_start_when_bad_middle_ufo_then_continue_actual_per_file_results(workbench, rich_inputs, tmp_path):
    owner, app = workbench
    configure(owner, rich_inputs)
    broken = tmp_path / "Broken.ufo"
    broken.mkdir()
    paths, destination, _ = rich_inputs
    owner.panel.set_sources([paths[0], broken, paths[1]])
    completed = []
    owner.panel.on_finish = completed.append
    assert owner.panel.start()
    process = owner.panel.process
    wait_until(app, lambda: not owner.panel.running)
    assert [row.ok for row in owner.panel.results] == [True, False, True]
    assert owner.panel.results[1].error
    assert len(completed) == 1 and completed[0] == owner.panel.results
    assert owner.panel.status.text == "Finished: 2 succeeded, 1 failed."
    assert not (destination / "Broken-transformed.ufo").exists()
    assert_process_released(process)


def test_release_when_saved_provider_called_then_fenced_before_deferred_cleanup(workbench):
    owner, app = workbench
    provider = owner.panel.recipe
    assert owner.release() is False
    assert owner.panel.start() is False
    with pytest.raises(RuntimeError, match="closed"):
        provider()
    assert owner.panel.on_finish is None
    app.processEvents()
    assert owner._released and owner.release() is True


def test_show_when_two_windows_then_independent_controls_and_cleanup(actual_qt):
    _, parent, app = actual_qt
    module = importlib.import_module("fontlabapp.fontui.batch_recipes")
    first, second = module.show(parent=parent), module.show(parent=parent)
    try:
        first.editor.matrix["dx"].setText("17.25")
        assert first.recipe().matrix[4] == 17.25
        assert second.recipe().matrix[4] == 0
        first.release()
        app.processEvents()
        assert first._released and not second._closing
        assert not second.editor.closed and not second.panel.closed
    finally:
        second.release()
        app.processEvents()
        assert first._released and second._released


@pytest.mark.parametrize("fault", ["false", "exception", "baseexception"])
def test_release_when_real_child_hide_refuses_then_owner_retained_for_explicit_retry(workbench, monkeypatch, fault):
    owner, app = workbench
    widget = owner.panel.widget
    real_hide = widget.hide
    error = RuntimeError("owned hide refusal") if fault == "exception" else KeyboardInterrupt("owned hide interruption")
    def refuse():
        if fault == "false":
            return False
        raise error
    monkeypatch.setattr(widget, "hide", refuse)
    owner.release()
    app.processEvents()
    assert not owner._released and owner in importlib.import_module("fontlabapp.fontui.batch_recipes")._HANDLES
    assert not owner.panel._batch_close["complete"] and owner.problems
    assert owner.panel.closed and owner.editor.closed
    monkeypatch.setattr(widget, "hide", real_hide)
    owner.release()
    app.processEvents()
    assert owner._released and owner.panel._batch_close["complete"]


def test_parent_when_destroyed_then_both_real_children_acknowledge(actual_qt):
    import shiboken6
    _, parent, app = actual_qt
    owner = importlib.import_module("fontlabapp.fontui.batch_recipes").show(parent=parent)
    shiboken6.delete(parent)
    app.processEvents()
    assert owner._released, owner.problems
    assert owner.editor._close_complete and owner.panel._batch_close["complete"]


@pytest.mark.parametrize("behavior", ["mutate-copy", "error", "close"])
def test_completion_when_callback_runs_then_exact_copy_error_and_close_semantics(workbench, rich_inputs, behavior):
    owner, app = workbench
    configure(owner, rich_inputs)
    seen = []
    def finish(rows):
        seen.append(rows)
        assert rows == owner.panel.results and rows is not owner.panel.results
        if behavior == "mutate-copy":
            rows.clear()
        elif behavior == "error":
            raise ValueError("owned callback failure")
        else:
            owner.release()
    owner.panel.on_finish = finish
    assert owner.panel.start()
    process = owner.panel.process
    wait_until(app, lambda: not owner.panel.running)
    assert len(seen) == 1 and len(owner.panel.results) == 2
    assert_process_released(process)
    if behavior == "error":
        assert "Callback failed: owned callback failure" in owner.panel.status.text
    elif behavior == "close":
        wait_until(app, lambda: owner._released)
        assert owner.panel.on_finish is None


def traced_interpreter(tmp_path, mode):
    """Owned -I adapter observes actual runner code; no run/save replacement."""
    import shlex
    trace = tmp_path / "observe_child.py"
    trace.write_text("""import inspect, json, os, sys, time
from pathlib import Path
from fontlab_fontport.batch import BatchRunner
from fontlab_fontport import batch
root = Path(__file__).parent
(root / 'child-origin.json').write_text(json.dumps({'pid': os.getpid(), 'batch': batch.__file__, 'isolated': sys.flags.isolated}))
lines, start = inspect.getsourcelines(BatchRunner._execute)
line = start + next(i for i, value in enumerate(lines) if 'if cancelled():' in value)
code = BatchRunner._execute.__code__
mode = """ + repr(mode) + """
def observe(frame, event, arg):
    if frame.f_code is code and event == 'line' and frame.f_lineno == line and frame.f_locals['index'] == 2:
        sys.settrace(None)
        (root / 'ready').touch()
        deadline = time.monotonic() + 15
        while not (root / 'go').exists():
            if time.monotonic() > deadline:
                raise TimeoutError('owned test barrier was not released')
            time.sleep(0.005)
        if mode == 'protocol':
            print('not a result row', flush=True)
            raise SystemExit(0)
        if mode == 'nonzero':
            raise SystemExit(7)
    return observe
sys.settrace(observe)
body, spec = sys.argv[-2:]
sys.argv = ['-c', spec]
exec(compile(body, '<actual BatchProcess CHILD>', 'exec'), {'__name__': '__main__'})
""")
    shell = tmp_path / "observed-python"
    shell.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -I " + shlex.quote(str(trace)) + ' "$@"\n')
    shell.chmod(0o755)
    return str(shell)


@pytest.mark.parametrize("action", ["cancel", "close", "destroy", "protocol", "nonzero"])
def test_actual_child_when_between_files_then_cancel_failure_or_close_preserves_partial_outputs(workbench, rich_inputs, tmp_path, action):
    import json
    from pathlib import Path
    import shiboken6
    owner, app = workbench
    configure(owner, rich_inputs)
    owner.panel.python = traced_interpreter(tmp_path, action)
    completions = []
    owner.panel.on_finish = completions.append
    assert owner.panel.start()
    process = owner.panel.process
    try:
        wait_until(app, lambda: (tmp_path / "ready").exists())
        wait_until(app, lambda: len(owner.panel.results) == 1 and owner.panel.log.count() == 1)
        assert (rich_inputs[1] / "A-transformed.ufo").is_dir()
        assert not (rich_inputs[1] / "B-transformed.ufo").exists()
        origin = json.loads((tmp_path / "child-origin.json").read_text())
        assert origin["isolated"] == 1 and origin["pid"] == process.child.pid
        assert origin["batch"].endswith("src/fontlab_fontport/batch.py")
        if action == "cancel":
            owner.panel.cancel()
        elif action == "close":
            owner.release()
        elif action == "destroy":
            shiboken6.delete(owner.owned.content)
        if action in ("close", "destroy"):
            # release()/destroy drain through QTimer.singleShot(0); open the child's barrier only once the
            # queued close has written the cancel request, or the child can finish file B first.
            wait_until(app, lambda: Path(process.cancel_path).exists())
        (tmp_path / "go").touch()
        if action in ("close", "destroy"):
            wait_until(app, lambda: owner._released)
            assert owner.panel._batch_close["complete"]
            assert owner.editor._close_complete
        else:
            wait_until(app, lambda: not owner.panel.running)
        wait_until(app, lambda: process.child.poll() is not None and not Path(process.scratch).exists())
        assert_process_released(process)
        assert not (rich_inputs[1] / "B-transformed.ufo").exists()
        assert len(completions) == (1 if action == "cancel" else 0)
        if action == "cancel":
            assert len(owner.panel.results) == 1 and owner.panel.status.text.startswith("Cancelled:")
        if action in ("protocol", "nonzero"):
            assert len(owner.panel.results) == 1 and owner.panel.results[0].ok
            assert owner.panel.status.text.startswith("Batch stopped:")
            assert owner.panel.start() is False, "existing partial output refuses replay"
            assert owner.panel.status.text.startswith("Not started:")
    finally:
        (tmp_path / "go").touch()
        if process.child.poll() is None:
            process.cancel()
            wait_until(app, lambda: process.child.poll() is not None)


@pytest.mark.parametrize("error_type", [ValueError, KeyboardInterrupt])
def test_show_when_second_child_construction_fails_then_primary_error_and_owned_cleanup(actual_qt, monkeypatch, error_type):
    qt, parent, app = actual_qt
    module = importlib.import_module("fontlabapp.fontui.batch_recipes")
    real = qt.QtGui.QProgressBar
    failure = error_type("owned panel construction failure")
    def refuse(*args, **kwargs):
        raise failure
    monkeypatch.setattr(qt.QtGui, "QProgressBar", refuse)
    before = list(module._HANDLES)
    with pytest.raises(error_type) as caught:
        module.show(parent=parent)
    assert caught.value is failure
    app.processEvents()
    assert module._HANDLES == before
    monkeypatch.setattr(qt.QtGui, "QProgressBar", real)


def test_release_when_hide_callback_reenters_then_no_duplicate_close(workbench, monkeypatch):
    owner, app = workbench
    real_hide = owner.panel.widget.hide
    calls = []
    def reenter():
        calls.append(1)
        assert owner._release_now() is False
        assert owner.panel.start() is False
        return real_hide()
    monkeypatch.setattr(owner.panel.widget, "hide", reenter)
    owner.release()
    app.processEvents()
    assert owner._released and calls == [1]


def test_choose_when_actual_dialog_cancelled_then_sources_unchanged(workbench, monkeypatch):
    owner, app = workbench
    qt = importlib.import_module("PythonQt")
    monkeypatch.setattr(qt.QtGui.QFileDialog, "getExistingDirectory", lambda *args: "")
    before = list(owner.panel.sources)
    owner.panel.add_button.click()
    assert owner.panel.sources == before and owner.panel.process is None


@pytest.mark.parametrize("error_type", [ValueError, KeyboardInterrupt])
def test_construction_when_primary_and_cleanup_fail_then_both_errors_and_owner_retained(actual_qt, monkeypatch, error_type):
    qt, parent, app = actual_qt
    module = importlib.import_module("fontlabapp.fontui.batch_recipes")
    base = qt.QtGui.QWidget
    refusal = [True]
    primary = error_type("owned constructor primary")
    class RefusingWidget(base):
        def hide(self):
            if refusal[0]:
                return False
            return super().hide()
    def broken_progress(*args):
        raise primary
    monkeypatch.setattr(qt.QtGui, "QWidget", RefusingWidget)
    monkeypatch.setattr(qt.QtGui, "QProgressBar", broken_progress)
    before = list(module._HANDLES)
    with pytest.raises(BaseExceptionGroup) as caught:
        module.show(parent=parent)
    pending, = [x for x in module._HANDLES if x not in before]
    leaves = []
    def visit(error):
        if isinstance(error, BaseExceptionGroup):
            for child in error.exceptions:
                visit(child)
        else:
            leaves.append(error)
    visit(caught.value)
    assert primary in leaves and any(isinstance(e, RuntimeError) for e in leaves)
    assert pending.peers and pending.problems and not pending._released
    refusal[0] = False
    pending.release()
    app.processEvents()
    if not pending._released:
        pending._release_now()
    assert pending._released


def test_two_windows_when_both_started_then_independent_processes_and_outputs(actual_qt, rich_inputs, tmp_path):
    _, parent, app = actual_qt
    module = importlib.import_module("fontlabapp.fontui.batch_recipes")
    owners = [module.show(parent=parent, python=sys.executable) for _ in range(2)]
    processes = []
    try:
        for index, owner in enumerate(owners):
            owner.panel.set_sources([rich_inputs[0][index]])
            owner.panel.destination_control.setText(str(tmp_path / ("output" + str(index))))
            owner.editor.matrix["dx"].setText(str(index + 1))
            assert owner.panel.start()
            processes.append(owner.panel.process)
        assert processes[0].child.pid != processes[1].child.pid
        wait_until(app, lambda: all(not owner.panel.running for owner in owners))
        for index, owner in enumerate(owners):
            assert len(owner.panel.results) == 1 and owner.panel.results[0].ok
            assert owner.panel.results[0].source == rich_inputs[0][index]
            assert_process_released(processes[index])
    finally:
        for owner in owners:
            owner.release()
        app.processEvents()
        assert all(owner._released for owner in owners)


def test_finished_run_when_next_recipe_refused_then_status_does_not_claim_current_success(workbench, rich_inputs):
    owner, app = workbench
    configure(owner, rich_inputs)
    seen = []
    owner.panel.on_finish = seen.append
    assert owner.panel.start()
    wait_until(app, lambda: not owner.panel.running)
    previous = list(owner.panel.results)
    owner.editor.matrix["xx"].setText("not a number")
    assert owner.panel.start() is False
    assert owner.panel.status.text.startswith("Not started: xx: not a number")
    assert owner.panel.results == previous and len(seen) == 1
    assert not owner.panel.running


@pytest.mark.parametrize("action", ["close", "close-nested-events", "nested-start", "nested-provider"])
def test_provider_when_dispatch_reenters_then_fenced_or_single_acquisition(workbench, rich_inputs, tmp_path, action):
    owner, app = workbench
    configure(owner, rich_inputs)
    nonexecutable = tmp_path / "not-python"
    nonexecutable.write_text("Owned non-executable selection")
    nonexecutable.chmod(0o600)
    owner.panel.python = str(nonexecutable)
    attempts, observed = [], []
    active = [True]
    def audit(event, args):
        if active[0] and event == "subprocess.Popen":
            attempts.append(args)
    sys.addaudithook(audit)
    code = type(owner.editor).recipe.__code__
    previous = sys.getprofile()
    def observe(frame, event, result):
        if event != "return" or frame.f_code is not code or frame.f_locals.get("self") is not owner.editor or observed:
            return
        observed.append(result)
        if action.startswith("close"):
            assert owner.release() is False
            if action == "close-nested-events":
                app.processEvents()
                assert not owner._released
                assert owner._release_now() is False
                assert not owner.editor._close_complete
                assert owner.panel._batch_close is None
        elif action == "nested-provider":
            with pytest.raises(RuntimeError, match="already being captured"):
                owner.recipe()
        else:
            assert owner.panel.start() is False
            assert "already being captured" in owner.panel.status.text
    try:
        sys.setprofile(observe)
        assert owner.panel.start() is False
    finally:
        sys.setprofile(previous)
        active[0] = False
    assert len(observed) == 1
    assert len(attempts) == (0 if action.startswith("close") else 1)
    assert owner.panel.process is None and not rich_inputs[1].exists()
    if action.startswith("close"):
        assert "closed" in owner.panel.status.text
        app.processEvents()
        assert owner._released
        assert owner.editor._close_complete and owner.panel._batch_close["complete"]
    else:
        assert "Permission denied" in owner.panel.status.text


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_release_when_scheduling_raises_then_same_error_and_public_retry(workbench, monkeypatch, error_type):
    owner, app = workbench
    timer = owner.qt.QtCore.QTimer
    real = timer.singleShot
    error = error_type("owned queue failure")
    calls = []
    def refuse(*args):
        raise error
    previous = sys.getprofile()
    def observe(frame, event, result):
        if event == "call" and frame.f_code.co_name == "close":
            for role, peer in (("editor", owner.editor), ("panel", owner.panel), ("outer", owner.owned)):
                if frame.f_locals.get("self") is peer and frame.f_code is type(peer).close.__code__:
                    calls.append(role)
    try:
        monkeypatch.setattr(timer, "singleShot", refuse)
        with pytest.raises(error_type) as caught:
            owner.release()
        assert caught.value is error
        assert owner._closing and not owner._queued and not owner._released
        assert owner in importlib.import_module("fontlabapp.fontui.batch_recipes")._HANDLES
        monkeypatch.setattr(timer, "singleShot", real)
        sys.setprofile(observe)
        assert owner.release() is False
        app.processEvents()
        assert owner._released
        assert calls == ["panel", "editor", "outer"]
        assert owner.release() is True and calls == ["panel", "editor", "outer"]
    finally:
        monkeypatch.setattr(timer, "singleShot", real)
        sys.setprofile(previous)


@pytest.fixture
def complete_geometry_inputs(rich_inputs, tmp_path):
    from copy import deepcopy
    from test_fontui_batch_containment import input_tree
    from ufoLib2 import Font
    from ufoLib2.objects import Guideline
    paths, models = [], []
    for index, original in enumerate(rich_inputs[2]):
        model = deepcopy(original)
        model.guidelines = [Guideline(17, 23, 30, "font guide")]
        model["A"].components[0].transformation = (1.5, 0.25, -0.5, 0.75, 13, -19)
        background = model.layers["owned.background"]["untouched"]
        background.height = 444
        background.unicodes = [0x41 + index]
        background.note = "owned background note"
        background.lib["owned.layer.glyph"] = [index]
        pen = background.getPen()
        pen.moveTo((-2, 3)); pen.lineTo((5, 7)); pen.lineTo((11, -13)); pen.closePath()
        background.guidelines = [Guideline(7, 9, 45, "background guide")]
        path = tmp_path / ("complete-" + str(index) + ".ufo")
        model.save(path)
        model.close()
        paths.append(path)
        models.append(Font.open(path, lazy=False))
    before = [input_tree(path) for path in paths]
    try:
        yield paths, tmp_path / "complete-output", models
    finally:
        assert [input_tree(path) for path in paths] == before
        for path, model in zip(paths, models, strict=True):
            with Font.open(path, lazy=False) as reopened:
                assert reopened == model
            model.close()


def expected_fractional_font(original):
    """Independent literal diagonal-affine oracle; no production transform call."""
    from copy import deepcopy
    import math
    expected = deepcopy(original)
    sx, sy, dx, dy = 1.125, 1.25, 1.0, -0.5
    def guide(g):
        x, y = g.x or 0, g.y or 0
        angle = g.angle if g.angle is not None else (0 if g.x is None else 90)
        radians = math.radians(angle)
        g.x, g.y = sx * x + dx, sy * y + dy
        g.angle = math.degrees(math.atan2(sy * math.sin(radians), sx * math.cos(radians))) % 360
    for layer in expected.layers:
        for glyph in layer:
            for contour in glyph.contours:
                for point in contour.points:
                    point.x, point.y = sx * point.x + dx, sy * point.y + dy
            glyph.width *= sx
            glyph.height *= sy
            for anchor in glyph.anchors:
                anchor.x, anchor.y = sx * anchor.x + dx, sy * anchor.y + dy
            for g in glyph.guidelines:
                guide(g)
            for component in glyph.components:
                a, b, c, d, e, f = component.transformation
                component.transformation = (a, sy*b/sx, sx*c/sy, d,
                    sx*e+dx-a*dx-sx*c*dy/sy, sy*f+dy-sy*b*dx/sx-d*dy)
            if glyph.image.fileName is not None:
                a, b, c, d, e, f = glyph.image.transformation
                glyph.image.transformation = (sx*a, sy*b, sx*c, sy*d, sx*e+dx, sy*f+dy)
    for g in expected.guidelines:
        guide(g)
    return expected


@pytest.mark.parametrize("selection", ["explicit", "environment"])
def test_connected_start_when_sources_added_then_complete_captured_fractional_outputs(workbench, complete_geometry_inputs, monkeypatch, selection):
    from ufoLib2 import Font
    owner, app = workbench
    paths, destination, models = complete_geometry_inputs
    qt = importlib.import_module("PythonQt")
    choices = iter(map(str, paths))
    monkeypatch.setattr(qt.QtGui.QFileDialog, "getExistingDirectory", lambda *a: next(choices))
    owner.panel.add_button.click()
    owner.panel.add_button.click()
    assert owner.panel.sources == list(map(str, paths))
    assert owner.panel.source_list.count() == 2
    owner.panel.destination_control.setText(str(destination))
    owner.editor.matrix["xx"].setText("2")
    owner.editor.matrix["yy"].setText("3")
    owner.editor.matrix["dx"].setText("8")
    owner.editor.matrix["dy"].setText("-4")
    owner.editor.intensity_field.setText("12.5")
    if selection == "explicit":
        monkeypatch.setenv("FONTLABAPP_BATCH_PYTHON", "owned-invalid-environment-interpreter")
        owner.panel.python = sys.executable
    else:
        monkeypatch.setenv("FONTLABAPP_BATCH_PYTHON", sys.executable)
        owner.panel.python = None
    captured = []
    code = type(owner.editor).recipe.__code__
    previous = sys.getprofile()
    def observe(frame, event, result):
        if event == "return" and frame.f_code is code and frame.f_locals.get("self") is owner.editor:
            captured.append(result)
    completed = []
    owner.panel.on_finish = completed.append
    try:
        sys.setprofile(observe)
        owner.panel.start_button.click()
    finally:
        sys.setprofile(previous)
    process = owner.panel.process
    assert process is not None and process.child.args[0] == sys.executable
    assert len(captured) == 1
    owner.editor.matrix["dx"].setText("999")
    owner.editor.intensity_field.setText("0")
    wait_until(app, lambda: not owner.panel.running)
    assert len(captured) == 1 and len(completed) == 1
    assert completed[0] == owner.panel.results and completed[0] is not owner.panel.results
    assert [row.ok for row in owner.panel.results] == [True, True]
    assert owner.panel.log.count() == 2 and owner.panel.progress.value() == 2
    assert owner.panel.status.text == "Finished: 2 succeeded, 0 failed."
    assert_process_released(process)
    for path, original in zip(paths, models, strict=True):
        with Font.open(destination / (path.stem + "-transformed.ufo"), lazy=False) as actual:
            expected = expected_fractional_font(original)
            # Floating-point conjugation may associate products differently.
            # Assert every independent matrix before normalizing only roundoff
            # for the exhaustive model equality that follows.
            for layer in actual.layers:
                for glyph in layer:
                    expected_glyph = expected.layers[layer.name][glyph.name]
                    assert len(glyph.components) == len(expected_glyph.components)
                    for component, expected_component in zip(glyph.components, expected_glyph.components, strict=True):
                        assert component.transformation == pytest.approx(expected_component.transformation, rel=1e-12, abs=1e-12)
                        expected_component.transformation = component.transformation
            assert actual == expected  # every layer, guide, component and metadata/resource field
            for layer in actual.layers:
                assert layer.lib == original.layers[layer.name].lib
                for glyph in layer:
                    old = original.layers[layer.name][glyph.name]
                    assert (glyph.unicodes, glyph.note, glyph.lib) == (old.unicodes, old.note, old.lib)
            assert actual.lib == original.lib and actual.info == expected.info
            assert actual.features.text == original.features.text
            assert actual.groups == original.groups and actual.kerning == original.kerning
            assert dict(actual.images) == dict(original.images) and dict(actual.data) == dict(original.data)
            expected.close()


def held_interpreter(tmp_path):
    """Pause the real child between files, ignoring TERM to observe the existing kill path."""
    import shlex
    trace = tmp_path / "hold_actual_child.py"
    trace.write_text("""import inspect, json, os, signal, sys, time
from pathlib import Path
from fontlab_fontport.batch import BatchRunner
root = Path(__file__).parent
code = BatchRunner._execute.__code__
lines, start = inspect.getsourcelines(BatchRunner._execute)
line = start + next(i for i, text in enumerate(lines) if 'if cancelled():' in text)
def observe(frame, event, arg):
    if frame.f_code is code and event == 'line' and frame.f_lineno == line and frame.f_locals['index'] == 2:
        sys.settrace(None)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        (root/'ready').write_text(json.dumps({'pid':os.getpid(), 'source':code.co_filename, 'isolated':sys.flags.isolated}))
        deadline = time.monotonic() + 60
        while not (root/'go').exists():
            if time.monotonic() >= deadline: raise TimeoutError('owned hold deadline')
            time.sleep(0.005)
    return observe
sys.settrace(observe)
body, spec = sys.argv[-2:]
sys.argv = ['-c', spec]
exec(compile(body, '<actual BatchProcess CHILD>', 'exec'), {'__name__':'__main__'})
""")
    shell = tmp_path / "held-python"
    shell.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -I " + shlex.quote(str(trace)) + ' "$@"\n')
    shell.chmod(0o755)
    return str(shell)


@pytest.mark.parametrize("action", ["cancel", "close"])
def test_two_active_windows_when_one_stops_then_other_completes_and_real_supervisor_reaps(actual_qt, rich_inputs, tmp_path, action):
    import json
    import shiboken6
    from pathlib import Path
    from fontlabapp.fontui import batch_worker
    from ufoLib2 import Font
    _, parent, app = actual_qt
    module = importlib.import_module("fontlabapp.fontui.batch_recipes")
    owners = [module.show(parent=parent, python=sys.executable) for _ in range(2)]
    barriers = [tmp_path / ("barrier" + str(index)) for index in range(2)]
    processes, completed = [], [[], []]
    try:
        for index, owner in enumerate(owners):
            barriers[index].mkdir()
            owner.panel.python = held_interpreter(barriers[index])
            owner.panel.set_sources(rich_inputs[0])
            owner.panel.destination_control.setText(str(tmp_path / ("window-output" + str(index))))
            owner.panel.on_finish = completed[index].append
            assert owner.panel.start()
            processes.append(owner.panel.process)
        wait_until(app, lambda: all((path / "ready").exists() for path in barriers))
        wait_until(app, lambda: all(len(owner.panel.results) == 1 for owner in owners))
        for path, process in zip(barriers, processes, strict=True):
            record = json.loads((path / "ready").read_text())
            assert record['pid'] == process.child.pid and record['isolated'] == 1
            assert process.child.poll() is None
        if action == "cancel":
            owners[0].panel.cancel_button.click()
            (barriers[0] / "go").touch()
        else:
            owners[0].release()
            wait_until(app, lambda: owners[0]._released)
            entry = processes[0]._supervision
            assert entry is not None and entry['accepted'] and not entry['complete']
            assert processes[0].child.poll() is None
            assert entry['grace'] == owners[0].panel.GRACE_SECONDS
            assert entry['interval'] == owners[0].panel.POLL_MS
        assert not owners[1]._closing and owners[1].panel.running
        assert processes[1].child.poll() is None
        (barriers[1] / "go").touch()
        wait_until(app, lambda: not owners[1].panel.running)
        assert len(completed[1]) == 1 and [row.ok for row in owners[1].panel.results] == [True, True]
        assert shiboken6.isValid(owners[1].panel.widget) and not owners[1].panel.closed
        for source, original in zip(rich_inputs[0], rich_inputs[2], strict=True):
            with Font.open(tmp_path / "window-output1" / (source.stem + "-transformed.ufo"), lazy=False) as reopened:
                assert reopened == original
        if action == "cancel":
            wait_until(app, lambda: not owners[0].panel.running)
            assert len(completed[0]) == 1 and len(owners[0].panel.results) == 1
        else:
            wait_until(app, lambda: entry['complete'], seconds=owners[0].panel.GRACE_SECONDS + batch_worker.KILL_SECONDS + 10)
            assert entry['terminate_ack'] and entry['kill_ack'] and entry['exited'] and entry['released'] and entry['deleted']
            assert completed[0] == []
            app.processEvents()
            assert not shiboken6.isValid(owners[0].panel.widget)
        assert not (tmp_path / "window-output0" / "B-transformed.ufo").exists()
        for process in processes:
            assert_process_released(process)
    finally:
        for path in barriers:
            if path.exists(): (path / "go").touch()
        for owner in owners:
            owner.release()
        app.processEvents()
        for process in processes:
            wait_until(app, lambda p=process: p.child.poll() is not None and not Path(p.scratch).exists())
        assert all(owner._released for owner in owners)


@pytest.mark.parametrize("role,fault", [("editor", "false"), ("editor", "exception"), ("editor", "baseexception"), ("outer", "false"), ("outer", "exception"), ("outer", "baseexception")])
def test_release_when_other_owner_boundary_refuses_then_retry_only_unacknowledged(workbench, monkeypatch, role, fault):
    owner, app = workbench
    widget = owner.editor.widget if role == "editor" else owner.owned.widget
    method = "hide" if role == "editor" else "close"
    original = getattr(widget, method)
    failure = RuntimeError("owned boundary refusal") if fault == "exception" else KeyboardInterrupt("owned boundary interruption")
    calls = []
    def refuse(*args):
        if fault == "false": return False
        raise failure
    previous = sys.getprofile()
    def observe(frame, event, result):
        if event == "call" and frame.f_code.co_name == "close":
            for label, peer in (("panel", owner.panel), ("editor", owner.editor), ("outer", owner.owned)):
                if frame.f_locals.get("self") is peer and frame.f_code is type(peer).close.__code__: calls.append(label)
    try:
        monkeypatch.setattr(widget, method, refuse)
        sys.setprofile(observe)
        owner.release()
        app.processEvents()
        assert not owner._released and owner.panel._batch_close["complete"]
        if role == "outer": assert owner.editor._close_complete
        else: assert not owner.editor._close_complete
        if fault != "false": assert any(error is failure for error in owner.problems)
        first = list(calls)
        monkeypatch.setattr(widget, method, original)
        owner.release()
        app.processEvents()
        assert owner._released and owner.editor._close_complete
        assert calls[len(first):] == (["editor", "outer"] if role == "editor" else ["outer"])
    finally:
        monkeypatch.setattr(widget, method, original)
        sys.setprofile(previous)


@pytest.mark.parametrize("error_type,cleanup_fault", [(ValueError, None), (KeyboardInterrupt, None), (ValueError, "false"), (ValueError, "exception"), (KeyboardInterrupt, "baseexception")])
def test_show_when_outer_show_fails_then_primary_and_cleanup_owners_retained(actual_qt, monkeypatch, error_type, cleanup_fault):
    qt, parent, app = actual_qt
    module = importlib.import_module("fontlabapp.fontui.batch_recipes")
    base = qt.QtGui.QDialog
    primary = error_type("owned outer show failure")
    cleanup = RuntimeError("owned outer cleanup failure") if cleanup_fault == "exception" else KeyboardInterrupt("owned outer cleanup interruption")
    failing = [True]
    class RefusingDialog(base):
        def show(self):
            raise primary
        def close(self):
            if failing[0] and cleanup_fault:
                if cleanup_fault == "false": return False
                raise cleanup
            return super().close()
    monkeypatch.setattr(qt.QtGui, "QDialog", RefusingDialog)
    before = list(module._HANDLES)
    caught = None
    try:
        module.show(parent=parent)
    except BaseException as error:
        caught = error
    assert caught is not None
    leaves = []
    def visit(error):
        if isinstance(error, BaseExceptionGroup):
            for child in error.exceptions: visit(child)
        else: leaves.append(error)
    visit(caught)
    assert any(error is primary for error in leaves)
    pending = [owner for owner in module._HANDLES if owner not in before]
    try:
        if cleanup_fault:
            assert len(pending) == 1
            owner = pending[0]
            assert owner.owned is not None and not owner._released
            if cleanup_fault != "false": assert any(error is cleanup for error in leaves)
            else: assert any(isinstance(error, RuntimeError) for error in leaves)
        else:
            app.processEvents()
            assert not pending
    finally:
        failing[0] = False
        for owner in pending: owner.release()
        app.processEvents()
        assert all(owner._released for owner in pending)
