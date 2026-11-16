#!/usr/bin/env python3
# this_file: src/fontlabapp/core/utils/__init__.py
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

"""Legacy utility exports, resolved lazily without importing children on startup."""

from importlib import import_module as _import_module

_CHILDREN = {"collections", "text", "merge", "json"}


def __getattr__(name: str):
    """Resolve the original wildcard utility surface only when requested."""
    if name == "__all__":
        collections = _import_module(__name__ + ".collections")
        text = _import_module(__name__ + ".text")
        return list(dict.fromkeys(["collections", "text", "merge", *(
            n for module in (collections, text) for n in vars(module)
            if not n.startswith("_")), "deepmerge"]))
    if name in _CHILDREN:
        return _import_module(__name__ + "." + name)
    if name.startswith("__"):
        raise AttributeError(name)
    if name == "deepmerge":
        return _import_module(__name__ + ".merge").deepmerge
    for child in ("text", "collections"):
        module = _import_module(__name__ + "." + child)
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(name)
