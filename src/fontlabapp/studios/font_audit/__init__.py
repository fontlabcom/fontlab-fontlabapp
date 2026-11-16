# this_file: src/fontlabapp/studios/font_audit/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Font Audit (Phase D A8): a read-only whole-font report studio with a TMetrics preview.

Launch inside FontLab with::

    from fly.ap.studios.font_audit import show; show()

One ``AppShell`` window, TMetrics on top, six tabs: Overview (Font Overview
and Label Statistics), Glyph table (Glyph Table CSV), Unicode (Unicode
Coverage), Empty (Empty Glyphs), Case & small caps (Case Coverage and
Smallcap Consistency) and Unreferenced (Select Unreferenced Glyphs).
Every tab reads one shared ``studios._records`` catalogue. Read-only: no
font edits, no history; side effects are Font-window selection, CSV export
and the clipboard, as in the Scriptmix scripts.
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Font Audit"
TAB_TITLES = ("Overview", "Glyph table", "Unicode", "Empty", "Case & small caps", "Unreferenced")


def _builder(title: str) -> Any:
    def build(shell: Any) -> Any:
        from .app import studio_for
        from .tabs import TAB_CLASSES

        return TAB_CLASSES[title](studio_for(shell)).widget

    return build


def register_tabs() -> tuple[str, ...]:
    """Register each tab title not registered yet in this process; return the titles."""
    registered = {spec.title for spec in registry.tabs(APP)}  # ``.tabs`` is the tab module once loaded
    for title in TAB_TITLES:
        if title not in registered:
            registry.register(APP, TabSpec(title, _builder(title)))
    return TAB_TITLES


def show(*args: Any, **kwargs: Any) -> Any:
    """Open Font Audit for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Studio`` state of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "register_tabs", "show", "studio_for"]
