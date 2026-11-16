# this_file: src/fontlabapp/fontui/node_editor/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Lazy Node Editor composition; native Qt loads only when the window opens."""


def show(parent=None):
    from .ui import show as open_editor

    return open_editor(parent=parent)
