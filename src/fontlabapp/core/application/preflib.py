#!/usr/bin/env python3
# this_file: src/fontlabapp/core/application/preflib.py
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

from typing import Any
try:
    from fontlabapp.core.utils import attribdict, deepmerge, json
except ImportError:
    from fontlabapp.core.utils import attribdict, deepmerge, json


class PrefLib(object):
    def __init__(self, app: Any) -> None:
        self.paths = app.paths
        self.lib = self._loadlib()
        self.pref = attribdict()
        self.update = deepmerge
        self.save()

    def getpref(self, prefobj: Any, defaults: Any) -> Any:
        defaults = attribdict(defaults)
        deepmerge(defaults, prefobj)
        deepmerge(prefobj, defaults)
        # self.pref = self.json2attribdict(self.attribdict2json(self.pref))
        self.save()
        return prefobj

    def save(self) -> Any:
        self.paths.appPrefLibPath.parent.mkdir(parents=True, exist_ok=True)
        with self.paths.appPrefLibPath.open("w", encoding="utf-8") as f:
            f.write(self.attribdict2json(self.lib))

    def json2attribdict(self, j: Any) -> Any:
        value = json.loads(j, object_hook=attribdict)
        if not isinstance(value, dict):
            raise ValueError("Preference library must contain a JSON object")
        return attribdict(value)


    def attribdict2json(self, adict: Any) -> Any:
        return json.dumps(
            adict, indent=2, cls=json.SmartJSONEncoder, ensure_ascii=False
        )

    def _loadlib(self) -> Any:
        pref = attribdict()
        if self.paths.appPrefLibPath.is_file():
            with self.paths.appPrefLibPath.open("r") as f:
                j = f.read()
                pref = self.json2attribdict(j)
        return pref


if __name__ == "__main__":
    from fontlabapp import *

    app = Application()
    preflib = app.preflib
    pref = preflib.getpref(
        preflib.lib.com.fontlab.demo, {"key1": "val1", "key2": "val2"}
    )
    pref.key1 = "val3"
    print("pref:", pref)
    print("preflib.pref:", preflib.pref)
    print("preflib.lib:", preflib.lib)
    preflib.save()
