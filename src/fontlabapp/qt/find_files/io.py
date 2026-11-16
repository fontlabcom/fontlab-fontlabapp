# this_file: src/fontlabapp/qt/find_files/io.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only 64KiB search chunks and original rounded file-size facts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

CHUNK = 65536


@dataclass(frozen=True)
class Result:
    """An exact activation path and observed byte size; never an editable label."""

    path: Path
    size: int

    @property
    def size_kib(self) -> int:
        """Return the original part2 integer ceiling in units of1024bytes."""
        return (self.size + 1023) // 1024


def result(path: Path, *, strict: bool) -> Result:
    """Part2 skips stat failures; part3 QFileInfo's missing-size outcome is zero."""
    try:
        size = path.stat().st_size
    except OSError:
        if strict:
            raise
        size = 0
    return Result(path, size)


def read_chunk(stream: BinaryIO, query: str, tail: Any, decoder: Any) -> tuple:
    """Preserve UTF8 replacement decoding versus literal UTF8 byte matching."""
    chunk = stream.read(CHUNK)
    text = decoder.decode(chunk, final=not chunk) if decoder is not None else chunk
    needle = query if decoder is not None else query.encode("utf-8")
    combined = tail + text
    found = needle in combined
    carry = combined[-(len(needle) - 1) :] if len(needle) > 1 else combined[:0]
    return found, not chunk, carry
