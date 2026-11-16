#!/usr/bin/env python3
# this_file: src/fontlabapp/core/application/ui.py
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
    from fontlabapp.core.utils import attribdict, slugify
except ImportError:
    from fontlabapp.core.utils import attribdict, slugify

from PythonQt import QtGui

from fontlabapp.qt.safe import qt_list


class ApplicationUI(object):
    def __init__(self, app: Any) -> None:
        self.app = app
        self.ws = self.app.ws
        self.main = self.app.main
        self.qmenus = self.app.qmenus
        self.item = self.app.item
        self.qapp = self.app.qapp
        self.pref = self.app.pref
        self.paths = self.app.paths
        self.loadUI()

    def loadUI(self) -> Any:
        self.widgets = self.buildWidgetsDict()
        self.panels = self.buildPanels()
        self.actions = self.getActions()
        self.menu = self.buildMainMenu()
        self.updatePanels()

    def buildWidgetsDict(self) -> Any:
        widgets = attribdict()
        for w in qt_list(self.qapp.allWidgets):
            if w.statusTip and w.statusTip[0] == "@":
                statusTips = w.statusTip[1:].split(".")
                if len(statusTips) == 2:
                    group, subgroup = statusTips
                    widgets[group] = widgets.get(group, attribdict())
                    widgets[group][subgroup] = w
        return widgets

    def findWidgets(self, widget: Any, className: Any=None) -> Any:
        widgets = []
        if hasattr(widget, "topLevelWidgets"):
            all_widgets = qt_list(widget.topLevelWidgets)
            if className:
                for w in all_widgets:
                    if w.className() == className:
                        widgets.append(w)
            else:
                widgets += all_widgets
        if className and hasattr(widget, "findChildren"):
            widgets += qt_list(widget.findChildren, className)
        elif hasattr(widget, "children"):
            all_widgets = widget.children()
            if className:
                widgets.extend(
                    w for w in widget.children() if w.className() == className
                )
            else:
                widgets += all_widgets
        return widgets

    def makeMenuEntry(self, menu: Any) -> Any:
        return attribdict([("qmenu", menu)])

    def makeActionEntry(self, action: Any) -> Any:
        return attribdict([("qaction", action), ("trigger", action.trigger)])

    def recurseMenu(self, menu: Any, menu_d: Any) -> Any:
        for action in menu.actions():
            if action.isVisible():
                text = slugify(action.text)
                if action.isSeparator():
                    continue
                if action.menu():
                    menu_d[text] = self.recurseMenu(
                        action.menu(), self.makeMenuEntry(action.menu())
                    )
                else:
                    menu_d[text] = self.makeActionEntry(action)
        return menu_d

    def buildMainMenu(self) -> Any:
        menu_d = attribdict()
        for menu in self.qmenus.children():
            if isinstance(menu, QtGui.QMenu):
                text = slugify(menu.title)
                menu_d[text] = self.recurseMenu(menu, self.makeMenuEntry(menu))
        return menu_d

    def getActions(self, pname: Any=None) -> Any:
        if pname:
            w = self.panels[pname].widget
        else:
            w = self.main
        actions = attribdict()
        if w:
            for action in w.children():
                if isinstance(action, QtGui.QAction):
                    if action.isVisible():
                        text = slugify(action.text)
                        if text:
                            if action.menu():
                                actions[text] = self.recurseMenu(
                                    action.menu(), self.makeMenuEntry(action.menu())
                                )
                            else:
                                actions[text] = self.makeActionEntry(action)
        return actions

    def fontWindows(self) -> Any:
        return self.getWindowsByClass("FontWindow")

    def glyphWindows(self) -> Any:
        return self.getWindowsByClass("GlyphWindow")

    def getWindowsByClass(self, className: Any) -> Any:
        window_frames = self.findWidgets(self.qapp, "YFrameWindow")
        windows = attribdict()
        for window_count, window_frame in enumerate(window_frames):
            windows_all = self.findWidgets(
                window_frame.children()[0].qt_tabwidget_stackedwidget, className
            )
            for window in windows_all:
                title = window.windowTitle
                if title in windows.keys():
                    title += f" {window_count}"
                windows[title] = window
        return windows

    def buildPanels(self) -> Any:  ## Redo with app.main.showPanel(2, True)
        panels = attribdict(
            [
                (
                    "anchors_pins",
                    attribdict(
                        [
                            ("widget", self.widgets.pinspanel.PinsPanel),
                            ("obj", self.widgets.pinspanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "brush",
                    attribdict(
                        [
                            ("widget", self.widgets.brushproperties.BrushProperties),
                            ("obj", self.widgets.brushproperties),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "classes",
                    attribdict(
                        [
                            ("widget", self.widgets.classespanel.ClassesPanel),
                            ("obj", self.widgets.classespanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "color",
                    attribdict(
                        [
                            ("widget", self.widgets.colorpanel.ColorPanel),
                            ("obj", self.widgets.colorpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "elements",
                    attribdict(
                        [
                            ("widget", self.widgets.shapespanel.ShapesPanel),
                            ("obj", self.widgets.shapespanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "features",
                    attribdict(
                        [
                            ("widget", self.widgets.featurespanel.FeaturesPanel),
                            ("obj", self.widgets.featurespanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "fontaudit",
                    attribdict(
                        [
                            ("widget", self.widgets.auditpanel.AuditPanel),
                            ("obj", self.widgets.auditpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "font_info",
                    attribdict(
                        [
                            ("widget", self.widgets.fontinfopanel.FontInfoPanel),
                            ("obj", self.widgets.fontinfopanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "font_map",
                    attribdict(
                        [
                            ("widget", None),  # TODO add support
                            ("obj", None),  # TODO add support
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "fonts",
                    attribdict(
                        [
                            ("widget", self.widgets.fontspanel.FontsPanel),
                            ("obj", self.widgets.fontspanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "gallery",
                    attribdict(
                        [
                            ("widget", self.widgets.gallerypanel.GalleryPanel),
                            ("obj", self.widgets.gallerypanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "glyph",
                    attribdict(
                        [
                            ("widget", self.widgets.inspector_glyph.InspectorGlyph),
                            ("obj", self.widgets.inspector_glyph),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "guide",
                    attribdict(
                        [
                            ("widget", self.widgets.inspector_guide.InspectorGuide),
                            ("obj", self.widgets.inspector_guide),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "help",
                    attribdict(
                        [
                            ("widget", self.widgets.quicktipspanel.QuickTipsPanel),
                            ("obj", self.widgets.quicktipspanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "history",
                    attribdict(
                        [
                            ("widget", self.widgets.historypanel.HistoryPanel),
                            ("obj", self.widgets.historypanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "image",
                    attribdict(
                        [
                            ("widget", self.widgets.filterpanel.FilterPanel),
                            ("obj", self.widgets.filterpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "kerning",
                    attribdict(
                        [
                            ("widget", self.widgets.kerningpanel.KerningPanel),
                            ("obj", self.widgets.kerningpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "layers_masters",
                    attribdict(
                        [
                            ("widget", self.widgets.inspector_layers.InspectorLayers),
                            ("obj", self.widgets.inspector_layers),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "lookups",
                    attribdict(
                        [
                            ("widget", self.widgets.lookupspanel.LookupsPanel),
                            ("obj", self.widgets.lookupspanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "measurements",
                    attribdict(
                        [
                            ("widget", self.widgets.measurepanel.MeasurePanel),
                            ("obj", self.widgets.measurepanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "metrics",
                    attribdict(
                        [
                            ("widget", self.widgets.metricsdatapanel.MetricsDataPanel),
                            ("obj", self.widgets.metricsdatapanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "node",
                    attribdict(
                        [
                            ("widget", self.widgets.inspector_node.InspectorNode),
                            ("obj", self.widgets.inspector_node),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "output",
                    attribdict(
                        [
                            ("widget", self.widgets.outputpanel.OutputPanel),
                            ("obj", self.widgets.outputpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "pairs_phrases",
                    attribdict(
                        [
                            ("widget", self.widgets.pairspanel.PairsPanel),
                            ("obj", self.widgets.pairspanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "panels",
                    attribdict(
                        [
                            ("widget", self.widgets.panelspanel.PanelsPanel),
                            ("obj", self.widgets.panelspanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "preview",
                    attribdict(
                        [
                            ("widget", self.widgets.previewpanel.PreviewPanel),
                            ("obj", self.widgets.previewpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "scripting_python",
                    attribdict(
                        [
                            ("widget", self.widgets.pythonpanel.PythonPanel),
                            ("obj", self.widgets.pythonpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "selections",
                    attribdict(
                        [
                            ("widget", self.widgets.selectionspanel.SelectionsPanel),
                            ("obj", self.widgets.selectionspanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "source",
                    attribdict(
                        [
                            ("widget", self.widgets.sourcepanel.SourcePanel),
                            ("obj", self.widgets.sourcepanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "stroke",
                    attribdict(
                        [
                            ("widget", self.widgets.strokepanel.StrokePanel),
                            ("obj", self.widgets.strokepanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "tables",
                    attribdict(
                        [
                            ("widget", self.widgets.tablespanel.TablesPanel),
                            ("obj", self.widgets.tablespanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "toolbar",
                    attribdict(
                        [
                            ("widget", self.widgets.toolbarpanel.ToolbarPanel),
                            ("obj", self.widgets.toolbarpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "transform",
                    attribdict(
                        [
                            ("widget", self.widgets.paneltransform.PanelTransform),
                            ("obj", self.widgets.paneltransform),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "truetype_hinting",
                    attribdict(
                        [
                            ("widget", self.widgets.tthpanel.TTHPanel),
                            ("obj", self.widgets.tthpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "variations",
                    attribdict(
                        [
                            ("widget", self.widgets.locationpanel.LocationPanel),
                            ("obj", self.widgets.locationpanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
                (
                    "view",
                    attribdict(
                        [
                            (
                                "widget",
                                self.widgets.editinglayerspanel.EditingLayersPanel,
                            ),
                            ("obj", self.widgets.editinglayerspanel),
                            ("show", None),
                            ("toggle", None),
                            ("actions", None),
                        ]
                    ),
                ),
            ]
        )
        return panels

    def updatePanels(self) -> Any:
        for pname, p in self.panels.items():
            self.panels[pname]["actions"] = self.getActions(pname)

        self.panels["anchors_pins"][
            "show"
        ] = self.actions.main.anchors_pins_panel.trigger
        self.panels["fontaudit"]["show"] = self.actions.main.fontaudit_panel.trigger
        self.panels["brush"]["show"] = self.actions.main.brush_panel.trigger
        self.panels["classes"]["show"] = self.actions.main.classes_panel.trigger
        self.panels["color"]["show"] = self.actions.main.color_panel.trigger
        self.panels["elements"]["show"] = self.actions.main.elements_panel.trigger
        self.panels["features"]["show"] = self.actions.main.features_panel.trigger
        self.panels["font_info"]["show"] = self.actions.main.font_info_panel.trigger
        self.panels["font_map"]["show"] = self.actions.main.font_map_panel.trigger
        self.panels["fonts"]["show"] = self.actions.main.fonts_panel.trigger
        self.panels["gallery"]["show"] = self.actions.main.gallery_panel.trigger
        self.panels["glyph"]["show"] = self.actions.main.glyph_panel.trigger
        self.panels["guide"]["show"] = self.actions.main.guide_panel.trigger
        self.panels["help"]["show"] = self.actions.main.help_panel.trigger
        self.panels["history"]["show"] = self.actions.main.history_panel.trigger
        self.panels["image"]["show"] = self.actions.main.image_panel.trigger
        self.panels["kerning"]["show"] = self.actions.main.kerning_panel.trigger
        self.panels["layers_masters"][
            "show"
        ] = self.actions.main.layers_masters_panel.trigger
        self.panels["lookups"]["show"] = self.actions.main.lookups_panel.trigger
        self.panels["measurements"][
            "show"
        ] = self.actions.main.measurements_panel.trigger
        self.panels["metrics"]["show"] = self.actions.main.metrics_panel.trigger
        self.panels["node"]["show"] = self.actions.main.node_panel.trigger
        self.panels["output"]["show"] = self.actions.main.output_panel.trigger
        self.panels["pairs_phrases"][
            "show"
        ] = self.actions.main.pairs_phrases_panel.trigger
        self.panels["panels"]["show"] = self.main.actionPanelsPanel.trigger
        self.panels["preview"]["show"] = self.actions.main.preview_panel.trigger
        self.panels["scripting_python"][
            "show"
        ] = self.actions.main.scripting_python_panel.trigger
        self.panels["selections"]["show"] = self.actions.main.selections_panel.trigger
        self.panels["source"]["show"] = self.actions.main.source_panel.trigger
        self.panels["stroke"]["show"] = self.actions.main.stroke_panel.trigger
        self.panels["tables"]["show"] = self.actions.main.tables_panel.trigger
        self.panels["toolbar"]["show"] = self.actions.main.window.toolbar.trigger
        self.panels["transform"]["show"] = self.actions.main.transform_panel.trigger
        self.panels["truetype_hinting"][
            "show"
        ] = self.actions.main.truetype_hinting_panel.trigger
        self.panels["variations"]["show"] = self.actions.main.variations_panel.trigger
        self.panels["view"]["show"] = self.actions.main.view_panel.trigger

        wpanels = self.panels.panels.widgets
        self.panels["anchors_pins"]["toggle"] = wpanels.buttonAnchors.toggle
        self.panels["fontaudit"]["toggle"] = wpanels.buttonFontAudit.toggle
        self.panels["brush"]["toggle"] = wpanels.buttonBrush.toggle
        self.panels["classes"]["toggle"] = wpanels.buttonGroups.toggle
        self.panels["color"]["toggle"] = wpanels.buttonColors.toggle
        self.panels["elements"]["toggle"] = wpanels.buttonShapes.toggle
        self.panels["features"]["toggle"] = wpanels.buttonFeatures.toggle
        self.panels["font_info"]["toggle"] = wpanels.buttonFontInfo.toggle
        self.panels["font_map"]["toggle"] = wpanels.buttonFontMap.toggle
        self.panels["fonts"]["toggle"] = wpanels.buttonFonts.toggle
        self.panels["gallery"]["toggle"] = wpanels.buttonGallery.toggle
        self.panels["glyph"]["toggle"] = wpanels.buttonGlyphInfo.toggle
        self.panels["guide"]["toggle"] = wpanels.buttonGuide.toggle
        self.panels["help"]["toggle"] = wpanels.buttonQuickTips.toggle
        self.panels["history"]["toggle"] = wpanels.buttonHistory.toggle
        self.panels["image"]["toggle"] = wpanels.buttonImage.toggle
        self.panels["kerning"]["toggle"] = wpanels.buttonKerning.toggle
        self.panels["layers_masters"]["toggle"] = wpanels.buttonLayers.toggle
        self.panels["lookups"]["toggle"] = wpanels.buttonLookups.toggle
        self.panels["measurements"]["toggle"] = wpanels.buttonMeasure.toggle
        self.panels["metrics"]["toggle"] = wpanels.buttonMetrics.toggle
        self.panels["node"]["toggle"] = wpanels.buttonNode.toggle
        self.panels["output"]["toggle"] = wpanels.buttonOutput.toggle
        self.panels["pairs_phrases"]["toggle"] = wpanels.buttonPairs.toggle
        self.panels["panels"]["toggle"] = self.main.actionPanelsPanel.trigger
        self.panels["preview"]["toggle"] = wpanels.buttonPreview.toggle
        self.panels["scripting_python"]["toggle"] = wpanels.buttonScripting.toggle
        self.panels["selections"]["toggle"] = wpanels.buttonSelections.toggle
        self.panels["source"]["toggle"] = wpanels.buttonSource.toggle
        self.panels["stroke"]["toggle"] = wpanels.buttonStroke.toggle
        self.panels["tables"]["toggle"] = wpanels.buttonTables.toggle
        self.panels["toolbar"]["toggle"] = self.main.actionToolbarPanel.trigger
        self.panels["transform"]["toggle"] = wpanels.buttonTransformation.toggle
        self.panels["truetype_hinting"]["toggle"] = wpanels.buttonTTH.toggle
        self.panels["variations"]["toggle"] = wpanels.buttonVariations.toggle
        self.panels["view"]["toggle"] = wpanels.buttonView.toggle
