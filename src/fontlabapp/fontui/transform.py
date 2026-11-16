# this_file: src/fontlabapp/fontui/transform.py
# SPDX-License-Identifier: Apache-2.0
"""Original affine transform preview over a borrowed detached UFO font."""

import contextlib
from collections.abc import Callable
from typing import Any

from ._fontport import require_fontport

with require_fontport(__name__):
    from fontlab_fontport.operations import transform_glyph
    from fontlab_fontport.recipe import Recipe
from PythonQt import QtGui

from .lifecycle import Owned
from .model import Outline, viewport
from .transform_view import MATRIX, build, exact_text, record


class TransformEditor(Owned):
    """Fontport builds and validates the recipe and transformed copy.

    The source font is never modified: compare, reset and zoom only change the
    view. Settings are written only by save_settings(path) to an explicit path.
    """

    def __init__(
        self,
        font: Any,
        name: str | None = None,
        parent: Any = None,
        on_change: Callable[[Any, Any], None] | None = None,
        on_invalidate: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.font: Any = font
        self.on_change: Callable[[Any, Any], None] | None = on_change
        self.on_invalidate: Callable[[], None] | None = None
        self._invalidating = False
        self.original: Outline | None = None
        self.result: Outline | None = None
        self.zoom: float = 1.0
        build(self)
        names = sorted(font.keys()) if font is not None else []
        self.glyph_control.addItems(names)
        if name in names:
            self.glyph_control.setCurrentIndex(names.index(name))
        self._show(Recipe())
        self.connect(self.glyph_control.currentIndexChanged, lambda *a: self.update())
        for control in self.matrix.values():
            self.connect(control.textChanged, lambda *a: self.update())
        self.connect(self.enabled_control.toggled, lambda *a: self.update())
        self.connect(self.intensity_slider.valueChanged, lambda *a: self._sync(True))
        self.connect(self.intensity_field.textChanged, lambda *a: self._sync(False))
        self.connect(self.compare_control.toggled, lambda *a: self.canvas.update())
        actions = {
            "reset": self.reset_transform,
            "view": self.reset_view,
            "zoom": lambda: self.set_zoom(self.zoom * 1.25),
            "script": self.show_script,
            "save": lambda: self._dialog(
                QtGui.QFileDialog.getSaveFileName, self.save_settings
            ),
            "load": lambda: self._dialog(
                QtGui.QFileDialog.getOpenFileName, self.load_settings
            ),
        }
        for key, action in actions.items():
            self.connect(self.buttons[key].clicked, lambda *a, run=action: run())
        self.update()
        # Initial on_change retains its legacy timing; linked peers may not exist yet.
        self.on_invalidate = on_invalidate

    def _invalidate(self) -> bool:
        """Clear this attempt before reads and let its consumer clear linked proof."""
        if self.closed or self._invalidating:
            return False
        self.result = None
        try:
            if self.on_invalidate is not None:
                self._invalidating = True
                try:
                    self.on_invalidate()
                finally:
                    self._invalidating = False
        except Exception as exc:  # noqa: BLE001 - notification refuses the attempt
            if not (self.closed or self.destroying or self._parent_dead):
                self.diagnostic.setText(str(exc))
            return False
        return not self.closed

    def _show(self, recipe: Recipe) -> None:
        """Write the recipe into the controls. Their signals stay blocked."""
        controls = [
            *self.matrix.values(),
            self.intensity_slider,
            self.intensity_field,
            self.enabled_control,
        ]
        blocked = [control.blockSignals(True) for control in controls]
        try:
            for (key, _), value in zip(MATRIX, recipe.matrix, strict=True):
                self.matrix[key].setText(exact_text(value))
            self.intensity_slider.setValue(round(recipe.intensity))
            self.intensity_field.setText(exact_text(recipe.intensity))
            self.enabled_control.setChecked(recipe.enabled)
        finally:
            for control, state in zip(controls, blocked, strict=True):
                control.blockSignals(state)

    def _sync(self, from_slider: bool) -> None:
        """The slider moves in whole percent; the text field keeps exact values."""
        if not self._invalidate():
            return
        target = self.intensity_field if from_slider else self.intensity_slider
        blocked = target.blockSignals(True)
        try:
            if from_slider:
                target.setText(str(self.intensity_slider.value))
            else:
                # recipe() reports invalid text, so the slider ignores it here.
                with contextlib.suppress(ValueError, OverflowError):
                    target.setValue(round(float(self.intensity_field.text)))
        finally:
            target.blockSignals(blocked)
        self.update()

    def recipe(self) -> Recipe:
        """Parse fields; Fontport's Recipe rejects invalid or singular matrices."""
        values = []
        for key, _ in MATRIX:
            text = self.matrix[key].text
            try:
                values.append(float(text))
            except ValueError:
                raise ValueError(f"{key}: not a number: {text!r}") from None
        text = self.intensity_field.text
        try:
            intensity = float(text)
        except ValueError:
            raise ValueError(f"intensity: not a number: {text!r}") from None
        return Recipe(
            matrix=tuple(values),
            intensity=intensity,
            enabled=bool(self.enabled_control.checked),
        )

    def update(self) -> bool:
        """Rebuild the preview. Show a recipe or model failure in the label.

        Return ``True`` when the preview is good. ``on_change`` runs after it.
        """
        if not self._invalidate():
            return False
        try:
            if self.font is None:
                raise ValueError("No font supplied")
            name = self.glyph_control.currentText
            if not name:
                raise ValueError("The font has no glyphs")
            recipe = self.recipe()
            glyph = self.font[name]
            transformed = transform_glyph(glyph, recipe)
            self.original, self.result = (
                record(self.font, glyph),
                record(self.font, transformed),
            )
        except Exception as exc:  # noqa: BLE001 - show recipe/model failures in owned UI
            self.result = None
            self.diagnostic.setText(str(exc))
            self.canvas.update()
            return False
        self.diagnostic.setText(
            f"{name}: affine preview at {recipe.intensity:g}%"
            + ("" if recipe.enabled else " (disabled: identity)")
            + "; the source font is unchanged."
        )
        self.canvas.update()
        if self.on_change is not None:
            try:
                self.on_change(recipe, transformed)
            except Exception as exc:  # noqa: BLE001 - consumer callback boundary
                self.diagnostic.setText(f"Callback failed: {exc}")
        return True

    def view(self, width: float, height: float) -> tuple[float, float, float]:
        """Return ``(scale, x, y)`` that fits both outlines into the canvas."""
        boxes = [o.bounds for o in (self.original, self.result) if o and o.bounds]
        bounds = None
        if boxes:
            bounds = tuple(
                f(b[i] for b in boxes) for i, f in enumerate((min, min, max, max))
            )
        info = self.font.info
        upm = info.unitsPerEm or 1000
        advance = max(self.original.width, self.result.width)
        return viewport(
            bounds,
            advance,
            info.descender if info.descender is not None else -0.2 * upm,
            info.ascender if info.ascender is not None else 0.8 * upm,
            width,
            height,
            self.zoom,
        )

    def set_zoom(self, zoom: float) -> None:
        self.zoom = min(64.0, max(1 / 64, zoom))
        self.canvas.update()

    def reset_view(self) -> None:
        self.set_zoom(1.0)

    def reset_transform(self) -> None:
        if not self._invalidate():
            return
        self._show(Recipe())
        self.update()

    def show_script(self) -> str:
        text = self.recipe().script()
        self.script_view.setPlainText(text)
        self.script_view.show()
        return text

    def save_settings(self, path: str) -> None:
        self.recipe().save(path)
        self.diagnostic.setText(f"Saved settings to {path}")

    def load_settings(self, path: str) -> None:
        if not self._invalidate():
            return
        self._show(Recipe.load(path))
        self.update()

    def _dialog(self, chooser: Any, action: Callable[[str], None]) -> None:
        """Ask for a settings path with ``chooser``; run ``action`` on it."""
        try:
            path = chooser(self.widget, "Transform settings", "", "JSON (*.json)")
            if path:
                action(str(path))
        except Exception as exc:  # noqa: BLE001 - file errors stay visible
            self.diagnostic.setText(str(exc))

    def close(self) -> None:
        self.on_change = None
        super().close()
