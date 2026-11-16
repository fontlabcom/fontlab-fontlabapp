# this_file: tests/test_fontui_tmetrics_layers.py
"""``write_metric``/``apply_kerning``: explicit target layer, undo label and default back-compat."""

from types import SimpleNamespace

import pytest
import _cov_qt as fq
from _tmetrics_fakes import EditableFont

from fontlabapp.fontui.tmetrics_model import write_metric


class LayeredFont(EditableFont):
    """An editable font with a second ``Bold`` layer whose A is 700 wide, bounds 50..650."""

    def getLayer(self, name):
        if name != "Bold":
            raise KeyError(name)
        return {"A": SimpleNamespace(width=700, bounds=(50, 0, 650, 700)), "E": SimpleNamespace(width=0)}


def test_write_metric_when_no_layer_then_default_layer_and_label():
    font = EditableFont()
    assert write_metric(font, "A", "rsb", 77)
    assert font.edits == [("A", "public.default", "TMetrics: RSB A")]


def test_write_metric_when_layer_and_undo_name_then_targets_that_layer():
    font = LayeredFont()
    assert write_metric(font, "A", "width", 720, layer="Bold", undo_name="Spacing Studio: width A")
    assert font.edits == [("A", "Bold", "Spacing Studio: width A")]


def test_write_metric_when_layer_value_unchanged_then_no_write():
    font = LayeredFont()
    assert not write_metric(font, "A", "lsb", 50, layer="Bold")
    assert not write_metric(font, "A", "rsb", 50, layer="Bold")
    assert font.edits == []


def test_write_metric_when_default_named_explicitly_then_same_as_default():
    font = EditableFont()
    assert write_metric(font, "A", "rsb", 66, layer="public.default")
    assert font.edits == [("A", "public.default", "TMetrics: RSB A")]


def test_write_metric_when_glyph_missing_on_layer_then_value_error():
    font = LayeredFont()
    with pytest.raises(ValueError, match="Glyph not found: Z"):
        write_metric(font, "Z", "width", 10, layer="Bold")
    with pytest.raises(ValueError, match="on layer Light"):
        write_metric(font, "A", "width", 10, layer="Light")


def test_write_metric_when_layer_glyph_has_no_outline_then_sidebearing_refused():
    font = LayeredFont()
    with pytest.raises(ValueError):
        write_metric(font, "E", "lsb", 10, layer="Bold")


class Pairs(dict):
    def __init__(self):
        super().__init__()
        self.applied = []

    def apply(self, values, *, undo_name):
        self.applied.append(undo_name)
        self.clear()
        self.update(values)


@pytest.fixture
def apply_kerning(monkeypatch):
    handle = fq.install(monkeypatch)
    yield handle.load("fontlabapp.fontui.kerning").apply_kerning
    fq.release()


def kerning_font(current="Regular"):
    return SimpleNamespace(defaultLayerName=current, kerning=Pairs(), groups={}, keys=lambda: ["L", "T"])


def test_apply_kerning_when_master_is_current_then_writes_with_label(apply_kerning):
    font = kerning_font()
    result = apply_kerning(font, "apply", ("L", "T"), -40, undo_name="Kerning Studio: kerning L T", master="Regular")
    assert result == {("L", "T"): -40}
    assert font.kerning.applied == ["Kerning Studio: kerning L T"]


def test_apply_kerning_when_master_not_current_then_refused_before_write(apply_kerning):
    font = kerning_font()
    with pytest.raises(ValueError, match=r"default master \(Regular\) only; Bold cannot be targeted\."):
        apply_kerning(font, "apply", ("L", "T"), -40, undo_name="x", master="Bold")
    assert font.kerning.applied == []


def test_apply_kerning_when_no_master_then_current_target_as_before(apply_kerning):
    font = kerning_font()
    apply_kerning(font, "apply", ("L", "T"), -10, undo_name="TMetrics: kerning L T")
    assert font.kerning.applied == ["TMetrics: kerning L T"]
