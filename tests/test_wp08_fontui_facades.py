# this_file: tests/test_wp08_fontui_facades.py
"""Public proof preview construction preserves read-only options and owns failure cleanup."""

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('stage', ['success', 'before-widget', 'after-widget'])
def test_metrics_preview_preserves_read_only_binding_and_cleans_partial_widget(monkeypatch, stage):
    import fontlabapp.fontui as fontui

    font, parent, hint = object(), object(), object()
    calls, closed = [], []

    class Preview:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))
            if stage == 'before-widget':
                raise RuntimeError('before widget')
            self.widget = object()
            if stage == 'after-widget':
                raise RuntimeError('after widget')

        def close(self):
            closed.append(self)

    loads = []

    def load(name):
        loads.append(name)
        return SimpleNamespace(TMetrics=Preview)

    monkeypatch.setattr(fontui, '_load', load)
    options = dict(text='/A /A', layer='Bold', controls=False, hint_check=hint, read_only=True)
    if stage == 'success':
        preview = fontui.metrics_preview(font, parent, **options)
        assert isinstance(preview, Preview)
        assert closed == []
    else:
        with pytest.raises(RuntimeError, match=stage.replace('-', ' ')):
            fontui.metrics_preview(font, parent, **options)
        assert len(closed) == (stage == 'after-widget')
    assert loads == ['tmetrics']
    assert calls == [((font, parent, None, '/A /A'), dict(
        controls=False, layer='Bold', label_prefix='TMetrics', hint_check=hint, read_only=True))]
