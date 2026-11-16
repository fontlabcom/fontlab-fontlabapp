# this_file: tests/test_font_history.py
"""commit_masters: guards, route-A call order, rollback and disclosure (offline)."""

import threading
from importlib import import_module

import pytest
from master_doubles import FakePackage, native

font_history = import_module("fontlabapp.core.history.masters")
edit_guards = import_module("fontlabapp.core.edit_guards")
history = import_module("fontlabapp.core.history.glyphs")


@pytest.fixture
def guards(monkeypatch):
    calls = []
    monkeypatch.setattr(edit_guards, "require_selection_window", calls.append)
    return calls


def ascender_edit(package, value, *, verify=None, write=None):
    """A MasterEdit that writes ascender_value on the selected master."""

    def read():
        return package.ascender_value

    def store(v):
        package.ascender_value = v

    return font_history.MasterEdit(
        read,
        write or (lambda: store(value)),
        read,
        verify or (lambda found: [] if found == value else [f"ascender {found}"]),
        store,
    )


def test_commit_masters_when_two_masters_then_one_notify_after_master_restore(guards):
    p = FakePackage()
    module = native(p, queue=(5, 7))
    edits = {"Bold": ascender_edit(p, 780.0), "Regular": ascender_edit(p, 760.0)}
    result = font_history.commit_masters(p, "Edit", edits, native=module)
    assert result.values == {"Regular": 760.0, "Bold": 780.0}, f"read-back values in font order: {result}"
    assert list(result.values) == ["Regular", "Bold"], "values must follow font master order"
    assert result["pending_updates"] == (5, 7), "queued ids must be disclosed, not cleared"
    assert "8537" in result["pending_note"], f"pending note expected: {result.pending_note!r}"
    assert result[0] is result.values, "tuple indexing must keep working"
    assert guards == [7], f"the Font-window guard must get the package id: {guards}"
    notifies = [e for e in p.log if e[0] == "notify"]
    assert notifies == [("notify", "Edit", (p, p.container), False)], f"exactly one route-A notify: {notifies}"
    assert p.log.index(("init", "package", 0)) < p.log.index(("setMaster", "Regular", False)), "init before writes"
    assert p.log[-2] == ("setMaster", "Regular", False), f"original master restored before notify: {p.log}"
    assert ("init", "container", 0) in p.log, "the masters container must be initialised"
    assert p.log.count("mastersContainer") == 1, "one container handle for init and notify"
    assert p.master == "Regular", "the starting master must stay current"
    assert p.data["Bold"]["ascender_value"] == 780.0 and p.data["Regular"]["ascender_value"] == 760.0, "both masters must hold their values"


def test_commit_masters_when_queue_empty_then_note_empty(guards):
    p = FakePackage(current="Bold")
    result = font_history.commit_masters(p, "Edit", {"Bold": ascender_edit(p, 1.0)}, native=native(p))
    assert result.pending_updates == () and result.pending_note == "", f"no queue, no note: {result}"
    assert p.master == "Bold", "the original master Bold must be restored"


@pytest.mark.parametrize(
    "title,edits,match",
    [("", {"Bold": None}, "title"), ("T", {}, "No master"), ("T", {"Black": None}, "Unknown"), ("T", {"Bold": 1}, "MasterEdit")],
)
def test_commit_masters_when_request_bad_then_refuses_before_history(guards, title, edits, match):
    p = FakePackage()
    with pytest.raises(ValueError, match=match):
        font_history.commit_masters(p, title, edits, native=native(p))
    assert p.log == [], f"no native call may happen before a refusal: {p.log}"


def test_commit_masters_when_masters_duplicate_then_refuses(guards):
    p = FakePackage()
    object.__setattr__(p, "data", {**p.data})
    p.__class__ = type("Dup", (FakePackage,), {"masters": property(lambda self: ["Bold", "Bold"])})
    with pytest.raises(ValueError, match="duplicate"):
        font_history.commit_masters(p, "T", {"Bold": ascender_edit(p, 1.0)}, native=native(p))


def test_commit_masters_when_off_gui_thread_then_refuses(guards):
    p = FakePackage()
    caught = []

    def run():
        try:
            font_history.commit_masters(p, "T", {"Bold": ascender_edit(p, 1.0)}, native=native(p))
        except ValueError as error:
            caught.append(error)

    worker = threading.Thread(target=run)
    worker.start()
    worker.join()
    assert caught and str(caught[0]) == font_history.THREAD_TEXT, f"off-thread refusal expected: {caught}"
    assert guards == [] and p.log == [], "nothing may run off the GUI thread"


def test_require_font_window_when_selection_guard_refuses_then_no_write(monkeypatch):
    def refuse(package_id):
        raise ValueError("Activate the Font window before selecting glyphs.")

    monkeypatch.setattr(edit_guards, "require_selection_window", refuse)
    p = FakePackage()
    with pytest.raises(ValueError, match="Font window"):
        font_history.commit_masters(p, "T", {"Bold": ascender_edit(p, 1.0)}, native=native(p))
    assert p.log == [], f"refusal must come before history: {p.log}"


@pytest.mark.parametrize("canvas", ["shown", "unreadable"])
def test_require_font_window_when_glyph_canvas_active_then_refuses(guards, monkeypatch, canvas):
    def glyphs(module):
        if canvas == "unreadable":
            raise RuntimeError("canvas")
        return frozenset({(7, "A")})

    monkeypatch.setattr(edit_guards, "canvas_glyphs", glyphs)
    p = FakePackage()
    with pytest.raises(ValueError, match="Font window"):
        font_history.commit_masters(p, "T", {"Bold": ascender_edit(p, 1.0)}, native=native(p))
    assert p.log == [], f"Glyph-window refusal must come before history: {p.log}"


def test_commit_masters_when_second_write_fails_then_restores_all_and_notifies_nothing(guards):
    p = FakePackage()
    before = {m: p.data[m]["ascender_value"] for m in p.data}

    def partial():
        p.ascender_value = 780.0
        raise OSError("boom")

    edits = {"Regular": ascender_edit(p, 760.0), "Bold": ascender_edit(p, 780.0, write=partial)}
    with pytest.raises(font_history.RolledBackError) as caught:
        font_history.commit_masters(p, "Edit", edits, native=native(p))
    assert isinstance(caught.value, ValueError), "a restored failure is a refusal"
    assert "boom" in str(caught.value) and font_history.RESTORED_TEXT in str(caught.value), str(caught.value)
    assert "Undo" not in str(caught.value).replace("nothing was added to Undo", ""), "no Undo advice"
    assert {m: p.data[m]["ascender_value"] for m in p.data} == before, "every master must be restored"
    assert not [e for e in p.log if e[0] == "notify"], f"no notify after a rollback: {p.log}"
    assert p.master == "Regular", "the original master must be selected again"


def test_commit_masters_when_read_back_differs_then_rolls_back_with_not_stored(guards):
    p = FakePackage()
    original = p.data["Bold"]["ascender_value"]
    edits = {"Bold": ascender_edit(p, 780.0, verify=lambda found: ["ascender rounded"])}
    with pytest.raises(font_history.RolledBackError, match=history.NOT_STORED) as caught:
        font_history.commit_masters(p, "Edit", edits, native=native(p))
    assert "ascender rounded" in str(caught.value), f"the mismatch text must be shown: {caught.value}"
    assert p.data["Bold"]["ascender_value"] == original, "a read-back gap must restore the value"
    assert not [e for e in p.log if e[0] == "notify"], "no notify after a read-back gap"


def test_commit_masters_when_restore_does_not_hold_then_unrestored_error(guards):
    p = FakePackage()
    p.fail[("store", "ascender_value")] = 999.0
    with pytest.raises(font_history.UnrestoredError) as caught:
        font_history.commit_masters(p, "Edit", {"Bold": ascender_edit(p, 780.0)}, native=native(p))
    text = str(caught.value)
    assert "not restored" in text and font_history.UNRESTORED_HINT in text, text
    assert "Edit > Undo" not in text, "no Undo advice without an Undo step"
    assert isinstance(caught.value, history.PartialWriteError), "callers catching PartialWriteError see it"
    assert len(caught.value.errors) == 2, f"failure and restore problem: {caught.value.errors}"


def test_commit_masters_when_master_switch_ignored_then_rolls_back(guards):
    p = FakePackage()
    p.fail[("stuck", "Bold")] = True
    with pytest.raises(font_history.RolledBackError, match="did not select"):
        font_history.commit_masters(p, "Edit", {"Bold": ascender_edit(p, 780.0)}, native=native(p))
    assert p.data["Bold"]["ascender_value"] != 780.0, "nothing may be written on the wrong master"


def test_commit_masters_when_restore_raises_and_original_unselectable_then_unrestored(guards):
    p = FakePackage()

    def bad_restore(saved):
        raise OSError("restore")

    edit = font_history.MasterEdit(lambda: 1, lambda: None, lambda: 1, lambda v: ["x"], bad_restore)
    p.fail[("stuck", "Regular")] = True
    with pytest.raises(font_history.UnrestoredError) as caught:
        font_history.commit_masters(p, "Edit", {"Bold": edit}, native=native(p))
    assert len(caught.value.errors) == 3, f"failure, restore and master problems: {caught.value.errors}"


def test_commit_masters_when_init_fails_then_rolled_back_without_writes(guards):
    p = FakePackage()
    p.fail["init-package"] = RuntimeError()
    with pytest.raises(font_history.RolledBackError, match="RuntimeError"):
        font_history.commit_masters(p, "Edit", {"Bold": ascender_edit(p, 780.0)}, native=native(p))
    assert not [e for e in p.log if isinstance(e, str) and e.startswith("set-")], "no write after init failed"


def test_commit_masters_when_notify_fails_then_unrestored_error_and_values_stay(guards):
    p = FakePackage()
    p.fail["notify"] = RuntimeError("notify")
    with pytest.raises(font_history.UnrestoredError, match="notify"):
        font_history.commit_masters(p, "Edit", {"Bold": ascender_edit(p, 780.0)}, native=native(p))
    assert p.data["Bold"]["ascender_value"] == 780.0, "after a failed notify the value is not touched again"


def test_commit_masters_when_write_interrupted_then_master_restored_and_interrupt_reraised(guards):
    p = FakePackage()
    before = {m: p.data[m]["ascender_value"] for m in p.data}

    def interrupted():
        p.ascender_value = 780.0
        raise KeyboardInterrupt

    edits = {"Regular": ascender_edit(p, 760.0), "Bold": ascender_edit(p, 780.0, write=interrupted)}
    with pytest.raises(KeyboardInterrupt):
        font_history.commit_masters(p, "Edit", edits, native=native(p))
    assert p.master == "Regular", "the original master must be restored after an interrupt"
    assert {m: p.data[m]["ascender_value"] for m in p.data} == before, "written values must be rolled back"
    assert not [e for e in p.log if e[0] == "notify"], "no notify after an interrupt"


def test_commit_masters_when_container_init_fails_then_rolled_back(guards):
    p = FakePackage()
    p.fail["init-container"] = RuntimeError("container")
    with pytest.raises(font_history.RolledBackError, match="container"):
        font_history.commit_masters(p, "Edit", {"Bold": ascender_edit(p, 780.0)}, native=native(p))
    assert not [e for e in p.log if isinstance(e, str) and e.startswith("set-")], "no write after the init failed"


def test_commit_masters_when_restored_text_given_then_rollback_text_uses_it(guards):
    p = FakePackage()
    edit = ascender_edit(p, 780.0, verify=lambda found: ["gap"])
    with pytest.raises(font_history.RolledBackError) as caught:
        font_history.commit_masters(p, "Edit", {"Bold": edit}, native=native(p), restored_text="Guides re-created.")
    assert str(caught.value).endswith("Guides re-created."), f"caller text expected: {caught.value}"


def test_require_font_window_when_selection_guard_refuses_then_master_text():
    p = FakePackage()
    import fontlabapp.core.edit_guards as guards

    original = guards.require_selection_window

    def refuse(package_id):
        raise ValueError("Activate the Font window before selecting glyphs.")

    guards.require_selection_window = refuse
    try:
        with pytest.raises(ValueError) as caught:
            font_history.require_font_window(p, native(p))
    finally:
        guards.require_selection_window = original
    assert str(caught.value) == font_history.WINDOW_TEXT, f"master writes need their own text: {caught.value}"
    assert "selecting glyphs" in str(caught.value.__cause__), "the selection text stays for selection writers"
