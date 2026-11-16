# this_file: src/fontlabapp/contours/open_contours/native.py
# SPDX-License-Identifier: Apache-2.0
"""Open Contours native boundary: read the current font, select the scanned glyphs."""

from fontlabapp import _native
from fontlabapp.core import scripting

from .model import OpenContoursReport, scan


def capture() -> OpenContoursReport:
    """Scan the current font; refuse when no font is open."""
    package = scripting.current_package()
    if package is None:
        raise ValueError("Open a font first.")
    font = _native("fontlab").CurrentFont()
    return OpenContoursReport(package.id, len(package.masters), scan(font, package))


def select(report: OpenContoursReport, names: list | None = None) -> list:
    """Select ``names`` (default every report glyph), once each, in the font it was scanned from."""
    names = list(dict.fromkeys(row[0] for row in report.rows if names is None or row[0] in names))
    return scripting.select_glyphs(names, package_id=report.package_id)
