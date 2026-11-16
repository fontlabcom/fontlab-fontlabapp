# this_file: src/fontlabapp/studios/feature_explorer/app.py
# SPDX-License-Identifier: Apache-2.0
"""Assemble the preserved native feature panels in the shared App shell."""
from typing import Any

ROUTES = [('Alternate Preview', 'alternate_preview', 'Dialog', None, ''), ('Ligature Finder', 'ligature_finder', 'Dialog', None, ''), ('Suffix Report', 'suffix_report', 'Dialog', None, '')]
SIGNALS = {'alternate_preview': (('base', 'textChanged'), ('scope', 'currentIndexChanged')), 'ligature_finder': (('search', 'textChanged'),), 'suffix_report': (('table', 'itemSelectionChanged'),)}


def build(module: str, factory: str, parent: Any) -> Any:
    """Load a task only when the shell builds its tab."""
    from fontlabapp.fontui import identity_panel

    return identity_panel(f"features.identity_tools.feature_explorer.{module}", factory,
                          parent, factory_type=factory == "panel_type")


def show(*, tab: str | None = None, parent: Any = None, **kwargs: Any) -> Any:
    """Open the studio, preserving the requested historical task route."""
    from fontlabapp.fontui import identity_route as Route
    from fontlabapp.fontui import identity_studio as assemble

    titles = [row[0] for row in ROUTES]
    if tab is not None and tab not in titles:
        raise ValueError(f"Unknown Feature Explorer tab: {tab}")
    routes = [Route(title, lambda parent, module=module, factory=factory: build(module, factory, parent),
                    refresh="reload" if module in ("classes_browser", "feature_code_viewer", "alternate_preview", "ligature_finder", "suffix_report") else "refresh", preview="refresh", apply=action,
                    apply_label=label or "Apply Changes",
                    preview_signals=SIGNALS[module], preview_text=lambda panel: panel.proof_text(),
                    glyph_column=0 if module in ("suffix_substitution", "ligature_finder") else None)
              for title, module, factory, action, label in ROUTES]
    shell = assemble('Feature Explorer', routes, preview='tmetrics', parent=parent, **kwargs)
    if tab is not None:
        shell.tabs.setCurrentIndex(titles.index(tab))
    return shell
