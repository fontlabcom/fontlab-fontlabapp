# this_file: src/fontlabapp/masters/layers/navigation/symbols.py
# SPDX-License-Identifier: Apache-2.0
"""Inspect exposed symbol state without reconstructing or serializing text.

Native DataCode values below UserAreaBegin are inspectable. Arbitrary private
user keys cannot be enumerated; full copy preserves them by construction, while
independent native oracles must qualify their retention and stale detection.
"""

from struct import pack
from typing import Any


def freeze(value: Any) -> Any:
    """Copy supported QVariant primitives into immutable comparison data."""
    if value is None:
        return ("None",)
    if type(value) is float:
        return ("float", pack(">d", value))
    if type(value) in (str, int, bool, bytes):
        return (type(value).__name__, value)
    if type(value) in (tuple, list):
        return (type(value).__name__, tuple(freeze(item) for item in value))
    if type(value) is dict:
        return (
            "dict",
            tuple(sorted((freeze(key), freeze(item)) for key, item in value.items())),
        )
    raise ValueError("Unsupported native symbol attribute value")


def symbol_token(symbol: Any, user_area: int) -> tuple:
    """Snapshot all exposed scalars and the complete native reserved data range."""
    fields = (
        symbol.id,
        symbol.pid,
        symbol.unicode,
        symbol.name,
        symbol.layerName,
        symbol.glyphIndex,
        symbol.ligatureIndex,
        symbol.cr,
        symbol.space,
    )
    data = tuple(
        (code, freeze(symbol.data(code)))
        for code in range(user_area)
        if symbol.containsData(code)
    )
    return tuple(freeze(value) for value in fields) + (data,)


def tokens(symbols: Any, user_area: int) -> tuple:
    """Retain original sequence order, separators and empty lines."""
    return tuple(symbol_token(symbol, user_area) for symbol in symbols)
