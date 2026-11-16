# this_file: tests/test_wp08_snapshot_audit.py
"""S60/S61 report windows reuse each original snapshot owner inside the shared shell."""

import importlib
import sys

import pytest

from _studio_qt import studio_qt  # noqa: F401

NAMES = ("fontlabapp.fontui.snapshot_audit", "fontlabapp.fontui.geometry_audit",
         "fontlabapp.fontui.master_structure_audit")


@pytest.fixture
def audit(studio_qt, monkeypatch):  # noqa: F811
    for name in NAMES:
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(NAMES[0])
    yield module, studio_qt
    for shell in tuple(module._HANDLES):
        shell.close()
    for name in NAMES:
        sys.modules.pop(name, None)


def routes(log, fail=False):
    def capture():
        log.append("capture")
        if fail:
            raise ValueError("native changed")
        return ("a", "b")
    return (
        ("One", "first", capture, lambda rows: "|".join(rows), lambda rows: f"{len(rows)} rows"),
        ("Two", "second", lambda: ("z",), lambda rows: rows[0], lambda rows: "1 row"),
    )


def test_show_when_routes_given_then_one_tab_each_with_rendered_text(audit):
    module, env = audit
    log = []
    shell = module.show_snapshots("Audit", routes(log), "about")
    titles = [shell.tabs.tabText(i) for i in range(3)]
    assert titles == ["One", "Two", "About"]
    first, second = shell.snapshot_tabs
    assert first.output.toPlainText() == "a|b" and second.output.toPlainText() == "z"
    assert first.output.isReadOnly() and first.report == ("a", "b")
    assert "2 rows" in shell.status.text() or "1 row" in shell.status.text()


def test_refresh_when_capture_fails_then_text_cleared_and_reason_shown(audit):
    module, env = audit
    log = []
    shell = module.show_snapshots("Audit", routes(log, fail=True), "about", only="One")
    tab, = shell.snapshot_tabs
    assert tab.output.toPlainText() == "" and tab.report is None
    assert "native changed" in shell.status.text()
    assert log == ["capture"]


def test_show_when_only_unknown_then_refused_without_shell(audit):
    module, env = audit
    with pytest.raises(ValueError, match="Unknown report: Nope"):
        module.show_snapshots("Audit", routes([]), "about", only="Nope")
    assert module._HANDLES == []


def test_show_when_off_main_thread_then_refused(audit, monkeypatch):
    module, env = audit
    monkeypatch.setattr(module, "current_thread", lambda: object())
    with pytest.raises(RuntimeError, match="main UI thread"):
        module.show_snapshots("Audit", routes([]), "about")
    assert module._HANDLES == []


def test_show_when_tab_build_fails_then_shell_closed_and_released(audit):
    module, env = audit
    bad = (("Bad", "d", lambda: 1, lambda r: (_ for _ in ()).throw(ValueError("render")), str),)
    shell = module.show_snapshots("Audit", bad, "about")
    assert "render" in shell.status.text()
    shell.close()
    assert module._HANDLES == []


def test_show_when_construction_fails_then_cleanup_failure_noted_and_owner_retained(audit, monkeypatch):
    module, env = audit

    def boom(self, spec):
        raise ValueError("tab build")

    monkeypatch.setattr(module.AppShell, "add_tab", boom)
    monkeypatch.setattr(module.SnapshotShell, "close",
                        lambda self: (_ for _ in ()).throw(RuntimeError("stuck")))
    with pytest.raises(ValueError, match="tab build") as raised:
        module.show_snapshots("Audit", routes([]), "about")
    assert any("stuck" in note for note in raised.value.__notes__)
    assert len(module._HANDLES) == 1
    monkeypatch.undo()
    module._HANDLES[0].close()


@pytest.mark.parametrize("mod,titles", [
    ("geometry_audit", ["Close But No Cigar", "Dangerous Offcurves", "Dump to Svg Path Commands",
                        "Point Counter (Master Layers)", "Point Counter"]),
    ("master_structure_audit", ["Master Node Compatibility Report", "Why You Not Compatible"]),
])
def test_routes_when_built_then_original_titles_and_callables(audit, mod, titles):
    module, env = audit
    owner = importlib.import_module(f"fontlabapp.fontui.{mod}")
    table = owner.routes()
    assert [r[0] for r in table] == titles
    assert all(callable(r[2]) and callable(r[3]) and callable(r[4]) and r[1] for r in table)
    assert table[0][4]([1, 2]).startswith(("2 ", "Snapshot"))


@pytest.mark.parametrize("mod", ["geometry_audit", "master_structure_audit"])
def test_show_when_called_then_passes_title_routes_and_only(audit, monkeypatch, mod):
    module, env = audit
    owner = importlib.import_module(f"fontlabapp.fontui.{mod}")
    calls = []
    monkeypatch.setattr(owner, "show_snapshots", lambda *a, **k: calls.append((a, k)) or "shell")
    assert owner.show(only="X") == "shell"
    (title, table, about), kwargs = calls[0]
    assert title in ("Geometry Audit", "Master Structure Audit") and kwargs == dict(parent=None, only="X")
    assert "github.com/fontlabcom" in about


def _pairs():
    from fontlabapp.contours.dangerous_offcurves import model as off_model
    from fontlabapp.contours.near_miss import model as near_model, native as near_native
    from fontlabapp.contours.point_counts import native as counts
    from fontlabapp.contours.svg_path import model as svg_model, native as svg_native
    from fontlabapp.masters.layers.compatibility import model as layers_model, native as layers_native
    from fontlabapp.masters.node_report import model as node_model, native as node_native
    from fontlabapp.masters.point_counts import model as master_model, native as master_native

    return {
        "Close But No Cigar": (near_native.capture, near_model.render, "2 selected glyph occurrences. No font changes."),
        "Dangerous Offcurves": (None, off_model.render, "Dangerous Offcurves refreshed."),
        "Dump to Svg Path Commands": (svg_native.capture, svg_model.render, "2 own paths. No font or file changes."),
        "Point Counter (Master Layers)": (master_native.capture, master_model.render, "Snapshot: 2 master layers. Refresh after changes."),
        "Point Counter": (counts.capture, counts.render, "Snapshot: 2 selected occurrences. Refresh after changes."),
        "Master Node Compatibility Report": (node_native.capture, node_model.render, "2 unique selected glyphs. No font changes."),
        "Why You Not Compatible": (layers_native.capture, layers_model.render, "Snapshot: 2 selected occurrences. Refresh after changes."),
    }


@pytest.mark.parametrize("mod", ["geometry_audit", "master_structure_audit"])
def test_routes_when_built_then_each_tab_binds_its_own_capture_render_pair_and_status(audit, mod):
    pairs = _pairs()
    owner = importlib.import_module(f"fontlabapp.fontui.{mod}")
    for title, _description, capture, render, status in owner.routes():
        want_capture, want_render, want_status = pairs[title]
        assert render is want_render, title
        if want_capture is not None:  # Dangerous Offcurves wraps native.run() in a lambda
            assert capture is want_capture, title
        assert status([1, 2]) == want_status, title


def test_routes_when_dangerous_offcurves_captured_then_native_run_is_called(audit, monkeypatch):
    from fontlabapp.contours.dangerous_offcurves import native
    owner = importlib.import_module("fontlabapp.fontui.geometry_audit")
    monkeypatch.setattr(native, "run", lambda: "ran")
    capture = dict((r[0], r[2]) for r in owner.routes())["Dangerous Offcurves"]
    assert capture() == "ran"
