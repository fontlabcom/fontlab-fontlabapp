# this_file: src/fontlabapp/studios/feature_authoring/app.py
# SPDX-License-Identifier: Apache-2.0
"""Assemble the preserved native feature panels in the shared App shell."""
from typing import Any

ROUTES = [('Build Suffix Substitution', 'suffix_substitution', 'Dialog', 'apply', 'Append to feature'), ('Classes Browser', 'classes_browser', 'Dialog', None, ''), ('Feature Code Viewer', 'feature_code_viewer', 'Dialog', None, ''), ('Generate Random Alternates Feature', 'random_alternates', 'panel_type', 'apply', 'Write feature')]
SIGNALS = {'suffix_substitution': (('suffix', 'textChanged'), ('tag', 'textChanged')), 'classes_browser': (('table', 'itemSelectionChanged'), ('search', 'textChanged')), 'feature_code_viewer': (('feature', 'currentIndexChanged'),), 'random_alternates': (('source_edit', 'textChanged'),)}


def build(module: str, factory: str, parent: Any) -> Any:
    """Load a task only when the shell builds its tab."""
    from fontlabapp.fontui import identity_panel

    return identity_panel(f"features.identity_tools.feature_authoring.{module}", factory,
                          parent, factory_type=factory == "panel_type")


def show(*, tab: str | None = None, parent: Any = None, **kwargs: Any) -> Any:
    """Open the studio, preserving the requested historical task route."""
    from fontlabapp.fontui import identity_route as Route
    from fontlabapp.fontui import identity_studio as assemble

    titles = [row[0] for row in ROUTES]
    if tab is not None and tab not in titles:
        raise ValueError(f"Unknown Feature Authoring tab: {tab}")
    routes = [Route(title, lambda parent, module=module, factory=factory: build(module, factory, parent),
                    refresh="reload" if module in ("classes_browser", "feature_code_viewer", "alternate_preview", "ligature_finder", "suffix_report") else "refresh", preview="preview_changes" if module == "random_alternates" else "refresh", apply=action,
                    apply_label=label or "Apply Changes",
                    preview_signals=SIGNALS[module], preview_text=lambda panel: panel.proof_text(),
                    glyph_column=0 if module in ("suffix_substitution", "ligature_finder") else None)
              for title, module, factory, action, label in ROUTES]
    shell = assemble('Feature Authoring', routes, preview='tmetrics', parent=parent, **kwargs)
    if tab is not None:
        shell.tabs.setCurrentIndex(titles.index(tab))
    return shell
