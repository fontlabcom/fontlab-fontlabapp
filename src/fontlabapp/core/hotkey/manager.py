#!/usr/bin/env python3
# this_file: src/fontlabapp/core/hotkey/manager.py
# -*- coding: utf-8 -*-

from typing import Any
from fontlabapp import app


class HotkeyManager:
    KEY_NAMES = [
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "F6",
        "F7",
        "F8",
        "F9",
        "F10",
        "F11",
        "F12",
        "`",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "-",
        "=",
        "Q",
        "W",
        "E",
        "R",
        "T",
        "Y",
        "U",
        "I",
        "O",
        "P",
        "[",
        "]",
        "\\",
        "A",
        "S",
        "D",
        "F",
        "G",
        "H",
        "J",
        "K",
        "L",
        ";",
        "'",
        "Z",
        "X",
        "C",
        "V",
        "B",
        "N",
        "M",
        ",",
        ".",
        "/",
        "Space",
        "Backspace",
        "Tab",
        "Enter",
        "Esc",
        "Delete",
        "Up",
        "Down",
        "Left",
        "Right",
        "PageUp",
        "PageDown",
        "Home",
        "End",
    ]

    def __init__(self) -> None:
        self._handlers_key_down = {key: [] for key in self.KEY_NAMES}
        self._handlers_key_up = {key: [] for key in self.KEY_NAMES}
        super(HotkeyManager, self).__init__()
        app.qapp.aboutToQuit.connect(self.stop)

    def on(self, event: Any, on_key_down: Any, on_key_up: Any = None) -> Any:
        self._handlers_key_down[event].append(on_key_down)
        if on_key_up:
            self._handlers_key_up[event].append(on_key_up)

    def run(self) -> Any:
        pass

    def stop(self) -> Any:
        pass
