# this_file: tests/test_zone_native.py
"""zone_native: the Backend callbacks through the whole dialog sequence (offline)."""

from importlib import import_module

import re

import pytest
from master_doubles import FakePackage, native, other_guides, zone_guides

zone_native = import_module("fontlabapp.metrics.zones.native")
zone_editor = import_module("fontlabapp.metrics.zones.editor")
font_history = import_module("fontlabapp.core.history.masters")
edit_guards = import_module("fontlabapp.core.edit_guards")
Editor = import_module("fontlabapp.metrics.zones.model").Editor


@pytest.fixture
def host(monkeypatch):
    p = FakePackage()
    module = native(p)
    state = {"package": p}
    monkeypatch.setattr(edit_guards, "require_selection_window", lambda package_id: None)
    monkeypatch.setattr(zone_native, "_native", lambda name: module)
    monkeypatch.setattr(font_history, "_native", lambda name: module)
    monkeypatch.setattr(
        zone_native,
        "current_package",
        lambda expected=None: state["package"] if expected in (None, 7) else None,
    )
    return p


def rows(snapshot, master):
    return Editor(snapshot).rows(master)


def test_capture_when_two_masters_then_plain_zones_and_master_restored(host):
    snapshot = zone_native.capture()
    assert snapshot.package_id == 7 and snapshot.current_master == "Regular", snapshot
    assert [m.name for m in snapshot.masters] == ["Regular", "Bold"], "font master order"
    assert rows(snapshot, "Regular") == (("Top", 500, 15, "x"), ("Bottom", 0, 15, "base")), "positive widths"
    bold = snapshot.masters[1]
    assert (bold.x_height, bold.caps_height) == (251.0, 1.0), f"metrics from *_value: {bold}"
    assert host.log[-1] == ("setMaster", "Regular", False), f"start master restored: {host.log}"
    assert not [e for e in host.log if e in ("convert", "update-zones")], "capture writes nothing"


def test_capture_when_no_font_or_bad_masters_then_refuses(host, monkeypatch):
    monkeypatch.setattr(zone_native, "current_package", lambda expected=None: None)
    with pytest.raises(ValueError, match="Open the font"):
        zone_native.capture()
    host.__class__ = type("Dup", (type(host),), {"masters": property(lambda self: ["Bold", "Bold"])})
    monkeypatch.setattr(zone_native, "current_package", lambda expected=None: host)
    with pytest.raises(ValueError, match="Unreadable font masters"):
        zone_native.capture()


def test_capture_when_switch_ignored_or_deadline_passed_then_no_snapshot(host, monkeypatch):
    host.fail[("stuck", "Bold")] = True
    with pytest.raises(ValueError, match="did not select"):
        zone_native.capture()
    assert host.master == "Regular", "the start master must be restored after a failure"
    host.fail.clear()
    monkeypatch.setattr(zone_native, "CAPTURE_SECONDS", -1.0)
    with pytest.raises(TimeoutError):
        zone_native.capture()


def test_check_when_capture_times_out_then_stale_text(host, monkeypatch):
    snapshot = zone_native.capture()
    monkeypatch.setattr(zone_native, "CAPTURE_SECONDS", -1.0)
    with pytest.raises(ValueError, match=re.escape(zone_native.STALE_TEXT)):
        zone_native.check(snapshot)
    assert host.master == "Regular", "the start master must be restored after a timeout"


def test_capture_when_native_zone_unreadable_then_refuses(host):
    host.data["Bold"]["cache"][0].append(host.data["Bold"]["cache"][0][0])
    with pytest.raises(ValueError, match="Unreadable native Top zone 'x'"):
        zone_native.capture()


def test_backend_when_dialog_sequence_then_one_undo_and_verified_baseline(host):
    backend = zone_native.backend()
    snapshot = backend.capture()
    backend.check(snapshot)
    editor = Editor(snapshot)
    origins = editor.origins("Bold")
    editor = editor.stage(
        "Bold",
        (("Top", 520, 18, "x"), ("Top", 700, 12, "caps"), ("Bottom", -10, 10, "base")),
        origins=(origins[1], origins[0], None),
    )
    changes = editor.plan()
    host.log.clear()
    after = backend.apply(snapshot, changes)
    zone_editor.check_result(snapshot, changes, after)
    assert Editor(after).pending() == (), "the returned baseline has no staged change"
    backend.check(after)
    notifies = [e for e in host.log if e[0] == "notify"]
    assert notifies == [("notify", zone_native.TITLE, (host, host.container), False)], notifies
    assert rows(after, "Bold") == (("Top", 700, 12, "caps"), ("Top", 520, 18, "x"), ("Bottom", -10, 10, "base")), "new baseline"
    guides = zone_guides(host, "Bold")
    assert (-10.0, -10.0, "base", "", False) in guides, f"bottom zone stored with negative extension: {guides}"
    assert after.masters[0] == snapshot.masters[0], "an unchanged master keeps its values"
    second = Editor(after).stage("Bold", (("Top", 530, 18, "x2"),), origins=(Editor(after).origins("Bold")[1],))
    final = backend.apply(after, second.plan())
    zone_editor.check_result(after, second.plan(), final)
    backend.check(final)
    assert rows(final, "Bold") == (("Top", 530, 18, "x2"),), "a second Apply on the returned baseline works"


def test_apply_when_retained_zone_edited_then_native_copy_keeps_tags_and_lock(host):
    snapshot = zone_native.capture()
    editor = Editor(snapshot)
    editor = editor.stage("Regular", (("Top", 500, 15, "x"), ("Bottom", -5, 20, "base")), origins=editor.origins("Regular"))
    zone_native.apply(snapshot, editor.plan())
    stored = [g for g in zone_guides(host, "Regular") if g[2] == "base"]
    assert stored == [(-5.0, -20.0, "base", "t1", True)], f"tags and lock of the source zone stay: {stored}"


def test_apply_when_no_change_then_returns_before_without_native_calls(host):
    snapshot = zone_native.capture()
    host.log.clear()
    assert zone_native.apply(snapshot, ()) is snapshot, "a no-op plan returns the same baseline"
    assert host.log == [], f"no native call for an empty plan: {host.log}"


@pytest.mark.parametrize(
    "table,match",
    [
        ((("Top", 520, 18, ""),), "Name every zone"),
        ((("Top", 520, 18, "a"), ("Top", 530, 18, "a")), "repeat"),
        ((("Bottom", 600, 0, "top6"),), "other kind"),
    ],
)
def test_apply_when_row_not_storable_then_refuses_before_history(host, table, match):
    snapshot = zone_native.capture()
    editor = Editor(snapshot).stage("Bold", table, origins=(None,) * len(table))
    host.log.clear()
    with pytest.raises(ValueError, match=match):
        zone_native.apply(snapshot, editor.plan())
    assert host.log == [], f"refusal before any native call: {host.log}"


def test_apply_when_plan_foreign_or_font_changed_then_refuses(host):
    snapshot = zone_native.capture()
    editor = Editor(snapshot).stage("Bold", (("Top", 520, 18, "x"),), origins=(None,))
    change = editor.plan()[0]
    stale = type(change)(change.master, type(change.before)(), change.after)
    with pytest.raises(ValueError, match="not from this snapshot"):
        zone_native.apply(snapshot, (stale,))
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        zone_native.apply(snapshot, (change, change))
    host.data["Bold"]["xHeight_value"] = 1.0
    with pytest.raises(ValueError, match="changed; reopen"):
        zone_native.apply(snapshot, (change,))


def test_check_when_font_closed_then_stale(host, monkeypatch):
    snapshot = zone_native.capture()
    monkeypatch.setattr(zone_native, "current_package", lambda expected=None: None)
    with pytest.raises(ValueError, match="changed; reopen"):
        zone_native.check(snapshot)
    with pytest.raises(ValueError, match="changed; reopen"):
        zone_native.bounds(snapshot, "Bold")


def test_apply_when_font_closes_after_check_then_stale(host, monkeypatch):
    snapshot = zone_native.capture()
    editor = Editor(snapshot).stage("Bold", (("Top", 520, 18, "x"),), origins=(None,))
    monkeypatch.setattr(zone_native, "check", lambda snap: None)
    monkeypatch.setattr(zone_native, "current_package", lambda expected=None: None)
    with pytest.raises(ValueError, match="changed; reopen"):
        zone_native.apply(snapshot, editor.plan())


def test_apply_when_native_renames_zone_then_rolled_back(host, monkeypatch):
    snapshot = zone_native.capture()
    editor = Editor(snapshot).stage("Bold", (("Top", 0, 0, "T"),), origins=(None,))
    before = zone_guides(host, "Bold")
    ids = [g[0] for g in host.data["Bold"]["guides"] if g[1]]
    others = other_guides(host, "Bold")
    real = host.updateZonesFromGuidelines

    def rename():
        real()
        cache = host.data[host.master]["cache"]
        for zone in cache[0]:
            zone.name = zone.name + ".9" if zone.name == "T" else zone.name

    monkeypatch.setattr(host, "updateZonesFromGuidelines", rename)
    with pytest.raises(font_history.RolledBackError, match="FontLab did not store") as caught:
        zone_native.apply(snapshot, editor.plan())
    assert zone_native.RESTORED_TEXT in str(caught.value), f"the text must say guides were re-created: {caught.value}"
    assert zone_guides(host, "Bold") == before, "the source zone values must be restored"
    assert [g[0] for g in host.data["Bold"]["guides"] if g[1]] != ids, "the restore re-creates zone guide ids"
    assert other_guides(host, "Bold") == others, "non-zone guides keep their ids and values"


def test_bounds_when_layers_missing_flat_or_present_then_extents(host):
    host.data["Regular"]["boxes"] = {"o": (-12.0, 524.0), "O": None}
    snapshot = zone_native.capture()
    assert zone_native.bounds(snapshot, "Regular") == ((-12.0, 512.0), None), "o extent, O missing layer"
    host.data["Regular"]["boxes"] = {"O": (0.0, 0.0)}
    assert zone_native.bounds(snapshot, "Regular") == (None, None), "no o glyph; flat O"


def test_backend_when_title_given_then_one_undo_step_named_title(host):
    """Vertical Metrics & Zones passes its own label; the default stays ``TITLE``."""
    assert zone_native.backend().apply is zone_native.apply, "the default backend is unchanged"
    backend = zone_native.backend(title="Vertical Metrics: set zones of Bold")
    snapshot = backend.capture()
    host.log.clear()
    backend.apply(snapshot, plan_bold(snapshot))
    notifies = [e for e in host.log if e[0] == "notify"]
    assert notifies == [("notify", "Vertical Metrics: set zones of Bold", (host, host.container), False)], notifies


@pytest.mark.parametrize("drift", ["other-master", "current-master"])
def test_apply_when_font_differs_after_commit_then_not_stored_error(host, monkeypatch, drift):
    snapshot = zone_native.capture()
    editor = Editor(snapshot).stage("Bold", (("Top", 520, 18, "x"),), origins=(None,))
    real = font_history.commit_masters

    def commit(*args, **kwargs):
        result = real(*args, **kwargs)
        if drift == "other-master":
            host.data["Regular"]["xHeight_value"] = 1.0
        else:
            object.__setattr__(host, "_master", "Bold")
        return result

    monkeypatch.setattr(zone_native, "commit_masters", commit)
    with pytest.raises(RuntimeError, match="FontLab did not store 1 change") as caught:
        zone_native.apply(snapshot, editor.plan())
    expected = "zones of master Regular" if drift == "other-master" else "the font or its current master"
    assert expected in str(caught.value), f"the read-back must name {expected!r}: {caught.value}"
    assert "Undo" not in str(caught.value), "history.unstored_error makes no claim about Undo"


def plan_bold(snapshot):
    return Editor(snapshot).stage("Bold", (("Top", 520, 18, "x"),), origins=(None,)).plan()


def test_apply_when_off_gui_thread_then_refuses_before_any_native_call(host):
    import threading

    snapshot = zone_native.capture()
    changes = plan_bold(snapshot)
    host.log.clear()
    caught = []
    worker = threading.Thread(target=lambda: caught.append(_raises(zone_native.apply, snapshot, changes)))
    worker.start()
    worker.join()
    assert caught == [font_history.THREAD_TEXT], f"off-thread refusal expected: {caught}"
    assert host.log == [], f"no master switch off the GUI thread: {host.log}"


def _raises(call, *args):
    try:
        call(*args)
    except ValueError as error:
        return str(error)
    return None


def test_apply_when_glyph_canvas_active_then_refuses_before_any_native_call(host, monkeypatch):
    snapshot = zone_native.capture()
    changes = plan_bold(snapshot)
    monkeypatch.setattr(edit_guards, "canvas_glyphs", lambda native=None: frozenset({(7, "C")}))
    host.log.clear()
    with pytest.raises(ValueError) as caught:
        zone_native.apply(snapshot, changes)
    assert str(caught.value) == font_history.WINDOW_TEXT, f"Glyph-window refusal expected: {caught.value}"
    assert host.log == [], f"no master switch with a Glyph window active: {host.log}"


def test_apply_when_row_refused_then_row_refusal_type(host):
    snapshot = zone_native.capture()
    changes = Editor(snapshot).stage("Bold", (("Top", 520, 18, ""),), origins=(None,)).plan()
    with pytest.raises(zone_native.RowRefusal):
        zone_native.apply(snapshot, changes)


def test_apply_when_read_back_capture_fails_after_commit_then_not_stored_error(host, monkeypatch):
    snapshot = zone_native.capture()
    changes = plan_bold(snapshot)
    real = zone_native.capture
    calls = []

    def capture(expected=None):
        calls.append(expected)
        if len(calls) > 1:  # check() reads first; the read-back after the commit fails
            raise TimeoutError("slow")
        return real(expected)

    monkeypatch.setattr(zone_native, "capture", capture)
    with pytest.raises(RuntimeError, match=r"FontLab did not store 1 change\(s\): zones of every master \(slow\)"):
        zone_native.apply(snapshot, changes)
    assert [e for e in host.log if e[0] == "notify"], "the commit happened before the failed read-back"
