# this_file: src/fontlabapp/studios/hint_tools/session.py
# SPDX-License-Identifier: Apache-2.0
"""Captured font and accepted hint plan; writers retain their own history step."""
from typing import Any, Callable

import fontlabapp.core.history.glyphs as history
from fontlabapp.studios.transform_studio.native import snapshot

from . import autohint, removal


class Session:
    """Refuse changed target, options or geometry between Preview and Apply."""

    def __init__(self, package: Callable[[], Any], selection: Callable[[], list[str]]) -> None:
        self.provider, self.selection = package, selection
        self.bound = package()
        if self.bound is None:
            raise ValueError('Open a font first.')
        self.bound_id = self.bound.id
        self.names = list(selection())
        self.master = str(self.bound.master)
        self.accepted = None
        self.rows = []

    def package(self) -> Any:
        package = self.provider()
        if package is None or package.id != self.bound_id:
            raise ValueError('The font changed. Reopen Hint Tools.')
        return package

    def refresh(self) -> None:
        self.package()
        self.names = list(self.selection())
        self.accepted = None
        self.rows = []

    def capture(self, mode: str, all_masters: bool, bases: bool, horizontal: bool, vertical: bool) -> tuple:
        package = self.package()
        if not self.names:
            raise ValueError('Select glyphs and Refresh first.')
        masters = list(package.masters) if all_masters else [self.master]
        facts = history.scan_auto_facts(package)
        if mode == 'autohint':
            rows = autohint.survey(package, self.names, masters, facts, bases)
        elif mode == 'remove':
            rows = removal.survey(package, self.names, masters, facts, bases, horizontal, vertical)
        else:
            raise ValueError('Unknown hint action.')
        token = (mode, all_masters, bases, horizontal, vertical, tuple(self.names), tuple(masters),
                 tuple((str(r.glyph.name), r.master, r.layer, r.before, r.note,
                        snapshot(r.layer) if not r.note else None) for r in rows))
        return rows, facts, token

    def preview(self, *options: Any) -> list:
        self.accepted = None
        self.rows, _, self.accepted = self.capture(*options)
        return self.rows

    def apply(self, mode: str, all_masters: bool, bases: bool, horizontal: bool, vertical: bool) -> dict:
        if self.accepted is None:
            raise ValueError('Preview Changes before applying.')
        rows, facts, token = self.capture(mode, all_masters, bases, horizontal, vertical)
        accepted, self.accepted = self.accepted, None
        if token != accepted:
            raise ValueError('Targets or options changed. Preview Changes again.')
        if mode == 'autohint':
            return autohint.autohint(rows, facts, bases)
        return removal.remove_hints(rows, horizontal, vertical, facts, bases)
