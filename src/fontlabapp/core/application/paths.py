#!/usr/bin/env python3
# this_file: src/fontlabapp/core/application/paths.py
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
from pathlib import Path



class ApplicationPaths(object):
    def __init__(self, app: Any) -> None:
        from fontlabapp import _native
        QtCore = _native("PythonQt").QtCore
        self.app = app
        stdp = QtCore.QStandardPaths
        if sys.platform == "darwin":
            self.appFolder = Path(
                self.app.qapp.applicationDirPath().replace("/Contents/MacOS", "")
            )
        else:
            self.appFolder = Path(self.app.qapp.applicationDirPath())
        self.appDataFolder = Path(self.appFolder, "Resources")
        self.appExePath = Path(self.app.qapp.applicationDirPath())
        self.sysAppsFolders = [
            Path(p) for p in stdp.standardLocations(stdp.ApplicationsLocation)
        ]
        self.sysFontFolders = [
            Path(p) for p in stdp.standardLocations(stdp.FontsLocation)
        ]
        self.sysUserCacheFolder = Path(stdp.writableLocation(stdp.GenericCacheLocation))
        self.sysUserDataFolder = Path(stdp.writableLocation(stdp.GenericDataLocation))
        self.sysUserDesktopFolder = Path(stdp.writableLocation(stdp.DesktopLocation))
        self.sysUserDocumentsFolder = Path(
            stdp.writableLocation(stdp.DocumentsLocation)
        )
        self.sysUserDownloadFolder = Path(stdp.writableLocation(stdp.DownloadLocation))
        self.sysUserHomeFolder = Path(stdp.writableLocation(stdp.HomeLocation))
        self.sysUserMoviesFolder = Path(stdp.writableLocation(stdp.MoviesLocation))
        self.sysUserMusicFolder = Path(stdp.writableLocation(stdp.MusicLocation))
        self.sysUserPicturesFolder = Path(stdp.writableLocation(stdp.PicturesLocation))
        self.tempFolder = Path(stdp.writableLocation(stdp.TempLocation))
        self.userAutoSaveFolder = Path(self.app.pref.pathAutoSave)
        self.userDataDefaultFolder = Path(self.app.pref.dataPathDefault)
        self.userDataFolder = Path(self.app.pref.dataPath)
        if sys.platform == "darwin":
            self.sysUserPrefFolder = Path(stdp.writableLocation(stdp.ConfigLocation))
        else:
            self.sysUserPrefFolder = Path(self.userDataFolder, "Data")
        self.userDsigCertificatePath = Path(self.app.pref.dsigCertificatePath)
        self.userDsigPrivateKeyPath = Path(self.app.pref.dsigPrivateKeyPath)
        self.dataFolders = [Path(self.userDataFolder), Path(self.appDataFolder)]
        app_name = self.app.qapp.applicationName
        app_name = app_name() if callable(app_name) else app_name
        self.appPrefLibPath = Path(
            self.sysUserPrefFolder, f"com.fontlab.{app_name}.lib.json"
        )

