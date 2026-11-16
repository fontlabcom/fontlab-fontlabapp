# this_file: src/fontlabapp/studios/kerning_browser/owner.py
# SPDX-License-Identifier: Apache-2.0
"""Retain the Browser until its owned cleanup reaches a terminal state."""
import sys
from collections.abc import Callable
from typing import Any

KEY = "kerning_browser"


def open_owned(factory: Callable[[], Any]) -> Any:
    """Replace only a completely closed Browser; never allocate past refusal."""
    registry = getattr(sys, "_fontlab_samples", None)
    if registry is None:
        registry = sys._fontlab_samples = {}
    old = registry.get(KEY)
    if old is not None:
        result = old.close()
        if result is False or not old._close_complete:
            old.show()
            return old
    shell = factory()
    close = shell.close

    def close_owned() -> Any:
        result = close()
        if shell._close_complete and registry.get(KEY) is shell:
            registry.pop(KEY)
        return result

    shell.close = close_owned
    registry[KEY] = shell
    return shell
