# this_file: tests/test_wp08_reference_images.py
"""The practical image shell keeps the original viewer and its cleanup refusal."""

import importlib
import sys

import pytest

from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def images(studio_qt, monkeypatch):  # noqa: F811
    name = "fontlabapp.fontui.reference_images"
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)
    yield module, studio_qt
    for shell in tuple(module._HANDLES):
        shell.close()
    sys.modules.pop(name, None)


def test_shell_when_opened_then_embeds_original_read_only_image_workflow(images, tmp_path):
    module, env = images
    shell = module.show()
    viewer = shell.images.viewer
    assert viewer.part == 2 and not viewer.isWindow()
    assert shell.preview_kind is None and shell.apply_button.isHidden()
    assert shell.tabs.tabText(0) == "Image" and shell.tabs.tabText(1) == "About"
    image = module.QtGui.QImage(120, 80, module.QtGui.QImage.Format_ARGB32)
    image.fill(module.QtGui.QColor("red"))
    path = tmp_path / "reference.png"
    assert image.save(str(path))
    original = path.read_bytes()
    assert viewer.load(str(path))
    viewer.commands["zoom_in"].trigger()
    assert viewer.scale == 1.25
    viewer.commands["fit"].trigger()
    assert viewer.fit
    viewer.commands["fit"].trigger()
    assert viewer.scale == 1.25
    viewer.commands["normal"].trigger()
    assert viewer.scale == 1
    dialog = viewer.open_file()
    assert dialog.parent() is viewer and dialog.isVisible()
    dialog.reject()
    assert path.read_bytes() == original
    viewer.commands["exit"].trigger()
    assert shell._close_complete and viewer.closed and shell not in module._HANDLES


@pytest.mark.parametrize("terminal", ["button", "escape", "viewer-close"])
def test_close_when_viewer_refuses_then_retains_owner_for_retry(images, monkeypatch, terminal):
    module, env = images
    shell = module.show()
    viewer = shell.images.viewer
    dispose = viewer.dispose
    monkeypatch.setattr(viewer, "dispose", lambda: False)
    if terminal == "button":
        shell.close_button.click()
    elif terminal == "escape":
        event = module.QtGui.QKeyEvent(env.QtCore.QEvent.KeyPress, env.QtCore.Qt.Key_Escape,
                                      env.QtCore.Qt.NoModifier)
        viewer.keyPressEvent(event)
    else:
        viewer.close()
    assert not shell._close_complete and shell.images in shell.children
    assert shell in module._HANDLES and "Retry Close" in shell.status.text()
    monkeypatch.setattr(viewer, "dispose", dispose)
    shell.close_button.click()
    assert shell._close_complete and shell not in module._HANDLES
    shell.close()


def test_show_when_construction_fails_then_closes_or_retains_failed_cleanup(images, monkeypatch):
    module, env = images

    def fail(*args):
        raise ValueError("viewer construction")

    monkeypatch.setattr(module, "panel_type", fail)
    with pytest.raises(ValueError, match="viewer construction"):
        module.show()
    assert module._HANDLES == []


def test_show_when_called_off_main_thread_then_refuses_before_shell(images, monkeypatch):
    module, env = images
    monkeypatch.setattr(module, "current_thread", lambda: object())
    with pytest.raises(RuntimeError, match="main UI thread"):
        module.show()
    assert module._HANDLES == []
