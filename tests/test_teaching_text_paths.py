# this_file: tests/test_teaching_text_paths.py
"""Path Problem Report: diagnosis, the two-pass tick scan and the panel, on real offscreen Qt."""

import json
import math
import sys
import threading
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


@pytest.fixture
def mod():
    from fontlabapp.fontui.teaching_text import paths

    return paths


def node(x, y, on=True):
    return NS(x=x, y=y, isOn=lambda: on)


def contour(points, closed=True):
    nodes = [node(*p) if len(p) == 2 else node(*p) for p in points]
    return NS(nodes=lambda: nodes, closed=closed)


SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]


def test_diagnose_when_clean_square_then_no_findings(mod):
    assert mod.diagnose([contour(SQUARE)], 4) == []


def test_diagnose_when_each_problem_then_one_record_each(mod):
    kinds = lambda c: [f["kind"] for f in mod.diagnose([c], 4)]  # noqa: E731
    assert kinds(contour(SQUARE, closed=False)) == ["open"]
    assert kinds(contour([(0, 0), (50, 50)])) == ["few-on-curve"]
    assert kinds(contour([(0, 0, False), (50, 50, False), (60, 70, False)])) == ["few-on-curve"]
    assert kinds(contour([(0, 0), (0, 0), (100, 0), (100, 100)])) == ["repeated-point"]
    assert kinds(contour([(0, 0), (1, 0), (1, 1), (0, 1)])) == ["small-extent"]
    assert kinds(contour([(0, 0), (4, 0), (4, 4), (0, 4)])) == []  # exactly the threshold is not small
    assert kinds(contour([(0, 0), (math.nan, 0), (1, 1)])) == ["nonfinite"]
    seam = mod.diagnose([contour([(0, 0), (100, 0), (100, 100), (0, 0)])], 4)
    assert seam == [{"contour": 1, "kind": "repeated-point", "node": 4, "point": [0.0, 0.0]}]
    empty = mod.diagnose([contour([])], 4)
    assert [f["kind"] for f in empty] == ["few-on-curve"] and empty[0]["count"] == 0
    small = mod.diagnose([contour([(0, 0), (1, 0), (1, 1), (0, 1)])], 4)[0]
    assert (small["width"], small["height"]) == (1.0, 1.0)


def test_diagnose_when_three_on_curve_nodes_then_not_few_and_two_is(mod):
    triangle = mod.diagnose([contour([(0, 0), (100, 0), (50, 100)])], 4)
    assert triangle == []  # exactly three on-curve nodes is enough
    two = mod.diagnose([contour([(0, 0), (100, 100)])], 4)
    assert [f["kind"] for f in two] == ["few-on-curve"] and two[0]["count"] == 2


def test_diagnose_when_single_closed_node_then_no_seam_repeat(mod):
    kinds = [f["kind"] for f in mod.diagnose([contour([(5, 5)])], 4)]
    assert kinds == ["few-on-curve", "small-extent"]  # one node has no neighbour to repeat


def test_diagnose_when_open_contour_ends_coincide_then_no_wrap_repeat(mod):
    open_loop = mod.diagnose([contour([(0, 0), (100, 0), (100, 100), (0, 0)], closed=False)], 4)
    assert [f["kind"] for f in open_loop] == ["open"]  # open endpoints stay distinct; no wrap comparison


@pytest.mark.parametrize("points", [[(0, 0), (100, 0), (100, 1), (0, 1)], [(0, 0), (1, 0), (1, 100), (0, 100)]])
def test_diagnose_when_only_one_extent_small_then_small_extent(mod, points):
    found = mod.diagnose([contour(points)], 4)
    assert [f["kind"] for f in found] == ["small-extent"]


@pytest.mark.parametrize("bad", [math.nan, math.inf, -1])
def test_diagnose_when_threshold_invalid_then_refused(mod, bad):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        mod.diagnose([], bad)


class Font:
    def __init__(self, names, fid=5):
        self.names, self.id = names, fid
        self.items = [NS(id=i, name=n) for i, n in enumerate(names)]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.items[i]


class Service:
    def __init__(self, font, contours):
        self.font, self.contours, self.package_alive = font, contours, True
        self.stamps = {n: 1000 + i for i, n in enumerate(font.names)}
        self.package = NS(id=3, fgId=font.id, master="Regular", findName=self.find)
        self.selected = []

    def find(self, name):
        if name not in self.stamps:
            return None
        layer = NS(getContours=lambda: self.contours.get(name, []))
        return NS(lastModified=NS(toMSecsSinceEpoch=lambda: self.stamps[name]),
                  findLayer=lambda master: None if name == "nolayer" else layer)

    def current_package(self, expected=None):
        return self.package if self.package_alive else None

    def select_glyphs(self, names, package_id):
        self.selected = (list(names), package_id)
        return names


def scan_of(mod, names, contours=None, threshold=4, **kw):
    font = Font(names)
    service = Service(font, contours or {})
    native = NS(CurrentFont=lambda: font)
    return mod.Scan(threshold, service, native, **kw), service, font


def run_to_end(scan, limit=100):
    for _ in range(limit):
        result = scan.step()
        if result is not None:
            return result
    raise AssertionError("scan never finished")


def test_scan_when_two_passes_then_report_after_verification_only(mod):
    names = ["a", "nolayer", "c"]
    scan, service, font = scan_of(mod, names, {"a": [contour(SQUARE, closed=False)]})
    assert scan.progress() == "Scanning 0 / 3 glyphs"
    assert scan.step() is None and scan.checking and scan.progress() == "Checking 0 / 3 glyphs"
    report = run_to_end(scan)
    assert report["schema"] == 1 and report["glyphs_scanned"] == 3 and report["master"] == "Regular"
    assert report["missing_layers"] == ["nolayer"] and list(report["problems"]) == ["a"]
    assert report["package_id"] == 3 and report["min_extent"] == 4


def test_scan_when_budget_spent_then_next_tick_continues(mod):
    names = [f"g{i}" for i in range(40)]
    ticks = iter(range(10**6))
    scan, service, font = scan_of(mod, names, clock=lambda: next(ticks) * 1.0)
    scan.step()
    assert 0 < scan.index < 40  # one glyph handed out, then the deadline passed
    assert run_to_end(scan)["glyphs_scanned"] == 40


def test_scan_when_32_glyph_cap_then_tick_ends(mod):
    scan, service, font = scan_of(mod, [f"g{i}" for i in range(70)], clock=lambda: 0.0)
    scan.step()
    assert scan.index == 32


def test_scan_when_things_change_then_refused(mod):
    scan, service, font = scan_of(mod, ["a", "b"])
    scan.step()  # first pass completes
    service.stamps["a"] = 999999
    with pytest.raises(ValueError, match="glyphs changed"):
        scan.step()
    scan, service, font = scan_of(mod, ["a"])
    service.stamps.clear()
    with pytest.raises(ValueError, match="glyphs changed"):
        scan.step()
    scan, service, font = scan_of(mod, ["a"])
    service.package_alive = False
    with pytest.raises(ValueError, match="master changed"):
        scan.step()
    scan, service, font = scan_of(mod, ["a"])
    font.items.append(NS(id=9, name="z"))
    with pytest.raises(ValueError, match="master changed"):
        scan.step()


def test_scan_when_constructed_badly_then_refused(mod):
    font = Font(["a"])
    service = Service(font, {})
    service.package_alive = False
    with pytest.raises(ValueError, match="Open a font"):
        mod.Scan(4, service, NS(CurrentFont=lambda: font))
    service.package_alive = True
    with pytest.raises(ValueError, match="font changed"):
        mod.Scan(4, service, NS(CurrentFont=lambda: Font(["a"], fid=99)))
    with pytest.raises(ValueError, match="font changed"):
        mod.Scan(4, service, NS(CurrentFont=lambda: None))
    with pytest.raises(ValueError, match="finite and nonnegative"):
        mod.Scan(-1, service, NS(CurrentFont=lambda: font))


def test_scan_when_off_main_thread_then_refused(mod):
    scan, service, font = scan_of(mod, ["a"])
    errors = []

    def work():
        try:
            scan.step()
        except RuntimeError as error:
            errors.append(str(error))

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    assert errors == ["Scan on the main UI thread."]


def test_scan_when_default_service_and_native_then_resolved_lazily(mod, monkeypatch):
    import fontlabapp
    import fontlabapp.core.scripting as scripting

    font = Font(["a"])
    service = Service(font, {})
    monkeypatch.setattr(scripting, "current_package", service.current_package)
    monkeypatch.setattr(fontlabapp, "_native", lambda name: NS(CurrentFont=lambda: font), raising=False)
    assert mod.Scan(4).total == 1


def test_report_text_and_export(mod, tmp_path):
    report = {"a": "é", "n": 1}
    assert mod.report_text(report) == json.dumps(report, ensure_ascii=True, indent=2) + "\n" and "\\u00e9" in mod.report_text(report)
    with pytest.raises(ValueError):
        mod.report_text({"x": math.nan})
    target = tmp_path / "r.json"
    mod.export_report(str(target), report)
    assert json.loads(target.read_text()) == report
    with pytest.raises(FileExistsError):
        mod.export_report(str(target), report)
    with pytest.raises(ValueError, match="absolute"):
        mod.export_report("r.json", report)
    with pytest.raises(ValueError, match="Qt cannot preserve"):
        mod.export_report(str(tmp_path / "a b.json"), report)


@pytest.fixture
def paths(lab, monkeypatch):  # noqa: F811
    module, shown = lab("paths")
    import fontlabapp
    import fontlabapp.core.scripting as scripting

    qt = sys.modules["PythonQt"]
    parent = qt.QtGui.QWidget()
    font = Font(["a", "b"])
    service = Service(font, {"a": [contour(SQUARE, closed=False)]})
    monkeypatch.setattr(scripting, "current_package", service.current_package)
    monkeypatch.setattr(scripting, "select_glyphs", service.select_glyphs)
    monkeypatch.setattr(fontlabapp, "_native", lambda name: NS(CurrentFont=lambda: font, MainWindow=lambda: parent) if name == "fontlab" else sys.modules[name], raising=False)
    yield module, qt, parent, service
    module._PANELS.clear()


def click(panel, qt, text):
    [b for b in panel.findChildren(qt.QtGui.QPushButton) if b.text() == text][0].click()


def finish(panel):
    for _ in range(20):
        if panel.result is not None:
            return
        panel.scan_step()


def test_panel_when_refreshed_then_ticks_publish_report_and_selection_and_export_work(paths, tmp_path):
    module, qt, parent, service = paths
    panel = module.show(qt, parent, embedded=True)
    assert panel in module._PANELS and panel.scan_work is not None
    assert panel.status_line.text().startswith("Scanning the current master")
    finish(panel)
    assert panel.result["problems"].keys() == {"a"} and "1 findings; 2 glyphs scanned" in panel.status_line.text()
    assert json.loads(panel.preview.toPlainText())["glyphs_scanned"] == 2
    hooks = []
    panel.lab_refresh_preview = lambda: hooks.append(1)
    click(panel, qt, "Select glyphs with findings")
    assert service.selected == (["a"], 3) and panel.status_line.text() == "Selected 1 glyphs with findings."
    panel.destination.setText(str(tmp_path / "out.json"))
    click(panel, qt, "Export")
    assert (tmp_path / "out.json").exists() and panel.status_line.text().startswith("Captured report exported")
    click(panel, qt, "Export")
    assert "exists" in panel.status_line.text().lower()
    click(panel, qt, "Cancel")
    assert panel.result is None and panel.preview.toPlainText() == ""
    assert panel.progress_line.text() == "Cancelled; no partial report kept."


def test_panel_when_no_report_or_no_findings_then_actions_refused(paths):
    module, qt, parent, service = paths
    panel = module.show(qt, parent, embedded=True)
    panel.cancel_scan()
    click(panel, qt, "Select glyphs with findings")
    assert panel.status_line.text() == "Finish a report first."
    click(panel, qt, "Export")
    assert panel.status_line.text() == "Refresh a report from an open font first."
    panel.result = {"problems": {}, "package_id": 3}
    click(panel, qt, "Select glyphs with findings")
    assert "no glyphs with findings" in panel.status_line.text()
    panel.scan_work = None
    panel.scan_step()  # nothing to do


def test_panel_when_scan_fails_then_cancelled_with_reason(paths):
    module, qt, parent, service = paths
    panel = module.show(qt, parent, embedded=True)
    service.stamps["a"] = 7
    panel.scan_work.step()
    service.stamps["a"] = 8
    for _ in range(5):
        panel.scan_step()
    assert panel.status_line.text() == "Font glyphs changed; refresh the report." and panel.scan_work is None
    service.package_alive = False
    click(panel, qt, "Refresh")
    assert panel.status_line.text() == "Open a font first."


def test_panel_when_closed_or_destroyed_then_released_or_retained(paths):
    module, qt, parent, service = paths
    panel = module.show(qt, parent, embedded=True)
    event = NS(ignored=False, accepted=False)
    event.ignore, event.accept = (lambda: setattr(event, "ignored", True)), (lambda: setattr(event, "accepted", True))
    panel.scope.finish = lambda destroyed=False: False
    panel.closeEvent(event)
    assert event.ignored and panel in module._PANELS
    del panel.scope.finish
    panel.closeEvent(event)
    assert event.accepted and panel not in module._PANELS
    other = module.show(qt, parent, embedded=True)
    other.release_owner()
    assert other not in module._PANELS and other.scan_work is None
    other.release_owner()


def test_show_when_start_fails_then_cleaned_up_and_main_build(paths, monkeypatch, capsys):
    module, qt, parent, service = paths
    shown_panel = module.show(qt, parent)
    assert shown_panel.isVisible()
    shown_panel.close()
    shown_panel.deleteLater()
    module._PANELS.clear()
    with monkeypatch.context() as local:
        local.setattr(qt.QtGui.QWidget, "show", lambda self: (_ for _ in ()).throw(RuntimeError("no screen")))
        with pytest.raises(RuntimeError, match="no screen"):
            module.show(qt, parent)
    assert module._PANELS == []
    seen = []
    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: parent))
    monkeypatch.setattr(module, "show", lambda q, p: seen.append(p))
    module.main()
    assert seen == [parent]
    monkeypatch.setattr(module, "show", lambda q, p: (_ for _ in ()).throw(ValueError("nope")))
    module.main()
    assert capsys.readouterr().out == f"{module.TITLE}: nope\n"
