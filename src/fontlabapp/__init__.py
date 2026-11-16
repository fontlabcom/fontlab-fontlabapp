#!/usr/bin/env python3
# this_file: src/fontlabapp/__init__.py
# -*- coding: utf-8 -*-
# Copyright (c) 2022 Adam Twardoch
# License: BSD 3-Clause License
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""FontLab context with host-free utility imports and lazy native access."""

from importlib import import_module
from importlib.util import find_spec
from typing import Any
from importlib.metadata import PackageNotFoundError, version
from fontlabapp._legacy import install as _install_legacy

_install_legacy()

try:
    __version__ = version("fontlab-fontlabapp")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "app",
    "Application",
    "FontLab",
    "menu",
    "actions",
    "panels",
    "glyph_actions",
]


def __getattr__(name: str) -> Any:
    legacy_name = "fontlabapp." + name
    if find_spec(legacy_name) is not None:
        value = import_module(legacy_name)
        globals()[name] = value
        return value
    if name.startswith("_"):
        raise AttributeError(name)
    if name == "FontLab":
        value = getattr(import_module("fontlabapp.core.controls"), name)
    elif name in {
        "Application",
        "ApplicationPaths",
        "Versions",
        "ApplicationUI",
        "PrefLib",
    }:
        value = getattr(import_module("fontlabapp.core.application"), name)
    elif name == "app":
        value = __getattr__("Application")()
    elif name in {"menu", "actions", "panels", "glyph_actions"}:
        return getattr(import_module("fontlabapp.core.host"), name)
    elif name in {"FL", "fontgate", "fontlab", "PythonQt"}:
        value = _native(name)
    elif name in {"Qt", "QtCore", "QtGui"}:
        value = getattr(_native("PythonQt"), name)
    else:
        for module in ("fontlab", "FL"):
            try:
                native = _native(module)
            except RuntimeError as error:
                # Host module absent (off-host): try the next one, then AttributeError.
                missing = error.__cause__
                if isinstance(missing, ModuleNotFoundError) and missing.name == module:
                    continue
                raise
            if hasattr(native, name):
                value = getattr(native, name)
                break
        else:
            raise AttributeError(name)
    globals()[name] = value
    return value


def _native(name: str) -> Any:
    try:
        return import_module(name)
    except ModuleNotFoundError as error:
        if error.name == name:
            raise RuntimeError(
                f"{name} requires the native API inside FontLab"
            ) from error
        raise
