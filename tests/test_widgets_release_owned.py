# this_file: tests/test_widgets_release_owned.py
"""``release_owned`` stops at the first refusal and records only Qt's RuntimeErrors."""

import pytest

from fontlabapp.qt.widgets import release_owned


class Part:
    """A scope, closer or owned window that logs its call and answers or raises."""

    def __init__(self, log, name, answer=True):
        self.log, self.name, self.answer = log, name, answer

    def _act(self):
        self.log.append(self.name)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer

    finish = close = _act


def parts(scope=True, closer=None, owned=True):
    log = []
    return log, Part(log, "scope", scope), Part(log, "closer", closer), Part(log, "owned", owned)


def test_release_when_everything_closes_then_true_in_order():
    log, scope, closer, owned = parts()
    problems = []
    assert release_owned(scope, owned, problems, (None, closer)) is True
    assert log == ["scope", "closer", "owned"] and problems == []


def test_release_when_nothing_owned_yet_then_true_after_scope_and_closers():
    log, scope, closer, _ = parts()
    assert release_owned(scope, None, [], (closer,)) is True
    assert log == ["scope", "closer"]


@pytest.mark.parametrize("refusal", [False, None, 0])
def test_release_when_scope_refuses_then_false_and_nothing_closes(refusal):
    log, scope, closer, owned = parts(scope=refusal)
    assert release_owned(scope, owned, [], (closer,)) is False
    assert log == ["scope"]


@pytest.mark.parametrize("refusal", [False, None, 0])
def test_release_when_owned_close_is_falsy_then_false_without_a_problem(refusal):
    log, scope, closer, owned = parts(owned=refusal)
    problems = []
    assert release_owned(scope, owned, problems, (closer,)) is False
    assert log == ["scope", "closer", "owned"] and problems == []


@pytest.mark.parametrize("answer", [False, None, 0])
def test_release_when_a_closer_returns_falsy_then_its_result_is_ignored(answer):
    log, scope, closer, owned = parts(closer=answer)
    assert release_owned(scope, owned, [], (closer,)) is True
    assert log == ["scope", "closer", "owned"]


def test_release_when_a_closer_raises_runtime_error_then_false_recorded_and_owned_kept():
    error = RuntimeError("editor refused")
    log, scope, closer, owned = parts(closer=error)
    problems = []
    assert release_owned(scope, owned, problems, (closer,)) is False
    assert log == ["scope", "closer"] and problems == [error]


def test_release_when_owned_raises_runtime_error_then_false_and_recorded():
    error = RuntimeError("deleted")
    _, scope, closer, owned = parts(owned=error)
    problems = []
    assert release_owned(scope, owned, problems, (closer,)) is False
    assert problems == [error]


def test_release_when_a_close_raises_another_error_then_it_propagates_unrecorded():
    log, scope, closer, owned = parts(closer=ValueError("bug"))
    problems = []
    with pytest.raises(ValueError, match="bug"):
        release_owned(scope, owned, problems, (closer,))
    assert log == ["scope", "closer"] and problems == []
