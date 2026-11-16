# this_file: tests/test_font_id.py
"""fontpr font addressing: every App call passes the FontGate id (issue 122, T14i).

fontpr finds a font by ``fgId`` (``mcptools.cpp:1025-1035``); ``package.id``
is the separate flObject id. The doubles give the two ids different values,
so a call with ``package.id`` fails. Offline proof only.
"""

import re
from pathlib import Path
from types import SimpleNamespace as NS

import fontlabapp.contours.raise_ascender._capture as capture
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - from-import hits the package __getattr__

SRC = Path(__file__).resolve().parents[1] / "src" / "fontlabapp"
#: A fontpr ``font_id`` built from any object's ``.id`` (``package.id``, ``pkg.id``,
#: ``self.font.id``); ``fgId`` and ``font["id"]`` (the ``get_fonts`` id) do not match.
WRONG = re.compile(r"""(?:font_id\s*=|"font_id":)\s*(?:int\()?\s*[\w.]*\.id\b""")


def test_font_id_when_ids_differ_then_fgid():
    assert scripting.font_id(NS(id=7, fgId=40)) == 40, "fontpr finds fonts by fgId"
    assert type(scripting.font_id(NS(id=7, fgId=40.0))) is int


def test_app_sources_when_scanned_then_no_font_id_from_package_id():
    found = [
        f"{path.name}:{number}"
        for path in sorted(SRC.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if WRONG.search(line)
    ]
    assert found == [], f"package.id is not a fontpr font_id: {found}"


def test_scan_pattern_when_wrong_forms_then_found():
    for line in (
        'call("get_font_info", font_id=int(package.id))',
        "call('x', font_id=package.id)",
        '"font_id": int(package.id),',
        "font_id=int(self.package.id)",
        "font_id=pkg.id",
        "font_id=int(self.font.id)",
    ):
        assert WRONG.search(line), line
    assert not WRONG.search("font_id=scripting.font_id(package)")
    assert not WRONG.search("font_id=int(package.fgId)")
    assert not WRONG.search('font_id=identifier')
    assert not WRONG.search('font_id=font["id"]')


def test_raise_ascender_masters_when_ids_differ_then_get_font_info_by_fgid(monkeypatch):
    calls = []
    data = {"masters": [{"fontMaster": {"name": "Regular", "xHeight": 500}}]}

    def call(tool, **args):
        calls.append((tool, args))
        return data

    monkeypatch.setattr(capture, "_native", lambda name: NS(call=call))
    package = NS(id=1, fgId=9, masters=["Regular"])
    assert capture.masters(package, None) == (("Regular", 500.0),)
    assert calls == [("get_font_info", {"font_id": 9})], "fontpr finds fonts by fgId"
