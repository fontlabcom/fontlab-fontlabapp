# this_file: tests/test_teaching_writers_name_encoding.py
"""Font Name Encoding Audit: capture, strict encoding report and panel, on real offscreen Qt."""

import json
import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_writers import font_name_encoding_audit

    return font_name_encoding_audit


def package(mod, master="Regular", pid=1, **over):
    return NS(isNull=False, id=pid, master=master, info=NS(**({f: f"{f}-v" for f in mod.FIELDS} | over)))


def sequence(packages):
    reads = iter(packages)

    class W:
        @property
        def currentPackage(self):
            return next(reads)

    return NS(flWorkspace=NS(instance=lambda: W()))


@pytest.mark.parametrize("bad", ["a\0", "a\r", "a ", "a ", "a ", "\ud800"])
def test_checked_when_unpreservable_then_refused(mod, bad):
    with pytest.raises(ValueError):
        mod.checked(bad)
    assert mod.checked("ok") == "ok"


def test_capture_info_when_stable_then_returned(mod, monkeypatch):
    p = package(mod)
    assert mod.capture_info(sequence([p] * 8))[0] == "Regular"
    monkeypatch.setitem(sys.modules, "fontlab", sequence([p] * 8))
    assert mod.capture_info()[1]["familyName"] == "familyName-v"


@pytest.mark.parametrize("case", ["none", "null", "gone", "other", "blank", "nontext", "master", "change"])
def test_capture_info_when_context_breaks_then_refused(mod, case):
    p = package(mod)
    changed = package(mod, familyName="changed")
    seq = {
        "none": [None],
        "null": [NS(isNull=True)],
        "gone": [p, None],
        "other": [p, package(mod, pid=2)],
        "blank": [p, package(mod, master=" ")],
        "nontext": [p, package(mod, familyName=3)],
        "master": [p, p, package(mod, master="Bold")],
        "change": [p, p, p, changed, changed],
    }[case]
    with pytest.raises(ValueError):
        mod.capture_info(sequence(seq + [p] * 10))


def test_export_new_guards(mod, tmp_path):
    target = tmp_path / "o.json"
    mod.export_new(str(target), "ok")
    assert target.read_text() == "ok"
    with pytest.raises(FileExistsError):
        mod.export_new(str(target), "ok")
    with pytest.raises(ValueError, match="absolute"):
        mod.export_new("rel", "ok")


def test_encoding_report_when_mixed_text_then_per_encoding_records(mod):
    info = {f: "abc" for f in mod.FIELDS} | {"familyName": "Ünï€", "postscriptFontName": "Psé"}
    report = json.loads(mod.encoding_report(("R", info)))
    assert report["scope"] == "Current master: R" and len(report["records"]) == 4 * len(mod.FIELDS)
    pick = {(r["field"], r["encoding"]): r for r in report["records"]}
    euro = pick["familyName", "cp1252"]
    assert euro["hex"] == "dc6eef80" and euro["unencodable"] == []
    ascii_ = pick["familyName", "ascii"]
    assert ascii_["hex"] is None and ascii_["unencodable"][0] == {"index": 0, "codepoint": "U+00DC"}
    mac = pick["familyName", "mac_roman"]
    assert mac["hex"] == "Ünï€".encode("mac_roman").hex() and mac["unencodable"] == []
    ps = pick["postscriptFontName", "ascii"]
    assert ps["ascii_required"] is True and ps["ascii_valid"] is False
    assert pick["familyName", "utf-16-be"]["purpose"] == "byte dump"
    assert pick["familyName", "ascii"]["purpose"] == "legacy encoding check"
    assert pick["styleName", "ascii"]["ascii_valid"] is None
    with pytest.raises(ValueError):
        mod.encoding_report(("R", info | {"copyright": "a\r"}))


@pytest.fixture
def panel_world(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.fontui.teaching_writers import font_name_encoding_audit as module

    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(module, "capture_info", lambda: ("Regular", {f: f"{f}-v" for f in module.FIELDS}))
    parent = qt.QtGui.QWidget()
    yield module, qt, parent
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_when_refreshed_and_exported(panel_world, tmp_path):
    module, qt, parent = panel_world
    panel = module.show(qt, parent, embedded=True)
    assert panel.master_line.text() == "Current master: Regular" and '"records"' in panel.preview.toPlainText()
    panel.destination.setText(str(tmp_path / "o.json"))
    click(panel, qt, "Export New")
    assert panel.status_line.text().startswith("Output exported") and (tmp_path / "o.json").exists()
    click(panel, qt, "Export New")
    assert "File exists" in panel.status_line.text()


def test_panel_when_capture_fails_then_cleared(panel_world, monkeypatch):
    module, qt, parent = panel_world
    monkeypatch.setattr(module, "capture_info", lambda: (_ for _ in ()).throw(ValueError("Open a font first.")))
    panel = module.show(qt, parent, embedded=True)
    assert panel.info is None and panel.preview.toPlainText() == ""
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
        mod.capture_info(sequence([package(mod, master=master)] * 10))


def test_capture_info_when_package_turns_null_on_reread_then_refused(mod):
    p = package(mod)
    stale = NS(isNull=True, id=1, master="Regular", info=p.info)
    with pytest.raises(ValueError, match="Current font or master changed"):
        mod.capture_info(sequence([p, p, stale] + [p] * 10))
    with pytest.raises(ValueError, match="Current font changed"):
        mod.capture_info(sequence([p, stale] + [p] * 10))
