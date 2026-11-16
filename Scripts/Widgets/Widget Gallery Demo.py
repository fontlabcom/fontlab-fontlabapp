# this_file: Scripts/Widgets/Widget Gallery Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Try the fontlabapp.qt widget helpers on live controls in one tabbed window.

What: Opens one nonmodal window with a tab for each helper family: linked
sliders (fontlabapp.qt.slider.profiles, fontlabapp.qt.numeric), a spin box
table (fontlabapp.qt.spinbox.delegate), editable choices and literal text
(fontlabapp.qt.choices, fontlabapp.qt.literal_text), colors restyled from a
preset list (fontlabapp.qt.colors), message boxes (fontlabapp.qt.dialogs),
classic and official calendars (fontlabapp.qt.calendars.classic and
fontlabapp.qt.calendars.official), a completion editor
(fontlabapp.qt.completion.editor), a pattern tester (fontlabapp.qt.regexp.model),
read-only and editable trees (fontlabapp.qt.trees.readonly and
fontlabapp.qt.trees.editable), a painted overlay (fontlabapp.qt.painting.drawing)
and key and resize events with a stack layout (fontlabapp.qt.events.key,
fontlabapp.qt.events.resize and fontlabapp.qt.layouts.stack).
Use: Run it from the Scripts menu, open each tab and try its controls. Close the
window when done.
Safety: Every widget, model, delegate, timer and message box is created by the
demo and released when the window closes, after all of its signals are
disconnected. If Qt refuses a disconnect or a close, the window and its demo are
kept and the status line says so. The window's controls are parented to it. The literal-text helper
creates two temporary objects with no parent and deletes them at once. The trees
and the table edit local copies of literal sample data. No file is read or
written and no Qt dialog that remembers settings is opened. No font, selection,
history, preference, Output or clipboard is read or written.
"""

_HANDLES: list = []  # each open demo stays referenced until its window closes
WORDS = ("anchor", "anchorage", "angle", "glyph", "glyphs", "kern", "kerning", "outline")
PRESETS = (
    ("Amber", (0.95, 0.75, 0.3, 1.0)),
    ("Teal", (0.2, 0.65, 0.65, 1.0)),
    ("Plum", (0.55, 0.3, 0.6, 1.0)),
)
SAMPLE_TREE = (
    (-1, ("Latin", "")),
    (0, ("A", "U+0041")),
    (0, ("B", "U+0042")),
    (-1, ("Greek", "")),
    (3, ("alpha", "U+03B1")),
)


class Demo:
    """One open window: its widgets, signal scope, message boxes and closers."""

    def __init__(self, qt, scope_type) -> None:
        self.qt, self.gui, self.core = qt, qt.QtGui, qt.QtCore
        self.problems: list = []
        self.scope = scope_type(self.fail)
        self.closers: list = []  # run newest first, after the scope disconnects
        self.boxes: list = []  # modeless message boxes owned by the Dialogs tab
        self.owned = None
        self.status = None

    def fail(self, error) -> None:
        """Keep a callback error and show it; Qt never sees it."""
        self.problems.append(error)
        if self.status is not None:
            self.status.setText(f"Callback error: {error}")

    def build(self, content) -> None:
        """Create the tabs inside ``content`` (the demo's own dialog)."""
        gui = self.gui

        class Page(gui.QWidget):
            """A tab page; a Python subclass can carry the attributes helpers expect."""

        content.resize(780, 600)
        layout = gui.QVBoxLayout(content)
        tabs = gui.QTabWidget(content)
        self.status = gui.QLabel("Each tab uses one family of fontlabapp.qt helpers.", content)
        layout.addWidget(tabs)
        layout.addWidget(self.status)
        for title, builder in TABS:
            page = Page(tabs)
            builder(self, page, gui.QVBoxLayout(page))
            tabs.addTab(page, title)
        self.scope.connect(content.finished, self.on_finished, closing=True)

    def on_finished(self, *args) -> None:
        """Release after Qt's dispatch returns, never from inside it."""
        self.core.QTimer.singleShot(0, lambda: self.release())

    def release(self) -> None:
        """Disconnect every signal, run the closers, close the window, drop this demo.

        If Qt refuses a step the window and this demo stay alive and the failure shows.
        """
        kept = not self.scope.finish()
        if not kept:
            for closer in reversed(self.closers):
                try:
                    kept = closer() is False or kept
                except Exception as error:  # run every closer, whatever one raises
                    kept = True
                    self.problems.append(error)
            self.closers.clear()
        if not kept and self.owned is not None:
            try:
                kept = not self.owned.close()
            except RuntimeError as error:
                kept = True
                self.problems.append(error)
        if kept:
            self.fail(RuntimeError("Qt refused part of the release; the window is kept open."))
        elif self in _HANDLES:
            _HANDLES.remove(self)


def tab_sliders(demo, page, layout) -> None:
    """A slider, scroll bar and dial linked by profiles.group; numeric drives a bar."""
    import fly.ap.qt.numeric as numeric
    from fly.ap.qt.slider.profiles import group

    gui, core = demo.gui, demo.core
    page.scope = demo.scope  # profiles.group connects through its owner's scope
    controls = group(page, core, gui, core.Qt.Horizontal)
    bar, label = gui.QProgressBar(page), gui.QLabel("", page)
    numeric.set_step_range(bar.setRange, numeric.STEPS)

    def changed(number) -> None:
        position = numeric.position(number, 0, 20, numeric.STEPS)
        numeric.set_position(bar.setValue, position)
        label.setText(f"Value {number} of 0..20 is step {position:.0f} of {numeric.STEPS}")

    for control in controls:
        control.setRange(0, 20)
        layout.addWidget(control)
    layout.addWidget(bar)
    layout.addWidget(label)
    demo.scope.connect(controls[0].valueChanged, changed)
    controls[0].setValue(5)
    changed(5)


def tab_spinbox(demo, page, layout) -> None:
    """A 4 by 2 table whose cells edit through the owned spin box delegate."""
    from fly.ap.qt.spinbox.delegate import delegate_type

    gui, core = demo.gui, demo.core
    model, view = gui.QStandardItemModel(4, 2, page), gui.QTableView(page)
    label = gui.QLabel("Double-click a cell and enter a number from 0 to 100.", page)
    for row in range(4):
        for column in range(2):
            item = gui.QStandardItem()
            item.setData(10 * (row + 1) + column, core.Qt.EditRole)
            model.setItem(row, column, item)
    commits = [0]

    def changed() -> None:
        commits[0] += 1
        label.setText(f"Cell edits committed: {commits[0]}")

    delegate = delegate_type(core, gui)(model, view, False, demo.fail, changed)
    view.setModel(model)
    view.setItemDelegate(delegate)
    layout.addWidget(view)
    layout.addWidget(label)

    def close_editors() -> bool:
        delegate.cancel()
        return delegate.finish()

    demo.closers.append(close_editors)


def tab_choices(demo, page, layout) -> None:
    """An editable combo box with commit tracking, and a line edit that keeps NUL."""
    import fly.ap.qt.choices as choices
    from fly.ap.qt.literal_text import line_edit_type, read_text
    from fly.ap.qt.properties import value

    gui = demo.gui
    combo = gui.QComboBox(page)
    report = gui.QLabel("Pick a choice, or type one and press Return.", page)
    set_text = gui.QPushButton("Set the text to Condensed", page)
    line, shown = line_edit_type(demo.qt)(page), gui.QLabel("", page)
    set_nul = gui.QPushButton("Put a NUL in the line", page)
    combo.addItems(["Regular", "Italic", "Bold"])
    choices.configure_combo(combo, gui.QComboBox.NoInsert)

    def activated(*args) -> None:
        if choices.accept_activation(combo, args):
            report.setText(f"Activated: {value(combo, 'currentText')}")

    def edited() -> None:
        if choices.consume_commit(combo.lineEdit()):
            report.setText(f"Committed: {value(combo, 'currentText')}")

    def put_nul() -> None:
        line.setText("a\0b")
        shown.setText(f"Line text is {read_text(demo.qt, value(line, 'text'))!r}")

    demo.scope.connect(combo.activated, activated)
    demo.scope.connect(combo.lineEdit().editingFinished, edited)
    demo.scope.connect(set_text.clicked, lambda *args: choices.set_combo_text(combo, "Condensed"))
    demo.scope.connect(set_nul.clicked, lambda *args: put_nul())
    for widget in (combo, report, set_text, line, set_nul, shown):
        layout.addWidget(widget)


def tab_colors(demo, page, layout) -> None:
    """A group box, swatch and label restyled by colors for each preset in a combo box."""
    import fly.ap.qt.colors as colors
    from fly.ap.qt.properties import value

    gui = demo.gui
    picker, swatch = gui.QComboBox(page), gui.QPushButton("Swatch", page)
    box = gui.QGroupBox("Styled by colors.group_box_style", page)
    label = gui.QLabel("Text color follows the preset", box)
    picker.addItems([name for name, _ in PRESETS])

    def apply(*args) -> None:
        channels = PRESETS[int(value(picker, "currentIndex"))][1]
        box.setStyleSheet(colors.group_box_style(lambda: colors.rgba_css(channels), lambda: "black", 2, 6))
        swatch.setStyleSheet(colors.swatch_style(colors.rgba255(channels)))
        text_color = colors.color_palette(
            gui, lambda: label, lambda: gui.QColor(*colors.rgba255(channels)), lambda palette: palette.WindowText
        )
        label.setPalette(text_color)

    demo.scope.connect(picker.currentIndexChanged, apply)
    gui.QVBoxLayout(box).addWidget(label)
    for widget in (picker, box, swatch):
        layout.addWidget(widget)
    apply()


def tab_dialogs(demo, page, layout) -> None:
    """A modeless message box the demo owns, and a file-chooser filter."""
    import fly.ap.qt.dialogs as dialogs

    gui = demo.gui
    button = gui.QPushButton("Show a message box", page)
    filters = dialogs.name_filters(["png", "jpg"])

    def show() -> None:
        dialogs.release_closed_message_boxes(demo.boxes)
        box = dialogs.create_message_box(gui, "Owned message box", "It closes with the Widget Gallery.", "Information", (page,))
        dialogs.show_message_box(box, demo.boxes, lambda current: current.setWindowTitle("Dialogs"))

    demo.scope.connect(button.clicked, lambda *args: show())
    demo.closers.append(lambda: dialogs.close_message_boxes(demo.boxes))
    layout.addWidget(button)
    layout.addWidget(gui.QLabel(f"dialogs.name_filters(['png', 'jpg']) = {filters}", page))


def calendar_tab(demo, page, layout, controls_type) -> None:
    """Host one calendar controls object; it shares the demo's signal scope."""
    controls = controls_type(demo.qt, page, demo.scope.connect)
    layout.addWidget(controls.widget)
    demo.closers.append(controls.close)


def tab_calendar_classic(demo, page, layout) -> None:
    from fly.ap.qt.calendars.classic.controls import Controls

    calendar_tab(demo, page, layout, Controls)


def tab_calendar_official(demo, page, layout) -> None:
    from fly.ap.qt.calendars.official.controls import Controls

    calendar_tab(demo, page, layout, Controls)


def tab_completion(demo, page, layout) -> None:
    """A text editor that completes words after three typed letters."""
    from fly.ap.qt.completion.editor import CompletionEditor

    def wire(completer, call):
        # PythonQt needs the QString overload named explicitly.
        if completer.connect("activated(QString)", call) is False:
            raise RuntimeError("Qt refused the completion connection.")
        return call

    def unwire(completer, slot) -> None:
        if completer.disconnect("activated(QString)", slot) is False:
            raise RuntimeError("Qt refused the completion disconnection.")

    editor = CompletionEditor(demo.qt, page, wire, unwire, demo.fail)
    editor.replace_words(WORDS)
    layout.addWidget(demo.gui.QLabel("Type three letters such as anc or gly, or press Ctrl+E.", page))
    layout.addWidget(editor.widget)
    demo.closers.append(editor.close)


def tab_regexp(demo, page, layout) -> None:
    """Evaluate a Qt regular expression against sample text as you type."""
    from fly.ap.qt.properties import value
    from fly.ap.qt.regexp.model import Rule, evaluate

    gui = demo.gui
    pattern, text, result = gui.QLineEdit(page), gui.QLineEdit(page), gui.QLabel("", page)
    pattern.setText(r"(s\w+)")
    text.setText("small stones")

    def changed(*args) -> None:
        found = evaluate(demo.core, Rule(value(pattern, "text")), value(text, "text"), ())
        result.setText(
            f"Match at {found['position']}, length {found['length']}, captures {found['captures']}"
            if found["valid"]
            else f"Invalid pattern: {found['error']}"
        )

    demo.scope.connect(pattern.textChanged, changed)
    demo.scope.connect(text.textChanged, changed)
    for widget in (gui.QLabel("Pattern", page), pattern, gui.QLabel("Text", page), text, result):
        layout.addWidget(widget)
    changed()


def tab_trees(demo, page, layout) -> None:
    """The same sample tree in a read-only model and in an editable draft model."""
    from fly.ap.qt.trees.data import Tree
    from fly.ap.qt.trees.editable.model import model_type as editable_type
    from fly.ap.qt.trees.readonly import model_type as readonly_type

    gui, core = demo.gui, demo.core
    tree = Tree(("Glyph", "Unicode"), SAMPLE_TREE)
    label = gui.QLabel("Read-only above; the lower tree is an editable local draft.", page)
    views = []
    for model_class in (readonly_type(core), editable_type(core, gui)):
        view = gui.QTreeView(page)
        model = model_class(tree, view)
        view.setModel(model)
        view.expandAll()
        layout.addWidget(view)
        views.append((view, model))

    def detach() -> None:
        for view, model in views:
            view.setModel(None)
            model.deactivate()

    edited = views[1][1]
    demo.scope.connect(edited.dataChanged, lambda *args: label.setText(f"Draft edited: {edited.edited}"))
    demo.closers.append(detach)
    layout.addWidget(label)


def tab_painting(demo, page, layout) -> None:
    """A frame with a transparent overlay widget that paints through Drawing."""
    from fly.ap.qt.painting.drawing import Drawing

    gui = demo.gui
    frame = gui.QFrame(page)
    frame.setMinimumHeight(120)

    def paint(painter) -> None:
        painter.setBrush(gui.QColor("#407eaa"))
        painter.drawEllipse(10, 10, 80, 80)
        painter.setBrush(gui.QColor("#ad6851"))
        painter.drawRect(100, 40, 80, 50)

    layout.addWidget(gui.QLabel("The shapes below are painted by painting.drawing.Drawing.", page))
    layout.addWidget(frame)
    demo.closers.append(Drawing(frame, paint).close)


def tab_events(demo, page, layout) -> None:
    """Key routing, resize forwarding, content fitting and an equal stack layout."""
    from types import SimpleNamespace

    from fly.ap.qt.events.key import key_press_handler
    from fly.ap.qt.events.resize import resize_event_handler
    from fly.ap.qt.layouts.content import fit_contents
    from fly.ap.qt.layouts.stack import distribute

    gui, core = demo.gui, demo.core
    keys, sizes = gui.QLabel("Type in the field; Escape clears it.", page), gui.QLabel("", page)
    owners = {}  # emptied on release, so a late resize event does nothing

    def on_key(widget, event) -> bool:
        handled = event.key() == core.Qt.Key_Escape
        if handled:
            widget.clear()
        keys.setText(f"Key code {event.key()}: " + ("Escape cleared the field" if handled else "passed to the field"))
        return handled

    class KeyField(gui.QLineEdit):
        keyPressEvent = key_press_handler(gui.QLineEdit, on_key)

    class ResizePanel(gui.QFrame):
        resizeEvent = resize_event_handler(gui.QFrame, lambda widget: owners.get("panel"), "on_resize")

    panel = ResizePanel(page)
    panel.setMinimumHeight(60)
    strip = gui.QWidget(panel)
    chips = [gui.QLabel(name, strip) for name in ("one", "two", "three")]

    def on_resize(width, height) -> None:
        fitted_width, fitted_height = fit_contents(panel, strip)
        lengths = [1.0] * len(chips)
        starts = distribute(lengths, float(fitted_width), 4.0, "equal")
        for chip, start, length in zip(chips, starts, lengths, strict=True):
            chip.setGeometry(round(start), 0, round(length), 24)
        sizes.setText(f"Panel {width} x {height}; content fitted to {fitted_width} x {fitted_height}")

    owners["panel"] = SimpleNamespace(on_resize=on_resize)
    demo.closers.append(owners.clear)
    for widget in (keys, KeyField(page), sizes, panel):
        layout.addWidget(widget)


TABS = (
    ("Sliders", tab_sliders),
    ("Spin box", tab_spinbox),
    ("Choices", tab_choices),
    ("Colors", tab_colors),
    ("Dialogs", tab_dialogs),
    ("Calendar (classic)", tab_calendar_classic),
    ("Calendar (official)", tab_calendar_official),
    ("Completion", tab_completion),
    ("Regexp", tab_regexp),
    ("Trees", tab_trees),
    ("Painting", tab_painting),
    ("Events", tab_events),
)


def main() -> None:
    """Open the gallery window, retaining it until it closes."""
    import fly
    from fly.ap.core.signals.scope import Scope
    from fly.ap.qt.safe import main_window
    from fly.ap.qt.widgets import create_dialog

    qt = fly.qt
    demo = Demo(qt, Scope)
    _HANDLES.append(demo)
    try:
        demo.owned = create_dialog(main_window(fly.fl, qt), "Widget Gallery Demo", demo.build)
    except BaseException:
        demo.release()
        raise


if __name__ == "__main__":
    main()
