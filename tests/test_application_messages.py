# this_file: tests/test_application_messages.py
"""Application output helpers keep their formatting after de-duplication."""

import importlib
import sys
import types

import pytest


@pytest.fixture
def app(monkeypatch):
    shown = []

    class Box:
        Information, Warning, Critical = "info", "warning", "critical"

        def __init__(self, kind, title, text):
            self.args = (kind, title, text)

        def exec(self):
            shown.append(self.args)

    monkeypatch.setitem(sys.modules, "fontlab", types.ModuleType("fontlab"))
    qt = types.ModuleType("PythonQt")
    qt.QtGui = types.SimpleNamespace(QMessageBox=Box)
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.delitem(sys.modules, "fontlabapp.core.application.context", raising=False)
    module = importlib.import_module("fontlabapp.core.application.context")
    out = []
    application = module.Application.__new__(module.Application)
    application.main = types.SimpleNamespace(
        doOutput=lambda msg, flag: out.append(("output", msg, flag)),
        doWarning=lambda msg: out.append(("warning", msg)),
    )
    yield application, out, shown, module
    monkeypatch.delitem(sys.modules, "fontlabapp.core.application.context", raising=False)


def test_plain_messages_when_logged_then_newline_and_channel(app):
    application, out, shown, _ = app
    application.debug("d")
    application.info("i")
    application.warn("w")
    application.error("e")
    assert out == [("output", "d\n", False), ("output", "i\n", True), ("warning", "w\n"), ("warning", "[ERROR] e\n")]
    assert shown == []


def test_markdown_messages_when_logged_then_html(app):
    application, out, _, module = app
    application.debug("**d**", md=True)
    application.warn("w", styled=True, css="x")
    application.error("**e**", md=True)
    assert out[0] == ("output", module.to_html("**d**", md=True, styled=False, css=""), False)
    assert out[1] == ("warning", module.to_html("w", md=False, styled=True, css="x"))
    assert out[2] == ("warning", module.to_html("<small>[ERROR] </small>\n**e**", md=True, styled=False,
                                                css="color:lightcoral;"))


def test_gui_messages_when_requested_then_message_box(app):
    application, out, shown, module = app
    application.info("i", gui=True)
    application.warn("w", gui=True)
    application.error("e", gui=True)
    application.error("**e**", gui=True, md=True)
    assert shown == [("info", "Info", "i\n"), ("warning", "Warning", "w\n"), ("critical", "Error", "e"),
                     ("critical", "Error", module.to_html("**e**", md=True, styled=False, css=""))]
    assert out == []
