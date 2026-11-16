# this_file: Scripts/Widgets/Find Files Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Search a folder of sample files with the fontlabapp.qt.find_files panel.

What: Writes three small text files into the demo's own temp folder and opens
the Find Font Source Files panel (fontlabapp.qt.find_files.model.show) with
that folder, the pattern * and the text "glyph" already filled in.
Use: Run it from the Scripts menu and click Find. Two of the three sample files
contain the word glyph, so two rows appear. Browse... lets you pick another
folder to search instead. Close the panel when done.
Safety: The search only reads files. It never edits, moves or deletes one. The
demo writes only alpha.txt, beta.txt and notes.txt in the fixed folder
fontlabapp-demos/find-files under the system temp directory, replacing them on
each run. The folder list starts with that folder alone. Browse... opens Qt's
own folder dialog, and Qt, not this demo, decides whether it remembers recent
folders. Double-clicking a result asks the desktop to open that file in its
default application. No font, selection, history, preference, Output or
clipboard is touched. The panel registers itself under one key, so running the
demo again closes the old panel. The exact-bytes variant,
fontlabapp.qt.find_files.model.show_bytes, is not used here.
"""

import tempfile
from pathlib import Path

SAMPLE_FOLDER = Path(tempfile.gettempdir()) / "fontlabapp-demos" / "find-files"
SAMPLE_FILES = {
    "alpha.txt": "glyph alpha\nanchor top\n",
    "beta.txt": "sub beta by beta.alt;\nglyph beta\n",
    "notes.txt": "nothing to see here\n",
}


def write_samples(folder: Path) -> Path:
    """Create ``folder`` with the sample files and return it."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in SAMPLE_FILES.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def main() -> None:
    """Write the samples, open the panel and point it at them."""
    from fly.ap.qt.find_files.model import show

    folder = str(write_samples(SAMPLE_FOLDER))
    panel = show()
    panel.directory.clear()
    panel.directory.addItem(folder)
    panel.directory.setEditText(folder)
    panel.pattern.setEditText("*")
    panel.containing.setEditText("glyph")


if __name__ == "__main__":
    main()
