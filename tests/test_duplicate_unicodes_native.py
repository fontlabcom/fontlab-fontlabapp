# this_file: tests/test_duplicate_unicodes_native.py
"""Owned binding doubles verify real ordered writes and failure finalization."""

from types import SimpleNamespace as NS

import fontlabapp.glyphs.unicode.duplicates.native as api
import pytest


class Record:
    def __init__(self, name, codes, log, fail=False, corrupt=False):
        self.name, self._codes, self.log = name, list(codes), log
        self.fail, self.corrupt = fail, corrupt

    @property
    def unicodes(self):
        return self._codes

    @unicodes.setter
    def unicodes(self, codes):
        self.log.append(("write", self.name, tuple(codes)))
        self._codes = list(codes) + ([999] if self.corrupt else [])
        if self.fail:
            raise RuntimeError("owned setter failed after mutation")


def setup(monkeypatch):
    log = []
    layers = [
        NS(
            id=11 + i,
            name="Regular",
            autoLayer=False,
            shapes=[],
            checkInitHistoryState=lambda zero: log.append(("history", zero)),
        )
        for i in range(2)
    ]
    glyphs = [
        NS(
            id=i + 1,
            fgGlyphId=i + 101,
            name=name,
            layers=[layer],
            lastModified="old",
            checkInitHistoryState=lambda zero: log.append(("history", zero)),
        )
        for i, (name, layer) in enumerate(zip(("A", "B"), layers))
    ]
    package = NS(
        id=7,
        fgId=8,
        master="Regular",
        masters=["Regular"],
        findFgId=lambda identity: next(
            (g for i, g in enumerate(glyphs) if i + 101 == identity), None
        ),
        findName=lambda name: next(g for g in glyphs if g.name == name),
    )
    records = [Record("A", [65, 66], log), Record("B", [65, 66], log)]
    font = NS(id=8, glyphs=records)
    for i, record in enumerate(records):
        record.id = 101 + i
    for glyph in glyphs:
        glyph.package = package
        glyph.isNull = False
        glyph.isValid = True
    native = NS(
        CurrentFont=lambda: font,
        flWorkspace=NS(instance=lambda: NS(currentPackage=package)),
        flGlyph=NS(updatedFgGlyphs=list),
        flItems=lambda: NS(
            notifyChangesApplied=lambda title, items: log.append(
                ("notify", title, tuple(x.id for x in items))
            )
        ),
    )
    qt = NS(
        QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "stamp")),
        QtGui=NS(QApplication=NS(allWidgets=lambda: [NS(inherits=lambda name: False)])),
    )
    monkeypatch.setattr(api, "current_package", lambda: package)
    monkeypatch.setattr(
        api, "_native", lambda name: native if name == "fontlab" else qt
    )
    monkeypatch.setattr(
        api, "_context", lambda deadline: ((7, 8, "Regular"), package, font)
    )
    monkeypatch.setattr(api, "_stamp", lambda glyph: (glyph.lastModified,))
    monkeypatch.setattr(
        api, "require_font_window", lambda identity: log.append(("window", identity))
    )
    return log, package, font, native, glyphs, layers


def test_complete_capture_and_removal_one_final_history_no_updateall(monkeypatch):
    log, _p, f, _n, g, _l = setup(monkeypatch)
    backend = api.Backend()
    facts = backend.capture()
    result = backend.apply(facts, [("B", 65), ("A", 66)])
    assert result == {"changed": ["A", "B"], "removals": 2}
    assert [r.unicodes for r in f.glyphs] == [[65], [66]]
    assert sum(x[0] == "notify" for x in log) == 1
    assert max(i for i, x in enumerate(log) if x[0] == "history") < min(
        i for i, x in enumerate(log) if x[0] == "write"
    )
    assert [x for x in log if x[0] == "notify"] == [
        ("notify", "Duplicate Unicodes", (12, 11, 2, 1))
    ]
    assert all(x.lastModified == "stamp" for x in g)


def test_empty_plan_never_initializes_history_or_writes(monkeypatch):
    log, _p, _f, _n, _g, _l = setup(monkeypatch)
    b = api.Backend()
    facts = b.capture()
    assert b.apply(facts, []) == {"changed": [], "removals": 0}
    assert log == []


@pytest.mark.parametrize("mode", ["setter", "corruption", "notify"])
def test_partial_failure_is_explicit_and_still_finalizes_once(monkeypatch, mode):
    log, _p, f, n, _g, _l = setup(monkeypatch)
    b = api.Backend()
    facts = b.capture()
    if mode == "setter":
        f.glyphs[1].fail = True
    if mode == "corruption":
        f.glyphs[1].corrupt = True
    if mode == "notify":

        def fail(title, items):
            log.append(("notify-fail",))
            raise RuntimeError("owned notification failed")

        n.flItems = lambda: NS(notifyChangesApplied=fail)
    with pytest.raises(api.PartialWriteError, match="Undo") as error:
        b.apply(facts, [("A", 65), ("B", 65)])
    assert error.value.attempted == 2
    assert sum(x[0].startswith("notify") for x in log) == 1
    assert f.glyphs[0].unicodes == [66]


@pytest.mark.parametrize("block", ["queue", "auto", "dependant", "window", "stale"])
def test_all_precise_preflight_refusals_happen_before_history(monkeypatch, block):
    log, _p, f, n, _g, l = setup(monkeypatch)
    if block == "auto":
        l[1].autoLayer = True
    if block == "dependant":
        l[0].autoLayer = True
        l[0].shapes = [NS(isComponent=True, shapeData=NS(componentGlyph="B"))]
    b = api.Backend()
    facts = b.capture()
    if block == "queue":
        n.flGlyph.updatedFgGlyphs = lambda: [123]
    if block == "stale":
        f.glyphs[0]._codes = [90]
    if block == "window":
        monkeypatch.setattr(
            api,
            "require_font_window",
            lambda identity: (_ for _ in ()).throw(ValueError("Font window")),
        )
    with pytest.raises(ValueError):
        b.apply(facts, [("B", 65)])
    assert not any(x[0] in ("history", "write", "notify") for x in log)


def test_stale_identity_and_midcapture_drift_are_refused(monkeypatch):
    _log, p, f, _n, _g, _l = setup(monkeypatch)
    calls = []

    def context(deadline):
        calls.append(1)
        return ((7 + len(calls), 8, "Regular"), p, f)

    monkeypatch.setattr(api, "_context", context)
    with pytest.raises(ValueError, match="changed"):
        api.Backend().capture()


def test_missing_font_is_a_valid_empty_panel_snapshot(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(api, "current_package", lambda: None)
    assert api.Backend().capture() is None


def test_absolute_deadline_and_main_thread_are_required(monkeypatch):
    setup(monkeypatch)
    with pytest.raises(TimeoutError):
        api.Backend().capture(deadline=0)
    monkeypatch.setattr(api, "current_thread", lambda: None)
    with pytest.raises(RuntimeError):
        api.Backend().capture()


@pytest.mark.parametrize(
    "mode", ["missing", "owner", "name", "fgid", "shared-layer", "invalid-code"]
)
def test_complete_capture_refuses_malformed_or_changed_native_domain(monkeypatch, mode):
    log, p, f, _n, g, l = setup(monkeypatch)
    if mode == "missing":
        p.findFgId = lambda identity: None
    if mode == "owner":
        g[0].package = NS(id=999)
    if mode == "name":
        g[0].name = "other"
    if mode == "fgid":
        g[0].fgGlyphId = 999
    if mode == "shared-layer":
        l[1].id = l[0].id
    if mode == "invalid-code":
        f.glyphs[0]._codes = [0x110000]
    with pytest.raises(ValueError):
        api.Backend().capture()
    assert log == []


def test_whole_scan_catches_component_dependency_and_queue_that_appears_last(
    monkeypatch,
):
    log, _p, _f, n, _g, l = setup(monkeypatch)
    l[0].shapes = [NS(isComponent=False)]
    backend = api.Backend()
    facts = backend.capture()
    original = backend.capture
    calls = []

    def capture(**kwargs):
        result = original(**kwargs)
        calls.append(1)
        if len(calls) == 2:
            n.flGlyph.updatedFgGlyphs = lambda: [42]
        return result

    monkeypatch.setattr(backend, "capture", capture)
    with pytest.raises(ValueError, match="pending"):
        backend.apply(facts, [("B", 65)])
    assert not any(x[0] in ("history", "write", "notify") for x in log)


def test_missing_manual_layers_refuses_before_history(monkeypatch):
    log, _p, _f, _n, g, _l = setup(monkeypatch)
    g[1].layers = []
    b = api.Backend()
    facts = b.capture()
    with pytest.raises(ValueError, match="manual layers"):
        b.apply(facts, [("B", 65)])
    assert not any(x[0] in ("history", "write", "notify") for x in log)


def test_failed_first_setter_does_not_stamp_or_notify_unattempted_glyph(monkeypatch):
    log, _p, f, _n, g, _l = setup(monkeypatch)
    b = api.Backend()
    facts = b.capture()
    f.glyphs[0].fail = True
    with pytest.raises(api.PartialWriteError) as error:
        b.apply(facts, [("A", 65), ("B", 65)])
    assert error.value.attempted == 1 and error.value.changed == ()
    assert g[0].lastModified == "stamp" and g[1].lastModified == "old"
    assert [x for x in log if x[0] == "notify"] == [
        ("notify", "Duplicate Unicodes", (11, 1))
    ]


def test_inactive_open_glyph_editor_refuses_before_history(monkeypatch):
    log, _p, _f, _n, _g, _l = setup(monkeypatch)
    b = api.Backend()
    facts = b.capture()
    qt = api._native("PythonQt")
    qt.QtGui = NS(
        QApplication=NS(
            allWidgets=lambda: [NS(inherits=lambda name: name == "GlyphWindow")]
        )
    )
    with pytest.raises(ValueError, match="Close.*Glyph"):
        b.apply(facts, [("B", 65)])
    assert not any(x[0] in ("history", "write", "notify") for x in log)


@pytest.mark.parametrize("mode", ["unknown-class", "read-error"])
def test_unreadable_open_editor_state_refuses_before_history(monkeypatch, mode):
    log, _p, _f, _n, _g, _l = setup(monkeypatch)
    b = api.Backend()
    facts = b.capture()

    def inherits(name):
        if mode == "read-error":
            raise RuntimeError("owned class query error")

    qt = api._native("PythonQt")
    qt.QtGui = NS(QApplication=NS(allWidgets=lambda: [NS(inherits=inherits)]))
    with pytest.raises((ValueError, RuntimeError)):
        b.apply(facts, [("B", 65)])
    assert not any(x[0] in ("history", "write", "notify") for x in log)
