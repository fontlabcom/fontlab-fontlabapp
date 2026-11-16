# this_file: src/fontlabapp/qt/dialogs.py
"""Injected Qt dialog construction, execution and retained-box ownership.

What it does:
    Builds, runs and deletes Qt dialogs that the caller owns. Modal and file
    choosers: ``run_owned_dialog``, ``run_message_box``, ``run_file_dialog``,
    ``run_text_dialog``, ``run_button_message_box``. ``run_standard_message_box``
    preserves static warning/question title/text/buttons with owned priority. Modeless boxes:
    ``create_message_box``, then ``show_message_box``, later
    ``release_closed_message_boxes`` or ``close_message_boxes``.
    ``name_filters`` builds the Qt file-filter list.

How to use:
    Pass ``PythonQt.QtGui`` as ``gui`` and parent widgets as ``parent_args``
    (positional: PythonQt constructors reject keywords). Callers keep the
    callback, answer, icon-style and foreign-window policy.

Why this design:
    Modal and file execution delete the owned dialog in ``finally``, so a
    failure in setup, ``exec()`` or the result read leaks no native dialog.
    The module imports no host and connects no signal, so it loads in a cold
    FontLab start and in tests without Qt.
"""

from collections.abc import Callable, Sequence
from typing import Any

__all__ = [
    "close_message_boxes",
    "create_message_box",
    "name_filters",
    "release_closed_message_boxes",
    "run_button_message_box",
    "run_file_dialog",
    "run_message_box",
    "run_owned_dialog",
    "run_standard_message_box",
    "run_text_dialog",
    "show_message_box",
]


def create_message_box(
    gui: Any,
    text: Any,
    informative: Any,
    icon: str,
    parent_args: tuple[Any, ...] = (),
    *,
    detail: Any = "",
) -> Any:
    """Prepare a caller-owned QMessageBox; do not show it.

    ``icon`` is a ``QMessageBox`` attribute name such as ``"Warning"``. A
    truthy ``detail`` becomes the box's Show Details text as ``str(detail)``;
    a falsy one ("", None) sets none.
    If setup fails, the box is deleted and the error propagates. Hand the box
    to ``run_message_box`` (modal) or ``show_message_box`` (modeless).
    """
    box = gui.QMessageBox(*parent_args)
    try:
        box.setText(str(text))
        box.setInformativeText(str(informative))
        box.setIcon(getattr(gui.QMessageBox, icon))
        if detail:
            box.setDetailedText(str(detail))
        return box
    except BaseException:
        box.deleteLater()
        raise


def run_owned_dialog(
    dialog: Any,
    configure: Callable[[Any], object],
    read_result: Callable[[Any, Any], Any],
) -> Any:
    """Configure and execute one owned dialog, read its result, then delete it.

    ``configure(dialog)`` runs first; ``read_result(dialog, exec_result)``
    gives the return value. The caller supplies defaults, text conversion and
    acceptance/cancel policy. ``deleteLater`` runs on every exit, also when
    configuration, execution or result conversion fails.
    """
    try:
        configure(dialog)
        return read_result(dialog, dialog.exec())
    finally:
        dialog.deleteLater()


def run_message_box(box: Any, buttons: Any) -> int:
    """Show ``box`` modally with standard ``buttons``; return ``exec()``'s result.

    The box is deleted on every exit. Only this box runs; no other dialog.
    """
    return run_owned_dialog(
        box,
        lambda current: current.setStandardButtons(buttons),
        lambda current, result: result,
    )


def run_standard_message_box(
    qt: Any,
    parent: Any,
    title: Any,
    text: Any,
    icon: str,
    buttons: Any,
    default_button: Any = None,
) -> Any:
    """Run an owned priority message with Qt's static standard-button result.

    ``icon`` names QMessageBox.Warning/Question/etc.; title and primary text
    stay distinct. None keeps Qt's automatic default. Every setup/exec/result
    failure deletes the box through run_owned_dialog; interrupted exec is Cancel.
    """
    kind = qt.QtGui.QMessageBox

    def configure(box: Any) -> None:
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(getattr(kind, icon))
        box.setStandardButtons(buttons)
        if default_button is None or default_button == kind.NoButton:
            # Static warning/question chooses the first standard AcceptRole.
            for button in sorted(box.buttons(), key=box.standardButton):
                if box.buttonRole(button) == kind.AcceptRole:
                    box.setDefaultButton(button)
                    break
        else:
            box.setDefaultButton(default_button)
        box.setWindowFlags(box.windowFlags() | qt.QtCore.Qt.WindowStaysOnTopHint)

    return run_owned_dialog(
        kind(parent),
        configure,
        lambda box, result: kind.Cancel
        if result == -1
        else box.standardButton(box.clickedButton()),
    )


def run_file_dialog(
    gui: Any,
    configure: Callable[[Any, Any], object],
    caption: Any,
    directory: Any,
    parent_args: tuple[Any, ...] = (),
) -> list[str] | None:
    """Run one owned ``QFileDialog``; return the selected paths or None.

    ``configure(QFileDialog, dialog)`` sets mode and filters (see
    ``name_filters``). A falsy ``directory`` keeps the Qt default. Cancel
    gives None. The dialog is deleted on every exit.
    """

    def setup(dialog: Any) -> None:
        dialog.setWindowTitle(str(caption or ""))
        if directory:
            dialog.setDirectory(str(directory))
        configure(gui.QFileDialog, dialog)

    return run_owned_dialog(
        gui.QFileDialog(*parent_args),
        setup,
        lambda dialog, accepted: list(dialog.selectedFiles()) if accepted else None,
    )


def name_filters(filetypes: Sequence[str] | None) -> list[str]:
    """Build the Qt name-filter list for a file chooser.

    ``["ufo", ".glyphs"]`` gives ``["Files (*.ufo *.glyphs)"]``. A leading dot
    is optional. ``None`` or an empty sequence gives ``[]``: no filter, so the
    chooser shows all files. Pure function; no Qt needed.
    """
    if not filetypes:
        return []
    patterns = " ".join(f"*.{kind.lstrip('.')}" for kind in filetypes)
    return [f"Files ({patterns})"]


def run_text_dialog(
    gui: Any,
    message: Any,
    value: Any,
    title: Any,
    ok_button: Any = None,
    parent_args: tuple[Any, ...] = (),
) -> str | None:
    """Run one owned ``QInputDialog`` text prompt; return the text or None.

    ``gui`` is ``PythonQt.QtGui`` (injected). ``message`` is the label,
    ``value`` the initial text, ``title`` the window title. Falsy values
    become empty text. A falsy ``ok_button`` keeps the Qt default label.
    ``parent_args`` are positional: PythonQt constructors reject keywords.
    Cancel gives None and the text is not read. The dialog is deleted on
    every exit, also when setup, execution or the text read fails.
    """

    def setup(dialog: Any) -> None:
        dialog.setWindowTitle(str(title or ""))
        dialog.setLabelText(str(message or ""))
        dialog.setTextValue(str(value or ""))
        if ok_button:
            dialog.setOkButtonText(str(ok_button))

    return run_owned_dialog(
        gui.QInputDialog(*parent_args),
        setup,
        lambda dialog, accepted: dialog.textValue() if accepted else None,
    )


def show_message_box(
    box: Any, boxes: list[Any], configure: Callable[[Any], object] | None = None
) -> None:
    """Show ``box`` modeless and keep it in the caller's ``boxes`` list.

    The box goes into ``boxes`` first, so a failure in ``configure(box)`` or
    in ``show()`` still leaves it retained for ``close_message_boxes``. A
    modeless box that Python does not retain could be deleted while visible.
    """
    boxes.append(box)
    if configure is not None:
        configure(box)
    box.setModal(False)
    box.show()


def close_message_boxes(boxes: list[Any]) -> None:
    """Close and delete every retained box, newest first; empty ``boxes``.

    Every box is tried. The first failure is re-raised at the end; a
    ``BaseException`` such as ``KeyboardInterrupt`` wins over an ``Exception``.
    """
    failures: list[BaseException] = []
    while boxes:
        box = boxes.pop()
        try:
            box.close()
            box.deleteLater()
        except BaseException as error:  # noqa: BLE001 - re-raised below
            failures.append(error)
    if failures:
        exits = [e for e in failures if not isinstance(e, Exception)]
        raise (exits or failures)[0]


def release_closed_message_boxes(boxes: list[Any]) -> None:
    """Delete the boxes that the user closed (hidden); keep the visible ones.

    Call it before showing a new box, so ``boxes`` does not grow without end.
    """
    for box in [current for current in boxes if not current.isVisible()]:
        boxes.remove(box)
        box.deleteLater()


def run_button_message_box(
    box: Any, buttons: list[Any], accessory: Any = None
) -> int | None:
    """Borrow widgets for one modal box and return the clicked input index.

    ``buttons`` are caller-owned ``QPushButton`` widgets; the return value is
    the index of the clicked one, or None. ``accessory`` is an optional extra
    widget placed under the text.

    All widgets return to their original parents before box deletion, including
    partial configuration or execution failure. Parent lookup accepts PythonQt
    properties and ordinary Qt methods. Restore failure propagates before any
    box deletion, preserving the caller's existing fail-closed ordering. Caller
    owns button/default/cancel policy and recovery after native restore failure.
    """
    parents = []
    try:
        for widget in buttons + ([] if accessory is None else [accessory]):
            parent = widget.parentWidget
            parents.append((widget, parent() if callable(parent) else parent))
        for button in buttons:
            box.addButton(button, box.AcceptRole)
        if accessory is not None:
            layout = box.layout()
            layout.addWidget(accessory, layout.rowCount(), 0, 1, layout.columnCount())
        box.exec()
        clicked = box.clickedButton()
        return buttons.index(clicked) if clicked in buttons else None
    finally:
        for widget, parent in parents:
            widget.setParent(parent)
        box.deleteLater()
