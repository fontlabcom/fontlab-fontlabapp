#!/usr/bin/env python3
# this_file: src/fontlabapp/core/application/context.py
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
from fontlabapp import _native

fontlab = _native("fontlab")

try:
    from fontlabapp.core.application.paths import ApplicationPaths
    from fontlabapp.core.application.versions import Versions
    from fontlabapp.core.utils import to_html, to_pre
except ImportError:
    from fontlabapp.paths import ApplicationPaths
    from fontlabapp.versions import Versions
    from fontlabapp.core.utils import to_html, to_pre
QtGui = _native("PythonQt").QtGui


class Application(object):
    @property
    def host(self) -> Any:
        """Live menus/actions/panels tree for this main window (``fontlabapp.core.host``)."""
        if '_host' not in self.__dict__:
            from fontlabapp.core.host import Host
            self._host = Host(self.main)
        return self._host

    @property
    def menu(self) -> Any:
        """Menu bar as attributes: ``app.menu.glyph.add_component()``."""
        return self.host.menu

    @property
    def actions(self) -> Any:
        """QActions by path or objectName: ``app.actions["Glyph > Add Component"]``."""
        return self.host.actions

    @property
    def panels(self) -> Any:
        """Panels with explicit visibility: ``app.panels.preview.show()``."""
        return self.host.panels

    @property
    def glyph_actions(self) -> Any:
        """Tools > Actions catalogue: ``app.glyph_actions.remove_overlap(["B"])``."""
        return self.host.glyph_actions

    @property
    def control(self) -> Any:
        """Native controls sharing this exact application and user objects."""
        if '_control' not in self.__dict__:
            from fontlabapp.core.controls import FontLab
            self._control = FontLab(application=self)
        return self._control

    def __init__(self, with_ui: Any=True, with_preflib: Any=True) -> None:
        self.ws = fontlab.flWorkspace.instance()
        self.main = self.ws.mainWindow
        self.qmenus = self.main.menuBar()
        self.item = fontlab.flItems
        self.qapp = QtGui.QApplication.instance()
        self.pref = fontlab.flPreferences()
        self.paths = ApplicationPaths(self)
        self.versions = Versions(self)
        if with_preflib:
            from fontlabapp.core.application.preflib import PrefLib

            self.preflib = PrefLib(self)
        if with_ui:
            from fontlabapp.core.application.ui import ApplicationUI

            self.ui = ApplicationUI(self)

    @staticmethod
    def _format(msg: Any, md: Any, styled: Any, css: Any, plain_suffix: str = "\n") -> Any:
        """HTML for Markdown/styled messages, else the text plus ``plain_suffix``."""
        if md or styled:
            return to_html(msg, md=bool(md), styled=styled, css=css)
        return msg + plain_suffix

    def _box(self, kind: Any, title: str, msg: Any) -> None:
        QtGui.QMessageBox(kind, title, msg).exec()

    def debug(self, msg: Any, md: Any=False, styled: Any=False, css: Any="") -> Any:
        self.main.doOutput(self._format(msg, md, styled, css), False)

    def info(self, msg: Any, gui: Any=False, md: Any=False, styled: Any=False, css: Any="") -> Any:
        msg = self._format(msg, md, styled, css)
        if gui:
            self._box(QtGui.QMessageBox.Information, "Info", msg)
        else:
            self.main.doOutput(msg, True)

    def warn(self, msg: Any, gui: Any=False, md: Any=False, styled: Any=False, css: Any="") -> Any:
        msg = self._format(msg, md, styled, css)
        if gui:
            self._box(QtGui.QMessageBox.Warning, "Warning", msg)
        else:
            self.main.doWarning(msg)

    def error(self, msg: Any, gui: Any=False, md: Any=False, styled: Any=False, css: Any="") -> Any:
        if gui:
            self._box(QtGui.QMessageBox.Critical, "Error", self._format(msg, md, styled, css, ""))
        elif md:
            self.main.doWarning(self._format(f"""<small>[ERROR] </small>\n{msg}""", md, styled, f"""color:lightcoral;{css}"""))
        elif styled:
            self.main.doWarning(self._format(msg, md, styled, f"""color:lightcoral;{css}"""))
        else:
            self.main.doWarning(f"[ERROR] {msg}\n")

    def print(self, msg: Any) -> Any:
        self.debug(to_pre(msg))

    def print_md(self, msg: Any, styled: Any=False, css: Any="") -> Any:
        self.debug(to_html(msg, md=True, styled=styled, css=css))

    def print_html(self, msg: Any, styled: Any=False, css: Any="") -> Any:
        self.debug(to_html(msg, md=False, styled=styled, css=css))
