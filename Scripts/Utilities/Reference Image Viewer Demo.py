# this_file: Scripts/Utilities/Reference Image Viewer Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open the Reference Image Viewer app: a read-only image viewer in the shared shell.

What: Opens fontlabapp.fontui.reference_images, the original image viewer
embedded in the shared App shell with an About tab.
Use: Choose File > Open, pick an image, then zoom, fit or print. Exit, Escape or
the Close button close the whole window.
Extension: fontlabapp.fontui.reference_images.show(parent=None) returns the shell.
Safety: Read-only. It reads the image you choose; it never touches font data.
"""

TITLE = "Reference Image Viewer Demo"


def main() -> None:
    """Open the viewer, or say why it did not open."""
    import fly
    from fly.ap.fontui.reference_images import show
    from fly.ap.qt.dialogs import run_standard_message_box

    try:
        show()
    except (ImportError, ValueError, RuntimeError) as error:
        qt = fly.qt
        parent = fly.fl.MainWindow()
        kind = qt.QtGui.QMessageBox
        run_standard_message_box(qt, parent, TITLE, f"Reference Image Viewer did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
