# this_file: Scripts/Proof/Text Holder Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open Text Holder, the floating scratch pad for proofing text, on sample text.

What: Calls fontlabapp.proof.text_holder.model.show with a file in one fixed
demo folder, fontlabapp-demos/text-holder under the system temp directory.
The demo rewrites that file with a short sample at every run. The pad is an
owned always-on-top window with Find, Find & Replace, Save, Save & Close and
Ignore & Close.
Use: Run it, edit the text, search and replace in it, then close the window.
Save and Save & Close write the sample file in the demo folder. Closing the
window in any way also stores the window size beside that file. Running the
demo again restores the sample text.
Safety: The real Text holder file and its saved size are never read or
written, because the demo hands the pad its own path. It writes only the
sample file and the window-size file in its temp folder, which it reuses and
never deletes. No font, selection, history, preference, Output or clipboard is
touched. If a Text Holder window is already open, the demo says so and stops,
since replacing it would close it.
"""

import sys
import tempfile
from pathlib import Path

TITLE = "Text Holder Demo"
FOLDER = Path("fontlabapp-demos") / "text-holder"
SAMPLE = (
    "Hamburgefonstiv 0123456789\n"
    "Sphinx of black quartz, judge my vow.\n"
    "Pack my box with five dozen liquor jugs.\n"
)


def sample_path() -> Path:
    """The demo's own text file in its fixed folder, rewritten with the sample."""
    folder = Path(tempfile.gettempdir()) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "Text holder.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def notify(text: str) -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    run_standard_message_box(qt, parent, TITLE, text, "Information", qt.QtGui.QMessageBox.Ok)


def is_open(key: str) -> bool:
    """True when the registry holds a live window; a destroyed one is dropped."""
    windows = getattr(sys, "_fontlab_samples", {})
    old = windows.get(key)
    if old is None:
        return False
    try:
        old.isVisible()
    except ValueError as error:
        # PythonQt: the wrapper outlived its QWidget, as in show_script_dialog;
        # any other ValueError leaves the window registered.
        if "destroyed" not in str(error):
            return True
        del windows[key]
        return False
    return True


def main() -> None:
    """Open the pad on the sample file, or say why it cannot be opened."""
    from fly.ap.proof.text_holder.model import KEY, show

    if is_open(KEY):
        notify("A Text Holder window is already open. Close it, then run this demo again.")
        return
    try:
        show(path=sample_path())
    except (OSError, ValueError, RuntimeError) as error:
        notify(f"Text Holder could not open: {error}")


if __name__ == "__main__":
    main()
