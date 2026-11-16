# this_file: src/fontlabapp/studios/proof_studio/practical.py
# SPDX-License-Identifier: Apache-2.0
"""Practical proof menus, assembled from the existing exact proof generators."""

from dataclasses import replace
from typing import Any

from fontlabapp.studios import TabSpec

from .generators import Generator


def context_generators() -> tuple[Generator, ...]:
    """Each original context command is a separately named tab, with its exact mode."""
    from .generators.between import GENERATOR as between
    from .generators.surround import GENERATOR as surround

    return tuple(
        replace(generator, title=generator.scripts[key], choices=((label, key),))
        for generator in (between, surround)
        for label, key in generator.choices
    )


def _builder(generator: Generator) -> Any:
    def build(shell: Any) -> Any:
        import fontlabapp.fontui as fontui

        from .app import studio_for
        from .tabs import GeneratorTab

        class Panel(fontui.owned_panel_type()):
            def close(self):
                if self.tab is not None:
                    self.tab.close()
                return super().close()

        owner = Panel(shell.widget)
        owner.tab = None
        try:
            owner.tab = GeneratorTab(studio_for(shell), generator.title, generators=(generator,), parent=owner.widget)
        except BaseException:
            owner.close()
            raise
        owner.layout.addWidget(owner.tab.widget)
        shell.set_actions(owner, refresh=owner.tab.regenerate, preview=owner.tab.regenerate)
        def selected(index: int) -> None:
            if shell.tabs.widget(index) is owner.widget:
                try:
                    owner.tab.show_part()
                except Exception as error:  # noqa: BLE001 - contain preview failures at the Qt boundary
                    shell.set_status(f"Preview unavailable: {error}")

        owner.connect(shell.tabs.currentChanged, selected)
        return owner

    return build


def show_context(parent: Any = None, **kwargs: Any) -> Any:
    """Open Context Proof using the existing read-only TMetrics shell and native writers."""
    from fontlabapp.core.scripting import current_package

    from .app import show
    from .session import selected_names

    package = kwargs.get("package") or current_package
    captured = package()
    expected_id = None if captured is None else captured.id

    def guard(callback: Any) -> Any:
        def run(*args: Any, **options: Any) -> Any:
            current = package()
            current_id = None if current is None else current.id
            if current_id != expected_id:
                raise ValueError("The active font changed. Close and reopen Context Proof for that font.")
            return callback(*args, **options)
        return run

    kwargs["selection"] = guard(kwargs.get("selection") or selected_names)
    routes = tuple(replace(g, open=guard(g.open)) for g in context_generators())
    shell = show(parent, title="Context Proof", tab_specs=tuple(
        TabSpec(generator.title, _builder(generator)) for generator in routes
    ), **kwargs)
    shell.tabs.setUsesScrollButtons(True)
    shell.set_about(
        "Context Proof\nSelect glyphs, including repeated Glyph-window occurrences, "
        "then choose a context tab. Preview and Copy keep the exact proof text; "
        "Open creates a new FontLab Glyph tab using the current master.\n"
        "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
        "Credits: Pedro Arilla, Apache-2.0; FontLab App contributors. "
        "See Scriptmix NOTICE and additional-tools.json for original provenance."
    )
    shell.tabs.setCurrentIndex(0)
    shell._run_action("preview")
    return shell
