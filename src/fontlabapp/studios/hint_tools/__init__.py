# this_file: src/fontlabapp/studios/hint_tools/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""PostScript hint tools with accepted plans and explicit master targets."""
from typing import Any


def show(*args: Any, **kwargs: Any) -> Any:
    """Open the two-tab hint studio inside FontLab."""
    import fontlabapp.fontui as fontui
    return fontui.hint_tools_window(*args, **kwargs)
