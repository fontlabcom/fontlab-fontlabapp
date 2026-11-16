# this_file: tests/test_teaching_text_icons.py
"""Script Icon Browser: enum filtering, list building and generated code, on real offscreen Qt."""

import sys

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import lab  # noqa: F401


class FakeStyleType:
    SP_DirIcon = 1
    SP_FileIcon = 2
    SP_CustomBase = 3
    Other = 4


@pytest.fixture
def icons(lab):  # noqa: F811
    module, shown = lab("icons")
    qt = sys.modules["PythonQt"]
    real = qt.QtGui.QStyle
    fake = type("QStyle", (), {"SP_DirIcon": real.StandardPixmap.SP_DirIcon,
                                "SP_FileIcon": real.StandardPixmap.SP_FileIcon, "SP_CustomBase": 0})
    qt.QtGui.QStyle = fake
    yield module, shown
    qt.QtGui.QStyle = real


def test_icon_names_when_filtered_then_sorted_sp_names_without_custom_base():
    from fontlabapp.fontui.teaching_text import icons as mod

    assert mod.icon_names(FakeStyleType, "") == ("SP_DirIcon", "SP_FileIcon")
    assert mod.icon_names(FakeStyleType, "dir") == ("SP_DirIcon",)
    assert mod.icon_names(FakeStyleType, "zzz") == ()


def test_dialog_when_previewed_then_rows_listed_and_selection_gives_code(icons):
    module, shown = icons
    dialog = module.build(None)
    dialog.preview()
    assert dialog.icons.count() == 2 and "2 standard icons" in dialog.status.text()
    dialog.icons.setCurrentRow(0)
    assert "QStyle.SP_DirIcon" in dialog.output.toPlainText()
    assert dialog.status.text() == "Icon code ready. Select text and Copy."
    dialog.filter_text.setText("file")
    dialog.preview_button.click()
    assert dialog.icons.count() == 1 and dialog.enum_names == ("SP_FileIcon",)
    dialog.select_icon(9)  # out of range: no code, no crash
    assert dialog.output.toPlainText() == ""


def test_dialog_when_result_not_exact_in_qt_then_refused(icons):
    module, shown = icons
    dialog = module.build(None)
    with pytest.raises(ValueError, match="cannot preserve"):
        dialog.publish("a\rb")
    dialog.enum_names = ("SP_A ",)
    dialog.select_icon(0)
    assert "cannot preserve" in dialog.status.text() and dialog.output.toPlainText() == ""
    dialog.output.toPlainText = lambda: "changed"
    with pytest.raises(ValueError, match="Qt changed"):
        dialog.publish("ok")


def test_dialog_when_build_fails_then_status_shows_error(icons, monkeypatch):
    module, shown = icons
    dialog = module.build(None)
    monkeypatch.setattr(module, "icon_names", lambda *a: (_ for _ in ()).throw(RuntimeError("no style")))
    dialog.preview()
    assert dialog.status.text() == "no style" and dialog.enum_names == () and dialog.icons.count() == 0


def test_close_button_when_lab_close_set_then_called_else_closes(icons):
    module, shown = icons
    dialog = module.build(None)
    calls = []
    dialog.lab_close = lambda: calls.append("lab")
    dialog.close_button.click()
    assert calls == ["lab"]
    del dialog.lab_close
    dialog.show()
    dialog.close_button.click()
    assert not dialog.isVisible()


def test_main_when_not_embedded_then_shown_through_script_dialog(icons):
    module, shown = icons
    module.main()
    assert shown[0][1] == "widgets_script_icon_browser"
