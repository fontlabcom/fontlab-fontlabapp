# this_file: tests/test_teaching_writers_localized_names.py
"""Localized Font Names: encoding, name table output, capture and the panel, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_writers import localized_font_names

    return localized_font_names


def info(mod, **over):
    return NS(**{f: f"{f}-v" for f in mod.FIELDS} | over)


def package(mod, master="Regular", pid=1, **over):
    return NS(isNull=False, id=pid, master=master, info=info(mod, **over))


def workspace(packages):
    reads = iter(packages)

    class W:
        @property
        def currentPackage(self):
            return next(reads)

    return NS(flWorkspace=NS(instance=lambda: W()))


@pytest.mark.parametrize("bad", ["a\0", "a\r", "\ud800"])
def test_checked_when_unpreservable_then_refused(mod, bad):
    with pytest.raises(ValueError):
        mod.checked(bad)
    assert mod.checked("ok") == "ok"


def test_feature_string_escapes_non_ascii_quote_and_backslash(mod):
    assert mod.feature_string('A"\\é') == "A\\0022\\005c\\00e9"
    assert mod.feature_string("\U0001f600") == "\\d83d\\de00"


@pytest.mark.parametrize("bad", ["", "  ", "a\tb"])
def test_feature_string_when_blank_or_control_then_refused(mod, bad):
    with pytest.raises(ValueError, match="nonempty"):
        mod.feature_string(bad)


def test_name_feature_decimal_and_hex(mod):
    out = mod.name_feature("Fam", "Sty", "1033", "Reg")
    assert out.startswith('# Current master: "Reg"\n')
    assert 'nameid 16 3 1 0x0409 "Fam";' in out and 'nameid 17 3 1 0x0409 "Sty";' in out
    assert "0x0409" in mod.name_feature("F", "S", "0X409", "R")


@pytest.mark.parametrize(
    ("lang", "match"),
    [("abc", "decimal or 0x"), ("0xzz", "decimal or 0x"), ("-1", "0..65535"), ("65536", "0..65535")],
)
def test_name_feature_when_language_bad_then_refused(mod, lang, match):
    with pytest.raises(ValueError, match=match):
        mod.name_feature("F", "S", lang, "R")


def test_capture_info_stable_default_native_and_breaks(mod, monkeypatch):
    p = package(mod)
    master, values = mod.capture_info(workspace([p] * 10))
    assert master == "Regular" and set(values) == set(mod.FIELDS)
    monkeypatch.setitem(sys.modules, "fontlab", workspace([p] * 10))
    assert mod.capture_info()[0] == "Regular"
    seqs = {
        "none": [None],
        "null": [NS(isNull=True)],
        "gone": [p, None],
        "other": [p, package(mod, pid=2)],
        "blank": [p, package(mod, master=" ")],
        "nontext": [p, package(mod, familyName=3)],
        "master": [p, p, package(mod, master="Bold")],
        "change": [p, p, p, package(mod, familyName="x"), package(mod, familyName="x")],
    }
    for name, seq in seqs.items():
        with pytest.raises(ValueError):
            mod.capture_info(workspace(seq + [p] * 10))


def test_export_new_guards(mod, tmp_path):
    target = tmp_path / "o.fea"
    mod.export_new(str(target), "ok")
    with pytest.raises(FileExistsError):
        mod.export_new(str(target), "ok")
    with pytest.raises(ValueError, match="absolute"):
        mod.export_new("rel", "ok")
    with pytest.raises(ValueError):
        mod.export_new(str(tmp_path / "n"), "a\r")


@pytest.fixture
def panel_world(studio_qt, monkeypatch):  # noqa: F811
    from fontlabapp.fontui.teaching_writers import localized_font_names as module

    qt = sys.modules["PythonQt"]
    values = {f: f"{f}-v" for f in module.FIELDS}
    values["openTypeNamePreferredFamilyName"] = ""
    values["openTypeNamePreferredSubfamilyName"] = ""
    monkeypatch.setattr(module, "capture_info", lambda: ("Regular", values))
    parent = qt.QtGui.QWidget()
    yield module, qt, parent
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_when_refreshed_edited_and_exported(panel_world, tmp_path):
    module, qt, parent = panel_world
    panel = module.show(qt, parent, embedded=True)
    assert panel.master_line.text() == "Current master: Regular"
    assert panel.family_field.text() == "familyName-v" and panel.style_field.text() == "styleName-v"
    assert panel.preview.toPlainText() == ""  # language empty
    assert not panel.unsaved
    panel.language_field.setText("1031")
    assert panel.unsaved and "Translation changed" in panel.status_line.text()
    click(panel, qt, "Refresh Current Font")
    assert panel.status_line.text() == "Export or discard the translation before Refresh."
    click(panel, qt, "Export New")  # no destination
    assert "absolute" in panel.status_line.text()
    panel.destination.setText(str(tmp_path / "n.fea"))
    click(panel, qt, "Export New")
    assert panel.status_line.text().startswith("Output exported") and not panel.unsaved
    assert "0x0407" in (tmp_path / "n.fea").read_text()
    click(panel, qt, "Export New")
    assert panel.status_line.text() == "[Errno 17] File exists: '" + str(tmp_path / "n.fea") + "'"
    panel.family_field.setText("X")
    click(panel, qt, "Discard Translation")
    assert not panel.unsaved and panel.family_field.text() == "familyName-v"


def test_panel_prefers_typographic_names_and_shows_preview(panel_world, monkeypatch):
    module, qt, parent = panel_world
    values = {f: "v" for f in module.FIELDS}
    values["openTypeNamePreferredFamilyName"] = "Pref"
    values["openTypeNamePreferredSubfamilyName"] = "Sub"
    monkeypatch.setattr(module, "capture_info", lambda: ("Bold", values))
    panel = module.show(qt, parent, embedded=True)
    assert panel.family_field.text() == "Pref" and panel.style_field.text() == "Sub"
    panel.language_field.setText("0x409")
    panel.unsaved = False
    click(panel, qt, "Refresh Current Font")
    assert 'nameid 16 3 1 0x0409 "Pref"' in panel.preview.toPlainText()


def test_panel_when_capture_fails_then_cleared(panel_world, monkeypatch):
    module, qt, parent = panel_world
    monkeypatch.setattr(module, "capture_info", lambda: (_ for _ in ()).throw(ValueError("Open a font first.")))
    panel = module.show(qt, parent, embedded=True)
    assert panel.info is None and panel.status_line.text() == "Open a font first."
    assert panel.master_line.text() == "Current master: —"
    click(panel, qt, "Export New")
    assert panel.status_line.text() == "Refresh from an open font first."


def test_panel_when_language_invalid_then_status(panel_world):
    module, qt, parent = panel_world
    panel = module.show(qt, parent, embedded=True)
    panel.language_field.setText("zz")
    panel.unsaved = False
    click(panel, qt, "Refresh Current Font")
    assert "decimal or 0x" in panel.status_line.text() and panel.preview.toPlainText() == ""


def test_panel_non_embedded_discard_closes_and_close_guard(panel_world, monkeypatch):
    module, qt, parent = panel_world
    monkeypatch.setattr(qt.QtGui.QWidget, "show", lambda self: None)
    panel = module.show(qt, parent)
    event = NS(ignored=0, accepted=0)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", 1)), (lambda: setattr(event, "accepted", 1))
    panel.mark_edited()
    panel.closeEvent(event)
    assert event.ignored and "Discard and Close" in panel.status_line.text()
    event.ignored = 0
    closed = []
    monkeypatch.setattr(type(panel), "close", lambda self: closed.append(1) or True)
    click(panel, qt, "Discard and Close")
    assert closed and not panel.unsaved
    panel.scope.finish = lambda destroyed=False: False
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    del panel.scope.finish
    panel.closeEvent(event)
    assert event.accepted and panel not in module._PANELS


def test_panel_release_owner_and_show_failure(panel_world, monkeypatch):
    module, qt, parent = panel_world
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
        mod.capture_info(workspace([package(mod, master=master)] * 10))


def test_capture_info_when_package_turns_null_on_reread_then_refused(mod):
    p = package(mod)
    stale = NS(isNull=True, id=1, master="Regular", info=p.info)
    with pytest.raises(ValueError, match="Current font or master changed"):
        mod.capture_info(workspace([p, p, stale] + [p] * 10))
    with pytest.raises(ValueError, match="Current font changed"):
        mod.capture_info(workspace([p, stale] + [p] * 10))


@pytest.mark.parametrize("lang,hexid", [("0", "0x0000"), ("65535", "0xffff")])
def test_name_feature_when_language_at_inclusive_bounds_then_accepted(mod, lang, hexid):
    assert hexid in mod.name_feature("F", "S", lang, "R")
