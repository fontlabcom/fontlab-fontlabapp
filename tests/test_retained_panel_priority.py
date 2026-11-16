# this_file: tests/test_retained_panel_priority.py
"""Actual Qt constructor failures keep their retry window and priority."""

from module_paths import module_name as _module_name
import importlib
import sys

import pytest

from test_spacing_worksheet import GUI, QtCore, drain

CASES = [
    ("anchor_duplicates_panel", None), ("background_clear_panel", False),
    ("background_clear_panel", True), ("crossfont_anchors_panel", None),
    ("regexp_panel", None), ("spacing_panel", False), ("spacing_panel", True),
    *[(name, part) for name in ("character_map_panel", "elastic_panel", "image_viewer_panel", "slider_panel", "spinbox_panel") for part in (2, 3)],
]


@pytest.mark.parametrize("name,profile", CASES)
def test_constructor_when_setup_and_cleanup_fail_then_visible_priority_and_exact_error(
    name, profile, monkeypatch, tmp_path
):
    module = importlib.import_module(_module_name(name))
    parent = GUI.QWidget()
    factory_args = (QtCore, GUI)
    if name in ("background_clear_panel", "character_map_panel", "image_viewer_panel"):
        factory_args += (profile,)
    kind = module.panel_type(*factory_args)
    base = kind.__bases__[0]
    control = base(parent) if issubclass(base, GUI.QDialog) else base(parent, QtCore.Qt.Window)
    expected_flags = control.windowFlags() | QtCore.Qt.WindowStaysOnTopHint
    control.deleteLater()
    error = RuntimeError("original setup failure")
    owners, shown = [], []

    def fail(owner, *args):
        owners.append(owner)
        raise error

    def show(owner):
        shown.append((owner.windowFlags(), owner.parentWidget()))
        GUI.QWidget.show(owner)

    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    monkeypatch.setattr(kind, "show", show)
    monkeypatch.setattr(kind, "close", lambda owner: False)
    if name == "image_viewer_panel":
        monkeypatch.setattr(kind, "dispose", lambda owner, **kwargs: False)
    if name == "elastic_panel":
        monkeypatch.setattr(kind, "build", fail)
    else:
        monkeypatch.setattr(module, "build", fail)
    args, kwargs = (parent, lambda **kwargs: None), {}
    if name in ("elastic_panel", "slider_panel", "spinbox_panel"):
        args += (profile,)
    if name == "spacing_panel":
        kwargs["official"] = profile
    if name == "image_viewer_panel":
        args, kwargs = (parent,), {"temporary_parent": tmp_path}
    try:
        with pytest.raises(RuntimeError) as caught:
            kind(*args, **kwargs)
        assert caught.value is error, "Keep the original setup exception"
        owner = owners[0]
        assert list(sys._fontlab_samples.values()) == [owner], "Keep the exact retry owner"
        assert shown and shown[0][0] & QtCore.Qt.WindowStaysOnTopHint, "Priority must precede error-window show"
        expected_type = QtCore.Qt.Dialog if name in ("anchor_duplicates_panel", "background_clear_panel", "crossfont_anchors_panel") else QtCore.Qt.Window
        assert shown[0][0] & QtCore.Qt.WindowType_Mask == expected_type, "Preserve the native window type"
        assert shown[0][0] == expected_flags, "Preserve every original window flag and chrome hint"
        assert shown[0][1] is parent and owner.isVisible(), "Keep parent and visible retry window"
        assert owner.terminal.records, "Keep owned terminal signals until cleanup succeeds"
    finally:
        for owner in owners:
            for scope_name in ("scope", "signals", "closers", "terminal"):
                scope = getattr(owner, scope_name, None)
                if scope is not None:
                    assert scope.finish(), "Release test-owned signals before native deletion"
            if name == "image_viewer_panel":
                owner.workspace.close()
            owner.hide()
            owner.deleteLater()
        parent.deleteLater()
        drain()
