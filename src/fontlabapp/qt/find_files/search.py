# this_file: src/fontlabapp/qt/find_files/search.py
# SPDX-License-Identifier: Apache-2.0
"""Two complete one-directory search profiles with explicit stream ownership.

The decoded profile follows file symlinks and publishes progressively. The byte
profile excludes symlinks and publishes only after completion. Candidate
collection is stepped too; Path.iterdir retains its ordinary name-snapshot order.
"""

import codecs
import fnmatch
import os
from collections import deque
from pathlib import Path
from typing import Any, BinaryIO, Literal

from fontlabapp.qt.find_files.io import Result, read_chunk, result

Profile = Literal["text", "bytes"]
TURN = 32


class Search:
    """Own one read-only query; each step scans32entries OR reads one64KiBchunk."""

    def __init__(
        self, directory: Path, pattern: str, needle: str, profile: Profile
    ) -> None:
        """Capture directory/text; only part2 may receive a later live glob."""
        if profile not in ("text", "bytes"):
            raise ValueError("Unknown Find Files profile")
        self.directory, self.pattern, self.needle, self.profile = (
            Path(directory),
            pattern,
            needle,
            profile,
        )
        self.entries: Any = None
        self.stream: BinaryIO | None = None
        self.decoder: Any = None
        self.tail: Any = "" if profile == "text" else b""
        self.path: Path | None = None
        self.pending: deque[Path] = deque()
        self.found: list[Path] = []
        self.results: list[Result] = []
        self.active, self.finished, self.cancelled = True, False, False
        self.collecting = profile == "bytes"
        self.history_ready = False
        self.scanned = self.total = self.processed = 0
        self.error = ""
        try:
            self.entries = (
                os.scandir(self.directory)
                if profile == "text"
                else self.directory.iterdir()
            )
        except OSError as error:
            self._fail(error)

    def _close_stream(self) -> None:
        """Release a stream even if closing it reports an OS failure."""
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.close()
            except OSError as error:
                self.error = str(error)

    def _close_entries(self) -> None:
        """Release scandir or the Path generator exactly once."""
        entries, self.entries = self.entries, None
        if entries is not None:
            try:
                entries.close()
            except OSError as error:
                self.error = str(error)

    def cancel(self) -> None:
        """Stop immediately, close resources and keep only already visible rows."""
        self.active = False
        self.cancelled = True
        self.pending.clear()
        self._close_stream()
        self._close_entries()

    def _fail(self, error: OSError) -> None:
        """Stop directory failures; never loop forever on a broken iterator."""
        self.cancel()
        self.cancelled = False
        self.error = str(error)

    def _finish(self) -> None:
        """Publish byte-profile rows only after the entire search finishes."""
        if self.profile == "bytes":
            self.results = [result(path, strict=False) for path in self.found]
        self.active = False
        self.finished = True
        self._close_stream()
        self._close_entries()

    def _next(self, pattern: str) -> Path | None:
        """Keep native directory order, profile symlinks and bounded candidate turns."""
        for _ in range(TURN):
            try:
                entry = next(self.entries)
            except StopIteration:
                self._close_entries()
                if self.collecting:
                    self.collecting = False
                    self.total = len(self.pending)
                    self.history_ready = True
                else:
                    self._finish()
                return None
            except OSError as error:
                self._fail(error)
                return None
            self.scanned += 1
            path = Path(entry.path) if self.profile == "text" else entry
            try:
                valid = entry.is_file() and (
                    self.profile == "text" or not path.is_symlink()
                )
            except OSError as error:
                if self.collecting:
                    self._fail(error)
                else:
                    self.error = str(error)
                return None
            if valid and fnmatch.fnmatch(path.name, pattern):
                if self.collecting:
                    self.pending.append(path)
                else:
                    return path
        return None

    def _record(self, path: Path) -> None:
        """Retain exact activation paths independently of part2 editable table cells."""
        if self.profile == "text":
            self.results.append(result(path, strict=True))
        self.found.append(path)

    def step(self, pattern: str | None = None) -> None:
        """Advance one GUI turn without any event pumping or file-content execution."""
        if not self.active:
            return
        glob = (
            (self.pattern or "*")
            if self.profile == "bytes"
            else self.pattern
            if pattern is None
            else pattern
        )
        if self.collecting:
            self._next(glob)
            return
        try:
            if self.stream is None:
                if self.profile == "bytes":
                    if not self.pending:
                        self._finish()
                        return
                    self.path = self.pending.popleft()
                    self.processed += 1
                else:
                    self.path = self._next(glob)
                    if self.path is None:
                        return
                if not self.needle:
                    self._record(self.path)
                    return
                self.stream = self.path.open("rb")
                self.decoder = (
                    codecs.getincrementaldecoder("utf-8")("replace")
                    if self.profile == "text"
                    else None
                )
                self.tail = "" if self.profile == "text" else b""
            found, end, self.tail = read_chunk(
                self.stream, self.needle, self.tail, self.decoder
            )
            if not self.active:
                return
            if found or end:
                self._close_stream()
                if found:
                    self._record(self.path)
        except OSError as error:
            self.error = str(error)
            self._close_stream()
