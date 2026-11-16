# this_file: tests/test_regexp_tools.py
"""Immutable boundary and orchestration tests; scripted native calls are not regex engines."""

import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from fontlabapp.qt.regexp.model import Rule, evaluate


def native():
    expression = Mock()
    expression.isValid.return_value = True
    expression.errorString.return_value = "no error occurred"
    expression.indexIn.return_value = 2
    expression.matchedLength.return_value = 3
    expression.captureCount.return_value = 1
    expression.cap.side_effect = lambda index: ("abc", "bc")[index]
    factory = Mock(return_value=expression)
    for index, name in enumerate(("RegExp", "RegExp2", "Wildcard", "FixedString")):
        setattr(factory, name, index + 10)
    return NS(QRegExp=factory, Qt=NS(CaseSensitive=9, CaseInsensitive=8)), expression


@pytest.mark.parametrize("syntax", range(4))
@pytest.mark.parametrize("case", [False, True])
@pytest.mark.parametrize("minimal", [False, True])
def test_native_configuration_and_complete_original_result(syntax, case, minimal):
    core, rx = native()
    rule = Rule("(s\\w+)", syntax, case, minimal)
    payload = evaluate(core, rule, "small stones", ("A", "A.alt"))
    assert payload["pattern"] == rule.pattern and payload["escaped"] == json.dumps(
        rule.pattern
    )
    assert (
        payload["position"] == 2
        and payload["length"] == 3
        and payload["captures"] == ["abc", "bc"]
    )
    assert payload["tested_glyphs"] == 2 and [
        row["name"] for row in payload["glyph_matches"]
    ] == ["A", "A.alt"]
    rx.setPatternSyntax.assert_called_once_with(syntax + 10)
    rx.setCaseSensitivity.assert_called_once_with(9 if case else 8)
    rx.setMinimal.assert_called_once_with(minimal)


@pytest.mark.parametrize(
    "fields",
    [
        {"pattern": None},
        {"syntax": True},
        {"syntax": 4},
        {"case": 1},
        {"minimal": "yes"},
    ],
)
def test_rule_when_unreadable_then_reject_before_qt(fields):
    with pytest.raises((TypeError, ValueError)):
        Rule(**{"pattern": "A", **fields})


def test_no_match_invalid_pattern_and_empty_vocabulary_stay_explicit():
    core, rx = native()
    rx.indexIn.return_value = -1
    rx.isValid.return_value = False
    rx.errorString.return_value = "bad pattern"
    result = evaluate(core, Rule("["), "", ())
    assert result["position"] == result["length"] == -1 and result["captures"] == []
    assert (
        result["valid"] is False
        and result["error"] == "bad pattern"
        and not result["glyph_matches"]
    )
    rx.cap.assert_not_called()


@pytest.mark.parametrize("words", [["A"], ("A", "A"), ("",), ("A", None)])
def test_vocabulary_boundary_rejects_partial_or_ambiguous_input(words):
    core, _ = native()
    with pytest.raises((TypeError, ValueError)):
        evaluate(core, Rule("A"), "A", words)


def test_deadline_discards_whole_batch_and_rejects_bad_native_return(monkeypatch):
    core, rx = native()
    with pytest.raises(TimeoutError):
        evaluate(core, Rule("A"), "A", ("A",), deadline=0)
    rx.indexIn.return_value = None
    with pytest.raises(TypeError):
        evaluate(core, Rule("A"), "A", ())


@pytest.mark.parametrize(
    "method,result",
    [
        ("matchedLength", None),
        ("captureCount", True),
        ("cap", None),
        ("isValid", 1),
        ("errorString", None),
    ],
)
def test_unreadable_native_return_never_appears_as_success(method, result):
    core, rx = native()
    getattr(rx, method).side_effect = None
    getattr(rx, method).return_value = result
    with pytest.raises(TypeError):
        evaluate(core, Rule("A"), "A", ())


def test_complete_batch_rechecks_deadline_after_last_native_call(monkeypatch):
    import fontlabapp.qt.regexp.model as module

    clock = iter((0, 0, 2))
    monkeypatch.setattr(module, "monotonic", lambda: next(clock))
    core, _ = native()
    with pytest.raises(TimeoutError):
        evaluate(core, Rule("A"), "A", ("A",), deadline=1)
    with pytest.raises(TypeError):
        evaluate(core, None, "A", ())
