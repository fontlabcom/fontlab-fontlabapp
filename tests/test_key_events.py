# this_file: tests/test_key_events.py
"""Shared event routing preserves native-base calls and caller error semantics."""
import subprocess
import sys
from types import SimpleNamespace

import pytest

from fontlabapp.qt.events.key import key_press_handler


@pytest.mark.parametrize('handled', [True, 1, False, 0, None])
def test_handler_when_policy_returns_then_accept_or_forward_exactly_once(handled):
    calls = []
    class Base:
        def keyPressEvent(self, event):
            calls.append(('base', self, event))
    def policy(widget, event):
        calls.append(('policy', widget, event))
        return handled
    class Widget(Base):
        keyPressEvent = key_press_handler(Base, policy)
    widget = Widget()
    event = SimpleNamespace(accept=lambda: calls.append(('accept',)))
    assert widget.keyPressEvent(event) is None
    assert calls == [('policy',widget,event),('accept',)] if handled else calls == [('policy',widget,event),('base',widget,event)]


@pytest.mark.parametrize('failure', ['policy','accept','base'])
def test_handler_when_a_stage_raises_then_propagate_without_fallback(failure):
    calls = []
    error = RuntimeError('owned failure')
    class Base:
        def keyPressEvent(self, event):
            calls.append('base')
            raise error
    def policy(widget, event):
        calls.append('policy')
        if failure == 'policy':
            raise error
        return failure == 'accept'
    def accept():
        calls.append('accept')
        raise error
    class Widget(Base):
        keyPressEvent = key_press_handler(Base, policy)
    with pytest.raises(RuntimeError) as observed:
        Widget().keyPressEvent(SimpleNamespace(accept=accept))
    assert observed.value is error
    assert calls == (['policy'] if failure == 'policy' else ['policy',failure])


def test_handler_when_imported_then_no_host_or_reverse_dependency():
    subprocess.run([sys.executable, '-c', "from fontlabapp.qt.events.key import key_press_handler; import sys; assert not {'PythonQt','fontlab','fontlab_glyport','fontlab_fontport','PySide6'}.intersection(sys.modules)"], check=True)
