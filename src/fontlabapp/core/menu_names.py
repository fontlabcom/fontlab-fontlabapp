# this_file: src/fontlabapp/core/menu_names.py
"""Stable Python names for FontLab's English menu labels (host-free).

Shared by the live tree (``fontlabapp.core.host``) and the static shim generator
(``fontlabapp.core.shimgen``), so both derive identical names from the same labels.
"""

from __future__ import annotations

import keyword
import re
import unicodedata
from collections.abc import Iterable, Sequence

_NON_WORD = re.compile(r"[^0-9a-z]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_ELLIPSIS = re.compile(r"(\.\.\.|…)\s*$")


def clean_label(text: str) -> str:
    """Human label: drop shortcut suffix, mnemonic ``&`` (``&&`` is ``&``), ellipsis."""
    text = text.split("\t", 1)[0]
    text = text.replace("&&", "\0").replace("&", "").replace("\0", "&")
    return _ELLIPSIS.sub("", text.strip()).strip()


def _identifier(words: str) -> str:
    words = unicodedata.normalize("NFKD", words).encode("ascii", "ignore").decode()
    name = _NON_WORD.sub("_", words.lower().replace("'", "")).strip("_")
    if name[:1].isdigit():
        name = "n" + name
    if keyword.iskeyword(name) or keyword.issoftkeyword(name):
        name += "_"
    return name


def snake(label: str) -> str:
    """snake_case identifier for a menu label; ``&`` reads as ``and``."""
    return _identifier(clean_label(label).replace("&", " and "))


def object_slug(object_name: str) -> str:
    """snake_case of a Qt objectName without its ``action``/``menu`` prefix."""
    name = re.sub(r"^(action|menu)(?=[A-Z_])", "", object_name)
    return _identifier(_CAMEL.sub("_", name))


def assign_names(
    entries: Sequence[tuple[str, str, bool]], reserved: Iterable[str] = ()
) -> list[str]:
    """Unique sibling names for ``(label, objectName, visible)`` entries.

    Names follow action identity, never visibility or menu position: among
    siblings whose labels give the same name, the one whose objectName slug
    *is* that name keeps it, else the smallest objectName, else the first
    entry without one. The others take their objectName slug, or a numbered
    suffix when that is empty or taken. Reserved names (the node's own API)
    get a trailing underscore. ``visible`` is accepted for callers but unused.
    """
    reserved = set(reserved)
    bases = [snake(label) or object_slug(obj) or "item" for label, obj, _ in entries]
    bases = [base + "_" if base in reserved else base for base in bases]

    def rank(i: int) -> tuple:
        obj = entries[i][1]
        return (object_slug(obj) != bases[i].rstrip("_"), not obj, obj, i)

    order = sorted(range(len(entries)), key=rank)
    names: list[str | None] = [None] * len(entries)
    used: set[str] = set()
    for i in order:
        if bases[i] not in used:
            names[i] = bases[i]
            used.add(bases[i])
    taken = set(bases) | reserved
    for i in order:
        if names[i] is not None:
            continue
        candidate = object_slug(entries[i][1])
        if not candidate or candidate in used or candidate in taken:
            n = 2
            while f"{bases[i]}_{n}" in used or f"{bases[i]}_{n}" in taken:
                n += 1
            candidate = f"{bases[i]}_{n}"
        names[i] = candidate
        used.add(candidate)
    return names  # type: ignore[return-value]
