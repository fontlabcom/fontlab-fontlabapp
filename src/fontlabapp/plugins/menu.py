# this_file: src/fontlabapp/plugins/menu.py
"""Install checkable reporter actions in a View > Reporters submenu."""

from typing import Any

_SUBMENU = "Reporters"
_HIDE_ALL = "Hide All"


def install(owner: Any, registry: Any) -> dict[str, int]:
    """Add View > Reporters with one owned QAction per reporter, then Hide All.

    Returns the reporter action tokens keyed by reporter name.
    """
    submenu = owner.menu(owner.add_menu("View", _SUBMENU))
    tokens = {}

    def populate():
        reporters = registry.available("reporter").items()
        for name, cls in sorted(reporters, key=lambda item: _label(item[1].title)):
            if name in tokens:
                continue
            token = owner.add_action(
                submenu, _label(cls.title),
                lambda name=name: _toggle(owner, registry, tokens[name], name),
                checkable=True,
            )
            tokens[name] = token

    def sync():
        # shortcut: rescan appends new actions after Hide All; restart restores sorting.
        # Never delete QActions during a plugin callback; OwnedMenus owns teardown.
        populate()
        for name, token in tokens.items():
            action = owner.action(token)
            if action is not None:
                action.setChecked(name in registry.enabled())

    populate()
    submenu.addSeparator()
    owner.add_action(submenu, _HIDE_ALL, lambda: _hide_all(owner, registry, tokens))
    sync()
    registry.listeners.append(sync)
    return tokens


def _label(title: str) -> str:
    """Drop a leading "Show " so entries read as reporter names."""
    return title.removeprefix("Show ")


def _toggle(owner: Any, registry: Any, token: int, name: str) -> None:
    """Restore QAction state if activation or persistence fails."""
    action = owner.action(token)
    try:
        registry.toggle(name)
    finally:
        if action is not None:
            action.setChecked(name in registry.enabled())


def _hide_all(owner: Any, registry: Any, tokens: dict[str, int]) -> None:
    """Disable every enabled reporter; keep checkmarks true even if one fails."""
    try:
        for name in registry.enabled():
            if name in tokens:
                registry.disable(name)
    finally:
        enabled = set(registry.enabled())
        for name, token in tokens.items():
            action = owner.action(token)
            if action is not None:
                action.setChecked(name in enabled)
