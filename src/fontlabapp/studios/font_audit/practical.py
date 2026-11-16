# this_file: src/fontlabapp/studios/font_audit/practical.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""WP08 source-named report routes over the existing Font Audit owners.

Category classification remains caller supplied: App never imports Glyport.
The XML is a selectable fragment, not a font edit or a file export.
"""

from typing import Any

from fontlabapp.studios import TabSpec
from .app import show as show_audit

ROUTES = (
    ("Case Coverage", "Case & small caps"),
    ("Categories to XML Lib Key", None),
    ("Empty Glyphs", "Empty"),
    ("Font Overview", "Overview"),
    ("Glyph Table CSV", "Glyph table"),
    ("Label Statistics", "Overview"),
    ("Smallcap Consistency", "Case & small caps"),
    ("Unicode Coverage", "Unicode"),
)


def report_tab(shell: Any, route: str) -> Any:
    """Keep each existing report implementation and its selectable source route."""
    from .app import studio_for
    from .tabs import TAB_CLASSES

    studio = studio_for(shell)
    tab = TAB_CLASSES[route](studio)
    if route == "Case & small caps":
        tab.case_coverage = guarded(studio, tab.case_coverage)
        tab.smallcaps = guarded(studio, tab.smallcaps)
    shell.set_actions(tab.widget, refresh=studio.reload)
    return tab.widget


def guarded(studio: Any, action: Any) -> Any:
    """Fence report actions which use native current-font backends."""
    def run() -> Any:
        studio.package()
        return action()
    return run


def captured_package(getter: Any) -> Any:
    """Keep the original package; refuse refresh after the active document changes."""
    package = getter()
    identity = None if package is None else package.id

    def current() -> Any:
        active = getter()
        active_id = None if active is None else active.id
        if active_id != identity:
            raise ValueError("Activate the original font or reopen Font Audit.")
        return package

    return current


def show(*, classify: Any = None, **kwargs: Any) -> Any:
    """Open the eight mapped reports; preserve original compound report controls."""
    from fontlabapp.core.scripting import current_package
    from fontlabapp.fontui import current_font, category_report

    kwargs["package"] = captured_package(kwargs.get("package") or current_package)
    font = (kwargs.get("font") or current_font)()
    kwargs["package"]()
    kwargs["font"] = lambda: font
    specs = tuple(
        TabSpec(title, (lambda shell: category_report(shell, classify)) if route is None
                else (lambda shell, selected=route: report_tab(shell, selected)))
        for title, route in ROUTES
    )
    shell = show_audit(task_specs=specs, **kwargs)
    shell.set_about(
        "Font Audit: whole-font reports with a separate read-only proof.\n"
        "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
        "Menus: https://github.com/fontlabcom/fontlab-python-scriptmix\n"
        "FontLab App contributors (Apache-2.0). Casefolding workflow: mekkablue "
        "(Apache-2.0). Category XML workflow: Simon Cozens (MIT). See NOTICE.\n"
        "Choose a report tab. Refresh reads the captured font; activate it again "
        "or reopen Font Audit after changing documents."
    )
    return shell
