# this_file: src/fontlabapp/studios/proof_studio/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Proof Studio (Phase D A7): generator registry and seven proof tabs.

Launch inside FontLab with::

    from fly.ap.studios.proof_studio import show; show()

One ``AppShell`` window with a TMetrics preview on top and one tab per
registry tab. It replaces the Scriptmix Proof scripts Glyphs Between Lining
Figures/Lowercase/Oldstyle Figures/Uppercase, Glyphs Surrounded by
H/HHOHH/I/Nnonn, Hoefler Lowercase, Hoefler Uppercase, KernKing and KernSym
(part 1), and the seven Random scripts, Real English/Spanish Text, Text
Filter, Word Finder, Waterfall, Text By Master, Master Text Comparison and
the Examples Saved Proof Sample (part 2).
Generators live one per module in ``generators``; "Open in FontLab Glyph tab"
opens the same new tabs, in the same order and number, as each script.
Read-only: no font edits, no history.
"""

from typing import Any

from fontlabapp.studios import TabSpec, register, tabs

APP = "Proof Studio"


def _builder(title: str) -> Any:
    def build(shell: Any) -> Any:
        from .app import studio_for
        from .tabs import GeneratorTab

        tab = GeneratorTab(studio_for(shell), title)
        tab.widget.destroyed.connect(lambda *args: tab.close())  # close cancels a running Open
        return tab.widget

    return build


def register_tabs() -> tuple[str, ...]:
    """Register each registry tab title not registered yet in this process; return the titles.

    Called by ``app.show``, not at import: listing the tabs imports every
    generator module, and importing the package must load no implementation.
    """
    from .generators import tab_titles

    titles = tab_titles()
    registered = {spec.title for spec in tabs(APP)}  # survives a reload of this package
    for title in titles:
        if title not in registered:  # new generator modules add their tabs; nothing is duplicated
            register(APP, TabSpec(title, _builder(title)))
            registered.add(title)
    return titles


def __getattr__(name: str) -> Any:
    if name == "TAB_TITLES":  # lazy: the registry's tab titles
        from .generators import tab_titles

        return tab_titles()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def show(*args: Any, **kwargs: Any) -> Any:
    """Open Proof Studio for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Studio`` state of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "register_tabs", "show", "studio_for"]
