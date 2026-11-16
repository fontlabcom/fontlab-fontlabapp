# this_file: Scripts/Font Editors/Batch Panel Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Explain App's batch panel and its worker process, without starting either.

What: Reads the settings of fontlabapp.fontui.batch (the panel BatchPanel,
made by fontlabapp.fontui.batch_panel) and fontlabapp.fontui.batch_worker (the
child process and its supervisor) and shows them in one message box: how the
child Python is chosen, how often and how much the panel reads from it, how
Cancel and Close stop it, how its outputs are named and which environment
variables it gets. Importing the panel needs Fontport, so this demo needs the
fontport extra.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is started. The batch panel is not opened: its Start button
launches a separate Python process and writes UFO folders, and its Add sources
button opens a directory dialog. The demo only imports the two modules and
reads their constants. It also reports whether the environment variable that
names the child Python is set, without showing its value. No font, master,
selection, history, preference, Output or clipboard is read or written and no
file is touched. Without the fontport extra the demo only says so.
"""

TITLE = "Batch Panel Demo"
MISSING = "This demo needs the fontport extra: pip install 'fontlab-fontlabapp[fontport]'."


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def lines() -> list[str]:
    """What the panel and its worker do, from their own constants."""
    import os

    from fly.ap.fontui import batch, batch_worker

    panel = batch.BatchPanel
    state = "set" if os.environ.get(batch.PYTHON_ENV) else "not set"
    return [
        "fontlabapp.fontui.batch.BatchPanel runs Fontport's BatchRunner over source UFOs, one run at a time.",
        f"Child Python: the python= argument, else ${batch.PYTHON_ENV} (here: {state}). It needs Python 3.11+ with fontlab-fontport.",
        "Start checks every job inside FontLab first and writes nothing if one is refused; then it starts the child.",
        f"Every {panel.POLL_MS} ms the panel reads at most {batch_worker.READ_BYTES} bytes and {batch_worker.ROWS_PER_POLL} result rows from the child.",
        "Cancel stops before the next font. Close cancels and returns at once.",
        f"fontlabapp.fontui.batch_worker.supervise then terminates the child after {panel.GRACE_SECONDS:g} s and kills it {batch_worker.KILL_SECONDS:g} s later.",
        "Outputs are named <stem>-transformed.ufo in the destination folder and never replace a file.",
        "The child gets only these environment variables: " + ", ".join(batch_worker.ENV_KEYS) + ".",
        "",
        "This demo does not open the panel: Start would launch a Python process and write UFO folders.",
    ]


def main() -> None:
    """Show the explanation, or say that the fontport extra is missing."""
    try:
        details = "\n".join(lines())
    except ImportError as error:
        # Only a missing extra package is the extra's fault; name any other failure as it is.
        culprit = error.name or getattr(error.__cause__, "name", None) or ""
        absent = culprit.partition(".")[0] in ("fontlab_fontport", "ufoLib2")
        notify(TITLE, MISSING if absent else "An App module could not be imported.", str(error))
        return
    notify(TITLE, "Batch panel reference. Nothing was started, read or written.", details)


if __name__ == "__main__":
    main()
