#!/usr/bin/env python3
# this_file: src/fontlabapp/core/utils/json.py
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
from datetime import timedelta
from pathlib import PosixPath, WindowsPath
from json import *
import json.decoder as decoder

# Add any serializing functions here
def stringify(obj: Any) -> Any:

    if isinstance(obj, bytes):
        return obj.decode("utf8", "ignore")

    if isinstance(obj, str):
        return obj

    if isinstance(obj, PosixPath):
        return str(obj)

    if isinstance(obj, WindowsPath):
        return str(obj)

    # Handle DateTime objects
    if hasattr(obj, "isoformat"):
        return obj.isoformat()

    if isinstance(obj, timedelta):
        return obj.__str__()

    # Handle hashes
    if hasattr(obj, 'hexdigest'):
        return obj.hexdigest()


class SmartJSONEncoder(JSONEncoder):
    def default(self, obj: Any) -> Any:
        out = stringify(obj)
        if out is not None:
            return out
        return JSONEncoder.default(self, obj)