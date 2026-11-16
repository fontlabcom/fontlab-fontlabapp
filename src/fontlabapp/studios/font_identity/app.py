# this_file: src/fontlabapp/studios/font_identity/app.py
# SPDX-License-Identifier: Apache-2.0
"""Font Identity keeps names, versions and detached trial export in one window."""

from typing import Any

import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid root lazy native exports


def show(parent: Any = None, *, package: Any = None, font: Any = None,
         tab: str | None = None) -> Any:
    """Open all identity tasks with their original guarded writers."""
    return fontui.identity_studio(
        'Font Identity',
        (
            fontui.identity_route('Names and Credits', lambda parent: fontui.identity_panel("fonts.identity_tools.font_identity.names", "panel_type", parent, factory_type=True), refresh='refresh', apply='apply'),
            fontui.identity_route('Bump Font Version', lambda parent: fontui.identity_panel("fonts.identity_tools.font_identity.version", "panel_type", parent, factory_type=True), refresh='refresh', apply='apply'),
            fontui.identity_route('Trial Font Maker', lambda parent: fontui.identity_panel("fonts.identity_tools.font_identity.trial", "studio_panel_type", parent, factory_type=True), refresh='refresh_exports',
                  apply='apply', apply_label='Make Trial Copies', buttons=('rescan_button',)),
        ),
        parent=parent, package=package, font=font, tab=tab,
    )
