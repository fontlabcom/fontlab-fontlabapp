#!/usr/bin/env python3
# this_file: src/fontlabapp/core/utils/merge.py
# -*- coding: utf-8 -*-
# Source: https://github.com/clarketm/mergedeep/
# Copyright (c) 2019 Travis Clarke <travis.m.clarke@gmail.com> (https://www.travismclarke.com/)
# License: The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from typing import Any
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from enum import Enum
from functools import reduce, partial
from typing import MutableMapping


class Strategy(Enum):
    # Replace `destination` item with one from `source` (default).
    REPLACE = 0
    # Combine `list`, `tuple`, `set`, or `Counter` types into one collection.
    ADDITIVE = 1
    # Alias to: `TYPESAFE_REPLACE`
    TYPESAFE = 2
    # Raise `TypeError` when `destination` and `source` types differ. Otherwise, perform a `REPLACE` merge.
    TYPESAFE_REPLACE = 3
    # Raise `TypeError` when `destination` and `source` types differ. Otherwise, perform a `ADDITIVE` merge.
    TYPESAFE_ADDITIVE = 4


def _handle_merge_replace(destination: Any, source: Any, key: Any) -> Any:
    if isinstance(destination[key], Counter) and isinstance(source[key], Counter):
        # Merge both destination and source `Counter` as if they were a standard dict.
        _deepmerge(destination[key], source[key])
    else:
        # If a key exists in both objects and the values are `different`, the value from the `source` object will be used.
        destination[key] = deepcopy(source[key])


def _handle_merge_additive(destination: Any, source: Any, key: Any) -> Any:
    # Values are combined into one long collection.
    if isinstance(destination[key], list) and isinstance(source[key], list):
        # Extend destination if both destination and source are `list` type.
        destination[key].extend(deepcopy(source[key]))
    elif isinstance(destination[key], set) and isinstance(source[key], set):
        # Update destination if both destination and source are `set` type.
        destination[key].update(deepcopy(source[key]))
    elif isinstance(destination[key], tuple) and isinstance(source[key], tuple):
        # Update destination if both destination and source are `tuple` type.
        destination[key] = destination[key] + deepcopy(source[key])
    elif isinstance(destination[key], Counter) and isinstance(source[key], Counter):
        # Update destination if both destination and source are `Counter` type.
        destination[key].update(deepcopy(source[key]))
    else:
        _handle_merge[Strategy.REPLACE](destination, source, key)


def _handle_merge_typesafe(destination: Any, source: Any, key: Any, strategy: Any) -> Any:
    # Raise a TypeError if the destination and source types differ.
    if type(destination[key]) is not type(source[key]):
        raise TypeError(
            f'destination type: {type(destination[key])} differs from source type: {type(source[key])} for key: "{key}"'
        )
    else:
        _handle_merge[strategy](destination, source, key)


_handle_merge = {
    Strategy.REPLACE: _handle_merge_replace,
    Strategy.ADDITIVE: _handle_merge_additive,
    Strategy.TYPESAFE: partial(_handle_merge_typesafe, strategy=Strategy.REPLACE),
    Strategy.TYPESAFE_REPLACE: partial(_handle_merge_typesafe, strategy=Strategy.REPLACE),
    Strategy.TYPESAFE_ADDITIVE: partial(_handle_merge_typesafe, strategy=Strategy.ADDITIVE),
}


def _is_recursive_merge(a: Any, b: Any) -> Any:
    both_mapping = isinstance(a, Mapping) and isinstance(b, Mapping)
    both_counter = isinstance(a, Counter) and isinstance(b, Counter)
    return both_mapping and not both_counter


def _deepmerge(dst: Any, src: Any, strategy: Any=Strategy.REPLACE) -> Any:
    for key in src:
        if key in dst:
            if _is_recursive_merge(dst[key], src[key]):
                # If the key for both `dst` and `src` are both Mapping types (e.g. dict), then recurse.
                _deepmerge(dst[key], src[key], strategy)
            elif dst[key] is src[key]:
                # If a key exists in both objects and the values are `same`, the value from the `dst` object will be used.
                pass
            else:
                _handle_merge.get(strategy)(dst, src, key)
        else:
            # If the key exists only in `src`, the value from the `src` object will be used.
            dst[key] = deepcopy(src[key])
    return dst


def deepmerge(destination: MutableMapping, *sources: Mapping, strategy: Strategy = Strategy.REPLACE) -> MutableMapping:
    """
    A deep merge function for 🐍.

    :param destination: The destination mapping.
    :param sources: The source mappings.
    :param strategy: The merge strategy.
    :return:
    """
    return reduce(partial(_deepmerge, strategy=strategy), sources, destination)
