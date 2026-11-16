# this_file: tests/test_wp08_revision_metrics.py
"""S62 Font Revision Comparison and S63 Metric Reports reuse the original snapshot owners."""

import importlib
from pathlib import Path

import pytest

from _studio_qt import studio_qt  # noqa: F401
from test_wp08_snapshot_audit import audit  # noqa: F401


@pytest.mark.usefixtures("audit")
def test_revision_routes_when_built_then_each_tab_binds_its_own_owner_pair_and_status(monkeypatch):
    from fontlabapp.proof.crossfont import model, native
    owner = importlib.import_module("fontlabapp.fontui.font_revision_comparison")
    table = owner.routes()
    assert [r[0] for r in table] == ["Report Composite Differences", "Report Glyph Set Differences"]
    calls = []
    monkeypatch.setattr(native, "capture", lambda **kw: calls.append(kw) or "snap")
    assert table[0][2]() == "snap" and table[1][2]() == "snap"
    assert [set(c) for c in calls] == [{"composites", "deadline"}] * 2
    assert [c["composites"] for c in calls] == [True, False]
    # The render shares the capture's absolute deadline, so formatting stays bounded.
    seen, captured = [], []
    monkeypatch.setattr(native, "capture", lambda **kw: captured.append(kw["deadline"]) or "snap")
    monkeypatch.setattr(model, "composite_text", lambda snap, *, deadline=None: seen.append(deadline) or "t")
    monkeypatch.setattr(model, "glyph_sets_text", lambda snap, *, deadline=None: seen.append(deadline) or "t")
    table = owner.routes()
    table[0][2](); table[0][3]("snap"); table[1][2](); table[1][3]("snap")
    assert seen == captured and all(isinstance(d, float) for d in seen)
    assert table[0][4]("x") == "Current font → first other open font."
    assert table[1][4]("x") == "Current font → every other open font."
    assert all(r[1] for r in table)


@pytest.mark.usefixtures("audit")
def test_metric_routes_when_built_then_vertical_metrics_pair_and_status():
    from fontlabapp.metrics.vertical import model, native
    owner = importlib.import_module("fontlabapp.fontui.metric_reports")
    (title, description, capture, render, status), = owner.routes()
    assert title == "Vertical Metrics Reporter" and description
    assert capture is native.capture and render is model.render
    assert status(type("R", (), {"fonts": 3, "rows": (1, 2, 3, 4)})()) == "Snapshot: 3 fonts, 4 masters. Refresh after changes."


@pytest.mark.parametrize("mod,title", [
    ("font_revision_comparison", "Font Revision Comparison"),
    ("metric_reports", "Metric Reports"),
])
@pytest.mark.usefixtures("audit")
def test_show_when_called_then_passes_title_routes_and_only(monkeypatch, mod, title):
    owner = importlib.import_module(f"fontlabapp.fontui.{mod}")
    calls = []
    monkeypatch.setattr(owner, "show_snapshots", lambda *a, **k: calls.append((a, k)) or "shell")
    assert owner.show(only="X") == "shell"
    (got, table, about), kwargs = calls[0]
    assert got == title and kwargs == dict(parent=None, only="X") and "github.com/fontlabcom" in about


CREDITS = {
    "font_revision_comparison": ("Jens Kutilek", "MIT", "2017"),
    "metric_reports": ("Pedro Arilla", "Apache-2.0"),
    "geometry_audit": ("Simon Cozens", "Alex Slobzheninov", "Reza Bohloul", "independent implementation inspired by", "no code copied"),
    "master_structure_audit": ("Fernando D\u00edaz", "Reset Type Studio", "Simon Cozens"),
    "open_contours": ("original workflow", "FontLab App contributors (Apache-2.0)"),
    "nodes_near_zones": ("FontLab App contributors (Apache-2.0)",),
    "reference_images": ("FontLab App contributors (Apache-2.0)",),
}


@pytest.mark.usefixtures("audit")
@pytest.mark.parametrize("name", sorted(CREDITS))
def test_about_when_read_then_credits_the_actual_original_authors(name):
    about = importlib.import_module(f"fontlabapp.fontui.{name}").ABOUT
    for needle in CREDITS[name]:
        assert needle in about, (name, needle)


@pytest.mark.usefixtures("audit")
@pytest.mark.parametrize("name", ["open_contours", "nodes_near_zones", "metric_reports"])
def test_about_when_original_is_not_cozens_then_does_not_credit_him(name):
    assert "Cozens" not in importlib.import_module(f"fontlabapp.fontui.{name}").ABOUT


@pytest.mark.usefixtures("audit")
def test_capture_when_no_deadline_then_budget_is_exactly_3_5_seconds(monkeypatch):
    native = importlib.import_module("fontlabapp.proof.crossfont.native")
    seen = []
    monkeypatch.setattr(native, "require_main_thread", lambda: None)
    monkeypatch.setattr(native, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(native, "_read", lambda composites, deadline: seen.append(deadline) or "snap")
    monkeypatch.setattr(native, "check", lambda deadline: None)
    native.capture()
    assert seen == [1003.5, 1003.5]


@pytest.mark.usefixtures("audit")
def test_route_when_captured_then_deadline_is_clock_plus_3_5_for_capture_and_render(monkeypatch):
    import time

    from fontlabapp.proof.crossfont import model, native
    owner = importlib.import_module("fontlabapp.fontui.font_revision_comparison")
    monkeypatch.setattr(time, "monotonic", lambda: 2000.0)
    got = []
    monkeypatch.setattr(native, "capture", lambda **kw: got.append(kw["deadline"]) or "snap")
    monkeypatch.setattr(model, "composite_text", lambda snap, *, deadline=None: got.append(deadline) or "t")
    route = owner.routes()[0]
    route[2](); route[3]("snap")
    assert got == [2003.5, 2003.5]


def test_font_audit_about_when_read_then_credits_mekkablue_and_cozens():
    text = Path(importlib.import_module("fontlabapp.studios.font_audit.practical").__file__).read_text()
    for needle in ("mekkablue", "Simon Cozens (MIT)", "FontLab App contributors (Apache-2.0)"):
        assert needle in text, needle
