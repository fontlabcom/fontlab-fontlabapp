# this_file: tests/test_teaching_writers_font_info.py
"""Font Info Snapshot: capture, JSON round trip, comparison and the panel, on real offscreen Qt."""

import json
import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_writers import font_info_snapshot

    return font_info_snapshot


def info(**over):
    from fontlabapp.fontui.teaching_writers import font_info_snapshot as m

    return NS(**{f: f"{f}-v" for f in m.FIELDS} | over)


def native(package_factory):
    return NS(flWorkspace=NS(instance=lambda: NS(currentPackage=package_factory())))


def package(master="Regular", pid=1, **over):
    return NS(isNull=False, id=pid, master=master, info=info(**over))


@pytest.mark.parametrize("bad", ["a\0", "a\r", "a ", "a ", "a ", "\ud800"])
def test_checked_when_unpreservable_then_refused(mod, bad):
    with pytest.raises(ValueError):
        mod.checked(bad)
    assert mod.checked("ok") == "ok"


def test_capture_info_when_stable_then_master_and_fields(mod):
    master, values = mod.capture_info(native(package))
    assert master == "Regular" and values["familyName"] == "familyName-v" and set(values) == set(mod.FIELDS)


def test_capture_info_when_default_native_then_imports_fontlab(mod, monkeypatch):
    monkeypatch.setitem(sys.modules, "fontlab", native(package))
    assert mod.capture_info()[0] == "Regular"


def workspace_sequence(packages):
    reads = iter(packages)

    class W:
        @property
        def currentPackage(self):
            return next(reads)

    return NS(flWorkspace=NS(instance=lambda: W()))


@pytest.mark.parametrize("case", ["none", "null", "gone", "other", "blank", "nontext", "master", "change"])
def test_capture_info_when_context_breaks_then_refused(mod, case):
    p = package()
    seq = {
        "none": [None],
        "null": [NS(isNull=True)],
        "gone": [p, None],
        "other": [p, package(pid=2)],
        "blank": [p, package(master=" ")],
        "nontext": [p, package(familyName=3)],
        "master": [p, p, package(master="Bold")],
        "change": [p, p, p, package(familyName="changed"), package(familyName="changed")],
    }[case]
    with pytest.raises(ValueError):
        mod.capture_info(workspace_sequence(seq + [p] * 10))


def test_snapshot_json_and_read_roundtrip_and_compare(mod, tmp_path):
    captured = ("Regular", {f: f"{f}-v" for f in mod.FIELDS})
    text = mod.snapshot_json(captured)
    path = tmp_path / "s.json"
    path.write_bytes(b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode())
    loaded, notes = mod.read_snapshot(str(path))
    assert loaded == captured and notes == ("UTF-8 BOM removed", "CR line endings normalized")
    changed = ("Regular", dict(captured[1], copyright="new"))
    diff = json.loads(mod.compare_info(captured, changed))
    assert diff["changes"] == {"copyright": {"saved": "copyright-v", "current": "new"}}
    with pytest.raises(ValueError, match="across masters"):
        mod.compare_info(captured, ("Bold", captured[1]))


def test_snapshot_json_and_read_refusals(mod, tmp_path):
    full = {f: "x" for f in mod.FIELDS}
    with pytest.raises(ValueError, match="named master"):
        mod.snapshot_json((" ", full))
    with pytest.raises(ValueError, match="exactly"):
        mod.snapshot_json(("R", {"familyName": "x"}))
    with pytest.raises(ValueError, match="absolute"):
        mod.read_snapshot("rel.json")
    for body, match in (
        ('{"schema":2,"schema":2}', "Duplicate JSON key"),
        ('{"schema":1,"master":"R","names":{}}', "schema 2"),
        ("[]", "schema 2"),
    ):
        path = tmp_path / "bad.json"
        path.write_text(body)
        with pytest.raises(ValueError, match=match):
            mod.read_snapshot(str(path))


def test_export_new_guards(mod, tmp_path):
    target = tmp_path / "o.json"
    mod.export_new(str(target), "ok")
    with pytest.raises(FileExistsError):
        mod.export_new(str(target), "ok")
    with pytest.raises(ValueError, match="absolute"):
        mod.export_new("rel", "ok")
    with pytest.raises(ValueError):
        mod.export_new(str(tmp_path / "n"), "a\r")


@pytest.fixture
def panel_world(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.fontui.teaching_writers import font_info_snapshot as module

    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(module, "capture_info", lambda: ("Regular", {f: f"{f}-v" for f in module.FIELDS}))
    parent = qt.QtGui.QWidget()
    yield module, qt, parent
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_when_refreshed_exported_and_compared(panel_world, tmp_path, monkeypatch):
    module, qt, parent = panel_world
    panel = module.show(qt, parent, embedded=True)
    assert panel.master_line.text() == "Current master: Regular" and '"schema": 2' in panel.preview.toPlainText()
    panel.destination.setText(str(tmp_path / "o.json"))
    click(panel, qt, "Export New")
    assert panel.status_line.text().startswith("Output exported")
    click(panel, qt, "Export New")  # exists now
    ref = tmp_path / "ref.json"
    ref.write_text((tmp_path / "o.json").read_text().replace("copyright-v", "old"))
    panel.reference_field.setText(str(ref))
    click(panel, qt, "Compare Saved")
    assert '"old"' in panel.preview.toPlainText() and panel.status_line.text().startswith("Comparison shown")
    ref.write_bytes(b"\xef\xbb\xbf" + ref.read_bytes())
    click(panel, qt, "Compare Saved")
    assert "UTF-8 BOM removed." in panel.status_line.text()
    panel.reference_field.setText(str(tmp_path / "missing.json"))
    click(panel, qt, "Compare Saved")
    assert panel.preview.toPlainText() == ""


def test_panel_when_capture_fails_then_cleared_and_output_refused(panel_world, monkeypatch):
    module, qt, parent = panel_world
    monkeypatch.setattr(module, "capture_info", lambda: (_ for _ in ()).throw(ValueError("Open a font first.")))
    panel = module.show(qt, parent, embedded=True)
    assert panel.info is None and panel.status_line.text() == "Open a font first."
    click(panel, qt, "Export New")
    assert panel.status_line.text() == "Refresh from an open font first."


def test_panel_close_destroy_and_show_failure(panel_world, monkeypatch):
    module, qt, parent = panel_world
    panel = module.show(qt, parent, embedded=True)
    event = NS(ignored=0, accepted=0)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", 1)), (lambda: setattr(event, "accepted", 1))
    panel.scope.finish = lambda destroyed=False: False
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    del panel.scope.finish
    panel.closeEvent(event)
    assert event.accepted and panel not in module._PANELS
    other = module.show(qt, parent, embedded=True)
    other.release_owner()
    other.release_owner()
    import fontlabapp.core.signals.scope as signals

    with monkeypatch.context() as local:
        local.setattr(qt.QtGui, "QPlainTextEdit", lambda *a: (_ for _ in ()).throw(RuntimeError("no edit")))
        with pytest.raises(RuntimeError):
            module.show(qt, parent, embedded=True)
        assert module._PANELS == []
        local.setattr(signals.Scope, "finish", lambda self, destroyed=False: False)
        with pytest.raises(RuntimeError):
            module.show(qt, parent, embedded=True)
        assert len(module._PANELS) == 1


def test_main_prints_error(panel_world, monkeypatch, capsys):
    module, qt, parent = panel_world
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    monkeypatch.setattr(module, "show", lambda q, p: (_ for _ in ()).throw(ValueError("nope")))
    module.main()
    assert capsys.readouterr().out == f"{module.TITLE}: nope\n"


@pytest.mark.parametrize("master,message", [(" ", "must have a name"), ("", "must have a name"), (7, "must have a name")])
def test_capture_info_when_master_name_unusable_then_named_refusal(mod, master, message):
    with pytest.raises(ValueError, match=message):
        mod.capture_info(workspace_sequence([package(master=master)] * 10))


def test_capture_info_when_package_turns_null_on_reread_then_refused(mod):
    p = package()
    stale = NS(isNull=True, id=1, master="Regular", info=p.info)
    with pytest.raises(ValueError, match="Current font or master changed"):
        mod.capture_info(workspace_sequence([p, p, stale] + [p] * 10))
    with pytest.raises(ValueError, match="Current font changed"):
        mod.capture_info(workspace_sequence([p, stale] + [p] * 10))
