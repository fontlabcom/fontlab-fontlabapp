# this_file: tests/test_teaching_text_scaffold.py
"""Script Scaffold Wizard: generated source and the two-page panel, on real offscreen Qt."""

import ast

import pytest

from _studio_qt import studio_qt  # noqa: F401
from _text_lab import button, lab  # noqa: F401


def test_scaffold_when_valid_then_parseable_source_with_title_as_data(lab):  # noqa: F811
    module, shown = lab("scaffold")
    source = module.scaffold("AuditWidths", "It's \"odd\"\nline")
    tree = ast.parse(source)
    assert any(isinstance(n, ast.ClassDef) and n.name == "AuditWidths" for n in tree.body)
    assert "TITLE: str = " + repr("It's \"odd\"\nline") in source


@pytest.mark.parametrize("name", ["", "1x", "class", "fl", "main", "bad name", "TITLE", "print"])
def test_scaffold_when_not_a_class_identifier_then_refused(lab, name):  # noqa: F811
    module, shown = lab("scaffold")
    with pytest.raises(ValueError, match="class identifier"):
        module.scaffold(name, "t")


def test_dialog_when_next_then_preview_page_shows_source(lab):  # noqa: F811
    module, shown = lab("scaffold")
    dialog = module.build(None)
    assert dialog.pages.currentIndex == 0
    button(dialog, "Next: Review Python").click()
    assert dialog.pages.currentIndex == 1 and "class MyFontTool" in dialog.output.toPlainText()
    button(dialog, "Back").click()
    assert dialog.pages.currentIndex == 0
    assert dialog.status.text().startswith("Python ready")


def test_dialog_when_name_invalid_then_stays_on_inputs_with_reason(lab):  # noqa: F811
    module, shown = lab("scaffold")
    dialog = module.build(None)
    dialog.class_name.setText("not valid")
    button(dialog, "Next: Review Python").click()
    assert dialog.pages.currentIndex == 0 and dialog.output.toPlainText() == ""
    assert "class identifier" in dialog.status.text()
    assert dialog.preview() is False
    dialog.extra_outputs = [dialog.output.__class__()]
    dialog.preview()  # extra editors are cleared as well


def test_close_and_main(lab):  # noqa: F811
    module, shown = lab("scaffold")
    dialog = module.build(None)
    calls = []
    dialog.lab_close = lambda: calls.append(1)
    button(dialog, "Close").click()
    assert calls == [1]
    module.main()
    assert shown[0][1] == "dialogs_classwizard"
