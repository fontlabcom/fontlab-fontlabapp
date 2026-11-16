# this_file: tests/test_master_text_delivery.py
"""Execute actual proof/sender/cleanup code on owned source-shaped carriers.

These tests verify the contract, never claim compiled FontLab binding/rendering.
"""

from types import SimpleNamespace as NS
import pytest
import fontlabapp.masters.text.capture as capture
import fontlabapp.masters.text.proof as proof
import fontlabapp.masters.text.sender as lifecycle
from fontlabapp.masters.text.model import analyze
from test_master_text_proof import host, Symbol, Symbols
from test_master_text_sender import Emitter


def delivery(monkeypatch):
    p, source, glyph, layers = host(monkeypatch)
    shape = NS(id=700, active=False)
    layers["R"].shapes.append(shape)
    opening = capture.read(100)
    comparison = analyze("aa,a", {97: "a"}, {"a"}, ("R", "B"), 1)

    class Block:
        def __init__(self, identity, package):
            self.id, self.package, self.symbols = identity, package, Symbols([])

        def symbolList(self):
            return self.symbols

    ws = NS(block=None, activeFontPanel=None)
    old = Block(10, p)
    ws.canvases = lambda: [NS(textBlocks=lambda: [old])]
    ws.getActiveTextBlock = lambda: ws.block
    ws.getActiveCanvas = lambda: ws.canvases()[0]  # native: the old canvas stays active
    events = []
    state = NS(create=lambda: None, send=lambda: None)
    emitter = Emitter()

    def set_text(text):
        emitter.texts.append(text)
        if text == "":
            events.append("create")
            ws.block = Block(100, p)
            state.create()

    emitter.setText = set_text

    def request(symbols, where):
        events.append("send")
        assert where == 0
        ws.block.symbols = symbols
        shape.active = True
        state.send()

    native = NS(
        fgSymbol=Symbol,
        fgSymbolList=Symbols,
        flTextBlock=Block,
        flCanvas=lambda raw: raw,
        flWorkspace=NS(instance=lambda: ws),
        MainWindow=lambda: "main",
        flItems=lambda: NS(requestContent=request),
    )
    monkeypatch.setattr(
        proof,
        "_native",
        lambda name: native
        if name == "fontlab"
        else NS(QtGui=NS(QLineEdit=lambda: emitter)),
    )
    monkeypatch.setattr(proof, "monotonic", lambda: 0)
    return NS(
        p=p,
        source=source,
        glyph=glyph,
        layers=layers,
        shape=shape,
        opening=opening,
        comparison=comparison,
        workspace=ws,
        old=old,
        native=native,
        events=events,
        emitter=emitter,
        state=state,
    )


def test_actual_complete_delivery_restores_shapes_keeps_font_and_exact_trailing_controls(
    monkeypatch,
):
    h = delivery(monkeypatch)
    proof.open_proof(h.opening, h.comparison, deadline=100)
    assert h.events == ["create", "send"] and h.emitter.deleted and not h.shape.active
    assert h.p.master == "R" and h.p.masters == ("R", "B")
    assert proof.signature(h.workspace.block.symbolList(), lambda: None)[-2:] == (
        ("", "", 32),
        ("", "", 10),
    )
    assert len(h.workspace.block.symbolList().values) == 12, (
        "Six named occurrences, four copy spaces and two group newlines"
    )


@pytest.mark.parametrize(
    "failure",
    [
        "old",
        "missing",
        "other",
        "panel",
        "master",
        "layer",
        "post_layer",
        "content",
        "main",
    ],
)
def test_actual_fresh_guard_and_complete_before_after_send_identity_refusals(
    monkeypatch, failure
):
    h = delivery(monkeypatch)
    if failure == "old":
        h.state.create = lambda: setattr(h.workspace, "block", h.old)
    elif failure == "missing":
        h.state.create = lambda: setattr(h.workspace, "block", None)
    elif failure == "other":
        h.state.create = lambda: setattr(h.workspace.block, "package", NS(id=999))
    elif failure == "panel":
        h.state.create = lambda: setattr(h.workspace, "activeFontPanel", object())
    elif failure == "master":
        h.state.create = lambda: setattr(h.p, "master", "B")
    elif failure == "layer":
        h.state.create = lambda: setattr(h.layers["B"], "id", 999)
    elif failure == "post_layer":
        h.state.send = lambda: setattr(h.layers["B"], "id", 999)
    elif failure == "content":
        h.state.send = lambda: setattr(h.workspace.block, "symbols", Symbols([]))
    else:
        h.native.MainWindow = lambda: None
    with pytest.raises(ValueError):
        proof.open_proof(h.opening, h.comparison, deadline=100)
    assert not h.shape.active
    if failure not in ("post_layer", "content"):
        assert "send" not in h.events, (
            "Never populate an old/stale/foreign/inactive target"
        )


def test_sender_and_shape_cleanup_failures_aggregate_and_retain_both_handles(
    monkeypatch,
):
    h = delivery(monkeypatch)
    h.emitter.disconnect_fail = True

    def restore(*args, **kwargs):
        proof.PENDING.append(NS(pending_states=args[0]))
        raise RuntimeError("shape restoration failure")

    monkeypatch.setattr(proof, "restore", restore)
    try:
        with pytest.raises(ExceptionGroup) as caught:
            proof.open_proof(h.opening, h.comparison, deadline=100)
        assert "shape restoration failure" in repr(caught.value)
        assert (
            lifecycle.PENDING[0].emitter is h.emitter
            and proof.PENDING[0].pending_states
        )
        with pytest.raises(ValueError, match="cleanup"):
            proof.open_proof(h.opening, h.comparison, deadline=100)
    finally:
        lifecycle.PENDING.clear()
        proof.PENDING.clear()


def test_deadline_cancellation_inside_complete_proof_loops_never_skips_cleanup(
    monkeypatch,
):
    h = delivery(monkeypatch)
    calls = []
    original = proof.checkpoint

    def count(*a):
        calls.append(1)
        return original(*a)

    monkeypatch.setattr(proof, "checkpoint", count)
    proof.open_proof(h.opening, h.comparison, deadline=100)
    total = len(calls)
    monkeypatch.setattr(proof, "checkpoint", original)
    # Every checkpoint across capture/stage/shapes/symbols/presend/postsend is
    # individually interrupted. Recovery gets its reserved uncancelled budget.
    for stop in range(1, total + 1):
        h = delivery(monkeypatch)
        count = []

        def cancelled():
            count.append(1)
            return len(count) == stop

        try:
            proof.open_proof(h.opening, h.comparison, deadline=100, cancelled=cancelled)
        except InterruptedError:
            assert not h.shape.active
            if h.emitter.connected:
                assert not h.emitter.deleted
        assert not proof.PENDING and not lifecycle.PENDING


def test_expired_native_primitive_retains_both_cleanup_fences_then_explicit_recovery(
    monkeypatch,
):
    from fontlabapp.glyphs.case_coverage.cleanup import recover as restore_shapes
    import fontlabapp.glyphs.case_coverage.cleanup as cleanup

    h = delivery(monkeypatch)
    clock = NS(now=0)
    monkeypatch.setattr(proof, "monotonic", lambda: clock.now)
    monkeypatch.setattr(cleanup, "monotonic", lambda: clock.now)
    h.state.send = lambda: setattr(clock, "now", 101)
    try:
        with pytest.raises(ExceptionGroup):
            proof.open_proof(h.opening, h.comparison, deadline=100)
        assert lifecycle.PENDING and proof.PENDING and h.shape.active
        assert h.emitter.connected and not h.emitter.deleted
        clock.now = 0
        lifecycle.recover(
            check=lambda: proof.checkpoint(100, lambda: clock.now, lambda: False)
        )
        restore_shapes(deadline=100)
        assert (
            not lifecycle.PENDING
            and not proof.PENDING
            and not h.shape.active
            and h.emitter.deleted
        )
    finally:
        proof.PENDING.clear()
        lifecycle.PENDING.clear()
