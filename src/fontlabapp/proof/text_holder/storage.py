# this_file: src/fontlabapp/proof/text_holder/storage.py
# SPDX-License-Identifier: Apache-2.0
"""Plain UTF8 text recovery and tool-only size, with injected owned paths."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def default_path(qt: Any) -> Path:
    """Resolve Qt application storage without constructing App or changing prefs."""
    paths = qt.QtCore.QStandardPaths
    root = paths.writableLocation(paths.AppDataLocation)
    if not root:
        raise OSError("FontLab application data location is unavailable.")
    return Path(root) / "Text holder.txt"


def _write(path: Path, text: str) -> None:
    """Replace a complete file after successful UTF8 encoding and temp write."""
    if not isinstance(text, str):
        raise TypeError("Text Holder content must be text.")
    text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix="." + path.name + ".",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _size(size: Any) -> tuple[int, int]:
    if (
        not isinstance(size, (list, tuple))
        or len(size) != 2
        or any(type(v) is not int for v in size)
        or not (500 <= size[0] <= 1200 and 400 <= size[1] <= 800)
    ):
        raise ValueError("Text Holder window size must be within 500×400 and 1200×800.")
    return tuple(size)


class TextStore:
    """Never access a path until explicitly loading or saving this tool."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.window_path = self.path.with_suffix(".window.json")

    def load(self) -> str:
        """Recover saved content; missing means empty, corrupt/unreadable raises."""
        try:
            return self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def save(self, text: str) -> None:
        """Publish complete text; failed replacement preserves the previous file."""
        _write(self.path, text)

    def size(self) -> tuple[int, int] | None:
        """Recover only this tool decorated frame size; never read global settings."""
        try:
            return _size(json.loads(self.window_path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return None

    def save_size(self, size: tuple[int, int]) -> None:
        """Keep source decorated frame resizing across sessions without saving draft text."""
        _write(self.window_path, json.dumps(_size(size)))
