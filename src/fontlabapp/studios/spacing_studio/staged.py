# this_file: src/fontlabapp/studios/spacing_studio/staged.py
# SPDX-License-Identifier: Apache-2.0
"""Stage the existing spacing actions for the shared shell's explicit Apply."""

from typing import Any

from PythonQt import QtGui

from fontlabapp.core.scripting import advance_widths_backends, spacing_offset_backends

ACTIONS = {
    "Apply to sidebearings": ("Preview sidebearings", "tune"),
    "Equalize sidebearings": ("Preview equalized sidebearings", "equalize"),
    "Centre in advance": ("Preview centred advance", "centre"),
    "Copy from reference": ("Preview reference metrics", "copy"),
    "Sync sidebearings": ("Preview synced sidebearings", "sync"),
    "Apply italic spacing": ("Preview italic spacing", "apply"),
}


def value(value: Any) -> Any:
    return value() if callable(value) else value


def buttons(layout: Any) -> Any:
    """Walk layout items without materializing PythonQt native child lists."""
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.layout() is not None:
            yield from buttons(item.layout())
        elif isinstance(item.widget(), QtGui.QPushButton):
            yield item.widget()


def capture(getter: Any) -> Any:
    """Bind the first successful read; failed startup remains recoverable."""
    from .._kerning_app import capture_source

    return capture_source(getter, deferred=True)


class Staged:
    """Keep a tab's accepted rows and refuse changed controls, sources or targets."""

    def __init__(self, panel: Any) -> None:
        self.panel = panel
        self.studio = panel.studio
        self.request: Any = None
        self.accepted: Any = None
        self.action = next((getattr(panel, method) for _, method in ACTIONS.values()
                            if hasattr(panel, method)), panel.refresh)

    def draft(self) -> tuple:
        fields = []
        for name, widget in vars(self.panel).items():
            if isinstance(widget, QtGui.QLineEdit):
                fields.append((name, value(widget.text)))
            elif isinstance(widget, QtGui.QComboBox):
                fields.append((name, value(widget.currentIndex)))
            elif isinstance(widget, QtGui.QCheckBox):
                fields.append((name, value(widget.isChecked)))
        return self.studio.master, tuple(fields)

    def preview(self, action: Any = None) -> Any:
        """Run an original action with its write boundary replaced by planning."""
        self.request = self.accepted = None
        self.studio.reload(preserve=self.studio.master is not None)
        if action is not None:
            self.action = action
        run = self.panel.run
        self.panel.run = self.stage
        try:
            return self.action()
        finally:
            self.panel.run = run

    def choose(self, action: Any) -> None:
        self.action = action
        self.studio.shell._run_action("preview")

    def stage(self, action: str, planner: Any, *, masters: Any = None) -> bool:
        panel, studio = self.panel, self.studio
        names = panel.names()
        options = {"all_masters": panel.every_master(), "masters": masters}
        rows = studio.plan(planner, names, **options)
        panel.show_rows(rows)
        if names and studio.preview is not None:
            studio.preview.set_text("/" + "/".join(names))
        backend = advance_widths_backends()
        changed = [row.glyph for row in rows if row.plan is not None and row.plan.changed]
        facts = backend.history.scan_auto_facts(studio.package())
        note = backend.panel.rebuild_note(backend.panel.auto_dependants(facts, changed))
        if note and not panel.bases_allowed():
            studio.say(f'Refused. {note}. Tick "Edit bases of auto glyphs anyway" to go on.')
            return False
        self.request = (action, planner, names, options, panel.bases_allowed())
        self.accepted = (studio.package(), list(rows), self.draft(), self.targets(rows))
        studio.say("Preview ready. Review the rows, then Apply Changes." + (f" {note}" if note else ""))
        return True

    def targets(self, rows: Any) -> tuple:
        """Stable native layer identities also catch replacement by equal metrics."""
        layers = [self.studio.layer(row.glyph, row.master) for row in rows]
        return tuple(getattr(layer, "id", id(layer)) for layer in layers)

    def ready(self) -> bool:
        return (self.request is not None and self.accepted[2] == self.draft()
                and any(row.plan is not None and row.plan.changed for row in self.accepted[1]))

    def apply(self) -> bool:
        if not self.ready():
            raise ValueError("Preview the current controls before applying changes.")
        action, planner, names, options, allow = self.request
        package, rows, _, targets = self.accepted
        if (self.studio.package() is not package or self.targets(rows) != targets
                or self.studio.plan(planner, names, **options) != rows):
            self.request = None
            raise ValueError("The font or source layers changed since preview; preview again.")
        self.request = None
        return self.studio.apply(action, planner, names, **options, allow_bases=allow)

    def revert(self) -> None:
        """Explicitly discard the accepted plan; controls remain available for a new preview."""
        self.request = self.accepted = None
        self.panel.show_rows([])
        self.panel.refresh()
        self.studio.say("Preview discarded. Controls retained.")


def bind(studio: Any) -> None:
    """Wire actual UI buttons while retaining the original callable action APIs."""
    shell = studio.shell
    for view in studio.views:
        panel = view.__self__
        if not panel.WRITES:
            shell.set_actions(panel.widget, refresh=studio.reload, preview=panel.show_strings)
            for button in buttons(panel.layout):
                if value(button.text) == "Open TMetrics window":
                    button.clicked.disconnect()
                    shell.connect(button.clicked, lambda *args, panel=panel: open_window(panel))
            raw = QtGui.QPushButton("Open raw spacing preview", panel.widget)
            panel.layout.addWidget(raw)
            shell.connect(raw.clicked, lambda *args, panel=panel: panel.guard(lambda: open_raw(panel)))
            selection = QtGui.QPushButton("Preview selected layers", panel.widget)
            panel.layout.addWidget(selection)
            shell.connect(selection.clicked, lambda *args, panel=panel: selected_offset(panel))
            shell.connect(panel.offset_box.valueChanged, lambda *args, panel=panel: update_offset(panel))
            panel.table.row_selected.disconnect(panel.row_chosen)
            panel.table.row_selected.connect(lambda name, layer=None, panel=panel: show_layer(panel, name, layer))
            continue
        staged = panel.staged = Staged(panel)
        for field in vars(panel).values():
            if isinstance(field, QtGui.QLineEdit):
                shell.connect(field.textChanged, lambda *args: shell._update_actions())
            elif isinstance(field, QtGui.QComboBox):
                shell.connect(field.currentIndexChanged, lambda *args: shell._update_actions())
            elif isinstance(field, QtGui.QCheckBox):
                shell.connect(field.toggled, lambda *args: shell._update_actions())
        for button in buttons(panel.layout):
            original = value(button.text)
            if original in ACTIONS:
                title, method = ACTIONS[original]
                button.clicked.disconnect()
                button.setText(title)
                button.setAccessibleName(title)
                shell.connect(button.clicked, lambda *args, owner=staged, action=getattr(panel, method): owner.choose(action))
        revert = QtGui.QPushButton("Discard preview", panel.widget)
        panel.layout.addWidget(revert)
        shell.connect(revert.clicked, lambda *args, owner=staged: owner.revert())
        shell.set_actions(panel.widget, refresh=studio.reload, preview=staged.preview,
                          apply=staged.apply, ready=staged.ready,
                          dirty=lambda: False)


def selected_offset(panel: Any) -> None:
    """Retain the original selected-layer snapshot, including repeated alternate layers."""
    try:
        panel.studio.package()
        backend = spacing_offset_backends()
        panel.offset_snapshot = backend.capture()
        update_offset(panel)
    except (ValueError, RuntimeError, TimeoutError) as error:
        panel.offset_snapshot = None
        panel.records = []
        panel.table.set_rows([])
        panel.studio.say(str(error))


def update_offset(panel: Any) -> None:
    if getattr(panel, "offset_snapshot", None) is None:
        return
    try:
        panel.studio.package()
        rows = spacing_offset_backends().preview(panel.offset_snapshot, int(value(panel.offset_box.value)))
        panel.records = [(name, layer, tuple("" if v is None else v for v in (left, right, width))
                          + ("Selected layer offset preview",)) for name, layer, left, right, width in rows]
        panel.table.set_rows(panel.records)
        panel.studio.say("Selected-layer preview only; font data is unchanged.")
    except (ValueError, RuntimeError, TimeoutError) as error:
        panel.offset_snapshot = None
        panel.records = []
        panel.table.set_rows([])
        panel.studio.say(str(error))


def show_layer(panel: Any, name: str, layer: Any) -> None:
    """A selected-layer row always previews its exact captured layer."""
    if panel.studio.preview is not None and name:
        panel.studio.preview.set_layer(layer)
        panel.studio.preview.set_text("/" + name)


def open_window(panel: Any) -> Any:
    """The editable child shares the captured font and refuses a lost target."""
    try:
        panel.studio.package()
        return panel.open_window()
    except (ValueError, RuntimeError) as error:
        panel.studio.say(str(error))
        return None


def open_raw(panel: Any) -> Any:
    """Load the original snapshot-guarded canvas only when requested."""
    from .raw import open_preview

    return open_preview(panel)
