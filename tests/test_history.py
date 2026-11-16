# this_file: tests/test_history.py
"""One-Undo commit helper and per-operation auto-layer refusals (issue 122, T14b).

The fakes record every native call in one log, so the tests check the exact
protocol order: init history, mutate, stamp, ONE notify(layers + created +
glyphs), stamp, read-back. They do not prove native FontLab behaviour.
"""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__

STAMP = "2026-10-21T12:00:00Z"


class Item:
    """A FontLab layer or glyph double that logs history calls."""

    def __init__(self, log, name, *, auto=False, fail_init=False, fail_stamp=False):
        self.log, self.name, self.autoLayer = log, name, auto
        self.fail_init, self.fail_stamp = fail_init, fail_stamp
        self._modified = None

    def checkInitHistoryState(self, flag):
        if self.fail_init:
            raise OSError("init refused")
        self.log.append(("init", self.name, flag))

    @property
    def lastModified(self):
        return self._modified

    @lastModified.setter
    def lastModified(self, value):
        if self.fail_stamp:
            raise OSError("stamp refused")
        self._modified = value
        self.log.append(("stamp", self.name, value))


class Native:
    """The ``fontlab`` module double: flItems().notifyChangesApplied and the queue."""

    def __init__(self, log, *, pending=(), fail_notify=False):
        self.log, self.pending, self.fail_notify = log, list(pending), fail_notify
        self.flGlyph = NS(updatedFgGlyphs=lambda: tuple(self.pending))

    def flItems(self):
        return self

    def notifyChangesApplied(self, title, items, *flags):
        if self.fail_notify:
            raise OSError("notify refused")
        # Two-argument calls log 3 fields; the deep flag adds a 4th field.
        self.log.append(("notify", title, [i.name for i in items], *flags))


def records(*rows):
    """Dependency records (name, auto, component bases), as guides.dependency_values gives."""
    return tuple(rows)


PLAIN = history.auto_facts(records(("A", False, ()), ("B", False, ())))


def setup(**native):
    log = []
    layers = [Item(log, "A/Regular"), Item(log, "B/Regular")]
    glyphs = [Item(log, "A"), Item(log, "B")]
    return log, layers, glyphs, Native(log, **native)


def run(layers, glyphs, mutate, native, **kw):
    kw.setdefault("operation", "geometry")
    kw.setdefault("facts", PLAIN)
    return history.commit("Edit", layers, glyphs, mutate, native=native, stamp=STAMP, **kw)


# ---------------------------------------------------------------- facts and refusals
def test_auto_facts_when_base_name_is_not_str_then_normalised_with_str():
    class Name:
        def __str__(self):
            return "acute"

    facts = history.auto_facts(records(("Aacute", True, (Name(),))))
    assert facts.users == {"acute": frozenset({"Aacute"})}
    assert facts.dependants("acute") == ("Aacute",)


def test_auto_facts_when_records_read_then_auto_owners_and_component_users():
    facts = history.auto_facts(
        records(("A", False, ()), ("Aacute", True, ("A", "acute")), ("Aacute", False, ()))
    )
    assert facts.autos == frozenset({"Aacute"})
    assert facts.users == {"A": frozenset({"Aacute"}), "acute": frozenset({"Aacute"})}


def test_dependants_when_chain_through_manual_composite_then_auto_end_found():
    facts = history.auto_facts(
        records(("e", False, ()), ("ebar", False, ("e",)), ("ebaracute", True, ("ebar",)))
    )
    assert facts.dependants("e") == ("ebaracute",)
    assert facts.dependants("ebar") == ("ebaracute",)
    assert facts.dependants("ebaracute") == ()


def test_dependants_when_components_are_circular_then_walk_ends():
    facts = history.auto_facts(records(("a", True, ("b",)), ("b", False, ("a",))))
    assert facts.dependants("b") == ("a",)
    assert facts.dependants("a") == (), "a glyph never depends on itself"


@pytest.mark.parametrize("operation", ["rename", "unicode", "geometry"])
def test_refusal_when_structural_operation_then_auto_owner_and_base_refused(operation):
    facts = history.auto_facts(
        records(("A", False, ()), ("Aacute", True, ("A",)), ("B", False, ()))
    )
    assert history.refusal(facts, "Aacute", operation) == "has auto layers"
    assert history.refusal(facts, "A", operation) == "base of auto Aacute"
    assert history.refusal(facts, "B", operation) == ""


def test_refusal_when_metadata_then_only_auto_owner_refused():
    facts = history.auto_facts(records(("A", False, ()), ("Aacute", True, ("A",))))
    assert history.refusal(facts, "Aacute", "metadata") == "has auto layers"
    assert history.refusal(facts, "A", "metadata") == ""


def test_refusal_when_bases_allowed_then_base_passes_but_auto_owner_still_refused():
    facts = history.auto_facts(records(("A", False, ()), ("Aacute", True, ("A",))))
    assert history.refusal(facts, "A", "geometry", allow_bases=True) == ""
    assert history.refusal(facts, "Aacute", "geometry", allow_bases=True) == "has auto layers"


def test_refusal_when_many_dependants_then_two_named_and_ellipsis():
    facts = history.auto_facts(
        records(("A", False, ()), ("Ac", True, ("A",)), ("Ab", True, ("A",)), ("Aa", True, ("A",)))
    )
    assert history.refusal(facts, "A", "rename") == "base of auto Aa, Ab…"


def test_refusal_when_unknown_operation_then_value_error():
    with pytest.raises(ValueError, match="Unknown operation 'move'"):
        history.refusal(PLAIN, "A", "move")


def test_refusals_when_names_given_then_only_refused_names_with_reason():
    facts = history.auto_facts(records(("A", False, ()), ("Aacute", True, ("A",)), ("B", False, ())))
    assert history.refusals(facts, ["A", "B", "Aacute"], "metadata") == {"Aacute": "has auto layers"}


def test_scan_auto_facts_when_package_given_then_guides_records_used(monkeypatch):
    import fontlabapp.guides.inspect.model as guides  # noqa: PLR0402

    seen = []
    monkeypatch.setattr(
        guides, "dependency_values", lambda p: seen.append(p) or (("x", True, ("y",)),)
    )
    facts = history.scan_auto_facts("PACKAGE")
    assert seen == ["PACKAGE"] and facts.autos == frozenset({"x"})
    assert facts.dependants("y") == ("x",)


# ---------------------------------------------------------------- commit protocol
def test_commit_when_success_then_init_mutate_stamp_one_notify_stamp_read_back():
    log, layers, glyphs, native = setup()
    result = run(
        layers,
        glyphs,
        lambda: log.append(("mutate",)),
        native,
        read_back=lambda: log.append(("read_back",)) or ["A: off by 1"],
    )
    assert log == [
        ("init", "A/Regular", 0),
        ("init", "B/Regular", 0),
        ("init", "A", 0),
        ("init", "B", 0),
        ("mutate",),
        ("stamp", "A", STAMP),
        ("stamp", "B", STAMP),
        ("notify", "Edit", ["A/Regular", "B/Regular", "A", "B"]),
        ("stamp", "A", STAMP),
        ("stamp", "B", STAMP),
        ("read_back",),
    ]
    assert result == history.Committed(created=(), mismatches=("A: off by 1",))


def test_commit_when_mutate_creates_layers_then_created_between_layers_and_glyphs():
    log, layers, glyphs, native = setup()
    new = Item(log, "A/Regular copy")
    result = run(layers, glyphs, lambda: [new], native)
    notify = [e for e in log if e[0] == "notify"]
    assert notify == [("notify", "Edit", ["A/Regular", "B/Regular", "A/Regular copy", "A", "B"])]
    assert result.created == (new,) and result.mismatches == ()


def test_commit_when_declared_layer_is_auto_then_refused_before_any_history():
    log, layers, glyphs, native = setup()
    layers.append(Item(log, "C/Regular", auto=True))
    with pytest.raises(ValueError, match="auto layer C/Regular"):
        run(layers, glyphs, lambda: log.append(("mutate",)), native)
    assert log == [], "nothing initialised, mutated or notified"


@pytest.mark.parametrize(
    ("operation", "refused"),
    [("rename", True), ("unicode", True), ("geometry", True), ("metadata", False)],
)
def test_commit_when_glyph_is_base_of_auto_then_refused_per_operation(operation, refused):
    log, layers, glyphs, native = setup()
    facts = history.auto_facts(records(("A", False, ()), ("B", False, ()), ("Aacute", True, ("A",))))
    mutate = lambda: log.append(("mutate",))
    if refused:
        with pytest.raises(ValueError, match="A: base of auto Aacute"):
            run(layers, glyphs, mutate, native, operation=operation, facts=facts)
        assert log == []
    else:
        run(layers, glyphs, mutate, native, operation=operation, facts=facts)
        assert ("mutate",) in log


@pytest.mark.parametrize("operation", ["rename", "unicode", "geometry", "metadata"])
def test_commit_when_glyph_owns_auto_layer_then_refused_for_every_operation(operation):
    log, layers, glyphs, native = setup()
    facts = history.auto_facts(records(("A", True, ()), ("B", False, ())))
    with pytest.raises(ValueError, match="A: has auto layers"):
        run(layers, glyphs, lambda: None, native, operation=operation, facts=facts)
    assert log == []


def test_commit_when_bases_allowed_then_base_of_auto_written():
    log, layers, glyphs, native = setup()
    facts = history.auto_facts(records(("A", False, ()), ("B", False, ()), ("Aacute", True, ("A",))))
    run(layers, glyphs, lambda: log.append(("mutate",)), native, facts=facts, allow_bases=True)
    assert ("mutate",) in log and log[-1] == ("stamp", "B", STAMP)


def test_commit_when_updates_pending_then_refused_and_queue_untouched():
    log, layers, glyphs, native = setup(pending=[3])
    with pytest.raises(ValueError, match="pending"):
        run(layers, glyphs, lambda: None, native, settled=True)
    assert log == [] and native.pending == [3]


def test_commit_when_default_then_pending_queue_disclosed_without_clearing(capsys):
    log, layers, glyphs, native = setup(pending=[3])
    result = run(layers, glyphs, lambda: log.append(("mutate",)), native)
    assert ("mutate",) in log
    assert result.pending_updates == (3,) and native.pending == [3]
    import fontlabapp.core.edit_guards as guards
    guards.disclose(result)
    output = capsys.readouterr().out
    assert result["pending_note"] in output and "8537" in output


def test_commit_when_window_given_then_unicode_guards_run_first(monkeypatch):
    log, layers, glyphs, native = setup()
    import fontlabapp.core.edit_guards as guards

    monkeypatch.setattr(guards, "require_selection_window", lambda pid: log.append(("window", pid)))
    monkeypatch.setattr(guards, "require_no_editors", lambda **kw: log.append(("editors", kw.get("action"))))
    run(layers, glyphs, lambda: None, native, operation="unicode", window=12)
    assert log[:3] == [("window", 12), ("editors", "writing to the font"), ("init", "A/Regular", 0)]


def test_commit_when_window_guard_refuses_then_nothing_written(monkeypatch):
    log, layers, glyphs, native = setup()
    import fontlabapp.core.edit_guards as guards

    def refuse(pid):
        raise ValueError("Activate the Font window before selecting glyphs.")

    monkeypatch.setattr(guards, "require_selection_window", refuse)
    with pytest.raises(ValueError, match="Activate the Font window"):
        run(layers, glyphs, lambda: None, native, operation="unicode", window=12)
    assert log == []


def test_commit_when_mutate_fails_partway_then_finalised_and_runtime_error_names_undo():
    log, layers, glyphs, native = setup()

    def mutate():
        log.append(("mutate", "A"))
        raise OSError("setter refused")

    with pytest.raises(history.PartialWriteError) as info:
        run(layers, glyphs, mutate, native, read_back=lambda: log.append(("read_back",)) or [])
    error = info.value
    assert isinstance(error, RuntimeError)
    assert "Native changes may remain; use Edit > Undo" in str(error)
    assert "setter refused" in str(error) and isinstance(error.__cause__, OSError)
    assert [e[0] for e in log] == ["init"] * 4 + ["mutate", "stamp", "stamp", "notify", "stamp", "stamp"]
    assert ("read_back",) not in log, "no read-back after a failed write"
    assert len(error.errors) == 1


def test_commit_when_init_fails_on_later_item_then_partial_write_error_before_mutate():
    log = []
    layers = [Item(log, "A/Regular"), Item(log, "B/Regular", fail_init=True)]
    glyphs = [Item(log, "A")]
    native = Native(log)
    with pytest.raises(history.PartialWriteError) as info:
        run(layers, glyphs, lambda: log.append(("mutate",)), native)
    error = info.value
    assert history.UNDO_HINT in str(error), "the recovery text is part of the contract"
    assert isinstance(error.__cause__, OSError) and "init refused" in str(error)
    assert [str(e) for e in error.errors] == ["init refused"]
    assert log == [("init", "A/Regular", 0)], "item 1 was initialised, nothing after the failure"


def test_commit_when_notify_and_stamp_fail_then_every_error_collected():
    log = []
    layers = [Item(log, "A/Regular")]
    glyphs = [Item(log, "A", fail_stamp=True)]
    native = Native(log, fail_notify=True)
    with pytest.raises(history.PartialWriteError) as info:
        run(layers, glyphs, lambda: None, native)
    texts = [str(e) for e in info.value.errors]
    assert texts == ["stamp refused", "notify refused", "stamp refused"], texts


def test_commit_when_created_layer_is_auto_then_left_out_of_notify_and_error():
    log, layers, glyphs, native = setup()
    created = [Item(log, "A/new"), Item(log, "A/auto", auto=True)]
    with pytest.raises(history.PartialWriteError, match="Native changes may remain; use Edit > Undo"):
        run(layers, glyphs, lambda: created, native)
    notify = [e for e in log if e[0] == "notify"]
    assert notify == [("notify", "Edit", ["A/Regular", "B/Regular", "A/new", "A", "B"])]


def test_commit_when_read_back_raises_then_partial_write_error():
    log, layers, glyphs, native = setup()

    def read_back():
        raise OSError("unreadable")

    with pytest.raises(history.PartialWriteError, match="unreadable"):
        run(layers, glyphs, lambda: None, native, read_back=read_back)
    assert any(e[0] == "notify" for e in log)


def test_commit_when_unknown_operation_then_value_error_before_history():
    log, layers, glyphs, native = setup()
    with pytest.raises(ValueError, match="Unknown operation"):
        run(layers, glyphs, lambda: None, native, operation="paint")
    assert log == []


def test_commit_when_no_stamp_given_then_one_utc_stamp_from_pythonqt(monkeypatch):
    log, layers, glyphs, native = setup()
    made = []
    clock = NS(currentDateTimeUtc=lambda: made.append(1) or "UTC")
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=NS(QDateTime=clock)))
    history.commit("Edit", layers, glyphs, lambda: None, operation="metadata", facts=PLAIN, native=native)
    assert made == [1], "one shared stamp"
    assert {e[2] for e in log if e[0] == "stamp"} == {"UTC"}


def test_commit_when_no_native_given_then_fontlab_module_used(monkeypatch):
    log, layers, glyphs, native = setup()
    monkeypatch.setitem(sys.modules, "fontlab", native)
    history.commit("Edit", layers, glyphs, lambda: None, operation="metadata", facts=PLAIN, stamp=STAMP)
    assert [e for e in log if e[0] == "notify"]


# ---------------------------------------------------------------- retained history objects (T14e)
def retained(log):
    """The (shape, shapeData, builder) doubles of one removed component."""
    return [Item(log, "shape"), Item(log, "data"), Item(log, "builder")]


def test_commit_when_retain_given_then_retained_first_and_deep_flag_true():
    log, layers, glyphs, native = setup()
    new = Item(log, "A/Regular copy")
    result = run(layers, glyphs, lambda: log.append(("mutate",)) or [new], native, retain=retained(log))
    assert log == [
        ("init", "A/Regular", 0),
        ("init", "B/Regular", 0),
        ("init", "A", 0),
        ("init", "B", 0),
        ("mutate",),
        ("stamp", "A", STAMP),
        ("stamp", "B", STAMP),
        (
            "notify",
            "Edit",
            ["shape", "data", "builder", "A/Regular", "B/Regular", "A/Regular copy", "A", "B"],
            True,
        ),
        ("stamp", "A", STAMP),
        ("stamp", "B", STAMP),
    ], "retained objects get no history init; one deep notify, retained first"
    assert result.created == (new,), "retained objects are not reported as created"


@pytest.mark.parametrize("retain", [(), []])
def test_commit_when_retain_empty_then_two_argument_notify_as_before(retain):
    log, layers, glyphs, native = setup()
    run(layers, glyphs, lambda: None, native, retain=retain)
    notify = [e for e in log if e[0] == "notify"]
    assert notify == [("notify", "Edit", ["A/Regular", "B/Regular", "A", "B"])], (
        "no deep flag and no extra objects without retained objects"
    )


def test_commit_when_retained_object_is_auto_then_refused_before_any_history():
    log, layers, glyphs, native = setup()
    retain = [Item(log, "shape"), Item(log, "A/auto", auto=True)]
    with pytest.raises(ValueError, match="auto layer A/auto is in the edit list"):
        run(layers, glyphs, lambda: log.append(("mutate",)), native, retain=retain)
    assert log == [], "nothing initialised, mutated or notified"


def test_commit_when_retained_object_has_no_auto_attribute_then_accepted():
    log, layers, glyphs, native = setup()
    plain = NS(name="builder")  # a native builder has no autoLayer property
    run(layers, glyphs, lambda: None, native, retain=[plain])
    notify = [e for e in log if e[0] == "notify"]
    assert notify == [("notify", "Edit", ["builder", "A/Regular", "B/Regular", "A", "B"], True)]


def test_commit_when_retain_and_mutate_fails_partway_then_deep_notify_and_undo_hint():
    log, layers, glyphs, native = setup()

    def mutate():
        log.append(("mutate", "remove"))
        raise OSError("insertShape refused")

    with pytest.raises(history.PartialWriteError) as info:
        run(layers, glyphs, mutate, native, retain=retained(log))
    error = info.value
    assert history.UNDO_HINT in str(error) and "insertShape refused" in str(error)
    assert isinstance(error.__cause__, OSError)
    notify = [e for e in log if e[0] == "notify"]
    assert notify == [
        ("notify", "Edit", ["shape", "data", "builder", "A/Regular", "B/Regular", "A", "B"], True)
    ], "the partial edit still reaches Undo with the retained objects"


def test_commit_when_retain_and_notify_fails_then_partial_write_error():
    log, layers, glyphs, native = setup(fail_notify=True)
    with pytest.raises(history.PartialWriteError, match="notify refused"):
        run(layers, glyphs, lambda: None, native, retain=retained(log))


def test_component_history_when_component_then_shape_data_builder_triple():
    builder = object()
    data = NS(builder=builder)
    shape = NS(isComponent=True, shapeData=data)
    assert history.component_history(shape) == (shape, data, builder)


def test_component_history_when_not_component_then_empty():
    shape = NS(isComponent=False, shapeData=NS(builder=object()))
    assert history.component_history(shape) == ()


def test_component_history_when_component_has_no_shape_data_then_value_error():
    with pytest.raises(ValueError, match="no shape data"):
        history.component_history(NS(isComponent=True, shapeData=None))


def test_component_history_when_retained_then_reaches_notify_first():
    log, layers, glyphs, native = setup()
    data = Item(log, "data")
    data.builder = Item(log, "builder")
    shape = Item(log, "shape")
    shape.isComponent, shape.shapeData = True, data
    run(layers, glyphs, lambda: None, native, retain=history.component_history(shape))
    notify = [e for e in log if e[0] == "notify"]
    assert notify[0][2][:3] == ["shape", "data", "builder"] and notify[0][3] is True


def test_history_when_cold_imported_then_only_stdlib_and_no_guides():
    import fontlabapp

    package_root = str(Path(fontlabapp.__file__).resolve().parent.parent)
    script = """
import importlib.abc
import sys

class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root not in ('fontlabapp', 'org') and root not in sys.stdlib_module_names:
            raise AssertionError('Non-stdlib import: ' + fullname)

sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.core.history.glyphs
lazy = {'fontlabapp.guides.inspect.model', 'fontlabapp.core.scripting', 'fontlabapp.masters.inspect.model'}
assert not lazy & set(sys.modules), lazy & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, package_root],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("ids", [(), (3, 7)])
def test_commit_reads_queue_once_before_mutation_and_returns_named_disclosure(ids):
    log, layers, glyphs, native = setup(pending=ids)
    reads = []
    native.flGlyph.updatedFgGlyphs = lambda: reads.append(tuple(native.pending)) or tuple(native.pending)
    def mutate():
        assert reads == [ids], "Queue snapshot must precede mutation and occur only once"
        native.pending.append(99)
    result = run(layers, glyphs, mutate, native)
    assert result["pending_updates"] == ids and result.pending_updates == ids
    assert reads == [ids] and native.pending == [*ids, 99]
    assert bool(result["pending_note"]) == bool(ids)
    if ids:
        assert "8537" in result["pending_note"] and "2 glyphs" in result["pending_note"]
