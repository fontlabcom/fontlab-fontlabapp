# this_file: src/fontlabapp/studios/transform_studio/actions.py
# SPDX-License-Identifier: Apache-2.0
"""Pin an outline composition to its original native and preview font."""
from typing import Any


def capture(shell: Any, font: Any) -> Any:
    """Pin the preview font and refuse writes after its native context changes."""
    from fontlabapp.core.scripting import current_package
    import fontlabapp.fontui as fontui

    getter = shell._package or current_package
    original = getter()
    identity = getattr(original, "id", None)

    def package() -> Any:
        live = getter()
        if live is original or (identity is not None and getattr(live, "id", None) == identity):
            return original
        return None

    shell._package = package
    captured = (font or fontui.current_font)()
    return lambda: captured
