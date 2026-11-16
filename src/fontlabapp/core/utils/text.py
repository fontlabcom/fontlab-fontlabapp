#!/usr/bin/env python3
# this_file: src/fontlabapp/core/utils/text.py
# -*- coding: utf-8 -*-
# Copyright (c) 2022 Adam Twardoch
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

from typing import Any
try:
    from unicodedata2 import normalize  # optional extra "unicode": newer Unicode data
except ImportError:
    from unicodedata import normalize
from datetime import datetime
import re
from html import escape
from xml.dom.minidom import parseString as parse_html

try:
    from markdown import Markdown

    extensions = [
        "tables",
        "fenced_code",
        "abbr",
        "admonition",
        "attr_list",
        "def_list",
        "meta",
        "md_in_html",
    ]
    extension_configs = {}
    try:
        import pymdownx

        extensions.extend(
            [
                "pymdownx.betterem",
                "pymdownx.caret",
                "pymdownx.details",
                "pymdownx.mark",
                "pymdownx.saneheaders",
                "pymdownx.superfences",
                "pymdownx.tilde",
            ]
        )
        extension_configs.update(
            {
                "pymdownx.betterem": {"smart_enable": "all"},
                "pymdownx.caret": {
                    "insert": True,
                    "smart_insert": True,
                    "superscript": True,
                },
                "pymdownx.tilde": {
                    "delete": True,
                    "smart_delete": False,
                    "subscript": False,
                },
            }
        )
        # PyMdown's keys extension; the former mdx_steroids.keys is not on PyPI.
        extensions.extend(["pymdownx.keys"])
        extension_configs.update(
            {
                "pymdownx.keys": {
                    "camel_case": True,
                    "separator": "+",
                    "strict": False,
                }
            }
        )
    except ImportError:
        pass

    pymd = Markdown(extensions=extensions, extension_configs=extension_configs)
    qtmd = None
except ImportError:
    qtmd = None
    pymd = None

re_tab = re.compile(r"\t.*")
re_punctuation = re.compile(r'[ !"#$%\'()*\-/<=>?@\[\\\]^_`{|},.]+')


def to_pre(msg: Any) -> Any:
    return f"""<pre>{escape(msg)}\n</pre>"""


def to_html(msg: Any, md: Any=False, styled: Any=False, css: Any="") -> Any:
    if md:
        msg = _markdown_to_html(msg)
    if styled:
        msg = style_html(msg, styled, css)
    return msg.strip() + "\n"


def style_html(html: Any, styled: Any=True, css: Any="") -> Any:
    if styled:
        body_css = """body {font-family:'.AppleSystemUIFont','MS Shell Dlg 2';} p, li { white-space: pre-wrap; } p {margin-top:8px; margin-bottom:8px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; } a:link{text-decoration:none;} a:visited{text-decoration:none;} a:hover{text-decoration:underline;} a:active{text-decoration:underline;}"""
        html = f"""<html><head><meta name="qrichtext" content="1" /><style type="text/css">{body_css}</style></head><body style="{css}">{html}</body></html>"""
    return html


def _py_markdown_to_html(markdown: Any, pymd: Any) -> Any:
    html = pymd.reset().convert(markdown).strip()
    return html.strip()


def _qt_markdown_to_html(markdown: Any, qtmd: Any) -> Any:
    qtmd.setMarkdown(markdown)
    html = qtmd.toHtml()
    html = "".join(
        [t.toxml() for t in parse_html(html).getElementsByTagName("body")[0].childNodes]
    )
    return html.strip()


def _markdown_to_html(markdown: Any) -> Any:
    global qtmd
    if pymd is None and qtmd is None:
        try:
            from PythonQt.QtGui import QTextEdit
        except ModuleNotFoundError as error:
            if error.name in {"PythonQt", "PythonQt.QtGui"}:
                raise RuntimeError("Markdown conversion requires fontlab-fontlabapp[markdown] or FontLab Qt") from error
            raise
        qtmd = QTextEdit()
    html = ""
    if pymd:
        html = _py_markdown_to_html(markdown, pymd).replace("\n", "")
    elif qtmd:
        html = _qt_markdown_to_html(markdown, qtmd).replace("\n", "")
    paragraphs = parse_html("<root>" + html + "</root>").getElementsByTagName("p") if html else []
    if html and "\n" not in markdown and len(paragraphs) == 1:
        html = "".join(
            [
                t.toxml()
                for t in paragraphs[0].childNodes
            ]
        )
    return html.strip()


def slugify(text: Any, delim: Any="_") -> Any:
    """
    Generate an ASCII-only slug.
    """

    result = []
    for word in re_punctuation.split(re_tab.sub("", text.lower().replace("&", ""))):
        word = normalize("NFKD", word).encode("ascii", "ignore").decode("utf-8")

        if word:
            result.append(word)

    result = delim.join(result).replace(":_", "__")
    return result


def timestamp() -> Any:
    now = datetime.now()
    return now.strftime("%y%m%d-%H%M%S")
