# this_file: tests/test_teaching_text_palette.py
"""Script Palette Roles: contrast maths, report building and the panel, on real offscreen Qt."""

import sys
from types import SimpleNamespace as NS

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import button, lab  # noqa: F401

BLACK, WHITE = (0, 0, 0, 255), (255, 255, 255, 255)


def test_role_value_when_placeholder_then_20_missing_none_unknown_refused():
    from fontlabapp.fontui.teaching_text import palette as mod

    assert mod.role_value(NS(), "PlaceholderText") == 20
    assert mod.role_value(NS(Text=7), "Text") == 7 and mod.role_value(NS(), "Text") is None
    with pytest.raises(ValueError, match="Unknown palette role"):
        mod.role_value(NS(), "Nope")


def test_contrast_when_black_on_white_then_21_and_alpha_composited():
    from fontlabapp.fontui.teaching_text import palette as mod

    assert mod.contrast(BLACK, WHITE) == pytest.approx(21.0)
    assert mod.contrast(WHITE, WHITE) == pytest.approx(1.0)
    half = mod.contrast((0, 0, 0, 128), WHITE)
    assert 1.0 < half < 21.0
    assert mod.contrast(BLACK, (255, 255, 255, 10)) is None  # translucent background has no ratio
    assert mod.contrast(WHITE, (0, 0, 1, 255)) > 15  # the dark-channel branch of the sRGB curve


@pytest.mark.parametrize("bad", [(0, 0, 0), (0, 0, 0, 256), (0, 0, 0, 1.0), (-1, 0, 0, 255)])
def test_contrast_when_channels_invalid_then_refused(bad):
    from fontlabapp.fontui.teaching_text import palette as mod

    with pytest.raises(ValueError, match="four integer"):
        mod.contrast(bad, WHITE)
    with pytest.raises(ValueError, match="four integer"):
        mod.contrast(WHITE, bad)


class FakePalette:
    def __init__(self, alpha=255):
        self.alpha = alpha

    def color(self, group, role):
        shade = 0 if role == 1 else 255
        return NS(red=lambda: shade, green=lambda: shade, blue=lambda: shade, alpha=lambda: self.alpha)


def fake_type(**extra):
    roles = {"WindowText": 1, "Window": 2, "Text": 1, "Base": 2}
    return NS(Active=0, Inactive=1, Disabled=2, **roles, **extra)


def test_palette_report_when_roles_partly_missing_then_listed_and_pairs_skipped():
    from fontlabapp.fontui.teaching_text import palette as mod

    report = mod.palette_report(FakePalette(), fake_type())
    assert report.count("Active\n") == 1 and "Disabled" in report
    assert "Button: unavailable by name" in report
    assert "WindowText: #000000 / alpha 255" in report and "Window: #ffffff / alpha 255" in report
    assert "WindowText/Window: 21.00:1" in report and "Text/Base: 21.00:1" in report
    assert "ButtonText/Button" not in report and "PlaceholderText/Base: 1.00:1" in report


def test_palette_report_when_background_translucent_then_stated():
    from fontlabapp.fontui.teaching_text import palette as mod

    assert "unavailable: translucent background" in mod.palette_report(FakePalette(alpha=100), fake_type())


def test_palette_report_when_group_missing_then_refused():
    from fontlabapp.fontui.teaching_text import palette as mod

    with pytest.raises(ValueError, match="does not expose group Active"):
        mod.palette_report(FakePalette(), NS())


def test_role_code_when_generated_then_compiles_and_names_every_role():
    from fontlabapp.fontui.teaching_text import palette as mod

    code = mod.role_code()
    compile(code, "<role_code>", "exec")
    assert all(role in code for role in mod.ROLES) and "self.subtitle.setForegroundRole" in code


def test_dialog_when_refreshed_then_report_and_code_published(lab):  # noqa: F811
    module, shown = lab("palette")
    dialog = module.build(None)
    dialog.palette = FakePalette()  # PythonQt reads it as a property; real Qt rejects the numeric role 20
    sys.modules["PythonQt"].QtGui.QPalette = fake_type()
    dialog.preview()
    assert dialog.report.toPlainText().startswith("Active") and "PLACEHOLDER_TEXT" in dialog.output.toPlainText()
    assert dialog.status.text().startswith("Palette report and role-based code ready")
    first = dialog.report.toPlainText()
    dialog.report.setPlainText("stale")
    button(dialog, "Refresh").click()
    assert dialog.report.toPlainText() == first and "PLACEHOLDER_TEXT" in dialog.output.toPlainText()


def test_dialog_when_report_fails_or_qt_alters_text_then_cleared(lab, monkeypatch):  # noqa: F811
    module, shown = lab("palette")
    dialog = module.build(None)
    monkeypatch.setattr(module, "palette_report", lambda p, t: (_ for _ in ()).throw(ValueError("no group")))
    dialog.preview()
    assert dialog.status.text() == "no group" and dialog.report.toPlainText() == ""
    monkeypatch.setattr(module, "palette_report", lambda p, t: "report")
    dialog.report.toPlainText = lambda: "altered"
    dialog.preview()
    assert "Qt changed palette output" in dialog.status.text() and dialog.output.toPlainText() == ""


def test_close_and_main(lab):  # noqa: F811
    module, shown = lab("palette")
    dialog = module.build(None)
    calls = []
    dialog.lab_close = lambda: calls.append(1)
    button(dialog, "Close").click()
    assert calls == [1]
    module.main()
    assert shown[0][1] == "widgets_script_palette_roles"
