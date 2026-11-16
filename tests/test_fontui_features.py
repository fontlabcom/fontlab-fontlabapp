# this_file: tests/test_fontui_features.py
"""B08: staged blocks, exact line endings, one Apply with readback."""

import importlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fontlabapp.fontui.features_state import PREFIX, FeatureState, line_ending

PREFIX_TEXT = "languagesystem DFLT dflt;\n# Ω\n"
LIGA = "feature liga {\n  sub f i by f_i; # 日本\n} liga;\n"


@pytest.fixture
def editor_class(monkeypatch):
    from _feature_source_qt import owned_application, dispose_controls
    widgets = []
    with owned_application():
        for name in ("features", "lifecycle"):
            monkeypatch.delitem(sys.modules, f"fontlabapp.fontui.{name}", raising=False)
        monkeypatch.setitem(sys.modules, "PythonQt", SimpleNamespace(QtGui=Mock()))
        monkeypatch.setitem(sys.modules, "fontlab", None)  # outside FontLab
        cls = importlib.import_module("fontlabapp.fontui.features").FeaturesEditor
        cls._source_widgets = widgets
        try:
            yield cls
        finally:
            dispose_controls(widgets)
        for name in ("features", "lifecycle"):
            sys.modules.pop(f"fontlabapp.fontui.{name}", None)


class Blocks:
    """Fontport-like structured model."""

    def __init__(self, prefix=PREFIX_TEXT, features=(("liga", LIGA),)):
        self.value = {"prefix": prefix, "features": list(features)}
        self.calls = []

    @property
    def text(self):
        return self.value["prefix"] + "".join(c for _, c in self.value["features"])

    def get_blocks(self):
        return {
            "prefix": self.value["prefix"],
            "features": list(self.value["features"]),
        }

    def set_blocks(self, values, *, undo_name):
        self.calls.append((values, undo_name))
        self.value = {"prefix": values["prefix"], "features": list(values["features"])}


class WholeText:
    def __init__(self, text):
        self.text, self.calls = text, []

    def apply(self, text, *, undo_name):
        self.calls.append(text)
        self.text = text


class TextControl:
    """Mimic QPlainTextEdit: every line break is shown as LF."""

    def __init__(self):
        self.value, self.readOnly = "", False

    def setPlainText(self, text):
        self.value = text.replace("\r\n", "\n").replace("\r", "\n")

    def toPlainText(self):
        return self.value

    def setReadOnly(self, flag):
        self.readOnly = flag

    def setEnabled(self, flag):
        pass


class Combo:
    def __init__(self):
        self.items, self.currentIndex = [], -1

    def blockSignals(self, flag):
        return False

    def clear(self):
        self.items = []

    def addItems(self, items):
        self.items += list(items)

    def setCurrentIndex(self, index):
        self.currentIndex = index

    def setEnabled(self, flag):
        pass


def make(cls, features):
    editor = cls.__new__(cls)
    editor.closed, editor.key, editor.state = False, PREFIX, None
    editor.font = SimpleNamespace(features=features)
    from _feature_source_qt import TextAdapter
    editor.text_control, editor.block_control = TextAdapter(editor, cls._source_widgets), Combo()
    editor.tag_control = SimpleNamespace(text="", setText=Mock(), setEnabled=Mock())
    for name in (
        "status",
        "diagnostic",
        "apply_button",
        "revert_button",
        "add_button",
        "remove_button",
    ):
        setattr(editor, name, Mock())
    editor.on_apply = Mock()
    assert editor.refresh()
    return editor


def message(editor):
    return editor.diagnostic.setText.call_args.args[0]


def select(editor, key):
    editor.block_control.currentIndex = editor.state.keys().index(key)
    editor._switch()


@pytest.mark.parametrize(
    "text,ending",
    [
        ("a\r\nb\r\n", "\r\n"),
        ("a\rb\r", "\r"),
        ("a\nb", "\n"),
        ("", "\n"),
        ("a\r\nb\n", None),
    ],
)
def test_line_ending_detection(text, ending):
    assert line_ending(text) == ending


@pytest.mark.parametrize("newline", ["\r\n", "\r", "\n"])
def test_state_restores_each_blocks_own_line_ending(newline):
    code = newline.join(["feature liga {", "} liga;", ""])
    state = FeatureState({"prefix": "p;\n", "features": [("liga", code)]})
    state.set_text("liga", "feature liga {\n  sub a by b;\n} liga;\n")
    assert dict(state.value()["features"])["liga"] == newline.join(
        ["feature liga {", "  sub a by b;", "} liga;", ""]
    )
    assert state.value()["prefix"] == "p;\n"


def test_state_refuses_rewriting_mixed_endings_but_allows_unchanged():
    state = FeatureState({"prefix": "a;\r\nb;\n", "features": []})
    state.set_text(PREFIX, "a;\nb;\n")
    assert not state.dirty
    with pytest.raises(ValueError, match="Mixed"):
        state.set_text(PREFIX, "a;\nc;\n")


def test_state_add_remove_and_duplicates():
    state = FeatureState({"prefix": "", "features": [("liga", LIGA)]})
    state.add("kern")
    assert state.keys() == [PREFIX, "liga", "kern"] and state.dirty
    with pytest.raises(ValueError, match="already exists"):
        state.add("liga")
    with pytest.raises(ValueError, match="prefix"):
        state.remove(PREFIX)
    state.remove("kern")
    assert not state.dirty


def test_features_factory_import_stays_host_free():
    code = (
        "import sys\nfrom fontlabapp.fontui import features_editor\n"
        "assert callable(features_editor) and 'PythonQt' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_block_edits_are_staged_then_applied_once(editor_class):
    features = Blocks()
    editor = make(editor_class, features)
    assert editor.block_control.items == [PREFIX, "liga"] and not editor.dirty
    select(editor, "liga")
    edited = "feature liga {\n  sub f l by f_l;\n} liga;\n"
    editor.text_control.value = edited
    assert editor.dirty and not features.calls
    assert editor.apply() is True
    assert features.calls == [
        ({"prefix": PREFIX_TEXT, "features": [("liga", edited)]}, "Edit font features")
    ]
    editor.on_apply.assert_called_once_with(editor.font, PREFIX_TEXT + edited)
    assert not editor.dirty and editor.key == "liga"


def test_crlf_document_is_written_back_with_crlf(editor_class):
    prefix = "languagesystem DFLT dflt;\r\n"
    features = Blocks(
        prefix=prefix, features=[("liga", "feature liga {\r\n} liga;\r\n")]
    )
    editor = make(editor_class, features)
    editor.text_control.value = "languagesystem DFLT dflt;\n# Ω\n"
    assert editor.apply() is True
    assert features.value["prefix"] == "languagesystem DFLT dflt;\r\n# Ω\r\n"
    assert features.value["features"] == [("liga", "feature liga {\r\n} liga;\r\n")]


def test_add_and_remove_feature_blocks(editor_class):
    features = Blocks()
    editor = make(editor_class, features)
    editor.tag_control.text = "kern"
    assert editor.add_feature() and editor.key == "kern"
    assert editor.apply() is True
    assert [t for t, _ in features.value["features"]] == ["liga", "kern"]
    select(editor, "liga")
    assert editor.remove_feature() and editor.apply() is True
    assert [t for t, _ in features.value["features"]] == ["kern"]


def test_revert_noop_and_malformed_code_is_stored(editor_class):
    features = Blocks()
    editor = make(editor_class, features)
    assert editor.apply() is False and message(editor) == "No changes to apply."
    editor.text_control.value = "garbage {"
    assert (
        editor.revert()
        and editor.text_control.value == PREFIX_TEXT
        and not features.calls
    )
    editor.text_control.value = "feature liga { sub ;"
    assert editor.apply() is True, "code is stored, not compiled"


def test_whole_text_model_and_mixed_refusal(editor_class):
    model = WholeText("a;\r\nb;\r\n")
    editor = make(editor_class, model)
    assert editor.block_control.items == ["Feature text"]
    editor.text_control.value = "a;\nc;\n"
    assert editor.apply() is True and model.text == "a;\r\nc;\r\n"
    mixed = WholeText("a;\r\nb;\n")
    editor = make(editor_class, mixed)
    editor.text_control.value = "x;\n"
    assert (
        editor.apply() is False
        and "Mixed" in message(editor)
        and mixed.text == "a;\r\nb;\n"
    )


def test_readonly_backend_error_and_ignored_write(editor_class):
    editor = make(editor_class, SimpleNamespace(text=LIGA))
    assert editor.text_control.readOnly and "read-only" in message(editor)
    failing = Blocks()
    failing.set_blocks = Mock(
        side_effect=ValueError("Feature block 'liga': history code differs")
    )
    editor = make(editor_class, failing)
    editor.text_control.value = "x;\n"
    assert editor.apply() is False and "history code differs" in message(editor)
    ignored = Blocks()
    ignored.set_blocks = Mock()
    editor = make(editor_class, ignored)
    editor.text_control.value = "x;\n"
    assert editor.apply() is False and "differs" in message(editor)
    editor.on_apply.assert_not_called()
    editor.closed = True
    assert editor.apply() is False and editor.refresh() is False


@pytest.mark.parametrize("dirty", [True, False])
def test_external_change_keeps_staged_text_or_reloads(editor_class, dirty, monkeypatch):
    editor = editor_class.__new__(editor_class)
    editor.closed = False
    monkeypatch.setattr(editor_class, "dirty", property(lambda self: dirty))
    editor.refresh, editor.diagnostic = Mock(return_value=True), Mock()
    editor._changed()
    if dirty:
        editor.refresh.assert_not_called()
        assert "Revert" in editor.diagnostic.setText.call_args.args[0]
    else:
        editor.refresh.assert_called_once_with()
