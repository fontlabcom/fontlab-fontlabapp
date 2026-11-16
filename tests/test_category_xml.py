# this_file: tests/test_category_xml.py
import plistlib
from types import SimpleNamespace as NS

import fontlabapp.features.categories.model as api
import pytest


def test_render_complete_original_mapping_and_xml_escaping():
    report = api.CategorySnapshot(
        7,
        (
            ("A&B<", "Letter"),
            ("acutecomb", "Mark"),
            ("f_i", "Ligature"),
            ("unknown", None),
        ),
    )
    text = api.render(report)
    parsed = plistlib.loads(("<plist><dict>" + text + "</dict></plist>").encode())
    assert list(parsed["public.openTypeCategories"].items()) == [
        ("A&B<", "base"),
        ("acutecomb", "mark"),
        ("f_i", "base"),
        ("unknown", "base"),
    ]


def test_render_empty_font_keeps_original_empty_dictionary():
    assert "<dict>\n\n    </dict>" in api.render(api.CategorySnapshot(1, ()))


@pytest.fixture
def host(monkeypatch):
    glyphs = [
        NS(id=10, name="A", unicodes=[65]),
        NS(id=11, name="acutecomb", unicodes=[769]),
    ]
    font = NS(id=1, isNull=False, glyphs=glyphs)
    monkeypatch.setattr(api, "_native", lambda name: NS(CurrentFont=lambda: font))
    return font


def test_capture_all_glyphs_and_classifies_every_record_twice(host):
    calls = []

    def classify(name, codes):
        calls.append((name, codes))
        return ("Mark" if codes == ["0301"] else "Letter", None)

    report = api.capture(classify)
    assert report.rows == (("A", "Letter"), ("acutecomb", "Mark"))
    assert len(calls) == 4


def test_capture_missing_font_refuses(monkeypatch):
    monkeypatch.setattr(api, "_native", lambda _: NS(CurrentFont=lambda: None))
    with pytest.raises(ValueError, match="Open a font"):
        api.capture(lambda *_: (None, None))


def test_capture_changed_category_refuses(host):
    calls = iter([("Letter", None), ("Mark", None), ("Other", None), ("Mark", None)])
    with pytest.raises(ValueError, match="changed"):
        api.capture(lambda *_: next(calls))


def test_capture_changed_glyph_order_refuses(host):
    def classify(*args):
        host.glyphs[0].name = "changed"
        return (None, None)

    with pytest.raises(ValueError, match="changed"):
        api.capture(classify)


def test_capture_deadline_refuses_complete_result(host, monkeypatch):
    clock = iter([0, 0, 3])
    monkeypatch.setattr(api, "monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError, match="deadline"):
        api.capture(lambda *_: (None, None))


def test_capture_classifier_failure_is_not_base(host):
    def fail(*args):
        raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        api.capture(fail)


def test_capture_invalid_category_refuses(host):
    with pytest.raises(TypeError, match="category"):
        api.capture(lambda *_: (42, None))


def test_dialog_policy_and_all_callbacks_use_shared_panel(monkeypatch):
    import importlib
    import sys

    class Panel:
        def __init__(self, *args):
            self.args = args

    monkeypatch.setitem(
        sys.modules, "fontlabapp.proof.reports.snapshot_ui", NS(SnapshotTextDialog=Panel)
    )
    sys.modules.pop("fontlabapp.features.categories.ui", None)
    ui = importlib.import_module("fontlabapp.features.categories.ui")
    policy = lambda *_: (None, None)
    report = api.CategorySnapshot(1, ())
    monkeypatch.setattr(
        api, "capture", lambda classifier: report if classifier is policy else None
    )
    panel = ui.dialog_type(policy)("parent")
    assert panel.args[0] == "parent"
    assert panel.args[4]() is report
    assert panel.args[5](report) == api.render(report)
    assert panel.args[6](report) == "0 glyphs. No font or file changes."
    sys.modules.pop("fontlabapp.features.categories.ui", None)


def test_original_source_mapping_with_complete_categories():
    rows = tuple(
        (str(index), category)
        for index, category in enumerate(
            (
                "Mark",
                "Letter",
                "Number",
                "Separator",
                "Symbol",
                "Punctuation",
                None,
                "mark",
                "Ligature",
                "Component",
            )
        )
    )
    text = api.render(api.CategorySnapshot(1, rows))
    assert text.count("<string>mark</string>") == 1
    assert text.count("<string>base</string>") == 9


def test_show_lazy_shared_route(monkeypatch):
    import sys
    from types import ModuleType

    ui = ModuleType("fontlabapp.features.categories.ui")
    scripting = ModuleType("fontlabapp.core.scripting")
    policy = lambda *_: (None, None)
    panel = type("Panel", (), {"KEY": "category_xml"})
    ui.dialog_type = lambda classifier: panel if classifier is policy else None
    scripting.show_script_dialog = lambda kind, key: (kind, key)
    monkeypatch.setitem(sys.modules, ui.__name__, ui)
    monkeypatch.setitem(sys.modules, scripting.__name__, scripting)
    assert api.show(policy) == (panel, "category_xml")
