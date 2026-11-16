# this_file: src/fontlabapp/studios/shape_generators/app.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Five specialized generators in a captured-font AppShell."""
from typing import Any

import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid native parent fallback
from fontlabapp.core.scripting import current_package
from fontlabapp.studios import TabSpec

from .._kerning import Tool
from ..derived_glyphs.outline import bind
from .angular import AngularPanel
from .medial import MedialPanel
from .panel import GeneratorPanel

APP = 'Shape Generators'


def show(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None,
         angular_backend: Any = None, preferences: Any = None) -> Any:
    """Open the original algorithms with explicit Preview/Apply and owned teardown."""
    getter = package or current_package
    captured = getter()
    captured_id = None if captured is None else captured.id
    def bound_package() -> Any:
        live = getter()
        if (None if live is None else live.id) != captured_id:
            raise ValueError('The font changed. Reopen Shape Generators.')
        return live
    shell = fontui.app_shell(APP, 'tglyph', parent=parent, package=bound_package)
    try:
        tool = shell.shape_generators_tool = Tool(shell, APP, font=font)
        tool.reload()
        captured_font = tool.font()
        tool._font = lambda: captured_font
        tool.preview = preview(shell, tool) if preview else (
            fontui.glyph_view(captured_font, shell.widget, layer=tool.current, controls=False,
                              label_prefix=APP, hint_check=shell.hint_check, read_only=True)
            if captured_font is not None else None)
        if tool.preview is not None:
            shell.set_preview(tool.preview)
        angular = AngularPanel.__new__(AngularPanel)
        try:
            AngularPanel.__init__(angular, tool, backend=angular_backend, preferences=preferences)
        except BaseException as error:
            fontui.cleanup_failed_window(angular, error)
            raise
        shell.add_tab(TabSpec('Angularizzle', lambda owner: angular))
        for mode, title in (('comb', 'Comb'), ('sandblast', 'Sandblast'), ('sansomatic', 'Sansomatic')):
            panel = GeneratorPanel(tool, mode)
            shell.add_tab(TabSpec(title, lambda owner, panel=panel: panel.widget))
            panel.refresh()
        medial = MedialPanel(tool)
        bind(shell, tool, medial, 'Myanmar Medial Ra')
        shell.set_about('Shape Generators\nChoose a captured glyph and master, review the live plan, then Apply. '
                        'Angularizzle preserves opening paths for repeated Process; Restore opening paths keeps its colour mark. '
                        'Comb retains cubic ribbon edges; Sandblast uses bounded seeded placements; Sansomatic builds only empty layers; '
                        'Myanmar medial-ra creates all-master variants with separate Add Glyph history steps.\n'
                        'Credits: NaN Angularizzle; independent rewrites after Simon Cozens (MIT), '
                        'https://github.com/simoncozens/GlyphsScripts . App integration: Apache-2.0.')
        shell.show()
    except BaseException as error:
        fontui.cleanup_failed_window(shell, error)
        raise
    return shell
