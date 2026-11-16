# this_file: tests/test_issue205_widgets.py
"""Real owned dock/dialog/widget state and failure cleanup on the Qt adapter."""

import importlib

import pytest
from legacy_panel_qt import QtCore, QtWidgets, legacy_qt as legacy_qt
from shiboken6 import isValid


@pytest.mark.parametrize("visible", [False, True])
def test_panel_when_registered_then_owned_floating_state_and_context_teardown_are_exact(
    legacy_qt, visible
):
    module = importlib.import_module("fontlabapp.qt.widgets")
    main = QtWidgets.QMainWindow()
    legacy_qt.owned.append(main)
    if visible:
        main.show()
    built = []
    with module.create_panel(main, "Owned dock", built.append, "left") as owned:
        dock, content = owned.widget, owned.content
        assert built == [content] and dock.widget() is content
        assert main.dockWidgetArea(dock) == QtCore.Qt.LeftDockWidgetArea
        assert dock.isFloating() is (not visible)
        assert dock.objectName().startswith("fontlabappPanel_") and not owned.closed
    assert owned.closed and owned.widget is owned.content is None
    owned.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(dock)
    with pytest.raises(ValueError, match="Dock area"):
        module.create_panel(main, "Bad area", None, "invalid")


def test_owned_widgets_when_closed_destroyed_or_build_fails_then_only_owned_resources_are_released(
    legacy_qt,
):
    module = importlib.import_module("fontlabapp.qt.widgets")
    main = QtWidgets.QMainWindow()
    legacy_qt.owned.append(main)
    dialog = module.create_dialog(main, "Owned dialog", None)
    assert dialog.widget.windowTitle() == "Owned dialog" and not dialog.widget.isModal()
    dialog.close()
    child = module.create_widget(main, None, show=False)
    assert child.widget.parent() is main and not child.widget.isVisible()
    child.close()
    floating = module.create_widget(main, None, floating=True)
    assert (
        floating.widget.isVisible() and floating.widget.windowFlags() & QtCore.Qt.Tool
    )
    widget = floating.widget
    widget.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert floating.closed and floating.content is None
    floating.close()
    built = []

    def fail(content):
        built.append(content)
        raise RuntimeError("owned build failure")

    with pytest.raises(RuntimeError, match="owned build failure"):
        module.create_widget(main, fail)
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(built[0]) and isValid(main)


def test_panel_when_registration_fails_then_created_dock_is_destroyed(legacy_qt):
    module = importlib.import_module("fontlabapp.qt.widgets")

    class Main(QtWidgets.QMainWindow):
        def addDockWidget(self, area, dock):
            self.attempted = dock
            raise RuntimeError("owned registration failure")

    main = Main()
    legacy_qt.owned.append(main)
    with pytest.raises(RuntimeError, match="owned registration failure"):
        module.create_panel(main, "Owned", None, "right")
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(main.attempted) and isValid(main)
