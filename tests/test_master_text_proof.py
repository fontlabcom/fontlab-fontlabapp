# this_file: tests/test_master_text_proof.py
"""Owned native-shaped carriers exercise full preflight and retained cleanup."""

from types import SimpleNamespace as NS
import pytest
import fontlabapp.masters.text.capture as capture
import fontlabapp.masters.text.proof as proof
from fontlabapp.masters.text.model import analyze


def host(monkeypatch):
    monkeypatch.setattr(capture, "monotonic", lambda: 0)
    layers = {
        m: NS(id=i, isNull=False, shapes=[]) for i, m in enumerate(("R", "B"), 20)
    }
    glyph = NS(
        id=10,
        name="a",
        isNull=False,
        layers=list(layers.values()),
        findLayer=layers.get,
    )
    package = NS(
        id=1,
        fgId=2,
        master="R",
        masters=("R", "B"),
        findName=lambda n: glyph if n == "a" else None,
    )
    source = NS(
        identity=1,
        fg_id=2,
        label="Owned",
        masters=("R", "B"),
        names=("a",),
        package=package,
        font=NS(glyphs=[NS(name="a", unicodes=[97])]),
    )
    monkeypatch.setattr(capture, "fonts", lambda *a, **k: (source,))
    monkeypatch.setattr(capture, "current_package", lambda *a: package)
    return package, source, glyph, layers


def test_capture_fences_complete_opening_font_master_glyph_and_unicode(monkeypatch):
    p, source, glyph, layers = host(monkeypatch)
    opening = capture.read(100, check=lambda: None)
    capture.validate(opening, 100, check=lambda: None)
    p.masters = ("B", "R")
    with pytest.raises(ValueError, match="changed"):
        capture.validate(opening, 100)
    p.masters = ("R", "B")
    glyph.id = 999
    with pytest.raises(ValueError, match="changed"):
        capture.validate(opening, 100)
    glyph.id = 10
    source.font.glyphs[0].unicodes = [65]
    with pytest.raises(ValueError, match="changed"):
        capture.validate(opening, 100)
    monkeypatch.setattr(capture, "current_package", lambda *a: None)
    with pytest.raises(ValueError, match="font"):
        capture.read(100)


class Symbol:
    def __init__(self, value):
        self.name = value if isinstance(value, str) else ""
        self.unicode = value if isinstance(value, int) else 0
        self.layerName = ""


class Symbols:
    def __init__(self, values):
        self.values = values

    def symbols(self):
        return self.values


def test_stage_preserves_literal_delimiters_named_controls_and_exact_layers(
    monkeypatch,
):
    p, source, _, layers = host(monkeypatch)
    opening = capture.read(100)
    comparison = analyze("a,a", {97: "a"}, {"a"}, ("R", "B"), 1)
    native = NS(fgSymbol=Symbol, fgSymbolList=Symbols)
    staged, identities, expected = proof.stage(
        native, opening, source, comparison, lambda: None
    )
    assert (
        expected
        == (("a", "R", 0), ("", "", 32), ("a", "B", 0), ("", "", 32), ("", "", 10)) * 2
    )
    assert len(identities) == 4 and identities[0] == ("a", 10, "R", 20)
    assert proof.signature(staged, lambda: None) == expected
    layers["R"].isNull = True
    with pytest.raises(ValueError, match="layer"):
        proof.stage(native, opening, source, comparison, lambda: None)


def test_stage_refuses_lossy_names_allocation_and_cancel(monkeypatch):
    p, source, _, _ = host(monkeypatch)
    opening = capture.read(100)
    comparison = analyze("a", {97: "a"}, {"a"}, ("R", "B"), 1)

    class Lossy(Symbol):
        def __init__(self, value):
            super().__init__(value)
            self.name = "changed"

    with pytest.raises(ValueError, match="represent"):
        proof.stage(
            NS(fgSymbol=Lossy, fgSymbolList=Symbols),
            opening,
            source,
            comparison,
            lambda: None,
        )

    def stop():
        raise TimeoutError("cancel")

    with pytest.raises(TimeoutError):
        proof.stage(NS(fgSymbol=Symbol), opening, source, comparison, stop)


def test_proof_full_preflight_fresh_guard_actual_readback_and_cleanup(monkeypatch):
    p, source, _, _ = host(monkeypatch)
    opening = capture.read(100)
    comparison = analyze("a", {97: "a"}, {"a"}, ("R", "B"), 0)
    workspace = NS(
        activeFontPanel=None,
        getActiveTextBlock=lambda: None,
        getActiveCanvas=lambda: None,
        canvases=lambda: [],
    )
    native = NS(
        fgSymbol=Symbol,
        fgSymbolList=Symbols,
        flWorkspace=NS(instance=lambda: workspace),
    )
    monkeypatch.setattr(
        proof, "_native", lambda name: native if name == "fontlab" else NS(QtGui=NS())
    )
    monkeypatch.setattr(proof, "monotonic", lambda: 0)
    events = []

    def fresh(
        native,
        ws,
        opening,
        source,
        symbols,
        identities,
        expected,
        previous_ids,
        check,
        cleanup,
        deadline,
    ):
        events.append("fresh")
        workspace.block = NS(id=100, package=p, symbolList=lambda: symbols)

    monkeypatch.setattr(proof, "fresh", fresh)
    monkeypatch.setattr(proof, "active_model", lambda *a: workspace.block)
    monkeypatch.setattr(proof, "remember", lambda *a: {1: (NS(active=False), False)})
    monkeypatch.setattr(
        proof,
        "restore",
        lambda *a, **k: events.append(("restore", k["context_pending"])),
    )
    proof.open_proof(opening, comparison, deadline=100)
    assert events == ["fresh", ("restore", False)]

    def fail(*a):
        raise ValueError("No new exact proof target became active")

    monkeypatch.setattr(proof, "fresh", fail)
    with pytest.raises(ValueError, match="No new"):
        proof.open_proof(opening, comparison, deadline=100)
    assert events[-1] == ("restore", False)
    proof.PENDING.append("owned")
    try:
        with pytest.raises(ValueError, match="cleanup"):
            proof.open_proof(opening, comparison, deadline=100)
    finally:
        proof.PENDING.clear()


def test_content_verification_includes_final_delimiters():
    with pytest.raises(ValueError, match="content"):
        proof.verify_content(
            Symbols([Symbol("a")]), (("a", "", 0), ("", "", 10)), lambda: None
        )


def test_capture_deadline_complete_unicode_and_all_identity_refusals(monkeypatch):
    p, source, glyph, _ = host(monkeypatch)
    calls = []
    opening = capture.read(100, check=lambda: calls.append(1))
    for stop_at in range(1, len(calls) + 1):
        count = []

        def cancelled():
            count.append(1)
            if len(count) == stop_at:
                raise InterruptedError("capture cancelled")

        with pytest.raises(InterruptedError):
            capture.read(100, check=cancelled)
    monkeypatch.setattr(capture, "monotonic", lambda: 101)
    with pytest.raises(TimeoutError):
        capture.read(100)
    monkeypatch.setattr(capture, "monotonic", lambda: 0)
    glyph.isNull = True
    with pytest.raises(ValueError, match="glyph"):
        capture.read(100)
    glyph.isNull = False
    monkeypatch.setattr(capture, "fonts", lambda *a, **k: ())
    with pytest.raises(ValueError, match="registered"):
        capture.read(100)
    with pytest.raises(ValueError, match="closed"):
        capture.validate(opening, 100)
