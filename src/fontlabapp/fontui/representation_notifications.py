# this_file: src/fontlabapp/fontui/representation_notifications.py
# SPDX-License-Identifier: Apache-2.0
"""Inspect glyph representations and observed changes without editing the font."""

from typing import Any

__all__ = ("show",)
_HANDLES = []
_REPRESENTATIONS = ("defcon.glyph.area",)


def _panel_type():
    from PythonQt import QtGui

    from . import _construct
    from .lifecycle import Owned
    from .model import outline
    from .native import Browser

    class Explorer(Owned):
        """Own the browser, observer and reports; borrow the supplied font."""

        def __init__(self, font, parent):
            self.font, self.browser, self.observed = font, None, None
            self.names, self.rows = (), ()
            self.notifications = 0
            self._registered = False
            self._reading = False
            super().__init__(parent)
            self.widget.setWindowTitle("Representation and Notification Explorer")
            self.status = QtGui.QLabel(self.widget)
            self.table = QtGui.QTreeWidget(self.widget)
            self.table.setHeaderLabels(["Representation", "Value", "Cache before", "Cache after"])
            note = QtGui.QLabel(
                "Reads cached area and fresh decomposed bounds and outlines. "
                "Representation reads populate caches. Observes scripting Glyph.Changed "
                "events only; external native changes are not verified or invalidated. "
                "Refresh rereads this borrowed view; it never discards pending edits.", self.widget)
            note.setWordWrap(True)
            self.refresh_button = QtGui.QPushButton("Refresh representations", self.widget)
            for widget in (note, self.table, self.status, self.refresh_button):
                self.layout.addWidget(widget)
            self.connect(self.refresh_button.clicked, lambda *args: self.refresh())
            self.browser = _construct(Browser, font, self.widget, None, False, False, self.selected)
            self.layout.addWidget(self.browser.widget)

        def _detach(self):
            if self.observed is not None:
                self.observed.removeObserver(self, "Glyph.Changed")
                self.observed = None
                self._registered = False

        def selected(self, font, names):
            if self.closed:
                return
            try:
                if font is not self.font:
                    raise ValueError("Selection belongs to another font")
                self._detach()
                self.names = tuple(names)
                self.notifications = 0
                if names:
                    glyph = font[names[0]]
                    model = glyph.naked() if callable(getattr(glyph, "naked", None)) else glyph
                    if all(callable(getattr(model, method, None)) for method in
                           ("addObserver", "removeObserver", "hasObserver", "getRepresentation", "hasCachedRepresentation")):
                        # Retain before registering so partial registration can be cleaned up.
                        self.observed = model
                        model.addObserver(self, "changed", "Glyph.Changed")
                        self._registered = bool(model.hasObserver(self, "Glyph.Changed"))
                        if not self._registered:
                            raise RuntimeError("Observer registration was not acknowledged")
                self.refresh()
            except Exception as error:  # noqa: BLE001 - contain backend errors at UI callbacks
                self.rows = ()
                self.table.clear()
                self.status.setText(str(error))

        def changed(self, notification):
            if self.closed:
                return
            self.notifications += 1
            self.refresh(notification=True)

        def refresh(self, notification=False):
            if self.closed or self._reading:
                return
            self._reading = True
            self.rows = ()
            self.table.clear()
            try:
                if not self.names:
                    self.status.setText("No font supplied" if self.font is None else "Select a glyph")
                    return
                if self.observed is not None and not self._registered:
                    raise RuntimeError("Observer registration is not verified")
                name = self.names[0]
                glyph = self.font[name]
                model = glyph.naked() if callable(getattr(glyph, "naked", None)) else glyph
                if self.observed is not None and model is not self.observed:
                    raise ValueError("Selected glyph identity changed; select it again")
                rows = []
                if self.observed is not None:
                    for key in _REPRESENTATIONS:
                        before = model.hasCachedRepresentation(key)
                        value = model.getRepresentation(key)
                        after = model.hasCachedRepresentation(key)
                        if self.closed:
                            return
                        rows.append((key, str(value), str(before), str(after)))
                drawing = outline(self.font, name)
                if self.closed:
                    return
                rows.extend((("Decomposed bounds", str(drawing.bounds), "uncached", "fresh read"),
                             ("Decomposed outline", repr(drawing.recording), "uncached", "fresh read")))
                self.rows = tuple(rows)
                for row in rows:
                    self.table.addTopLevelItem(QtGui.QTreeWidgetItem(list(row)))
                if self.browser is not None:
                    self.browser.preview.set_glyph(name)
                status = (f"{self.notifications} Glyph.Changed notifications observed; "
                          if self.observed is not None else "Notifications/cache API unavailable; ")
                self.status.setText(status + ("notification refresh completed" if notification else "explicit read completed"))
            except Exception as error:  # noqa: BLE001 - contain backend errors at UI callbacks
                self.status.setText(f"Refresh failed: {error}")
            finally:
                self._reading = False

        def close(self):
            self.closed = True
            self._detach()
            self._close_with_child(self.browser)
            if self._close_complete:
                self.font = self.browser = None
                if self in _HANDLES:
                    _HANDLES.remove(self)

    return Explorer


def show(font: Any, parent: Any = None) -> Any:
    """Show a retained owned browser and report over one explicitly borrowed font."""
    from . import _construct

    owner = _construct(_panel_type(), font, parent)
    _HANDLES.append(owner)
    try:
        owner.widget.show()
    except BaseException:
        owner.close()
        raise
    return owner
