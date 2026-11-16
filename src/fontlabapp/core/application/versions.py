#!/usr/bin/env python3
# this_file: src/fontlabapp/core/application/versions.py
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
import sys
import platform
import re
from collections import namedtuple

version_info = namedtuple('version_info', ('major', 'minor', 'micro', 'build'))

class Versions(object):
    def __init__(self, app: Any) -> None:
        from fontlabapp import _native
        QtCore = _native("PythonQt").QtCore
        self.app = app
        self._sysinfo = QtCore.QSysInfo()
        # Application name, version and arch
        self.app_name = self.app.qapp.applicationName
        self.app_version = self.app.qapp.applicationVersion
        self.app_version_info = self._get_version_info_from_str(self.app_version)
        self.app_arch = self._sysinfo.buildCpuArchitecture()
        # Operating system name, version and arch
        self.os_name = sys.platform
        self.os_full_name = self._sysinfo.prettyProductName()
        if sys.platform == 'win32':
            self.os_version = f"{self._sysinfo.productVersion()}.{platform.version()}"
        elif sys.platform == 'darwin':
            self.os_version = self._sysinfo.productVersion()
        else:
            self.os_version = self._sysinfo.productVersion()
        self.os_version_info = self._get_version_info_from_str(self.os_version)
        self.os_arch = self._sysinfo.currentCpuArchitecture()
        # Python version
        self.py_version = platform.python_version()
        self.py_version_info = version_info(
            major = sys.version_info.major,
            minor = sys.version_info.minor,
            micro = sys.version_info.micro,
            build = sys.version_info.serial)
        # Qt version
        self.qt_version = QtCore.qVersion()
        self.qt_version_info = self._get_version_info_from_str(self.qt_version)

    def _get_version_info_from_str(self, verstr: Any) -> Any:
        fields = verstr.split('.')[:4]
        matches = [re.match(r"^([0-9]+)", field) for field in fields]
        if not all(matches):
            raise ValueError(f"Version must begin with numeric components: {verstr!r}")
        verlist = [int(match.group(1)) for match in matches]
        if len(verlist) < 4:
            verlist += [0] * (4 - len(verlist))
        return version_info(*verlist)
