# this_file: tests/test_fontui_lifecycle.py
"""``follow_history`` and the pure factory import (App keeps both after T13b).

Fontport's moved kerning editor reuses ``fontui.lifecycle.follow_history``.
The tests that covered it lived with the kerning editor, so they live here now.
All tests are host-free: PythonQt and ``fontlab`` are doubles.
"""

import importlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from _studio_qt import studio_qt as _studio_qt

studio_qt = _studio_qt
del _studio_qt

LIFECYCLE = "fontlabapp.fontui.lifecycle"


class Signal:
    """Minimal Qt signal double: remembers slots, emits to all of them."""

    def __init__(self) -> None:
        self.slots: list = []

    def connect(self, slot) -> None:
        self.slots.append(slot)

    def disconnect(self, slot) -> None:
        self.slots.remove(slot)

    def emit(self, *args) -> None:
        for slot in list(self.slots):
            slot(*args)


@pytest.fixture
def lifecycle(monkeypatch):
    """Import a fresh ``fontui.lifecycle`` over a PythonQt double."""
    monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock()))
    monkeypatch.delitem(sys.modules, LIFECYCLE, raising=False)
    module = importlib.import_module(LIFECYCLE)
    yield module
    sys.modules.pop(LIFECYCLE, None)


def owned(lifecycle):
    """Return a bare ``Owned`` with the state ``close`` and ``connect`` need."""
    owner = lifecycle.Owned.__new__(lifecycle.Owned)
    owner.closed, owner.connections, owner.destroying = False, [], False
    owner._closing = False
    owner._close_complete = False
    owner._child_closed = False
    owner._hidden = False
    owner._delete_scheduled = False
    owner._close_error = None
    owner._parent_dead = False
    owner._own_observer = None
    owner._parent_observer = None
    owner.widget = Mock()
    return owner


def test_follow_history_when_undo_and_redo_fire_then_callback_runs_until_close(
    lifecycle, monkeypatch
):
    actions = {
        "actionUndo": SimpleNamespace(triggered=Signal()),
        "actionRedo": SimpleNamespace(triggered=Signal()),
    }
    window = SimpleNamespace(findChild=lambda _type, name: actions.get(name))
    monkeypatch.setitem(
        sys.modules, "fontlab", SimpleNamespace(MainWindow=lambda: window)
    )
    owner, calls = owned(lifecycle), []
    attached = lifecycle.follow_history(owner, lambda: calls.append(1))
    assert attached == 2, "undo and redo must both be followed"
    actions["actionUndo"].triggered.emit(False)
    actions["actionRedo"].triggered.emit(False)
    assert calls == [1, 1], calls
    owner.close()
    actions["actionUndo"].triggered.emit(False)
    assert calls == [1, 1], "no callback after close"
    assert not actions["actionUndo"].triggered.slots, "slot must be disconnected"


def test_follow_history_when_outside_fontlab_then_returns_zero_and_connects_nothing(
    lifecycle, monkeypatch
):
    monkeypatch.setitem(sys.modules, "fontlab", None)
    owner = SimpleNamespace(connect=Mock())
    assert lifecycle.follow_history(owner, lambda: None) == 0
    owner.connect.assert_not_called()


def test_fontui_when_general_factories_imported_then_host_and_peers_stay_unloaded():
    code = (
        "import sys\n"
        "from fontlabapp.fontui import (designspace_panel, features_editor,\n"
        "    font_browser, glyph_browser, glyph_preview)\n"
        "assert 'PythonQt' not in sys.modules, 'host module loaded'\n"
        "assert 'fontlab_fontport' not in sys.modules, 'Fontport loaded'\n"
        "assert 'fontlab_glyport' not in sys.modules, 'Glyport loaded'\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr


def test_app_shell_when_closed_then_embedded_widgets_stop_following(studio_qt, monkeypatch):
    """M2: closing the shell closes embedded widgets, which drop follow_history and owned signals."""
    qt = studio_qt
    actions = {
        "actionUndo": SimpleNamespace(triggered=Signal()),
        "actionRedo": SimpleNamespace(triggered=Signal()),
    }
    window = SimpleNamespace(findChild=lambda _type, name: actions.get(name))
    monkeypatch.setitem(sys.modules, "fontlab", SimpleNamespace(MainWindow=lambda: window))
    shell = qt.modules.appshell.AppShell("Kerning Studio", preview="tmetrics")
    child = qt.modules.lifecycle.Owned(None)
    changed, calls = Signal(), []
    assert qt.modules.lifecycle.follow_history(child, lambda: calls.append(1)) == 2
    child.connect(changed, lambda *a: calls.append(2))
    shell.set_preview(child)
    actions["actionUndo"].triggered.emit(False)
    changed.emit()
    assert calls == [1, 2]
    shell.close()
    actions["actionRedo"].triggered.emit(False)
    changed.emit()
    assert calls == [1, 2] and child.closed
    assert not actions["actionUndo"].triggered.slots and not changed.slots



def _lifecycle_origin_bytes(path):
    """Read an exact regular origin without following any symlink component."""
    import os
    import stat
    from pathlib import Path

    assert path.is_absolute() and path == Path(os.path.abspath(path)), "lifecycle-origin: noncanonical path"
    for parent in path.parents:
        assert stat.S_ISDIR(parent.lstat().st_mode), "lifecycle-origin: linked or missing parent"
    assert stat.S_ISREG(path.lstat().st_mode), "lifecycle-origin: nonregular file"
    return path.read_bytes()


def _assert_lifecycle_origin(module):
    """Bind lifecycle to current source or the controller-approved reader record."""
    import hashlib
    import json
    import os
    from pathlib import Path

    approved_hash = "3aba977d29e639bfece85bd334c44d96dd063c9f108e3853b62e3545de11aaf8"
    record_path = os.environ.get("FONTLABAPP_READER_ORIGIN_RECORD")
    record_hash = os.environ.get("FONTLABAPP_READER_ORIGIN_SHA256")
    if record_path is None:
        assert record_hash is None, "lifecycle-origin: record hash without record"
        root = Path(os.path.abspath(__file__)).parents[1] / "src" / "fontlabapp"
    else:
        assert record_path and record_hash, "lifecycle-origin: controller record/hash required"
        raw = _lifecycle_origin_bytes(Path(record_path))
        assert hashlib.sha256(raw).hexdigest() == record_hash, "lifecycle-origin: unapproved record"
        record = json.loads(raw)
        assert type(record) is dict and set(record) == {
            "prefix", "package_root", "worker_file", "worker_sha256"
        }, "lifecycle-origin: reader record fields differ"
        assert all(type(value) is str and value for value in record.values()), "lifecycle-origin: reader record values"
        prefix, root = Path(record["prefix"]), Path(record["package_root"])
        assert prefix.is_absolute() and str(prefix) == sys.prefix, "lifecycle-origin: interpreter prefix differs"
        assert root == prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "fontlabapp", "lifecycle-origin: package root differs"
        worker = root / "fontui" / "batch_worker.py"
        assert record["worker_file"] == str(worker), "lifecycle-origin: worker path differs"
        assert record["worker_sha256"] == "55eee9192350e076d80c45f86633e733672674802cd0df3c902925c0536d654e", "lifecycle-origin: worker hash differs"
        assert hashlib.sha256(_lifecycle_origin_bytes(worker)).hexdigest() == record["worker_sha256"], "lifecycle-origin: worker bytes differ"
    expected = root / "fontui" / "lifecycle.py"
    assert hashlib.sha256(_lifecycle_origin_bytes(expected)).hexdigest() == approved_hash, "lifecycle-origin: lifecycle bytes differ"
    assert module.__name__ == LIFECYCLE and module.__package__ == "fontlabapp.fontui", "lifecycle-origin: module name/package differs"
    assert module.__spec__ is not None, "lifecycle-origin: missing spec"
    assert module.__spec__.name == LIFECYCLE and module.__spec__.parent == module.__package__, "lifecycle-origin: spec name/package differs"
    assert module.__spec__.origin == module.__file__ == str(expected), "lifecycle-origin: spec/file differs"
    assert list(sys.modules["fontlabapp"].__path__) == [str(root)], "lifecycle-origin: package path differs"
    assert list(sys.modules["fontlabapp.fontui"].__path__) == [str(root / "fontui")], "lifecycle-origin: fontui path differs"
    assert module.Owned.close.__code__.co_filename == str(expected), "lifecycle-origin: close code differs"


def test_owned_when_partial_disconnect_fails_then_successes_stay_drained(monkeypatch):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        _assert_lifecycle_origin(module)
        parent = handle.qt.QtGui.QWidget()
        owner = module.Owned(parent)
        observers = tuple(owner.connections)
        signal_a, signal_b = fq.Signal(), fq.Signal()
        owner.connect(signal_a, lambda: None)
        owner.connect(signal_b, lambda: None)
        pair_a, = (pair for pair in owner.connections if pair[0] is signal_a)
        pair_b, = (pair for pair in owner.connections if pair[0] is signal_b)
        normal_disconnect_a = signal_a.disconnect
        failure = RuntimeError("controlled disconnect A failure before acknowledgement")
        failing = True
        attempts, acknowledgements = [], []

        def disconnect_a(callback):
            attempts.append(callback)
            if failing:
                raise failure
            result = normal_disconnect_a(callback)
            acknowledgements.append((callback, result))
            return result

        monkeypatch.setattr(signal_a, "disconnect", disconnect_a)
        with pytest.raises(RuntimeError) as caught:
            owner.close()
        assert caught.value is failure, "retain the exact disconnect failure"
        assert owner.closed, "close fences new work before disconnecting"
        assert not any(pair is pair_b for pair in owner.connections), (
            "acknowledged B pair must be removed before A's disconnect failure"
        )
        assert any(pair is pair_a for pair in owner.connections), (
            "failed A pair must remain available for retry"
        )
        assert all(
            any(pair is observer for pair in owner.connections)
            for observer in observers
        ), "unattempted actual constructor observers remain by identity"
        assert len(owner.connections) == len(observers) + 1
        assert signal_b.slots == [], "B was actually disconnected"
        assert acknowledgements == []

        failing = False
        owner.close()
        assert len(attempts) == 2 and all(
            callback is pair_a[1] for callback in attempts
        ), "retry A once using the actual registered callback"
        assert len(acknowledgements) == 1
        assert acknowledgements[0][0] is pair_a[1]
        assert acknowledgements[0][1] is None, "None acknowledges disconnection"
        assert signal_a.slots == signal_b.slots == []
        assert owner.connections == [], "completed close retires every actual record"
        assert not owner.widget.shown and owner.widget.deleted
        # The house signal raises if an already-drained callback is replayed.
        owner.close()
        assert len(attempts) == 2 and len(acknowledgements) == 1
        assert not owner.widget.shown and owner.widget.deleted
    finally:
        fq.release()



@pytest.mark.parametrize(
    "operation,kind",
    [("hide", "error"), ("hide", "false"), ("deleteLater", "error"), ("deleteLater", "false")],
    ids=["hide-error", "hide-false", "delete-error", "delete-false"],
)
def test_owned_when_widget_stage_fails_then_retry_finishes(monkeypatch, operation, kind):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        owner = module.Owned(handle.qt.QtGui.QWidget())
        observers = tuple(owner.connections)
        work = fq.Signal()
        owner.connect(work, lambda: None)
        work_pair, = (pair for pair in owner.connections if pair[0] is work)
        initial = (owner.widget.shown, owner.widget.deleted, tuple(owner.connections))
        normal_hide, normal_delete = owner.widget.hide, owner.widget.deleteLater
        error = RuntimeError("controlled widget stage failure")
        fault = True
        attempts, acknowledgements = [], []

        def stage(name, normal):
            def call():
                attempts.append(name)
                if fault and name == operation:
                    if kind == "error":
                        raise error
                    return False
                answer = normal()
                if answer is not False:
                    acknowledgements.append((name, answer))
                return answer
            return call

        monkeypatch.setattr(owner.widget, "hide", stage("hide", normal_hide))
        monkeypatch.setattr(owner.widget, "deleteLater", stage("deleteLater", normal_delete))
        captured = None
        try:
            owner.close()
        except BaseException as caught:
            captured = caught
        failure_state = (
            owner.closed, owner.widget.shown, owner.widget.deleted,
            tuple(owner.connections), tuple(attempts), tuple(acknowledgements),
        )
        if kind == "error":
            assert captured is error, "retain the exact widget-stage exception"
        else:
            assert isinstance(captured, RuntimeError), "singletonFalse widget result must refuse"
        assert owner.closed, "the actual failed close fences work"
        assert initial[0] is True and initial[1] is False
        assert not any(pair is work_pair for pair in failure_state[3])
        assert work.slots == [], "ordinary work was actually disconnected before widget stages"

        fault = False
        owner.close()
        restored_state = (owner.widget.shown, owner.widget.deleted)
        assert restored_state == (False, True), "retry must complete the unfinished widget stage"
        assert {id(pair) for pair in failure_state[3]} == {id(pair) for pair in observers}
        assert owner.connections == []
        assert acknowledgements == [("hide", None), ("deleteLater", None)]
        expected = ["hide", "hide", "deleteLater"] if operation == "hide" else ["hide", "deleteLater", "deleteLater"]
        assert attempts == expected, "retry only unfinished stages, without replaying successful hide"
        owner.close()
        assert attempts == expected and acknowledgements == [("hide", None), ("deleteLater", None)]
        assert (owner.widget.shown, owner.widget.deleted) == restored_state
    finally:
        fq.release()



@pytest.mark.parametrize("_case", [None], ids=["singleton-false"])
def test_owned_when_connect_returns_false_then_refused_without_record(monkeypatch, _case):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        owner = module.Owned(handle.qt.QtGui.QWidget())
        original_records = tuple(owner.connections)
        signal, entries = fq.Signal(), []

        def refuse(callback):
            entries.append(callback)
            return False

        monkeypatch.setattr(signal, "connect", refuse)
        captured = None
        try:
            owner.connect(signal, lambda: None)
        except BaseException as caught:
            captured = caught
        assert isinstance(captured, RuntimeError), "singletonFalse sender connection must refuse"
        assert len(entries) == 1 and signal.slots == []
        assert [id(pair) for pair in owner.connections] == [id(pair) for pair in original_records]
    finally:
        fq.release()


@pytest.mark.parametrize("_case", [None], ids=["actual-close-before-connect"])
def test_owned_when_closed_then_connect_refused_before_sender_entry(monkeypatch, _case):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        owner = module.Owned(handle.qt.QtGui.QWidget())
        owner.close()
        assert owner.closed and not owner.widget.shown and owner.widget.deleted
        original_records = tuple(owner.connections)
        signal, entries = fq.Signal(), []
        normal_connect = signal.connect

        def connect(callback):
            entries.append(callback)
            return normal_connect(callback)

        monkeypatch.setattr(signal, "connect", connect)
        captured = None
        try:
            owner.connect(signal, lambda: None)
        except BaseException as caught:
            captured = caught
        assert isinstance(captured, RuntimeError), "actual closed owner must reject ordinary connect"
        assert entries == [] and signal.slots == [], "refuse before entering the sender"
        assert [id(pair) for pair in owner.connections] == [id(pair) for pair in original_records]
    finally:
        fq.release()


@pytest.mark.parametrize("_case", [None], ids=["failed-disconnect-late-work"])
def test_owned_when_close_fails_then_late_connected_and_saved_work_stays_fenced(monkeypatch, _case):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        owner = module.Owned(handle.qt.QtGui.QWidget())
        signal, seen = fq.Signal(), []

        def callback(value, *, marker=None):
            seen.append((value, marker))

        owner.connect(signal, callback)
        pair, = (pair for pair in owner.connections if pair[0] is signal)
        saved = pair[1]
        assert signal.slots[0] is saved
        token, marker = object(), object()
        signal.emit(token)
        assert len(seen) == 1 and seen[0][0] is token and seen[0][1] is None
        error = RuntimeError("controlled disconnect before acknowledgement")

        def fail_disconnect(registered):
            assert registered is saved
            raise error

        monkeypatch.setattr(signal, "disconnect", fail_disconnect)
        captured = None
        try:
            owner.close()
        except BaseException as caught:
            captured = caught
        assert captured is error and owner.closed, "actual close failure establishes the work fence"
        before = list(seen)
        signal.emit(token)
        saved(token, marker=marker)
        assert seen == before, "connected and saved ordinary work must stay fenced after failed close"
        assert signal.slots[0] is saved
        assert any(record is pair for record in owner.connections)
    finally:
        fq.release()


@pytest.mark.parametrize("_case", [None], ids=["direct-reentry"])
def test_owned_when_disconnect_reenters_close_then_nested_call_refuses(monkeypatch, _case):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        owner = module.Owned(handle.qt.QtGui.QWidget())
        signal = fq.Signal()
        owner.connect(signal, lambda: None)
        pair, = (record for record in owner.connections if record[0] is signal)
        normal_disconnect = signal.disconnect
        nested, attempts, acknowledgements, snapshots = [], [], [], []

        def disconnect(registered):
            attempts.append(registered)
            before = tuple(id(record) for record in owner.connections)
            inner_error, inner_result = None, None
            try:
                inner_result = owner.close()
            except BaseException as caught:
                inner_error = caught
            nested.append((inner_error, inner_result))
            snapshots.append((before, tuple(id(record) for record in owner.connections)))
            answer = normal_disconnect(registered)
            acknowledgements.append((registered, answer))
            return answer

        monkeypatch.setattr(signal, "disconnect", disconnect)
        outer_error = None
        try:
            owner.close()
        except BaseException as caught:
            outer_error = caught
        assert outer_error is None, "handled inner refusal must not become an outer cleanup error"
        inner_error, inner_result = nested[0]
        assert isinstance(inner_error, RuntimeError), "direct in-progress close reentry must refuse"
        assert len(nested) == 1 and inner_result is None
        assert len(attempts) == 1 and attempts[0] is pair[1]
        assert len(acknowledgements) == 1 and acknowledgements[0][0] is pair[1]
        assert acknowledgements[0][1] is None and snapshots[0][0] == snapshots[0][1]
        assert signal.slots == [] and owner.connections == []
        assert owner.closed and not owner.widget.shown and owner.widget.deleted
    finally:
        fq.release()


@pytest.mark.parametrize("_case", [None], ids=["none-and-argument-identities"])
def test_owned_when_connect_acknowledges_none_then_registered_slot_preserves_arguments(monkeypatch, _case):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        owner = module.Owned(handle.qt.QtGui.QWidget())
        signal, answers, seen = fq.Signal(), [], []
        normal_connect = signal.connect

        def connect(registered):
            answer = normal_connect(registered)
            answers.append(answer)
            return answer

        def callback(value, *, marker=None):
            seen.append((value, marker))

        monkeypatch.setattr(signal, "connect", connect)
        owner.connect(signal, callback)
        pair, = (record for record in owner.connections if record[0] is signal)
        saved = pair[1]
        assert answers == [None] and len(signal.slots) == 1
        assert signal.slots[0] is saved, "retain the actual registered callable, including any wrapper"
        token, marker = object(), object()
        signal.emit(token)
        saved(token, marker=marker)
        assert len(seen) == 2 and all(value is token for value, _ in seen)
        assert seen[0][1] is None and seen[1][1] is marker
        owner.close()
        assert signal.slots == [] and not any(record is pair for record in owner.connections)
        assert owner.closed and not owner.widget.shown and owner.widget.deleted
    finally:
        fq.release()



@pytest.mark.parametrize("entry", ["close-event", "own-destroyed", "parent-destroyed"])
def test_owned_when_qt_entry_disconnect_fails_then_contains_exact_error(monkeypatch, entry):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        parent = handle.qt.QtGui.QWidget()
        owner = module.Owned(parent)
        root = owner.widget
        close_event = root.closeEvent
        own_pair, = (pair for pair in owner.connections if pair[0] is root.destroyed)
        parent_pair, = (pair for pair in owner.connections if pair[0] is parent.destroyed)
        foreign = fq.Signal()
        owner.connect(foreign, lambda: None)
        foreign_pair, = (pair for pair in owner.connections if pair[0] is foreign)
        error = RuntimeError("controlled ordinary disconnect at Qt entry")
        actions = []
        event = SimpleNamespace(accept=lambda: actions.append("accept"), ignore=lambda: actions.append("ignore"))

        def fail_disconnect(callback):
            assert callback is foreign_pair[1]
            raise error

        monkeypatch.setattr(foreign, "disconnect", fail_disconnect)
        captured = None
        try:
            if entry == "close-event":
                close_event(event)
            else:
                (own_pair if entry == "own-destroyed" else parent_pair)[1]()
        except BaseException as caught:
            captured = caught
        assert captured is None, "Qt entry must contain the actual teardown error"
        if entry == "close-event":
            assert actions == ["ignore"], "failed close event is ignored, never accepted"
        assert owner.closed
        assert any(pair is foreign_pair for pair in owner.connections)
        assert owner._close_error is error, "retain the exact failure after containment is proved"
    finally:
        fq.release()


@pytest.mark.parametrize("which", ["own", "parent"])
def test_owned_when_destroyed_during_disconnect_then_observer_does_not_reenter(monkeypatch, which):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        entries = []
        delivering = [False]

        class EntryOwned(module.Owned):
            def close(self):
                entries.append("observer" if delivering[0] else "outer")
                return super().close()

        parent = handle.qt.QtGui.QWidget()
        owner = EntryOwned(parent)
        sender = owner.widget.destroyed if which == "own" else parent.destroyed
        observer, = (pair for pair in owner.connections if pair[0] is sender)
        ordinary = fq.Signal()
        owner.connect(ordinary, lambda: None)
        ordinary_pair, = (pair for pair in owner.connections if pair[0] is ordinary)
        normal_disconnect = ordinary.disconnect
        observer_errors, frames, acknowledgements = [], [], []

        def disconnect(callback):
            before = tuple(id(pair) for pair in owner.connections)
            captured = None
            delivering[0] = True
            try:
                observer[1]()
            except BaseException as caught:
                captured = caught
            finally:
                delivering[0] = False
            observer_errors.append(captured)
            frames.append((before, tuple(id(pair) for pair in owner.connections)))
            answer = normal_disconnect(callback)
            if answer is not False:
                acknowledgements.append((callback, answer))
            return answer

        monkeypatch.setattr(ordinary, "disconnect", disconnect)
        outer_error = None
        try:
            owner.close()
        except BaseException as caught:
            outer_error = caught
        assert outer_error is None and observer_errors == [None]
        assert entries == ["outer"], "active destruction observer must not dispatch a nested close override"
        assert len(frames) == 1 and frames[0][0] == frames[0][1]
        assert len(acknowledgements) == 1 and acknowledgements[0] == (ordinary_pair[1], None)
        assert owner.closed and owner.connections == []
    finally:
        fq.release()


@pytest.mark.parametrize("which", ["own", "parent"])
def test_owned_when_destroyed_then_only_own_witness_waives_root_widget_stages(monkeypatch, which):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        parent = handle.qt.QtGui.QWidget()
        owner = module.Owned(parent)
        root = owner.widget
        sender = root.destroyed if which == "own" else parent.destroyed
        observer, = (pair for pair in owner.connections if pair[0] is sender)
        methods = [("hide", root.hide), ("deleteLater", root.deleteLater)]
        attempts, acknowledgements = [], []

        def delegate(name, normal):
            def call():
                attempts.append(name)
                assert which != "own", "no widget stage call after supported own destruction witness"
                answer = normal()
                if answer is not False:
                    acknowledgements.append((name, answer))
                return answer
            return call

        for name, normal in methods:
            monkeypatch.setattr(root, name, delegate(name, normal))
        captured = None
        try:
            observer[1]()
        except BaseException as caught:
            captured = caught
        assert captured is None
        assert owner.closed and owner.destroying is (which == "own")
        expected = [] if which == "own" else ["hide", "deleteLater"]
        assert attempts == expected
        assert acknowledgements == [(name, None) for name in expected]
        # Inspect local counters, never Root properties after an own witness.
    finally:
        fq.release()


@pytest.mark.parametrize("which", ["own", "parent"])
def test_owned_when_external_disconnect_fails_then_death_observer_retains_unknown_pair(monkeypatch, which):
    import _cov_qt as fq

    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        parent = handle.qt.QtGui.QWidget()
        owner = module.Owned(parent)
        sender = owner.widget.destroyed if which == "own" else parent.destroyed
        observer, = (pair for pair in owner.connections if pair[0] is sender)
        external = fq.Signal()
        owner.connect(external, lambda: None)
        external_pair, = (pair for pair in owner.connections if pair[0] is external)
        error = RuntimeError("external sender refused before acknowledgement")

        def refuse(callback):
            assert callback is external_pair[1]
            raise error

        monkeypatch.setattr(external, "disconnect", refuse)
        captured = None
        try:
            owner.close()
        except BaseException as caught:
            captured = caught
        assert captured is error and owner.closed
        before = tuple(id(pair) for pair in owner.connections)
        observer_error = None
        try:
            observer[1]()
        except BaseException as caught:
            observer_error = caught
        assert observer_error is None
        assert tuple(id(pair) for pair in owner.connections) == before
        assert any(pair is external_pair for pair in owner.connections)
        assert external.slots[0] is external_pair[1]
        assert captured is error, "RuntimeError is retained as data, never interpreted as sender death"
    finally:
        fq.release()



@pytest.mark.parametrize("case", ['false-then-none'])
def test_owned_when_disconnect_returns_false_then_record_retained_until_actual_ack(monkeypatch, case):
    import _cov_qt as fq
    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        owner = module.Owned(handle.qt.QtGui.QWidget())
        bad, good = fq.Signal(), fq.Signal()
        owner.connect(bad, lambda: None)
        owner.connect(good, lambda: None)
        bad_pair, = (p for p in owner.connections if p[0] is bad)
        good_pair, = (p for p in owner.connections if p[0] is good)
        real_bad, real_good = bad.disconnect, good.disconnect
        refused = [True]
        bad_attempts, good_acks, bad_acks = [], [], []
        def disconnect_bad(slot):
            bad_attempts.append(slot)
            if refused[0]:
                return False
            answer = real_bad(slot)
            bad_acks.append((slot, answer))
            return answer
        def disconnect_good(slot):
            answer = real_good(slot)
            good_acks.append((slot, answer))
            return answer
        monkeypatch.setattr(bad, "disconnect", disconnect_bad)
        monkeypatch.setattr(good, "disconnect", disconnect_good)
        captured = None
        try:
            owner.close()
        except BaseException as caught:
            captured = caught
        assert isinstance(captured, RuntimeError) and owner._close_error is captured
        assert owner.closed and not owner._close_complete
        assert any(p is bad_pair for p in owner.connections)
        assert not any(p is good_pair for p in owner.connections)
        assert good_acks == [(good_pair[1], None)] and bad_acks == []
        refused[0] = False
        owner.close()
        owner.close()
        assert owner._close_complete and owner.connections == [] and owner._close_error is None
        assert bad_attempts == [bad_pair[1], bad_pair[1]]
        assert bad_acks == [(bad_pair[1], None)] and good_acks == [(good_pair[1], None)]
    finally:
        fq.release()



@pytest.mark.parametrize("case", ['own-hide-pre-ack', 'own-hide-post-ack', 'own-deleteLater-pre-ack', 'own-deleteLater-post-ack', 'parent-hide-pre-ack', 'parent-hide-post-ack', 'parent-deleteLater-pre-ack', 'parent-deleteLater-post-ack'])
def test_owned_when_death_during_widget_stage_then_exact_witness_controls_remaining_work(monkeypatch, case):
    import _cov_qt as fq
    which, selected, timing = case.split("-", 2)
    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        parent = handle.qt.QtGui.QWidget()
        owner = module.Owned(parent)
        root = owner.widget
        observer, = (p for p in owner.connections if p[0] is (root.destroyed if which == "own" else parent.destroyed))
        methods = [("hide", root.hide), ("deleteLater", root.deleteLater)]
        delivered = [False]
        attempts, acknowledgements, frames = [], [], []
        def observe():
            before = tuple(id(p) for p in owner.connections)
            observer[1]()
            delivered[0] = True
            frames.append((before, tuple(id(p) for p in owner.connections)))
        def delegate(name, normal):
            def call():
                assert not (which == "own" and delivered[0]), "no following Root call after own witness"
                attempts.append(name)
                if name == selected and timing == "pre-ack":
                    observe()
                    # Boundary models destruction inside this in-flight Qt call.
                    # An own-dead Root must not be called again by the double.
                    answer = None if which == "own" else normal()
                else:
                    answer = normal()
                if answer is not False:
                    acknowledgements.append((name, answer))
                if name == selected and timing == "post-ack":
                    observe()
                return answer
            return call
        for name, normal in methods:
            monkeypatch.setattr(root, name, delegate(name, normal))
        owner.close()
        assert delivered[0] and len(frames) == 1 and frames[0][0] == frames[0][1]
        assert owner._close_complete and owner.connections == []
        assert owner.destroying is (which == "own") and owner._parent_dead is (which == "parent")
        expected = ["hide"] if which == "own" and selected == "hide" else ["hide", "deleteLater"]
        assert attempts == expected and acknowledgements == [(n, None) for n in expected]
        assert owner._hidden and owner._delete_scheduled is (len(expected) == 2)
        owner.close()
        assert attempts == expected
    finally:
        fq.release()



@pytest.mark.parametrize("case", ['own', 'parent'])
def test_owned_when_dead_observer_is_retired_then_native_disconnect_is_not_replayed(monkeypatch, case):
    import _cov_qt as fq
    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        parent = handle.qt.QtGui.QWidget()
        owner = module.Owned(parent)
        root = owner.widget
        dead_signal = root.destroyed if case == "own" else parent.destroyed
        dead_pair, = (p for p in owner.connections if p[0] is dead_signal)
        live_pair, = (p for p in owner.connections if p is not dead_pair)
        real_hide, real_live = root.hide, live_pair[0].disconnect
        error = RuntimeError("pause widget cleanup before observer retirement")
        def pause():
            raise error
        monkeypatch.setattr(root, "hide", pause)
        captured = None
        try:
            owner.close()
        except BaseException as caught:
            captured = caught
        assert captured is error and not owner._close_complete
        before = tuple(id(p) for p in owner.connections)
        dead_pair[1]()
        assert tuple(id(p) for p in owner.connections) == before
        dead_calls, live_acks = [], []
        def forbidden(slot):
            dead_calls.append(slot)
            raise AssertionError("no native disconnect of witnessed-dead observer")
        def disconnect_live(slot):
            answer = real_live(slot)
            live_acks.append((slot, answer))
            return answer
        monkeypatch.setattr(dead_signal, "disconnect", forbidden)
        monkeypatch.setattr(live_pair[0], "disconnect", disconnect_live)
        monkeypatch.setattr(root, "hide", real_hide)
        owner.close()
        owner.close()
        assert owner._close_complete and owner.connections == [] and dead_calls == []
        assert live_acks == [(live_pair[1], None)]
    finally:
        fq.release()



@pytest.mark.parametrize("case", ['own-error', 'own-false', 'parent-error', 'parent-false'])
def test_owned_when_observer_dies_during_disconnect_then_exact_failure_waits_for_safe_retry(monkeypatch, case):
    import _cov_qt as fq
    which, kind = case.split("-", 1)
    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        parent = handle.qt.QtGui.QWidget()
        owner = module.Owned(parent)
        root = owner.widget
        signal = root.destroyed if which == "own" else parent.destroyed
        pair, = (p for p in owner.connections if p[0] is signal)
        other, = (p for p in owner.connections if p is not pair)
        real_other = other[0].disconnect
        attempts, other_acks, frames = [], [], []
        error = RuntimeError("observer died during refused disconnect")
        def disconnect(slot):
            attempts.append(slot)
            before = tuple(id(p) for p in owner.connections)
            pair[1]()
            frames.append((before, tuple(id(p) for p in owner.connections)))
            if kind == "error":
                raise error
            return False
        def disconnect_other(slot):
            answer = real_other(slot)
            other_acks.append((slot, answer))
            return answer
        monkeypatch.setattr(signal, "disconnect", disconnect)
        monkeypatch.setattr(other[0], "disconnect", disconnect_other)
        captured = None
        try:
            owner.close()
        except BaseException as caught:
            captured = caught
        assert isinstance(captured, RuntimeError)
        if kind == "error":
            assert captured is error
        assert owner._close_error is captured and not owner._close_complete
        assert any(p is pair for p in owner.connections) and frames[0][0] == frames[0][1]
        owner.close()
        owner.close()
        assert attempts == [pair[1]], "retry retires only the known dead observer without native replay"
        assert other_acks == [(other[1], None)]
        assert owner._close_complete and owner.connections == []
    finally:
        fq.release()



@pytest.mark.parametrize("case", ['false', 'error'])
def test_owned_when_live_external_refuses_after_own_death_then_pair_stays_pending(monkeypatch, case):
    import _cov_qt as fq
    handle = fq.install(monkeypatch)
    try:
        module = handle.load(LIFECYCLE)
        owner = module.Owned(handle.qt.QtGui.QWidget())
        own_pair = owner._own_observer
        external = fq.Signal()
        owner.connect(external, lambda: None)
        pair, = (p for p in owner.connections if p[0] is external)
        normal = external.disconnect
        refused = [True]
        error = RuntimeError("live external refusal remains live")
        attempts, acknowledgements = [], []
        def disconnect(slot):
            attempts.append(slot)
            if refused[0]:
                if case == "error":
                    raise error
                return False
            answer = normal(slot)
            acknowledgements.append((slot, answer))
            return answer
        monkeypatch.setattr(external, "disconnect", disconnect)
        for attempt in range(2):
            captured = None
            try:
                owner.close()
            except BaseException as caught:
                captured = caught
            assert isinstance(captured, RuntimeError) and owner._close_error is captured
            if case == "error":
                assert captured is error
            assert not owner._close_complete and any(p is pair for p in owner.connections)
            if attempt == 0:
                before = tuple(id(p) for p in owner.connections)
                own_pair[1]()
                assert tuple(id(p) for p in owner.connections) == before
        refused[0] = False
        owner.close()
        assert owner._close_complete and owner.connections == []
        assert len(attempts) == 3 and acknowledgements == [(pair[1], None)]
    finally:
        fq.release()
