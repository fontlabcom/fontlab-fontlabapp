# this_file: tests/test_case_coverage_proof.py
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
import fontlabapp.glyphs.case_coverage.proof as proof
from fontlabapp.glyphs.case_coverage.model import Options
from fontlabapp.glyphs.case_coverage.capture import Snapshot, FontReport
from fontlabapp.glyphs.case_coverage.targets import TargetChoiceRequired


@pytest.fixture
def host(monkeypatch):
    shape = NS(id=90, active=False)
    layer = NS(id=91, isNull=False, shapes=[shape])
    glyph = NS(isNull=False, layers=[layer], findLayer=lambda name: layer)
    packages = {
        i: NS(id=i, fgId=i * 10, master="Regular", findName=lambda name: glyph)
        for i in (1, 2)
    }
    carriers = tuple(
        NS(identity=i, fg_id=i * 10, package=p, names=("A", "a"))
        for i, p in packages.items()
    )

    def canvas(cid, pid):
        block = NS(id=cid + 100, package=packages[pid], contents=[])
        block.symbolList = lambda: NS(symbols=lambda: block.contents)
        return NS(id=cid, textBlocks=lambda: [block])

    a, b = canvas(10, 1), canvas(20, 2)
    state = NS(
        canvases=[a, b],
        active=a,
        current=1,
        calls=[],
        shape=shape,
        packages=packages,
        layer=layer,
    )
    workspace = NS(
        activeFontPanel=None,
        canvases=lambda: state.canvases,
        getActiveCanvas=lambda: state.active,
        getActiveTextBlock=lambda: None
        if state.active is None
        else state.active.textBlocks()[0],
    )
    workspace.setActiveCanvas = lambda c: setattr(state, "active", c)

    def tool(name, **kwargs):
        state.current = kwargs["font_id"] // 10
        state.calls.append((name, kwargs))

    def request(symbols, zero):
        state.calls.append(("reuse", state.active.id, symbols))
        shape.active = True
        state.active.textBlocks()[0].contents = symbols

    native = NS(
        flTextBlock=NS,
        flWorkspace=NS(instance=lambda: workspace),
        flCanvas=lambda c: c,
        fgSymbol=lambda name: NS(name=name),
        fgSymbolList=lambda values: list(values),
        flItems=lambda: NS(requestContent=request),
    )
    monkeypatch.setattr(
        proof,
        "_native",
        lambda name: native
        if name == "fontlab"
        else (NS(QtGui=object()) if name == "PythonQt" else NS(call=tool)),
    )
    monkeypatch.setattr(proof, "fonts", lambda deadline, *, checkpoint=None: carriers)
    monkeypatch.setattr(
        proof,
        "current_package",
        lambda expected=None: packages.get(state.current)
        if expected in (None, state.current)
        else None,
    )

    def fresh(native, workspace, identity, symbols, expected, previous, check, gui):
        state.calls.append(("fresh", identity, expected))
        c = canvas(30 + len(state.canvases), identity)
        state.canvases.append(c)
        state.active = c
        shape.active = True
        c.textBlocks()[0].contents = symbols

    monkeypatch.setattr(proof, "_fresh", fresh)
    reports = tuple(
        FontReport(
            i,
            i * 10,
            f"Font {i}",
            "Regular",
            dict(proof=["A", "a", "A"], all_clear=False),
        )
        for i in (1, 2)
    )
    state.snapshot = Snapshot(1, reports)
    return state, workspace


def test_allfont_reuse_exact_named_layer_order_and_restore(host):
    state, workspace = host
    proof.open_proofs(state.snapshot, Options(), deadline=float("inf"))
    reused = [r for r in state.calls if r[0] == "reuse"]
    assert [r[1] for r in reused] == [10, 20]
    assert [(s.name, s.layerName) for s in reused[1][2]] == [
        ("A", "Regular"),
        ("a", "Regular"),
        ("A", "Regular"),
    ]
    assert state.current == 1 and state.active.id == 10 and not state.shape.active


def test_fresh_or_missing_view_and_ambiguous_explicit_selection(host):
    state, workspace = host
    proof.open_proofs(state.snapshot, Options(reuseTab=False), deadline=float("inf"))
    assert len([r for r in state.calls if r[0] == "fresh"]) == 2
    state.calls.clear()
    with pytest.raises(TargetChoiceRequired) as caught:
        proof.open_proofs(state.snapshot, Options(), deadline=float("inf"))
    candidates = caught.value.targets[2]
    assert len(candidates) == 2 and state.calls == []
    target = candidates[1]
    proof.open_proofs(
        state.snapshot,
        Options(),
        deadline=float("inf"),
        choices={2: (target.canvas_id, target.block_id)},
    )
    assert any(r[0] == "reuse" and r[1] == target.canvas_id for r in state.calls)
    state.canvases = state.canvases[:1]
    state.calls.clear()
    proof.open_proofs(state.snapshot, Options(), deadline=float("inf"))
    assert any(r[0] == "fresh" and r[1] == 2 for r in state.calls)


def test_stale_layer_cancel_and_switched_target_refuse_before_population(host):
    state, workspace = host
    state.layer.isNull = True
    with pytest.raises(ValueError, match="layer"):
        proof.open_proofs(state.snapshot, Options(), deadline=float("inf"))
    assert state.calls == []
    state.layer.isNull = False
    with pytest.raises(InterruptedError):
        proof.open_proofs(
            state.snapshot, Options(), deadline=float("inf"), cancelled=lambda: True
        )
    with pytest.raises(TimeoutError):
        proof.open_proofs(state.snapshot, Options(), deadline=0)
    original = workspace.setActiveCanvas
    workspace.setActiveCanvas = lambda c: original(state.canvases[0])
    with pytest.raises(ValueError, match="target"):
        proof.open_proofs(state.snapshot, Options(), deadline=float("inf"))
    assert not any(r[0] == "reuse" and r[1] == 20 for r in state.calls)
    assert not state.shape.active


def test_active_wrapper_model_normalization_and_missing_binding_fail_closed():
    class Model:
        pass

    model = Model()
    native = NS(flTextBlock=Model)
    workspace = NS(getActiveTextBlock=lambda: None, getActiveCanvas=lambda: None)
    assert proof._active_model(native, workspace) is None
    workspace.getActiveTextBlock = lambda: NS(textBlock=lambda: model)
    assert proof._active_model(native, workspace) is model
    workspace.getActiveTextBlock = lambda: NS(id=99)
    with pytest.raises(ValueError, match="model identity"):
        proof._active_model(native, workspace)


def test_no_findings_no_native_access_and_original_font_stale(host):
    state, workspace = host
    empty = Snapshot(
        1,
        tuple(
            FontReport(r.identity, r.fg_id, r.label, r.master, dict(proof=[]))
            for r in state.snapshot.fonts
        ),
    )
    proof.open_proofs(empty, Options(), deadline=float("inf"))
    assert state.calls == []
    state.current = 2
    with pytest.raises(ValueError, match="current source"):
        proof.open_proofs(state.snapshot, Options(), deadline=float("inf"))


def test_failed_population_still_restores_flags_and_context(host, monkeypatch):
    state, workspace = host
    native = proof._native("fontlab")

    def fail(*args):
        state.shape.active = True
        raise RuntimeError("population failed")

    native.flItems = lambda: NS(requestContent=fail)
    with pytest.raises(RuntimeError, match="population"):
        proof.open_proofs(state.snapshot, Options(), deadline=float("inf"))
    assert state.current == 1 and state.active.id == 10 and not state.shape.active
    check = Mock(side_effect=TimeoutError("cleanup deadline"))
    with pytest.raises(proof._restore.__globals__["CleanupIncomplete"]) as caught:
        proof._restore(
            {90: (state.shape, False)},
            workspace,
            state.active,
            NS(fg_id=10),
            proof._native("fontpr"),
            check,
        )
    assert isinstance(caught.value.errors[0], TimeoutError)
    proof.PENDING.clear()


def test_action_carrier_reads_receive_cleanup_reserve_and_cooperative_checkpoint(
    host, monkeypatch
):
    state, workspace = host
    original = proof.fonts
    deadlines = []

    def bounded(deadline, *, checkpoint=None):
        assert checkpoint is not None
        checkpoint()
        deadlines.append(deadline)
        return original(deadline, checkpoint=checkpoint)

    monkeypatch.setattr(proof, "fonts", bounded)
    monkeypatch.setattr(proof, "monotonic", lambda: 0)
    proof.open_proofs(state.snapshot, Options(), deadline=3)
    assert deadlines and set(deadlines) == {2.5}
