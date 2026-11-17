# this_file: tests/_light_canvas.py
"""Fake-Qt tests have no palette; give painters the light-theme colours."""


def light_canvas(monkeypatch, *modules):
    def colors(widget, light):
        return {**light, "selection_background": "#d8eaff", "selection_foreground": "#202124"}

    for module in modules:
        monkeypatch.setattr(module, "_canvas_colors", colors)
