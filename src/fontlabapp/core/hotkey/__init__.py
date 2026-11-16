#!/usr/bin/env python3
# this_file: src/fontlabapp/core/hotkey/__init__.py
# -*- coding: utf-8 -*-

"""Platform hotkey managers, imported only on first attribute access."""

import importlib as _importlib
import sys as _sys

__all__ = ["HotkeyManager"]


def __getattr__(name):
    if name != "HotkeyManager":
        raise AttributeError(name)
    if _sys.platform == "darwin":
        return _importlib.import_module(__name__ + ".mac").HotkeyManager
    if _sys.platform == "win32":
        raise NotImplementedError
    raise AttributeError(name)
