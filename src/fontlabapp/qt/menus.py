# this_file: src/fontlabapp/qt/menus.py
"""Menu actions and tool windows that are safe to remove under signal dispatch.

What it does:
    ``OwnedMenus`` adds QActions to FontLab menus (or to one menu it owns)
    and shows widgets in tool windows. Each item gets an integer token.
    ``remove(token)`` and ``close()`` undo the items in a safe way.

Why:
    A menu callback or a window button often removes its own item. If the
    host disconnects or deletes the QAction or QWidget while its signal still
    dispatches, PythonQt deletes the signal receiver twice and FontLab crashes
    (AGENTS.md: disconnect before ``deleteLater``; never tear down in a slot).
    Every slot that this class connects counts a dispatch depth. While the
    depth is above zero, ``remove`` and ``close`` queue their work. One shared
    zero-delay ``DeferredBatch`` timer runs the queue after the outermost
    slot returns. Each queued item runs once.

How to use:
    ``menus = OwnedMenus(qt, fontlab, error_sink=sink)``
    ``token = menus.add_action("Edit", "My action", callback)``
    ``menus.remove(token)`` or ``menus.close()`` at unload.
    ``token, window = menus.tool_window(widget, "Title", on_close=done)``.

Rules:
    GUI thread only. ``qt`` is the ``PythonQt`` module and ``fontlab`` is the
    FontLab module; the caller passes both in. Callbacks take no arguments.
    Their errors go to ``error_sink(error, owner)`` and never reach Qt.
    ``QAction.text`` is a property in PythonQt, not a method.

Guard scope:
    The dispatch guard covers only the slots that this class connects: menu
    ``triggered`` and the tool-window close. A signal that the caller connects
    itself (for example a button in the tool window) does not raise the
    depth. If such a slot calls ``remove`` or ``close``, the teardown runs at
    once, inside that dispatch. Such a slot must queue its own call, for
    example with ``QTimer.singleShot(0, ...)``. Subclasses wrap their own
    slots with ``_slot`` (Glyport's plugin host does this for Apply/Cancel).

Cold import: stdlib plus ``fontlabapp.core.signals.deferred`` and ``fontlabapp.qt.safe``.
"""

from collections.abc import Callable
from itertools import count
from typing import Any, ClassVar

from fontlabapp.core.signals.deferred import DeferredBatch
from fontlabapp.qt.safe import main_window as find_main_window, qt_list

__all__ = ["OWNED_MENU_TITLE", "OwnedMenus"]

#: Default title of the one menu that ``OwnedMenus`` creates when needed.
OWNED_MENU_TITLE = "Plugins"


def _tool_window_class(base: type) -> type:
    """Return a ``base`` subclass whose title-bar close calls ``_on_close`` once."""

    class ToolWindow(base):  # type: ignore[misc, valid-type]
        _on_close: Callable[[], object] | None = None

        def closeEvent(self, event: Any) -> None:
            callback, self._on_close = self._on_close, None
            base.closeEvent(self, event)  # type: ignore[attr-defined]
            if callback is not None:
                callback()

    return ToolWindow


class OwnedMenus:
    """Own menu actions and tool windows; tear them down outside dispatch.

    The first ``add_action`` that finds no FontLab menu with the requested
    title creates one menu, titled ``owned_title``. ``close`` removes that menu.

    Attributes (read-only after construction):
        qt: the ``PythonQt`` module that was passed in.
        fl: the FontLab module that was passed in.
        sink: the ``error_sink`` callable.
        owned_title: title of the owned fallback menu.
    """

    # id(QtCore) -> (QtCore, batch). The QtCore reference pins the id.
    _batches: ClassVar[dict[int, tuple[Any, DeferredBatch["OwnedMenus"]]]] = {}

    def __init__(
        self,
        qt: Any,
        fontlab: Any,
        *,
        error_sink: Callable[[Exception, object], object],
        owned_title: str = OWNED_MENU_TITLE,
        main_window: Any = None,
    ) -> None:
        """Store the modules and the policy; create no Qt object yet.

        ``qt``: the ``PythonQt`` module. ``fontlab``: the FontLab module.
        ``error_sink(error, owner)``: receives every callback and teardown
        failure; it must not raise. ``owned_title``: title of the fallback
        menu. ``main_window``: an already known main window; ``None`` makes
        ``main_window()`` look it up on first use.
        """
        self.qt, self.fl, self.sink = qt, fontlab, error_sink
        self.owned_title = owned_title
        self._main = main_window
        self._ids = count(1)
        self._tokens: dict[int, Callable[[], None]] = {}
        self._actions: dict[int, Any] = {}
        self._menus: dict[int, Any] = {}  # add_menu token -> QMenu
        self._owned_menu: tuple[Any, Any] | None = None  # (QMenu, menubar QAction)
        self._pending: list[Callable[[], None]] = []
        self._window_class: type | None = None
        self._depth = 0  # above zero while one of our own slots runs
        self._widget_owner: dict[int, int] = {}  # id(widget) -> tool window token

    # --- public API -------------------------------------------------------------
    @property
    def has_items(self) -> bool:
        """Return True if this owner has an action or tool window to remove."""
        return bool(self._tokens)

    @property
    def dispatching(self) -> bool:
        """Return True while a slot connected by this owner runs."""
        return bool(self._depth)

    def add_action(
        self,
        menu_title: Any,
        text: str,
        callback: Callable[[], object],
        *,
        index: int | None = None,
        checkable: bool = False,
    ) -> int:
        """Add an action to the menu titled ``menu_title``; return its token.

        ``menu_title`` may also be a QMenu, such as one from ``menu(token)``.
        ``&`` in menu titles is ignored when matching. If no menu matches, the
        action goes to the owned menu. ``index`` inserts before that action
        position; an index outside the menu appends. ``callback()`` runs when
        the action triggers, inside the dispatch guard.
        """
        gui = self.qt.QtGui
        target = self._menu(menu_title) if isinstance(menu_title, str) else menu_title
        action = gui.QAction(text, target)
        if checkable:
            action.setCheckable(True)
        actions = qt_list(target.actions)
        if index is not None and 0 <= index < len(actions):
            target.insertAction(actions[index], action)
        else:
            target.addAction(action)

        @self._slot
        def triggered(*args: Any) -> None:
            self._guarded(action, callback)

        action.triggered.connect(triggered)

        def undo() -> None:
            action.triggered.disconnect(triggered)
            target.removeAction(action)
            action.deleteLater()

        token = self._token(undo)
        self._actions[token] = action
        return token

    def action(self, token: int) -> Any:
        """Return the live QAction of ``token``, or ``None`` once removed."""
        return self._actions.get(token)

    def add_menu(self, menu_title: str, text: str) -> int:
        """Append a submenu titled ``text`` to ``menu_title``; return its token.

        ``menu(token)`` returns the QMenu; pass it to ``add_action``. Removing
        the submenu removes its owned actions before deleting their Qt parent.
        """
        parent = self._menu(menu_title)
        submenu = self.qt.QtGui.QMenu(text)
        entry = parent.addMenu(submenu)

        def undo() -> None:
            children = qt_list(submenu.actions)
            for child_token, action in reversed(tuple(self._actions.items())):
                if action in children:
                    self.remove(child_token)
            parent.removeAction(entry)
            submenu.deleteLater()

        token = self._token(undo)
        self._menus[token] = submenu
        return token

    def menu(self, token: int) -> Any:
        """Return the live QMenu of an ``add_menu`` token, or ``None`` once removed."""
        return self._menus.get(token)

    def tool_window(
        self,
        widget: Any,
        title: str,
        *,
        on_close: Callable[[], object] | None = None,
    ) -> tuple[int, Any]:
        """Show ``widget`` in a tool window; return ``(token, window)``.

        ``on_close()`` runs once when the title-bar close or ``remove(token)``
        ends the window. Widget and window teardown wait for the event loop.
        The widget is detached first, so the caller keeps it. The caller may
        resize ``window`` after this call.
        """
        gui, core = self.qt.QtGui, self.qt.QtCore
        if self._window_class is None:
            self._window_class = _tool_window_class(gui.QWidget)
        window = self._window_class()
        window.setWindowFlags(core.Qt.Tool | core.Qt.WindowStaysOnTopHint)
        window.setWindowTitle(str(title))
        widget.setParent(window)
        widget.move(0, 0)
        widget.show()
        closed = [False]

        def teardown() -> None:
            window._on_close = None
            if self._widget_owner.get(id(widget)) == token:  # not reopened meanwhile
                del self._widget_owner[id(widget)]
                widget.setParent(None)  # the caller keeps its widget
                widget.hide()
            window.close()
            window.deleteLater()

        def finish() -> None:
            if closed[0]:
                return
            closed[0] = True
            self._tokens.pop(token, None)
            window.hide()
            self._defer(teardown)
            if on_close is not None:
                self._guarded(window, on_close)

        window._on_close = self._slot(finish)
        token = self._token(finish)
        self._widget_owner[id(widget)] = token
        window.show()
        return token, window

    def remove(self, token: int) -> None:
        """Undo one item; unknown or repeated tokens do nothing.

        Inside one of our slots the removal is queued and runs once later.
        """
        if self._depth:
            self._defer(lambda: self.remove(token))
            return
        undo = self._tokens.pop(token, None)
        self._actions.pop(token, None)
        self._menus.pop(token, None)
        if undo is not None:
            undo()

    def close(self) -> None:
        """Remove every item newest first, run queued teardown, drop the menu.

        Every item is tried. The first failure is re-raised at the end. Inside
        one of our slots the whole call is queued instead.
        """
        if self._depth:
            self._defer(self.close)
            return
        failures: list[Exception] = []
        for token in sorted(self._tokens, reverse=True):
            try:
                self.remove(token)
            except Exception as error:  # noqa: BLE001 - re-raised below
                failures.append(error)
        try:
            self._reap()
        except Exception as error:  # noqa: BLE001
            failures.append(error)
        if self._owned_menu is not None:
            menu, action = self._owned_menu
            self._owned_menu = None
            try:
                self._menubar().removeAction(action)
                menu.deleteLater()
            except Exception as error:  # noqa: BLE001
                failures.append(error)
        if failures:
            raise failures[0]

    def main_window(self) -> Any:
        """Return FontLab's main window (cached); see ``qtsafe.main_window``.

        Raises ``qtsafe.MainWindowNotFound`` (a ``RuntimeError``) if the
        window does not exist. Nothing is cached then; the next call retries.
        """
        if self._main is None:
            self._main = find_main_window(self.fl, self.qt)
        return self._main

    # --- internals --------------------------------------------------------------
    def _token(self, undo: Callable[[], None]) -> int:
        """Register ``undo`` under a new token and return the token.

        ``remove(token)`` runs ``undo`` once. Subclasses use this for their
        own items, so ``close`` removes them in the same newest-first pass.
        """
        token = next(self._ids)
        self._tokens[token] = undo
        return token

    @classmethod
    def _batch(cls, qt: Any) -> DeferredBatch["OwnedMenus"]:
        """Return the one retained batch per Qt namespace (never torn down)."""
        key = id(qt.QtCore)
        if key not in cls._batches:
            batch = DeferredBatch(qt, lambda owner: owner._reap())
            cls._batches[key] = (qt.QtCore, batch)
        return cls._batches[key][1]

    @property
    def _reaper(self) -> Any:
        """The shared batch's QTimer.

        Test seam: offline tests fire this timer to stand in for the event
        loop; Glyport's host tests read it too. ``OwnedMenus`` itself schedules
        through ``_batch``, never through this property.
        """
        return self._batch(self.qt).timer

    def _slot(self, function: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a slot connected to our widgets; it counts the dispatch depth."""

        def run(*args: Any) -> Any:
            self._depth += 1
            try:
                return function(*args)
            finally:
                self._depth -= 1
                if not self._depth and self._pending:
                    self._batch(self.qt).schedule(self)  # one drain after the slot

        return run

    def _defer(self, teardown: Callable[[], None], *, first: bool = False) -> None:
        """Queue ``teardown`` for the event loop, after the current dispatch.

        Subclass seam. ``first=True`` inserts ``teardown`` at index 0 of
        ``_pending``, so it runs before the work that waits there now. Use it
        when a release must run before App's own teardown, for example:
        disconnect the buttons that a subclass added to a tool window before
        App closes and deletes that window.

        Limit: a drain (``_reap``) takes the whole list before it runs it. A
        call made by teardown during a drain goes to the new list, so it runs
        after the rest of the batch that is running, never before it. The
        queue stays a plain list in ``_pending``.
        """
        if first:
            self._pending.insert(0, teardown)
        else:
            self._pending.append(teardown)
        if not self._depth:
            self._batch(self.qt).schedule(self)

    def _reap(self) -> None:
        """Run queued teardown once each, never while one of our slots runs.

        A nested event-loop tick inside a slot leaves the queue untouched.
        Work queued by teardown itself runs in the same drain.
        """
        while self._pending and not self._depth:
            pending, self._pending = self._pending, []
            for teardown in pending:
                self._guarded(self, teardown)

    def _guarded(self, owner: object, function: Callable[..., Any], *args: Any) -> None:
        """Call ``function(*args)``; send an ``Exception`` to the sink as ``owner``.

        Used for every callback and queued teardown, so no error reaches Qt.
        ``BaseException`` (``KeyboardInterrupt``, ``SystemExit``) still passes.
        """
        try:
            function(*args)
        except Exception as error:  # noqa: BLE001 - never raise into a Qt slot
            self.sink(error, owner)

    def _menubar(self) -> Any:
        """Return the main window's ``QMenuBar`` (looked up through ``main_window``)."""
        return self.main_window().menuBar()

    def _menu(self, title: str) -> Any:
        """Return the FontLab menu titled ``title`` (``&`` ignored), else ours."""
        wanted = title.replace("&", "")
        for action in qt_list(self._menubar().actions):
            if action.text.replace("&", "") == wanted and action.menu() is not None:
                return action.menu()
        return self.own_menu()

    def own_menu(self) -> Any:
        """Return this owner's own menu, creating it on first use.

        The lookup never consults other menus, so a FontLab or another host's
        menu with the same title as ``owned_title`` is not shared. Pass the
        result to ``add_action``.
        """
        if self._owned_menu is None:
            menu = self.qt.QtGui.QMenu(self.owned_title)
            self._owned_menu = (menu, self._menubar().addMenu(menu))
        return self._owned_menu[0]
