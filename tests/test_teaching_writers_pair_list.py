# this_file: tests/test_teaching_writers_pair_list.py
"""Import Kerning Pair List: parsing, validation, plan/apply and the panel, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_writers import import_kerning_pair_list

    return import_kerning_pair_list


def test_parse_pairs_when_mixed_rows_then_values_and_errors(mod):
    text = "# header\nA V -40  # trailing\n\nA V -41\nT o 12.5\nT p -12.5\nbad row\nX Y nan\nX Z 40000\nX W abc\n"
    rows = mod.parse_pairs(text)
    by_line = {r["line"]: r for r in rows}
    assert by_line[2]["value"] == -40 and by_line[2]["error"] == ""
    assert "Repeated pair" in by_line[4]["error"]
    assert by_line[5]["value"] == 13 and by_line[6]["value"] == -13
    assert by_line[7]["error"] == "Expected left right value."
    assert by_line[8]["error"] == "Value must be finite."
    assert "exceeds" in by_line[9]["error"]
    assert "could not convert" in by_line[10]["error"]
    assert 1 not in by_line and 3 not in by_line


@pytest.mark.parametrize("bad", ["a\0", "a ", "a ", "a "])
def test_parse_pairs_when_qt_hostile_then_refused(mod, bad):
    with pytest.raises(ValueError, match="Qt cannot preserve"):
        mod.parse_pairs(bad)


def history_fake(refuse=None):
    return NS(refusal=lambda facts, name, kind: (refuse or {}).get(name, ""), scan_auto_facts=lambda package: "facts")


def test_validate_row_when_error_group_or_refusal_then_raises(mod):
    seen = []
    batch = NS(validate_pair=lambda package, master, pair, groups: seen.append((master, pair, groups)))
    snap = NS(groups={"R": {"A": (("A", "Aacute"), None)}})
    row = {"error": "", "left": "@A", "right": "V"}
    mod.validate_row("pkg", "R", row, snap, None, batch, history_fake())
    assert seen == [("R", ("@A", "V"), snap.groups["R"])]
    with pytest.raises(ValueError, match="Aacute: no"):
        mod.validate_row("pkg", "R", row, snap, None, batch, history_fake({"Aacute": "no"}))
    with pytest.raises(ValueError, match="boom"):
        mod.validate_row("pkg", "R", {**row, "error": "boom"}, snap, None, batch, history_fake())


class World:
    def __init__(self, monkeypatch, pairs=None):
        import fontlabapp.core.history.glyphs as history
        import fontlabapp.core.scripting as scripting
        import fontlabapp.kerning.batch as batch

        self.package = NS(master="R", id=7)
        self.snapshot = NS(groups={"R": {}}, pairs={"R": pairs or {("A", "V"): -10}})
        self.written = []
        self.ensured = []
        self.invalid = set()
        self.write_result = True
        self.current = self.package
        monkeypatch.setattr(history, "scan_auto_facts", lambda package: "facts")
        monkeypatch.setattr(history, "refusal", lambda facts, name, kind: "")
        monkeypatch.setattr(scripting, "current_package", lambda *a: self.current)
        monkeypatch.setattr(batch, "snapshot_kerning", lambda package: self.snapshot)
        monkeypatch.setattr(batch, "ensure_snapshot", lambda package, snap: self.ensured.append(snap))

        def validate(package, master, pair, groups):
            if pair in self.invalid:
                raise ValueError("bad pair")

        monkeypatch.setattr(batch, "validate_pair", validate)

        def write(package, edits, title, expected):
            self.written.append((edits, title, expected))
            return self.write_result

        monkeypatch.setattr(batch, "write_kerning", write)


@pytest.fixture
def world(monkeypatch):
    return World(monkeypatch)


def test_prepare_and_apply_pairs_happy_path(mod, world):
    plan = mod.prepare_pairs("A V -40\nT o 5\n")
    assert plan["master"] == "R" and plan["package_id"] == 7
    assert [r["current"] for r in plan["rows"]] == [-10, None]
    assert mod.apply_pairs(plan, "A V -40\nT o 5\n") is True
    edits, title, expected = world.written[0]
    assert edits == {"R": {("A", "V"): -40, ("T", "o"): 5}} and title == mod.TITLE and expected is world.snapshot


def test_prepare_pairs_when_invalid_row_then_error_recorded(mod, world):
    world.invalid.add(("T", "o"))
    plan = mod.prepare_pairs("T o 5\n")
    assert plan["rows"][0]["error"] == "bad pair"


def test_prepare_pairs_when_no_font_or_master_changes_then_refused(mod, world, monkeypatch):
    import fontlabapp.kerning.batch as batch

    monkeypatch.setattr(batch, "ensure_snapshot", lambda package, snap: setattr(world.package, "master", "B"))
    with pytest.raises(ValueError, match="master changed"):
        mod.prepare_pairs("A V 1\n")
    world.current = None
    with pytest.raises(ValueError, match="Open a font first"):
        mod.prepare_pairs("A V 1\n")


def test_apply_pairs_refusals(mod, world):
    plan = mod.prepare_pairs("A V -40\n")
    with pytest.raises(ValueError, match="Text changed"):
        mod.apply_pairs(plan, "other")
    with pytest.raises(ValueError, match="Correct the rows"):
        mod.apply_pairs({**plan, "rows": []}, plan["text"])
    world.current = None
    with pytest.raises(ValueError, match="font or master changed"):
        mod.apply_pairs(plan, plan["text"])
    world.current = NS(master="B", id=7)
    with pytest.raises(ValueError, match="font or master changed"):
        mod.apply_pairs(plan, plan["text"])
    world.current = world.package
    world.invalid.add(("A", "V"))
    with pytest.raises(ValueError, match="bad pair"):
        mod.apply_pairs(plan, plan["text"])


@pytest.fixture
def panel_world(studio_qt, world):  # noqa: F811
    from fontlabapp.fontui.teaching_writers import import_kerning_pair_list as module

    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    yield module, qt, parent, world
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def test_panel_preview_apply_flow(panel_world):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, embedded=True)
    assert not panel.apply_button.isEnabled()
    click(panel, qt, "Apply")
    panel.input_field.setPlainText("A V -40\nT o 5\n")
    click(panel, qt, "Preview")
    table = panel.preview_table
    assert table.rowCount() == 2 and table.item(0, 3).text() == "-10" and table.item(1, 3).text() == "Absent"
    assert table.item(1, 5).text() == "Ready" and panel.apply_button.isEnabled()
    assert panel.status_line.text() == "R: 2 rows. Ready to Apply."
    click(panel, qt, "Apply")
    assert panel.status_line.text() == "Pairs applied and read back." and panel.plan_data is None
    assert not panel.apply_button.isEnabled()
    click(panel, qt, "Preview")
    world.write_result = False
    click(panel, qt, "Apply")
    assert panel.status_line.text() == "No pair values changed."


def test_panel_when_invalid_rows_or_edits_then_apply_blocked(panel_world):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, embedded=True)
    panel.input_field.setPlainText("oops\n")
    click(panel, qt, "Preview")
    assert "Correct invalid rows" in panel.status_line.text() and not panel.apply_button.isEnabled()
    panel.input_field.setPlainText("A V 1\n")
    click(panel, qt, "Preview")
    assert panel.apply_button.isEnabled()
    panel.input_field.setPlainText("A V 2\n")
    assert panel.plan_data is None and panel.preview_table.rowCount() == 0
    panel.input_field.setPlainText("a\0")
    click(panel, qt, "Preview")
    assert "Qt cannot preserve" in panel.status_line.text()
    panel.input_field.setPlainText("A V 1\n")
    click(panel, qt, "Preview")
    world.current = None
    click(panel, qt, "Apply")
    assert "font or master changed" in panel.status_line.text()


def test_panel_lab_hooks_are_used_when_present(panel_world):
    module, qt, parent, world = panel_world
    panel = module.show(qt, parent, embedded=True)
    calls = []
    panel.lab_refresh_preview = lambda: calls.append("refresh")
    panel.lab_check_target = lambda: calls.append("check")
    panel.input_field.setPlainText("A V 1\n")
    click(panel, qt, "Preview")
    click(panel, qt, "Apply")
    assert calls == ["refresh", "check"] and panel.preview_table.isSortingEnabled()


def test_panel_close_destroy_and_show_failure(panel_world, monkeypatch):
    module, qt, parent, world = panel_world
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
    with monkeypatch.context() as local:
        local.setattr(qt.QtGui.QWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("no show")))
        with pytest.raises(RuntimeError):
            module.show(qt, parent)
        assert module._PANELS == []


def test_main_prints_error(panel_world, monkeypatch, capsys):
    module, qt, parent, world = panel_world
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    monkeypatch.setattr(module, "show", lambda q, p: (_ for _ in ()).throw(ValueError("nope")))
    module.main()
    assert capsys.readouterr().out == f"{module.TITLE}: nope\n"


def test_parse_pairs_when_value_at_32767_boundary_then_accepted_and_just_above_refused(mod):
    rows = {r["line"]: r for r in mod.parse_pairs("A V 32767\nA W -32767\nA X 32767.4\nA Y 32768\nA Z -32768\n")}
    assert rows[1]["error"] == "" and rows[1]["value"] == 32767
    assert rows[2]["error"] == "" and rows[2]["value"] == -32767
    assert all("exceeds" in rows[line]["error"] for line in (3, 4, 5))  # the limit applies before rounding
