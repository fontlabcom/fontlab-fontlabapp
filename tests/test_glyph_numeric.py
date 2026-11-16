# this_file: tests/test_glyph_numeric.py
"""Captured package/UPM/selection/date stability and lazy public launch paths."""

from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
import fontlabapp.proof.numeric.launcher as module
from fontlabapp.proof.numeric.model import Facts


def setup(monkeypatch):
    import fontlabapp.metrics.worksheet.capture as widths
    import fontlabapp.glyphs.catalog.native as dates
    import fontlabapp.core.scripting as scripting

    package = NS(id=7, master="R", upm=1000)
    selected = NS(
        context=(7, "R"), rows=(NS(glyph_name="A", layer_name="R", width=500.5),)
    )
    table = NS(rows=(("A", "U+0041", ""),), epochs=(None,))
    monkeypatch.setattr(scripting, "current_package", Mock(return_value=package))
    monkeypatch.setattr(widths, "capture", Mock(return_value=selected))
    monkeypatch.setattr(dates, "capture", Mock(return_value=table))
    return package, selected, table, scripting, widths, dates


def test_capture_complete_twice_and_no_handles(monkeypatch):
    p, s, t, script, widths, dates = setup(monkeypatch)
    assert module.capture() == Facts(1000, (("A", "R", 500.5),), (("A", None),))
    assert widths.capture.call_count == dates.capture.call_count == 2
    assert script.current_package.call_args.args == (7,)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "changed",
        "master",
        "incomplete",
        "deadline",
        "mismatch",
        "post_deadline",
        "thread",
    ],
)
def test_missing_unstable_partial_timeout_thread_refused(monkeypatch, fault):
    p, s, t, script, widths, dates = setup(monkeypatch)
    if fault == "missing":
        script.current_package.return_value = None
    if fault == "changed":
        script.current_package.side_effect = [p, None]
    if fault == "master":
        s.context = (7, "Other")
    if fault == "incomplete":
        t.epochs = ()
    if fault == "deadline":
        monkeypatch.setattr(module, "monotonic", Mock(side_effect=[0, 3]))
    if fault == "mismatch":
        monkeypatch.setattr(module, "_once", Mock(side_effect=[(1, 2, 3), (1, 2, 4)]))
    if fault == "post_deadline":
        monkeypatch.setattr(module, "_once", Mock(return_value=(1, 2, 3)))
        monkeypatch.setattr(module, "monotonic", Mock(side_effect=[0, 3]))
    if fault == "thread":
        monkeypatch.setattr(module, "current_thread", lambda: None)
    with pytest.raises((ValueError, TimeoutError, RuntimeError)):
        module.capture()


def test_public_facades_bind_native_once_and_registry_keys(monkeypatch):
    import fontlabapp
    import fontlabapp.core.scripting as scripting
    import fontlabapp.proof.numeric.ui as panel

    native = NS(QtCore=object(), QtGui=object())
    loader = Mock(return_value=native)
    kind = Mock(return_value="panel")
    factory = Mock(return_value=kind)
    monkeypatch.setattr(fontlabapp, "_native", loader)
    monkeypatch.setattr(panel, "panel_type", factory)

    def show(build, key):
        assert key in ("glyph_numeric_2", "glyph_numeric_3")
        return build("parent")

    monkeypatch.setattr(scripting, "show_script_dialog", show)
    assert module.show() == module.show_detailed() == "panel"
    assert loader.call_args.args == ("PythonQt",)
    assert kind.call_args.args == ("parent", module.capture, 3)
    monkeypatch.setattr(module, "current_thread", lambda: None)
    with pytest.raises(RuntimeError):
        module.show()
