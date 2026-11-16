#!/usr/bin/env python3
# this_file: src/fontlabapp/core/utils/collections.py
# -*- coding: utf-8 -*-
# Source: https://github.com/kateliev/vfjLib/
# Copyright (c) 2019, Vassil Kateliev.
# License: BSD 3-Clause License
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import absolute_import, unicode_literals, print_function
from typing import Any
from collections import defaultdict

__version__ = "0.2.1"

# - Objects ------------------------------------------
class dictextractor:
    """A collection of dicionary value extractors"""

    @staticmethod
    def extract(obj: Any, search: Any) -> Any:
        """Pull all values of specified key (search)

        Attributes:
                search (Str): Search string

        Returns:
                generator
        """

        def extract_helper(obj: Any, search: Any) -> Any:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == search:
                        yield value
                    else:
                        if isinstance(value, (dict, list)):
                            for result in extract_helper(value, search):
                                yield result

            elif isinstance(obj, list):
                for item in obj:
                    for result in extract_helper(item, search):
                        yield result

        return extract_helper(obj, search)

    @staticmethod
    def find(obj: Any, search: Any, search_type: Any=None) -> Any:
        """Pull all objects that contain keys of specified search.

        Attributes:
                search (Str): Search string
                search_type (type) : Value type
        Returns:
                generator
        """

        def isisntance_plus(entity: Any, test_type: Any) -> Any:
            if test_type is not None:
                return isinstance(entity, test_type)
            else:
                return True

        def where_helper(obj: Any, search: Any) -> Any:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == search and isisntance_plus(value, search_type):
                        yield obj
                    else:
                        if isinstance(value, (dict, list)):
                            for result in where_helper(value, search):
                                yield result

            elif isinstance(obj, list):
                for item in obj:
                    for result in where_helper(item, search):
                        yield result

        return where_helper(obj, search)

    @staticmethod
    def where(obj: Any, search_value: Any, search_key: Any=None) -> Any:
        """Pull all objects that contain values of specified search.

        Attributes:
                search_value (Str): Search value
                search_key (Str) : Search for specific key that contains above value
        Returns:
                generator
        """

        def eq_plus(test: Any, pass_test: Any) -> Any:
            if pass_test is not None:
                return test
            else:
                return True

        def where_helper(obj: Any, search_value: Any) -> Any:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if value == search_value and eq_plus(key == search_key, search_key):
                        yield obj
                    else:
                        if isinstance(value, (dict, list)):
                            for result in where_helper(value, search_value):
                                yield result

            elif isinstance(obj, list):
                for item in obj:
                    for result in where_helper(item, search_value):
                        yield result

        return where_helper(obj, search_value)

    @staticmethod
    def contains(obj: Any, search: Any, search_type: Any=None) -> Any:
        """Does the object contain ANY value or nested object with given name (search)

        Attributes:
                search (Str): Search string
                search_type (type) : Value type

        Returns:
                Bool
        """

        def isisntance_plus(entity: Any, test_type: Any) -> Any:
            if test_type is not None:
                return isinstance(entity, test_type)
            else:
                return True

        def contains_helper(obj: Any, search: Any) -> Any:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if search in key and isisntance_plus(value, search_type):
                        yield True
                    else:
                        if isinstance(value, (dict, list)):
                            for result in contains_helper(value, search):
                                yield result

            elif isinstance(obj, list):
                for item in obj:
                    for result in contains_helper(item, search):
                        yield result

        return any(list(contains_helper(obj, search)))


class attribdict(defaultdict):
    """Default dictionary where keys can be accessed as attributes"""

    def __init__(self, *args: Any, **kwdargs: Any) -> None:
        super(attribdict, self).__init__(attribdict, *args, **kwdargs)

    def __getattribute__(self, name: Any) -> Any:
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)

    def __setattr__(self, name: Any, value: Any) -> Any:
        if name in self.keys():
            self[name] = value
            return value
        else:
            object.__setattr__(self, name, value)

    def __delattr__(self, name: Any) -> Any:
        try:
            return object.__delattr__(self, name)
        except AttributeError:
            return self.pop(name, None)

    def to_dict(self, attrib_dict: Any) -> Any:
        simple_dict = {}
        for key, value in attrib_dict.items():
            if isinstance(value, self.__class__):
                simple_dict[key] = self.to_dict(value)
            else:
                simple_dict[key] = value
        return simple_dict

    def as_dict(self) -> Any:
        return self.to_dict(self)

    def __repr__(self) -> Any:
        return f"{self.__class__.__name__}({self.to_dict(self).__repr__()})"

    def __hash__(self) -> Any:
        import copy

        def hash_helper(obj: Any) -> Any:
            if isinstance(obj, (set, tuple, list)):
                return tuple([hash_helper(element) for element in obj])

            elif not isinstance(obj, dict):
                return hash(obj)

            new_obj = {}

            for key, value in obj.items():
                new_obj[key] = hash_helper(value)

            return hash(tuple(frozenset(sorted(new_obj.items()))))

        return hash_helper(self)

    def dir(self) -> Any:
        tree_map = ["   .%s\t%s" % (key, type(value)) for key, value in self.items()]
        print("Attributes (Keys) map:\n%s" % ("\n".join(tree_map).expandtabs(30)))

    def factory(self, factory_type: Any) -> Any:
        self.default_factory = factory_type

    def lock(self) -> Any:
        self.default_factory = None

    def extract(self, search: Any) -> Any:
        """Pull all values of specified key (search)

        Attributes:
                search (Str): Search string

        Returns:
                generator
        """
        return dictextractor.extract(self, search)

    def find(self, search: Any, search_type: Any=None) -> Any:
        """Pull all objects that contain keys of specified search.

        Attributes:
                search (Str): Search string
                search_type (type) : Value type
        Returns:
                generator
        """
        return dictextractor.find(self, search, search_type)

    def where(self, search_value: Any, search_key: Any=None) -> Any:
        """Pull all objects that contain values of specified search.

        Attributes:
                search_value (Str): Search value
                search_key (Str) : Search for specific key that contains above value
        Returns:
                generator
        """
        return dictextractor.where(self, search_value, search_key)

    def contains(self, search: Any, search_type: Any=None) -> Any:
        """Does the object contain ANY value or nested object with given name (search)

        Attributes:
                search (Str): Search string
                search_type (type) : Value type

        Returns:
                Bool
        """
        return dictextractor.contains(self, search, search_type)
