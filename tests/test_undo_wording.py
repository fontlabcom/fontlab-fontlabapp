# this_file: tests/test_undo_wording.py
"""No App text claims what Undo restores (issue 122, T14i; T14g M3, G11 M7, T14h M6).

The App may say that an edit "is recorded as one Undo step" and "Check those
layers before you save." It must not promise "Edit > Undo restores ...",
"brings back" or hedge with "may not restore": no native measurement shows
what Undo restores. The measured "Undo does not restore" sentence stays.
"""

import re
from pathlib import Path

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - from-import hits the package __getattr__

SRC = Path(__file__).resolve().parents[1] / "src" / "fontlabapp"
#: An Undo claim followed by its object; "what Undo restores." has no object.
CLAIM = re.compile(r"(Undo\s+restores|brings?\s+back|Undo\s+may\s+not\s+restore)\s+\w")


def test_app_sources_when_scanned_then_no_undo_restore_claim():
    found = [
        f"{path.name}:{number}"
        for path in sorted(SRC.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if CLAIM.search(line)
    ]
    assert found == [], f"claims about what Undo restores: {found}"


def test_claim_pattern_when_old_texts_then_found():
    for text in (
        "Check Preferences > Rounding. Edit > Undo restores the font.",
        "FontLab rebuilt it and Edit > Undo may not restore it. Check it.",
        "Undo brings back the component",
    ):
        assert CLAIM.search(text), text
    assert not CLAIM.search("This module makes no claim about what Undo restores.")
    assert not CLAIM.search("Undo does not restore them")


def test_unstored_error_when_advice_then_not_stored_prefix_and_check_text():
    error = history.unstored_error(["a/top", "b/top"], "Check Preferences > Rounding.")
    assert type(error) is RuntimeError
    assert str(error) == (
        "FontLab did not store 2 change(s): a/top, b/top. "
        "Check Preferences > Rounding. Check those layers before you save."
    )
    assert str(error).startswith(history.NOT_STORED)


def test_unstored_error_when_many_then_first_six_named():
    missed = [f"g{i}" for i in range(9)]
    text = str(history.unstored_error(missed))
    assert text == f"FontLab did not store 9 change(s): {', '.join(missed[:6])}. {history.CHECK_TEXT}"
