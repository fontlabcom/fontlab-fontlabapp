# this_file: src/fontlabapp/fontui/node_editor/ui.py
# SPDX-License-Identifier: Apache-2.0
"""One AppShell for five node tasks, with a captured read-only TGlyph view."""

from PythonQt import QtCore, QtGui

import fontlabapp.fontui as fontui
from fontlabapp.core import scripting
from fontlabapp.fontui.appshell import AppShell
from fontlabapp.fontui.lifecycle import Owned
from . import preview as overlays
from fontlabapp.studios import TabSpec
from fontlabapp.fontui.node_editor.session import NativePlan, PerGlyphPlan

TITLE = "Node Editor"
OPEN_WINDOWS = []
ABOUT = """Node Editor
Per-glyph duplication uses each glyph's own reference selection and compatible
master policy. The three literal policies use the first selected layer: Current
Layer, All Foreground Layers, and Two Handles. They remain distinct operations.
Preview Changes accepts the displayed plan; Apply refuses changed targets.
Discard staged changes before refreshing. Coordinates tracks selected nodes in
the captured font and Copy rechecks the displayed snapshot.
Credits: independent behaviour rewrite after Fernando Díaz, Reset Type Studio;
https://github.com/Reset-Type-Studio/Glyphs-Scripts (Apache-2.0 in README).
FontLab App contributors: https://github.com/fontlabcom/fontlab-fontlabapp
"""


class NodeShell(AppShell):
    """Retain a failed-close window, release the registry only after cleanup ACK."""

    def close(self):
        super().close()
        if self in OPEN_WINDOWS:
            OPEN_WINDOWS.remove(self)


class PanelOwner(Owned):
    """Embed existing task controls, owning their exact timer and signal teardown."""

    def __init__(self, shell, panel_type):
        super().__init__(shell.widget)
        self.panel = None
        shell.children.append(self)
        panel = panel_type.__new__(panel_type)
        self.panel = panel
        panel_type.__init__(panel, self.widget)
        panel.setWindowFlags(QtCore.Qt.Widget)
        self.layout.addWidget(panel)
        for name in ("close_button", "apply_button", "reload_button"):
            button = getattr(panel, name, None)
            if button is not None:
                button.setEnabled(False)
                button.setDefault(False)
                button.setAutoDefault(False)
                button.hide()

    def close(self):
        self.closed = True
        if self.panel is not None:
            timer = getattr(self.panel, "timer", None)
            if timer is not None:
                timer.stop()
                if timer.isActive():
                    raise RuntimeError("Node coordinate timer did not stop; retry Close.")
            for pair in reversed(tuple(getattr(self.panel, "_connections", ()))):
                signal, slot = pair
                if signal.disconnect(slot) is False:
                    raise RuntimeError("Node control disconnect refused; retry Close.")
                self.panel._connections.remove(pair)
            self.panel.package = None
            self.panel.glyphs = []
            self.panel._closed = True
        super().close()


class WriteTab(Owned):
    """Literal-mode controls and explicit accepted-plan lifecycle."""

    def __init__(self, shell, package, mode, preview):
        super().__init__(shell.widget)
        self.shell, self.preview_view = shell, preview
        self.session = NativePlan(package, mode)
        self.details = QtGui.QLabel(
            "Select source nodes, then Preview Changes. "
            "The first selected layer supplies indices for this policy.", self.widget)
        self.details.setWordWrap(True)
        self.layout.addWidget(self.details)
        self.bind()

    def bind(self):
        self.last_error = None
        self.discard_button = QtGui.QPushButton("Discard staged changes", self.widget)
        self.layout.addWidget(self.discard_button)
        self.connect(self.discard_button.clicked, lambda *a: self.discard())
        self.shell.set_actions(self, refresh=self.refresh, preview=self.preview,
                               apply=self.apply, dirty=lambda: self.session.dirty,
                               ready=lambda: self.session.dirty)

    def discard(self):
        self.session.discard()
        if self.preview_view is not None:
            self.preview_view.set_overlay(None)
        self.shell.set_status("Staged changes discarded. Preview again before Apply.")

    def refresh(self):
        self.session.target()
        if self.session.dirty:
            raise ValueError("Discard staged changes before refreshing.")
        self.preview_view.refresh()
        self.shell.set_status("Selection refreshed. Preview Changes before Apply.")

    def preview(self):
        result = self.session.preview()
        before = self.session.accepted
        if not before.bound:
            self.session.discard()
            raise ValueError("Select a glyph layer before previewing nodes.")
        glyph, layer = next(iter(before.bound.values()))
        try:
            self.preview_view.load(str(glyph.name), str(layer.name))
            overlay = overlays.literal(self.preview_view.model.data, before, result, layer.id)
            self.preview_view.set_overlay(overlay)
        except BaseException:
            self.session.discard()
            raise
        self.details.setText(
            f"{result.inserted} inserted nodes; {len(result.skipped)} skipped indices.\n"
            f"{result.no_selection_message or ''}\n"
            + "\n".join(f"{g.name} · {layer.name}" for g, layer in before.bound.values()))
        self.shell.set_status("Preview accepted. Apply uses this exact captured source.")

    def apply(self):
        try:
            result = self.session.apply()
        except BaseException as error:
            self.last_error = error
            raise
        self.preview_view.set_overlay(None)
        self.preview_view.refresh()
        self.shell.set_status(f"Applied: {result}. Use Edit > Undo to undo the operation.")

    def close(self):
        self.session.discard()
        super().close()


class DuplicateTab(PanelOwner):
    """The per-glyph controls embedded directly, without a secondary window."""

    def __init__(self, shell, package, preview):
        from fontlabapp.fontui.node_editor.duplicate import DuplicatePanel

        captured_id = package.id

        class BoundPanel(DuplicatePanel):
            def read_font(self):
                self.package = scripting.current_package(captured_id)
                if self.package is None:
                    raise ValueError("The captured font changed; reopen Node Editor.")
                self.package_id = captured_id
                self.masters = list(self.package.masters)
                self.current_master = self.package.master

        super().__init__(shell, BoundPanel)
        self.shell, self.preview_view = shell, preview
        self.session = PerGlyphPlan(package, self.panel)
        WriteTab.bind(self)

    discard = WriteTab.discard
    apply = WriteTab.apply

    def refresh(self):
        self.session.target()
        if self.session.dirty:
            raise ValueError("Discard staged changes before refreshing.")
        self.panel.reload()
        self.preview_view.refresh()

    def preview(self):
        plan = self.session.preview()
        glyph, layer, edits = plan.work[0]
        try:
            self.preview_view.load(str(glyph.name), str(layer.name))
            self.preview_view.set_overlay(overlays.per_glyph(self.preview_view.model.data, layer, edits))
        except BaseException:
            self.session.discard()
            raise
        self.shell.set_status(self.panel.summary(plan) + ". Preview accepted.")

    def close(self):
        if hasattr(self, "session"):
            self.session.discard()
        super().close()


class CoordinatesTab(PanelOwner):
    """Live coordinate and distance tables with the original guarded Copy."""

    def __init__(self, shell, package, preview):
        from fontlabapp.fontui.node_editor.coordinates import NodePanel

        super().__init__(shell, NodePanel)
        if self.panel._bound_id != package.id:
            raise ValueError("The captured font changed while opening coordinates.")
        self.preview_view, self.shell = preview, shell
        self.connect(self.panel.timer.timeout, lambda *a: self.follow())
        shell.set_actions(self, refresh=self.panel.tick, apply=self.panel.apply,
                          ready=lambda: self.panel._snapshot_valid, apply_label="Copy Coordinates")

    def follow(self):
        try:
            if self.shell.tabs.currentWidget() is not self.widget:
                return
            if self.panel._snapshot_valid and self.panel.signature[0] is not None:
                name, layer, _ = self.panel.signature
                self.preview_view.load(name, layer)
        except Exception as error:  # noqa: BLE001 - contain the native timer callback
            self.panel.show_error(error)
            self.shell.set_status(str(error))


def show(parent=None):
    """Capture once, build all controls and retain any failed-close owner for retry."""
    package = scripting.current_package()
    if package is None:
        raise ValueError("Open a font before opening Node Editor.")
    shell = NodeShell(TITLE, "tglyph", parent=parent,
                     package=lambda: scripting.current_package(package.id))
    OPEN_WINDOWS.append(shell)
    try:
        shell.set_about(ABOUT)
        font = fontui.current_font()
        preview = fontui.glyph_view(font, parent=shell.widget, layer=str(package.master),
                                    controls=False, read_only=True, hint_check=shell.hint_check)
        shell.set_preview(preview)
        # PanelOwner registers before construction can fail; add_tab must not own it twice.
        def embedded(cls):
            owner = cls(shell, package, preview)
            return owner.widget

        shell.add_tab(TabSpec("Per-glyph Duplicator", lambda s: embedded(DuplicateTab)))
        for title, mode in (("Current Layer", "current"), ("All Foreground Layers", "all"),
                            ("Two Handles", "handles")):
            shell.add_tab(TabSpec(title, lambda s, m=mode: fontui._construct(WriteTab, s, package, m, preview)))
        shell.add_tab(TabSpec("Coordinates", lambda s: embedded(CoordinatesTab)))
        shell.show()
    except BaseException as error:
        fontui.cleanup_failed_window(shell, error)
        raise
    return shell
