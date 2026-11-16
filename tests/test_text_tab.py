# this_file: tests/test_text_tab.py
"""Owned native-shaped tab controls; no FontLab/QApplication is constructed."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.proof.tabs.text as api


@pytest.fixture
def host(monkeypatch):
    state = NS(
        font=True,
        main=object(),
        current=True,
        calls=[],
        tabs=[],
        connect=True,
        disconnect=True,
        failure=None,
        seconds=0.0,
    )
    shape = NS(id=1, active=False)
    old_shape = NS(id=2, active=True)
    package = NS(
        id=7,
        findName=lambda name: (
            NS(layers=[NS(shapes=[shape])]) if name != "missing" else None
        ),
    )
    other = NS(findName=lambda name: NS(layers=[NS(shapes=[old_shape])]))
    old_block = NS(package=other, getAllGlyphs=lambda: [NS(glyph=NS(name="old"))])
    state.block = old_block
    workspace = NS(
        getActiveTextBlock=lambda: state.block, getActiveCanvas=lambda: state.canvas
    )
    state.canvas = None
    native = NS(
        flWorkspace=NS(instance=lambda: workspace),
        MainWindow=lambda: state.main,
        CurrentFont=lambda: (
            NS(glyphs=[NS(name="A"), NS(name="missing"), NS(name="A")])
            if state.font
            else None
        ),
    )

    class Sender:
        def __init__(self):
            state.calls.append("create")
            self.connected = False

        def setText(self, text):
            state.calls.append(("text", text))
            if state.failure == ("emit" if self.connected else "bootstrap"):
                raise RuntimeError("owned " + state.failure)
            if self.connected:
                state.tabs.append(text)
                shape.active, old_shape.active = True, False
            if state.failure == "late":
                state.seconds = 3.0

        def connect(self, *args):
            assert args == (
                "textChanged(QString)",
                state.main,
                "doCreateTextBlock(QString)",
            )
            state.calls.append("connect")
            self.connected = state.connect
            return state.connect

        def disconnect(self, *args):
            assert args == (
                "textChanged(QString)",
                state.main,
                "doCreateTextBlock(QString)",
            )
            state.calls.append("disconnect")
            self.connected = False
            return state.disconnect

        def deleteLater(self):
            state.calls.append("delete")

    gui = NS(QLineEdit=Sender)
    monkeypatch.setattr(
        api, "_native", lambda name: native if name == "fontlab" else NS(QtGui=gui)
    )
    monkeypatch.setattr(
        api,
        "current_package",
        lambda expected_id: package if expected_id == 7 and state.current else None,
    )
    monkeypatch.setattr(api, "monotonic", lambda: state.seconds)
    return NS(**locals())


@pytest.mark.parametrize("text", ["", "Aa zero? 🙂 ", "fontlabapp-before-connect"])
def test_literal_text_uses_one_new_native_slot_and_restores_all_prior_flags(host, text):
    api.open_text_tab(text, expected_id=7)
    assert host.state.tabs == [text]
    assert host.shape.active is False and host.old_shape.active is True
    assert host.state.calls[-2:] == ["disconnect", "delete"]
    assert host.state.calls[1][1] != text, (
        "Bootstrap must differ and never reach native slot"
    )


@pytest.mark.parametrize("case", ["wrong_id", "no_font", "no_current_font", "no_main"])
def test_missing_or_switched_source_refuses_before_sender_creation(host, case):
    if case == "no_font":
        host.state.current = False
    if case == "no_current_font":
        host.state.font = False
    if case == "no_main":
        host.state.main = None
    with pytest.raises((ValueError, RuntimeError)):
        api.open_text_tab("Aa", expected_id=8 if case == "wrong_id" else 7)
    assert host.state.calls == [] and not host.state.tabs


def test_non_string_refuses_before_host_lookup(host):
    with pytest.raises(TypeError):
        api.open_text_tab(None, expected_id=7)
    assert not host.state.calls


@pytest.mark.parametrize(
    "case",
    ["none", "empty_canvas", "canvas_block", "empty_block", "no_active_attribute"],
)
def test_rendered_block_fallback_and_empty_domains_keep_complete_cleanup(host, case):
    if case != "empty_block":
        host.state.block = None
    if case == "empty_canvas":
        host.state.canvas = NS(textBlocks=list)
    if case == "canvas_block":
        host.state.canvas = NS(textBlocks=lambda: [host.old_block])
    if case == "empty_block":
        host.old_block.getAllGlyphs = lambda: None
    if case == "no_active_attribute":
        del host.shape.active
    api.open_text_tab("Aa", expected_id=7)
    assert host.state.tabs == ["Aa"] and host.state.calls[-1] == "delete"
    if case == "canvas_block":
        assert host.old_shape.active is True


@pytest.mark.parametrize(
    "failure", ["bootstrap", "emit", "connect", "disconnect", "late"]
)
def test_native_failures_always_delete_sender_and_disconnect_when_connected(
    host, failure
):
    if failure == "connect":
        host.state.connect = False
    elif failure == "disconnect":
        host.state.disconnect = False
    else:
        host.state.failure = failure
    with pytest.raises((RuntimeError, TimeoutError)):
        api.open_text_tab("Aa", expected_id=7)
    assert host.state.calls[-1] == "delete"
    assert ("disconnect" in host.state.calls) == (
        failure not in ("bootstrap", "connect")
    )
    if failure != "disconnect":
        assert host.state.tabs == []
    assert host.shape.active is False and host.old_shape.active is True


def test_font_switch_during_complete_preflight_refuses_before_sender(host, monkeypatch):
    original = api._snapshot

    def switched(*args):
        result = original(*args)
        host.state.current = False
        return result

    monkeypatch.setattr(api, "_snapshot", switched)
    with pytest.raises(ValueError, match="changed during"):
        api.open_text_tab("Aa", expected_id=7)
    assert not host.state.calls


def test_slow_snapshot_fails_before_sender_creation(host, monkeypatch):
    host.native.CurrentFont = lambda: (
        setattr(host.state, "seconds", 3.0) or NS(glyphs=[NS(name="A")])
    )
    with pytest.raises(TimeoutError):
        api.open_text_tab("Aa", expected_id=7)
    assert not host.state.calls


def test_restore_attempts_other_shapes_even_after_one_setter_failure():
    class Broken:
        @property
        def active(self):
            return True

        @active.setter
        def active(self, value):
            raise RuntimeError("owned restore failure")

    other = NS(active=True)
    with pytest.raises(ExceptionGroup, match="restoration") as error:
        api._restore({1: (Broken(), False), 2: (other, False)})
    assert other.active is False and len(error.value.exceptions) == 1
