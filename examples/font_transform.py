# this_file: examples/font_transform.py
"""Inside FontLab, preview affine transforms and batch-export detached UFOs.

Work on a detached UFO, for example Fontport's export_ufo_subset() copy of a
FontLab document. The source is never edited.

Batch work runs in a separate Python 3.11+ with fontlab-fontport, never in
FontLab's own Python. Create it once in Terminal (FontLab never loads it, so
its architecture need not match FontLab's):

    uv venv --python cpython-3.11-macos-aarch64-none ~/.fontlab-batch
    uv pip install --python ~/.fontlab-batch/bin/python \\
        "fontlab-fontport @ git+https://github.com/fontlabcom/fontlab-fontport@c9fee0009e869120870e1b62758f19afe954d58c"
    ~/.fontlab-batch/bin/python -I -c "import fontlab_fontport.batch"  # check

A Fontport wheel works too (uv pip install ... fontlab_fontport-*.whl). Then,
in FontLab, pass that interpreter (or set $FONTLABAPP_BATCH_PYTHON to it; the
variable keeps its App-era name for compatibility):

    import os
    editor, batch = transform_tools(ufo_font, python=os.path.expanduser("~/.fontlab-batch/bin/python"))
    batch.set_sources(["/path/In.ufo"]); batch.destination_control.setText("/out")
    batch.start()  # outputs /out/In-transformed.ufo

The child gets only PATH, HOME, TMPDIR, USER, LOGNAME and locale variables.
close() returns at once; the child is collected afterwards (terminated after
GRACE_SECONDS if it ignores the cancel, then killed).

TransformEditor exposes .matrix fields, .intensity_slider/.intensity_field (exact),
.enabled_control, .compare_control (overlay only), .buttons (reset transform,
reset view, zoom, script, save/load settings), .recipe(), .save_settings(path)
(never overwrites, full precision) and .load_settings(path). Only affine transforms exist;
interpolation and stem-preserving methods are listed as unavailable.
"""

from typing import Any

from fly.ap.fontui import batch_panel, transform_editor


def transform_tools(font: Any, python: str | None = None) -> tuple[Any, Any]:
    """Return a retained transform preview and a batch panel using its recipe."""
    editor = transform_editor(font)
    batch = batch_panel(editor.recipe, python=python)
    for handle in (editor, batch):
        handle.widget.resize(900, 800)
        handle.widget.show()
    return editor, batch
