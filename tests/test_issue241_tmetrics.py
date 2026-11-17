# this_file: tests/test_issue241_tmetrics.py
"""Master selection and text-host round trips on the actual TMetrics controller."""
from _tmetrics_fakes import TwoLayerFont
from test_cov_ui_tmetrics import tm_mod  # noqa: F401


class Host:
    def __init__(self):
        self.text = "AV"
        self.writes = []
        self.available = True

    def read_text(self):
        return self.text

    def write_text(self, text):
        if not self.available:
            return False
        self.text = text
        self.writes.append(text)
        return True

    def subscribe(self, owner, callback, fonts, text_callback=None):
        self.callback = callback
        self.fonts = fonts


def make(module, **kwargs):
    font = TwoLayerFont()
    font.layerOrder = ["public.default", "Bold"]
    host = Host()
    return module.TMetrics(font, host=host, **kwargs), host


def test_master_selection_targets_layer_metrics_and_refuses_wrong_master_kerning(tm_mod):  # noqa: F811 - shared fixture
    window, host = make(tm_mod, text="AV")
    window.layer_control.setCurrentIndex(2)
    assert window.layer == window.model.layer == "Bold"
    assert window.model.cells[0].width == 700
    assert "kerning is unavailable" in window.diagnostic.text
    assert not window.model.settings.kerning
    assert all(cell.kern == 0 for cell in window.model.cells)
    assert window.pair_readout.text == ""
    window.model.select(0)
    assert window.commit("width", "720")
    assert window.font.getLayer("Bold")["A"].width == 720
    assert window.font["A"].width != 720
    window.model.select(1)
    assert not window.commit("kerning", "-50")
    window.set_layer(None)
    assert window.layer_control.currentIndex == 0
    window.layer_control.currentIndex = 99
    window.choose_layer()
    assert "Error:" in window.diagnostic.text


def test_text_round_trip_follows_host_and_preserves_unsubmitted_draft(tm_mod):  # noqa: F811 - shared fixture
    window, host = make(tm_mod)
    host.callback()
    assert window.text_control.text == "AV"
    window.text_control.setText("VA")
    host.text = "AA"
    host.callback()
    assert window.text_control.text == "VA"
    window.text_control.returnPressed.emit()
    assert host.writes == ["VA"]
    host.text = "VV"
    host.callback()
    assert window.text_control.text == "VV"
    host.callback()
    assert host.writes == ["VA"]
    host.text = None
    host.callback()
    assert window.text_control.text == "VV"


def test_follow_when_host_text_changes_then_reshapes_once(tm_mod, monkeypatch):  # noqa: F811
    window, host = make(tm_mod)
    reshape = window.model.reshape
    shaped = []

    def record_reshape():
        shaped.append(window.model.settings.text)
        reshape()

    monkeypatch.setattr(window.model, "reshape", record_reshape)
    window.echo.record(window.drawn)
    host.callback()
    assert shaped == ["AV"]
    assert window.echo.token is None
    assert [cell.name for cell in window.model.cells] == ["A", "V"]
    host.text = "VV"
    host.callback()
    assert shaped == ["AV", "VV"]
    assert window.model.settings.text == "VV"
    assert [cell.name for cell in window.model.cells] == ["V", "V"]


def test_follow_when_first_layout_fails_then_retries(tm_mod, monkeypatch):  # noqa: F811
    window, host = make(tm_mod)
    relayout = window._relayout
    attempts = []

    def fail_once():
        attempts.append(window.text_control.text)
        if len(attempts) == 1:
            raise RuntimeError("layout failed")
        relayout()

    monkeypatch.setattr(window, "_relayout", fail_once)
    generation = window._refresh_generation
    host.callback()
    assert attempts == ["AV", "AV"]
    assert window._refresh_generation == generation + 1
    assert window.drawn == window.model.fingerprint()


def test_follow_when_observer_changes_font_after_refresh_then_refreshes_again(tm_mod, monkeypatch):  # noqa: F811
    window, host = make(tm_mod)
    follow_text = window._follow_text

    def follow_then_mutate():
        follow_text()
        window.font["A"].width += 25

    monkeypatch.setattr(window, "_follow_text", follow_then_mutate)
    generation = window._refresh_generation
    host.callback()
    assert window._refresh_generation == generation + 2
    assert window.model.cells[0].width == window.font["A"].width
    assert window.drawn == window.model.fingerprint()


def test_text_unavailable_readonly_closed_and_errors_are_safe(tm_mod):  # noqa: F811 - shared fixture
    window, host = make(tm_mod, text="AV")
    host.available = False
    assert not window.commit_text()
    assert "stays local" in window.diagnostic.text
    host.write_text = lambda text: (_ for _ in ()).throw(RuntimeError("write failed"))
    assert not window.commit_text()
    assert "write failed" in window.diagnostic.text
    window.read_only = True
    assert not window.commit_text()
    window.close()
    assert not window.commit_text()


def test_explicit_unlisted_layer_retained_in_selector(tm_mod):  # noqa: F811 - shared fixture
    window, host = make(tm_mod, layer="Other")
    assert window.layer_choices[-1] == "Other"
    window.set_layer("Bold")
    assert window.layer_choices[window.layer_control.currentIndex] == "Bold"


def test_initial_text_draft_and_embedded_preview_are_not_replaced(tm_mod):  # noqa: F811
    window, host = make(tm_mod, text="VV")
    host.callback()
    assert window.text_control.text == "VV"
    embedded, embedded_host = make(tm_mod, controls=False)
    embedded_host.callback()
    assert embedded.text_control.text == ""


def test_first_available_host_preserves_draft_and_readonly_preview(tm_mod):  # noqa: F811
    window, host = make(tm_mod)
    host.text = None
    host.callback()
    window.text_control.setText("VV")
    host.text = "AV"
    host.callback()
    assert window.text_control.text == "VV"
    readonly, readonly_host = make(tm_mod, read_only=True)
    readonly_host.callback()
    assert readonly.text_control.text == ""


def test_window_when_created_then_compact_metrics_and_view_above_controls(tm_mod):  # noqa: F811 - shared fixture
    window, _ = make(tm_mod, text="AV")
    assert [args for call, args in window.layout.calls if call == "setContentsMargins"] == [(6, 6, 6, 6)]
    assert [args for call, args in window.layout.calls if call == "setSpacing"] == [(4,)]
    assert [args for call, args in window.layout.calls if call == "insertWidget"] == [(0, window.scroll, 1)]
