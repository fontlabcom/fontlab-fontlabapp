# this_file: src/fontlabapp/studios/nastaliq_connections/app.py
# SPDX-License-Identifier: Apache-2.0
"""Assemble the preserved native feature panels in the shared App shell."""
from typing import Any

ROUTES = [('Nastaliq Connection Editor', 'editor', 'panel_type', 'apply', 'Save connection')]
SIGNALS = {'editor': (('left_pick', 'currentIndexChanged'), ('family_pick', 'currentIndexChanged'), ('variant_pick', 'currentIndexChanged'), ('master_pick', 'currentIndexChanged'))}


def build(module: str, factory: str, parent: Any) -> Any:
    """Load a task only when the shell builds its tab."""
    from fontlabapp.fontui import identity_panel

    return identity_panel(f"features.identity_tools.nastaliq_connections.{module}", factory,
                          parent, factory_type=factory == "panel_type")


def show(*, tab: str | None = None, parent: Any = None, **kwargs: Any) -> Any:
    """Open the studio, preserving the requested historical task route."""
    from fontlabapp.fontui import identity_route as Route
    from fontlabapp.fontui import identity_studio as assemble

    titles = [row[0] for row in ROUTES]
    if tab is not None and tab not in titles:
        raise ValueError(f"Unknown Nastaliq Connections tab: {tab}")
    routes = [Route(title, lambda parent, module=module, factory=factory: build(module, factory, parent),
                    refresh="refresh", preview="preview_pair", apply=action,
                    apply_label=label or "Apply Changes",
                    preview_signals=SIGNALS[module], preview_target=lambda panel: panel.proof_target(),
                    glyph_column=None)
              for title, module, factory, action, label in ROUTES]
    shell = assemble('Nastaliq Connections', routes, preview='tglyph', parent=parent, **kwargs)
    if tab is not None:
        shell.tabs.setCurrentIndex(titles.index(tab))
    return shell
