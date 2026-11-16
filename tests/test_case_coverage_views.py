# this_file: tests/test_case_coverage_views.py
from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
import fontlabapp.glyphs.case_coverage.views as views


class Block:
    def __init__(self, identity=10, package=1):
        self.id = identity
        self.package = NS(id=package)
        self.content = []

    def symbolList(self):
        return NS(symbols=lambda: self.content)


def test_fresh_exact_named_content_and_full_sender_cleanup(monkeypatch):
    state = NS(active=Block(), created=0)
    workspace = NS(getActiveTextBlock=lambda: state.active, activeFontPanel=None)

    def create(text):
        state.active = Block(20)
        state.created += 1

    cleanup = Mock()

    @contextmanager
    def sender(*args, **kwargs):
        try:
            yield NS(setText=create)
        finally:
            kwargs["before_disconnect"]()
            cleanup()

    monkeypatch.setattr(views, "text_tab_sender", sender)

    def request(symbols, index):
        state.active.content = symbols

    native = NS(
        flTextBlock=Block,
        MainWindow=lambda: object(),
        flItems=lambda: NS(requestContent=request),
    )
    symbols = [
        NS(name="A.alt", layerName="Regular"),
        NS(name="A.alt", layerName="Regular"),
    ]
    expected = (("A.alt", "Regular"), ("A.alt", "Regular"))
    views.fresh(native, workspace, 1, symbols, expected, {10}, lambda: None, object())
    assert state.created == 1 and cleanup.call_count == 1
    assert views.verify(native, workspace, 1, expected, lambda: None).id == 20
    state.active.content = []
    with pytest.raises(ValueError, match="exact proof content"):
        views.verify(native, workspace, 1, expected, lambda: None)
    workspace.activeFontPanel = object()
    with pytest.raises(ValueError, match="Font window"):
        views.verify(native, workspace, 1, expected, lambda: None)
    workspace.activeFontPanel = None
    with pytest.raises(ValueError, match="changed"):
        views.verify(native, workspace, 2, expected, lambda: None)
    native.MainWindow = lambda: None
    with pytest.raises(ValueError, match="main window"):
        views.fresh(
            native, workspace, 1, symbols, expected, {10}, lambda: None, object()
        )


def test_fresh_never_replaces_old_target_or_wrong_package_and_checks_panel(monkeypatch):
    state = NS(active=Block())
    workspace = NS(getActiveTextBlock=lambda: state.active, activeFontPanel=None)

    @contextmanager
    def sender(*args, **kwargs):
        yield NS(setText=lambda text: None)

    monkeypatch.setattr(views, "text_tab_sender", sender)
    request = Mock()
    native = NS(
        flTextBlock=Block,
        MainWindow=lambda: object(),
        flItems=lambda: NS(requestContent=request),
    )
    with pytest.raises(ValueError, match="No new"):
        views.fresh(native, workspace, 1, [], (), {10}, lambda: None, object())
    assert not request.called
    state.active = Block(20)
    workspace.activeFontPanel = object()
    with pytest.raises(ValueError, match="not active"):
        views.fresh(native, workspace, 1, [], (), {10}, lambda: None, object())
    assert not request.called


def test_fresh_when_new_tab_is_only_the_active_canvas_block_then_populates(monkeypatch):
    """FontLab 9: a fresh tab never becomes the active text block."""
    state = NS(canvas_blocks=[Block()])
    workspace = NS(
        getActiveTextBlock=lambda: None,
        getActiveCanvas=lambda: NS(textBlocks=lambda: list(state.canvas_blocks)),
        activeFontPanel=None,
    )

    @contextmanager
    def sender(*args, **kwargs):
        yield NS(setText=lambda text: state.canvas_blocks.__setitem__(0, Block(20)))

    monkeypatch.setattr(views, "text_tab_sender", sender)

    def request(symbols, index):
        state.canvas_blocks[0].content = symbols

    native = NS(flTextBlock=Block, MainWindow=lambda: object(),
                flItems=lambda: NS(requestContent=request))
    symbols = [NS(name="A", layerName="Regular")]
    views.fresh(native, workspace, 1, symbols, (("A", "Regular"),), {10}, lambda: None, object())
    assert state.canvas_blocks[0].content == symbols
