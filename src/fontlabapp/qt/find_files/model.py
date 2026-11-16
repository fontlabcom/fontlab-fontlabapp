# this_file: src/fontlabapp/qt/find_files/model.py
# SPDX-License-Identifier: Apache-2.0
"""Complete paired font-source/script file finders, loaded through public Fly.

Only owned search resources are closed. No font, file-content, preference,
clipboard or Output writer is used. Explicit result activation delegates to the
normal desktop opener; file contents are never imported or executed here.
"""

from typing import Any

from fontlabapp.qt.find_files.search import Search

__all__ = ["Search", "show", "show_bytes"]


def show() -> Any:
    """Open the decoded UTF8/incremental-table profile for real user directories."""
    from fontlabapp.qt.find_files.ui import dialog_type
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(dialog_type("text"), "find-font-files-text")


def show_bytes() -> Any:
    """Open the exact UTF8-byte/final-table profile with query histories."""
    from fontlabapp.qt.find_files.ui import dialog_type
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(dialog_type("bytes"), "find-font-files-bytes")
