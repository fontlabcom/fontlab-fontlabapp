#!/usr/bin/env python3
# this_file: src/fontlabapp/core/hotkey/mac.py
# -*- coding: utf-8 -*-

from typing import Any
import Quartz
from fontlabapp.core.hotkey import manager

txt_permissions = """
1. Quit FontLab.
2. Open 'System Preferences > Security & Privacy > Privacy'.
3. Click the lock to make changes and enter your password.
4. Click 'Accessibility'.
5. If 'FontLab 8.app' is there, select it and click the minus button.
6. Open FontLab and run this code again.
7. When the dialog 'Accessibility Access' appears, click 'Open System Preferences'.
8. 'FontLab 8.app' should be there. Turn on the checkbox next to it.
"""

class HotkeyManager(manager.HotkeyManager):
    KEY_CODES = {
        122: "F1",
        120: "F2",
        99: "F3",
        118: "F4",
        96: "F5",
        97: "F6",
        98: "F7",
        100: "F8",
        101: "F9",
        109: "F10",
        103: "F11",
        111: "F12",
        50: "`",
        29: "0",
        18: "1",
        19: "2",
        20: "3",
        21: "4",
        23: "5",
        22: "6",
        26: "7",
        28: "8",
        25: "9",
        27: "-",
        24: "=",
        12: "Q",
        13: "W",
        14: "E",
        15: "R",
        17: "T",
        16: "Y",
        32: "U",
        34: "I",
        31: "O",
        35: "P",
        33: "[",
        30: "]",
        42: "\\",
        0: "A",
        1: "S",
        2: "D",
        3: "F",
        5: "G",
        4: "H",
        38: "J",
        40: "K",
        37: "L",
        41: ";",
        39: "'",
        6: "Z",
        7: "X",
        8: "C",
        9: "V",
        11: "B",
        45: "N",
        46: "M",
        43: ",",
        47: ".",
        44: "/",
        49: "Space",
        51: "Backspace",
        48: "Tab",
        36: "Enter",
        53: "Esc",
        117: "Delete",
        126: "Up",
        125: "Down",
        123: "Left",
        124: "Right",
        116: "PageUp",
        121: "PageDown",
        115: "Home",
        119: "End",
    }

    def __init__(self) -> None:
        self._tap = None
        self.loop_ref = None
        self.loop_source = None
        super(HotkeyManager, self).__init__()

    def run(self) -> Any:
        if self._tap is not None:
            raise RuntimeError("Hotkey event tap is already running")
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
            | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
            self._handle_event_tap,
            None,
        )
        if self._tap is None:
            raise RuntimeError(txt_permissions)
        self.loop_source = Quartz.CFMachPortCreateRunLoopSource(
            Quartz.kCFAllocatorDefault, self._tap, 0
        )
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            self.loop_source,
            Quartz.kCFRunLoopCommonModes,
        )

        self.loop_ref = Quartz.CFRunLoopGetCurrent()

        Quartz.CGEventTapEnable(self._tap, True)
        try:
            Quartz.CFRunLoopRun()  # Only returns after stop() is called.
        finally:
            self.stop()

    def stop(self) -> Any:
        if self.loop_ref is None:
            return
        Quartz.CFRunLoopStop(self.loop_ref)
        Quartz.CFMachPortInvalidate(self._tap)
        Quartz.CFRunLoopRemoveSource(self.loop_ref, self.loop_source, Quartz.kCFRunLoopCommonModes)
        self.loop_ref = None
        self.loop_source = None
        self._tap = None

    def _handle_event_tap(self, proxy: Any, cg_event_type: Any, cg_event: Any, refcon: Any) -> Any:
        # re-enable the tap on timeout
        if cg_event_type == Quartz.kCGEventTapDisabledByTimeout:
            Quartz.CGEventTapEnable(self._tap, True)
            return cg_event
        if not self._handle_event(cg_event, cg_event_type):
            return cg_event

    def _handle_event(self, event: Any, cg_event_type: Any) -> Any:

        code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        flags = Quartz.CGEventGetFlags(event)
        alt = True if flags & Quartz.kCGEventFlagMaskAlternate else False
        cmd = True if flags & Quartz.kCGEventFlagMaskCommand else False
        ctrl = True if flags & Quartz.kCGEventFlagMaskControl else False
        shift = True if flags & Quartz.kCGEventFlagMaskShift else False

        if cg_event_type == Quartz.kCGEventKeyDown and code in self.KEY_CODES:
            for handler in self._handlers_key_down[self.KEY_CODES[code]]:
                if handler() == False:
                    return True

        elif cg_event_type == Quartz.kCGEventKeyUp and code in self.KEY_CODES:
            for handler in self._handlers_key_up[self.KEY_CODES[code]]:
                if handler() == False:
                    return True
