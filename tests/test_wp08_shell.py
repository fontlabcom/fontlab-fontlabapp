# this_file: tests/test_wp08_shell.py
"""Exercise the native PythonQt property shape when adding practical tabs."""

from types import SimpleNamespace

from _studio_qt import studio_qt  # noqa: F401


def test_first_task_when_count_is_property_then_selected(studio_qt):  # noqa: F811
    module = studio_qt.modules.appshell
    app = module.AppShell("Reports")
    studio_qt.owned.append(app)
    tabs = app.tabs
    app.tabs = SimpleNamespace(
        count=2, insertTab=tabs.insertTab, indexOf=tabs.indexOf,
        setCurrentIndex=tabs.setCurrentIndex,
    )
    page = module.QtGui.QWidget()
    app.add_tab(SimpleNamespace(title="Report", build=lambda owner: page))
    assert tabs.currentWidget() is page


def test_actions_when_current_widget_is_property_then_dispatch(studio_qt):  # noqa: F811
    module = studio_qt.modules.appshell
    app = module.AppShell("Reports")
    studio_qt.owned.append(app)
    page = module.QtGui.QWidget()
    app.tabs = SimpleNamespace(currentWidget=page)
    calls = []
    app.set_actions(page, refresh=lambda: calls.append("refresh"))
    app.refresh_button.click()
    assert calls == ["refresh"]
