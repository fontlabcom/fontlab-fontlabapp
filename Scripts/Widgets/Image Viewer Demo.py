# this_file: Scripts/Widgets/Image Viewer Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Zoom and fit a generated sample picture in the fontlabapp.qt.images.viewer panel.

What: Draws a small picture (an ellipse and a rectangle on a cream ground) with
fontlabapp.qt.images.viewer.io.generated_image, saves it as a PNG in the demo's
own temp folder and opens it in the free-zoom reference image viewer.
Use: Run it from the Scripts menu. Use the View menu to zoom in and out, return
to normal size or fit the picture to the window. File > Open lets you view
another image instead. Close the viewer when done.
Safety: Reads no font and edits no font. The one file the demo writes is
sample.png in the fixed folder fontlabapp-demos/image-viewer under the system
temp directory, replaced on each run. File > Open starts in a separate temporary
folder the viewer creates then and removes when it closes. It is Qt's own file
dialog, and Qt, not this demo, decides whether it remembers recent folders.
Print only acts if you choose File > Print: Qt's print dialog can then send the
picture to a printer or write a PDF to any path you pick there. The viewer
registers itself under one key, so running the demo again closes the old viewer
first. The bounded variant, fontlabapp.qt.images.viewer.model.show_bounded, is
not used here. No selection, history, preference, Output or clipboard is touched.
"""

import tempfile
from pathlib import Path

SAMPLE_FOLDER = Path(tempfile.gettempdir()) / "fontlabapp-demos" / "image-viewer"


def save_sample(gui, folder: Path) -> Path:
    """Write the generated picture into ``folder`` and return its path."""
    from fly.ap.qt.images.viewer.io import generated_image

    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "sample.png"
    if not generated_image(gui).save(str(path)):
        raise OSError(f"Qt could not write {path}")
    return path


def main() -> None:
    """Save the sample picture and open it in the image viewer."""
    import fly
    from fly.ap.qt.images.viewer.model import show

    path = save_sample(fly.qt.QtGui, SAMPLE_FOLDER)
    show().load(str(path))


if __name__ == "__main__":
    main()
