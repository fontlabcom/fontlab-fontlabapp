# this_file: tests/test_native_tabs.py
"""Owned native-shaped controls for shared tab mechanics and caller policy."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.core.native_tabs as api


@pytest.mark.parametrize("source", ["active", "canvas", "empty", "none"])
def test_rendered_block_preserves_active_then_first_canvas_precedence(source):
    block = object()
    workspace = NS(
        getActiveTextBlock=lambda: block if source == "active" else None,
        getActiveCanvas=lambda: (
            NS(textBlocks=lambda: [block, object()] if source == "canvas" else [])
            if source != "none"
            else None
        ),
    )
    assert api.rendered_block(workspace) is (
        block if source in ("active", "canvas") else None
    )


@pytest.mark.parametrize("failure", [False, True])
def test_activation_context_restores_changed_flags_and_keeps_body_exception(failure):
    shape = NS(id=1, active=False)
    calls = []
    package = NS(
        findName=lambda name: (
            calls.append(name)
            or (NS(layers=[NS(shapes=[shape, NS(id=2)])]) if name == "A" else None)
        )
    )

    def run():
        with api.preserve_shape_activation(package, ["A", "missing", "A"]):
            shape.active = True
            if failure:
                raise ValueError("owned body error")

    if failure:
        with pytest.raises(ValueError, match="owned body"):
            run()
    else:
        run()
    assert shape.active is False and calls == ["A", "missing"]


def test_activation_context_keeps_original_missing_layers_and_duplicate_id_policy():
    first, last = NS(id=1, active=False), NS(id=1, active=True)
    package = NS(
        findName=lambda name: (
            NS() if name == "empty" else NS(layers=[NS(shapes=[first, last])])
        )
    )
    with api.preserve_shape_activation(package, ["empty", "A"]):
        first.active = True
        last.active = False
    assert first.active is True and last.active is True, (
        "Preserve original last-wrapper-per-id behavior"
    )


@pytest.mark.parametrize("present", [False, True])
def test_rendered_activation_context_handles_no_block_and_restores_block_shapes(
    present,
):
    shape = NS(id=1, active=False)
    package = NS(findName=lambda name: NS(layers=[NS(shapes=[shape])]))
    block = NS(package=package, getAllGlyphs=lambda: [NS(glyph=NS(name="A"))])
    workspace = NS(
        getActiveTextBlock=lambda: block if present else None,
        getActiveCanvas=lambda: None,
    )
    with api.preserve_rendered_activation(workspace):
        shape.active = True
    assert shape.active is (not present)


@pytest.fixture
def sender():
    state = NS(events=[], failure=None, connected=True, disconnected=True)
    receiver = object()

    class Sender:
        def __init__(self):
            state.events.append("create")

        def setText(self, text):
            state.events.append(("text", text))
            if state.failure == "bootstrap":
                raise RuntimeError("bootstrap")

        def connect(self, *args):
            assert args == (
                "textChanged(QString)",
                receiver,
                "doCreateTextBlock(QString)",
            )
            state.events.append("connect")
            if state.failure == "connect":
                raise RuntimeError("connect")
            return state.connected

        def disconnect(self, *args):
            assert args == (
                "textChanged(QString)",
                receiver,
                "doCreateTextBlock(QString)",
            )
            state.events.append("disconnect")
            if state.failure == "disconnect":
                raise RuntimeError("disconnect")
            return state.disconnected

        def deleteLater(self):
            state.events.append("delete")

    state.gui = NS(QLineEdit=Sender)
    state.receiver = receiver
    return state


def context(sender, **kwargs):
    return api.text_tab_sender(
        sender.gui,
        sender.receiver,
        bootstrap_text="bootstrap",
        connection_error=ValueError("caller connect"),
        disconnection_error=OSError("caller disconnect"),
        **kwargs,
    )


@pytest.mark.parametrize("cleanup", [False, True])
def test_sender_owns_only_native_connection_and_retains_cleanup_order(sender, cleanup):
    callback = (lambda: sender.events.append("restore")) if cleanup else None
    with context(sender, before_disconnect=callback) as emitter:
        emitter.setText("proof")
    assert sender.events == [
        "create",
        ("text", "bootstrap"),
        "connect",
        ("text", "proof"),
    ] + (["restore"] if cleanup else []) + ["disconnect", "delete"]


@pytest.mark.parametrize(
    "failure",
    [
        "bootstrap",
        "connect",
        "connection_false",
        "disconnect",
        "disconnection_false",
        "body",
        "cleanup",
    ],
)
def test_sender_preserves_caller_errors_and_deletes_on_every_failure(sender, failure):
    sender.failure = failure
    sender.connected = failure != "connection_false"
    sender.disconnected = failure != "disconnection_false"

    def cleanup():
        sender.events.append("restore")
        if failure == "cleanup":
            raise LookupError("cleanup")

    with (
        pytest.raises((RuntimeError, ValueError, OSError, LookupError)) as caught,
        context(sender, before_disconnect=cleanup),
    ):
        if failure == "body":
            raise RuntimeError("body")
    assert sender.events[-1] == "delete"
    assert "restore" in sender.events
    assert ("disconnect" in sender.events) == (
        failure not in ("bootstrap", "connect", "connection_false")
    )
    if failure == "connection_false":
        assert (
            type(caught.value) is ValueError and str(caught.value) == "caller connect"
        )
    if failure == "disconnection_false":
        assert (
            type(caught.value) is OSError and str(caught.value) == "caller disconnect"
        )


def test_canvases_when_binding_raises_typeerror_then_active_canvas_only():
    """FontLab 9.0.9804: flWorkspace.canvases() raises TypeError (native probe)."""
    from types import SimpleNamespace as NS

    import fontlabapp.core.native_tabs as tabs

    def broken():
        raise TypeError("Incorrect argument type. flObject, flCanvas or int expected")

    active = NS(id=5)
    native = NS(flCanvas=lambda raw: ("wrapped", raw))
    assert tabs.canvases(native, NS(canvases=broken, getActiveCanvas=lambda: active)) == [active]
    assert tabs.canvases(native, NS(canvases=broken, getActiveCanvas=lambda: None)) == []
    assert tabs.canvases(native, NS(canvases=lambda: [1])) == [("wrapped", 1)]
