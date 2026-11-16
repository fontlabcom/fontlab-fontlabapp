# this_file: tests/test_teaching_writers_kerning_rules.py
"""Kerning Copy Rules: rule expansion, pair-list build guards and the panel with real Qt."""

import importlib
import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401

MODULE = "fontlabapp.fontui.teaching_writers.kerning_copy_rules"


@pytest.fixture
def mod():
    return importlib.import_module(MODULE)


@pytest.mark.parametrize("token", ["AV", "A|", "|V", "A|V|W", "A |V", "A|#", "A|=", "A|\0"])
def test_pair_token_when_malformed_then_refused(mod, token):
    with pytest.raises(ValueError, match="left\\|right"):
        mod.pair_token(token)


def test_pair_token_when_class_names_then_parsed(mod):
    assert mod.pair_token("@A|@V") == ("@A", "@V")


PAIRS = {("T", "o"): -40, ("@T", "@o"): 10}


def test_expand_rules_when_offsets_and_comments_then_destinations_copy_source(mod):
    text = "# header\nA|V A|W = T|o @ -5  # trailing\n\n@X|@Y = @T|@o\nB|B = T|o @+3\n"
    assert mod.expand_rules(text, PAIRS) == {
        ("A", "V"): -45, ("A", "W"): -45, ("@X", "@Y"): 10, ("B", "B"): -37,
    }


@pytest.mark.parametrize("text,message", [
    ("A|V = T|o\0", "cannot preserve"),
    ("A|V = T|o ", "cannot preserve"),
    ("A|V T|o", "Line 1: Use exactly one"),
    ("A|V = T|o = x", "Line 1: Use exactly one"),
    ("A|V = T|o @ x", "optional @ signed-integer"),
    ("A|V = Q|o", "No explicit source pair: Q|o"),
    ("= T|o", "at least one destination"),
    ("A|V = T|o\nA|V = T|o", "Line 2: Repeated destination"),
    ("# only a comment\n", "at least one copy rule"),
    ("A|V = T|o @ " + "9" * 400, "Line 1: "),
])
def test_expand_rules_when_invalid_then_whole_output_refused(mod, text, message):
    with pytest.raises(ValueError, match=message):
        mod.expand_rules(text, PAIRS)


def test_expand_rules_when_source_not_whole_then_refused(mod):
    with pytest.raises(ValueError, match="whole units"):
        mod.expand_rules("A|V = T|o", {("T", "o"): float("inf")})
    with pytest.raises(ValueError, match="whole units"):
        mod.expand_rules("A|V = T|o", {("T", "o"): 1.5})


class Fake:
    """Install fake kerning batch and scripting modules around build_pair_list."""

    def __init__(self, monkeypatch, *, package, snapshot, same=True, master_after=None):
        self.validated = []
        import fontlabapp.core.scripting as scripting
        import fontlabapp.kerning.batch as batch

        self.package = package
        monkeypatch.setattr(scripting, "current_package", lambda *a: self.package)
        monkeypatch.setattr(batch, "snapshot_kerning", lambda package: snapshot)
        monkeypatch.setattr(
            batch, "validate_pair", lambda package, master, pair, groups=None: self.validated.append(pair)
        )

        def ensure(package, expected):
            if master_after is not None:
                package.master = master_after
            if not same:
                raise ValueError("Kerning changed after the scan.")

        monkeypatch.setattr(batch, "ensure_snapshot", ensure)


def package(master="Regular", upm=1000):
    return NS(master=master, upm=upm, id=1)


def snap(master="Regular", pairs=None):
    return NS(pairs={master: dict(PAIRS) if pairs is None else pairs}, groups={master: {}})


def test_build_pair_list_when_valid_then_header_escapes_master_and_lists_pairs(mod, monkeypatch):
    fake = Fake(monkeypatch, package=package("Bold\nItalic"), snapshot=snap("Bold\nItalic"))
    out = mod.build_pair_list("A|V = T|o @ -5")
    assert out == "# Master: Bold\\nItalic\nA V -45\n"
    assert fake.validated == [("A", "V")]


@pytest.mark.parametrize("kwargs,message", [
    (dict(package=None, snapshot=None), "Open a font first"),
    (dict(package=package("Other"), snapshot=snap("Regular")), "master changed during capture"),
    (dict(package=package(upm=0), snapshot=snap("Regular")), "positive units per em"),
    (dict(package=package(upm=float("nan")), snapshot=snap("Regular")), "positive units per em"),
    (dict(package=package(), snapshot=snap(), same=False), "Kerning changed after the scan"),
    (dict(package=package(), snapshot=snap(), master_after="Bold"), "master changed; Build again"),
])
def test_build_pair_list_when_guard_trips_then_refused(mod, monkeypatch, kwargs, message):
    if kwargs["package"] is not None and kwargs["package"].upm == 0:
        pass
    Fake(monkeypatch, **kwargs)
    with pytest.raises(ValueError, match=message):
        mod.build_pair_list("A|V = T|o")


def test_build_pair_list_when_value_exceeds_double_upm_then_refused(mod, monkeypatch):
    Fake(monkeypatch, package=package(upm=10), snapshot=snap(pairs={("T", "o"): 25}))
    with pytest.raises(ValueError, match="exceeds the pair-list"):
        mod.build_pair_list("A|V = T|o")


def test_export_new_when_relative_empty_or_existing_then_refused_else_exact(mod, tmp_path):
    for name, content in (("rel.txt", "x"), (str(tmp_path / "e.txt"), "")):
        with pytest.raises(ValueError, match="absolute output path"):
            mod.export_new(name, content)
    target = tmp_path / "out.txt"
    mod.export_new(str(target), "A V -45\r\n")
    assert target.read_bytes() == b"A V -45\r\n"
    with pytest.raises(FileExistsError):
        mod.export_new(str(target), "again")


def test_panel_when_built_copied_and_exported_then_status_follows(studio_qt, mod, monkeypatch, tmp_path):  # noqa: F811
    qt = sys.modules["PythonQt"]
    monkeypatch.setattr(mod, "build_pair_list", lambda text: "# Master: R\nA V -1\n")
    panel = mod.show(qt, None, embedded=True)
    assert panel in mod._PANELS
    panel.copy_result()
    assert panel.status_line.text() == "Build the pair list first."
    panel.build_result()
    assert panel.content.endswith("A V -1\n") and "Import Kerning" in panel.status_line.text()
    panel.copy_result()
    assert "Paste into" in panel.status_line.text()
    panel.path_field.setText(str(tmp_path / "p.txt"))
    panel.save_result()
    assert "exported" in panel.status_line.text() and (tmp_path / "p.txt").exists()
    panel.save_result()  # file now exists: partial-write warning, no crash
    assert "partial file" in panel.status_line.text()
    panel.rule_field.setPlainText("A|V = T|o")  # editing the recipe discards the stale result
    assert panel.content == "" and panel.result_field.toPlainText() == ""
    monkeypatch.setattr(mod, "build_pair_list", lambda text: (_ for _ in ()).throw(ValueError("bad rule")))
    panel.build_result()
    assert panel.status_line.text() == "bad rule" and panel.content == ""
    panel.close()
    assert panel not in mod._PANELS


def test_panel_when_destroyed_or_close_cleanup_fails_then_released_or_retained(studio_qt, mod):  # noqa: F811
    qt = sys.modules["PythonQt"]
    panel = mod.show(qt, None, embedded=True)
    panel.scope.finish = lambda destroyed=False: False
    event = NS(ignored=False, accepted=False)
    event.ignore = lambda: setattr(event, "ignored", True)
    event.accept = lambda: setattr(event, "accepted", True)
    panel.closeEvent(event)
    assert event.ignored and panel in mod._PANELS
    del panel.scope.finish
    panel.release_owner()
    assert panel not in mod._PANELS
    panel.release_owner()  # idempotent


def test_show_when_window_show_fails_then_scope_finished_and_error_reraised(studio_qt, mod, monkeypatch):  # noqa: F811
    qt = sys.modules["PythonQt"]
    gui = qt.QtGui
    monkeypatch.setattr(gui.QWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("no screen")))
    before = list(mod._PANELS)
    with pytest.raises(RuntimeError, match="no screen"):
        mod.show(qt, None)
    assert mod._PANELS == before


def test_main_when_show_refuses_then_prints_title_and_reason(mod, monkeypatch, capsys):
    fl = NS(MainWindow=lambda: "window")
    monkeypatch.setitem(sys.modules, "fontlab", fl)
    monkeypatch.setitem(sys.modules, "PythonQt", NS())
    seen = []
    monkeypatch.setattr(mod, "show", lambda qt, parent: seen.append(parent))
    mod.main()
    assert seen == ["window"]
    monkeypatch.setattr(mod, "show", lambda qt, parent: (_ for _ in ()).throw(ValueError("nope")))
    mod.main()
    assert capsys.readouterr().out == "Kerning Copy Rules: nope\n"
