# this_file: src/fontlabapp/features/categories/ui.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Bind a caller-supplied category policy to the shared owned text report UI."""

from typing import Any

import fontlabapp.features.categories.model as api
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


def dialog_type(classify: api.Classifier) -> type:
    """Keep foreign category policy outside App; reuse Refresh/Close lifecycle."""

    class CategoryXmlDialog(SnapshotTextDialog):
        """A complete selectable lib fragment; no clipboard, file or font writers."""

        KEY = "category_xml"

        def __init__(self, parent: Any = None) -> None:
            super().__init__(
                parent,
                "Categories to XML Lib Key",
                self.KEY,
                "All glyphs in font order. Mark categories become mark; all others become base. Select the fragment to insert into a UFO lib dictionary. Refresh after changes.",
                lambda: api.capture(classify),
                api.render,
                lambda report: f"{len(report.rows)} glyphs. No font or file changes.",
            )

    return CategoryXmlDialog
