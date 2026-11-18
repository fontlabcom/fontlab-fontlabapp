# this_file: src/fontlabapp/fontui/appshell.py
# SPDX-License-Identifier: Apache-2.0
"""AppShell: the window every studio app shares.

What: one owned window with a resizable splitter, a tab per task, an optional
embedded preview (TGlyph on the right, or TMetrics on top) and a status line.
The shell owns the content-driven initial window size and title; embedded
widgets never size or title themselves. Later user resizing is retained.

Edits: host-mode tab writes go through ``AppShell.history(label, glyphs, ...)``.
It first calls ``core.edit_guards.require_history_scope`` and then the existing
``core.history`` commit path, so every write is one named Undo step on the
explicit live layers the caller passes. A refusal or a partial write never
raises out of a button: its message goes to the status line.

Use: ``shell = show_app("Kerning Studio", preview="tmetrics", tabs=[TabSpec(...)])``.
A tab spec is any object with ``title`` and ``build(shell)``; ``build`` returns
an ``Owned`` (closed with the shell) or a plain widget.
"""

from collections.abc import Callable, Sequence
from typing import Any

from PythonQt import QtCore, QtGui

from ..qt.properties import value
from .hinting import hint_state_of
from .lifecycle import Owned

PREVIEWS = ("tglyph", "tmetrics", None)
# Retained public values for import compatibility; initial sizing now uses content hints.
WIDTH_SHARE = 0.8
HEIGHT_SHARE = 0.75
READY_TEXT = "Ready."
NO_FONT_TEXT = "Open a font first."


def available_geometry(widget: Any) -> Any:
    """The available screen rectangle for ``widget`` (Qt 5 desktop or Qt 6 screen)."""
    screen = getattr(widget, "screen", None)
    current = screen() if callable(screen) else None
    if current is not None:
        # FontLab 9 for Windows exposes QScreen.availableGeometry as a QRect value.
        return value(current, "availableGeometry")
    return QtGui.QApplication.desktop().availableGeometry(widget)


class AppShell(Owned):
    """The shared studio window; see the module text."""

    def __init__(
        self,
        title: str,
        preview: str | None = None,
        tabs: Sequence[Any] = (),
        *,
        parent: Any = None,
        package: Callable[[], Any] | None = None,
    ):
        if preview not in PREVIEWS:
            raise ValueError(f"preview must be one of {PREVIEWS}, not {preview!r}")
        super().__init__(parent)
        self.title = title
        self.layout.setSizeConstraint(QtGui.QLayout.SetNoConstraint)
        self.preview_kind = preview
        self._package = package
        self.children: list[Any] = []
        self.preview: Any = None
        self._shown = False
        self._actions: dict[Any, dict[str, Any]] = {}
        orientation = QtCore.Qt.Vertical if preview == "tmetrics" else QtCore.Qt.Horizontal
        self.splitter = QtGui.QSplitter(orientation, self.widget)
        self.splitter.setChildrenCollapsible(False)
        self.tabs = QtGui.QTabWidget(self.splitter)
        self.preview_box = QtGui.QWidget(self.splitter)
        self.preview_layout = QtGui.QVBoxLayout(self.preview_box)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        if preview == "tmetrics":
            self.splitter.insertWidget(0, self.preview_box)
        if preview is None:
            self.preview_box.hide()
        self.status = QtGui.QLabel(READY_TEXT, self.widget)
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Status")
        self.layout.addWidget(self.splitter, 1)
        self.layout.addWidget(self.status)
        self.about = QtGui.QLabel(
            "FontLab App — shared studio tools\n"
            "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
            "Credits: FontLab App contributors. Shared shell: Apache-2.0.\nSee package NOTICE for component licences.\n"
            "Choose a task tab for its controls and help.", self.tabs
        )
        self.about.setWordWrap(True)
        self.tabs.addTab(self.about, "About")
        row = QtGui.QHBoxLayout()
        for name, label in (("refresh", "Refresh"), ("preview", "Preview Changes"),
                            ("apply", "Apply Changes"), ("close", "Close")):
            button = QtGui.QPushButton(label, self.widget)
            setattr(self, name + "_button", button)
            row.addWidget(button)
        self.connect(self.close_button.clicked, lambda *args: self._run_action("close"), closing=True)
        self._close_connection = self.connections[-1]
        for name in ("refresh", "preview", "apply"):
            self.connect(getattr(self, name + "_button").clicked, lambda *args, action=name: self._run_action(action))
        self.layout.addLayout(row)
        self.connect(self.tabs.currentChanged, lambda *args: self._update_actions())
        for spec in tabs:
            self.add_tab(spec)
        if tabs:
            self.tabs.setCurrentIndex(0)
        self._update_actions()

    def embed(self, child: Any) -> Any:
        """Own ``child``: an ``Owned`` closes with the shell. Return its widget."""
        if isinstance(child, Owned):
            self.children.append(child)
            return child.widget
        return child

    def add_tab(self, spec: Any) -> Any:
        """Build ``spec`` into a new tab and return what ``spec.build`` returned."""
        built = spec.build(self)
        if isinstance(built, Owned):
            built.as_tab_page()  # built as Owned(shell.widget), so only now is it a tab page
        self.tabs.insertTab(self.tabs.indexOf(self.about), self.embed(built), spec.title)
        if value(self.tabs, "count") == 2:
            self.tabs.setCurrentIndex(0)
        return built

    def set_about(self, text: str) -> None:
        """Set task help, source links and credits without changing task-tab state."""
        self.about.setText(text)

    def set_actions(self, tab: Any, *, refresh: Any = None, preview: Any = None,
                    apply: Any = None, dirty: Any = None, ready: Any = None,
                    apply_label: str = "Apply Changes", status: Any = None) -> None:
        """Bind explicit task actions; ``ready`` must validate the accepted plan and target.

        ``status`` returns the task's own status text; it is shown after Apply so a
        refusal the task reports in its panel is not hidden behind "Ready.".
        ``dirty`` reports staged edits. Refresh refuses to discard them; the task
        must expose its own explicit discard/revert action. Tab switches keep state.
        """
        widget = tab.widget if isinstance(tab, Owned) else tab
        self._actions[widget] = {"refresh": refresh, "preview": preview, "apply": apply,
                                 "dirty": dirty, "ready": ready, "apply_label": apply_label,
                                 "status": status}
        self._update_actions()

    def _update_actions(self) -> None:
        actions = self._actions.get(value(self.tabs, "currentWidget"), {})
        self.refresh_button.setEnabled(callable(actions.get("refresh")))
        self.preview_button.setEnabled(callable(actions.get("preview")))
        self.apply_button.setVisible(callable(actions.get("apply")))
        self.apply_button.setText(actions.get("apply_label", "Apply Changes"))
        ready = actions.get("ready")
        try:
            self.apply_button.setEnabled(callable(actions.get("apply")) and callable(ready) and bool(ready()))
        except Exception as error:  # noqa: BLE001 - a stale native target must disable Apply
            self.apply_button.setEnabled(False)
            self.status.setText(f"Error: {error}")

    def _run_action(self, action: str) -> None:
        if action == "close":
            try:
                self.close()
            except Exception as error:  # noqa: BLE001 - contain task and Qt callback failures
                self.set_status(f"Close incomplete: {error}. Retry Close.")
            return
        if self.closed:
            return
        actions = self._actions.get(value(self.tabs, "currentWidget"), {})
        callback = actions.get(action)
        if not callable(callback):
            return
        try:
            if action == "refresh" and actions.get("dirty") and actions["dirty"]():
                self.set_status("Refresh would discard staged edits. Revert or apply them in this task first.")
                return
            if action == "apply" and (not actions.get("ready") or not actions["ready"]()):
                self.set_status("Apply requires an accepted plan and a valid, unchanged target.")
                return
            callback()
            if action == "apply" and callable(actions.get("status")):
                text = actions["status"]()
                if text:
                    self.set_status(text)
        except Exception as error:  # noqa: BLE001 - contain task and Qt callback failures
            self.set_status(f"Error: {error}")
        finally:
            self._update_actions()

    def set_preview(self, preview: Any) -> Any:
        """Embed the preview widget (TGlyph or TMetrics) in the preview pane."""
        self.preview = preview
        self.preview_layout.addWidget(self.embed(preview))
        return preview

    def set_status(self, text: str) -> None:
        self.status.setText(text)
        self._update_actions()

    def package(self) -> Any:
        """The live font package the shell writes to, or None."""
        if self._package is not None:
            return self._package()
        from fontlabapp.core.scripting import current_package

        return current_package()

    def current_layer(self) -> str | None:
        """The live master name the app edits: the font's current (default) master."""
        package = self.package()
        if package is None:
            self.set_status(NO_FONT_TEXT)
            return None
        return package.defaultMaster

    def hint_check(self, name: str, layer: str | None = None) -> Any:
        """The live hint state of ``name`` on ``layer`` (default: the current master), or None.

        Studios pass this as ``hint_check=`` to the embedded TMetrics/TGlyph so
        the guard reads the package the shell writes to.
        """
        return hint_state_of(self.package(), name, layer)

    def history(
        self,
        label: str,
        glyphs: Sequence[Any],
        mutate: Callable[[], Any],
        *,
        layers: Sequence[Any],
        read_back: Callable[[], Sequence[str]] | None = None,
        operation: str = "geometry",
        native: Any = None,
        allow_bases: bool = False,
        retain: Sequence[Any] = (),
        window: int | None = None,
    ) -> Any:
        """One named Undo step over explicit live ``layers``; None when refused.

        ``allow_bases=True`` is the user's "Edit bases of auto glyphs anyway"
        opt-in; by default geometry writes to a base of an auto glyph are refused.
        ``retain`` lists native objects the write removes that Undo must keep
        (for example ejected components, fl#7641); empty keeps the plain
        two-argument notification. ``window`` (a destination package object
        id) adds the shared commit's Font-window and no-open-editors guards,
        as a write into a font that is not the shell's own needs (Layer
        Manager's Copy Layers From Font); None, the default, adds none.

        ``require_history_scope(glyphs)`` refuses before any write when the
        Glyph window would undo only part of it. Refusals, partial writes,
        scan timeouts and native/lookup errors are shown in the status line instead of raising.
        """
        import fontlabapp.core.history.glyphs as history
        from fontlabapp.core.edit_guards import require_history_scope

        try:
            require_history_scope(glyphs, creates=False, native=native)
            committed = history.commit(
                label,
                layers,
                glyphs,
                mutate,
                operation=operation,
                facts=history.scan_auto_facts(self.package()),
                read_back=read_back,
                native=native,
                allow_bases=allow_bases,
                retain=retain,
                window=window,
            )
        except history.PartialWriteError as error:
            self.set_status(f"Partly applied: {error}")
            return None
        except ValueError as error:
            self.set_status(str(error))
            return None
        except (TimeoutError, RuntimeError, TypeError, KeyError) as error:
            # Scan deadline, native refusal or a missing glyph/layer in mutate:
            # report it; the app stays usable and nothing claims success.
            self.set_status(f"Error: {error}")
            return None
        note = getattr(committed, "pending_note", "") or ""
        self.set_status(f"{label}. {note}".strip())
        return committed

    def show(self) -> None:
        """Initially fit content and equal preview panes; clamp later user resizes."""
        area = available_geometry(self.widget)
        self.widget.setWindowTitle(self.title)
        if not self._shown:
            size = value(self.widget, "sizeHint").expandedTo(value(self.widget, "minimumSizeHint"))
            if self.preview_kind is not None:
                panes = [value(pane, "sizeHint").expandedTo(value(pane, "minimumSizeHint"))
                         for pane in (self.tabs, self.preview_box)]
                splitter_hint = value(self.splitter, "sizeHint")
                handle = value(self.splitter, "handleWidth")
                # Both halves must fit the larger pane without squeezing its controls.
                if self.preview_kind == "tmetrics":
                    size.setHeight(size.height() - splitter_hint.height() + 2 * max(p.height() for p in panes) + handle)
                else:
                    size.setWidth(size.width() - splitter_hint.width() + 2 * max(p.width() for p in panes) + handle)
            self.widget.resize(size)
        self.widget.show()
        geometry = self.widget.geometry
        geometry = geometry() if callable(geometry) else geometry
        frame = self.widget.frameGeometry
        frame = frame() if callable(frame) else frame
        left, top = geometry.x() - frame.x(), geometry.y() - frame.y()
        extra_width, extra_height = frame.width() - geometry.width(), frame.height() - geometry.height()
        width = min(geometry.width(), max(1, area.width() - extra_width))
        height = min(geometry.height(), max(1, area.height() - extra_height))
        x = min(max(geometry.x(), area.x() + left), area.x() + area.width() - width - extra_width + left)
        y = min(max(geometry.y(), area.y() + top), area.y() + area.height() - height - extra_height + top)
        self.widget.setGeometry(x, y, width, height)
        if not self._shown and self.preview_kind is not None:
            extent = value(self.splitter, "height" if self.preview_kind == "tmetrics" else "width")
            self.splitter.setSizes([extent // 2, extent // 2])
        self._shown = True

    def close(self) -> None:
        self.closed = True
        if self._closing:
            raise RuntimeError("Owned cleanup is already in progress")
        self._closing = True
        try:
            while self.children:
                child = self.children[-1]
                child.close()
                if not getattr(child, "_close_complete", True):
                    raise RuntimeError("Child cleanup is incomplete; owner retained")
                self.children.pop()
        except BaseException as error:
            self._close_error = error
            raise
        finally:
            self._closing = False
        try:
            super().close()
        except BaseException:
            if self._close_connection not in self.connections and not self.destroying:
                self.connect(self.close_button.clicked, lambda *args: self._run_action("close"), closing=True)
                self._close_connection = self.connections[-1]
            raise


def show_app(
    title: str,
    preview: str | None = None,
    tabs: Sequence[Any] = (),
    *,
    parent: Any = None,
    package: Callable[[], Any] | None = None,
) -> AppShell:
    """Build, size, title and show an ``AppShell``; return it."""
    shell = AppShell(title, preview, tabs, parent=parent, package=package)
    shell.show()
    return shell
